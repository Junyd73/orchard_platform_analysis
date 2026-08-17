import json
import math
import re
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import requests
from core.api_config import (
    AGRI_OBSR_CODE,
    KMA_MID_LAND_REG_ID,
    KMA_MID_TA_REG_ID,
    WEATHER_API_KEY,
)
from core.kma_mid_region_map import resolve_kma_mid_region_codes
from core.ops_biz_date import now_ops, today_ops

# OPEN API 기술명세: 농업기상 기본 관측데이터 V3 — GnrlWeather / getWeatherYearDayList3
AGRI_WEATHER_YEAR_DAY_URL = (
    "https://apis.data.go.kr/1390802/AgriWeather/WeatherObsrInfo/V3/GnrlWeather/"
    "getWeatherYearDayList3"
)
KMA_MID_LAND_FCST_URL = "https://apis.data.go.kr/1360000/MidFcstInfoService/getMidLandFcst"
KMA_MID_TA_URL = "https://apis.data.go.kr/1360000/MidFcstInfoService/getMidTa"

# 외부 HTTP: 연결·응답 타임아웃 (초). 무제한 대기 금지.
WEATHER_HTTP_CONNECT_TIMEOUT = 2.0
WEATHER_HTTP_READ_TIMEOUT = 5.0
WEATHER_HTTP_TIMEOUT = (WEATHER_HTTP_CONNECT_TIMEOUT, WEATHER_HTTP_READ_TIMEOUT)
# 오늘 캐시 유효시간(초)
WORK_LOG_WEATHER_TODAY_TTL_SEC = 3600
# 영농일지 세션 메모리 캐시 (farm|dt|nx|ny)
_WORK_LOG_WEATHER_MEM_CACHE: Dict[str, Dict[str, Any]] = {}

# 모바일 날씨 상세 — 단기/주간/시간별 범위
MOBILE_DETAIL_SHORT_DAYS = 4
MOBILE_DETAIL_WEEKLY_DAYS = 7
MOBILE_DETAIL_HOURLY_HOURS = 24
MOBILE_DETAIL_SUN_MARKER_SUNRISE = "sunrise"
MOBILE_DETAIL_SUN_MARKER_SUNSET = "sunset"
MOBILE_DETAIL_SOURCE_SHORT = "short"
MOBILE_DETAIL_SOURCE_MID = "mid"


