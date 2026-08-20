# -*- coding: utf-8 -*-
"""t_sales_delivery 다배송지 컬럼 멱등 ALTER (Stage 6 보완 2C).

운영 자동 실행 금지. 로컬·테스트에서만 호출.
물리 FK·NOT NULL 없음. 기존 행은 NULL 유지.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SALES_DELIVERY_COLUMNS = (
    ("dlvry_group_no", "TEXT"),
    ("ship_fee", "REAL"),
)


def ensure_sales_delivery_schema(db: Path | str | sqlite3.Connection | Any) -> dict[str, Any]:
    """t_sales_delivery.dlvry_group_no · ship_fee 멱등 추가."""
    stats: dict[str, Any] = {"ok": True, "columns": [], "reason": ""}
    conn, owns = _open_conn(db)
    if conn is None:
        stats["ok"] = False
        stats["reason"] = "db_unavailable"
        return stats
    try:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
            ("t_sales_delivery",),
        ).fetchone()
        if not row:
            stats["ok"] = False
            stats["reason"] = "table_missing"
            return stats
        cols = {
            str(r[1]).strip().lower()
            for r in conn.execute("PRAGMA table_info(t_sales_delivery)")
        }
        for name, col_def in SALES_DELIVERY_COLUMNS:
            if name.lower() in cols:
                continue
            conn.execute(f"ALTER TABLE t_sales_delivery ADD COLUMN {name} {col_def}")
            stats["columns"].append(f"t_sales_delivery.{name}")
            cols.add(name.lower())
        conn.commit()
    except Exception as exc:  # noqa: BLE001
        try:
            conn.rollback()
        except sqlite3.Error:
            pass
        stats["ok"] = False
        stats["reason"] = str(exc)
        logger.exception("ensure_sales_delivery_schema failed")
    finally:
        if owns:
            conn.close()
    return stats


def _open_conn(db: Path | str | sqlite3.Connection | Any) -> tuple[sqlite3.Connection | None, bool]:
    if isinstance(db, sqlite3.Connection):
        return db, False
    if hasattr(db, "conn") and getattr(db, "conn", None) is not None:
        return db.conn, False  # type: ignore[return-value]
    path = Path(str(db))
    if not path.is_file():
        return None, False
    return sqlite3.connect(str(path)), True
