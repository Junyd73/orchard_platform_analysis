# -*- coding: utf-8 -*-
"""Stage 3A allocation DDL — 멱등. 운영 자동 실행 금지.

DEC-015: active reserved_qty>0 이면 ALTER/CREATE를 중단한다.
historical HOLD/CANCEL_HOLD 로그 존재만으로는 차단하지 않는다.
백필은 이 모듈에서 수행하지 않는다.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from core.order_alloc_constants import (
    COL_ALLOCATED_QTY,
    IO_TYPE_HOLD,
    MSG_ALLOC_MIGRATE_BLOCKED,
    TABLE_ORDER_ALLOC,
)

CREATE_ORDER_ALLOC_SQL = f"""
CREATE TABLE IF NOT EXISTS {TABLE_ORDER_ALLOC} (
    alloc_id TEXT PRIMARY KEY,
    farm_cd TEXT NOT NULL,
    order_no TEXT NOT NULL,
    order_detail_id TEXT NOT NULL,
    wh_cd TEXT NOT NULL,
    item_cd TEXT NOT NULL,
    variety_cd TEXT NOT NULL,
    grade_cd TEXT NOT NULL,
    size_cd TEXT NOT NULL,
    weight REAL NOT NULL,
    harvest_year INTEGER NOT NULL,
    storage_dt TEXT NOT NULL,
    allocated_qty REAL NOT NULL DEFAULT 0,
    shipped_qty REAL NOT NULL DEFAULT 0,
    reg_id TEXT,
    reg_dt TEXT,
    mod_id TEXT,
    mod_dt TEXT,
    UNIQUE (
        farm_cd, order_detail_id, wh_cd, item_cd, variety_cd,
        grade_cd, size_cd, weight, harvest_year, storage_dt
    )
)
"""


class OrderAllocMigrateBlocked(RuntimeError):
    def __init__(self, message: str = MSG_ALLOC_MIGRATE_BLOCKED):
        super().__init__(message)
        self.message = message


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {str(r[1]) for r in rows}


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (table,),
    ).fetchone()
    return row is not None


def inspect_hold_state(conn: sqlite3.Connection) -> dict[str, Any]:
    """현재 active reserved가 있으면 차단. HOLD 로그 건수는 보고만 한다."""
    reserved_rows = 0
    reserved_sum = 0.0
    hold_logs = 0
    order_count = 0
    if _table_exists(conn, "t_stock_master") and "reserved_qty" in _table_columns(
        conn, "t_stock_master"
    ):
        row = conn.execute(
            """
            SELECT COUNT(*), COALESCE(SUM(reserved_qty), 0)
            FROM t_stock_master
            WHERE COALESCE(reserved_qty, 0) > 0
            """
        ).fetchone()
        reserved_rows = int(row[0] or 0)
        reserved_sum = float(row[1] or 0)
    if _table_exists(conn, "t_stock_log"):
        hold_logs = int(
            conn.execute(
                "SELECT COUNT(*) FROM t_stock_log WHERE io_type = ?",
                (IO_TYPE_HOLD,),
            ).fetchone()[0]
            or 0
        )
    if _table_exists(conn, "t_order_master"):
        order_count = int(
            conn.execute("SELECT COUNT(*) FROM t_order_master").fetchone()[0] or 0
        )
    blocked = reserved_rows > 0
    return {
        "reserved_rows": reserved_rows,
        "reserved_sum": reserved_sum,
        "hold_logs": hold_logs,
        "order_count": order_count,
        "blocked": blocked,
    }


def ensure_order_alloc_schema(
    db: Path | str | sqlite3.Connection,
    *,
    skip_preflight: bool = False,
) -> dict[str, Any]:
    """allocated_qty 컬럼 + t_order_alloc 테이블을 멱등 생성.

    skip_preflight=True 는 테스트 전용. 운영/로컬 적용은 기본 점검 후 중단.
    """
    owns = False
    if isinstance(db, sqlite3.Connection):
        conn = db
    else:
        path = Path(db).expanduser().resolve()
        if not path.is_file():
            return {"ok": False, "reason": "db_missing"}
        conn = sqlite3.connect(str(path))
        owns = True
    stats: dict[str, Any] = {
        "ok": True,
        "allocated_qty_added": False,
        "alloc_table_created": False,
        "preflight": {},
    }
    try:
        pre = inspect_hold_state(conn)
        stats["preflight"] = pre
        if pre["blocked"] and not skip_preflight:
            raise OrderAllocMigrateBlocked()
        detail_cols = _table_columns(conn, "t_order_detail")
        if not detail_cols:
            stats["ok"] = False
            stats["reason"] = "t_order_detail_missing"
            return stats
        if COL_ALLOCATED_QTY not in detail_cols:
            conn.execute(
                "ALTER TABLE t_order_detail "
                f"ADD COLUMN {COL_ALLOCATED_QTY} REAL NOT NULL DEFAULT 0"
            )
            stats["allocated_qty_added"] = True
        existed = _table_exists(conn, TABLE_ORDER_ALLOC)
        conn.execute(CREATE_ORDER_ALLOC_SQL)
        stats["alloc_table_created"] = not existed
        if owns:
            conn.commit()
        return stats
    except Exception:
        if owns:
            conn.rollback()
        raise
    finally:
        if owns:
            conn.close()
