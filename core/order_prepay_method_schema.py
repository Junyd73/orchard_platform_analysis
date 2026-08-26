# -*- coding: utf-8 -*-
"""t_order_master.pre_pay_method_cd 멱등 적용 (DEC-028).

운영 자동 배포/ALTER는 대표 승인 후. 로컬·테스트에서만 호출.
production 직접 실행 금지. backfill 없음.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

ORDER_PREPAY_METHOD_COLUMN = ("pre_pay_method_cd", "TEXT")


def ensure_order_prepay_method_schema(db_path: Path | str | Any) -> dict:
    """pre_pay_method_cd TEXT NULL 멱등 추가. 기존 row는 NULL."""
    stats: dict[str, Any] = {"ok": True, "columns": [], "reason": ""}
    conn, owns = _open_conn(db_path)
    if conn is None:
        stats["ok"] = False
        stats["reason"] = "db_unavailable"
        return stats
    try:
        _ensure_column(conn, stats)
        conn.commit()
    except Exception as exc:  # noqa: BLE001
        try:
            conn.rollback()
        except sqlite3.Error:
            pass
        stats["ok"] = False
        stats["reason"] = str(exc)
        logger.exception("ensure_order_prepay_method_schema failed")
    finally:
        if owns:
            conn.close()
    return stats


def _ensure_column(conn: sqlite3.Connection, stats: dict[str, Any]) -> None:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='t_order_master'"
    ).fetchone()
    if not row:
        return
    cols = {
        str(r[1]).strip().lower()
        for r in conn.execute("PRAGMA table_info(t_order_master)")
    }
    name, col_def = ORDER_PREPAY_METHOD_COLUMN
    if name.lower() in cols:
        return
    conn.execute(f"ALTER TABLE t_order_master ADD COLUMN {name} {col_def}")
    stats["columns"].append(f"t_order_master.{name}")


def _open_conn(db_path: Path | str | Any) -> tuple[sqlite3.Connection | None, bool]:
    if hasattr(db_path, "conn") and getattr(db_path, "conn", None) is not None:
        return db_path.conn, False
    if isinstance(db_path, sqlite3.Connection):
        return db_path, False
    path = Path(str(db_path)).expanduser().resolve()
    if not path.is_file():
        return None, False
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn, True
