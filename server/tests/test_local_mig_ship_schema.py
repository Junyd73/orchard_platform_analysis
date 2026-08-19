# -*- coding: utf-8 -*-
"""T-LOCAL-MIG-01~04: trace 멱등 + DIRECT는 alloc 스키마 불필요."""

from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve()
_SERVER = _HERE.parents[1]
_ROOT = _HERE.parents[2]
for p in (_SERVER, _ROOT):
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)

from core.order_ship_constants import SHIP_MODE_DIRECT, SHIP_MODE_STOCK  # noqa: E402
from core.order_ship_service import (  # noqa: E402
    OrderShipService,
    ShipConfirmIn,
    ShipError,
    ShipLineIn,
)
from core.sales_stock_trace_schema import ensure_sales_stock_trace_schema  # noqa: E402

FARM = "OR001"
ITEM = "FR010100"
VARIETY = "FR010101"
GRADE = "GR010100"
SIZE = "FR020102"
WEIGHT = 15.0
YEAR = 2026
WH = "WH01"


def _cols(conn: sqlite3.Connection, table: str) -> set[str]:
    return {str(r[1]) for r in conn.execute(f"PRAGMA table_info({table})")}


def _open() -> tuple[Path, sqlite3.Connection]:
    fd, name = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    path = Path(name)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return path, conn


DIRECT_ONLY_SQL = f"""
CREATE TABLE t_sales_master (
    sales_no TEXT, farm_cd TEXT, sales_dt TEXT, sales_tp TEXT, custm_id TEXT,
    tot_sales_amt REAL, tot_ship_fee REAL, tot_item_amt REAL,
    tot_paid_amt REAL, tot_unpaid_amt REAL, status_cd TEXT, rmk TEXT,
    reg_id TEXT, reg_dt TEXT, order_no TEXT,
    sales_status TEXT, sales_source TEXT,
    PRIMARY KEY (sales_no, farm_cd)
);
CREATE TABLE t_sales_detail (
    sale_detail_no TEXT, sales_no TEXT, farm_cd TEXT,
    item_cd TEXT, variety_cd TEXT, grade_cd TEXT, size_cd TEXT,
    qty REAL, unit_price REAL, tot_item_amt REAL, tot_sale_amt REAL,
    order_detail_id TEXT, wh_cd TEXT,
    reg_id TEXT, reg_dt TEXT,
    PRIMARY KEY (sale_detail_no, farm_cd)
);
CREATE TABLE t_stock_master (
    stock_seq INTEGER PRIMARY KEY AUTOINCREMENT,
    farm_cd TEXT NOT NULL, wh_cd TEXT NOT NULL, item_cd TEXT NOT NULL,
    variety_cd TEXT NOT NULL, grade_cd TEXT, size_cd TEXT,
    weight REAL, harvest_year INTEGER, storage_dt TEXT,
    in_qty REAL DEFAULT 0, out_qty REAL DEFAULT 0, reserved_qty REAL DEFAULT 0,
    reg_id TEXT, mod_id TEXT, mod_dt TEXT
);
CREATE UNIQUE INDEX idx_stock_nk ON t_stock_master(
    farm_cd, wh_cd, item_cd, variety_cd, grade_cd,
    size_cd, weight, harvest_year, storage_dt
);
CREATE TABLE t_stock_log (
    log_seq INTEGER PRIMARY KEY AUTOINCREMENT,
    farm_cd TEXT, item_cd TEXT, variety_cd TEXT, harvest_year INTEGER,
    grade_cd TEXT, size_cd TEXT, weight REAL, io_type TEXT, qty REAL,
    remark TEXT, reg_id TEXT, reg_dt TEXT
);
CREATE TABLE t_order_detail (
    order_detail_id TEXT PRIMARY KEY, order_no TEXT, farm_cd TEXT, qty REAL
);
"""


