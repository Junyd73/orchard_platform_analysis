# -*- coding: utf-8 -*-
"""영농일지 MVP 서비스 — PC t_work_master / t_work_detail 계약."""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from app.core.exceptions import BusinessRuleError, EntityNotFoundError
from app.db.sqlite import get_sqlite_connection, get_sqlite_write_connection
from app.schemas.work_log import (
    WorkLogAccountCodeOption,
    WorkLogDailyResponse,
    WorkLogDayCell,
    WorkLogDayWorkItem,
    WorkLogDeletePreviewResponse,
    WorkLogExpenseDto,
    WorkLogIntegratedSaveRequest,
    WorkLogMasterDto,
    WorkLogMasterUpsertRequest,
    WorkLogMonthlyResponse,
    WorkLogMonthSummary,
    WorkLogPartnerOption,
    WorkLogPesticideCancelRequest,
    WorkLogPesticideCancelResponse,
    WorkLogPesticideDocDto,
    WorkLogPesticideItemOption,
    WorkLogPesticideLineDto,
    WorkLogPesticideReplaceRequest,
    WorkLogResourceDto,
    WorkLogSaveResponse,
    WorkLogWeatherFetchResponse,
    WorkLogWorkItem,
    WorkLogWorksUpsertRequest,
    WorkLogWorkUpsertItem,
)
from app.services._core_path import ensure_repo_root_on_path
from app.services.observation_ai_db_bridge import ServerDbBridge

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME_RE = re.compile(r"^\d{2}:\d{2}$")
WORK_MAIN_CD = "WK01"
# m_common_code WK01 — 모바일 캘린더·요약 필터와 동일
WORK_MID_CD_PESTICIDE = "WK010200"  # 방제/약제살포
WORK_MID_CD_FERTILIZER = "WK010800"  # 비료/영양제작업
WORK_MID_CD_OTHER = "WK010600"  # 기타작업
MSG_FUTURE = "영농일지는 오늘까지만 작성할 수 있습니다."
MSG_FUTURE_DETAIL = (
    "미래 일자의 인력·경비·농약·최종승인은 할 수 없습니다. "
    "기본정보만 준비중으로 등록해 주세요."
)
MSG_FUTURE_STATUS = "미래 일자는 준비중(WO010100) 상태만 저장할 수 있습니다."
MSG_FARM_LOCATION_MISSING = (
    "농장의 위도·경도·격자 정보가 없습니다. "
    "과수원 관리에서 위치를 먼저 저장해 주세요."
)
MSG_WEATHER_FETCH_FAILED = "날씨 데이터를 가져오지 못했습니다."
STATUS_PREPARING_CD = "WO010100"
STATUS_IN_PROGRESS_CD = "WO010200"
STATUS_DONE_CD = "WO010300"
STATUS_CANCEL_CD = "WO010400"
# PC WeatherManager.PARTNER / _dashboard_weather_text 와 동일 (core import 회피)
WEATHER_NM_BY_CD = {
    "WT010100": "맑음",
    "WT010200": "구름많음",
    "WT010300": "흐림",
    "WT010400": "비",
    "WT010500": "비/눈",
    "WT010600": "눈",
    "WT010700": "소나기",
    "WT019900": "정보 없음",
}
# PC DBManager.PARTNER_WORKER_TYPES_IN_LABOR_TOTAL 과 동일
LABOR_WORKER_TYPES = ("EMP", "TEMP")
LABOR_WORKER_TYPES_SQL = ", ".join(f"'{t}'" for t in LABOR_WORKER_TYPES)


def _s(v) -> str:
    return str(v or "").strip()


def _allocate_work_id(
    *,
    digits: str,
    requested: str,
    occupied: set[str],
    payload_seen: set[str],
    next_seq: list[int],
) -> str:
    """일자 work_id 채번.

    - 유효하고 이번 payload에서 아직 안 쓴 ID → 그대로 사용(기존 행 수정)
    - 비었거나 payload 내 중복 → DB/occupied 기준 다음 빈 seq
    """
    wid = _s(requested)
    if wid and wid.startswith(digits) and wid not in payload_seen:
        payload_seen.add(wid)
        occupied.add(wid)
        if wid.startswith(digits + "-"):
            tail = wid[len(digits) + 1 :]
            if tail.isdigit():
                next_seq[0] = max(next_seq[0], int(tail))
        return wid
    while True:
        next_seq[0] += 1
        cand = f"{digits}-{next_seq[0]:02d}"
        if cand not in occupied and cand not in payload_seen:
            occupied.add(cand)
            payload_seen.add(cand)
            return cand


def _load_day_work_id_state(
    conn: sqlite3.Connection, farm: str, dt: str, digits: str
) -> tuple[set[str], list[int]]:
    occupied: set[str] = set()
    next_seq = [0]
    for row in conn.execute(
        """
        SELECT work_id FROM t_work_detail
        WHERE farm_cd = ? AND work_dt = ?
        """,
        (farm, dt),
    ).fetchall():
        eid = _s(row["work_id"] if hasattr(row, "keys") else row[0])
        if not eid:
            continue
        occupied.add(eid)
        if eid.startswith(digits + "-"):
            tail = eid[len(digits) + 1 :]
            if tail.isdigit():
                next_seq[0] = max(next_seq[0], int(tail))
    return occupied, next_seq


def _f(v) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _dt_key_sql(alias: str) -> str:
    a = alias
    return f"""
        CASE
            WHEN length(COALESCE(trim({a}), '')) >= 10 AND instr(COALESCE(trim({a}), ''), '-') = 5
                THEN replace(substr(COALESCE(trim({a}), ''), 1, 10), '-', '')
            WHEN length(COALESCE(trim({a}), '')) >= 8
                THEN substr(COALESCE(trim({a}), ''), 1, 8)
            ELSE ''
        END
    """


def _norm_dt(raw) -> str:
    s = _s(raw)
    if len(s) >= 10 and s[4] == "-":
        return s[:10]
    digits = "".join(ch for ch in s if ch.isdigit())
    if len(digits) >= 8:
        return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"
    return s


def _ensure_not_future(work_dt: str) -> None:
    if not _DATE_RE.match(work_dt):
        raise BusinessRuleError("작업일은 YYYY-MM-DD 형식이어야 합니다.")
    if work_dt > date.today().isoformat():
        raise BusinessRuleError(MSG_FUTURE)


def _ensure_date(work_dt: str) -> str:
    dt = _norm_dt(work_dt)
    if not _DATE_RE.match(dt):
        raise BusinessRuleError("작업일은 YYYY-MM-DD 형식이어야 합니다.")
    return dt


def _is_future_dt(work_dt: str) -> bool:
    return work_dt > date.today().isoformat()


def _normalize_status_for_date(work_dt: str, status_cd: str | None) -> str | None:
    """미래일은 준비중만 허용. 없으면 준비중 기본."""
    st = _s(status_cd) or None
    if _is_future_dt(work_dt):
        if st and st != STATUS_PREPARING_CD:
            raise BusinessRuleError(MSG_FUTURE_STATUS)
        return STATUS_PREPARING_CD
    return st


def _calendar_grid_range(year: int, month: int) -> tuple[str, str, str, str]:
    """월간 캘린더(일~토) 그리드 범위 + 해당 월 범위.

    Returns:
        grid_start, grid_end_excl, month_start, month_end_excl (YYYYMMDD)
    """
    first = date(year, month, 1)
    # Python weekday Mon=0..Sun=6 → 일요일 시작 인덱스
    sun0 = (first.weekday() + 1) % 7
    grid_start = first - timedelta(days=sun0)
    if month == 12:
        month_end = date(year + 1, 1, 1)
    else:
        month_end = date(year, month + 1, 1)
    last = month_end - timedelta(days=1)
    last_sun0 = (last.weekday() + 1) % 7
    pad = (6 - last_sun0) % 7
    grid_end = last + timedelta(days=pad + 1)
    return (
        grid_start.strftime("%Y%m%d"),
        grid_end.strftime("%Y%m%d"),
        first.strftime("%Y%m%d"),
        month_end.strftime("%Y%m%d"),
    )


def _dt_in_month_keys(dt: str, month_start: str, month_end: str) -> bool:
    key = dt.replace("-", "")[:8]
    return month_start <= key < month_end


def _classify_in_progress(status_cd: str, status_nm: str) -> bool:
    nm = _s(status_nm)
    cd = _s(status_cd).upper()
    if "진행" in nm:
        return True
    return cd in (STATUS_IN_PROGRESS_CD, "ST010300")


def _is_pesticide_work(mid_cd: str, mid_nm: str) -> bool:
    cd = _s(mid_cd).upper()
    if cd == WORK_MID_CD_PESTICIDE:
        return True
    nm = _s(mid_nm)
    return "방제" in nm or "약제살포" in nm


