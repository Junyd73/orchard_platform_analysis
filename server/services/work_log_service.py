# -*- coding: utf-8 -*-
"""영농일지 MVP 서비스 — PC t_work_master / t_work_detail 계약."""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any

from app.core.exceptions import BusinessRuleError, EntityNotFoundError
from app.db.sqlite import get_sqlite_connection, get_sqlite_write_connection
from app.schemas.work_log import (
    WorkLogDailyResponse,
    WorkLogDayCell,
    WorkLogMasterDto,
    WorkLogMasterUpsertRequest,
    WorkLogMonthlyResponse,
    WorkLogMonthSummary,
    WorkLogSaveResponse,
    WorkLogWorkItem,
    WorkLogWorksUpsertRequest,
    WorkLogWorkUpsertItem,
)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME_RE = re.compile(r"^\d{2}:\d{2}$")
WORK_MAIN_CD = "WK01"
MSG_FUTURE = "영농일지는 오늘까지만 작성할 수 있습니다."
STATUS_IN_PROGRESS_CD = "WO010200"


def _s(v) -> str:
    return str(v or "").strip()


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


def _classify_in_progress(status_cd: str, status_nm: str) -> bool:
    nm = _s(status_nm)
    cd = _s(status_cd).upper()
    if "진행" in nm:
        return True
    return cd in (STATUS_IN_PROGRESS_CD, "ST010300")


