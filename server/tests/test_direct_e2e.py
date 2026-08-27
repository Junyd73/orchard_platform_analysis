# -*- coding: utf-8 -*-
"""T-DIRECT-E2E-01~04: file-backed SQLite, alloc 스키마 없이 DIRECT 정합."""

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

from core.order_constants import ORDER_STATUS_PREP_CD  # noqa: E402
from core.order_ship_constants import (  # noqa: E402
    SALES_STATUS_CONFIRMED,
    SHIP_MODE_DIRECT,
)
from core.order_ship_service import (  # noqa: E402
    OrderShipService,
    ShipConfirmIn,
    ShipConflictError,
    ShipLineIn,
)
from core.sales_class_constants import (  # noqa: E402
    DEFAULT_DIRECT_SALES_CATEGORY_CD,
    DEFAULT_DIRECT_SALES_TYPE_CD,
)
from core.sales_stock_trace_schema import REF_TYPE_SALE  # noqa: E402
from core.sales_class_schema import ensure_sales_class_schema  # noqa: E402
from core.sales_stock_trace_schema import ensure_sales_stock_trace_schema  # noqa: E402
from test_local_mig_ship_schema import DIRECT_ONLY_SQL, FARM, GRADE, ITEM, SIZE, VARIETY, WEIGHT, WH, YEAR  # noqa: E402

ORDER_NO = "ORD20260819-E2E"
DET_ID = "ORD20260819-E2E-01"


