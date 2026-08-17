# -*- coding: utf-8 -*-
"""구글 캘린더 OAuth·동기화 — WLS-001 Phase3 (Schedule만, Orchard 우선)."""

from __future__ import annotations

import base64
import json
import re
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

from app.core.config import Settings, get_settings
from app.core.ops_biz_date import today_ops
from app.core.exceptions import BusinessRuleError, EntityNotFoundError
from app.db.sqlite import get_sqlite_connection, get_sqlite_write_connection
from app.services._core_path import ensure_repo_root_on_path
from app.services.google_calendar_client import (
    GoogleCalendarClientError,
    build_authorization_url,
    delete_event,
    exchange_code_for_tokens,
    expiry_iso_from_expires_in,
    fetch_user_email,
    list_events,
    refresh_access_token,
    revoke_token,
    upsert_event,
)

ensure_repo_root_on_path()
from core.google_calendar_constants import (  # noqa: E402
    DESC_MARKER_PREFIX,
    DESC_MARKER_WORK_PREFIX,
    ERR_GOOGLE_NOT_CONFIGURED,
    ERR_GOOGLE_NOT_CONNECTED,
    EXT_PROP_FARM_CD,
    EXT_PROP_KIND,
    EXT_PROP_SCHED_ID,
    EXT_PROP_WORK_ID,
    GOOGLE_CALENDAR_ID_PRIMARY,
    MSG_GOOGLE_IMPORT_EMPTY,
    MSG_GOOGLE_NOT_CONFIGURED,
    MSG_GOOGLE_NOT_CONNECTED,
    ORCHARD_KIND_SCHED,
    ORCHARD_KIND_WORK,
)
from core.google_calendar_schema import ensure_google_calendar_schema  # noqa: E402
from core.work_schedule_constants import (  # noqa: E402
    DEFAULT_WORK_MAIN_CD,
    GOOGLE_EVENT_DEFAULT_DURATION_MIN,
    GOOGLE_EVENT_TIMEZONE,
    SCHED_ID_PREFIX,
    SCHED_STATUS_CANCELLED,
    SCHED_STATUS_PENDING,
    SYNC_STATUS_FAILED,
    SYNC_STATUS_PENDING,
    SYNC_STATUS_SYNCED,
)
from core.work_schedule_schema import ensure_work_schedule_schema  # noqa: E402

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME_RE = re.compile(r"^\d{2}:\d{2}$")
_DEFAULT_IMPORT_MID = "WK010100"
STATUS_PREPARING_CD = "WO010100"
_KST = timezone(timedelta(hours=9))


def _s(v: object | None) -> str:
    return str(v or "").strip()


def _parse_event_start(start_obj: dict[str, Any]) -> tuple[str, str | None] | None:
    """Google start → (work_dt, work_tm|None). 종일은 work_tm=None."""
    work_dt = _s(start_obj.get("date"))
    if _DATE_RE.match(work_dt):
        return work_dt, None
    raw = _s(start_obj.get("dateTime"))
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    local = dt.astimezone(_KST)
    return local.date().isoformat(), local.strftime("%H:%M")


def _parse_event_end_tm(end_obj: dict[str, Any], work_dt: str) -> str | None:
    raw = _s(end_obj.get("dateTime"))
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    local = dt.astimezone(_KST)
    if local.date().isoformat() != work_dt:
        return local.strftime("%H:%M")
    return local.strftime("%H:%M")


def _timed_end_iso(work_dt: str, work_tm: str, end_tm: str | None = None) -> str:
    if end_tm and _TIME_RE.match(end_tm):
        end = datetime.fromisoformat(f"{work_dt}T{end_tm}:00")
        start = datetime.fromisoformat(f"{work_dt}T{work_tm}:00")
        if end <= start:
            end = start + timedelta(minutes=GOOGLE_EVENT_DEFAULT_DURATION_MIN)
        return end.strftime("%Y-%m-%dT%H:%M:%S")
    start = datetime.fromisoformat(f"{work_dt}T{work_tm}:00")
    end = start + timedelta(minutes=GOOGLE_EVENT_DEFAULT_DURATION_MIN)
    return end.strftime("%Y-%m-%dT%H:%M:%S")


def build_work_event_summary(*, loc_nm: str, mid_nm: str) -> str:
    parts = [p for p in (_s(loc_nm), _s(mid_nm)) if p]
    return " ".join(parts) or "영농 작업"


