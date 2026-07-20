# -*- coding: utf-8 -*-
"""알림 서비스 — 목록·요약·읽음 (NTF-001 Phase1)."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.exceptions import EntityNotFoundError
from app.db.sqlite import get_sqlite_connection, get_sqlite_write_connection, map_sqlite_error
from app.schemas.notification import (
    NotificationItem,
    NotificationReadAllResponse,
    NotificationReadResponse,
    NotificationSummary,
)
from app.services._core_path import ensure_repo_root_on_path

ensure_repo_root_on_path()

from core.notification_schema import (  # noqa: E402
    PRIORITY_URGENT_CD,
    ensure_notification_schema,
)

DEFAULT_USER_ID = "MOBILE_USER"


def _now_local() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _s(value: Any) -> str:
    return str(value or "").strip()


def _parse_payload(raw: Any) -> dict[str, Any] | None:
    text = _s(raw)
    if not text:
        return None
    try:
        data = json.loads(text)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _resolve_user(user_id: str | None) -> str:
    uid = _s(user_id)
    return uid or DEFAULT_USER_ID


class NotificationService:
    def __init__(self, db_path: Path | str):
        self._db_path = Path(db_path)
        ensure_notification_schema(self._db_path)

    def list_notifications(
        self,
        farm_cd: str,
        *,
        user_id: str | None = None,
        unread_only: bool = False,
        noti_type_cd: str | None = None,
        limit: int = 50,
    ) -> list[NotificationItem]:
        farm = _s(farm_cd)
        uid = _resolve_user(user_id)
        lim = max(1, min(int(limit or 50), 200))
        type_cd = _s(noti_type_cd)

        sql = """
            SELECT
                n.noti_id, n.farm_cd, n.noti_type_cd, n.priority_cd,
                n.title, n.body, n.payload_json, n.source_cd,
                n.ref_type, n.ref_id, n.event_at,
                COALESCE(r.read_yn, 'N') AS read_yn,
                r.read_dt,
                COALESCE(NULLIF(TRIM(t.code_nm), ''), n.noti_type_cd) AS noti_type_nm,
                COALESCE(NULLIF(TRIM(p.code_nm), ''), n.priority_cd) AS priority_nm
            FROM t_notification n
            LEFT JOIN t_notification_read r
              ON r.farm_cd = n.farm_cd
             AND r.noti_id = n.noti_id
             AND r.user_id = ?
             AND COALESCE(r.dismiss_yn, 'N') = 'N'
            LEFT JOIN m_common_code t
              ON t.farm_cd = n.farm_cd AND t.code_cd = n.noti_type_cd
            LEFT JOIN m_common_code p
              ON p.farm_cd = n.farm_cd AND p.code_cd = n.priority_cd
            WHERE n.farm_cd = ?
              AND COALESCE(n.use_yn, 'Y') = 'Y'
              AND COALESCE(r.dismiss_yn, 'N') = 'N'
        """
        params: list[Any] = [uid, farm]
        if unread_only:
            sql += " AND COALESCE(r.read_yn, 'N') = 'N'"
        if type_cd:
            sql += " AND n.noti_type_cd = ?"
            params.append(type_cd)
        sql += " ORDER BY n.event_at DESC, n.noti_id DESC LIMIT ?"
        params.append(lim)

        try:
            with get_sqlite_connection(self._db_path) as conn:
                rows = conn.execute(sql, params).fetchall()
        except sqlite3.Error as exc:
            raise map_sqlite_error(exc) from exc

        return [self._to_item(row) for row in rows]

    def get_summary(
        self, farm_cd: str, *, user_id: str | None = None
    ) -> NotificationSummary:
        farm = _s(farm_cd)
        uid = _resolve_user(user_id)
        sql = """
            SELECT
                SUM(CASE WHEN COALESCE(r.read_yn, 'N') = 'N' THEN 1 ELSE 0 END)
                    AS unread_count,
                SUM(
                    CASE
                        WHEN COALESCE(r.read_yn, 'N') = 'N'
                         AND n.priority_cd = ?
                        THEN 1 ELSE 0
                    END
                ) AS urgent_count
            FROM t_notification n
            LEFT JOIN t_notification_read r
              ON r.farm_cd = n.farm_cd
             AND r.noti_id = n.noti_id
             AND r.user_id = ?
             AND COALESCE(r.dismiss_yn, 'N') = 'N'
            WHERE n.farm_cd = ?
              AND COALESCE(n.use_yn, 'Y') = 'Y'
              AND COALESCE(r.dismiss_yn, 'N') = 'N'
        """
        try:
            with get_sqlite_connection(self._db_path) as conn:
                row = conn.execute(
                    sql, (PRIORITY_URGENT_CD, uid, farm)
                ).fetchone()
        except sqlite3.Error as exc:
            raise map_sqlite_error(exc) from exc
        if not row:
            return NotificationSummary()
        return NotificationSummary(
            unread_count=int(row["unread_count"] or 0),
            urgent_count=int(row["urgent_count"] or 0),
        )

    def mark_read(
        self,
        farm_cd: str,
        noti_id: str,
        *,
        user_id: str | None = None,
    ) -> NotificationReadResponse:
        farm = _s(farm_cd)
        nid = _s(noti_id)
        uid = _resolve_user(user_id)
        now = _now_local()
        try:
            with get_sqlite_write_connection(self._db_path) as conn:
                exists = conn.execute(
                    """
                    SELECT 1 FROM t_notification
                    WHERE farm_cd = ? AND noti_id = ? AND COALESCE(use_yn, 'Y') = 'Y'
                    """,
                    (farm, nid),
                ).fetchone()
                if not exists:
                    raise EntityNotFoundError("알림을 찾을 수 없습니다.")
                conn.execute(
                    """
                    INSERT INTO t_notification_read (
                        farm_cd, noti_id, user_id, read_yn, read_dt,
                        dismiss_yn, reg_dt, mod_dt
                    ) VALUES (?, ?, ?, 'Y', ?, 'N', ?, ?)
                    ON CONFLICT(farm_cd, noti_id, user_id) DO UPDATE SET
                        read_yn = 'Y',
                        read_dt = excluded.read_dt,
                        mod_dt = excluded.mod_dt
                    """,
                    (farm, nid, uid, now, now, now),
                )
        except EntityNotFoundError:
            raise
        except sqlite3.Error as exc:
            raise map_sqlite_error(exc) from exc
        return NotificationReadResponse(noti_id=nid, read_yn="Y", read_dt=now)

    def mark_read_all(
        self, farm_cd: str, *, user_id: str | None = None
    ) -> NotificationReadAllResponse:
        farm = _s(farm_cd)
        uid = _resolve_user(user_id)
        now = _now_local()
        try:
            with get_sqlite_write_connection(self._db_path) as conn:
                unread = conn.execute(
                    """
                    SELECT n.noti_id
                    FROM t_notification n
                    LEFT JOIN t_notification_read r
                      ON r.farm_cd = n.farm_cd
                     AND r.noti_id = n.noti_id
                     AND r.user_id = ?
                    WHERE n.farm_cd = ?
                      AND COALESCE(n.use_yn, 'Y') = 'Y'
                      AND COALESCE(r.dismiss_yn, 'N') = 'N'
                      AND COALESCE(r.read_yn, 'N') = 'N'
                    """,
                    (uid, farm),
                ).fetchall()
                count = 0
                for row in unread:
                    nid = _s(row["noti_id"])
                    conn.execute(
                        """
                        INSERT INTO t_notification_read (
                            farm_cd, noti_id, user_id, read_yn, read_dt,
                            dismiss_yn, reg_dt, mod_dt
                        ) VALUES (?, ?, ?, 'Y', ?, 'N', ?, ?)
                        ON CONFLICT(farm_cd, noti_id, user_id) DO UPDATE SET
                            read_yn = 'Y',
                            read_dt = excluded.read_dt,
                            mod_dt = excluded.mod_dt
                        """,
                        (farm, nid, uid, now, now, now),
                    )
                    count += 1
        except sqlite3.Error as exc:
            raise map_sqlite_error(exc) from exc
        return NotificationReadAllResponse(updated_count=count)

    def _to_item(self, row: sqlite3.Row) -> NotificationItem:
        return NotificationItem(
            noti_id=_s(row["noti_id"]),
            farm_cd=_s(row["farm_cd"]),
            noti_type_cd=_s(row["noti_type_cd"]),
            noti_type_nm=_s(row["noti_type_nm"]),
            priority_cd=_s(row["priority_cd"]),
            priority_nm=_s(row["priority_nm"]),
            title=_s(row["title"]),
            body=_s(row["body"]) or None,
            payload=_parse_payload(row["payload_json"]),
            source_cd=_s(row["source_cd"]),
            ref_type=_s(row["ref_type"]) or None,
            ref_id=_s(row["ref_id"]) or None,
            event_at=_s(row["event_at"]),
            read_yn=_s(row["read_yn"]) or "N",
            read_dt=_s(row["read_dt"]) or None,
        )