def _is_fertilizer_work(mid_cd: str, mid_nm: str) -> bool:
    cd = _s(mid_cd).upper()
    if cd == WORK_MID_CD_FERTILIZER:
        return True
    nm = _s(mid_nm)
    return "비료" in nm or "영양제" in nm


def _is_other_work(mid_cd: str, mid_nm: str) -> bool:
    cd = _s(mid_cd).upper()
    if cd == WORK_MID_CD_OTHER:
        return True
    nm = _s(mid_nm)
    return "기타작업" in nm or nm == "기타"


def _weather_nm_fallback(weather_cd: str) -> str:
    cd = _s(weather_cd)
    return WEATHER_NM_BY_CD.get(cd, "") if cd else ""


def _looks_like_weather_cd(value: str) -> bool:
    s = _s(value)
    return len(s) >= 6 and s.upper().startswith("WT") and s.isalnum()


def _weather_label_from_cache(payload: dict[str, Any]) -> str:
    """t_weather_cache JSON → 표시용 기상명. 코드값(WT…)은 이름으로 쓰지 않는다."""
    for key in ("weather_nm", "weather_text", "weather_label"):
        label = _s(payload.get(key))
        if label and label != "-" and not _looks_like_weather_cd(label):
            return label
    return _weather_nm_fallback(_s(payload.get("weather_cd")))


def _master_from_weather_cache(
    *, farm: str, work_dt: str, payload: dict[str, Any]
) -> WorkLogMasterDto:
    """영농일지 master 없을 때 캐시로 표시용 DTO 구성 (저장하지 않음)."""
    return WorkLogMasterDto(
        work_dt=work_dt,
        farm_cd=farm,
        weather_cd=_s(payload.get("weather_cd")) or None,
        weather_nm=_weather_label_from_cache(payload) or None,
        temp_min=_f(payload.get("temp_min")),
        temp_max=_f(payload.get("temp_max")),
        precip=_f(payload.get("precip")),
        humidity=_f(payload.get("humidity")),
        sun_rise=_s(payload.get("sun_rise")) or None,
        sun_set=_s(payload.get("sun_set")) or None,
        sunshine_hr=_f(payload.get("sunshine_hr")),
        wind_max=_f(payload.get("wind_max")),
        wind_min=_f(payload.get("wind_min")),
        work_rmk=None,
    )


def _merge_master_weather_gaps(
    master: WorkLogMasterDto, payload: dict[str, Any]
) -> WorkLogMasterDto:
    """master에 비어 있는 기상 필드만 캐시로 보강."""
    label = _weather_label_from_cache(payload)
    return master.model_copy(
        update={
            "weather_cd": master.weather_cd or (_s(payload.get("weather_cd")) or None),
            "weather_nm": master.weather_nm or (label or None),
            "temp_min": master.temp_min if master.temp_min is not None else _f(payload.get("temp_min")),
            "temp_max": master.temp_max if master.temp_max is not None else _f(payload.get("temp_max")),
            "precip": master.precip if master.precip is not None else _f(payload.get("precip")),
            "humidity": master.humidity if master.humidity is not None else _f(payload.get("humidity")),
            "sun_rise": master.sun_rise or (_s(payload.get("sun_rise")) or None),
            "sun_set": master.sun_set or (_s(payload.get("sun_set")) or None),
            "sunshine_hr": master.sunshine_hr
            if master.sunshine_hr is not None
            else _f(payload.get("sunshine_hr")),
            "wind_max": master.wind_max if master.wind_max is not None else _f(payload.get("wind_max")),
            "wind_min": master.wind_min if master.wind_min is not None else _f(payload.get("wind_min")),
        }
    )


