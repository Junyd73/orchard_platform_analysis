# -*- coding: utf-8 -*-
"""weather_detail_page.py - 날씨 상세 (기상청 단기예보 기반)"""
import os
from datetime import date, datetime, timedelta
from functools import partial
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import QObject, QThread, QTimer, Qt, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from ui.pages.dashboard_detail_base import DashboardDetailBase
from ui.styles import MainStyles
from ui.widgets.weather.weather_air_quality_card import WeatherAirQualityCard
from ui.widgets.weather.weather_hourly_chart import WeatherHourlyChart
from ui.widgets.weather.weather_metric_grid import WeatherMetricGrid
from ui.widgets.weather.weather_rain_chart import WeatherRainChart
from ui.widgets.weather.weather_sun_arc_widget import WeatherSunArcWidget
from ui.widgets.weather.weather_wind_chart import WeatherWindChart

from core.api_config import AIRKOREA_API_KEY
from core.geo_korea import wgs84_to_korea2000_central_m
from core.weather_manager import WeatherManager

def _distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine 거리(km)."""
    from math import atan2, cos, radians, sin, sqrt

    r_e = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(
        dlon / 2
    ) ** 2
    return r_e * 2 * atan2(sqrt(a), sqrt(1 - a))


def _station_candidate_distance_km(
    user_lat: float, user_lon: float, row: dict
) -> Optional[float]:
    """근접 측정소 행 → 사용자 위치까지 거리(km). dmX·dmY(경위도) 우선, 없으면 tm(거리)."""
    try:
        sx = row.get("dmX")
        sy = row.get("dmY")
        if sx is not None and sy is not None:
            slon = float(sx)
            slat = float(sy)
            return _distance_km(user_lat, user_lon, slat, slon)
    except (TypeError, ValueError):
        pass
    tm = row.get("tm")
    if tm is None:
        return None
    try:
        t = abs(float(tm))
        if t > 300:
            return t / 1000.0
        return t
    except (TypeError, ValueError):
        return None


# 한국환경공단 CAI 등급 코드 → 표시명 (워커 스레드에서 UI import 없음)
_KHAI_GRADE_NAMES = {
    "1": "좋음",
    "2": "보통",
    "3": "나쁨",
    "4": "매우 나쁨",
}


def _airkorea_parse_items(payload: dict) -> List[dict]:
    """AirKorea JSON body.items / body.item → 리스트 정규화."""

    def _normalize_item(it):
        if isinstance(it, list):
            return [x for x in it if isinstance(x, dict)]
        if isinstance(it, dict):
            return [it]
        return []

    body = payload.get("response", {}).get("body")
    if not isinstance(body, dict):
        return []

    out: List[dict] = []
    items = body.get("items")
    if isinstance(items, list):
        return [x for x in items if isinstance(x, dict)]
    if isinstance(items, dict):
        out = _normalize_item(items.get("item"))
    if not out:
        out = _normalize_item(body.get("item"))
    return out


def _airkorea_header_ok(payload: dict) -> bool:
    h = payload.get("response", {}).get("header") or {}
    c = h.get("resultCode")
    if c is None:
        return False
    return str(c).strip() in ("00", "0")


def _safe_int_air(val, default: int = 0) -> int:
    if val is None:
        return default
    s = str(val).strip()
    if s in ("", "-", ".", "측정불가", "통신장애"):
        return default
    try:
        return int(round(float(s.replace(",", ""))))
    except (TypeError, ValueError):
        return default


def _fmt_pm_display(val) -> str:
    if val is None:
        return "—"
    s = str(val).strip()
    if s in ("", "-", ".", "측정불가", "통신장애"):
        return "—"
    try:
        n = float(s.replace(",", ""))
        if n != n:  # NaN
            return "—"
        return f"{int(round(n))} µg/m³"
    except (TypeError, ValueError):
        return "—"


def _khai_grade_display(raw) -> str:
    if raw is None:
        return "—"
    s = str(raw).strip()
    if s in _KHAI_GRADE_NAMES:
        return _KHAI_GRADE_NAMES[s]
    return s if s else "—"


def _parse_airkorea_data_time(val) -> Optional[datetime]:
    """에어코리아 측정일시(공백 구분 / compact YYYYMMDDHHMM 등)."""
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    if len(s) == 12 and s.isdigit():
        try:
            return datetime.strptime(s, "%Y%m%d%H%M")
        except ValueError:
            pass
    if len(s) >= 19:
        try:
            return datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass
    if len(s) >= 16:
        try:
            return datetime.strptime(s[:16], "%Y-%m-%d %H:%M")
        except ValueError:
            pass
    return None


def _airkorea_log_header_fail(prefix: str, payload: dict) -> None:
    h = payload.get("response", {}).get("header") or {}
    print(
        f"AirKorea {prefix}: resultCode={h.get('resultCode')} "
        f"resultMsg={h.get('resultMsg')}"
    )


def _airkorea_infer_broadcast_region(lat: float, lon: float) -> Optional[str]:
    """에어코리아 통보 informGrade 권역명과 맞추기 위한 근사 격자(완벽 분할 아님)."""
    la, lo = float(lat), float(lon)
    if 33.05 <= la <= 33.65 and 125.95 <= lo <= 126.95:
        return "제주"
    if 37.42 <= la <= 37.70 and 126.76 <= lo <= 127.18:
        return "서울"
    if 37.37 <= la <= 37.72 and 126.62 <= lo <= 126.95:
        return "인천"
    if 36.70 <= la <= 38.45 and 126.60 <= lo <= 127.35:
        return "경기남부" if la < 37.55 else "경기북부"
    return None


def _airkorea_parse_region_grade(inform_grade: str, region_key: str) -> Optional[str]:
    if not inform_grade or not region_key:
        return None
    for part in inform_grade.split(","):
        p = str(part).strip()
        if region_key in p and ":" in p:
            return p.split(":", 1)[1].strip() or None
    return None


def _parse_openmeteo_hour_time(raw: str) -> Optional[datetime]:
    """Open-Meteo hourly ISO 시간 → 로컬 naive datetime."""
    s = str(raw or "").strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone().replace(tzinfo=None)
    return dt


def _fetch_openmeteo_air_forecast(lat: float, lon: float) -> List[Dict[str, Any]]:
    """Open-Meteo CAMS: 약 이후 24시간 PM2.5/PM10 모델 예보(무료, 관측 아님)."""
    try:
        import requests

        url = "https://air-quality-api.open-meteo.com/v1/air-quality"
        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": "pm2_5,pm10",
            "timezone": "Asia/Seoul",
            "forecast_days": 2,
        }
        r = requests.get(url, params=params, timeout=8)
        r.raise_for_status()
        js = r.json()
    except Exception as e:
        print(f"Open-Meteo air forecast: {e}")
        return []

    block = js.get("hourly") or {}
    hours = block.get("time") or []
    pm25s = block.get("pm2_5") or []
    pm10s = block.get("pm10") or []
    n = len(hours)
    now = datetime.now().replace(second=0, microsecond=0)
    end = now + timedelta(hours=24)
    out: List[Dict[str, Any]] = []
    for i in range(n):
        t = hours[i] if i < len(hours) else None
        dt = _parse_openmeteo_hour_time(t) if t else None
        if dt is None:
            continue
        if not (now <= dt <= end):
            continue
        p25 = pm25s[i] if i < len(pm25s) else None
        p10 = pm10s[i] if i < len(pm10s) else None
        try:
            i25 = int(round(float(p25))) if p25 is not None else 0
        except (TypeError, ValueError):
            i25 = 0
        try:
            i10 = int(round(float(p10))) if p10 is not None else 0
        except (TypeError, ValueError):
            i10 = 0
        out.append(
            {
                "time": f"{dt.hour}시",
                "pm25": max(0, i25),
                "pm10": max(0, i10),
                "_dt": dt,
            }
        )
    out.sort(key=lambda r: r["_dt"])
    for r in out:
        r.pop("_dt", None)
    return out[:24]


def _compose_air_card_payload(
    air: Optional[Dict[str, Any]],
    air_forecast: Optional[List[Dict[str, Any]]],
) -> Dict[str, Any]:
    """AirKorea 관측 + Open-Meteo 예보 + 출처 캡션을 하나의 카드 payload로."""
    forecast = [dict(x) for x in (air_forecast or [])][:24]
    st = str((air or {}).get("station") or "측정소").strip()
    lines = [
        f"현재 관측: AirKorea ({st} 측정소)",
        "24시간 예보: Open-Meteo CAMS 모델",
        "※ 예보값은 실제 관측과 차이가 있을 수 있음",
    ]
    br = (air or {}).get("broadcast_line")
    if br:
        lines.append(str(br))
    cap = "\n".join(lines)

    if not air:
        out = _air_quality_fallback_payload()
        out["forecast"] = forecast
        out["caption"] = (
            "현재 관측: 데이터 없음 (AirKorea)\n"
            "24시간 예보: Open-Meteo CAMS 모델\n"
            "※ 예보값은 실제 관측과 차이가 있을 수 있음"
        )
        return out

    merged = {
        k: v
        for k, v in air.items()
        if k not in ("station", "broadcast_line")
    }
    merged["caption"] = cap
    merged["forecast"] = forecast
    return merged


def _fetch_airkorea_broadcast_forecast_line(
    lat: float, lon: float, service_key: str
) -> Optional[str]:
    """당일 대기질 통보(권역 등급 문구). 시간별 수치 ‘예보’는 제공하지 않음."""
    key = (service_key or "").strip()
    if not key:
        return None
    try:
        import requests

        url = (
            "https://apis.data.go.kr/B552584/ArpltnInforInqireSvc/"
            "getMinuDustFrcstDspth"
        )
        r = requests.get(
            url,
            params={
                "serviceKey": key,
                "returnType": "json",
                "searchDate": datetime.now().strftime("%Y-%m-%d"),
                "ver": "1.1",
            },
            timeout=10,
        )
        r.raise_for_status()
        js = r.json()
        if not _airkorea_header_ok(js):
            return None
        items = _airkorea_parse_items(js)
        if not items:
            return None
        row = items[0]
        inform_grade = str(row.get("informGrade") or "")
        inform_overall = str(row.get("informOverall") or "").strip()
        region = _airkorea_infer_broadcast_region(lat, lon)
        if region:
            g = _airkorea_parse_region_grade(inform_grade, region)
            if g:
                return f"오늘 권역 예보({region}): {g}"
        if inform_overall:
            one = inform_overall.replace("\n", " ")
            if len(one) > 100:
                one = one[:97] + "…"
            return f"오늘 통보: {one}"
        return None
    except Exception:
        return None


def _fetch_airkorea_air_quality(lat: float, lon: float) -> Optional[Dict[str, Any]]:
    """환경공단 에어코리아 인근 측정소 + 측정 이력. 실패 시 None.

    getNearbyMsrstnList 용 tmX/tmY 는 `core.geo_korea` TM(미터)와 동일 체계를 쓴다.
    """
    print("=== 사용자 위치 ===")
    print("lat:", lat, "lon:", lon)
    service_key = (AIRKOREA_API_KEY or "").strip()
    if not service_key:
        print("AirKorea: service key missing")
        return None
    try:
        import requests

        tm_x, tm_y = wgs84_to_korea2000_central_m(lon, lat)
        print("=== TM 변환 ===")
        print("tmX:", tm_x, "tmY:", tm_y)

        url_station = (
            "https://apis.data.go.kr/B552584/MsrstnInfoInqireSvc/getNearbyMsrstnList"
        )
        params_station = {
            "serviceKey": service_key,
            "returnType": "json",
            "tmX": tm_x,
            "tmY": tm_y,
            "numOfRows": 5,
            "pageNo": 1,
            "ver": "1.1",
        }
        rs = requests.get(url_station, params=params_station, timeout=8)
        rs.raise_for_status()
        js_station = rs.json()
        if not _airkorea_header_ok(js_station):
            _airkorea_log_header_fail("station", js_station)
            return None
        near = _airkorea_parse_items(js_station)
        if not near:
            print("AirKorea: no nearby station items")
            return None

        candidates: List[tuple[float, str, dict]] = []
        for row in near[:5]:
            print("=== 측정소 raw ===")
            print("stationName:", row.get("stationName"))
            print("dmX:", row.get("dmX"), "dmY:", row.get("dmY"))
            print("tm:", row.get("tm"))

            nm = row.get("stationName")
            if nm is None or str(nm).strip() == "":
                continue
            dist = _station_candidate_distance_km(lat, lon, row)
            if dist is None:
                continue
            print("=== 거리 계산 ===")
            print("측정소:", nm)
            print("거리(km):", round(dist, 2))
            print("필터 전 거리:", dist)
            if dist > 50.0:
                print("→ 제외됨 (거리 초과)")
                continue
            candidates.append((dist, str(nm).strip(), row))

        candidates.sort(key=lambda x: x[0])
        print("=== 최종 선택 ===")
        if candidates:
            print("선택 측정소:", candidates[0][1])
            print("거리:", round(candidates[0][0], 2))
        else:
            print("선택된 측정소 없음")

        if not candidates:
            print("AirKorea: 50km 이내 유효 측정소 없음")
            return None

        station = candidates[0][1]

        url_air = (
            "https://apis.data.go.kr/B552584/ArpltnInforInqireSvc/"
            "getMsrstnAcctoRltmMesureDnsty"
        )
        params_air = {
            "serviceKey": service_key,
            "returnType": "json",
            "numOfRows": 24,
            "pageNo": 1,
            "stationName": station,
            "dataTerm": "DAILY",
            "ver": "1.0",
        }
        ra = requests.get(url_air, params=params_air, timeout=15)
        ra.raise_for_status()
        js_air = ra.json()
        if not _airkorea_header_ok(js_air):
            _airkorea_log_header_fail("air(DAILY×24)", js_air)
            return None
        items_a = _airkorea_parse_items(js_air)

        if not items_a:
            params_hour = {
                "serviceKey": service_key,
                "returnType": "json",
                "numOfRows": 24,
                "pageNo": 1,
                "stationName": station,
                "dataTerm": "HOUR",
                "ver": "1.0",
            }
            rd = requests.get(url_air, params=params_hour, timeout=10)
            rd.raise_for_status()
            js_d = rd.json()
            if _airkorea_header_ok(js_d):
                items_a = _airkorea_parse_items(js_d)

        if not items_a:
            print(f"AirKorea: empty realtime rows for station={station!r}")
            return None

        # API 기본: 최신 → 과거; 현재값 헤더는 items[0]
        d = items_a[0]

        hourly_rows: List[Dict[str, Any]] = []
        for row in items_a:
            ds = str(row.get("dataTime") or "")
            if len(ds) >= 13:
                time_label = ds[11:13] + "시"
            else:
                pdt = _parse_airkorea_data_time(ds)
                time_label = f"{pdt.hour}시" if pdt else "—"
            hourly_rows.append(
                {
                    "time": time_label,
                    "aqi": int(max(0, _safe_int_air(row.get("khaiValue"), 0))),
                    "pm25": int(max(0, _safe_int_air(row.get("pm25Value"), 0))),
                    "pm10": int(max(0, _safe_int_air(row.get("pm10Value"), 0))),
                }
            )
        # API는 최신→과거; 막대는 왼쪽=과거·오른쪽=최신이 자연스러움
        hourly_rows.reverse()

        khai = _safe_int_air(d.get("khaiValue"), 0)
        pm25_raw = d.get("pm25Value")
        pm10_raw = d.get("pm10Value")

        broadcast_line = _fetch_airkorea_broadcast_forecast_line(lat, lon, service_key)

        return {
            "aqi": khai,
            "status": _khai_grade_display(d.get("khaiGrade")),
            "pm25": _fmt_pm_display(pm25_raw),
            "pm10": _fmt_pm_display(pm10_raw),
            "station": station,
            "broadcast_line": broadcast_line,
            "hourly": hourly_rows,
        }
    except Exception as e:
        msg = str(e)
        print(f"AirKorea air quality: {e}")
        if "403" in msg:
            print(
                "→ 공공데이터포털에서 이 인증키로 「한국환경공단 에어코리아」 "
                "측정소·실시간 대기오염 API 활용 신청이 되어 있는지 확인하세요. "
                "(기상청 전용 키만 있으면 403이 납니다.)"
            )
        return None


def _air_quality_fallback_payload() -> Dict[str, Any]:
    """에어코리아 조회 실패 시 카드용."""
    return {
        "aqi": 0,
        "status": "데이터 없음",
        "pm25": "—",
        "pm10": "—",
        "caption": "대기질 데이터 없음",
        "hourly": [{"time": "—", "aqi": 0, "pm25": 0, "pm10": 0}],
        "forecast": [],
    }


class WeatherDetailWorker(QObject):
    """단기예보 슬롯만 백그라운드에서 조회(SQLite는 워커 전용 연결)."""

    finished = pyqtSignal(dict)

    def __init__(self, db_file: str, farm_cd: str):
        super().__init__()
        self._db_file = str(db_file or "orchard_platform.db")
        self._farm_cd = str(farm_cd or "").strip()

    @pyqtSlot()
    def run(self):
        db_local = None
        try:
            from core.db_manager import DBManager
            from core.weather_manager import WeatherManager

            db_local = DBManager(self._db_file)
            rows = db_local.execute_query(
                "SELECT lat, lon, nx, ny FROM m_farm_info WHERE farm_cd = ? LIMIT 1",
                (self._farm_cd,),
            )
            if not rows:
                self.finished.emit(
                    {"ok": False, "message": "위치 정보 없음", "slots": []}
                )
                return
            row = rows[0]
            rec = dict(row) if hasattr(row, "keys") else {
                "lat": row[0],
                "lon": row[1],
                "nx": row[2],
                "ny": row[3],
            }
            lat, lon, nx, ny = (
                rec.get("lat"),
                rec.get("lon"),
                rec.get("nx"),
                rec.get("ny"),
            )
            if lat is None or lon is None or nx is None or ny is None:
                self.finished.emit(
                    {"ok": False, "message": "위치 정보 없음", "slots": []}
                )
                return
            wm = WeatherManager(db_manager=db_local)
            slots = wm.get_short_forecast_slots(int(nx), int(ny), days=2)
            work_dt = date.today().isoformat()
            daily: Dict[str, Any] = {}
            try:
                merged = wm.get_weather(
                    int(nx), int(ny), work_dt, float(lat), float(lon)
                )
                if isinstance(merged, dict):
                    daily = merged
            except Exception as e:
                print(f"WeatherDetailWorker get_weather: {e}")
            air = _fetch_airkorea_air_quality(float(lat), float(lon))
            air_fc = _fetch_openmeteo_air_forecast(float(lat), float(lon))
            self.finished.emit(
                {
                    "ok": True,
                    "message": "",
                    "slots": list(slots or []),
                    "daily": daily,
                    "air": air,
                    "air_forecast": air_fc,
                }
            )
        except Exception as e:
            print(f"WeatherDetailWorker error: {e}")
            self.finished.emit(
                {"ok": False, "message": str(e) or "데이터 없음", "slots": []}
            )
        finally:
            if db_local is not None:
                try:
                    db_local.close()
                except Exception:
                    pass


class WeatherDetailPage(DashboardDetailBase):
    """날씨 상세: 단기예보 슬롯(현재시각~+24시간)"""

    def __init__(self, db_manager, session, parent=None):
        super().__init__(
            "weather",
            "날씨",
            "🌤️",
            db_manager,
            session,
            parent,
            sidebar_nav_title=None,
            content_split=(1, 0),
        )
        self.sidebar.hide()
        self.sidebar.setMinimumWidth(0)
        self.sidebar.setMaximumWidth(0)
        self._detail_seq = 0
        self._detail_thread: Optional[QThread] = None
        self._detail_worker: Optional[QObject] = None

        self._weather_status_lbl: Optional[QLabel] = None
        self._hourly_chart: Optional[WeatherHourlyChart] = None
        self._rain_chart: Optional[WeatherRainChart] = None
        self._wind_chart: Optional[WeatherWindChart] = None
        self._metric_grid: Optional[WeatherMetricGrid] = None
        self._sun_widget: Optional[WeatherSunArcWidget] = None
        self._air_card: Optional[WeatherAirQualityCard] = None

        self._apply_page_title_style()
        self._build_content()
        QTimer.singleShot(0, self._load_detail_async)

    def _build_content(self):
        self.summary_frame.hide()

        self._weather_status_lbl = QLabel("날씨 상세 데이터를 불러오는 중...")
        self._weather_status_lbl.setStyleSheet(MainStyles.TXT_CAPTION + " color:#718096;")
        self.main_layout.addWidget(self._weather_status_lbl)

        self.main_layout.setSpacing(12)
        self.main_layout.addWidget(
            self._build_section(
                "시간별 예보",
                self._build_hourly_widget(),
                "🕒",
            )
        )
        self.main_layout.addWidget(
            self._build_section(
                "시간별 강수",
                self._build_rain_widget(),
                "☔",
            )
        )
        self.main_layout.addWidget(
            self._build_section(
                "시간별 풍속 (m/s)",
                self._build_wind_widget(),
                "🌬️",
            )
        )
        mid_row = QHBoxLayout()
        mid_row.setContentsMargins(0, 0, 0, 0)
        mid_row.setSpacing(12)
        mid_row.addWidget(
            self._build_section(
                "현재 상세 날씨",
                self._build_metric_widget(),
                "🌤️",
            ),
            1,
        )
        mid_row.addWidget(
            self._build_section(
                "일출 / 일몰",
                self._build_sun_arc_widget(),
                "🌅",
            ),
            1,
        )
        self.main_layout.addLayout(mid_row)
        self.main_layout.addWidget(
            self._build_section(
                "대기질",
                self._build_air_quality_widget(),
                "🌫️",
            )
        )
        self.main_layout.addStretch()

    def _build_section(self, title: str, inner_widget, icon: str = ""):
        host = QFrame()
        host.setStyleSheet(MainStyles.CARD + " QLabel { border:none; background:transparent; }")
        lay = QVBoxLayout(host)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)

        title_text = f"{icon} {title}" if icon else str(title or "")
        lbl = QLabel(title_text)
        lbl.setStyleSheet(MainStyles.TXT_CARD_TITLE + " border:none; background:transparent;")
        lay.addWidget(lbl)
        lay.addWidget(inner_widget)
        return host

    def _apply_page_title_style(self):
        page_title = f"{self._icon} {self._title}"
        for lbl in self.findChildren(QLabel):
            if lbl.text() == page_title:
                lbl.setStyleSheet(
                    MainStyles.PAGE_LBL_TITLE + " border:none; background:transparent;"
                )
                break

    def _build_hourly_widget(self):
        chart = WeatherHourlyChart()
        chart.setMinimumHeight(150)
        chart.set_data([])
        self._hourly_chart = chart
        return chart

    def _build_rain_widget(self):
        chart = WeatherRainChart()
        chart.setMinimumHeight(130)
        chart.set_data([])
        self._rain_chart = chart
        return chart

    def _build_wind_widget(self):
        chart = WeatherWindChart()
        chart.setMinimumHeight(130)
        chart.set_data([])
        self._wind_chart = chart
        return chart

    def _build_metric_widget(self):
        grid = WeatherMetricGrid(columns=3)
        grid.set_data(self._empty_metric_payload())
        self._metric_grid = grid
        return grid

    @staticmethod
    def _empty_metric_payload() -> Dict[str, str]:
        return {
            "temp": "—",
            "feels_like": "—",
            "rain": "—",
            "wind": "—",
            "humidity": "—",
            "pressure": "—",
        }

    def _build_air_quality_widget(self):
        card = WeatherAirQualityCard(embedded=True)
        card.set_data(self._air_quality_placeholder())
        self._air_card = card
        return card

    @staticmethod
    def _air_quality_placeholder() -> dict:
        """초기·오류 시(24h 가짜 막대 방지: 1행)."""
        return {
            "aqi": 0,
            "status": "데이터 없음",
            "caption": "대기질 정보를 불러오는 중이거나 연결되지 않았습니다.",
            "pm25": "—",
            "pm10": "—",
            "hourly": [
                {"time": "—", "aqi": 0, "pm25": 0, "pm10": 0},
            ],
            "forecast": [],
        }

    def _build_sun_arc_widget(self):
        sun = WeatherSunArcWidget()
        sun.setMinimumHeight(290)
        sun.set_data({})
        self._sun_widget = sun
        return sun

    @staticmethod
    def _filter_next_24h_slots(slots: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        now = datetime.now()
        end = now + timedelta(hours=24)
        filtered: List[Dict[str, Any]] = []
        for row in slots or []:
            try:
                d = str(row.get("date") or "").strip()
                t = str(row.get("time") or "").strip().zfill(4)
                if len(t) != 4:
                    continue
                dt = datetime.strptime(f"{d} {t}", "%Y-%m-%d %H%M")
                if now <= dt <= end:
                    filtered.append(row)
            except Exception:
                continue
        return filtered

    @staticmethod
    def _format_slot_time_label(row: Dict[str, Any]) -> str:
        t = str(row.get("time") or "").strip().zfill(4)
        if len(t) >= 4:
            try:
                return f"{int(t[:2])}시"
            except ValueError:
                pass
        return "—"

    @staticmethod
    def _icon_from_slot(row: Dict[str, Any]) -> str:
        try:
            pop = int(row.get("pop") or 0)
        except (TypeError, ValueError):
            pop = 0
        try:
            pcp = float(row.get("pcp") or 0.0)
        except (TypeError, ValueError):
            pcp = 0.0
        if pcp >= 1.0 or pop >= 70:
            return "rain"
        if pop >= 50:
            return "cloud"
        if pop >= 30:
            return "partly_cloudy"
        try:
            hh = int(str(row.get("time") or "1200")[:2])
        except ValueError:
            hh = 12
        if 6 <= hh <= 18:
            return "sun"
        return "moon"

    def _slots_to_hourly_rows(self, slots: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """강수 차트와 동일한 슬롯 개수·순서 유지(tmp 없으면 temp 생략 → 위젯에서 해당 칸만 선 생략)."""
        rows = []
        for s in slots:
            row: Dict[str, Any] = {
                "time": self._format_slot_time_label(s),
                "icon": self._icon_from_slot(s),
            }
            tmp = s.get("tmp")
            try:
                if tmp is not None:
                    row["temp"] = float(tmp)
            except (TypeError, ValueError):
                pass
            rows.append(row)
        return rows

    def _slots_to_rain_rows(self, slots: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """강수량(PCP, mm) — WeatherRainChart `rain`은 mm 스케일(0이면 막대 최소/기본 위젯 동작)."""
        rows = []
        for s in slots:
            # 슬롯 pcp는 API 보정 전 문자열일 수 있음 — KMA PCP 파서 재사용(WM 파일 미수정)
            rain_val = WeatherManager._parse_kma_pcp_mm(s.get("pcp"))
            rows.append(
                {
                    "time": self._format_slot_time_label(s),
                    "rain": rain_val,
                    "pop": s.get("pop"),
                }
            )
        return rows

    def _slots_to_wind_rows(self, slots: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """단기예보 WSD(m/s) — 강수와 동일 슬롯 순서."""
        rows = []
        for s in slots:
            wsd = s.get("wsd")
            try:
                wind_val = float(wsd) if wsd is not None else 0.0
            except (TypeError, ValueError):
                wind_val = 0.0
            rows.append(
                {
                    "time": self._format_slot_time_label(s),
                    "wind": max(0.0, wind_val),
                }
            )
        return rows

    def _metric_from_slots(self, slots: List[Dict[str, Any]]) -> Dict[str, str]:
        base = self._empty_metric_payload()
        if not slots:
            return base
        cur = slots[0]
        tmp = cur.get("tmp")
        if tmp is not None:
            try:
                base["temp"] = f"{int(round(float(tmp)))}℃"
            except (TypeError, ValueError):
                pass
        try:
            pcp = cur.get("pcp")
            if pcp is not None:
                base["rain"] = f"{float(pcp):.1f}mm"
        except (TypeError, ValueError):
            pass
        try:
            wsd = cur.get("wsd")
            if wsd is not None:
                base["wind"] = f"{float(wsd):.1f}m/s"
        except (TypeError, ValueError):
            pass
        return base

    @staticmethod
    def _approx_feels_like_c(
        temp_c: Optional[float], wind_ms: Optional[float], rh: Optional[int]
    ) -> Optional[float]:
        """단기 슬롯 기온·풍속 + 일별 습도로 단순 체감 추정(별도 API 없을 때)."""
        if temp_c is None:
            return None
        try:
            t = float(temp_c)
            w = max(0.0, float(wind_ms or 0))
        except (TypeError, ValueError):
            return None
        if t < 16:
            feels = t - min(w * 0.55, 10.0)
        else:
            feels = t - min(w * 0.35, 6.0)
        if rh is not None and rh >= 65 and t >= 28:
            feels += (rh - 65) * 0.08
        return round(max(-35.0, min(48.0, feels)), 1)

    def _metric_from_slots_and_daily(
        self, slots: List[Dict[str, Any]], daily: Dict[str, Any]
    ) -> Dict[str, str]:
        base = self._metric_from_slots(slots) if slots else self._empty_metric_payload()
        if not daily:
            return base
        hi: Optional[int] = None
        hum_raw = daily.get("humidity")
        try:
            if hum_raw is not None:
                hi = int(round(float(hum_raw)))
                if hi > 0:
                    base["humidity"] = f"{hi}%"
        except (TypeError, ValueError):
            hi = None
        cur = slots[0] if slots else {}
        tmp: Optional[float] = None
        wsd: Optional[float] = None
        try:
            if cur.get("tmp") is not None:
                tmp = float(cur["tmp"])
        except (TypeError, ValueError):
            pass
        try:
            if cur.get("wsd") is not None:
                wsd = float(cur["wsd"])
        except (TypeError, ValueError):
            pass
        fl = self._approx_feels_like_c(tmp, wsd, hi)
        if fl is not None:
            base["feels_like"] = f"{fl:.1f}℃"
        return base

    def _apply_context_panels(
        self,
        daily: Dict[str, Any],
        air_pl: Optional[Dict[str, Any]],
        air_forecast: Optional[List[Dict[str, Any]]],
        slots: List[Dict[str, Any]],
    ) -> None:
        """일출·일몰, 대기질, 상세 수치(습도·체감) 반영. 기압은 API 미연동으로 — 유지."""
        if self._sun_widget is not None:
            sr = str(daily.get("sun_rise") or "").strip()
            ss = str(daily.get("sun_set") or "").strip()
            if sr and ss:
                self._sun_widget.set_data({"sunrise": sr, "sunset": ss})
            else:
                self._sun_widget.set_data({})
        if self._air_card is not None:
            self._air_card.set_data(_compose_air_card_payload(air_pl, air_forecast))
        if self._metric_grid is not None:
            self._metric_grid.set_data(self._metric_from_slots_and_daily(slots, daily))

    def _load_detail_async(self):
        if self._detail_thread is not None and self._detail_thread.isRunning():
            return
        self._detail_seq += 1
        seq = self._detail_seq
        db_file = (
            os.path.basename(self.db.db_name)
            if getattr(self.db, "db_name", None)
            else "orchard_platform.db"
        )
        farm = str(self.farm_cd or "").strip()

        thread = QThread()
        worker = WeatherDetailWorker(db_file, farm)
        worker.moveToThread(thread)

        self._detail_thread = thread
        self._detail_worker = worker

        thread.started.connect(worker.run)
        worker.finished.connect(partial(self._on_detail_loaded, seq, thread, worker))

        thread.start()

    def _on_detail_loaded(
        self,
        seq: int,
        thread: QThread,
        worker: QObject,
        payload: dict,
    ):
        try:
            if seq != self._detail_seq:
                return
            ok = bool(payload.get("ok"))
            message = str(payload.get("message") or "")
            raw_slots: List[Dict[str, Any]] = list(payload.get("slots") or [])
            daily: Dict[str, Any] = dict(payload.get("daily") or {})
            air_pl: Optional[Dict[str, Any]] = payload.get("air")

            if not ok:
                if self._weather_status_lbl is not None:
                    self._weather_status_lbl.setText(message or "데이터 없음")
                    self._weather_status_lbl.setVisible(True)
                if self._hourly_chart:
                    self._hourly_chart.set_data([])
                if self._rain_chart:
                    self._rain_chart.set_data([])
                if self._wind_chart:
                    self._wind_chart.set_data([])
                if self._sun_widget:
                    self._sun_widget.set_data({})
                if self._air_card:
                    self._air_card.set_data(self._air_quality_placeholder())
                if self._metric_grid:
                    self._metric_grid.set_data(self._empty_metric_payload())
                return

            slots = self._filter_next_24h_slots(raw_slots)
            air_fc = payload.get("air_forecast")
            self._apply_context_panels(daily, air_pl, air_fc, slots)

            if not slots:
                if self._weather_status_lbl is not None:
                    self._weather_status_lbl.setText(
                        "현재~24시간 구간에 표시할 단기예보가 없습니다."
                    )
                    self._weather_status_lbl.setVisible(True)
                if self._hourly_chart:
                    self._hourly_chart.set_data([])
                if self._rain_chart:
                    self._rain_chart.set_data([])
                if self._wind_chart:
                    self._wind_chart.set_data([])
                return

            if self._weather_status_lbl is not None:
                self._weather_status_lbl.setText("")
                self._weather_status_lbl.setVisible(False)

            hourly = self._slots_to_hourly_rows(slots)
            rain = self._slots_to_rain_rows(slots)
            wind = self._slots_to_wind_rows(slots)
            if self._hourly_chart:
                self._hourly_chart.set_data(hourly)
            if self._rain_chart:
                self._rain_chart.set_data(rain)
            if self._wind_chart:
                self._wind_chart.set_data(wind)
        finally:
            thread.quit()
            thread.wait()
            worker.deleteLater()
            thread.deleteLater()
            if self._detail_thread is thread:
                self._detail_thread = None
                self._detail_worker = None

    def _build_sidebar(self):
        return