def _weather_label_from_cache(payload: dict[str, Any]) -> str:
    """t_weather_cache JSON → 표시용 기상명 (스키마 변경 없음)."""
    for key in ("weather_nm", "weather_text", "weather_label"):
        label = _s(payload.get(key))
        if label and label != "-":
            return label
    cd = _s(payload.get("weather_cd"))
    return cd


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

        start_key = f"{year:04d}{month:02d}01"
        if month == 12:
            end_key = f"{year + 1:04d}0101"
        else:
            end_key = f"{year:04d}{month + 1:02d}01"

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
                    COALESCE(st.code_nm, '') AS status_nm,
                    COALESCE(NULLIF(TRIM(mid.code_nm), ''), TRIM(d.work_mid_cd), '-')
                        AS work_mid_nm,
                    COALESCE(lab.labor_sum, 0) AS labor_sum,
                    COALESCE(exp.expense_sum, 0) AS expense_sum,
                    COALESCE(rc.resource_count, 0) AS resource_count
                FROM t_work_detail d
                LEFT JOIN m_common_code mid
                  ON mid.farm_cd = d.farm_cd AND mid.code_cd = d.work_mid_cd
                LEFT JOIN m_common_code st
                  ON st.farm_cd = d.farm_cd AND st.code_cd = d.status_cd
                LEFT JOIN (
                    SELECT work_id, farm_cd, SUM(COALESCE(daily_wage, 0)) AS labor_sum
                    FROM t_work_resource GROUP BY work_id, farm_cd
                ) lab ON lab.work_id = d.work_id AND lab.farm_cd = d.farm_cd
                LEFT JOIN (
                    SELECT work_id, farm_cd, COUNT(*) AS resource_count
                    FROM t_work_resource GROUP BY work_id, farm_cd
                ) rc ON rc.work_id = d.work_id AND rc.farm_cd = d.farm_cd
                LEFT JOIN (
                    SELECT work_id, farm_cd, SUM(COALESCE(total_amt, 0)) AS expense_sum
                    FROM t_work_expense GROUP BY work_id, farm_cd
                ) exp ON exp.work_id = d.work_id AND exp.farm_cd = d.farm_cd
                WHERE d.farm_cd = ?
                  AND ({wk}) >= ? AND ({wk}) < ?
                ORDER BY ({wk}) ASC, d.work_id ASC
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

        for row in details:
            dt = _norm_dt(row["work_dt"])
            if not dt:
                continue
            cell = days.get(dt)
            if cell is None:
                cell = WorkLogDayCell(work_dt=dt)
                days[dt] = cell
            cell.has_work = True
            cell.work_count += 1
            nm = _s(row["work_mid_nm"]) or "-"
            if nm not in cell.work_names:
                cell.work_names.append(nm)
            cell.labor_sum += float(row["labor_sum"] or 0)
            cell.expense_sum += float(row["expense_sum"] or 0)
            cell.resource_count += int(row["resource_count"] or 0)
            if _classify_in_progress(
                _s(row["status_cd"]), _s(row["status_nm"])
            ):
                cell.has_in_progress = True

        work_day_count = 0
        work_count = 0
        resource_count = 0
        labor_sum = 0.0
        expense_sum = 0.0
        for cell in days.values():
            names = list(cell.work_names or [])
            # 모바일 캘린더 밀도: 전체 작업명 유지, extra는 호환용
            cell.extra_work_count = max(0, len(names) - 2)
            cell.work_names = names
            cell.total_cost = float(cell.labor_sum or 0) + float(cell.expense_sum or 0)
            if cell.has_work:
                work_day_count += 1
                work_count += int(cell.work_count or 0)
                resource_count += int(cell.resource_count or 0)
                labor_sum += float(cell.labor_sum or 0)
                expense_sum += float(cell.expense_sum or 0)

        return WorkLogMonthlyResponse(
            year=year,
            month=month,
            summary=WorkLogMonthSummary(
                work_day_count=work_day_count,
                work_count=work_count,
                resource_count=resource_count,
                labor_sum=labor_sum,
                expense_sum=expense_sum,
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
            )
            for r in rows
        ]
        return WorkLogDailyResponse(
            work_dt=dt, farm_cd=farm, master=master, works=works
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
        farm = self._ensure_farm(farm_cd)
        dt = _norm_dt(work_dt)
        _ensure_not_future(dt)
        uid = _s(user_id) or "MOBILE"
        items = list(body.works or [])
        digits = dt.replace("-", "")
        keep_ids: list[str] = []

        with get_sqlite_write_connection(self._db_path) as conn:
            # ensure master row exists (minimal)
            exists = conn.execute(
                "SELECT 1 FROM t_work_master WHERE farm_cd = ? AND work_dt = ?",
                (farm, dt),
            ).fetchone()
            if not exists:
                try:
                    d = datetime.strptime(dt, "%Y-%m-%d")
                    week = ["월", "화", "수", "목", "금", "토", "일"]
                    dow = week[d.weekday()]
                except ValueError:
                    dow = ""
                conn.execute(
                    """
                    INSERT INTO t_work_master (
                        work_dt, farm_cd, day_of_week, reg_id, reg_dt
                    ) VALUES (?, ?, ?, ?, datetime('now','localtime'))
                    """,
                    (dt, farm, dow or None, uid),
                )

            for i, item in enumerate(items):
                mid = _s(item.work_mid_cd)
                if not mid:
                    raise BusinessRuleError("작업 유형을 선택해 주세요.")
                start = _s(item.start_tm) or None
                end = _s(item.end_tm) or None
                if start and not _TIME_RE.match(start):
                    raise BusinessRuleError("시작 시각은 HH:MM 형식이어야 합니다.")
                if end and not _TIME_RE.match(end):
                    raise BusinessRuleError("종료 시각은 HH:MM 형식이어야 합니다.")
                wid = _s(item.work_id) or f"{digits}-{i + 1:02d}"
                if not wid.startswith(digits):
                    wid = f"{digits}-{i + 1:02d}"
                keep_ids.append(wid)
                conn.execute(
                    """
                    INSERT INTO t_work_detail (
                        work_id, work_dt, farm_cd, work_main_cd, work_mid_cd,
                        work_loc_id, rmk, start_tm, end_tm, status_cd,
                        reg_id, reg_dt
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now','localtime'))
                    ON CONFLICT(work_id) DO UPDATE SET
                        work_mid_cd = excluded.work_mid_cd,
                        work_loc_id = excluded.work_loc_id,
                        rmk = excluded.rmk,
                        start_tm = excluded.start_tm,
                        end_tm = excluded.end_tm,
                        status_cd = excluded.status_cd,
                        mod_id = ?,
                        mod_dt = datetime('now','localtime')
                    """,
                    (
                        wid,
                        dt,
                        farm,
                        WORK_MAIN_CD,
                        mid,
                        _s(item.work_loc_id) or None,
                        _s(item.rmk) or None,
                        start,
                        end,
                        _s(item.status_cd) or None,
                        uid,
                        uid,
                    ),
                )

            prev = [
                _s(r[0])
                for r in conn.execute(
                    """
                    SELECT work_id FROM t_work_detail
                    WHERE farm_cd = ? AND work_dt = ?
                    """,
                    (farm, dt),
                ).fetchall()
                if r and r[0]
            ]
            to_delete = [x for x in prev if x not in keep_ids]
            for wid in to_delete:
                self._assert_can_delete_work(conn, farm, wid)
                conn.execute(
                    "DELETE FROM t_work_detail WHERE farm_cd = ? AND work_id = ?",
                    (farm, wid),
                )

            conn.commit()

        return WorkLogSaveResponse(
            work_dt=dt,
            farm_cd=farm,
            message="작업 목록이 저장되었습니다.",
            work_ids=keep_ids,
        )

    def delete_work(
        self,
        farm_cd: str,
        work_id: str,
        *,
        user_id: str | None = None,
    ) -> WorkLogSaveResponse:
        farm = self._ensure_farm(farm_cd)
        wid = _s(work_id)
        if not wid:
            raise BusinessRuleError("삭제할 작업이 없습니다.")
        with get_sqlite_write_connection(self._db_path) as conn:
            row = conn.execute(
                """
                SELECT work_dt FROM t_work_detail
                WHERE farm_cd = ? AND work_id = ?
                """,
                (farm, wid),
            ).fetchone()
            if not row:
                raise EntityNotFoundError("Work not found")
            dt = _norm_dt(row["work_dt"])
            self._assert_can_delete_work(conn, farm, wid)
            conn.execute(
                "DELETE FROM t_work_detail WHERE farm_cd = ? AND work_id = ?",
                (farm, wid),
            )
            conn.commit()
        return WorkLogSaveResponse(
            work_dt=dt, farm_cd=farm, message="작업이 삭제되었습니다."
        )

    @staticmethod
    def _assert_can_delete_work(
        conn: sqlite3.Connection, farm: str, work_id: str
    ) -> None:
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
                """,
                (farm, work_id),
            ).fetchone()
            if cnt and int(cnt["c"] or 0) > 0:
                raise BusinessRuleError(
                    "재고 확정된 농약 사용이 있어 삭제할 수 없습니다."
                )
        except sqlite3.Error:
            pass