class LocalMigShipSchemaTest(unittest.TestCase):
    def tearDown(self) -> None:
        conn = getattr(self, "conn", None)
        path = getattr(self, "path", None)
        if conn is not None:
            conn.close()
        if path is not None and path.is_file():
            path.unlink(missing_ok=True)

    def test_t_local_mig_01_trace_preserves_rows(self) -> None:
        self.path, self.conn = _open()
        self.conn.executescript(
            """
            CREATE TABLE t_sales_detail (
                sale_detail_no TEXT PRIMARY KEY, sales_no TEXT, farm_cd TEXT, qty REAL
            );
            CREATE TABLE t_stock_log (
                log_seq INTEGER PRIMARY KEY AUTOINCREMENT,
                farm_cd TEXT, io_type TEXT, qty REAL, remark TEXT
            );
            INSERT INTO t_sales_detail VALUES ('S1', '20260101-01', 'OR001', 3);
            INSERT INTO t_stock_log (farm_cd, io_type, qty, remark)
            VALUES ('OR001', 'IN', 3, 'keep-me');
            """
        )
        self.conn.commit()
        before_d = [
            tuple(r) for r in self.conn.execute("SELECT * FROM t_sales_detail").fetchall()
        ]
        before_l = [
            tuple(r) for r in self.conn.execute(
                "SELECT farm_cd, io_type, qty, remark FROM t_stock_log"
            ).fetchall()
        ]
        stats = ensure_sales_stock_trace_schema(self.conn)
        self.assertTrue(stats["ok"])
        after_d = [
            tuple(r)[:4] for r in self.conn.execute("SELECT * FROM t_sales_detail").fetchall()
        ]
        after_l = [
            tuple(r) for r in self.conn.execute(
                "SELECT farm_cd, io_type, qty, remark FROM t_stock_log"
            ).fetchall()
        ]
        self.assertEqual(before_d, after_d)
        self.assertEqual(before_l, after_l)
        null_seq = self.conn.execute(
            "SELECT stock_seq FROM t_sales_detail WHERE sale_detail_no='S1'"
        ).fetchone()[0]
        self.assertIsNone(null_seq)

    def test_t_local_mig_02_trace_idempotent(self) -> None:
        self.path, self.conn = _open()
        self.conn.executescript(
            """
            CREATE TABLE t_sales_detail (sale_detail_no TEXT PRIMARY KEY);
            CREATE TABLE t_stock_log (log_seq INTEGER PRIMARY KEY);
            """
        )
        first = ensure_sales_stock_trace_schema(self.conn)
        second = ensure_sales_stock_trace_schema(self.conn)
        self.assertTrue(first["ok"] and second["ok"])
        self.assertEqual(second["columns"], [])

    def test_t_local_mig_03_direct_without_alloc_schema(self) -> None:
        self.path, self.conn = _open()
        self.conn.executescript(DIRECT_ONLY_SQL)
        self.conn.execute(
            """
            INSERT INTO t_stock_master (
                farm_cd, wh_cd, item_cd, variety_cd, grade_cd, size_cd,
                weight, harvest_year, storage_dt, in_qty
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, '2026-08-01', 10)
            """,
            (FARM, WH, ITEM, VARIETY, GRADE, SIZE, WEIGHT, YEAR),
        )
        self.conn.commit()
        self.assertFalse(
            self.conn.execute(
                "SELECT 1 FROM sqlite_master WHERE name='t_order_alloc'"
            ).fetchone()
        )
        self.assertNotIn("allocated_qty", _cols(self.conn, "t_order_detail"))
        ensure_sales_stock_trace_schema(self.conn)
        out = OrderShipService(self.conn).confirm(
            ShipConfirmIn(
                farm_cd=FARM,
                ship_mode=SHIP_MODE_DIRECT,
                order_no=None,
                sales_dt="2026-08-19",
                user_id="T",
                lines=[
                    ShipLineIn(
                        qty=2,
                        item_cd=ITEM,
                        variety_cd=VARIETY,
                        grade_cd=GRADE,
                        size_cd=SIZE,
                        weight=WEIGHT,
                        harvest_year=YEAR,
                        wh_cd=WH,
                        unit_price=1000,
                    )
                ],
            )
        )
        self.assertTrue(out["ok"])
        self.assertEqual(out["ship_mode"], SHIP_MODE_DIRECT)

    def test_t_local_mig_04_stock_needs_alloc_schema(self) -> None:
        self.path, self.conn = _open()
        self.conn.executescript(DIRECT_ONLY_SQL)
        ensure_sales_stock_trace_schema(self.conn)
        with self.assertRaises(ShipError) as ctx:
            OrderShipService(self.conn).confirm(
                ShipConfirmIn(
                    farm_cd=FARM,
                    ship_mode=SHIP_MODE_STOCK,
                    order_no="ORD1",
                    sales_dt="2026-08-19",
                    user_id="T",
                    lines=[ShipLineIn(qty=1, order_detail_id="ORD1-01")],
                )
            )
        self.assertEqual(ctx.exception.code, "SCHEMA_PRECONDITION")


if __name__ == "__main__":
    unittest.main()