def build_work_event_description(*, status_nm: str, rmk: str, work_id: str) -> str:
    parts: list[str] = []
    st = _s(status_nm)
    if st:
        parts.append(f"상태: {st}")
    note = _s(rmk)
    if note:
        parts.append(note)
    parts.append(f"{DESC_MARKER_WORK_PREFIX}{work_id}]")
    return "\n".join(parts)


class GoogleCalendarService:
    def __init__(
        self,
        db_path: Path | str,
        *,
        settings: Settings | None = None,
    ) -> None:
        self._db_path = Path(db_path)
        self._settings = settings or get_settings()
        ensure_work_schedule_schema(self._db_path)
        ensure_google_calendar_schema(self._db_path)

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

    def _require_configured(self) -> None:
        if not self._settings.google_oauth_configured:
            raise BusinessRuleError(
                MSG_GOOGLE_NOT_CONFIGURED,
                error_code=ERR_GOOGLE_NOT_CONFIGURED,
            )

    def status(self, farm_cd: str) -> dict[str, Any]:
        farm = self._ensure_farm(farm_cd)
        configured = self._settings.google_oauth_configured
        connected = False
        email = None
        calendar_id = GOOGLE_CALENDAR_ID_PRIMARY
        if configured:
            tok = self._load_token_row(farm)
            if tok and (
                _s(tok.get("access_token")) or _s(tok.get("refresh_token"))
            ):
                connected = True
                email = _s(tok.get("connected_email")) or None
                calendar_id = (
                    _s(tok.get("calendar_id")) or GOOGLE_CALENDAR_ID_PRIMARY
                )
        return {
            "configured": configured,
            "connected": connected,
            "connected_email": email,
            "calendar_id": calendar_id,
        }

    def build_auth_url(
        self,
        farm_cd: str,
        *,
        user_id: str | None = None,
        success_redirect: str | None = None,
    ) -> dict[str, str]:
        self._require_configured()
        farm = self._ensure_farm(farm_cd)
        uid = _s(user_id) or self._settings.default_user_id
        success = _s(success_redirect) or self._settings.google_oauth_success_redirect
        state = self._encode_state(
            {"farm_cd": farm, "user_id": uid, "success_redirect": success}
        )
        url = build_authorization_url(
            client_id=self._settings.google_oauth_client_id,
            redirect_uri=self._settings.google_oauth_redirect_uri,
            state=state,
        )
        return {"auth_url": url, "state": state}

    def handle_oauth_callback(self, *, code: str, state: str) -> str:
        self._require_configured()
        payload = self._decode_state(state)
        farm = self._ensure_farm(_s(payload.get("farm_cd")))
        uid = _s(payload.get("user_id")) or self._settings.default_user_id
        success = _s(payload.get("success_redirect")) or (
            self._settings.google_oauth_success_redirect
        )
        try:
            tokens = exchange_code_for_tokens(
                client_id=self._settings.google_oauth_client_id,
                client_secret=self._settings.google_oauth_client_secret,
                redirect_uri=self._settings.google_oauth_redirect_uri,
                code=_s(code),
            )
        except GoogleCalendarClientError as exc:
            raise BusinessRuleError(exc.message, error_code=exc.code) from exc
        access = _s(tokens.get("access_token"))
        refresh = _s(tokens.get("refresh_token"))
        if not access:
            raise BusinessRuleError("구글 액세스 토큰을 받지 못했습니다.")
        email = fetch_user_email(access)
        expiry = expiry_iso_from_expires_in(tokens.get("expires_in"))
        with get_sqlite_write_connection(self._db_path) as conn:
            prev = conn.execute(
                "SELECT refresh_token FROM t_google_calendar_token WHERE farm_cd = ?",
                (farm,),
            ).fetchone()
            if not refresh and prev:
                refresh = _s(prev["refresh_token"])
            conn.execute(
                """
                INSERT INTO t_google_calendar_token (
                    farm_cd, user_id, access_token, refresh_token, token_expiry,
                    calendar_id, connected_email, scope_text, use_yn,
                    reg_id, reg_dt, mod_id, mod_dt
                ) VALUES (
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, 'Y',
                    ?, datetime('now','localtime'), ?, datetime('now','localtime')
                )
                ON CONFLICT(farm_cd) DO UPDATE SET
                    user_id = excluded.user_id,
                    access_token = excluded.access_token,
                    refresh_token = COALESCE(
                        excluded.refresh_token,
                        t_google_calendar_token.refresh_token
                    ),
                    token_expiry = excluded.token_expiry,
                    connected_email = excluded.connected_email,
                    scope_text = excluded.scope_text,
                    use_yn = 'Y',
                    mod_id = excluded.mod_id,
                    mod_dt = datetime('now','localtime')
                """,
                (
                    farm,
                    uid,
                    access,
                    refresh or None,
                    expiry,
                    GOOGLE_CALENDAR_ID_PRIMARY,
                    email or None,
                    _s(tokens.get("scope")) or None,
                    uid,
                    uid,
                ),
            )
            conn.commit()
        sep = "&" if "?" in success else "?"
        return f"{success}{sep}google=connected&farm_cd={quote(farm)}"

    def disconnect(self, farm_cd: str, *, user_id: str | None = None) -> dict[str, Any]:
        farm = self._ensure_farm(farm_cd)
        uid = _s(user_id) or self._settings.default_user_id
        with get_sqlite_write_connection(self._db_path) as conn:
            row = conn.execute(
                """
                SELECT access_token, refresh_token FROM t_google_calendar_token
                WHERE farm_cd = ?
                """,
                (farm,),
            ).fetchone()
            if row:
                for t in (_s(row["access_token"]), _s(row["refresh_token"])):
                    if t:
                        revoke_token(t)
            conn.execute(
                """
                UPDATE t_google_calendar_token SET
                    use_yn = 'N',
                    access_token = '',
                    refresh_token = NULL,
                    mod_id = ?,
                    mod_dt = datetime('now','localtime')
                WHERE farm_cd = ?
                """,
                (uid, farm),
            )
            conn.commit()
        return {"success": True, "connected": False}

    def push_work(
        self,
        farm_cd: str,
        work_id: str,
        *,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """실적 1건 → 구글 upsert."""
        self._require_configured()
        farm = self._ensure_farm(farm_cd)
        wid = _s(work_id)
        uid = _s(user_id) or self._settings.default_user_id
        access, calendar_id = self._ensure_access_token(farm)
        with get_sqlite_connection(self._db_path) as conn:
            row = conn.execute(
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
                WHERE d.farm_cd = ? AND d.work_id = ?
                """,
                (farm, wid),
            ).fetchone()
        if not row:
            raise EntityNotFoundError("Work not found")
        event_id = (
            (_s(row["google_event_id"]) or None)
            if "google_event_id" in row.keys()
            else None
        )
        body = self._work_event_body(farm, row)
        try:
            result = upsert_event(
                access_token=access,
                calendar_id=calendar_id,
                event_id=event_id,
                body=body,
            )
        except GoogleCalendarClientError as exc:
            with get_sqlite_write_connection(self._db_path) as conn:
                self._set_work_sync(conn, farm, wid, None, SYNC_STATUS_FAILED, uid)
                conn.commit()
            raise BusinessRuleError(exc.message, error_code=exc.code) from exc
        new_id = _s(result.get("id")) or event_id
        with get_sqlite_write_connection(self._db_path) as conn:
            self._set_work_sync(conn, farm, wid, new_id, SYNC_STATUS_SYNCED, uid)
            conn.commit()
        return {
            "success": True,
            "kind": ORCHARD_KIND_WORK,
            "work_id": wid,
            "google_event_id": new_id,
            "created": not bool(event_id),
        }

    def push_schedule(
        self,
        farm_cd: str,
        sched_id: str,
        *,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """예정 1건 → 구글 upsert."""
        self._require_configured()
        farm = self._ensure_farm(farm_cd)
        sid = _s(sched_id)
        uid = _s(user_id) or self._settings.default_user_id
        access, calendar_id = self._ensure_access_token(farm)
        with get_sqlite_connection(self._db_path) as conn:
            row = conn.execute(
                """
                SELECT s.*, COALESCE(mid.code_nm, '') AS work_mid_nm
                FROM t_work_schedule s
                LEFT JOIN m_common_code mid
                  ON mid.farm_cd = s.farm_cd AND mid.code_cd = s.work_mid_cd
                WHERE s.farm_cd = ? AND s.sched_id = ?
                """,
                (farm, sid),
            ).fetchone()
        if not row:
            raise EntityNotFoundError("Schedule not found")
        status = _s(row["sched_status_cd"])
        event_id = _s(row["google_event_id"]) or None
        if status == SCHED_STATUS_CANCELLED:
            if event_id:
                try:
                    delete_event(
                        access_token=access,
                        calendar_id=calendar_id,
                        event_id=event_id,
                    )
                except GoogleCalendarClientError as exc:
                    raise BusinessRuleError(exc.message, error_code=exc.code) from exc
            with get_sqlite_write_connection(self._db_path) as conn:
                conn.execute(
                    """
                    UPDATE t_work_schedule SET
                        google_event_id = NULL,
                        sync_status = ?,
                        last_synced_at = datetime('now','localtime'),
                        mod_id = ?,
                        mod_dt = datetime('now','localtime')
                    WHERE farm_cd = ? AND sched_id = ?
                    """,
                    (SYNC_STATUS_SYNCED, uid, farm, sid),
                )
                conn.commit()
            return {
                "success": True,
                "kind": ORCHARD_KIND_SCHED,
                "sched_id": sid,
                "google_event_id": None,
                "deleted": True,
            }
        body = self._schedule_event_body(farm, row)
        try:
            result = upsert_event(
                access_token=access,
                calendar_id=calendar_id,
                event_id=event_id,
                body=body,
            )
        except GoogleCalendarClientError as exc:
            with get_sqlite_write_connection(self._db_path) as conn:
                conn.execute(
                    """
                    UPDATE t_work_schedule SET
                        sync_status = ?,
                        mod_id = ?,
                        mod_dt = datetime('now','localtime')
                    WHERE farm_cd = ? AND sched_id = ?
                    """,
                    (SYNC_STATUS_FAILED, uid, farm, sid),
                )
                conn.commit()
            raise BusinessRuleError(exc.message, error_code=exc.code) from exc
        new_id = _s(result.get("id")) or event_id
        with get_sqlite_write_connection(self._db_path) as conn:
            conn.execute(
                """
                UPDATE t_work_schedule SET
                    google_event_id = ?,
                    sync_status = ?,
                    last_synced_at = datetime('now','localtime'),
                    mod_id = ?,
                    mod_dt = datetime('now','localtime')
                WHERE farm_cd = ? AND sched_id = ?
                """,
                (new_id, SYNC_STATUS_SYNCED, uid, farm, sid),
            )
            conn.commit()
        return {
            "success": True,
            "kind": ORCHARD_KIND_SCHED,
            "sched_id": sid,
            "google_event_id": new_id,
            "created": not bool(event_id),
        }

    def delete_work_event(
        self,
        farm_cd: str,
        work_id: str,
        *,
        google_event_id: str | None = None,
    ) -> None:
        """실적 삭제 시 연동 구글 이벤트 제거(연결 시에만)."""
        if not self._settings.google_oauth_configured:
            return
        farm = _s(farm_cd)
        wid = _s(work_id)
        eid = _s(google_event_id)
        if not eid:
            with get_sqlite_connection(self._db_path) as conn:
                row = conn.execute(
                    """
                    SELECT google_event_id FROM t_work_detail
                    WHERE farm_cd = ? AND work_id = ?
                    """,
                    (farm, wid),
                ).fetchone()
            if row and "google_event_id" in row.keys():
                eid = _s(row["google_event_id"])
        if not eid:
            return
        try:
            access, calendar_id = self._ensure_access_token(farm)
            delete_event(
                access_token=access,
                calendar_id=calendar_id,
                event_id=eid,
            )
        except (BusinessRuleError, GoogleCalendarClientError):
            return

    def delete_schedule_event(
        self,
        farm_cd: str,
        sched_id: str,
        *,
        google_event_id: str | None = None,
    ) -> None:
        if not self._settings.google_oauth_configured:
            return
        farm = _s(farm_cd)
        sid = _s(sched_id)
        eid = _s(google_event_id)
        if not eid:
            with get_sqlite_connection(self._db_path) as conn:
                row = conn.execute(
                    """
                    SELECT google_event_id FROM t_work_schedule
                    WHERE farm_cd = ? AND sched_id = ?
                    """,
                    (farm, sid),
                ).fetchone()
            if row:
                eid = _s(row["google_event_id"])
        if not eid:
            return
        try:
            access, calendar_id = self._ensure_access_token(farm)
            delete_event(
                access_token=access,
                calendar_id=calendar_id,
                event_id=eid,
            )
        except (BusinessRuleError, GoogleCalendarClientError):
            return

    def preview_import(
        self,
        farm_cd: str,
        work_dt: str,
    ) -> dict[str, Any]:
        """해당일 구글 일정 미리보기 (확인 후 저장용)."""
        self._require_configured()
        farm = self._ensure_farm(farm_cd)
        dt = _s(work_dt)[:10]
        if not _DATE_RE.match(dt):
            raise BusinessRuleError("날짜는 YYYY-MM-DD 형식이어야 합니다.")
        access, calendar_id = self._ensure_access_token(farm)
        end_plus = (date.fromisoformat(dt) + timedelta(days=1)).isoformat()
        try:
            events = list_events(
                access_token=access,
                calendar_id=calendar_id,
                time_min=f"{dt}T00:00:00+09:00",
                time_max=f"{end_plus}T00:00:00+09:00",
            )
        except GoogleCalendarClientError as exc:
            raise BusinessRuleError(exc.message, error_code=exc.code) from exc

        with get_sqlite_connection(self._db_path) as conn:
            work_cols = {
                str(r[1]) for r in conn.execute("PRAGMA table_info(t_work_detail)")
            }
            known_work: dict[str, str] = {}
            if "google_event_id" in work_cols:
                known_work = {
                    _s(r["google_event_id"]): _s(r["work_id"])
                    for r in conn.execute(
                        """
                        SELECT work_id, google_event_id FROM t_work_detail
                        WHERE farm_cd = ? AND IFNULL(google_event_id,'') != ''
                        """,
                        (farm,),
                    ).fetchall()
                }
        items: list[dict[str, Any]] = []
        for ev in events:
            event_id = _s(ev.get("id"))
            if not event_id:
                continue
            priv = ((ev.get("extendedProperties") or {}).get("private")) or {}
            marked_farm = _s(priv.get(EXT_PROP_FARM_CD))
            if marked_farm and marked_farm != farm:
                continue
            start_obj = ev.get("start") or {}
            end_obj = ev.get("end") or {}
            parsed = _parse_event_start(
                start_obj if isinstance(start_obj, dict) else {}
            )
            if not parsed:
                continue
            work_day, start_tm = parsed
            if work_day != dt:
                continue
            end_tm = _parse_event_end_tm(
                end_obj if isinstance(end_obj, dict) else {}, work_day
            )
            title = _s(ev.get("summary")) or "구글 일정"
            desc = _s(ev.get("description"))
            for prefix in (DESC_MARKER_PREFIX, DESC_MARKER_WORK_PREFIX):
                if prefix in desc:
                    desc = desc.split(prefix)[0].strip()
            linked_work = known_work.get(event_id)
            items.append(
                {
                    "google_event_id": event_id,
                    "title": title,
                    "description": desc or None,
                    "work_dt": work_day,
                    "start_tm": start_tm,
                    "end_tm": end_tm,
                    "suggested_kind": ORCHARD_KIND_WORK,
                    "linked_work_id": linked_work or None,
                    "linked_sched_id": None,
                    "already_linked": bool(linked_work),
                }
            )

        return {
            "success": True,
            "work_dt": dt,
            "message": MSG_GOOGLE_IMPORT_EMPTY if not items else "",
            "items": items,
        }

    def confirm_import(
        self,
        farm_cd: str,
        body: dict[str, Any],
        *,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """미리보기 항목을 확인·수정 후 OPS+구글 반영."""
        self._require_configured()
        farm = self._ensure_farm(farm_cd)
        uid = _s(user_id) or self._settings.default_user_id
        event_id = _s(body.get("google_event_id"))
        if not event_id:
            raise BusinessRuleError("google_event_id가 필요합니다.")
        work_dt = _s(body.get("work_dt"))[:10]
        if not _DATE_RE.match(work_dt):
            raise BusinessRuleError("날짜는 YYYY-MM-DD 형식이어야 합니다.")
        start_tm = _s(body.get("start_tm")) or None
        end_tm = _s(body.get("end_tm")) or None
        if start_tm and not _TIME_RE.match(start_tm):
            raise BusinessRuleError("시작 시각은 HH:MM 형식이어야 합니다.")
        if end_tm and not _TIME_RE.match(end_tm):
            raise BusinessRuleError("종료 시각은 HH:MM 형식이어야 합니다.")
        title = _s(body.get("title")) or "구글 일정"
        contents = _s(body.get("description")) or None
        work_mid_cd = _s(body.get("work_mid_cd")) or _DEFAULT_IMPORT_MID
        work_loc_id = _s(body.get("work_loc_id")) or None
        # 예정 테이블 폐기: 항상 실적(work)로 저장. 미래일은 준비중.
        if work_dt > today_ops().isoformat():
            status_cd = STATUS_PREPARING_CD
        else:
            status_cd = _s(body.get("status_cd")) or STATUS_PREPARING_CD

        result = self._confirm_as_work(
            farm,
            uid,
            event_id=event_id,
            work_dt=work_dt,
            start_tm=start_tm,
            end_tm=end_tm,
            title=title,
            contents=contents,
            work_mid_cd=work_mid_cd,
            work_loc_id=work_loc_id,
            status_cd=status_cd,
            existing_work_id=_s(body.get("work_id")) or None,
        )
        self.push_work(farm, result["work_id"], user_id=uid)
        return {"success": True, **result}

    def _confirm_as_work(
        self,
        farm: str,
        uid: str,
        *,
        event_id: str,
        work_dt: str,
        start_tm: str | None,
        end_tm: str | None,
        title: str,
        contents: str | None,
        work_mid_cd: str,
        work_loc_id: str | None,
        status_cd: str | None,
        existing_work_id: str | None,
    ) -> dict[str, Any]:
        rmk_parts = []
        if title:
            rmk_parts.append(title)
        if contents:
            rmk_parts.append(contents)
        rmk = "\n".join(rmk_parts) if rmk_parts else None
        with get_sqlite_write_connection(self._db_path) as conn:
            wid = existing_work_id
            if not wid:
                linked = conn.execute(
                    """
                    SELECT work_id FROM t_work_detail
                    WHERE farm_cd = ? AND google_event_id = ?
                    """,
                    (farm, event_id),
                ).fetchone()
                if linked:
                    wid = _s(linked["work_id"])
            if not wid:
                wid = self._next_work_id(conn, farm, work_dt)
                conn.execute(
                    """
                    INSERT INTO t_work_master (
                        work_dt, day_of_week, farm_cd,
                        reg_id, reg_dt, mod_id, mod_dt
                    ) SELECT ?, '', ?, ?, datetime('now','localtime'),
                             ?, datetime('now','localtime')
                    WHERE NOT EXISTS (
                        SELECT 1 FROM t_work_master
                        WHERE work_dt = ? AND farm_cd = ?
                    )
                    """,
                    (work_dt, farm, uid, uid, work_dt, farm),
                )
                conn.execute(
                    """
                    INSERT INTO t_work_detail (
                        work_id, work_dt, farm_cd, work_main_cd, work_mid_cd,
                        work_loc_id, start_tm, end_tm, status_cd, rmk,
                        google_event_id, sync_status, last_synced_at,
                        reg_id, reg_dt, mod_id, mod_dt
                    ) VALUES (
                        ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?,
                        ?, ?, datetime('now','localtime'),
                        ?, datetime('now','localtime'), ?, datetime('now','localtime')
                    )
                    """,
                    (
                        wid,
                        work_dt,
                        farm,
                        DEFAULT_WORK_MAIN_CD,
                        work_mid_cd,
                        work_loc_id,
                        start_tm,
                        end_tm,
                        status_cd,
                        rmk,
                        event_id,
                        SYNC_STATUS_PENDING,
                        uid,
                        uid,
                    ),
                )
            else:
                conn.execute(
                    """
                    UPDATE t_work_detail SET
                        work_dt = ?,
                        work_mid_cd = ?,
                        work_loc_id = ?,
                        start_tm = ?,
                        end_tm = ?,
                        status_cd = ?,
                        rmk = ?,
                        google_event_id = ?,
                        sync_status = ?,
                        mod_id = ?,
                        mod_dt = datetime('now','localtime')
                    WHERE farm_cd = ? AND work_id = ?
                    """,
                    (
                        work_dt,
                        work_mid_cd,
                        work_loc_id,
                        start_tm,
                        end_tm,
                        status_cd,
                        rmk,
                        event_id,
                        SYNC_STATUS_PENDING,
                        uid,
                        farm,
                        wid,
                    ),
                )
            conn.commit()
        return {"kind": ORCHARD_KIND_WORK, "work_id": wid, "work_dt": work_dt}

    def _confirm_as_schedule(
        self,
        farm: str,
        uid: str,
        *,
        event_id: str,
        work_dt: str,
        start_tm: str | None,
        title: str,
        contents: str | None,
        work_mid_cd: str,
        work_loc_id: str | None,
        existing_sched_id: str | None,
    ) -> dict[str, Any]:
        with get_sqlite_write_connection(self._db_path) as conn:
            sid = existing_sched_id
            if not sid:
                linked = conn.execute(
                    """
                    SELECT sched_id FROM t_work_schedule
                    WHERE farm_cd = ? AND google_event_id = ?
                    """,
                    (farm, event_id),
                ).fetchone()
                if linked:
                    sid = _s(linked["sched_id"])
            if not sid:
                sid = self._next_sched_id(conn, farm, work_dt)
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
                        NULL, ?, ?, datetime('now','localtime'),
                        datetime('now','localtime'), ?, datetime('now','localtime'), ?
                    )
                    """,
                    (
                        farm,
                        sid,
                        work_dt,
                        start_tm,
                        DEFAULT_WORK_MAIN_CD,
                        work_mid_cd,
                        work_loc_id,
                        title,
                        contents,
                        SCHED_STATUS_PENDING,
                        event_id,
                        SYNC_STATUS_PENDING,
                        uid,
                        uid,
                    ),
                )
            else:
                conn.execute(
                    """
                    UPDATE t_work_schedule SET
                        work_dt = ?,
                        work_tm = ?,
                        work_mid_cd = ?,
                        work_loc_id = ?,
                        title = ?,
                        contents = ?,
                        google_event_id = ?,
                        sync_status = ?,
                        mod_id = ?,
                        mod_dt = datetime('now','localtime')
                    WHERE farm_cd = ? AND sched_id = ?
                    """,
                    (
                        work_dt,
                        start_tm,
                        work_mid_cd,
                        work_loc_id,
                        title,
                        contents,
                        event_id,
                        SYNC_STATUS_PENDING,
                        uid,
                        farm,
                        sid,
                    ),
                )
            conn.commit()
        return {"kind": ORCHARD_KIND_SCHED, "sched_id": sid, "work_dt": work_dt}

    @staticmethod
    def _encode_state(payload: dict[str, str]) -> str:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("ascii")

    @staticmethod
    def _decode_state(state: str) -> dict[str, Any]:
        try:
            raw = base64.urlsafe_b64decode(_s(state).encode("ascii"))
            data = json.loads(raw.decode("utf-8"))
            if not isinstance(data, dict):
                raise ValueError("bad state")
            return data
        except Exception as exc:  # noqa: BLE001
            raise BusinessRuleError("잘못된 구글 인증 state 입니다.") from exc

    def _load_token_row(self, farm: str) -> dict[str, Any] | None:
        with get_sqlite_connection(self._db_path) as conn:
            row = conn.execute(
                """
                SELECT * FROM t_google_calendar_token
                WHERE farm_cd = ? AND use_yn = 'Y'
                """,
                (farm,),
            ).fetchone()
        return dict(row) if row else None

    def _ensure_access_token(self, farm: str) -> tuple[str, str]:
        row = self._load_token_row(farm)
        if not row:
            raise BusinessRuleError(
                MSG_GOOGLE_NOT_CONNECTED,
                error_code=ERR_GOOGLE_NOT_CONNECTED,
            )
        access = _s(row.get("access_token"))
        refresh = _s(row.get("refresh_token"))
        calendar_id = _s(row.get("calendar_id")) or GOOGLE_CALENDAR_ID_PRIMARY
        expiry = _s(row.get("token_expiry"))
        need_refresh = True
        if access and expiry:
            try:
                exp = datetime.fromisoformat(expiry.replace("Z", "+00:00"))
                if exp.tzinfo is None:
                    exp = exp.replace(tzinfo=timezone.utc)
                need_refresh = exp <= datetime.now(timezone.utc)
            except ValueError:
                need_refresh = True
        if need_refresh:
            if not refresh:
                raise BusinessRuleError(
                    MSG_GOOGLE_NOT_CONNECTED,
                    error_code=ERR_GOOGLE_NOT_CONNECTED,
                )
            try:
                tokens = refresh_access_token(
                    client_id=self._settings.google_oauth_client_id,
                    client_secret=self._settings.google_oauth_client_secret,
                    refresh_token=refresh,
                )
            except GoogleCalendarClientError as exc:
                raise BusinessRuleError(exc.message, error_code=exc.code) from exc
            access = _s(tokens.get("access_token"))
            expiry = expiry_iso_from_expires_in(tokens.get("expires_in"))
            with get_sqlite_write_connection(self._db_path) as conn:
                conn.execute(
                    """
                    UPDATE t_google_calendar_token SET
                        access_token = ?,
                        token_expiry = ?,
                        mod_dt = datetime('now','localtime')
                    WHERE farm_cd = ?
                    """,
                    (access, expiry, farm),
                )
                conn.commit()
        if not access:
            raise BusinessRuleError(
                MSG_GOOGLE_NOT_CONNECTED,
                error_code=ERR_GOOGLE_NOT_CONNECTED,
            )
        return access, calendar_id

    def _work_event_body(self, farm: str, row: sqlite3.Row) -> dict[str, Any]:
        work_id = _s(row["work_id"])
        work_dt = _s(row["work_dt"])[:10]
        start_tm = _s(row["start_tm"])[:5] or None
        end_tm = _s(row["end_tm"])[:5] or None
        if start_tm and not _TIME_RE.match(start_tm):
            start_tm = None
        if end_tm and not _TIME_RE.match(end_tm):
            end_tm = None
        summary = build_work_event_summary(
            loc_nm=_s(row["work_loc_nm"]) if "work_loc_nm" in row.keys() else "",
            mid_nm=_s(row["work_mid_nm"]) if "work_mid_nm" in row.keys() else "",
        )
        if summary == "영농 작업":
            summary = _s(row["work_mid_cd"]) or summary
        desc = build_work_event_description(
            status_nm=_s(row["status_nm"]) if "status_nm" in row.keys() else "",
            rmk=_s(row["rmk"]),
            work_id=work_id,
        )
        body: dict[str, Any] = {
            "summary": summary,
            "description": desc,
            "extendedProperties": {
                "private": {
                    EXT_PROP_KIND: ORCHARD_KIND_WORK,
                    EXT_PROP_WORK_ID: work_id,
                    EXT_PROP_FARM_CD: farm,
                }
            },
        }
        if start_tm:
            body["start"] = {
                "dateTime": f"{work_dt}T{start_tm}:00",
                "timeZone": GOOGLE_EVENT_TIMEZONE,
            }
            body["end"] = {
                "dateTime": _timed_end_iso(work_dt, start_tm, end_tm),
                "timeZone": GOOGLE_EVENT_TIMEZONE,
            }
        else:
            end_dt = (date.fromisoformat(work_dt) + timedelta(days=1)).isoformat()
            body["start"] = {"date": work_dt}
            body["end"] = {"date": end_dt}
        return body

    def _schedule_event_body(self, farm: str, row: sqlite3.Row) -> dict[str, Any]:
        sched_id = _s(row["sched_id"])
        work_dt = _s(row["work_dt"])
        work_tm = (
            (_s(row["work_tm"]) or None) if "work_tm" in row.keys() else None
        )
        if work_tm and not _TIME_RE.match(work_tm):
            work_tm = None
        title = (
            _s(row["title"])
            or (_s(row["work_mid_nm"]) if "work_mid_nm" in row.keys() else "")
            or _s(row["work_mid_cd"])
            or "영농 일정"
        )
        contents = _s(row["contents"])
        desc_parts = []
        if contents:
            desc_parts.append(contents)
        desc_parts.append(f"{DESC_MARKER_PREFIX}{sched_id}]")
        body: dict[str, Any] = {
            "summary": title,
            "description": "\n".join(desc_parts),
            "extendedProperties": {
                "private": {
                    EXT_PROP_KIND: ORCHARD_KIND_SCHED,
                    EXT_PROP_SCHED_ID: sched_id,
                    EXT_PROP_FARM_CD: farm,
                }
            },
        }
        if work_tm:
            body["start"] = {
                "dateTime": f"{work_dt}T{work_tm}:00",
                "timeZone": GOOGLE_EVENT_TIMEZONE,
            }
            body["end"] = {
                "dateTime": _timed_end_iso(work_dt, work_tm),
                "timeZone": GOOGLE_EVENT_TIMEZONE,
            }
        else:
            end_dt = (date.fromisoformat(work_dt) + timedelta(days=1)).isoformat()
            body["start"] = {"date": work_dt}
            body["end"] = {"date": end_dt}
        return body

    @staticmethod
    def _set_work_sync(
        conn: sqlite3.Connection,
        farm: str,
        work_id: str,
        event_id: str | None,
        sync_status: str,
        uid: str,
    ) -> None:
        cols = {str(r[1]) for r in conn.execute("PRAGMA table_info(t_work_detail)")}
        if "google_event_id" not in cols:
            return
        conn.execute(
            """
            UPDATE t_work_detail SET
                google_event_id = ?,
                sync_status = ?,
                last_synced_at = datetime('now','localtime'),
                mod_id = ?,
                mod_dt = datetime('now','localtime')
            WHERE farm_cd = ? AND work_id = ?
            """,
            (event_id, sync_status, uid, farm, work_id),
        )

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
        prefix = f"{ymd}-"
        row = conn.execute(
            """
            SELECT work_id FROM t_work_detail
            WHERE farm_cd = ? AND work_id LIKE ?
            ORDER BY work_id DESC LIMIT 1
            """,
            (farm, f"{prefix}%"),
        ).fetchone()
        seq = 1
        if row:
            last = _s(row["work_id"])
            try:
                seq = int(last.rsplit("-", 1)[-1]) + 1
            except ValueError:
                seq = 1
        return f"{prefix}{seq:02d}"
