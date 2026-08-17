# -*- coding: utf-8 -*-
"""영농 일정(Schedule) 서비스 — WLS-001 Phase1."""

from __future__ import annotations

import re
import sqlite3
from datetime import date
from pathlib import Path

from app.core.ops_biz_date import today_ops
from app.core.exceptions import BusinessRuleError, EntityNotFoundError
from app.db.sqlite import get_sqlite_connection, get_sqlite_write_connection
from app.schemas.work_schedule import (
    WorkScheduleConvertData,
    WorkScheduleConvertPrefill,
    WorkScheduleConvertResponse,
    WorkScheduleCreateRequest,
    WorkScheduleCreateResponse,
    WorkScheduleItem,
    WorkScheduleListResponse,
    WorkScheduleMessageResponse,
    WorkScheduleUpdateRequest,
)
from app.services._core_path import ensure_repo_root_on_path

ensure_repo_root_on_path()
from core.work_schedule_constants import (  # noqa: E402
    DEFAULT_WORK_MAIN_CD,
    ERR_FUTURE_CONVERT,
    MSG_FUTURE_CONVERT,
    MSG_INVALID_WORK_TM,
    SCHED_ID_PREFIX,
    SCHED_STATUS_CANCELLED,
    SCHED_STATUS_CONVERTED,
    SCHED_STATUS_PENDING,
    SYNC_STATUS_PENDING,
    WORK_TM_RE,
)
from core.work_schedule_schema import ensure_work_schedule_schema  # noqa: E402

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME_RE = re.compile(WORK_TM_RE)


def _s(v: object | None) -> str:
    return str(v or "").strip()


def _norm_dt(work_dt: str) -> str:
    return _s(work_dt)[:10]


def _norm_tm(work_tm: str | None) -> str | None:
    """HH:MM 또는 None(종일). 빈 문자열은 None."""
    tm = _s(work_tm)
    if not tm:
        return None
    tm = tm[:5]
    if not _TIME_RE.match(tm):
        raise BusinessRuleError(MSG_INVALID_WORK_TM)
    hh, mm = int(tm[:2]), int(tm[3:5])
    if hh > 23 or mm > 59:
        raise BusinessRuleError(MSG_INVALID_WORK_TM)
    return f"{hh:02d}:{mm:02d}"