class WeatherManager:
    def __init__(self, service_key=None, db_manager=None):
        # 키는 core에서 일원화 관리(인자 미전달 시 기본키/환경변수 사용)
        self.service_key = service_key or WEATHER_API_KEY
        self.db = db_manager
        self.base_url = "http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst"
        self.agri_obsr_code = AGRI_OBSR_CODE
        self.mid_land_fcst_url = KMA_MID_LAND_FCST_URL
        self.mid_ta_url = KMA_MID_TA_URL
        # 1회 실행 내 중복 호출 최소화용 런타임 캐시
        self._agri_year_cache: Dict[int, List[dict]] = {}
        self._quota_exceeded = False
        self._weather_error_code: Optional[str] = None
        self._weather_error_msg: Optional[str] = None
        self._cache_date = None
        self._cache_data = None
        self._http_session: Optional[requests.Session] = None
        if self.db:
            try:
                self._ensure_weather_cache_table()
            except Exception:
                pass

    def _ensure_http_session(self) -> requests.Session:
        if self._http_session is None:
            self._http_session = requests.Session()
        return self._http_session

    def _http_get(self, url: str, params: dict) -> requests.Response:
        """연결/응답 타임아웃 명시. 네트워크 일시 오류만 최대 1회 재시도."""
        session = self._ensure_http_session()
        last_exc: Optional[Exception] = None
        for attempt in range(2):
            try:
                return session.get(url, params=params, timeout=WEATHER_HTTP_TIMEOUT)
            except (requests.Timeout, requests.ConnectionError) as e:
                last_exc = e
                if attempt == 0:
                    continue
                raise
        if last_exc:
            raise last_exc
        raise requests.ConnectionError("weather http failed")

    def _ensure_weather_cache_table(self) -> None:
        if not self.db:
            return
        sql = """
            CREATE TABLE IF NOT EXISTS t_weather_cache (
                farm_cd TEXT,
                weather_dt TEXT,
                weather_json TEXT,
                reg_dt TEXT,
                PRIMARY KEY (farm_cd, weather_dt)
            )
        """
        self.db.execute_query(sql)

    def _get_weather_from_db(self, farm_cd: str, date_str: str) -> Optional[Dict[str, Any]]:
        if not self.db:
            return None
        sql = """
            SELECT weather_json
            FROM t_weather_cache
            WHERE farm_cd = ? AND weather_dt = ?
        """
        try:
            res = self.db.execute_query(sql, (farm_cd, date_str))
            if not res:
                return None
            row = res[0]
            raw = row["weather_json"] if hasattr(row, "keys") else row[0]
            if raw is None or str(raw).strip() == "":
                return None
            data = json.loads(raw)
            return data if isinstance(data, dict) else None
        except Exception:
            return None

    def _save_weather_to_db(self, farm_cd: str, date_str: str, data: Dict[str, Any]) -> None:
        if not self.db or not data:
            return
        sql = """
            INSERT OR REPLACE INTO t_weather_cache
            (farm_cd, weather_dt, weather_json, reg_dt)
            VALUES (?, ?, ?, ?)
        """
        self.db.execute_query(
            sql,
            (
                farm_cd,
                date_str,
                json.dumps(data, ensure_ascii=False),
                now_ops().strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )

    @staticmethod
    def _normalize_dashboard_date_str(target_date: Any) -> str:
        if hasattr(target_date, "strftime"):
            return target_date.strftime("%Y-%m-%d")
        s = str(target_date or "").strip()
        return s[:10] if len(s) >= 10 else s

    def _record_weather_error(self, code: str, msg: Optional[str] = None) -> None:
        """실패 원인 추적용 코드 저장(기존 값 유지, 429는 최우선)."""
        c = str(code or "").strip()
        m = str(msg or "").strip() or None
        if not c:
            return
        if c == "429":
            self._weather_error_code = "429"
            self._weather_error_msg = m or "API token quota exceeded"
            return
        if not self._weather_error_code:
            self._weather_error_code = c
            self._weather_error_msg = m

    @staticmethod
    def _tag_local(tag: str) -> str:
        if not tag:
            return ""
        return tag.split("}")[-1]

    @staticmethod
    def _safe_float(val, default=0.0):
        if val is None or val == "":
            return default
        try:
            return float(str(val).strip())
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _safe_int(val, default=0):
        if val is None or val == "":
            return default
        try:
            return int(float(str(val).strip()))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _parse_kma_pcp_mm(val) -> float:
        """단기예보 PCP fcstValue — 숫자, '강수없음', 'nmm', '1mm미만' 등."""
        if val is None:
            return 0.0
        s = str(val).strip()
        if not s or "강수없음" in s:
            return 0.0
        try:
            return max(0.0, float(s))
        except ValueError:
            pass
        low = s.lower()
        if "mm" in low:
            s = re.sub(r"mm.*", "", s, flags=re.I).strip()
        m = re.search(r"(\d+\.?\d*)", s.replace(",", ""))
        if not m:
            return 0.0
        n = float(m.group(1))
        if "미만" in val and n >= 1.0:
            n = min(n * 0.5, 0.9)
        return max(0.0, n)

    def _agri_first_float(self, row: dict, keys: tuple, default: float) -> float:
        """V3 명세 필드명 우선, 구버전/별칭 fallback."""
        for k in keys:
            if k not in row:
                continue
            v = row.get(k)
            if v is None or str(v).strip() == "":
                continue
            return self._safe_float(v, default)
        return default

    def _agri_first_int(self, row: dict, keys: tuple, default: int = 0) -> int:
        for k in keys:
            if k not in row:
                continue
            v = row.get(k)
            if v is None or str(v).strip() == "":
                continue
            return self._safe_int(v, default)
        return default

    def _make_default_weather(self, lat, lon, work_dt):
        """API 모두 실패 시 UI/저장용 최소 구조( None 미반환 )."""
        sr_str, ss_str, sr_h, ss_h = self.calculate_sun_times_korea(lat, lon, work_dt)
        return {
            "temp_max": -99.0,
            "temp_min": 99.0,
            "humidity": 0,
            "precip": 0.0,
            "wind_max": 0.0,
            "wind_min": 0.0,
            "sun_rise": sr_str,
            "sun_set": ss_str,
            "sunshine_hr": 0.0,
            "weather_cd": "WT019900",
            "raw_info": "DEFAULT",
        }

    def _get_agri_weather(self, work_dt, lat, lon):
        """
        농업기상 기본 관측 일별(연도별) API — 과거 일자 1일분.
        성공 시 dict, 실패 시 None.
        (상세·AI 등 공용 — 연도 리스트 캐시 유지)
        """
        if not (work_dt or "").strip():
            return None
        ds = str(work_dt).strip().replace("-", "")
        if len(ds) != 8 or not ds.isdigit():
            return None
        year = int(ds[:4])
        items = self._fetch_agri_year_item_list(year)
        row = self._pick_agri_day_row(items, ds) if items else None
        if row:
            return self._map_agri_row_to_result(row, lat, lon, work_dt)
        return None

    def _get_agri_weather_dashboard_fast(self, work_dt, lat, lon):
        """단건 일자 FAST: 연중 일수로 시작 페이지를 추정해 왕복을 줄인다."""
        if not (work_dt or "").strip():
            return None
        ds = str(work_dt).strip().replace("-", "")
        if len(ds) != 8 or not ds.isdigit():
            return None
        year = int(ds[:4])
        try:
            target = datetime.strptime(ds, "%Y%m%d").date()
            doy = (target - date(year, 1, 1)).days + 1
        except Exception:
            doy = 1
        # Page_Size=100 기준 대략 일수→페이지
        start_page = max(1, (doy - 1) // 100 + 1)
        # 예상 페이지 전후를 우선 조회 후, 앞에서부터 보조 검색
        pages = []
        for p in range(start_page, start_page + 4):
            if p not in pages:
                pages.append(p)
        for p in range(max(1, start_page - 2), start_page):
            if p not in pages:
                pages.append(p)
        for p in range(1, 16):
            if p not in pages:
                pages.append(p)

        acc: List[dict] = []
        for page in pages[:12]:
            chunk = self._agri_fetch_page_raw_items(year, page)
            if not chunk:
                continue
            acc.extend(chunk)
            row = self._pick_agri_day_row(acc, ds)
            if row:
                # 부분 누적을 연도 캐시에 보강(다음 호출 가속)
                if year not in self._agri_year_cache:
                    self._agri_year_cache[year] = list(acc)
                return self._map_agri_row_to_result(row, lat, lon, work_dt)
        return None

    def _agri_fetch_page_raw_items(self, year: int, page: int) -> List[dict]:
        """농업기상 일별 API 한 페이지의 item 전체(JSON·XML 공통). 실패 시 []."""
        if self._quota_exceeded:
            return []
        params = {
            "serviceKey": self.service_key,
            "Page_No": str(page),
            "Page_Size": "100",
            "obsr_Spot_Cd": self.agri_obsr_code,
            "search_Year": str(year),
        }
        try:
            r = self._http_get(AGRI_WEATHER_YEAR_DAY_URL, params)
            text = r.text or ""
            if r.status_code == 429 or "quota exceeded" in text.lower():
                self._quota_exceeded = True
                self._weather_error_code = "429"
                self._weather_error_msg = "API token quota exceeded"
                return []
            if not text.strip():
                return []
            if text.strip().startswith("{"):
                try:
                    data = r.json()
                except Exception:
                    return []
                code = (
                    str(
                        data.get("response", {})
                        .get("header", {})
                        .get("resultCode", "")
                    ).strip()
                )
                if code and code != "00":
                    self._weather_error_code = code
                    self._weather_error_msg = str(
                        data.get("response", {})
                        .get("header", {})
                        .get("resultMsg", "")
                    ).strip() or None
                    return []
                body = data.get("response", {}).get("body", {}) or {}
                items_wrap = body.get("items")
                if isinstance(items_wrap, dict):
                    item_list = items_wrap.get("item")
                else:
                    item_list = None
                if item_list is None:
                    return []
                if isinstance(item_list, dict):
                    return [item_list]
                return list(item_list)
            try:
                root = ET.fromstring(text.encode("utf-8"))
            except Exception:
                try:
                    root = ET.fromstring(text)
                except Exception:
                    return []
            hdr = None
            for el in root.iter():
                if self._tag_local(el.tag) == "resultCode":
                    hdr = (el.text or "").strip()
                    break
            if hdr and hdr != "00":
                self._weather_error_code = hdr
                return []
            items: List[dict] = []
            for el in root.iter():
                if self._tag_local(el.tag) == "item":
                    d = {}
                    for ch in el:
                        d[self._tag_local(ch.tag)] = (ch.text or "").strip()
                    items.append(d)
            return items
        except Exception:
            self._weather_error_code = "999"
            self._weather_error_msg = "agri fetch exception"
            return []

    def _fetch_agri_year_item_list(self, year: int) -> List[dict]:
        """관측소·연도 기준 일별 item 누적(페이징). 짧은 기간 조회 시 API 왕복 최소화."""
        if year in self._agri_year_cache:
            return list(self._agri_year_cache.get(year) or [])
        acc: List[dict] = []
        for page in range(1, 40):
            chunk = self._agri_fetch_page_raw_items(year, page)
            if not chunk:
                break
            acc.extend(chunk)
        self._agri_year_cache[year] = list(acc)
        return list(acc)

    def _weather_result_is_trustworthy(self, res: dict) -> bool:
        """기본 더미(DEFAULT)·무효 온도가 아니면 실측/예보로 간주."""
        if not res:
            return False
        raw = str(res.get("raw_info") or "")
        if raw.upper().startswith("DEFAULT"):
            return False
        return self._forecast_temps_valid(res)

    def aggregate_period_for_recommendation(
        self,
        nx: int,
        ny: int,
        lat: float,
        lon: float,
        d_start: date,
        d_end: date,
    ) -> Dict[str, Any]:
        """
        최근 구간 일자별로 공공 API(농업기상 일별 + get_weather 병합) 집계.
        반환 키는 pesticide_ai_recommend_manager.get_weather_summary 와 동일.
        """
        defaults: Dict[str, Any] = {
            "avg_temp_3d": 28.0,
            "rain_sum_7d": 45.0,
            "rain_days_7d": 4,
            "avg_humidity_7d": 82.0,
            "weather_trace_ok": False,
            "weather_source": "default",
            "weather_error_code": None,
            "weather_error_msg": None,
        }
        if d_end < d_start:
            return dict(defaults)

        dates: List[date] = []
        cur = d_start
        while cur <= d_end:
            dates.append(cur)
            cur += timedelta(days=1)

        years = sorted({d.year for d in dates})
        agri_cache: Dict[int, List[dict]] = {y: self._fetch_agri_year_item_list(y) for y in years}

        d3 = d_end - timedelta(days=3)
        temps_3d: List[float] = []
        rain_sum = 0.0
        rain_days = 0
        hums: List[float] = []
        trustworthy_days = 0

        for d in dates:
            ds = d.isoformat()
            ymd = ds.replace("-", "")
            items = agri_cache.get(d.year) or []
            row = self._pick_agri_day_row(items, ymd) if items else None
            if row:
                res = self._map_agri_row_to_result(row, lat, lon, ds)
            else:
                res = None
            if res is None or not self._forecast_temps_valid(res):
                res = self.get_weather(nx, ny, ds, lat, lon)

            if self._weather_result_is_trustworthy(res):
                trustworthy_days += 1

            pr = float(res.get("precip") or 0)
            rain_sum += pr
            if pr > 0:
                rain_days += 1

            hu = res.get("humidity")
            if hu is not None:
                try:
                    hums.append(float(hu))
                except (TypeError, ValueError):
                    pass

            if self._forecast_temps_valid(res) and d >= d3:
                try:
                    ta = (float(res["temp_max"]) + float(res["temp_min"])) / 2.0
                    temps_3d.append(ta)
                except (TypeError, ValueError, KeyError):
                    pass

        if trustworthy_days == 0:
            out = dict(defaults)
            out["weather_source"] = "default"
            out["weather_error_code"] = self._weather_error_code
            out["weather_error_msg"] = self._weather_error_msg
            return out

        avg_temp_3d = (
            sum(temps_3d) / len(temps_3d) if temps_3d else defaults["avg_temp_3d"]
        )
        avg_humidity_7d = (
            sum(hums) / len(hums) if hums else defaults["avg_humidity_7d"]
        )
        return {
            "avg_temp_3d": float(avg_temp_3d),
            "rain_sum_7d": float(rain_sum),
            "rain_days_7d": int(rain_days),
            "avg_humidity_7d": float(avg_humidity_7d),
            "weather_trace_ok": True,
            "weather_source": "api",
            "weather_error_code": None,
            "weather_error_msg": None,
        }

    def _pick_agri_day_row(self, items, yyyymmdd):
        """item 리스트에서 date가 조회일과 일치하는 행."""
        for it in items:
            if not isinstance(it, dict):
                continue
            raw = (
                it.get("date")
                or it.get("Date")
                or it.get("obsrvn_Ymd")
                or it.get("obsrvn_dt")
                or it.get("OBSR_DT")
                or ""
            )
            raw = str(raw).strip()
            norm = raw.replace("-", "")[:8]
            if norm == yyyymmdd:
                return it
        return None

    def _map_agri_row_to_result(self, row, lat, lon, work_dt):
        # V3 명세: hghst_Artmp, lowst_Artmp, hum, rn, max_Wind, wind, sun_Time
        tmax = self._agri_first_float(
            row,
            (
                "hghst_Artmp",
                "max_Temp",
                "max_temp",
                "TEMP_MAX",
            ),
            -99.0,
        )
        tmin = self._agri_first_float(
            row,
            (
                "lowst_Artmp",
                "min_Temp",
                "min_temp",
                "TEMP_MIN",
            ),
            99.0,
        )
        hum = self._agri_first_int(row, ("hum", "HUM", "humidity"), 0)
        rain = self._agri_first_float(
            row,
            (
                "rn",
                "Rf",
                "rf",
                "RN",
                "day_Rn",
                "day_rn",
                "acmlRn",
                "rain",
                "RAIN",
                "rainfall",
            ),
            0.0,
        )
        wmax = self._agri_first_float(
            row,
            ("max_Wind", "max_wind", "MAX_WIND"),
            0.0,
        )
        wmin = self._agri_first_float(
            row,
            ("wind", "WIND", "wind_spd"),
            0.0,
        )
        sun_t = self._agri_first_float(
            row,
            ("sun_Time", "sun_time", "SUN_TIME"),
            0.0,
        )
        sr_str, ss_str, sr_h, ss_h = self.calculate_sun_times_korea(lat, lon, work_dt)
        pty = "1" if rain > 0 else "0"
        sky = "1"
        if hum >= 80:
            sky = "3"
        if rain > 5:
            sky = "4"
        extra_bits = []
        for k in ("temp", "srqty", "condens_Time", "gr_Temp", "soil_Temp", "soil_Wt"):
            v = row.get(k)
            if v is not None and str(v).strip() != "":
                extra_bits.append(f"{k}:{v}")
        extra_raw = ("; " + ", ".join(extra_bits)) if extra_bits else ""
        res = {
            "temp_max": tmax if tmax > -90 else -99.0,
            "temp_min": tmin if tmin < 90 else 99.0,
            "humidity": hum,
            "precip": rain,
            "wind_max": wmax if wmax > 0 else 0.0,
            "wind_min": wmin if wmin > 0 else 0.0,
            "sun_rise": sr_str,
            "sun_set": ss_str,
            "sunshine_hr": round(sun_t, 1) if sun_t > 0 else 0.0,
            "weather_cd": self.match_weather_code_db(sky, pty),
            "raw_info": (
                f"HGHST:{tmax},LOWST:{tmin},HUM:{hum},RN:{rain},"
                f"MAX_W:{wmax},WIND:{wmin},SUN:{sun_t},SRC:AGRI_V3{extra_raw}"
            ),
        }
        return res

    @staticmethod
    def _forecast_temps_valid(res: dict) -> bool:
        """단기예보/병합 결과에 실온 역이 있으면 True(-99/99 는 무실데이터)."""
        try:
            tmax = float(res.get("temp_max", -99))
            tmin = float(res.get("temp_min", 99))
        except (TypeError, ValueError):
            return False
        return tmax > -90.0 and tmin < 90.0

    def _parse_vilage_items_to_res(
        self, items, target_fcst_date: str, work_dt: str, lat, lon, base_tag: str
    ):
        """item 리스트·단일 dict 모두 처리. target_fcst_date: yyyymmdd."""
        if items is None:
            return None
        if isinstance(items, dict):
            item_list = [items]
        else:
            item_list = list(items)
        sr_str, ss_str, sr_h, ss_h = self.calculate_sun_times_korea(lat, lon, work_dt)
        wsd_list = []
        sky_list = []
        precip_sum = 0.0
        res = {
            "temp_max": -99.0,
            "temp_min": 99.0,
            "humidity": 0,
            "precip": 0.0,
            "wind_max": 0.0,
            "wind_min": 99.0,
            "sun_rise": sr_str,
            "sun_set": ss_str,
            "sunshine_hr": 0.0,
            "weather_cd": "WT010100",
            "raw_info": "",
        }
        for item in item_list:
            if item.get("fcstDate") != target_fcst_date:
                continue
            cat, val = item.get("category"), item.get("fcstValue")
            if cat == "WSD":
                try:
                    wsd_list.append(float(val))
                except (TypeError, ValueError):
                    pass
            if cat == "SKY":
                sky_list.append(val)
            if cat == "TMX":
                try:
                    res["temp_max"] = float(val)
                except (TypeError, ValueError):
                    pass
            if cat == "TMN":
                try:
                    res["temp_min"] = float(val)
                except (TypeError, ValueError):
                    pass
            if cat == "TMP":
                try:
                    v = float(val)
                    res["temp_max"] = max(res.get("temp_max", -99), v)
                    res["temp_min"] = min(res.get("temp_min", 99), v)
                except (TypeError, ValueError):
                    pass
            if cat == "REH":
                res["humidity"] = self._safe_int(val, 0)
            if cat == "PCP":
                precip_sum += self._parse_kma_pcp_mm(val)
            if cat == "SKY" and str(item.get("fcstTime", "")) == "1200":
                res["sky_val"] = val
            if cat == "PTY" and str(item.get("fcstTime", "")) == "1200":
                res["pty_val"] = val
        if wsd_list:
            res["wind_max"] = max(wsd_list)
            res["wind_min"] = min(wsd_list)
        if res["wind_min"] >= 90.0:
            res["wind_min"] = 0.0
        res["precip"] = round(precip_sum, 1)
        daylight_duration = ss_h - sr_h
        if sky_list and daylight_duration > 0:
            clear_sky_count = sky_list.count("1") + (sky_list.count("3") * 0.5)
            res["sunshine_hr"] = round(
                daylight_duration * (clear_sky_count / len(sky_list)), 1
            )
        res["weather_cd"] = self.match_weather_code_db(
            res.get("sky_val", "1"), res.get("pty_val", "0")
        )
        res["raw_info"] = (
            f"SKY:{res.get('sky_val', '1')}, PTY:{res.get('pty_val', '0')}, SRC:VILAGE:{base_tag}"
        )
        return res

    def _fetch_vilage_fcst_once(self, nx, ny, base_yyyymmdd: str, base_hhmm: str):
        """API 1회 호출. resultCode 00이면 item(s)만 반환, 아니면 None."""
        if self._quota_exceeded:
            return None
        params = {
            "serviceKey": self.service_key,
            "pageNo": "1",
            "numOfRows": "1000",
            "dataType": "JSON",
            "base_date": base_yyyymmdd,
            "base_time": base_hhmm,
            "nx": nx,
            "ny": ny,
        }
        response = self._http_get(self.base_url, params)
        if response.status_code == 429:
            self._quota_exceeded = True
            self._record_weather_error("429", "API token quota exceeded")
            return None
        text = response.text or ""
        if "quota exceeded" in text.lower():
            self._quota_exceeded = True
            self._record_weather_error("429", "API token quota exceeded")
            return None
        try:
            data = response.json()
        except Exception:
            self._record_weather_error("999", "vilage forecast exception")
            return None
        header = data.get("response", {}).get("header", {}) or {}
        code = str(header.get("resultCode") or "").strip()
        msg = str(header.get("resultMsg") or "").strip()
        if code and code != "00":
            self._record_weather_error(code, msg or None)
            return None
        body = data.get("response", {}).get("body") or {}
        wrap = body.get("items")
        if not wrap:
            return None
        return wrap.get("item")

    def _get_vilage_fcst_weather(self, nx, ny, work_dt, lat, lon):
        """기상청 단기예보: item 단일/리스트 정규화, base_time 후보 순회(당일 온도 누락 완화)."""
        target_date = work_dt.replace("-", "")
        base_times = (
            "0200",
            "0500",
            "0800",
            "1100",
            "1400",
            "1700",
            "2000",
            "2300",
        )
        last_res = None
        for bt in base_times:
            items = self._fetch_vilage_fcst_once(nx, ny, target_date, bt)
            if items is None:
                continue
            res = self._parse_vilage_items_to_res(
                items, target_date, work_dt, lat, lon, f"{target_date}/{bt}"
            )
            if res is None:
                continue
            last_res = res
            if self._forecast_temps_valid(res):
                return res
        d = datetime.strptime(work_dt, "%Y-%m-%d")
        prev = (d - timedelta(days=1)).strftime("%Y%m%d")
        for bt in ("2300", "2000", "1700"):
            items = self._fetch_vilage_fcst_once(nx, ny, prev, bt)
            if items is None:
                continue
            res = self._parse_vilage_items_to_res(
                items, target_date, work_dt, lat, lon, f"{prev}/{bt}+1d"
            )
            if res is None:
                continue
            last_res = res
            if self._forecast_temps_valid(res):
                return res
        return last_res

    def _get_vilage_fcst_weather_fast(self, nx, ny, work_dt, lat, lon):
        """대시보드 전용 경량 단기예보: 최신 base 후보 2회 + 실패 시 전일 발표 1회(최대 3 API)."""
        target_date = work_dt.replace("-", "")
        candidates = self._latest_kma_base_candidates()
        pairs: List[Tuple[str, str]] = list(candidates[:2])
        tried: set = set(pairs)

        def _try_pairs(to_fetch: List[Tuple[str, str]]) -> Optional[Dict[str, Any]]:
            for bd, bt in to_fetch:
                items = self._fetch_vilage_fcst_once(nx, ny, bd, bt)
                if items is None:
                    continue
                res = self._parse_vilage_items_to_res(
                    items, target_date, work_dt, lat, lon, f"{bd}/{bt}"
                )
                if res and self._forecast_temps_valid(res):
                    return res
            return None

        hit = _try_pairs(pairs)
        if hit is not None:
            return hit

        prev_extra: List[Tuple[str, str]] = []
        for c in candidates:
            if c[0] != target_date and c not in tried:
                prev_extra.append(c)
                break
        if not prev_extra:
            return None
        return _try_pairs(prev_extra)

    def _merge_agri_vilage_forecast(
        self,
        ag: Optional[Dict[str, Any]],
        v: Optional[Dict[str, Any]],
        lat,
        lon,
        work_dt: str,
    ) -> Dict[str, Any]:
        """get_weather와 동일한 농업기상·단기 병합(기본 더미 포함)."""
        if ag is not None and self._forecast_temps_valid(ag):
            if v is not None:
                try:
                    vp = float(v.get("precip") or 0)
                    ap = float(ag.get("precip") or 0)
                    if vp > ap:
                        ag = dict(ag)
                        ag["precip"] = round(vp, 1)
                        ag["raw_info"] = f"{ag.get('raw_info', '')}|PRECIP_VILAGE"
                except (TypeError, ValueError):
                    pass
            return ag
        if v is not None and self._forecast_temps_valid(v):
            return v
        if v is not None:
            return v
        if ag is not None:
            return ag
        return self._make_default_weather(lat, lon, work_dt)

    def _get_agri_weather_for_day(self, work_dt, lat, lon):
        """단건 일자 농업기상. 세션 연도 캐시가 있으면 재사용, 없으면 FAST(최대 10페이지)."""
        if not (work_dt or "").strip():
            return None
        ds = str(work_dt).strip().replace("-", "")
        if len(ds) != 8 or not ds.isdigit():
            return None
        year = int(ds[:4])
        if year in self._agri_year_cache:
            items = self._agri_year_cache.get(year) or []
            row = self._pick_agri_day_row(items, ds) if items else None
            if row:
                return self._map_agri_row_to_result(row, lat, lon, work_dt)
            return None
        return self._get_agri_weather_dashboard_fast(work_dt, lat, lon)

    def get_weather(self, nx, ny, work_dt, lat, lon):
        """농업기상 + 단기예보 병합.

        - 과거일: 관측(FAST) 우선, 충분하면 단기예보 다중 호출을 생략
        - 오늘: 농업기상 FAST + 단기예보 FAST를 병렬 조회(최대 수회 API)
        """
        t0 = time.perf_counter()
        work_dt_s = str(work_dt or "").strip()[:10]
        today_s = today_ops().isoformat()
        is_past = bool(work_dt_s) and work_dt_s < today_s

        ag = None
        v = None
        try:
            if is_past:
                t_ag = time.perf_counter()
                ag = self._get_agri_weather_for_day(work_dt_s, lat, lon)
                print(
                    f"[Weather] agri(past) {time.perf_counter() - t_ag:.2f}s "
                    f"ok={bool(ag)}"
                )
                if ag and self._forecast_temps_valid(ag):
                    print(f"[Weather] get_weather total {time.perf_counter() - t0:.2f}s (agri-only)")
                    return ag
                # 과거 관측 실패 시 단기예보 소량 시도(최근일만 유효할 수 있음)
                t_v = time.perf_counter()
                try:
                    v = self._get_vilage_fcst_weather_fast(nx, ny, work_dt_s, lat, lon)
                except Exception as e:
                    print(f"[Weather] vilage(past): {e}")
                    v = None
                print(
                    f"[Weather] vilage(past) {time.perf_counter() - t_v:.2f}s ok={bool(v)}"
                )
            else:
                t_par = time.perf_counter()
                with ThreadPoolExecutor(max_workers=2) as executor:
                    f_ag = executor.submit(
                        self._get_agri_weather_for_day, work_dt_s, lat, lon
                    )
                    f_v = executor.submit(
                        self._get_vilage_fcst_weather_fast, nx, ny, work_dt_s, lat, lon
                    )
                    try:
                        ag = f_ag.result()
                    except Exception as e:
                        print(f"[Weather] agri: {e}")
                        ag = None
                    try:
                        v = f_v.result()
                    except Exception as e:
                        print(f"[Weather] vilage: {e}")
                        v = None
                print(
                    f"[Weather] parallel agri+vilage_fast "
                    f"{time.perf_counter() - t_par:.2f}s "
                    f"agri={bool(ag)} vilage={bool(v)}"
                )
        except Exception as e:
            print(f"[Weather] get_weather: {e}")

        merged = self._merge_agri_vilage_forecast(ag, v, lat, lon, work_dt_s)
        print(f"[Weather] get_weather total {time.perf_counter() - t0:.2f}s")
        return merged

    @staticmethod
    def work_log_weather_cache_key(farm_cd, work_dt, nx, ny) -> str:
        return f"{str(farm_cd or '').strip()}|{str(work_dt or '').strip()[:10]}|{int(nx)}|{int(ny)}"

    @staticmethod
    def _strip_work_log_cache_meta(data: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not isinstance(data, dict):
            return None
        out = dict(data)
        for k in ("_cache_nx", "_cache_ny", "_cached_at", "_cache_source"):
            out.pop(k, None)
        return out

    def _work_log_cache_is_fresh(
        self, data: Dict[str, Any], work_dt: str, nx: int, ny: int
    ) -> bool:
        try:
            if int(data.get("_cache_nx")) != int(nx):
                return False
            if int(data.get("_cache_ny")) != int(ny):
                return False
        except (TypeError, ValueError):
            return False
        work_dt_s = str(work_dt or "").strip()[:10]
        today_s = today_ops().isoformat()
        if work_dt_s < today_s:
            return True
        cached_at = str(data.get("_cached_at") or "").strip()
        if not cached_at:
            return False
        try:
            # _cached_at → 'YYYY-MM-DD HH:MM:SS' (KST)
            ts = datetime.strptime(cached_at[:19], "%Y-%m-%d %H:%M:%S")
        except Exception:
            try:
                ts = datetime.fromisoformat(cached_at.replace("Z", ""))
            except Exception:
                return False
        age = (now_ops().replace(tzinfo=None) - ts).total_seconds()
        return age <= float(WORK_LOG_WEATHER_TODAY_TTL_SEC)

    def peek_work_log_weather_cache(
        self, farm_cd: str, work_dt: str, nx: int, ny: int
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """메모리 → t_weather_cache. (data, source) / 없으면 (None, None)."""
        key = self.work_log_weather_cache_key(farm_cd, work_dt, nx, ny)
        mem = _WORK_LOG_WEATHER_MEM_CACHE.get(key)
        if isinstance(mem, dict) and self._work_log_cache_is_fresh(mem, work_dt, nx, ny):
            return self._strip_work_log_cache_meta(mem), "memory"

        raw = self._get_weather_from_db(str(farm_cd or "").strip(), str(work_dt or "").strip()[:10])
        if isinstance(raw, dict) and self._work_log_cache_is_fresh(raw, work_dt, nx, ny):
            _WORK_LOG_WEATHER_MEM_CACHE[key] = dict(raw)
            return self._strip_work_log_cache_meta(raw), "cache"
        return None, None

    def _store_work_log_weather_cache(
        self, farm_cd: str, work_dt: str, nx: int, ny: int, data: Dict[str, Any]
    ) -> None:
        if not data:
            return
        payload = dict(data)
        payload["_cache_nx"] = int(nx)
        payload["_cache_ny"] = int(ny)
        payload["_cached_at"] = now_ops().replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S")
        key = self.work_log_weather_cache_key(farm_cd, work_dt, nx, ny)
        _WORK_LOG_WEATHER_MEM_CACHE[key] = dict(payload)
        try:
            self._save_weather_to_db(
                str(farm_cd or "").strip(), str(work_dt or "").strip()[:10], payload
            )
        except Exception as e:
            print(f"[Weather] cache save: {e}")

    def classify_weather_fetch_error(self) -> Tuple[str, str]:
        """사용자 안내용 (kind, message)."""
        code = str(self._weather_error_code or "").strip()
        msg = str(self._weather_error_msg or "").strip()
        if code == "429" or "quota" in msg.lower():
            return "auth", "API 인증 오류(호출 한도 초과)"
        if code in ("03", "10", "11", "12", "20", "21", "22", "30"):
            return "auth", "API 인증 오류"
        if code in ("999",) and "exception" in msg.lower():
            return "network", "네트워크 지연"
        if code:
            return "empty", "데이터 없음"
        return "empty", "데이터 없음"

    def fetch_work_log_weather(
        self,
        farm_cd: str,
        work_dt: str,
        nx: int,
        ny: int,
        lat: float,
        lon: float,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """영농일지 ‘날씨 가져오기’용. 캐시→API, 결과 형식은 get_weather와 동일."""
        t0 = time.perf_counter()
        out: Dict[str, Any] = {
            "ok": False,
            "data": None,
            "source": "",
            "error": None,
            "error_kind": None,
            "elapsed": 0.0,
        }
        work_dt_s = str(work_dt or "").strip()[:10]
        if not work_dt_s:
            out["error"] = "날짜 정보 누락"
            out["error_kind"] = "empty"
            out["elapsed"] = time.perf_counter() - t0
            return out

        if not force_refresh:
            cached, src = self.peek_work_log_weather_cache(farm_cd, work_dt_s, nx, ny)
            if cached:
                out["ok"] = True
                out["data"] = cached
                out["source"] = "캐시" if src == "cache" else "캐시"
                if src == "memory":
                    out["source"] = "캐시"
                out["elapsed"] = time.perf_counter() - t0
                return out

        self._weather_error_code = None
        self._weather_error_msg = None
        try:
            data = self.get_weather(nx, ny, work_dt_s, lat, lon)
        except (requests.Timeout, requests.ConnectionError) as e:
            out["error_kind"] = "network"
            out["error"] = "네트워크 지연"
            out["elapsed"] = time.perf_counter() - t0
            print(f"[Weather] fetch network: {e}")
            return out
        except Exception as e:
            out["error_kind"] = "network"
            out["error"] = f"날씨 조회 실패: {e}"
            out["elapsed"] = time.perf_counter() - t0
            print(f"[Weather] fetch error: {e}")
            return out

        if not data or not self._weather_result_is_trustworthy(data):
            kind, msg = self.classify_weather_fetch_error()
            out["error_kind"] = kind
            out["error"] = msg
            out["elapsed"] = time.perf_counter() - t0
            return out

        self._store_work_log_weather_cache(farm_cd, work_dt_s, nx, ny, data)
        out["ok"] = True
        out["data"] = self._strip_work_log_cache_meta(data)
        out["source"] = "API"
        out["elapsed"] = time.perf_counter() - t0
        return out

    # -------------------------
    # Spray timing 확장용 컨텍스트
    # -------------------------
    def get_past_weather_context(
        self, nx: int, ny: int, lat: float, lon: float, days: int = 3
    ) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "days": int(days),
            "rain_sum": 0.0,
            "rain_days": 0,
            "avg_temp": None,
            "avg_wind": None,
            "weather_ok": False,
        }
        d = max(1, int(days or 1))
        today = today_ops()
        temps: List[float] = []
        winds: List[float] = []
        ok = 0
        for i in range(d):
            target = (today - timedelta(days=(d - 1 - i))).isoformat()
            res = self.get_weather(nx, ny, target, lat, lon)
            if self._weather_result_is_trustworthy(res):
                ok += 1
            try:
                pr = float(res.get("precip") or 0)
            except (TypeError, ValueError):
                pr = 0.0
            out["rain_sum"] += pr
            if pr > 0:
                out["rain_days"] += 1
            try:
                if self._forecast_temps_valid(res):
                    temps.append((float(res["temp_max"]) + float(res["temp_min"])) / 2.0)
            except (TypeError, ValueError, KeyError):
                pass
            try:
                winds.append(float(res.get("wind_max") or 0))
            except (TypeError, ValueError):
                pass
        out["rain_sum"] = round(float(out["rain_sum"]), 1)
        out["avg_temp"] = round(sum(temps) / len(temps), 1) if temps else None
        out["avg_wind"] = round(sum(winds) / len(winds), 1) if winds else None
        out["weather_ok"] = ok > 0
        return out

    def _latest_kma_base_candidates(self) -> List[Tuple[str, str]]:
        """단기예보 base_date/base_time 후보를 최근 순으로 반환."""
        now = now_ops().replace(tzinfo=None)
        today = now.strftime("%Y%m%d")
        prev = (now - timedelta(days=1)).strftime("%Y%m%d")
        times = ["2300", "2000", "1700", "1400", "1100", "0800", "0500", "0200"]
        out: List[Tuple[str, str]] = []
        hhmm = now.strftime("%H%M")
        for bt in times:
            if bt <= hhmm:
                out.append((today, bt))
        for bt in ("2300", "2000", "1700"):
            out.append((prev, bt))
        return out

    def get_short_forecast_slots(
        self, nx: int, ny: int, days: int = 3
    ) -> List[Dict[str, Any]]:
        """단기예보 원시 슬롯(POP/PCP/WSD/TMP/REH/SKY/PTY) 추출.

        days: 오늘을 포함한 집계 일수(예: 3 → 오늘·내일·모레).
        SPRAY_FORECAST_DAYS 등 상위 상수와 동일한 값으로 맞추는 것을 권장한다.
        """
        d = max(1, int(days or 1))
        items = None
        for bd, bt in self._latest_kma_base_candidates():
            raw = self._fetch_vilage_fcst_once(nx, ny, bd, bt)
            if raw:
                if isinstance(raw, dict):
                    items = [raw]
                else:
                    items = list(raw)
                break
        if not items:
            return []

        today = today_ops()
        limit_dates = {
            (today + timedelta(days=i)).strftime("%Y%m%d"): i for i in range(d)
        }
        bucket: Dict[Tuple[str, str], Dict[str, Any]] = {}
        for it in items:
            fdate = str(it.get("fcstDate") or "")
            ftime = str(it.get("fcstTime") or "")
            cat = str(it.get("category") or "")
            if fdate not in limit_dates or len(ftime) != 4:
                continue
            key = (fdate, ftime)
            rec = bucket.setdefault(
                key,
                {
                    "date": f"{fdate[:4]}-{fdate[4:6]}-{fdate[6:8]}",
                    "time": ftime,
                    "pop": None,
                    "pcp": 0.0,
                    "wsd": None,
                    "tmp": None,
                    "reh": None,
                    "sky": None,
                    "pty": None,
                },
            )
            val = it.get("fcstValue")
            if cat == "POP":
                rec["pop"] = self._safe_int(val, 0)
            elif cat == "PCP":
                rec["pcp"] = self._parse_kma_pcp_mm(val)
            elif cat == "WSD":
                rec["wsd"] = self._safe_float(val, 0.0)
            elif cat == "TMP":
                rec["tmp"] = self._safe_float(val, 0.0)
            elif cat == "REH":
                rec["reh"] = self._safe_int(val, 0)
            elif cat == "SKY":
                rec["sky"] = self._safe_int(val, 0)
            elif cat == "PTY":
                rec["pty"] = self._safe_int(val, 0)
        out = list(bucket.values())
        out.sort(key=lambda x: (x["date"], x["time"]))
        return out

    def build_period_forecast(
        self, slot_rows: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """오전(06~12)/오후(12~18) 집계 + 각 구간 시작 후 24h 지표."""
        if not slot_rows:
            return {}

        by_dt: Dict[str, List[Dict[str, Any]]] = {}
        for r in slot_rows:
            by_dt.setdefault(str(r.get("date") or ""), []).append(r)
        for k in by_dt:
            by_dt[k].sort(key=lambda x: str(x.get("time") or "0000"))

        all_rows = sorted(slot_rows, key=lambda x: (str(x.get("date")), str(x.get("time"))))
        out: Dict[str, Dict[str, Dict[str, Any]]] = {}

        def _agg(rows: List[Dict[str, Any]], start_key: str) -> Dict[str, Any]:
            pops = [int(r.get("pop") or 0) for r in rows]
            pcps = [float(r.get("pcp") or 0.0) for r in rows]
            ws = [float(r.get("wsd") or 0.0) for r in rows if r.get("wsd") is not None]
            start_dt = datetime.strptime(start_key, "%Y-%m-%d %H%M")
            end_dt = start_dt + timedelta(hours=24)
            p24: List[int] = []
            r24: List[float] = []
            for rr in all_rows:
                try:
                    t = datetime.strptime(
                        f"{rr.get('date')} {str(rr.get('time') or '0000')}",
                        "%Y-%m-%d %H%M",
                    )
                except Exception:
                    continue
                if start_dt < t <= end_dt:
                    p24.append(int(rr.get("pop") or 0))
                    r24.append(float(rr.get("pcp") or 0.0))
            max_slot_pcp = max(pcps) if pcps else 0.0
            return {
                "max_pop": max(pops) if pops else 0,
                "sum_pcp": round(sum(pcps), 1) if pcps else 0.0,
                "max_pcp_hour": round(float(max_slot_pcp), 1),
                "avg_wind": round(sum(ws) / len(ws), 1) if ws else 0.0,
                "max_wind": max(ws) if ws else 0.0,
                "next24h_max_pop": max(p24) if p24 else 0,
                "next24h_sum_pcp": round(sum(r24), 1) if r24 else 0.0,
            }

        for dt, rows in by_dt.items():
            am = [r for r in rows if "0600" <= str(r.get("time") or "") < "1200"]
            pm = [r for r in rows if "1200" <= str(r.get("time") or "") < "1800"]
            day_out: Dict[str, Dict[str, Any]] = {}
            if am:
                day_out["am"] = _agg(am, f"{dt} 0600")
            if pm:
                day_out["pm"] = _agg(pm, f"{dt} 1200")
            if day_out:
                out[dt] = day_out
        return out

    def _resolve_mid_forecast_region_codes(
        self, lat: Optional[float], lon: Optional[float]
    ) -> Tuple[str, str]:
        """중기예보 지역코드 결정.

        정밀 GIS·행정구역 매핑 전 1차 bbox 권역 매핑(core.kma_mid_region_map).
        좌표 없음·파싱 실패·어느 권역에도 안 맞으면 api_config 기본 regId.
        """
        return resolve_kma_mid_region_codes(
            lat,
            lon,
            default_land=KMA_MID_LAND_REG_ID,
            default_ta=KMA_MID_TA_REG_ID,
        )

    def _mid_tmfc_candidates(self) -> List[str]:
        now = now_ops().replace(tzinfo=None)
        base = now.replace(minute=0, second=0, microsecond=0)
        cands: List[str] = []
        if now.hour >= 18:
            cands.append(base.replace(hour=18).strftime("%Y%m%d%H00"))
        if now.hour >= 6:
            cands.append(base.replace(hour=6).strftime("%Y%m%d%H00"))
        y = now - timedelta(days=1)
        cands.append(y.replace(hour=18, minute=0, second=0, microsecond=0).strftime("%Y%m%d%H00"))
        cands.append(y.replace(hour=6, minute=0, second=0, microsecond=0).strftime("%Y%m%d%H00"))
        return cands

    def _fetch_mid_land_fcst(self, reg_id: str) -> Dict[str, Any]:
        cands = self._mid_tmfc_candidates()
        if not cands:
            return {}
        tm_fc = cands[0]
        params = {
            "serviceKey": self.service_key,
            "numOfRows": "10",
            "pageNo": "1",
            "dataType": "JSON",
            "regId": reg_id,
            "tmFc": tm_fc,
        }
        try:
            r = self._http_get(self.mid_land_fcst_url, params)
            data = r.json()
        except Exception:
            self._record_weather_error("999", "mid forecast exception")
            return {}
        header = data.get("response", {}).get("header", {}) or {}
        code = str(header.get("resultCode") or "").strip()
        msg = str(header.get("resultMsg") or "").strip()
        if code and code != "00":
            self._record_weather_error(code, msg or None)
            return {}
        item = (
            (data.get("response", {}).get("body", {}) or {})
            .get("items", {})
            .get("item")
        )
        if isinstance(item, list):
            item = item[0] if item else {}
        if isinstance(item, dict) and item:
            return dict(item)
        return {}

    def _fetch_mid_ta_fcst(self, reg_id: str) -> Dict[str, Any]:
        cands = self._mid_tmfc_candidates()
        if not cands:
            return {}
        tm_fc = cands[0]
        params = {
            "serviceKey": self.service_key,
            "numOfRows": "10",
            "pageNo": "1",
            "dataType": "JSON",
            "regId": reg_id,
            "tmFc": tm_fc,
        }
        try:
            r = self._http_get(self.mid_ta_url, params)
            data = r.json()
        except Exception:
            self._record_weather_error("999", "mid forecast exception")
            return {}
        header = data.get("response", {}).get("header", {}) or {}
        code = str(header.get("resultCode") or "").strip()
        msg = str(header.get("resultMsg") or "").strip()
        if code and code != "00":
            self._record_weather_error(code, msg or None)
            return {}
        item = (
            (data.get("response", {}).get("body", {}) or {})
            .get("items", {})
            .get("item")
        )
        if isinstance(item, list):
            item = item[0] if item else {}
        if isinstance(item, dict) and item:
            return dict(item)
        return {}

    def get_mid_forecast(self, lat: Optional[float], lon: Optional[float]) -> Dict[str, Any]:
        land_id, ta_id = self._resolve_mid_forecast_region_codes(lat, lon)
        land = self._fetch_mid_land_fcst(land_id)
        ta = self._fetch_mid_ta_fcst(ta_id)
        return {"land": land, "ta": ta, "ok": bool(land) and bool(ta)}

    def summarize_mid_forecast(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "has_rain_window": False,
            "first_rain_date": None,
            "rain_days": [],
            "daily_summary": [],
            "forecast_ok": False,
        }
        if not raw or not raw.get("ok"):
            return out
        land = raw.get("land") or {}
        ta = raw.get("ta") or {}
        today = today_ops()
        daily: List[Dict[str, Any]] = []
        for n in range(4, 11):
            ds = (today + timedelta(days=n)).isoformat()
            rain_am = self._safe_int(land.get(f"rnSt{n}Am"), 0)
            rain_pm = self._safe_int(land.get(f"rnSt{n}Pm"), 0)
            tmin = self._safe_float(ta.get(f"taMin{n}"), 0.0)
            tmax = self._safe_float(ta.get(f"taMax{n}"), 0.0)
            daily.append(
                {
                    "date": ds,
                    "rain_am": rain_am,
                    "rain_pm": rain_pm,
                    "tmin": tmin,
                    "tmax": tmax,
                }
            )
        rain_days = [
            d["date"] for d in daily if int(d["rain_am"]) >= 40 or int(d["rain_pm"]) >= 40
        ]
        out["daily_summary"] = daily
        out["rain_days"] = rain_days
        out["has_rain_window"] = bool(rain_days)
        out["first_rain_date"] = rain_days[0] if rain_days else None
        out["forecast_ok"] = True
        return out

    def calculate_sun_times_korea(self, lat, lon, date_str):
        d = datetime.strptime(date_str, "%Y-%m-%d")
        day_of_year = d.timetuple().tm_yday
        cos_val = math.cos(math.radians((day_of_year + 10) * 360 / 365))
        lat_adj = (lat - 37.5) * 0.05
        sr_h = 6.45 + (cos_val * 1.35) + lat_adj
        ss_h = 18.65 - (cos_val * 1.25) - lat_adj
        return (
            f"{int(sr_h):02d}:{int((sr_h % 1) * 60):02d}",
            f"{int(ss_h):02d}:{int((ss_h % 1) * 60):02d}",
            sr_h,
            ss_h,
        )

    def match_weather_code_db(self, sky, pty):
        if pty == "0":
            if sky == "1":
                return "WT010100"
            elif sky == "3":
                return "WT010200"
            elif sky == "4":
                return "WT010300"
        elif pty == "1":
            return "WT010400"
        elif pty == "2":
            return "WT010500"
        elif pty == "3":
            return "WT010600"
        elif pty == "4":
            return "WT010700"
        return "WT019900"

    @staticmethod
    def _dashboard_weather_text(weather_cd: str) -> str:
        code = str(weather_cd or "").strip()
        mapping = {
            "WT010100": "맑음",
            "WT010200": "구름많음",
            "WT010300": "흐림",
            "WT010400": "비",
            "WT010500": "비/눈",
            "WT010600": "눈",
            "WT010700": "소나기",
        }
        return mapping.get(code, "정보 없음")

    @staticmethod
    def _dashboard_icon_from_text(text: str) -> str:
        t = str(text or "")
        if "비/눈" in t:
            return "sleet"
        if "소나기" in t or "비" in t:
            return "rain"
        if "눈" in t:
            return "snow"
        if "흐림" in t or "구름" in t:
            return "cloud"
        if "맑" in t:
            return "sun"
        return "partly_cloudy"

    @staticmethod
    def _to_int_or_none(value) -> Optional[int]:
        if value in ("", None):
            return None
        try:
            return int(round(float(value)))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _weekday_ko(ymd: str) -> str:
        try:
            dt = datetime.strptime(str(ymd), "%Y-%m-%d")
        except Exception:
            return ""
        names = ["월", "화", "수", "목", "금", "토", "일"]
        return names[dt.weekday()]

    def _get_farm_location(self, farm_cd: str):
        if not self.db or not farm_cd:
            return None
        try:
            rows = self.db.execute_query(
                "SELECT lat, lon, nx, ny FROM m_farm_info WHERE farm_cd = ?",
                (farm_cd,),
            )
            if not rows:
                return None
            lat, lon, nx, ny = rows[0]
            if not all([lat, lon, nx, ny]):
                return None
            return float(lat), float(lon), int(nx), int(ny)
        except Exception:
            return None

    def _build_dashboard_weekly(self, lat: Optional[float], lon: Optional[float]) -> List[dict]:
        # 하위 호환: 기존 시그니처 호출 시 중기만 반환
        if lat is None or lon is None:
            return []
        return self._build_dashboard_weekly_mid(lat, lon)

    @staticmethod
    def _hhmm_to_minutes(hhmm: str) -> Optional[int]:
        s = str(hhmm or "").strip()
        if len(s) != 4 or not s.isdigit():
            return None
        hh = int(s[:2])
        mm = int(s[2:])
        if not (0 <= hh <= 23 and 0 <= mm <= 59):
            return None
        return (hh * 60) + mm

    def _get_latest_vilage_items(self, nx: int, ny: int):
        for bd, bt in self._latest_kma_base_candidates():
            raw = self._fetch_vilage_fcst_once(nx, ny, bd, bt)
            if raw:
                if isinstance(raw, dict):
                    return [raw]
                return list(raw)
        return []

    def _get_current_temp_from_db_row(self, row: Dict[str, Any]) -> Optional[int]:
        if not isinstance(row, dict):
            return None
        for key in ("temp_now", "current_temp", "temp_cur", "temp_current", "tmp_now"):
            if key in row:
                v = self._to_int_or_none(row.get(key))
                if v is not None:
                    return v
        return None

    def _get_current_temp_from_vilage_slots(
        self,
        nx: int,
        ny: int,
        target_date: str,
        items: Optional[List[Any]] = None,
    ) -> Optional[int]:
        if items is None:
            items = self._get_latest_vilage_items(nx, ny)
        if not items:
            return None
        ymd = str(target_date or "").replace("-", "")
        now_min = now_ops().replace(tzinfo=None).hour * 60 + now_ops().replace(tzinfo=None).minute
        best_gap = None
        best_temp = None
        for it in items:
            if str(it.get("fcstDate") or "") != ymd:
                continue
            if str(it.get("category") or "") != "TMP":
                continue
            t = self._to_int_or_none(it.get("fcstValue"))
            if t is None:
                continue
            fcst_min = self._hhmm_to_minutes(str(it.get("fcstTime") or ""))
            if fcst_min is None:
                continue
            gap = abs(fcst_min - now_min)
            if best_gap is None or gap < best_gap:
                best_gap = gap
                best_temp = t
        return best_temp

    def _icon_from_short(self, pty_vals: List[int], pcp_sum: float, sky_vals: List[int]) -> str:
        if any(v == 2 for v in pty_vals):
            return "sleet"
        if any(v in (3, 4) for v in pty_vals):
            return "snow"
        if any(v == 1 for v in pty_vals):
            return "rain"
        if pcp_sum >= 1.0:
            return "rain"
        if any(v == 4 for v in sky_vals):
            return "cloud"
        if any(v == 3 for v in sky_vals):
            return "partly_cloudy"
        return "sun"

    def _build_dashboard_weekly_short(
        self,
        nx: int,
        ny: int,
        start_date: str,
        days: int = 4,
        items: Optional[List[Any]] = None,
    ) -> List[dict]:
        if items is None:
            items = self._get_latest_vilage_items(nx, ny)
        if not items:
            return []
        try:
            base_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
        except Exception:
            base_dt = today_ops()
        wanted = {(base_dt + timedelta(days=i)).strftime("%Y%m%d") for i in range(max(1, int(days or 1)))}

        bucket: Dict[str, Dict[str, Any]] = {}
        for it in items:
            ds = str(it.get("fcstDate") or "")
            if ds not in wanted:
                continue
            cat = str(it.get("category") or "")
            rec = bucket.setdefault(ds, {"tmp": [], "sky": [], "pty": [], "pcp_sum": 0.0})
            if cat == "TMP":
                v = self._safe_float(it.get("fcstValue"), None)
                if v is not None:
                    rec["tmp"].append(v)
            elif cat == "SKY":
                rec["sky"].append(self._safe_int(it.get("fcstValue"), 0))
            elif cat == "PTY":
                rec["pty"].append(self._safe_int(it.get("fcstValue"), 0))
            elif cat == "PCP":
                rec["pcp_sum"] += self._parse_kma_pcp_mm(it.get("fcstValue"))

        out: List[dict] = []
        for ds in sorted(bucket.keys()):
            rec = bucket[ds]
            if not rec["tmp"]:
                continue
            dt = f"{ds[:4]}-{ds[4:6]}-{ds[6:8]}"
            out.append(
                {
                    "_date": dt,
                    "day": self._weekday_ko(dt),
                    "date": ds[6:8],
                    "min": int(round(min(rec["tmp"]))),
                    "max": int(round(max(rec["tmp"]))),
                    "icon": self._icon_from_short(rec["pty"], rec["pcp_sum"], rec["sky"]),
                }
            )
        return out

    def _weekly_rows_from_mid_raw(self, mid: Optional[Dict[str, Any]]) -> List[dict]:
        """get_mid_forecast 결과 dict → 대시보드 주간(중기) 행."""
        if not mid or not mid.get("ok"):
            return []
        try:
            summary = self.summarize_mid_forecast(mid)
            daily = summary.get("daily_summary") or []
            out: List[dict] = []
            for row in daily:
                ds = str(row.get("date") or "")
                min_v = self._to_int_or_none(row.get("tmin"))
                max_v = self._to_int_or_none(row.get("tmax"))
                rain_am = int(row.get("rain_am") or 0)
                rain_pm = int(row.get("rain_pm") or 0)
                if rain_am >= 60 or rain_pm >= 60:
                    icon = "rain"
                elif rain_am >= 40 or rain_pm >= 40:
                    icon = "cloud"
                else:
                    icon = "sun"
                out.append(
                    {
                        "_date": ds,
                        "day": self._weekday_ko(ds),
                        "date": ds[-2:] if len(ds) >= 10 else "",
                        "min": min_v if min_v is not None else 0,
                        "max": max_v if max_v is not None else 0,
                        "icon": icon,
                    }
                )
            return out
        except Exception:
            return []

    def _build_dashboard_weekly_mid(self, lat: Optional[float], lon: Optional[float]) -> List[dict]:
        if lat is None or lon is None:
            return []
        mid = self.get_mid_forecast(lat, lon)
        return self._weekly_rows_from_mid_raw(mid)

    def _merge_dashboard_weekly(self, short_rows: List[dict], mid_rows: List[dict], start_date: str, total_days: int = 7) -> List[dict]:
        merged: Dict[str, dict] = {}
        for r in mid_rows or []:
            ds = str(r.get("_date") or "")
            if ds:
                merged[ds] = dict(r)
        for r in short_rows or []:
            ds = str(r.get("_date") or "")
            if ds:
                merged[ds] = dict(r)  # 단기 우선

        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
        except Exception:
            start_dt = today_ops()

        out: List[dict] = []
        for i in range(max(1, int(total_days or 7))):
            ds = (start_dt + timedelta(days=i)).strftime("%Y-%m-%d")
            row = merged.get(ds)
            if row is None:
                out.append(
                    {
                        "day": self._weekday_ko(ds),
                        "date": ds[-2:],
                        "min": 0,
                        "max": 0,
                        "icon": "cloud",
                    }
                )
                continue
            out.append(
                {
                    "day": row.get("day") or self._weekday_ko(ds),
                    "date": row.get("date") or ds[-2:],
                    "min": int(row.get("min") or 0),
                    "max": int(row.get("max") or 0),
                    "icon": row.get("icon") or "cloud",
                }
            )
        return out[: total_days or 7]

    def _fetch_weather_api(
        self,
        payload: Dict[str, Any],
        target_date: str,
        nx: int,
        ny: int,
        lat: float,
        lon: float,
    ) -> None:
        """대시보드 전용 API 조립: FAST 단기 + 중기 병렬, 단기 item 1회 재사용."""
        vilage_items = self._get_latest_vilage_items(nx, ny)
        if payload.get("temp_now") is None:
            payload["temp_now"] = self._get_current_temp_from_vilage_slots(
                nx, ny, target_date, items=vilage_items
            )

        ag_result = None
        try:
            ag_result = self._get_agri_weather_dashboard_fast(target_date, lat, lon)
        except Exception:
            pass

        v_result = None
        mid_raw: Dict[str, Any] = {"land": {}, "ta": {}, "ok": False}
        try:
            with ThreadPoolExecutor(max_workers=2) as executor:
                f_vil = executor.submit(
                    self._get_vilage_fcst_weather_fast, nx, ny, target_date, lat, lon
                )
                f_mid = executor.submit(self.get_mid_forecast, lat, lon)
                v_result = f_vil.result()
                mid_raw = f_mid.result() or mid_raw
        except Exception:
            try:
                v_result = self._get_vilage_fcst_weather_fast(
                    nx, ny, target_date, lat, lon
                )
                mid_raw = self.get_mid_forecast(lat, lon) or mid_raw
            except Exception:
                pass

        merged_api = self._merge_agri_vilage_forecast(
            ag_result, v_result, lat, lon, target_date
        )

        if (
            payload.get("temp_now") is None
            or payload.get("temp_max") is None
            or payload.get("temp_min") is None
        ):
            try:
                api_row = merged_api or {}
                tmax = self._to_int_or_none(api_row.get("temp_max"))
                tmin = self._to_int_or_none(api_row.get("temp_min"))
                temp_now = payload.get("temp_now")
                if temp_now is None:
                    temp_now = tmax if tmax is not None else tmin
                payload.update(
                    {
                        "temp_now": temp_now,
                        "weather_text": payload.get("weather_text")
                        if payload.get("weather_text") != "데이터 없음"
                        else self._dashboard_weather_text(api_row.get("weather_cd")),
                        "temp_max": payload.get("temp_max")
                        if payload.get("temp_max") is not None
                        else tmax,
                        "temp_min": payload.get("temp_min")
                        if payload.get("temp_min") is not None
                        else tmin,
                    }
                )
            except Exception:
                pass

        short_rows = self._build_dashboard_weekly_short(
            nx, ny, target_date, days=4, items=vilage_items
        )
        mid_rows = self._weekly_rows_from_mid_raw(mid_raw)
        payload["weekly"] = self._merge_dashboard_weekly(
            short_rows, mid_rows, target_date, total_days=7
        )

    def _slot_to_datetime(self, slot: Dict[str, Any]) -> Optional[datetime]:
        ds = str(slot.get("date") or "").strip()
        tm = str(slot.get("time") or "0000").strip().zfill(4)
        if len(ds) != 10 or len(tm) != 4:
            return None
        try:
            return datetime.strptime(f"{ds} {tm}", "%Y-%m-%d %H%M")
        except ValueError:
            return None

    def _icon_from_slot(self, slot: Dict[str, Any]) -> str:
        pty = slot.get("pty")
        sky = slot.get("sky")
        pty_vals = [int(pty)] if pty is not None else []
        sky_vals = [int(sky)] if sky is not None else []
        pcp = float(slot.get("pcp") or 0.0)
        return self._icon_from_short(pty_vals, pcp, sky_vals)

    def _weather_cd_from_slot(self, slot: Dict[str, Any]) -> str:
        sky = str(slot.get("sky") if slot.get("sky") is not None else "1")
        pty = str(slot.get("pty") if slot.get("pty") is not None else "0")
        return self.match_weather_code_db(sky, pty)

    def _filter_hourly_slots(
        self,
        slots: List[Dict[str, Any]],
        *,
        now: Optional[datetime] = None,
        hours: int = MOBILE_DETAIL_HOURLY_HOURS,
    ) -> List[Dict[str, Any]]:
        """현재 시각 이후 hours 구간의 슬롯(시각 내림 포함)."""
        base = now or now_ops().replace(tzinfo=None)
        start = base.replace(minute=0, second=0, microsecond=0)
        end = start + timedelta(hours=max(1, int(hours or 1)))
        out: List[Dict[str, Any]] = []
        for slot in slots:
            dt = self._slot_to_datetime(slot)
            if dt is None:
                continue
            if start <= dt <= end:
                out.append(slot)
        return out

    def _build_hourly_timeline(
        self,
        slots: List[Dict[str, Any]],
        sun_events: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """시간별 슬롯 + 일출/일몰 마커를 시간순으로 합성."""
        rows: List[Dict[str, Any]] = []
        for slot in slots:
            dt = self._slot_to_datetime(slot)
            if dt is None:
                continue
            icon = self._icon_from_slot(slot)
            rows.append(
                {
                    "at": dt.strftime("%Y-%m-%dT%H:%M:00"),
                    "kind": "hour",
                    "temp_c": self._safe_float(slot.get("tmp"), None),
                    "precip_prob_pct": self._safe_int(slot.get("pop"), 0),
                    "precip_mm": round(float(slot.get("pcp") or 0.0), 1),
                    "humidity_pct": self._safe_int(slot.get("reh"), None)
                    if slot.get("reh") is not None
                    else None,
                    "wind_ms": self._safe_float(slot.get("wsd"), None)
                    if slot.get("wsd") is not None
                    else None,
                    "icon": icon,
                    "weather_cd": self._weather_cd_from_slot(slot),
                    "marker": None,
                }
            )
        for ev in sun_events:
            at = str(ev.get("at") or "").strip()
            kind = str(ev.get("kind") or "").strip()
            if not at or kind not in (
                MOBILE_DETAIL_SUN_MARKER_SUNRISE,
                MOBILE_DETAIL_SUN_MARKER_SUNSET,
            ):
                continue
            rows.append(
                {
                    "at": at,
                    "kind": "sun",
                    "temp_c": None,
                    "precip_prob_pct": None,
                    "precip_mm": None,
                    "humidity_pct": None,
                    "wind_ms": None,
                    "icon": kind,
                    "weather_cd": None,
                    "marker": kind,
                }
            )
        rows.sort(key=lambda r: str(r.get("at") or ""))
        return rows

    def _sun_events_for_range(
        self,
        lat: float,
        lon: float,
        start_date: str,
        days: int,
        daily_by_date: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """일출/일몰 이벤트. daily에 sun_rise/set이 있으면 우선, 없으면 계산."""
        try:
            base = datetime.strptime(str(start_date)[:10], "%Y-%m-%d").date()
        except ValueError:
            base = today_ops()
        out: List[Dict[str, Any]] = []
        daily_by_date = daily_by_date or {}
        for i in range(max(1, int(days or 1))):
            ds = (base + timedelta(days=i)).isoformat()
            daily = daily_by_date.get(ds) or {}
            sr = str(daily.get("sun_rise") or "").strip()
            ss = str(daily.get("sun_set") or "").strip()
            if not sr or not ss:
                calc_sr, calc_ss, _, _ = self.calculate_sun_times_korea(lat, lon, ds)
                sr = sr or calc_sr
                ss = ss or calc_ss
            if len(sr) >= 5:
                out.append(
                    {
                        "at": f"{ds}T{sr[:5]}:00",
                        "kind": MOBILE_DETAIL_SUN_MARKER_SUNRISE,
                    }
                )
            if len(ss) >= 5:
                out.append(
                    {
                        "at": f"{ds}T{ss[:5]}:00",
                        "kind": MOBILE_DETAIL_SUN_MARKER_SUNSET,
                    }
                )
        return out

    def _day_temp_minmax_from_slots(
        self, slots: List[Dict[str, Any]]
    ) -> Dict[str, Tuple[Optional[float], Optional[float]]]:
        by_date: Dict[str, List[float]] = {}
        for slot in slots:
            ds = str(slot.get("date") or "")
            tmp = slot.get("tmp")
            if not ds or tmp is None:
                continue
            by_date.setdefault(ds, []).append(float(tmp))
        out: Dict[str, Tuple[Optional[float], Optional[float]]] = {}
        for ds, vals in by_date.items():
            out[ds] = (min(vals), max(vals))
        return out

    def _day_icon_from_slots(
        self, slots: List[Dict[str, Any]]
    ) -> Dict[str, str]:
        by_date: Dict[str, Dict[str, Any]] = {}
        for slot in slots:
            ds = str(slot.get("date") or "")
            if not ds:
                continue
            rec = by_date.setdefault(ds, {"pty": [], "sky": [], "pcp_sum": 0.0})
            if slot.get("pty") is not None:
                rec["pty"].append(int(slot["pty"]))
            if slot.get("sky") is not None:
                rec["sky"].append(int(slot["sky"]))
            rec["pcp_sum"] += float(slot.get("pcp") or 0.0)
        return {
            ds: self._icon_from_short(rec["pty"], rec["pcp_sum"], rec["sky"])
            for ds, rec in by_date.items()
        }

    def _period_half_to_am_pm(
        self, half: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        half = half or {}
        return {
            "precip_prob_pct": int(half.get("max_pop") or 0),
            "precip_mm": round(float(half.get("sum_pcp") or 0.0), 1),
            "wind_ms": round(float(half.get("avg_wind") or 0.0), 1),
        }

    def build_weekly_am_pm(
        self,
        *,
        nx: int,
        ny: int,
        lat: float,
        lon: float,
        start_date: str,
        days: int = MOBILE_DETAIL_WEEKLY_DAYS,
        slots: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """주간 오전/오후 예보 — 단기 period + 중기 rain_am/pm 병합."""
        try:
            base = datetime.strptime(str(start_date)[:10], "%Y-%m-%d").date()
        except ValueError:
            base = today_ops()
        total = max(1, int(days or MOBILE_DETAIL_WEEKLY_DAYS))
        short_slots = slots if slots is not None else self.get_short_forecast_slots(
            nx, ny, days=MOBILE_DETAIL_SHORT_DAYS
        )
        period = self.build_period_forecast(short_slots)
        temps = self._day_temp_minmax_from_slots(short_slots)
        icons = self._day_icon_from_slots(short_slots)

        mid_summary = self.summarize_mid_forecast(self.get_mid_forecast(lat, lon))
        mid_by_date = {
            str(row.get("date") or ""): row
            for row in (mid_summary.get("daily_summary") or [])
        }

        weekly: List[Dict[str, Any]] = []
        for i in range(total):
            ds = (base + timedelta(days=i)).isoformat()
            short_day = period.get(ds) or {}
            mid_day = mid_by_date.get(ds) or {}
            tmin_s, tmax_s = temps.get(ds, (None, None))
            if short_day:
                am = self._period_half_to_am_pm(short_day.get("am"))
                pm = self._period_half_to_am_pm(short_day.get("pm"))
                source = MOBILE_DETAIL_SOURCE_SHORT
                icon = icons.get(ds) or "cloud"
                tmin = int(round(tmin_s)) if tmin_s is not None else None
                tmax = int(round(tmax_s)) if tmax_s is not None else None
            elif mid_day:
                am = {
                    "precip_prob_pct": int(mid_day.get("rain_am") or 0),
                    "precip_mm": None,
                    "wind_ms": None,
                }
                pm = {
                    "precip_prob_pct": int(mid_day.get("rain_pm") or 0),
                    "precip_mm": None,
                    "wind_ms": None,
                }
                source = MOBILE_DETAIL_SOURCE_MID
                rain_am = int(mid_day.get("rain_am") or 0)
                rain_pm = int(mid_day.get("rain_pm") or 0)
                if rain_am >= 60 or rain_pm >= 60:
                    icon = "rain"
                elif rain_am >= 40 or rain_pm >= 40:
                    icon = "cloud"
                else:
                    icon = "sun"
                tmin = self._to_int_or_none(mid_day.get("tmin"))
                tmax = self._to_int_or_none(mid_day.get("tmax"))
            else:
                am = {"precip_prob_pct": 0, "precip_mm": None, "wind_ms": None}
                pm = {"precip_prob_pct": 0, "precip_mm": None, "wind_ms": None}
                source = MOBILE_DETAIL_SOURCE_SHORT
                icon = "cloud"
                tmin = None
                tmax = None
            weekly.append(
                {
                    "date": ds,
                    "weekday": self._weekday_ko(ds),
                    "temp_min": tmin if tmin is not None else 0,
                    "temp_max": tmax if tmax is not None else 0,
                    "icon": icon,
                    "am": am,
                    "pm": pm,
                    "source": source,
                }
            )
        return weekly

    def build_mobile_weather_detail(
        self,
        *,
        nx: int,
        ny: int,
        lat: float,
        lon: float,
        target_date: Optional[str] = None,
        location_label: str = "",
    ) -> Dict[str, Any]:
        """모바일 날씨 상세 조립(현재·시간별·주간 오전/오후). 미세먼지 제외."""
        t0 = time.perf_counter()
        today_s = self._normalize_dashboard_date_str(target_date or today_ops().isoformat())
        yesterday_s = (
            datetime.strptime(today_s, "%Y-%m-%d").date() - timedelta(days=1)
        ).isoformat()

        daily = self.get_weather(nx, ny, today_s, lat, lon) or {}
        slots = self.get_short_forecast_slots(nx, ny, days=MOBILE_DETAIL_SHORT_DAYS)
        hourly_slots = self._filter_hourly_slots(slots)
        period = self.build_period_forecast(slots)

        nearest_tmp = None
        nearest_pop = 0
        now = now_ops().replace(tzinfo=None)
        best_gap = None
        for slot in slots:
            dt = self._slot_to_datetime(slot)
            if dt is None or slot.get("tmp") is None:
                continue
            gap = abs((dt - now).total_seconds())
            if best_gap is None or gap < best_gap:
                best_gap = gap
                nearest_tmp = float(slot["tmp"])
                nearest_pop = int(slot.get("pop") or 0)

        temp_min = self._safe_float(daily.get("temp_min"), None)
        temp_max = self._safe_float(daily.get("temp_max"), None)
        temp_c = nearest_tmp
        if temp_c is None:
            if temp_min is not None and temp_max is not None:
                temp_c = round((temp_min + temp_max) / 2.0, 1)
            elif temp_max is not None:
                temp_c = temp_max
            elif temp_min is not None:
                temp_c = temp_min

        temp_diff = None
        try:
            y_daily = self.get_weather(nx, ny, yesterday_s, lat, lon) or {}
            y_min = self._safe_float(y_daily.get("temp_min"), None)
            y_max = self._safe_float(y_daily.get("temp_max"), None)
            y_avg = None
            if y_min is not None and y_max is not None:
                y_avg = (y_min + y_max) / 2.0
            elif y_max is not None:
                y_avg = y_max
            elif y_min is not None:
                y_avg = y_min
            if temp_c is not None and y_avg is not None:
                temp_diff = round(float(temp_c) - float(y_avg), 1)
        except Exception:
            temp_diff = None

        tomorrow_s = (
            datetime.strptime(today_s, "%Y-%m-%d").date() + timedelta(days=1)
        ).isoformat()
        tomorrow_am = None
        t_am = (period.get(tomorrow_s) or {}).get("am")
        if t_am:
            tomorrow_am = self._period_half_to_am_pm(t_am)

        sun_events = self._sun_events_for_range(
            lat,
            lon,
            today_s,
            days=2,
            daily_by_date={today_s: daily},
        )
        # 시간별 구간에 들어오는 일출·일몰만 표시
        if hourly_slots:
            h0 = self._slot_to_datetime(hourly_slots[0])
            h1 = self._slot_to_datetime(hourly_slots[-1])
            if h0 and h1:
                filtered_sun = []
                for ev in sun_events:
                    try:
                        edt = datetime.strptime(str(ev["at"]), "%Y-%m-%dT%H:%M:%S")
                    except (KeyError, ValueError):
                        continue
                    if h0 <= edt <= h1 + timedelta(hours=1):
                        filtered_sun.append(ev)
                sun_events = filtered_sun

        hourly = self._build_hourly_timeline(hourly_slots, sun_events)
        weekly = self.build_weekly_am_pm(
            nx=nx,
            ny=ny,
            lat=lat,
            lon=lon,
            start_date=today_s,
            days=MOBILE_DETAIL_WEEKLY_DAYS,
            slots=slots,
        )

        weather_cd = str(daily.get("weather_cd") or "").strip() or "WT019900"
        return {
            "ok": True,
            "date": today_s,
            "location": location_label or "",
            "current": {
                "temp_c": temp_c,
                "temp_min": temp_min,
                "temp_max": temp_max,
                "temp_diff_from_yesterday": temp_diff,
                "weather_cd": weather_cd,
                "weather_nm": self._dashboard_weather_text(weather_cd),
                "humidity_pct": self._safe_float(daily.get("humidity"), None),
                "wind_ms": self._safe_float(daily.get("wind_max"), None),
                "precip_mm": self._safe_float(daily.get("precip"), None),
                "precip_prob_pct": nearest_pop,
                "sun_rise": str(daily.get("sun_rise") or "").strip() or None,
                "sun_set": str(daily.get("sun_set") or "").strip() or None,
            },
            "tomorrow_am": tomorrow_am,
            "hourly": hourly,
            "sun_events": sun_events,
            "weekly": weekly,
            "updated_at": now_ops().replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S"),
            "elapsed": round(time.perf_counter() - t0, 3),
        }

    def get_dashboard_weather(self, farm_cd: str, target_date: str) -> Dict[str, Any]:
        farm_cd = str(farm_cd or "").strip()
        today_str = self._normalize_dashboard_date_str(target_date)
        cache_key = f"{farm_cd}|{today_str}"

        if self._cache_date == cache_key and self._cache_data:
            return self._cache_data

        if self.db:
            db_data = self._get_weather_from_db(farm_cd, today_str)
            if db_data:
                self._cache_date = cache_key
                self._cache_data = db_data
                return db_data

        payload: Dict[str, Any] = {
            "temp_now": None,
            "weather_text": "데이터 없음",
            "temp_max": None,
            "temp_min": None,
            "weekly": [],
        }
        loc = self._get_farm_location(str(farm_cd or "").strip())
        lat = lon = nx = ny = None
        if loc:
            lat, lon, nx, ny = loc

        # 1) 영농일지 DB 우선
        if self.db:
            try:
                rows = self.db.get_weather_info(farm_cd, today_str) or []
                if rows:
                    row = dict(rows[0])
                    tmax = self._to_int_or_none(row.get("temp_max"))
                    tmin = self._to_int_or_none(row.get("temp_min"))
                    weather_text = self._dashboard_weather_text(row.get("weather_cd"))
                    temp_now = self._get_current_temp_from_db_row(row)
                    payload.update(
                        {
                            "temp_now": temp_now,
                            "weather_text": weather_text,
                            "temp_max": tmax,
                            "temp_min": tmin,
                        }
                    )
            except Exception:
                pass

        # 2)~3) 대시보드 전용 FAST 경로(_fetch_weather_api). 상세/AI는 get_weather → 전체 단기 유지.
        if all(v is not None for v in (nx, ny, lat, lon)):
            self._fetch_weather_api(payload, today_str, nx, ny, lat, lon)
        else:
            payload["weekly"] = []

        if self.db:
            try:
                self._save_weather_to_db(farm_cd, today_str, payload)
            except Exception:
                pass

        self._cache_date = cache_key
        self._cache_data = payload
        return payload


def convert_to_grid(lat, lon):
    RE = 6371.00877
    GRID = 5.0
    SLAT1 = 30.0
    SLAT2 = 60.0
    OLON = 126.0
    OLAT = 38.0
    XO = 43
    YO = 136
    DEGRAD = math.pi / 180.0
    re = RE / GRID
    slat1 = SLAT1 * DEGRAD
    slat2 = SLAT2 * DEGRAD
    olon = OLON * DEGRAD
    olat = OLAT * DEGRAD
    sn = math.tan(math.pi * 0.25 + slat2 * 0.5) / math.tan(math.pi * 0.25 + slat1 * 0.5)
    sn = math.log(math.cos(slat1) / math.cos(slat2)) / math.log(sn)
    sf = math.tan(math.pi * 0.25 + slat1 * 0.5)
    sf = math.pow(sf, sn) * math.cos(slat1) / sn
    ro = math.tan(math.pi * 0.25 + olat * 0.5)
    ro = re * sf / math.pow(ro, sn)
    ra = math.tan(math.pi * 0.25 + lat * DEGRAD * 0.5)
    ra = re * sf / math.pow(ra, sn)
    theta = lon * DEGRAD - olon
    if theta > math.pi:
        theta -= 2.0 * math.pi
    if theta < -math.pi:
        theta += 2.0 * math.pi
    theta *= sn
    nx = int(math.floor(ra * math.sin(theta) + XO + 0.5))
    ny = int(math.floor(ro - ra * math.cos(theta) + YO + 0.5))
    return nx, ny
