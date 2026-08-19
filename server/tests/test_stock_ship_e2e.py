# -*- coding: utf-8 -*-
"""T-STOCK-E2E-01~08 부분/전량 STOCK + DIRECT 회귀."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve()
_SERVER = _HERE.parents[1]
_ROOT = _HERE.parents[2]
_TESTS = str(_HERE.parent)
for p in (_TESTS, str(_SERVER), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from core.order_alloc_constants import (  # noqa: E402
    MSG_ALLOC_INVARIANT,
    MSG_ALLOC_QTY_UNAVAILABLE,
)
from core.order_allocation_service import AllocationConflictError  # noqa: E402
from core.order_constants import ORDER_STATUS_DELIVERED_CD, ORDER_STATUS_PREP_CD  # noqa: E402
from core.order_ship_constants import (  # noqa: E402
    MSG_STOCK_UNAVAILABLE,
    SHIP_MODE_DIRECT,
    SHIP_MODE_STOCK,
)
from core.order_ship_service import ShipConflictError  # noqa: E402
from core.sales_stock_trace_schema import REF_TYPE_SALE as TRACE_SALE  # noqa: E402
from test_order_ship_service import (  # noqa: E402
    _allocate,
    _insert_stock,
    _open,
    _order,
    _ship,
    _stock_row,
)


class StockShipE2ETest(unittest.TestCase):
    def setUp(self) -> None:
        self.path, self.conn = _open()

    def tearDown(self) -> None:
        self.conn.close()
        self.path.unlink(missing_ok=True)

    def test_t_stock_e2e_01_to_07(self) -> None:
        seq = _insert_stock(self.conn, storage_dt="2026-08-01", in_qty=20)
        before = _stock_row(self.conn, seq)
        self.assertEqual(before["reserved_qty"], 0)
        order_no = _order(self.conn, qty=5)
        det = f"{order_no}-01"
        _allocate(self.conn, order_no, qty=5)
        mid = _stock_row(self.conn, seq)
        self.assertEqual(mid["reserved_qty"], 5)
        self.assertEqual(mid["out_qty"], 0)
        self.assertEqual(mid["in_qty"] - mid["out_qty"] - mid["reserved_qty"], 15)

        out1 = _ship(self.conn, mode=SHIP_MODE_STOCK, qty=3, order_no=order_no, det=det)
        self.assertEqual(out1["order_status_cd"], ORDER_STATUS_PREP_CD)
        a1 = self.conn.execute(
            "SELECT allocated_qty, shipped_qty FROM t_order_alloc WHERE order_detail_id=?",
            (det,),
        ).fetchone()
        self.assertEqual(a1["allocated_qty"], 5)
        self.assertEqual(a1["shipped_qty"], 3)
        s1 = _stock_row(self.conn, seq)
        self.assertEqual(s1["reserved_qty"], 2)
        self.assertEqual(s1["out_qty"], 3)
        d1 = self.conn.execute(
            "SELECT stock_seq, qty FROM t_sales_detail WHERE sales_no=?",
            (out1["sales_no"],),
        ).fetchone()
        self.assertEqual(int(d1["stock_seq"]), seq)
        log1 = self.conn.execute(
            "SELECT io_type, ref_type, stock_seq FROM t_stock_log WHERE ref_id LIKE ?",
            (out1["sales_no"] + "%",),
        ).fetchone()
        self.assertEqual(log1["io_type"], "OUT")
        self.assertEqual(log1["ref_type"], TRACE_SALE)

        out2 = _ship(self.conn, mode=SHIP_MODE_STOCK, qty=2, order_no=order_no, det=det)
        self.assertEqual(out2["order_status_cd"], ORDER_STATUS_DELIVERED_CD)
        a2 = self.conn.execute(
            "SELECT allocated_qty, shipped_qty FROM t_order_alloc WHERE order_detail_id=?",
            (det,),
        ).fetchone()
        self.assertEqual(a2["allocated_qty"], 5)
        self.assertEqual(a2["shipped_qty"], 5)
        s2 = _stock_row(self.conn, seq)
        self.assertEqual(s2["reserved_qty"], 0)
        self.assertEqual(s2["out_qty"], 5)
        st = self.conn.execute(
            "SELECT status_cd, stock_status FROM t_order_master WHERE order_no=?",
            (order_no,),
        ).fetchone()
        self.assertEqual(st["status_cd"], ORDER_STATUS_DELIVERED_CD)
        self.assertEqual(st["stock_status"], "Y")

    def test_t_stock_e2e_08_direct_after_schema(self) -> None:
        _insert_stock(self.conn, storage_dt="2026-08-02", in_qty=8)
        out = _ship(self.conn, mode=SHIP_MODE_DIRECT, qty=1)
        self.assertEqual(out["ship_mode"], SHIP_MODE_DIRECT)
        self.assertTrue(out["ok"])

    def test_oversold_lot_is_not_alloc_or_direct_candidate(self) -> None:
        bad = _insert_stock(self.conn, storage_dt="2026-08-01", in_qty=1, out_qty=50)
        order_no = _order(self.conn, qty=5)
        with self.assertRaises(AllocationConflictError) as ctx:
            _allocate(self.conn, order_no, qty=5)
        self.assertIn(MSG_ALLOC_QTY_UNAVAILABLE, str(ctx.exception))
        self.assertEqual(_stock_row(self.conn, bad)["reserved_qty"], 0)
        with self.assertRaises(ShipConflictError) as ship_ctx:
            _ship(self.conn, mode=SHIP_MODE_DIRECT, qty=1)
        self.assertIn(MSG_STOCK_UNAVAILABLE, str(ship_ctx.exception))
        self.assertEqual(_stock_row(self.conn, bad)["out_qty"], 50)

    def test_oversold_other_lot_does_not_block_healthy_fifo(self) -> None:
        _insert_stock(self.conn, storage_dt="2025-01-01", in_qty=1, out_qty=50)
        seq = _insert_stock(self.conn, storage_dt="2026-08-01", in_qty=20)
        order_no = _order(self.conn, qty=5)
        _allocate(self.conn, order_no, qty=5)
        self.assertEqual(_stock_row(self.conn, seq)["reserved_qty"], 5)
        self.assertEqual(_stock_row(self.conn, seq)["stock_seq"], seq)

    def test_reserved_over_real_still_blocks(self) -> None:
        _insert_stock(self.conn, storage_dt="2026-07-01", in_qty=10, reserved=15)
        _insert_stock(self.conn, storage_dt="2026-08-01", in_qty=20)
        order_no = _order(self.conn, qty=5)
        with self.assertRaises(AllocationConflictError) as ctx:
            _allocate(self.conn, order_no, qty=5)
        self.assertIn(MSG_ALLOC_INVARIANT, str(ctx.exception))

    def test_negative_real_with_reserved_still_blocks(self) -> None:
        _insert_stock(self.conn, storage_dt="2026-07-01", in_qty=1, out_qty=50, reserved=2)
        _insert_stock(self.conn, storage_dt="2026-08-01", in_qty=20)
        order_no = _order(self.conn, qty=5)
        with self.assertRaises(AllocationConflictError) as ctx:
            _allocate(self.conn, order_no, qty=5)
        self.assertIn(MSG_ALLOC_INVARIANT, str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