class WorkScheduleService:
    def __init__(self, db_path: Path | str) -> None:
        self._db_path = Path(db_path)
        ensure_work_schedule_schema(self._db_path)

    def _ensure_farm(self, farm_cd: str) -> str:
        farm = _s(farm_cd)
        if not farm:
            raise BusinessRuleError("농장 코드가 필요합니다.")
        with get_sqlite_connection(self._db_path) as conn:
            row = conn.execute(
                "SELECT 1 FROM m_farm_info WHERE farm_cd = ?",
                (farm,),
            ).fetchone()
            if not row:
                raise EntityNotFoundError("Farm not found")
        return farm

    @staticmethod
    def _row_to_item(row: sqlite3.Row) -> WorkScheduleItem:
        return WorkScheduleItem(
            farm_cd=_s(row["farm_cd"]),
            sched_id=_s(row["sched_id"]),
            work_dt=_s(row["work_dt"]),
            work_tm=(_s(row["work_tm"]) or None) if "work_tm" in row.keys() else None,
            work_main_cd=_s(row["work_main_cd"]) or DEFAULT_WORK_MAIN_CD,
            work_mid_cd=_s(row["work_mid_cd"]),
            work_loc_id=_s(row["work_loc_id"]) or None,
            title=_s(row["title"]) or None,
            contents=_s(row["contents"]) or None,
            sched_status_cd=_s(row["sched_status_cd"]) or SCHED_STATUS_PENDING,
            converted_work_id=_s(row["converted_work_id"]) or None,
            google_event_id=_s(row["google_event_id"]) or None,
            sync_status=_s(row["sync_status"]) or SYNC_STATUS_PENDING,
            last_synced_at=_s(row["last_synced_at"]) or None,
        )

    def list_schedules(
        self,
        farm_cd: str,
        *,
        start_dt: str | None = None,
        end_dt: str | None = None,
        status_cd: str | None = None,
    ) -> WorkScheduleListResponse:
        farm = self._ensure_farm(farm_cd)
        clauses = ["farm_cd = ?"]
        params: list[object] = [farm]
        if start_dt:
            sd = _norm_dt(start_dt)
            if not _DATE_RE.match(sd):
                raise BusinessRuleError("start_dt는 YYYY-MM-DD 형식이어야 합니다.")
            clauses.append("work_dt >= ?")
            params.append(sd)
        if end_dt:
            ed = _norm_dt(end_dt)
            if not _DATE_RE.match(ed):
                raise BusinessRuleError("end_dt는 YYYY-MM-DD 형식이어야 합니다.")
            clauses.append("work_dt <= ?")
            params.append(ed)
        if status_cd:
            clauses.append("sched_status_cd = ?")
            params.append(_s(status_cd))
        where = " AND ".join(clauses)
        with get_sqlite_connection(self._db_path) as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM t_work_schedule
                WHERE {where}
                ORDER BY work_dt ASC, IFNULL(work_tm, '99:99') ASC, sched_id ASC
                """,
                params,
            ).fetchall()
        return WorkScheduleListResponse(
            data=[self._row_to_item(r) for r in rows]
        )

    def create(
        self,
        farm_cd: str,
        body: WorkScheduleCreateRequest,
        *,
        user_id: str | None = None,
    ) -> WorkScheduleCreateResponse:
        farm = self._ensure_farm(farm_cd)
        dt = _norm_dt(body.work_dt)
        if not _DATE_RE.match(dt):
            raise BusinessRuleError("일정일은 YYYY-MM-DD 형식이어야 합니다.")
        tm = _norm_tm(body.work_tm)
        mid = _s(body.work_mid_cd)
        if not mid:
            raise BusinessRuleError("작업 유형(work_mid_cd)을 선택해 주세요.")
        uid = _s(user_id) or "MOBILE"
        with get_sqlite_write_connection(self._db_path) as conn:
            sched_id = self._next_sched_id(conn, farm, dt)
            conn.execute(
                """
                INSERT INTO t_work_schedule (
                    farm_cd, sched_id, work_dt, work_tm, work_main_cd, work_mid_cd,
                    work_loc_id, title, contents, sched_status_cd,
                    converted_work_id, google_event_id, sync_status, last_synced_at,
                    reg_dt, reg_id, mod_dt, mod_id
                ) VALUES (
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    NULL, NULL, ?, NULL,
                    datetime('now','localtime'), ?, datetime('now','localtime'), ?
                )
                """,
                (
                    farm,
                    sched_id,
                    dt,
                    tm,
                    DEFAULT_WORK_MAIN_CD,
                    mid,
                    _s(body.work_loc_id) or None,
                    _s(body.title) or None,
                    _s(body.contents) or None,
                    SCHED_STATUS_PENDING,
                    SYNC_STATUS_PENDING,
                    uid,
                    uid,
                ),
            )
            conn.commit()
        return WorkScheduleCreateResponse(
            data={"sched_id": sched_id, "sched_status_cd": SCHED_STATUS_PENDING}
        )

    def update(
        self,
        farm_cd: str,
        sched_id: str,
        body: WorkScheduleUpdateRequest,
        *,
        user_id: str | None = None,
    ) -> WorkScheduleItem:
        farm = self._ensure_farm(farm_cd)
        sid = _s(sched_id)
        uid = _s(user_id) or "MOBILE"
        with get_sqlite_write_connection(self._db_path) as conn:
            row = conn.execute(
                "SELECT * FROM t_work_schedule WHERE farm_cd = ? AND sched_id = ?",
                (farm, sid),
            ).fetchone()
            if not row:
                raise EntityNotFoundError("Schedule not found")
            new_dt = _norm_dt(body.work_dt) if body.work_dt is not None else _s(row["work_dt"])
            if not _DATE_RE.match(new_dt):
                raise BusinessRuleError("일정일은 YYYY-MM-DD 형식이어야 합니다.")
            if "work_tm" in body.model_fields_set:
                new_tm = _norm_tm(body.work_tm)
            elif "work_tm" in row.keys():
                new_tm = _norm_tm(_s(row["work_tm"]) or None)
            else:
                new_tm = None
            mid = (
                _s(body.work_mid_cd)
                if body.work_mid_cd is not None
                else _s(row["work_mid_cd"])
            )
            if not mid:
                raise BusinessRuleError("작업 유형(work_mid_cd)을 선택해 주세요.")
            status = (
                _s(body.sched_status_cd)
                if body.sched_status_cd is not None
                else _s(row["sched_status_cd"])
            )
            if status not in (
                SCHED_STATUS_PENDING,
                SCHED_STATUS_CONVERTED,
                SCHED_STATUS_CANCELLED,
            ):
                raise BusinessRuleError("유효하지 않은 일정 상태입니다.")
            loc = (
                _s(body.work_loc_id)
                if body.work_loc_id is not None
                else _s(row["work_loc_id"])
            )
            title = _s(body.title) if body.title is not None else _s(row["title"])
            contents = (
                _s(body.contents) if body.contents is not None else _s(row["contents"])
            )
            conn.execute(
                """
                UPDATE t_work_schedule SET
                    work_dt = ?,
                    work_tm = ?,
                    work_mid_cd = ?,
                    work_loc_id = ?,
                    title = ?,
                    contents = ?,
                    sched_status_cd = ?,
                    sync_status = ?,
                    mod_id = ?,
                    mod_dt = datetime('now','localtime')
                WHERE farm_cd = ? AND sched_id = ?
                """,
                (
                    new_dt,
                    new_tm,
                    mid,
                    loc or None,
                    title or None,
                    contents or None,
                    status,
                    SYNC_STATUS_PENDING,
                    uid,
                    farm,
                    sid,
                ),
            )
            conn.commit()
            out = conn.execute(
                "SELECT * FROM t_work_schedule WHERE farm_cd = ? AND sched_id = ?",
                (farm, sid),
            ).fetchone()
        return self._row_to_item(out)

    def delete(
        self,
        farm_cd: str,
        sched_id: str,
        *,
        user_id: str | None = None,
    ) -> WorkScheduleMessageResponse:
        farm = self._ensure_farm(farm_cd)
        sid = _s(sched_id)
        google_eid = ""
        with get_sqlite_write_connection(self._db_path) as conn:
            row = conn.execute(
                """
                SELECT google_event_id FROM t_work_schedule
                WHERE farm_cd = ? AND sched_id = ?
                """,
                (farm, sid),
            ).fetchone()
            if not row:
                raise EntityNotFoundError("Schedule not found")
            google_eid = _s(row["google_event_id"])
            conn.execute(
                "DELETE FROM t_work_schedule WHERE farm_cd = ? AND sched_id = ?",
                (farm, sid),
            )
            conn.commit()
        if google_eid:
            try:
                from app.services.google_calendar_service import (  # noqa: WPS433
                    GoogleCalendarService,
                )

                GoogleCalendarService(self._db_path).delete_schedule_event(
                    farm, sid, google_event_id=google_eid
                )
            except Exception:  # noqa: BLE001
                pass
        return WorkScheduleMessageResponse(message="일정이 삭제되었습니다.")

    def convert_to_draft(
        self,
        farm_cd: str,
        sched_id: str,
        *,
        user_id: str | None = None,
    ) -> WorkScheduleConvertResponse:
        farm = self._ensure_farm(farm_cd)
        sid = _s(sched_id)
        uid = _s(user_id) or "MOBILE"
        today = today_ops().isoformat()

        with get_sqlite_write_connection(self._db_path) as conn:
            row = conn.execute(
                "SELECT * FROM t_work_schedule WHERE farm_cd = ? AND sched_id = ?",
                (farm, sid),
            ).fetchone()
            if not row:
                raise EntityNotFoundError("Schedule not found")

            dt = _s(row["work_dt"])
            status = _s(row["sched_status_cd"])
            existing_wid = _s(row["converted_work_id"])
            mid = _s(row["work_mid_cd"])
            loc = _s(row["work_loc_id"]) or None
            title = _s(row["title"])
            contents = _s(row["contents"])
            work_tm = (
                (_s(row["work_tm"]) or None) if "work_tm" in row.keys() else None
            )
            memo = self._build_memo(title, contents)

            if status == SCHED_STATUS_CANCELLED:
                raise BusinessRuleError("취소된 일정은 실적으로 전환할 수 없습니다.")

            if status == SCHED_STATUS_CONVERTED and existing_wid:
                alive = conn.execute(
                    """
                    SELECT 1 FROM t_work_detail
                    WHERE farm_cd = ? AND work_id = ?
                    """,
                    (farm, existing_wid),
                ).fetchone()
                if alive:
                    return WorkScheduleConvertResponse(
                        data=WorkScheduleConvertData(
                            sched_id=sid,
                            work_id=existing_wid,
                            prefilled_data=WorkScheduleConvertPrefill(
                                work_dt=dt,
                                work_mid_cd=mid,
                                work_loc_id=loc,
                                start_tm=work_tm,
                                memo=memo,
                            ),
                        )
                    )

            if dt > today:
                raise BusinessRuleError(
                    MSG_FUTURE_CONVERT,
                    error_code=ERR_FUTURE_CONVERT,
                )

            work_id = self._next_work_id(conn, farm, dt)
            self._ensure_master_row(conn, farm, dt, uid)
            conn.execute(
                """
                INSERT INTO t_work_detail (
                    work_id, work_dt, farm_cd, work_main_cd, work_mid_cd,
                    work_loc_id, start_tm, end_tm, status_cd, rmk,
                    reg_id, reg_dt, mod_id, mod_dt
                ) VALUES (
                    ?, ?, ?, ?, ?,
                    ?, ?, NULL, NULL, ?,
                    ?, datetime('now','localtime'), ?, datetime('now','localtime')
                )
                """,
                (
                    work_id,
                    dt,
                    farm,
                    DEFAULT_WORK_MAIN_CD,
                    mid,
                    loc,
                    work_tm,
                    memo or None,
                    uid,
                    uid,
                ),
            )
            conn.execute(
                """
                UPDATE t_work_schedule SET
                    sched_status_cd = ?,
                    converted_work_id = ?,
                    mod_id = ?,
                    mod_dt = datetime('now','localtime')
                WHERE farm_cd = ? AND sched_id = ?
                """,
                (SCHED_STATUS_CONVERTED, work_id, uid, farm, sid),
            )
            conn.commit()

        return WorkScheduleConvertResponse(
            data=WorkScheduleConvertData(
                sched_id=sid,
                work_id=work_id,
                prefilled_data=WorkScheduleConvertPrefill(
                    work_dt=dt,
                    work_mid_cd=mid,
                    work_loc_id=loc,
                    start_tm=work_tm,
                    memo=memo,
                ),
            )
        )

    @staticmethod
    def rollback_converted_work(
        conn: sqlite3.Connection,
        farm_cd: str,
        work_id: str,
        *,
        user_id: str = "MOBILE",
    ) -> None:
        """작업 삭제 시 연결된 일정을 PENDING으로 복구."""
        farm = _s(farm_cd)
        wid = _s(work_id)
        if not farm or not wid:
            return
        try:
            conn.execute(
                """
                UPDATE t_work_schedule SET
                    sched_status_cd = ?,
                    converted_work_id = NULL,
                    mod_id = ?,
                    mod_dt = datetime('now','localtime')
                WHERE farm_cd = ?
                  AND converted_work_id = ?
                  AND sched_status_cd = ?
                """,
                (
                    SCHED_STATUS_PENDING,
                    _s(user_id) or "MOBILE",
                    farm,
                    wid,
                    SCHED_STATUS_CONVERTED,
                ),
            )
        except sqlite3.Error:
            # 테이블 미생성 등 — 실적 삭제는 계속
            pass

    @staticmethod
    def _build_memo(title: str, contents: str) -> str:
        title = _s(title)
        contents = _s(contents)
        if title and contents:
            return f"[일정 연동] {title}\n상세: {contents}"
        if title:
            return f"[일정 연동] {title}"
        if contents:
            return f"[일정 연동]\n상세: {contents}"
        return "[일정 연동]"

    @staticmethod
    def _next_sched_id(conn: sqlite3.Connection, farm: str, work_dt: str) -> str:
        ymd = work_dt.replace("-", "")
        prefix = f"{SCHED_ID_PREFIX}{ymd}-"
        row = conn.execute(
            """
            SELECT sched_id FROM t_work_schedule
            WHERE farm_cd = ? AND sched_id LIKE ?
            ORDER BY sched_id DESC LIMIT 1
            """,
            (farm, f"{prefix}%"),
        ).fetchone()
        seq = 1
        if row:
            last = _s(row["sched_id"])
            try:
                seq = int(last.rsplit("-", 1)[-1]) + 1
            except ValueError:
                seq = 1
        return f"{prefix}{seq:03d}"

    @staticmethod
    def _next_work_id(conn: sqlite3.Connection, farm: str, work_dt: str) -> str:
        ymd = work_dt.replace("-", "")
        rows = conn.execute(
            """
            SELECT work_id FROM t_work_detail
            WHERE farm_cd = ? AND work_dt = ?
            """,
            (farm, work_dt),
        ).fetchall()
        max_seq = 0
        for r in rows:
            wid = _s(r["work_id"])
            if not wid.startswith(f"{ymd}-"):
                continue
            try:
                max_seq = max(max_seq, int(wid.split("-", 1)[1]))
            except (IndexError, ValueError):
                continue
        return f"{ymd}-{max_seq + 1:02d}"

    @staticmethod
    def _ensure_master_row(
        conn: sqlite3.Connection, farm: str, work_dt: str, user_id: str
    ) -> None:
        exists = conn.execute(
            "SELECT 1 FROM t_work_master WHERE work_dt = ? AND farm_cd = ?",
            (work_dt, farm),
        ).fetchone()
        if exists:
            return
        dow = ""
        try:
            from datetime import datetime

            d = datetime.strptime(work_dt, "%Y-%m-%d")
            week = ["월", "화", "수", "목", "금", "토", "일"]
            dow = week[d.weekday()]
        except ValueError:
            dow = ""
        conn.execute(
            """
            INSERT INTO t_work_master (
                work_dt, day_of_week, farm_cd, reg_id, reg_dt
            ) VALUES (?, ?, ?, ?, datetime('now','localtime'))
            """,
            (work_dt, dow or None, farm, user_id),
        )
