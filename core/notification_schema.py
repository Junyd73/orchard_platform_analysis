# -*- coding: utf-8 -*-
"""알림 스키마 멱등 적용 — NTF-001 Phase1 (t_notification / t_notification_read)."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

NOTI_TYPE_PARENT_CD = "NT01"
PRIORITY_PARENT_CD = "NP01"

PRIORITY_URGENT_CD = "NP010100"
PRIORITY_NORMAL_CD = "NP010200"
PRIORITY_LOW_CD = "NP010300"

SOURCE_INTERNAL = "INTERNAL"

_NOTI_TYPE_PARENT = (NOTI_TYPE_PARENT_CD, "알림유형")
_PRIORITY_PARENT = (PRIORITY_PARENT_CD, "알림우선순위")

_NOTI_TYPE_CHILDREN: tuple[tuple[str, str, str], ...] = (
    (NOTI_TYPE_PARENT_CD, "NT010100", "작업 알림"),
    (NOTI_TYPE_PARENT_CD, "NT010200", "관찰 위험·주의"),
    (NOTI_TYPE_PARENT_CD, "NT010300", "관찰 AI 미확정"),
    (NOTI_TYPE_PARENT_CD, "NT010400", "재관찰 예정"),
    (NOTI_TYPE_PARENT_CD, "NT010500", "기상"),
    (NOTI_TYPE_PARENT_CD, "NT010600", "농촌진흥청"),
    (NOTI_TYPE_PARENT_CD, "NT010700", "기술센터"),
    (NOTI_TYPE_PARENT_CD, "NT010800", "농업 뉴스"),
    (NOTI_TYPE_PARENT_CD, "NT010900", "시스템"),
)

_PRIORITY_CHILDREN: tuple[tuple[str, str, str], ...] = (
    (PRIORITY_PARENT_CD, PRIORITY_URGENT_CD, "긴급"),
    (PRIORITY_PARENT_CD, PRIORITY_NORMAL_CD, "보통"),
    (PRIORITY_PARENT_CD, PRIORITY_LOW_CD, "낮음"),
)


def ensure_notification_schema(db_path: Path | str | Any) -> dict:
    """
    t_notification / t_notification_read / NT01·NP01 공통코드 멱등 생성.

    db_path: SQLite 파일 경로 또는 DBManager(conn 속성 보유).
    """
    stats: dict[str, Any] = {
        "ok": True,
        "tables": [],
        "codes_seeded": False,
        "reason": "",
    }

    conn, owns = _open_conn(db_path)
    if conn is None:
        stats["ok"] = False
        stats["reason"] = "db_unavailable"
        return stats

    try:
        _create_tables(conn, stats)
        _seed_common_codes(conn, stats)
        conn.commit()
    except Exception as exc:
        try:
            conn.rollback()
        except sqlite3.Error:
            pass
        stats["ok"] = False
        stats["reason"] = str(exc)
        logger.exception("ensure_notification_schema failed")
    finally:
        if owns:
            conn.close()
    return stats


def _open_conn(db_path: Path | str | Any) -> tuple[sqlite3.Connection | None, bool]:
    if hasattr(db_path, "conn") and getattr(db_path, "conn", None) is not None:
        return db_path.conn, False
    path = Path(str(db_path)).expanduser().resolve()
    if not path.is_file():
        return None, False
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn, True


def _create_tables(conn: sqlite3.Connection, stats: dict[str, Any]) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS t_notification (
            noti_id       TEXT NOT NULL,
            farm_cd       TEXT NOT NULL,
            noti_type_cd  TEXT NOT NULL,
            priority_cd   TEXT NOT NULL DEFAULT 'NP010200',
            title         TEXT NOT NULL,
            body          TEXT,
            payload_json  TEXT,
            source_cd     TEXT NOT NULL,
            ref_type      TEXT,
            ref_id        TEXT,
            event_at      TEXT NOT NULL,
            expires_at    TEXT,
            dedupe_key    TEXT NOT NULL,
            use_yn        TEXT NOT NULL DEFAULT 'Y',
            reg_id        TEXT NOT NULL DEFAULT 'SYSTEM',
            reg_dt        TEXT NOT NULL,
            mod_id        TEXT,
            mod_dt        TEXT,
            PRIMARY KEY (farm_cd, noti_id)
        )
        """
    )
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ux_noti_dedupe
            ON t_notification (farm_cd, dedupe_key) WHERE use_yn = 'Y'
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_noti_farm_event
            ON t_notification (farm_cd, event_at DESC)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_noti_farm_type
            ON t_notification (farm_cd, noti_type_cd, event_at DESC)
        """
    )
    stats["tables"].append("t_notification")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS t_notification_read (
            farm_cd    TEXT NOT NULL,
            noti_id    TEXT NOT NULL,
            user_id    TEXT NOT NULL,
            read_yn    TEXT NOT NULL DEFAULT 'N',
            read_dt    TEXT,
            dismiss_yn TEXT NOT NULL DEFAULT 'N',
            dismiss_dt TEXT,
            reg_dt     TEXT NOT NULL,
            mod_dt     TEXT,
            PRIMARY KEY (farm_cd, noti_id, user_id)
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_noti_read_user
            ON t_notification_read (user_id, read_yn, farm_cd)
        """
    )
    stats["tables"].append("t_notification_read")


def _seed_common_codes(conn: sqlite3.Connection, stats: dict[str, Any]) -> None:
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='m_common_code'"
    )
    if not cur.fetchone():
        return

    farms = conn.execute("SELECT farm_cd FROM m_farm_info").fetchall()
    farm_cds = [str(r[0]).strip() for r in farms if r and r[0]]
    if not farm_cds:
        farm_cds = ["OR001"]

    now_sql = "datetime('now','localtime')"
    parents = (_NOTI_TYPE_PARENT, _PRIORITY_PARENT)
    children = _NOTI_TYPE_CHILDREN + _PRIORITY_CHILDREN

    for farm_cd in farm_cds:
        for code_cd, code_nm in parents:
            conn.execute(
                f"""
                INSERT INTO m_common_code (
                    farm_cd, code_cd, code_nm, parent_cd, use_yn,
                    reg_id, reg_dt, mod_id, mod_dt
                )
                SELECT ?, ?, ?, NULL, 'Y', 'SYSTEM', {now_sql}, 'SYSTEM', {now_sql}
                WHERE NOT EXISTS (
                    SELECT 1 FROM m_common_code
                    WHERE farm_cd = ? AND code_cd = ?
                )
                """,
                (farm_cd, code_cd, code_nm, farm_cd, code_cd),
            )
        for parent_cd, code_cd, code_nm in children:
            conn.execute(
                f"""
                INSERT INTO m_common_code (
                    farm_cd, code_cd, code_nm, parent_cd, use_yn,
                    reg_id, reg_dt, mod_id, mod_dt
                )
                SELECT ?, ?, ?, ?, 'Y', 'SYSTEM', {now_sql}, 'SYSTEM', {now_sql}
                WHERE NOT EXISTS (
                    SELECT 1 FROM m_common_code
                    WHERE farm_cd = ? AND code_cd = ?
                )
                """,
                (farm_cd, code_cd, code_nm, parent_cd, farm_cd, code_cd),
            )
    stats["codes_seeded"] = True