class WorkLogService:
    def __init__(self, *, db_path: Path | str) -> None:
        self._db_path = Path(db_path)

    def _ensure_farm(self, farm_cd: str) -> str:
        farm = _s(farm_cd)
        if not farm:
            raise BusinessRuleError("농장 코드가 없습니다.")
        with get_sqlite_connection(self._db_path) as conn:
            row = conn.execute(
                "SELECT 1 FROM m_farm_info WHERE farm_cd = ? LIMIT 1",
                (farm,),
            ).fetchone()
        if not row:
            raise EntityNotFoundError("Farm not found")
        return farm

    def list_partners(self, farm_cd: str) -> list[WorkLogPartnerOption]:
        """PC CodeManager.get_partners — 인력 직원 콤보."""
        farm = self._ensure_farm(farm_cd)
        with get_sqlite_connection(self._db_path) as conn:
            rows = conn.execute(
                """
                SELECT pt_id, pt_nm, base_price, worker_type_cd
                FROM m_partner
                WHERE farm_cd = ? AND IFNULL(use_yn, 'Y') = 'Y'
                ORDER BY pt_nm ASC
                """,
                (farm,),
            ).fetchall()
        out: list[WorkLogPartnerOption] = []
        for r in rows or []:
            out.append(
                WorkLogPartnerOption(
                    pt_id=str(r["pt_id"]),
                    pt_nm=_s(r["pt_nm"]) or str(r["pt_id"]),
                    base_price=float(r["base_price"])
                    if r["base_price"] is not None
                    else None,
                    worker_type_cd=_s(r["worker_type_cd"]) or None,
                )
            )
        return out

    def list_account_codes(
        self,
        farm_cd: str,
        *,
        prefix: str,
        level: int | None = None,
    ) -> list[WorkLogAccountCodeOption]:
        """PC AccountManager.get_account_codes — 지급방식·지출내용."""
        self._ensure_farm(farm_cd)
        pref = _s(prefix)
        if not pref:
            raise BusinessRuleError("계정 prefix가 필요합니다.")
        sql = """
            SELECT acct_cd, acct_nm, acct_level
            FROM m_account_code
            WHERE acct_cd LIKE ? AND IFNULL(use_yn, 'Y') = 'Y'
        """
        params: list[Any] = [f"{pref}%"]
        if level is not None:
            sql += " AND CAST(acct_level AS TEXT) = ?"
            params.append(str(int(level)))
        sql += " ORDER BY acct_cd ASC"
        with get_sqlite_connection(self._db_path) as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
        return [
            WorkLogAccountCodeOption(
                acct_cd=_s(r["acct_cd"]),
                acct_nm=_s(r["acct_nm"]) or _s(r["acct_cd"]),
                acct_level=int(r["acct_level"])
                if r["acct_level"] is not None
                else None,
            )
            for r in (rows or [])
            if _s(r["acct_cd"])
        ]

    def list_pesticide_items(
        self, farm_cd: str, *, kind: str = "pesticide"
    ) -> list[WorkLogPesticideItemOption]:
        """영농일지 농약/비료 품목. kind=pesticide|fertilizer."""
        from core.pesticide_manager import (
            sql_item_is_nutrient,
            sql_item_not_nutrient,
        )
        from core.work_log_constants import (
            STOCK_ITEM_KIND_FERTILIZER,
            STOCK_ITEM_KIND_PESTICIDE,
        )

        farm = self._ensure_farm(farm_cd)
        k = (kind or STOCK_ITEM_KIND_PESTICIDE).strip().lower()
        if k not in (STOCK_ITEM_KIND_PESTICIDE, STOCK_ITEM_KIND_FERTILIZER):
            raise BusinessRuleError(
                f"kind는 {STOCK_ITEM_KIND_PESTICIDE} 또는 "
                f"{STOCK_ITEM_KIND_FERTILIZER} 만 허용됩니다.",
                code="INVALID_ITEM_KIND",
            )
        cat_sql = (
            sql_item_is_nutrient("m")
            if k == STOCK_ITEM_KIND_FERTILIZER
            else sql_item_not_nutrient("m")
        )
        with get_sqlite_connection(self._db_path) as conn:
            rows = conn.execute(
                f"""
                SELECT item_id, item_nm, spec_nm, qty_piece, pest_category_nm
                FROM m_pesticide_item m
                WHERE farm_cd = ? AND IFNULL(use_yn, 'Y') = 'Y'
                  AND ({cat_sql})
                ORDER BY IFNULL(sort_ord, 0), item_nm
                """,
                (farm,),
            ).fetchall()
        return [
            WorkLogPesticideItemOption(
                item_id=int(r["item_id"]),
                item_nm=_s(r["item_nm"]) or f"품목{r['item_id']}",
                spec_nm=_s(r["spec_nm"]) or None,
                qty_piece=int(r["qty_piece"] or 0),
                pest_category_nm=_s(r["pest_category_nm"]) or None,
            )
            for r in (rows or [])
        ]

    def _load_weather_cache_payload(
        self, farm_cd: str, work_dt: str
    ) -> dict[str, Any] | None:
        """PC WeatherManager가 적재한 t_weather_cache를 읽는다 (테이블 없으면 무시)."""
        try:
            with get_sqlite_connection(self._db_path) as conn:
                row = conn.execute(
                    """
                    SELECT weather_json
                    FROM t_weather_cache
                    WHERE farm_cd = ? AND weather_dt = ?
                    LIMIT 1
                    """,
                    (farm_cd, work_dt),
                ).fetchone()
        except sqlite3.Error:
            return None
        if not row:
            return None
        raw = row["weather_json"] if isinstance(row, sqlite3.Row) else row[0]
        try:
            data = json.loads(_s(raw) or "{}")
        except (TypeError, ValueError, json.JSONDecodeError):
            return None
        return data if isinstance(data, dict) and data else None

    def _load_weather_cache_range(
        self, farm_cd: str, start_key: str, end_key: str
    ) -> dict[str, dict[str, Any]]:
        """그리드 구간 t_weather_cache 일괄 조회. 테이블 없으면 빈 dict."""
        wk = _dt_key_sql("weather_dt")
        try:
            with get_sqlite_connection(self._db_path) as conn:
                rows = conn.execute(
                    f"""
                    SELECT weather_dt, weather_json
                    FROM t_weather_cache
                    WHERE farm_cd = ?
                      AND ({wk}) >= ? AND ({wk}) < ?
                    """,
                    (farm_cd, start_key, end_key),
                ).fetchall()
        except sqlite3.Error:
            return {}
        out: dict[str, dict[str, Any]] = {}
        for row in rows or []:
            dt = _norm_dt(row["weather_dt"])
            if not dt:
                continue
            raw = row["weather_json"] if isinstance(row, sqlite3.Row) else row[1]
            try:
                data = json.loads(_s(raw) or "{}")
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
            if isinstance(data, dict) and data:
                out[dt] = data
        return out

    def _enrich_monthly_days_from_weather_cache(
        self,
        farm: str,
        days: dict[str, WorkLogDayCell],
        *,
        start_key: str,
        end_key: str,
    ) -> None:
        """일간과 동일: master 기상 우선, 없으면 t_weather_cache로 보강."""
        for dt, payload in self._load_weather_cache_range(
            farm, start_key, end_key
        ).items():
            cd = _s(payload.get("weather_cd"))
            label = _weather_label_from_cache(payload)
            if not cd and not label:
                continue
            cell = days.get(dt)
            if cell is None:
                days[dt] = WorkLogDayCell(
                    work_dt=dt,
                    weather_cd=cd,
                    weather_nm=label or "-",
                )
                continue
            if _s(cell.weather_cd):
                continue
            cell.weather_cd = cd
            nm = _s(cell.weather_nm)
            if not nm or nm == "-":
                cell.weather_nm = label or "-"

    def get_monthly(
        self, farm_cd: str, *, year: int, month: int
    ) -> WorkLogMonthlyResponse:
        farm = self._ensure_farm(farm_cd)
        empty = WorkLogMonthlyResponse(
            year=year,
            month=month,
            summary=WorkLogMonthSummary(),
            days={},
        )
        if year < 1 or month < 1 or month > 12:
            return empty

        # days: 캘린더 그리드(앞·뒷달 패딩 포함) · summary: 해당 월만
        grid_start, grid_end, month_start, month_end = _calendar_grid_range(
            year, month
        )
        start_key = grid_start
        end_key = grid_end

        mk = _dt_key_sql("m.work_dt")
        wk = _dt_key_sql("d.work_dt")
        days: dict[str, WorkLogDayCell] = {}

        with get_sqlite_connection(self._db_path) as conn:
            masters = conn.execute(
                f"""
                SELECT
                    m.work_dt, m.weather_cd,
                    COALESCE(w.code_nm, '') AS weather_nm,
                    COALESCE(m.work_rmk, '') AS work_rmk
                FROM t_work_master m
                LEFT JOIN m_common_code w
                  ON w.farm_cd = m.farm_cd AND w.code_cd = m.weather_cd
                WHERE m.farm_cd = ?
                  AND ({mk}) >= ? AND ({mk}) < ?
                """,
                (farm, start_key, end_key),
            ).fetchall()

            details = conn.execute(
                f"""
                SELECT
                    d.work_id, d.work_dt, d.work_mid_cd, d.status_cd,
                    COALESCE(d.rmk, '') AS rmk,
                    COALESCE(st.code_nm, '') AS status_nm,
                    COALESCE(NULLIF(TRIM(mid.code_nm), ''), TRIM(d.work_mid_cd), '-')
                        AS work_mid_nm,
                    COALESCE(lab.labor_sum, 0) AS labor_sum,
                    COALESCE(exp.expense_sum, 0) AS expense_sum
                FROM t_work_detail d
                LEFT JOIN m_common_code mid
                  ON mid.farm_cd = d.farm_cd AND mid.code_cd = d.work_mid_cd
                LEFT JOIN m_common_code st
                  ON st.farm_cd = d.farm_cd AND st.code_cd = d.status_cd
                LEFT JOIN (
                    SELECT
                        r.work_id,
                        r.farm_cd,
                        SUM(COALESCE(r.daily_wage, 0)) AS labor_sum
                    FROM t_work_resource r
                    LEFT JOIN m_partner p
                      ON p.farm_cd = r.farm_cd
                     AND TRIM(CAST(p.pt_id AS TEXT)) = TRIM(CAST(r.emp_cd AS TEXT))
                    WHERE r.farm_cd = ?
                      AND COALESCE(p.worker_type_cd, 'EMP') IN ({LABOR_WORKER_TYPES_SQL})
                    GROUP BY r.work_id, r.farm_cd
                ) lab ON lab.work_id = d.work_id AND lab.farm_cd = d.farm_cd
                LEFT JOIN (
                    SELECT work_id, farm_cd, SUM(COALESCE(total_amt, 0)) AS expense_sum
                    FROM t_work_expense
                    WHERE farm_cd = ?
                    GROUP BY work_id, farm_cd
                ) exp ON exp.work_id = d.work_id AND exp.farm_cd = d.farm_cd
                WHERE d.farm_cd = ?
                  AND ({wk}) >= ? AND ({wk}) < ?
                ORDER BY ({wk}) ASC, d.work_id ASC
                """,
                (farm, farm, farm, start_key, end_key),
            ).fetchall()

            # 일자별 고유 인원·투입시간 (동일인 다작업 = 1명, man_hour 합산)
            # 인원·시간은 OWNER/FAMILY 포함. 인건비(labor_sum)만 EMP/TEMP.
            labor_rows = conn.execute(
                f"""
                SELECT
                    d.work_dt,
                    TRIM(CAST(r.emp_cd AS TEXT)) AS emp_cd,
                    SUM(COALESCE(r.man_hour, 0)) AS hour_sum
                FROM t_work_resource r
                INNER JOIN t_work_detail d
                  ON d.work_id = r.work_id AND d.farm_cd = r.farm_cd
                WHERE r.farm_cd = ?
                  AND ({wk}) >= ? AND ({wk}) < ?
                  AND TRIM(CAST(COALESCE(r.emp_cd, '') AS TEXT)) <> ''
                GROUP BY d.work_dt, TRIM(CAST(r.emp_cd AS TEXT))
                """,
                (farm, start_key, end_key),
            ).fetchall()

        for row in masters:
            dt = _norm_dt(row["work_dt"])
            if not dt:
                continue
            rmk = _s(row["work_rmk"])
            days[dt] = WorkLogDayCell(
                work_dt=dt,
                weather_cd=_s(row["weather_cd"]),
                weather_nm=_s(row["weather_nm"]) or "-",
                work_rmk=rmk,
                has_issue=bool(rmk),
            )

        pesticide_count = 0
        fertilizer_count = 0
        for row in details:
            dt = _norm_dt(row["work_dt"])
            if not dt:
                continue
            in_month = _dt_in_month_keys(dt, month_start, month_end)
            cell = days.get(dt)
            if cell is None:
                cell = WorkLogDayCell(work_dt=dt)
                days[dt] = cell
            cell.has_work = True
            cell.work_count += 1
            mid_cd = _s(row["work_mid_cd"])
            nm = _s(row["work_mid_nm"]) or "-"
            rmk = _s(row["rmk"]) or None
            if nm not in cell.work_names:
                cell.work_names.append(nm)
            status_cd = _s(row["status_cd"]) or None
            # 준비중(일정): 동일 mid라도 건별 표시 — A/B/C 캘린더 누락 방지
            # 기타작업: 메모별 각각 표시 · 그 외 실적: mid 이름 중복 제거
            if status_cd == STATUS_PREPARING_CD or _is_other_work(mid_cd, nm):
                cell.work_items.append(
                    WorkLogDayWorkItem(
                        work_mid_cd=mid_cd,
                        work_mid_nm=nm,
                        status_cd=status_cd,
                        rmk=rmk,
                    )
                )
            elif not any(
                it.work_mid_cd == mid_cd and it.work_mid_nm == nm
                for it in cell.work_items
            ):
                cell.work_items.append(
                    WorkLogDayWorkItem(
                        work_mid_cd=mid_cd,
                        work_mid_nm=nm,
                        status_cd=status_cd,
                        rmk=rmk,
                    )
                )
            cell.labor_sum += float(row["labor_sum"] or 0)
            cell.expense_sum += float(row["expense_sum"] or 0)
            if in_month:
                if _is_pesticide_work(mid_cd, nm):
                    pesticide_count += 1
                elif _is_fertilizer_work(mid_cd, nm):
                    fertilizer_count += 1
            if _classify_in_progress(
                _s(row["status_cd"]), _s(row["status_nm"])
            ):
                cell.has_in_progress = True

        # 일자별: 동일 emp_cd = 1명, man_hour 합 = 투입시간
        month_emp_ids: set[str] = set()
        labor_hour_sum = 0.0
        for row in labor_rows:
            dt = _norm_dt(row["work_dt"])
            emp = _s(row["emp_cd"])
            hours = float(row["hour_sum"] or 0)
            if not dt or not emp:
                continue
            cell = days.get(dt)
            if cell is None:
                cell = WorkLogDayCell(work_dt=dt)
                days[dt] = cell
            cell.resource_count += 1
            cell.labor_hour_sum = float(cell.labor_hour_sum or 0) + hours
            if _dt_in_month_keys(dt, month_start, month_end):
                month_emp_ids.add(emp)
                labor_hour_sum += hours

        # 일간과 동일: 영농일지 없는 날도 t_weather_cache 기상 표시
        self._enrich_monthly_days_from_weather_cache(
            farm, days, start_key=start_key, end_key=end_key
        )

        work_day_count = 0
        work_count = 0
        labor_sum = 0.0
        expense_sum = 0.0
        for cell in days.values():
            names = list(cell.work_names or [])
            # 모바일 캘린더 밀도: 전체 작업명 유지, extra는 호환용
            cell.extra_work_count = max(0, len(names) - 2)
            cell.work_names = names
            cell.total_cost = float(cell.labor_sum or 0) + float(cell.expense_sum or 0)
            cell.labor_hour_sum = round(float(cell.labor_hour_sum or 0), 1)
            if cell.has_work and _dt_in_month_keys(
                cell.work_dt, month_start, month_end
            ):
                work_day_count += 1
                work_count += int(cell.work_count or 0)
                labor_sum += float(cell.labor_sum or 0)
                expense_sum += float(cell.expense_sum or 0)

        return WorkLogMonthlyResponse(
            year=year,
            month=month,
            summary=WorkLogMonthSummary(
                work_day_count=work_day_count,
                work_count=work_count,
                resource_count=len(month_emp_ids),
                labor_hour_sum=round(labor_hour_sum, 1),
                labor_sum=labor_sum,
                expense_sum=expense_sum,
                pesticide_count=pesticide_count,
                fertilizer_count=fertilizer_count,
            ),
            days=days,
        )

    def get_daily(self, farm_cd: str, work_dt: str) -> WorkLogDailyResponse:
        farm = self._ensure_farm(farm_cd)
        dt = _norm_dt(work_dt)
        if not _DATE_RE.match(dt):
            raise BusinessRuleError("작업일은 YYYY-MM-DD 형식이어야 합니다.")

        with get_sqlite_connection(self._db_path) as conn:
            m = conn.execute(
                """
                SELECT m.*, COALESCE(w.code_nm, '') AS weather_nm
                FROM t_work_master m
                LEFT JOIN m_common_code w
                  ON w.farm_cd = m.farm_cd AND w.code_cd = m.weather_cd
                WHERE m.farm_cd = ? AND m.work_dt = ?
                """,
                (farm, dt),
            ).fetchone()
            rows = conn.execute(
                """
                SELECT
                    d.*,
                    COALESCE(mid.code_nm, '') AS work_mid_nm,
                    COALESCE(st.code_nm, '') AS status_nm,
                    COALESCE(site.site_nm, '') AS work_loc_nm
                FROM t_work_detail d
                LEFT JOIN m_common_code mid
                  ON mid.farm_cd = d.farm_cd AND mid.code_cd = d.work_mid_cd
                LEFT JOIN m_common_code st
                  ON st.farm_cd = d.farm_cd AND st.code_cd = d.status_cd
                LEFT JOIN m_farm_site site
                  ON site.farm_cd = d.farm_cd AND site.site_id = d.work_loc_id
                WHERE d.farm_cd = ? AND d.work_dt = ?
                ORDER BY d.work_id ASC
                """,
                (farm, dt),
            ).fetchall()

        master = None
        if m:
            master = WorkLogMasterDto(
                work_dt=dt,
                farm_cd=farm,
                day_of_week=_s(m["day_of_week"]) or None,
                weather_cd=_s(m["weather_cd"]) or None,
                weather_nm=_s(m["weather_nm"]) or None,
                temp_min=_f(m["temp_min"]),
                temp_max=_f(m["temp_max"]),
                precip=_f(m["precip"]),
                humidity=_f(m["humidity"]),
                sun_rise=_s(m["sun_rise"]) or None,
                sun_set=_s(m["sun_set"]) or None,
                sunshine_hr=_f(m["sunshine_hr"]),
                wind_max=_f(m["wind_max"]),
                wind_min=_f(m["wind_min"]),
                work_rmk=_s(m["work_rmk"]) or None,
            )

        # 신규 API 없이 기존 t_weather_cache로 표시용 기상 보강
        cache_payload = self._load_weather_cache_payload(farm, dt)
        if cache_payload:
            if master is None:
                master = _master_from_weather_cache(
                    farm=farm, work_dt=dt, payload=cache_payload
                )
            else:
                master = _merge_master_weather_gaps(master, cache_payload)

        # weather_cd만 있거나 weather_nm이 코드로 들어온 경우 공통코드명으로 보정
        if master is not None:
            cd = _s(master.weather_cd)
            nm = _s(master.weather_nm)
            if cd and (not nm or nm == "-" or _looks_like_weather_cd(nm) or nm == cd):
                resolved = self._resolve_weather_nm(farm, cd)
                if resolved:
                    master = master.model_copy(update={"weather_nm": resolved})

        works = [
            WorkLogWorkItem(
                work_id=_s(r["work_id"]),
                work_dt=dt,
                farm_cd=farm,
                work_main_cd=_s(r["work_main_cd"]) or WORK_MAIN_CD,
                work_mid_cd=_s(r["work_mid_cd"]) or None,
                work_mid_nm=_s(r["work_mid_nm"]) or None,
                work_loc_id=_s(r["work_loc_id"]) or None,
                work_loc_nm=_s(r["work_loc_nm"]) or None,
                rmk=_s(r["rmk"]) or None,
                start_tm=_s(r["start_tm"]) or None,
                end_tm=_s(r["end_tm"]) or None,
                status_cd=_s(r["status_cd"]) or None,
                status_nm=_s(r["status_nm"]) or None,
                google_event_id=(
                    (_s(r["google_event_id"]) or None)
                    if "google_event_id" in r.keys()
                    else None
                ),
                sync_status=(
                    (_s(r["sync_status"]) or None)
                    if "sync_status" in r.keys()
                    else None
                ),
            )
            for r in rows
        ]
        work_ids = [w.work_id for w in works if w.work_id]
        resources, expenses, pesticides = self._load_daily_side_data(
            farm, work_ids
        )
        return WorkLogDailyResponse(
            work_dt=dt,
            farm_cd=farm,
            master=master,
            works=works,
            resources=resources,
            expenses=expenses,
            pesticides=pesticides,
        )

    def _load_daily_side_data(
        self, farm: str, work_ids: list[str]
    ) -> tuple[
        list[WorkLogResourceDto],
        list[WorkLogExpenseDto],
        list[WorkLogPesticideDocDto],
    ]:
        if not work_ids:
            return [], [], []
        ph = ",".join(["?"] * len(work_ids))
        resources: list[WorkLogResourceDto] = []
        expenses: list[WorkLogExpenseDto] = []
        pesticides: list[WorkLogPesticideDocDto] = []
        with get_sqlite_connection(self._db_path) as conn:
            res_rows = conn.execute(
                f"""
                SELECT r.*, COALESCE(p.pt_nm, '') AS emp_nm,
                       COALESCE(pm.acct_nm, '') AS pay_method_nm
                FROM t_work_resource r
                LEFT JOIN m_partner p
                  ON p.farm_cd = r.farm_cd
                 AND TRIM(CAST(p.pt_id AS TEXT)) = TRIM(CAST(r.emp_cd AS TEXT))
                LEFT JOIN m_account_code pm
                  ON pm.acct_cd = r.pay_method_cd
                WHERE r.farm_cd = ? AND r.work_id IN ({ph})
                ORDER BY r.res_id
                """,
                (farm, *work_ids),
            ).fetchall()
            for r in res_rows or []:
                resources.append(
                    WorkLogResourceDto(
                        res_id=int(r["res_id"]) if r["res_id"] is not None else None,
                        work_id=_s(r["work_id"]),
                        emp_cd=_s(r["emp_cd"]),
                        emp_nm=_s(r["emp_nm"]),
                        man_hour=float(r["man_hour"] or 0),
                        daily_wage=float(r["daily_wage"] or 0),
                        pay_method_cd=_s(r["pay_method_cd"]),
                        pay_method_nm=_s(r["pay_method_nm"]),
                        pay_status=_s(r["pay_status"]) or "N",
                        slip_no=_s(r["slip_no"]) or None,
                    )
                )
            exp_rows = conn.execute(
                f"""
                SELECT e.*, COALESCE(ac.acct_nm, '') AS acct_nm,
                       COALESCE(pm.acct_nm, '') AS pay_method_nm
                FROM t_work_expense e
                LEFT JOIN m_account_code ac
                  ON ac.acct_cd = e.acct_cd
                LEFT JOIN m_account_code pm
                  ON pm.acct_cd = e.pay_method_cd
                WHERE e.farm_cd = ? AND e.work_id IN ({ph})
                ORDER BY e.exp_id
                """,
                (farm, *work_ids),
            ).fetchall()
            for e in exp_rows or []:
                expenses.append(
                    WorkLogExpenseDto(
                        exp_id=int(e["exp_id"]) if e["exp_id"] is not None else None,
                        work_id=_s(e["work_id"]),
                        trans_dt=_s(e["trans_dt"]),
                        acct_cd=_s(e["acct_cd"]),
                        acct_nm=_s(e["acct_nm"]),
                        item_nm=_s(e["item_nm"]),
                        total_amt=float(e["total_amt"] or 0),
                        pay_method_cd=_s(e["pay_method_cd"]),
                        pay_method_nm=_s(e["pay_method_nm"]),
                        pay_status=_s(e["pay_status"]) or "N",
                        slip_no=_s(e["slip_no"]) or None,
                    )
                )
            use_rows = conn.execute(
                f"""
                SELECT use_id, work_id, stock_applied_yn, IFNULL(cancel_yn, 'N') AS cancel_yn
                FROM t_pesticide_use
                WHERE farm_cd = ? AND work_id IN ({ph})
                  AND IFNULL(use_yn, 'Y') = 'Y'
                  AND IFNULL(cancel_yn, 'N') != 'Y'
                """,
                (farm, *work_ids),
            ).fetchall()
            for u in use_rows or []:
                uid = int(u["use_id"])
                lines = conn.execute(
                    """
                    SELECT item_id, use_qty, item_nm_snapshot, spec_nm_snapshot,
                           purpose_nm, line_rmk
                    FROM t_pesticide_use_line
                    WHERE use_id = ?
                    ORDER BY line_no, use_line_id
                    """,
                    (uid,),
                ).fetchall()
                pesticides.append(
                    WorkLogPesticideDocDto(
                        work_id=_s(u["work_id"]),
                        use_id=uid,
                        stock_applied_yn=_s(u["stock_applied_yn"]) or "N",
                        lines=[
                            WorkLogPesticideLineDto(
                                item_id=int(ln["item_id"]),
                                use_qty=int(ln["use_qty"] or 0),
                                item_nm_snapshot=_s(ln["item_nm_snapshot"]),
                                spec_nm_snapshot=_s(ln["spec_nm_snapshot"]),
                                purpose_nm=_s(ln["purpose_nm"]),
                                line_rmk=_s(ln["line_rmk"]),
                            )
                            for ln in lines or []
                        ],
                    )
                )
        return resources, expenses, pesticides

    def save_integrated(
        self,
        farm_cd: str,
        work_dt: str,
        body: WorkLogIntegratedSaveRequest,
        user_id: str | None = None,
    ) -> WorkLogSaveResponse:
        """PC 최종승인 = Core WorkLogIntegratedSaveService.save_integrated."""
        ensure_repo_root_on_path()
        from core.work_log_integrated_save_service import (  # noqa: WPS433
            ExpenseRowDto,
            LaborRowDto,
            MasterDto,
            PesticideLineDto,
            WorkDetailDto,
            WorkLogIntegratedSaveService,
            WorkLogSaveError,
            WorkLogSavePayload,
            day_of_week_from_ymd,
        )

        farm = self._ensure_farm(farm_cd)
        dt = _norm_dt(work_dt)
        if not _DATE_RE.match(dt):
            raise BusinessRuleError("작업일은 YYYY-MM-DD 형식이어야 합니다.")
        if _is_future_dt(dt):
            raise BusinessRuleError(MSG_FUTURE_DETAIL)
        uid = _s(user_id) or "MOBILE"

        master_req = body.master
        master = MasterDto(
            work_dt=dt,
            day_of_week=_s(master_req.day_of_week) if master_req else day_of_week_from_ymd(dt),
            weather_cd=_s(master_req.weather_cd) if master_req else "",
            temp_max=float(master_req.temp_max or 0) if master_req else 0.0,
            temp_min=float(master_req.temp_min or 0) if master_req else 0.0,
            precip=float(master_req.precip or 0) if master_req else 0.0,
            humidity=float(master_req.humidity or 0) if master_req else 0.0,
            sun_rise=_s(master_req.sun_rise) if master_req else "",
            sun_set=_s(master_req.sun_set) if master_req else "",
            sunshine_hr=float(master_req.sunshine_hr or 0) if master_req else 0.0,
            wind_max=float(master_req.wind_max or 0) if master_req else 0.0,
            wind_min=float(master_req.wind_min or 0) if master_req else 0.0,
            work_rmk=_s(master_req.work_rmk) if master_req else "",
        )
        if not master.day_of_week:
            master.day_of_week = day_of_week_from_ymd(dt)

        ymd_compact = dt.replace("-", "")
        works_out: list[WorkDetailDto] = []
        with get_sqlite_write_connection(self._db_path) as conn:
            occupied, next_seq = _load_day_work_id_state(
                conn, farm, dt, ymd_compact
            )
            payload_seen: set[str] = set()
            reallocated_ids: list[str] = []
            # payload 내 선행 행이 먼저 seen에 들어가 중복 ID 재할당
            for w in body.works or []:
                mid = _s(w.work_mid_cd)
                if not mid:
                    continue
                requested = _s(w.work_id)
                wid = _allocate_work_id(
                    digits=ymd_compact,
                    requested=requested,
                    occupied=occupied,
                    payload_seen=payload_seen,
                    next_seq=next_seq,
                )
                if not requested or requested != wid:
                    reallocated_ids.append(wid)
                pest_lines = [
                    PesticideLineDto(
                        item_id=int(ln.item_id),
                        use_qty=int(ln.use_qty or 0),
                        item_nm_snapshot=_s(ln.item_nm_snapshot),
                        spec_nm_snapshot=_s(ln.spec_nm_snapshot),
                        purpose_nm=_s(ln.purpose_nm),
                        line_rmk=_s(ln.line_rmk),
                    )
                    for ln in (w.pesticide_lines or [])
                    if int(ln.item_id or 0) > 0
                ]
                mid_nm = _s(w.work_mid_nm)
                # 재고 라인 유무로 is_pesticide=True 강제 금지.
                # WK010800 비료영양 + 영양제 저장이 농약으로 오인되던 원인.
                if pest_lines:
                    is_pest_flag: bool | None = (
                        True
                        if _is_pesticide_work(mid, mid_nm)
                        else (
                            False
                            if _is_fertilizer_work(mid, mid_nm)
                            else None
                        )
                    )
                else:
                    is_pest_flag = None
                works_out.append(
                    WorkDetailDto(
                        work_id=wid,
                        work_mid_cd=mid,
                        work_mid_nm=mid_nm,
                        work_loc_id=w.work_loc_id,
                        rmk=_s(w.rmk),
                        start_tm=_s(w.start_tm),
                        end_tm=_s(w.end_tm),
                        status_cd=_s(w.status_cd),
                        pesticide_lines=pest_lines,
                        replace_pesticide_use_id=w.replace_pesticide_use_id,
                        is_pesticide=is_pest_flag,
                    )
                )

            labor_rows = [
                LaborRowDto(
                    status=_s(r.status) or "INS",
                    res_id=r.res_id,
                    emp_cd=_s(r.emp_cd),
                    emp_nm=_s(r.emp_nm) or _s(r.emp_cd),
                    man_hour=float(r.man_hour or 0),
                    daily_wage=float(r.daily_wage or 0),
                    pay_method_cd=_s(r.pay_method_cd),
                    pay_status=_s(r.pay_status) or "N",
                )
                for r in (body.labor_rows or [])
                if _s(r.emp_cd)
            ]
            expense_rows = [
                ExpenseRowDto(
                    status=_s(r.status) or "INS",
                    exp_id=r.exp_id,
                    acct_cd=_s(r.acct_cd),
                    item_nm=_s(r.item_nm),
                    amt=float(r.amt or 0),
                    pay_method_cd=_s(r.pay_method_cd),
                    pay_status=_s(r.pay_status) or "N",
                    trans_dt=_s(r.trans_dt) or dt,
                )
                for r in (body.expense_rows or [])
                if _s(r.acct_cd)
            ]

            out_ids = {w.work_id for w in works_out}
            labor_wid = _s(body.labor_work_id)
            # 신규/재할당 행이 있으면 인력·경비는 그 행에 (잘못된 -02 예측이 B에 붙지 않게)
            if reallocated_ids:
                if labor_wid not in reallocated_ids:
                    labor_wid = reallocated_ids[-1]
            elif not labor_wid or labor_wid not in out_ids:
                labor_wid = works_out[-1].work_id if works_out else None
            exp_wid = _s(body.expense_work_id) or labor_wid
            if exp_wid not in out_ids:
                exp_wid = labor_wid

            payload = WorkLogSavePayload(
                master=master,
                works=works_out,
                labor_work_id=labor_wid,
                labor_rows=labor_rows,
                removed_res_ids=list(body.removed_res_ids or []),
                expense_work_id=exp_wid,
                expense_rows=expense_rows,
                removed_exp_ids=list(body.removed_exp_ids or []),
                worker_nm=_s(body.worker_nm) or uid,
                worker_id=uid,
            )

            bridge = ServerDbBridge(conn)
            svc = WorkLogIntegratedSaveService(bridge, farm)
            try:
                svc.save_integrated(uid, payload)
            except WorkLogSaveError as e:
                raise BusinessRuleError(e.message) from e

        return WorkLogSaveResponse(
            work_dt=dt,
            farm_cd=farm,
            message="영농일지와 장부가 동기화되었습니다.",
            work_ids=[w.work_id for w in works_out],
        )

    def cancel_pesticide_use(
        self,
        farm_cd: str,
        body: WorkLogPesticideCancelRequest,
        user_id: str | None = None,
    ) -> WorkLogPesticideCancelResponse:
        ensure_repo_root_on_path()
        from core.work_log_integrated_save_service import (  # noqa: WPS433
            WorkLogIntegratedSaveService,
        )

        farm = self._ensure_farm(farm_cd)
        uid = _s(user_id) or "MOBILE"
        if body.use_id is None or int(body.use_id) <= 0:
            raise BusinessRuleError("use_id가 필요합니다.")
        with get_sqlite_write_connection(self._db_path) as conn:
            bridge = ServerDbBridge(conn)
            svc = WorkLogIntegratedSaveService(bridge, farm)
            result = svc.cancel_pesticide_use(uid, use_id=int(body.use_id))
        if not result.ok:
            raise BusinessRuleError(result.message or "농약 사용 취소 실패")
        return WorkLogPesticideCancelResponse(message=result.message)

    def cancel_all_pesticide_uses_for_work(
        self,
        farm_cd: str,
        work_id: str,
        user_id: str | None = None,
    ) -> WorkLogPesticideCancelResponse:
        ensure_repo_root_on_path()
        from core.work_log_integrated_save_service import (  # noqa: WPS433
            WorkLogIntegratedSaveService,
        )

        farm = self._ensure_farm(farm_cd)
        uid = _s(user_id) or "MOBILE"
        with get_sqlite_write_connection(self._db_path) as conn:
            bridge = ServerDbBridge(conn)
            svc = WorkLogIntegratedSaveService(bridge, farm)
            result = svc.cancel_all_pesticide_uses_for_work(uid, work_id)
        if not result.ok:
            raise BusinessRuleError(result.message or "작업 농약 전체 취소 실패")
        return WorkLogPesticideCancelResponse(message=result.message)

    def replace_pesticide_use(
        self,
        farm_cd: str,
        body: "WorkLogPesticideReplaceRequest",
        user_id: str | None = None,
    ) -> WorkLogPesticideCancelResponse:
        ensure_repo_root_on_path()
        from core.work_log_integrated_save_service import (  # noqa: WPS433
            PesticideLineDto,
            PesticideReplacePayload,
            WorkLogIntegratedSaveService,
        )

        farm = self._ensure_farm(farm_cd)
        uid = _s(user_id) or "MOBILE"
        lines = [
            PesticideLineDto(
                item_id=int(ln.item_id),
                use_qty=int(ln.use_qty or 0),
                item_nm_snapshot=_s(ln.item_nm_snapshot),
                spec_nm_snapshot=_s(ln.spec_nm_snapshot),
                purpose_nm=_s(ln.purpose_nm),
                line_rmk=_s(ln.line_rmk),
            )
            for ln in (body.lines or [])
            if int(ln.item_id or 0) > 0
        ]
        payload = PesticideReplacePayload(
            use_dt=_s(body.use_dt),
            site_id=body.site_id,
            worker_nm=_s(body.worker_nm) or uid,
            worker_id=uid,
            work_type_nm=_s(body.work_type_nm),
            rmk=_s(body.rmk) or "영농일지 연동",
            work_id=_s(body.work_id) or None,
            lines=lines,
        )
        with get_sqlite_write_connection(self._db_path) as conn:
            bridge = ServerDbBridge(conn)
            svc = WorkLogIntegratedSaveService(bridge, farm)
            result = svc.replace_pesticide_use(uid, int(body.use_id), payload)
        if not result.ok:
            raise BusinessRuleError(result.message or "농약 교체 저장 실패")
        return WorkLogPesticideCancelResponse(message=result.message)

    def _load_farm_location(
        self, farm_cd: str
    ) -> tuple[float, float, int, int]:
        """m_farm_info 위도·경도·격자. 누락 시 BusinessRuleError."""
        with get_sqlite_connection(self._db_path) as conn:
            row = conn.execute(
                """
                SELECT lat, lon, nx, ny
                FROM m_farm_info
                WHERE farm_cd = ?
                LIMIT 1
                """,
                (farm_cd,),
            ).fetchone()
        if not row:
            raise EntityNotFoundError("Farm not found")
        lat, lon, nx, ny = row["lat"], row["lon"], row["nx"], row["ny"]
        if lat is None or lon is None or nx is None or ny is None:
            raise BusinessRuleError(MSG_FARM_LOCATION_MISSING)
        try:
            return float(lat), float(lon), int(nx), int(ny)
        except (TypeError, ValueError) as exc:
            raise BusinessRuleError(MSG_FARM_LOCATION_MISSING) from exc

    def _resolve_weather_nm(self, farm_cd: str, weather_cd: str) -> str:
        cd = _s(weather_cd)
        if not cd:
            return ""
        with get_sqlite_connection(self._db_path) as conn:
            row = conn.execute(
                """
                SELECT COALESCE(code_nm, '') AS code_nm
                FROM m_common_code
                WHERE farm_cd = ? AND code_cd = ?
                LIMIT 1
                """,
                (farm_cd, cd),
            ).fetchone()
        if row:
            nm = _s(row["code_nm"])
            if nm and not _looks_like_weather_cd(nm):
                return nm
        return _weather_nm_fallback(cd)

    def fetch_weather(
        self,
        farm_cd: str,
        work_dt: str,
        *,
        force_refresh: bool = False,
    ) -> WorkLogWeatherFetchResponse:
        """PC WeatherManager.fetch_work_log_weather 위임 (캐시 적재, master 미저장)."""
        farm = self._ensure_farm(farm_cd)
        dt = _norm_dt(work_dt)
        _ensure_not_future(dt)
        lat, lon, nx, ny = self._load_farm_location(farm)

        ensure_repo_root_on_path()
        from core.weather_manager import WeatherManager  # noqa: WPS433

        with get_sqlite_write_connection(self._db_path) as conn:
            bridge = ServerDbBridge(conn)
            wm = WeatherManager(db_manager=bridge)
            result = wm.fetch_work_log_weather(
                farm,
                dt,
                nx,
                ny,
                lat,
                lon,
                force_refresh=bool(force_refresh),
            )

        if not result or not result.get("ok") or not result.get("data"):
            raise BusinessRuleError(
                _s(result.get("error") if result else "") or MSG_WEATHER_FETCH_FAILED
            )

        data = result["data"]
        if not isinstance(data, dict):
            raise BusinessRuleError(MSG_WEATHER_FETCH_FAILED)

        master = _master_from_weather_cache(farm=farm, work_dt=dt, payload=data)
        weather_cd = _s(master.weather_cd)
        weather_nm = self._resolve_weather_nm(farm, weather_cd) or _s(
            master.weather_nm
        )
        if weather_nm:
            master = master.model_copy(update={"weather_nm": weather_nm})

        source = _s(result.get("source")) or "API"
        elapsed = float(result.get("elapsed") or 0.0)
        return WorkLogWeatherFetchResponse(
            work_dt=dt,
            farm_cd=farm,
            source=source,
            elapsed=elapsed,
            message=f"날씨 조회 완료 · {source}",
            master=master,
        )

    def upsert_master(
        self,
        farm_cd: str,
        work_dt: str,
        body: WorkLogMasterUpsertRequest,
        *,
        user_id: str | None = None,
    ) -> WorkLogSaveResponse:
        farm = self._ensure_farm(farm_cd)
        dt = _norm_dt(work_dt)
        _ensure_not_future(dt)
        uid = _s(user_id) or "MOBILE"
        dow = _s(body.day_of_week)
        if not dow:
            try:
                d = datetime.strptime(dt, "%Y-%m-%d")
                week = ["월", "화", "수", "목", "금", "토", "일"]
                dow = week[d.weekday()]
            except ValueError:
                dow = ""

        with get_sqlite_write_connection(self._db_path) as conn:
            conn.execute(
                """
                INSERT INTO t_work_master (
                    day_of_week, weather_cd, temp_min, temp_max, precip, humidity,
                    sun_rise, sun_set, sunshine_hr, wind_max, wind_min,
                    work_rmk, reg_id, farm_cd, work_dt, reg_dt
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now','localtime'))
                ON CONFLICT(work_dt) DO UPDATE SET
                    day_of_week=excluded.day_of_week,
                    weather_cd=excluded.weather_cd,
                    temp_min=excluded.temp_min,
                    temp_max=excluded.temp_max,
                    precip=excluded.precip,
                    humidity=excluded.humidity,
                    sun_rise=excluded.sun_rise,
                    sun_set=excluded.sun_set,
                    sunshine_hr=excluded.sunshine_hr,
                    wind_max=excluded.wind_max,
                    wind_min=excluded.wind_min,
                    work_rmk=excluded.work_rmk,
                    mod_id=excluded.reg_id,
                    mod_dt=datetime('now','localtime')
                """,
                (
                    dow or None,
                    _s(body.weather_cd) or None,
                    body.temp_min,
                    body.temp_max,
                    body.precip,
                    body.humidity,
                    _s(body.sun_rise) or None,
                    _s(body.sun_set) or None,
                    body.sunshine_hr,
                    body.wind_max,
                    body.wind_min,
                    _s(body.work_rmk) or None,
                    uid,
                    farm,
                    dt,
                ),
            )
            conn.commit()

        return WorkLogSaveResponse(
            work_dt=dt, farm_cd=farm, message="기상·이슈가 저장되었습니다."
        )

    def upsert_works(
        self,
        farm_cd: str,
        work_dt: str,
        body: WorkLogWorksUpsertRequest,
        *,
        user_id: str | None = None,
    ) -> WorkLogSaveResponse:
        """작업-only 저장 — Core save_work_log_basic (인력·경비·Ledger·농약 없음)."""
        ensure_repo_root_on_path()
        from core.work_log_integrated_save_service import (  # noqa: WPS433
            MasterDto,
            WorkDetailDto,
            WorkLogIntegratedSaveService,
            WorkLogSaveError,
            WorkLogSavePayload,
        )

        farm = self._ensure_farm(farm_cd)
        dt = _ensure_date(work_dt)
        uid = _s(user_id) or "MOBILE"
        items = list(body.works or [])
        digits = dt.replace("-", "")
        works: list[WorkDetailDto] = []
        keep_ids: list[str] = []

        with get_sqlite_write_connection(self._db_path) as conn:
            # 기존 채번 + payload 내 중복 work_id → 다음 빈 seq (덮어쓰기 방지)
            occupied, next_seq = _load_day_work_id_state(conn, farm, dt, digits)
            payload_seen: set[str] = set()

            for item in items:
                mid = _s(item.work_mid_cd)
                if not mid:
                    raise BusinessRuleError("작업 유형을 선택해 주세요.")
                start = _s(item.start_tm) or None
                end = _s(item.end_tm) or None
                if start and not _TIME_RE.match(start):
                    raise BusinessRuleError("시작 시각은 HH:MM 형식이어야 합니다.")
                if end and not _TIME_RE.match(end):
                    raise BusinessRuleError("종료 시각은 HH:MM 형식이어야 합니다.")
                status = _normalize_status_for_date(dt, item.status_cd)
                wid = _allocate_work_id(
                    digits=digits,
                    requested=_s(item.work_id),
                    occupied=occupied,
                    payload_seen=payload_seen,
                    next_seq=next_seq,
                )
                keep_ids.append(wid)
                works.append(
                    WorkDetailDto(
                        work_id=wid,
                        work_mid_cd=mid,
                        work_loc_id=_s(item.work_loc_id) or None,
                        rmk=_s(item.rmk) or None,
                        start_tm=start,
                        end_tm=end,
                        status_cd=status,
                        pesticide_lines=[],
                    )
                )

            dow = ""
            try:
                d = datetime.strptime(dt, "%Y-%m-%d")
                week = ["월", "화", "수", "목", "금", "토", "일"]
                dow = week[d.weekday()]
            except ValueError:
                dow = ""

            payload = WorkLogSavePayload(
                master=MasterDto(work_dt=dt, day_of_week=dow),
                works=works,
                worker_nm=uid,
                worker_id=uid,
            )
            bridge = ServerDbBridge(conn)
            # 작업-only: 기존 기상 마스터를 보존(빈 MasterDto로 덮어쓰지 않음)
            row = conn.execute(
                """
                SELECT day_of_week, weather_cd, temp_min, temp_max, precip, humidity,
                       sun_rise, sun_set, sunshine_hr, wind_max, wind_min, work_rmk
                FROM t_work_master WHERE work_dt = ? AND farm_cd = ?
                """,
                (dt, farm),
            ).fetchone()
            if row:
                payload.master = MasterDto(
                    work_dt=dt,
                    day_of_week=_s(row["day_of_week"]) or dow,
                    weather_cd=_s(row["weather_cd"]) or None,
                    temp_min=row["temp_min"],
                    temp_max=row["temp_max"],
                    precip=row["precip"],
                    humidity=row["humidity"],
                    sun_rise=_s(row["sun_rise"]) or None,
                    sun_set=_s(row["sun_set"]) or None,
                    sunshine_hr=row["sunshine_hr"],
                    wind_max=row["wind_max"],
                    wind_min=row["wind_min"],
                    work_rmk=_s(row["work_rmk"]) or None,
                )
            svc = WorkLogIntegratedSaveService(bridge, farm)
            try:
                svc.save_work_log_basic(uid, payload)
            except WorkLogSaveError as e:
                raise BusinessRuleError(e.message or "작업 저장 실패") from e

        return WorkLogSaveResponse(
            work_dt=dt,
            farm_cd=farm,
            message="작업 목록이 저장되었습니다.",
            work_ids=keep_ids,
        )

    def get_delete_preview(
        self,
        farm_cd: str,
        work_id: str,
    ) -> WorkLogDeletePreviewResponse:
        """삭제 확인 모달용 연관정보 조회 (읽기 전용)."""
        farm = self._ensure_farm(farm_cd)
        wid = _s(work_id)
        if not wid:
            raise BusinessRuleError("삭제할 작업이 없습니다.")
        with get_sqlite_connection(self._db_path) as conn:
            cols = {
                str(r[1]) for r in conn.execute("PRAGMA table_info(t_work_detail)")
            }
            select_cols = "work_dt, work_mid_cd, rmk, status_cd"
            if "google_event_id" in cols:
                select_cols += ", google_event_id"
            row = conn.execute(
                f"""
                SELECT {select_cols} FROM t_work_detail
                WHERE farm_cd = ? AND work_id = ?
                """,
                (farm, wid),
            ).fetchone()
            if not row:
                raise EntityNotFoundError("Work not found")
            dt = _norm_dt(row["work_dt"])
            mid = _s(row["work_mid_cd"])
            mid_nm = ""
            if mid:
                nm_row = conn.execute(
                    """
                    SELECT code_nm FROM m_common_code
                    WHERE farm_cd = ? AND code_cd = ?
                    LIMIT 1
                    """,
                    (farm, mid),
                ).fetchone()
                if nm_row:
                    mid_nm = _s(nm_row["code_nm"]) or mid
            labor_row = conn.execute(
                """
                SELECT COUNT(*) AS c,
                       COALESCE(SUM(COALESCE(daily_wage, 0)), 0) AS amt
                FROM t_work_resource
                WHERE farm_cd = ? AND work_id = ?
                """,
                (farm, wid),
            ).fetchone()
            exp_row = conn.execute(
                """
                SELECT COUNT(*) AS c,
                       COALESCE(SUM(COALESCE(total_amt, 0)), 0) AS amt
                FROM t_work_expense
                WHERE farm_cd = ? AND work_id = ?
                """,
                (farm, wid),
            ).fetchone()
            pest_cnt = 0
            pest_items: list[str] = []
            fert_cnt = 0
            fert_items: list[str] = []
            try:
                ensure_repo_root_on_path()
                from core.pesticide_manager import (  # noqa: WPS433
                    is_nutrient_category,
                )

                # use_id별 품목을 영양제(비료) / 그 외(농약)로 분리
                pest_use_ids: set[int] = set()
                fert_use_ids: set[int] = set()
                pest_names_seen: set[str] = set()
                fert_names_seen: set[str] = set()
                has_item_cat = False
                try:
                    col_names = {
                        str(r[1])
                        for r in conn.execute(
                            "PRAGMA table_info(m_pesticide_item)"
                        )
                    }
                    has_item_cat = "pest_category_nm" in col_names
                except sqlite3.Error:
                    has_item_cat = False
                cat_expr = (
                    "IFNULL(i.pest_category_nm, '')"
                    if has_item_cat
                    else "''"
                )
                join_item = (
                    "LEFT JOIN m_pesticide_item i "
                    "ON i.item_id = l.item_id AND i.farm_cd = u.farm_cd"
                    if has_item_cat
                    else ""
                )
                for pr in conn.execute(
                    f"""
                    SELECT u.use_id,
                           COALESCE(NULLIF(TRIM(l.item_nm_snapshot), ''),
                                    CAST(l.item_id AS TEXT)) AS nm,
                           {cat_expr} AS cat
                    FROM t_pesticide_use u
                    JOIN t_pesticide_use_line l ON l.use_id = u.use_id
                    {join_item}
                    WHERE u.farm_cd = ? AND u.work_id = ?
                      AND COALESCE(u.use_yn, 'Y') = 'Y'
                      AND COALESCE(u.cancel_yn, 'N') != 'Y'
                    ORDER BY nm
                    """,
                    (farm, wid),
                ).fetchall():
                    uid = int(pr["use_id"] or 0)
                    nm = _s(pr["nm"])
                    cat = _s(pr["cat"])
                    if is_nutrient_category(cat):
                        if uid:
                            fert_use_ids.add(uid)
                        if nm and nm not in fert_names_seen:
                            fert_names_seen.add(nm)
                            fert_items.append(nm)
                    else:
                        if uid:
                            pest_use_ids.add(uid)
                        if nm and nm not in pest_names_seen:
                            pest_names_seen.add(nm)
                            pest_items.append(nm)
                pest_cnt = len(pest_use_ids)
                fert_cnt = len(fert_use_ids)
            except sqlite3.Error:
                pass
            photo_cnt = 0
            try:
                photo_cnt = int(
                    conn.execute(
                        """
                        SELECT COUNT(*) AS c FROM t_work_photo
                        WHERE farm_cd = ? AND work_id = ?
                          AND COALESCE(use_yn, 'Y') = 'Y'
                        """,
                        (farm, wid),
                    ).fetchone()["c"]
                    or 0
                )
            except sqlite3.Error:
                pass
            google_linked = bool(
                "google_event_id" in cols and _s(row["google_event_id"])
            )
            fertilizer = _is_fertilizer_work(mid, mid_nm)
            has_related = (
                int(labor_row["c"] or 0) > 0
                or int(exp_row["c"] or 0) > 0
                or pest_cnt > 0
                or fert_cnt > 0
                or photo_cnt > 0
                or google_linked
            )
            fert_note = None
            if fert_cnt > 0:
                fert_note = "비료(영양제) 사용·재고 복구 포함"
            elif fertilizer:
                fert_note = "비료/영양제 작업"
            return WorkLogDeletePreviewResponse(
                work_id=wid,
                work_dt=dt,
                farm_cd=farm,
                work_mid_cd=mid or None,
                work_mid_nm=mid_nm or None,
                rmk=_s(row["rmk"]) or None,
                status_cd=_s(row["status_cd"]) or None,
                labor_count=int(labor_row["c"] or 0),
                labor_amount=float(labor_row["amt"] or 0),
                expense_count=int(exp_row["c"] or 0),
                expense_amount=float(exp_row["amt"] or 0),
                pesticide_count=pest_cnt,
                pesticide_item_names=pest_items,
                fertilizer_count=fert_cnt,
                fertilizer_item_names=fert_items,
                is_fertilizer_work=fertilizer,
                fertilizer_note=fert_note,
                photo_count=photo_cnt,
                google_calendar_linked=google_linked,
                has_related=has_related,
            )

    def delete_work(
        self,
        farm_cd: str,
        work_id: str,
        *,
        user_id: str | None = None,
    ) -> WorkLogSaveResponse:
        """작업 삭제 orchestrator — 인력/경비 역분개·농약 취소·사진 soft 재사용."""
        ensure_repo_root_on_path()
        from core.work_log_integrated_save_service import (  # noqa: WPS433
            WorkLogIntegratedSaveService,
            WorkLogSaveError,
        )

        farm = self._ensure_farm(farm_cd)
        wid = _s(work_id)
        if not wid:
            raise BusinessRuleError("삭제할 작업이 없습니다.")
        uid = _s(user_id) or "MOBILE"
        google_eid = ""
        dt = ""
        with get_sqlite_write_connection(self._db_path) as conn:
            cols = {
                str(r[1]) for r in conn.execute("PRAGMA table_info(t_work_detail)")
            }
            select_cols = "work_dt"
            if "google_event_id" in cols:
                select_cols = "work_dt, google_event_id"
            row = conn.execute(
                f"""
                SELECT {select_cols} FROM t_work_detail
                WHERE farm_cd = ? AND work_id = ?
                """,
                (farm, wid),
            ).fetchone()
            if not row:
                raise EntityNotFoundError("Work not found")
            dt = _norm_dt(row["work_dt"])
            google_eid = (
                _s(row["google_event_id"])
                if "google_event_id" in cols
                else ""
            )

            def _schedule_rollback(cur: sqlite3.Cursor) -> None:
                try:
                    from app.services.work_schedule_service import (  # noqa: WPS433
                        WorkScheduleService,
                    )

                    WorkScheduleService.rollback_converted_work(
                        cur.connection, farm, wid, user_id=uid
                    )
                except Exception:  # noqa: BLE001
                    pass

            bridge = ServerDbBridge(conn)
            svc = WorkLogIntegratedSaveService(bridge, farm)
            try:
                svc.purge_work_related(
                    uid,
                    wid,
                    dt,
                    extra_cursor_ops=[_schedule_rollback],
                )
            except WorkLogSaveError as e:
                raise BusinessRuleError(e.message or "작업 삭제 실패") from e

        if google_eid:
            try:
                from app.services.google_calendar_service import (  # noqa: WPS433
                    GoogleCalendarService,
                )

                GoogleCalendarService(self._db_path).delete_work_event(
                    farm, wid, google_event_id=google_eid
                )
            except Exception:  # noqa: BLE001
                pass
        return WorkLogSaveResponse(
            work_dt=dt, farm_cd=farm, message="작업이 삭제되었습니다."
        )

    @staticmethod
    def _assert_can_delete_work(
        conn: sqlite3.Connection, farm: str, work_id: str
    ) -> None:
        """레거시 차단 검사 — 신규 삭제는 purge_work_related 경로를 사용."""
        for table, label in (
            ("t_work_resource", "인력"),
            ("t_work_expense", "경비"),
        ):
            try:
                cnt = conn.execute(
                    f"""
                    SELECT COUNT(*) AS c FROM {table}
                    WHERE farm_cd = ? AND work_id = ?
                    """,
                    (farm, work_id),
                ).fetchone()
                if int(cnt["c"] or 0) > 0:
                    raise BusinessRuleError(
                        f"연결된 {label} 데이터가 있어 삭제할 수 없습니다. "
                        "PC에서 먼저 정리해 주세요."
                    )
            except sqlite3.Error:
                continue
        try:
            cnt = conn.execute(
                """
                SELECT COUNT(*) AS c FROM t_pesticide_use
                WHERE farm_cd = ? AND work_id = ?
                  AND COALESCE(stock_applied_yn, 'N') = 'Y'
                  AND COALESCE(cancel_yn, 'N') != 'Y'
                """,
                (farm, work_id),
            ).fetchone()
            if cnt and int(cnt["c"] or 0) > 0:
                raise BusinessRuleError(
                    "재고 확정된 농약 사용이 있어 삭제할 수 없습니다."
                )
        except sqlite3.Error:
            pass
