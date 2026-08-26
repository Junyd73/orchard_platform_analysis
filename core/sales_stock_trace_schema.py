# -*- coding: utf-8 -*-
"""Stage 5C 판매↔재고 추적 컬럼 멱등 ALTER (DEC-027).

운영 자동 실행 금지. 로컬·테스트에서만 호출.
ensure_order_alloc_schema 와 분리. HOLD/reserved 정리 없음.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

REF_TYPE_SALE = "SALE"

SALES_DETAIL_COLUMNS = (("stock_seq", "INTEGER"),)
STOCK_LOG_COLUMNS = (
    ("stock_seq", "INTEGER"),
    ("ref_type", "TEXT"),
    ("ref_id", "TEXT"),
)


def ensure_sales_stock_trace_schema(db: Path | str | sqlite3.Connection | Any) -> dict[str, Any]:
    """t_sales_detail.stock_seq · t_stock_log stock_seq/ref_type/ref_id 멱등 추가.

    물리 FK·NOT NULL 없음. 기존 행은 NULL 유지.
    """
    stats: dict[str, Any] = {"ok": True, "columns": [], "reason": ""}
    conn, owns = _open_conn(db)
    if conn is None:
        stats["ok"] = False
        stats["reason"] = "db_unavailable"
        return stats
    try:
        _ensure_table_columns(conn, "t_sales_detail", SALES_DETAIL_COLUMNS, stats)
        _ensure_table_columns(conn, "t_stock_log", STOCK_LOG_COLUMNS, stats)
        conn.commit()
    except Exception as exc:  # noqa: BLE001
        try:
            conn.rollback()
        except sqlite3.Error:
            pass
        stats["ok"] = False
        stats["reason"] = str(exc)
        logger.exception("ensure_sales_stock_trace_schema failed")
    finally:
        if owns:
            conn.close()
    return stats


def _ensure_table_columns(
    conn: sqlite3.Connection,
    table: str,
    columns: tuple[tuple[str, str], ...],
    stats: dict[str, Any],
) -> None:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (table,),
    ).fetchone()
    if not row:
        return
    cols = {str(r[1]).strip().lower() for r in conn.execute(f"PRAGMA table_info({table})")}
    for name, col_def in columns:
        if name.lower() in cols:
            continue
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {col_def}")
        stats["columns"].append(f"{table}.{name}")
        cols.add(name.lower())


def _open_conn(db: Path | str | sqlite3.Connection | Any) -> tuple[sqlite3.Connection | None, bool]:
    if isinstance(db, sqlite3.Connection):
        return db, False
    if hasattr(db, "conn") and getattr(db, "conn", None) is not None:
        return db.conn, False
    path = Path(str(db)).expanduser().resolve()
    if not path.is_file():
        return None, False
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn, True