def _ship(conn: sqlite3.Connection, *, qty: float, order_no: str | None = None, det: str | None = None):
    kwargs: dict = {
        "farm_cd": FARM,
        "ship_mode": SHIP_MODE_DIRECT,
        "order_no": order_no,
        "sales_dt": "2026-08-19",
        "user_id": "T",
        "lines": [
            ShipLineIn(
                qty=qty,
                order_detail_id=det,
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
    }
    if not order_no:
        kwargs["sales_type_cd"] = DEFAULT_DIRECT_SALES_TYPE_CD
        kwargs["sales_category_cd"] = DEFAULT_DIRECT_SALES_CATEGORY_CD
    return OrderShipService(conn).confirm(ShipConfirmIn(**kwargs))


class DirectE2EFileDbTest(unittest.TestCase):
    def tearDown(self) -> None:
        conn = getattr(self, "conn", None)
        path = getattr(self, "path", None)
        if conn is not None:
            conn.close()
        if path is not None and Path(path).is_file():
            Path(path).unlink(missing_ok=True)

    def _open_file_db(self) -> None:
        fd, name = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.path = name
        self.conn = sqlite3.connect(name)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(DIRECT_ONLY_SQL)
        self.conn.execute("DROP TABLE t_order_detail")
        self.conn.executescript(
            """
            CREATE TABLE t_order_detail (
                order_detail_id TEXT PRIMARY KEY, order_no TEXT, farm_cd TEXT,
                item_cd TEXT, variety_cd TEXT, grade_cd TEXT, size_cd TEXT,
                weight REAL, harvest_year INTEGER, wh_cd TEXT,
                qty REAL, out_qty REAL DEFAULT 0
            );
            CREATE TABLE t_order_master (
                order_no TEXT PRIMARY KEY, farm_cd TEXT, custm_id TEXT,
                status_cd TEXT, stock_status TEXT, sales_no TEXT,
                pre_pay_amt REAL DEFAULT 0,
                sales_type_cd TEXT, season_type_cd TEXT,
                mod_id TEXT, mod_dt TEXT
            );
            """
        )
        ensure_sales_stock_trace_schema(self.conn)
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS m_common_code (
                farm_cd TEXT, code_cd TEXT, code_nm TEXT, parent_cd TEXT,
                use_yn TEXT DEFAULT 'Y',
                reg_id TEXT, reg_dt TEXT, mod_id TEXT, mod_dt TEXT
            )
            """
        )
        for col in ("reg_id", "reg_dt", "mod_id", "mod_dt"):
            try:
                self.conn.execute(f"ALTER TABLE m_common_code ADD COLUMN {col} TEXT")
            except sqlite3.OperationalError:
                pass
        stats = ensure_sales_class_schema(self.conn)
        if not stats.get("ok"):
            raise RuntimeError(f"ensure_sales_class_schema failed: {stats.get('reason')}")
        self.conn.commit()

    def _insert_stock(self, *, in_qty: float, reserved: float = 0, storage_dt: str = "2026-08-01") -> int:
        cur = self.conn.execute(
            """
            INSERT INTO t_stock_master (
                farm_cd, wh_cd, item_cd, variety_cd, grade_cd, size_cd,
                weight, harvest_year, storage_dt, in_qty, reserved_qty, out_qty
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """,
            (FARM, WH, ITEM, VARIETY, GRADE, SIZE, WEIGHT, YEAR, storage_dt, in_qty, reserved),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def test_t_direct_e2e_01_no_order_without_alloc(self) -> None:
        self._open_file_db()
        self.assertFalse(
            self.conn.execute(
                "SELECT 1 FROM sqlite_master WHERE name='t_order_alloc'"
            ).fetchone()
        )
        seq = self._insert_stock(in_qty=10)
        out = _ship(self.conn, qty=2)
        self.assertTrue(out["ok"])
        row = self.conn.execute(
            "SELECT out_qty, reserved_qty FROM t_stock_master WHERE stock_seq=?",
            (seq,),
        ).fetchone()
        self.assertEqual(row["out_qty"], 2)
        self.assertEqual(row["reserved_qty"], 0)

    def test_t_direct_e2e_02_order_remaining_st01(self) -> None:
        self._open_file_db()
        self._insert_stock(in_qty=10)
        self.conn.execute(
            "INSERT INTO t_order_master (order_no, farm_cd, custm_id, status_cd, stock_status) "
            "VALUES (?, ?, 'C1', 'ST010200', 'N')",
            (ORDER_NO, FARM),
        )
        self.conn.execute(
            """
            INSERT INTO t_order_detail (
                order_detail_id, order_no, farm_cd, item_cd, variety_cd, grade_cd,
                size_cd, weight, harvest_year, wh_cd, qty, out_qty
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 4, 0)
            """,
            (DET_ID, ORDER_NO, FARM, ITEM, VARIETY, GRADE, SIZE, WEIGHT, YEAR, WH),
        )
        self.conn.commit()
        out = _ship(self.conn, qty=1, order_no=ORDER_NO, det=DET_ID)
        self.assertEqual(out["order_status_cd"], ORDER_STATUS_PREP_CD)
        rem = out["remaining_order"][0]
        self.assertEqual(rem["order_qty"], 4)
        self.assertEqual(rem["confirmed_shipped_qty"], 1)
        self.assertEqual(rem["remaining_order_qty"], 3)
        cols = {str(r[1]) for r in self.conn.execute("PRAGMA table_info(t_order_detail)")}
        if "out_qty" in cols:
            out_qty = self.conn.execute(
                "SELECT out_qty FROM t_order_detail WHERE order_detail_id=?",
                (DET_ID,),
            ).fetchone()[0]
            self.assertEqual(float(out_qty or 0), 0.0)
        shipped = self.conn.execute(
            """
            SELECT COALESCE(SUM(d.qty), 0)
            FROM t_sales_detail d
            JOIN t_sales_master m ON m.sales_no = d.sales_no AND m.farm_cd = d.farm_cd
            WHERE d.order_detail_id = ? AND m.sales_status = ?
            """,
            (DET_ID, SALES_STATUS_CONFIRMED),
        ).fetchone()[0]
        self.assertEqual(float(shipped), 1)

    def test_t_direct_e2e_03_reserved_reduces_available(self) -> None:
        self._open_file_db()
        seq = self._insert_stock(in_qty=10, reserved=3)
        with self.assertRaises(ShipConflictError) as ctx:
            _ship(self.conn, qty=8)
        self.assertEqual(ctx.exception.code, "STOCK_UNAVAILABLE")
        out = _ship(self.conn, qty=7)
        self.assertTrue(out["ok"])
        row = self.conn.execute(
            "SELECT out_qty, reserved_qty FROM t_stock_master WHERE stock_seq=?",
            (seq,),
        ).fetchone()
        self.assertEqual(row["out_qty"], 7)
        self.assertEqual(row["reserved_qty"], 3)

    def test_t_direct_e2e_04_sales_stock_log_trace(self) -> None:
        self._open_file_db()
        seq = self._insert_stock(in_qty=5)
        out = _ship(self.conn, qty=1)
        sales_no = out["sales_no"]
        master = self.conn.execute(
            "SELECT sales_status FROM t_sales_master WHERE sales_no=?",
            (sales_no,),
        ).fetchone()
        self.assertEqual(master["sales_status"], SALES_STATUS_CONFIRMED)
        det = self.conn.execute(
            "SELECT sale_detail_no, stock_seq, qty FROM t_sales_detail WHERE sales_no=?",
            (sales_no,),
        ).fetchone()
        self.assertEqual(int(det["stock_seq"]), seq)
        self.assertEqual(det["qty"], 1)
        log = self.conn.execute(
            "SELECT io_type, stock_seq, ref_type, ref_id FROM t_stock_log WHERE ref_id=?",
            (det["sale_detail_no"],),
        ).fetchone()
        self.assertEqual(log["io_type"], "OUT")
        self.assertEqual(int(log["stock_seq"]), seq)
        self.assertEqual(log["ref_type"], REF_TYPE_SALE)
        self.assertEqual(log["ref_id"], det["sale_detail_no"])
        self.assertEqual(REF_TYPE_SALE, "SALE")


if __name__ == "__main__":
    unittest.main()
