# -*- coding: utf-8 -*-
"""관찰 AI 분석용 내부 컨텍스트 — 사용자 입력 없이 서버가 조립.

사진과 함께 프롬프트에만 넣고, 농장코드·경로·개인정보는 포함하지 않는다.
기상은 WeatherManager(공공 API) 우선, 실패 시 DB, 없으면 생략.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any

_logger = logging.getLogger(__name__)

# 24절기 (대략 일자 — 연도 보정 없이 월·일로 표시용)
_SOLAR_TERMS: tuple[tuple[int, int, str], ...] = (
    (1, 6, "소한"),
    (1, 20, "대한"),
    (2, 4, "입춘"),
    (2, 19, "우수"),
    (3, 6, "경칩"),
    (3, 21, "춘분"),
    (4, 5, "청명"),
    (4, 20, "곡우"),
    (5, 6, "입하"),
    (5, 21, "소만"),
    (6, 6, "망종"),
    (6, 21, "하지"),
    (7, 7, "소서"),
    (7, 23, "대서"),
    (8, 8, "입추"),
    (8, 23, "처서"),
    (9, 8, "백로"),
    (9, 23, "추분"),
    (10, 8, "한로"),
    (10, 23, "상강"),
    (11, 7, "입동"),
    (11, 22, "소설"),
    (12, 7, "대설"),
    (12, 22, "동지"),
)


def _as_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _parse_ymd(raw: str | None) -> date | None:
    s = _as_str(raw)
    if not s:
        return None
    digits = "".join(ch for ch in s if ch.isdigit())
    if len(digits) >= 8:
        try:
            return date(int(digits[0:4]), int(digits[4:6]), int(digits[6:8]))
        except ValueError:
            return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"):
        try:
            return datetime.strptime(s[:10], fmt).date()
        except ValueError:
            continue
    return None


def season_label(d: date) -> str:
    """간단 계절명."""
    m = d.month
    if m in (3, 4, 5):
        return "봄"
    if m in (6, 7, 8):
        return "여름"
    if m in (9, 10, 11):
        return "가을"
    return "겨울"


def solar_term_label(d: date) -> str:
    """관찰일 기준 직전 절기명."""
    md = (d.month, d.day)
    current = _SOLAR_TERMS[-1][2]
    for month, day, name in _SOLAR_TERMS:
        if md >= (month, day):
            current = name
        else:
            break
    return current


def growth_stage_for_date(d: date, crop_nm: str = "") -> str:
    """배(및 동일 달력) 기준 생육단계 — AI 방제 추천과 동일 규칙."""
    _ = (crop_nm or "").strip()
    m, day = d.month, d.day
    if m in (1, 2):
        return "기타"
    if m == 3 or (m == 4 and day <= 15):
        return "개화기"
    if m == 4 and 16 <= day <= 30:
        return "만개기"
    if m == 5:
        return "착과기"
    if m in (6, 7):
        return "비대기"
    if m in (8, 9):
        return "성숙기"
    if m == 10 and day <= 15:
        return "수확전 방제기"
    if m == 10 and day >= 16:
        return "수확기"
    return "기타"


def _row_dict(row: Any) -> dict[str, Any]:
    if row is None:
        return {}
    if isinstance(row, dict):
        return dict(row)
    try:
        return dict(row)
    except Exception:
        return {}


def _resolve_crop_hint(db: Any, farm_cd: str, crop_hint: str) -> str:
    hint = _as_str(crop_hint)
    if hint:
        return hint
    try:
        rows = db.list_farm_crops(farm_cd, active_only=True) if hasattr(db, "list_farm_crops") else []
        if rows:
            return _as_str(_row_dict(rows[0]).get("crop_nm"))
    except Exception:
        pass
    try:
        rows = db.execute_query(
            """
            SELECT crop_nm FROM m_farm_crop
            WHERE farm_cd = ? AND IFNULL(use_yn, 'Y') = 'Y'
            ORDER BY sort_ord, crop_nm LIMIT 1
            """,
            (farm_cd,),
        ) or []
        if rows:
            return _as_str(_row_dict(rows[0]).get("crop_nm"))
    except Exception:
        pass
    return ""


def _weather_from_api(db: Any, farm_cd: str, obs_day: date) -> dict[str, Any] | None:
    """PC AI 추천과 동일: WeatherManager 공공 API 집계. 실패·기본값이면 None."""
    try:
        from core.weather_manager import WeatherManager, convert_to_grid

        loc = db.execute_query(
            "SELECT lat, lon, nx, ny FROM m_farm_info WHERE farm_cd = ?",
            (farm_cd,),
        )
        if not loc:
            return None
        r0 = loc[0]
        if isinstance(r0, dict):
            lat_raw, lon_raw = r0.get("lat"), r0.get("lon")
            nx_raw, ny_raw = r0.get("nx"), r0.get("ny")
        else:
            lat_raw, lon_raw = r0[0], r0[1]
            nx_raw = r0[2] if len(r0) > 2 else None
            ny_raw = r0[3] if len(r0) > 3 else None

        def _f(v: Any) -> float | None:
            try:
                if v is None or str(v).strip() == "":
                    return None
                return float(v)
            except (TypeError, ValueError):
                return None

        lat, lon = _f(lat_raw), _f(lon_raw)
        if lat is None or lon is None:
            return None
        try:
            nx_i = int(nx_raw) if nx_raw is not None and str(nx_raw).strip() != "" else None
            ny_i = int(ny_raw) if ny_raw is not None and str(ny_raw).strip() != "" else None
        except (TypeError, ValueError):
            nx_i, ny_i = None, None
        if nx_i is None or ny_i is None:
            nx_i, ny_i = convert_to_grid(lat, lon)

        d_start = obs_day - timedelta(days=7)
        wm = WeatherManager()
        summary = wm.aggregate_period_for_recommendation(
            nx_i, ny_i, lat, lon, d_start, obs_day
        )
        if not isinstance(summary, dict):
            return None
        if not summary.get("weather_trace_ok"):
            return None
        if str(summary.get("weather_source") or "") == "default":
            return None
        return {
            "source": "api",
            "avg_temp_3d": summary.get("avg_temp_3d"),
            "rain_sum_7d": summary.get("rain_sum_7d"),
            "rain_days_7d": summary.get("rain_days_7d"),
            "avg_humidity_7d": summary.get("avg_humidity_7d"),
        }
    except Exception as exc:  # noqa: BLE001
        _logger.debug("[AI_CTX] weather api skip: %s", type(exc).__name__)
        return None


def _weather_from_db(db: Any, farm_cd: str, obs_ymd: str) -> dict[str, Any] | None:
    """영농일지/기상 저장분 폴백."""
    try:
        rows = None
        if hasattr(db, "get_weather_info"):
            rows = db.get_weather_info(farm_cd, obs_ymd)
        if not rows:
            rows = db.execute_query(
                "SELECT * FROM t_work_master WHERE farm_cd = ? AND work_dt = ?",
                (farm_cd, obs_ymd),
            )
        if not rows:
            return None
        r = _row_dict(rows[0])
        temp_min = r.get("temp_min")
        temp_max = r.get("temp_max")
        precip = r.get("precip")
        humidity = r.get("humidity")
        weather_nm = _as_str(r.get("weather_nm") or r.get("weather_cd"))
        if all(
            v is None or str(v).strip() == ""
            for v in (temp_min, temp_max, precip, humidity, weather_nm)
        ):
            return None
        return {
            "source": "db",
            "temp_min": temp_min,
            "temp_max": temp_max,
            "precip": precip,
            "humidity": humidity,
            "weather_label": weather_nm,
        }
    except Exception as exc:  # noqa: BLE001
        _logger.debug("[AI_CTX] weather db skip: %s", type(exc).__name__)
        return None


def _fmt_num(value: Any, digits: int = 1) -> str:
    try:
        if value is None or str(value).strip() == "":
            return ""
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return ""


def format_context_prompt_text(ctx: dict[str, Any]) -> str:
    """OpenAI user prompt에 붙일 한글 요약 (농장코드 없음)."""
    lines: list[str] = ["[관찰 맥락 — 참고용, 확진 근거로 쓰지 말 것]"]
    if ctx.get("obs_dt"):
        lines.append(f"- 관찰일: {ctx['obs_dt']}")
    if ctx.get("crop_hint"):
        lines.append(f"- 작물: {ctx['crop_hint']}")
    if ctx.get("growth_stage"):
        lines.append(f"- 생육단계: {ctx['growth_stage']}")
    season_bits = [x for x in (ctx.get("season"), ctx.get("solar_term")) if x]
    if season_bits:
        lines.append(f"- 계절·절기: {' / '.join(season_bits)}")

    w = ctx.get("weather") or {}
    if w:
        parts: list[str] = []
        t3 = _fmt_num(w.get("avg_temp_3d"))
        if t3:
            parts.append(f"최근3일 평균기온 {t3}℃")
        rain = _fmt_num(w.get("rain_sum_7d"))
        if rain:
            days = w.get("rain_days_7d")
            day_s = f"({int(days)}일)" if days is not None and str(days).strip() != "" else ""
            parts.append(f"최근7일 강수 {rain}mm{day_s}")
        hum = _fmt_num(w.get("avg_humidity_7d"))
        if hum:
            parts.append(f"최근7일 평균습도 {hum}%")
        tmin, tmax = _fmt_num(w.get("temp_min")), _fmt_num(w.get("temp_max"))
        if tmin or tmax:
            parts.append(f"당일 기온 {tmin or '—'}~{tmax or '—'}℃")
        precip = _fmt_num(w.get("precip"))
        if precip:
            parts.append(f"당일 강수 {precip}mm")
        if w.get("weather_label"):
            parts.append(f"당일 날씨 {w['weather_label']}")
        if parts:
            lines.append(f"- 기상: {', '.join(parts)}")

    if len(lines) <= 1:
        return ""
    return "\n".join(lines)


def build_observation_ai_context(
    db: Any,
    *,
    farm_cd: str,
    obs_id: str,
    crop_hint: str = "",
) -> dict[str, Any]:
    """관찰 1건 기준 AI 컨텍스트 dict + prompt_text."""
    farm = _as_str(farm_cd)
    oid = _as_str(obs_id)
    out: dict[str, Any] = {
        "obs_dt": "",
        "crop_hint": "",
        "growth_stage": "",
        "season": "",
        "solar_term": "",
        "weather": None,
        "prompt_text": "",
    }
    if not farm or not oid:
        return out

    obs: dict[str, Any] = {}
    try:
        if hasattr(db, "get_observation"):
            obs = dict(db.get_observation(farm, oid) or {})
        else:
            rows = db.execute_query(
                """
                SELECT obs_dt, obs_title, site_id
                FROM t_observation_master
                WHERE farm_cd = ? AND obs_id = ? AND IFNULL(use_yn, 'Y') = 'Y'
                """,
                (farm, oid),
            ) or []
            if rows:
                obs = _row_dict(rows[0])
    except Exception:
        obs = {}

    obs_dt_raw = _as_str(obs.get("obs_dt"))
    obs_day = _parse_ymd(obs_dt_raw) or date.today()
    out["obs_dt"] = obs_day.isoformat()
    crop = _resolve_crop_hint(db, farm, crop_hint)
    out["crop_hint"] = crop
    out["growth_stage"] = growth_stage_for_date(obs_day, crop)
    out["season"] = season_label(obs_day)
    out["solar_term"] = solar_term_label(obs_day)

    weather = _weather_from_api(db, farm, obs_day)
    if weather is None:
        weather = _weather_from_db(db, farm, out["obs_dt"])
    out["weather"] = weather
    out["prompt_text"] = format_context_prompt_text(out)
    return out
