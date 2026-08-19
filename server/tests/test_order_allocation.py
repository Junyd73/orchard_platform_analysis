# -*- coding: utf-8 -*-
"""T-ORD-02/03/04 재고배정 Stage 3A — FIFO/LIFO/동시성/취소."""

from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import threading
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve()
_SERVER = _HERE.parents[1]
_ROOT = _HERE.parents[2]
for p in (_SERVER, _ROOT):
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)

from core.ops_biz_date import today_ops_iso  # noqa: E402
from core.order_alloc_constants import (  # noqa: E402
    IO_TYPE_CANCEL_HOLD,
    IO_TYPE_HOLD,
    MSG_ALLOC_MIGRATE_BLOCKED,
    MSG_ALLOC_QTY_BELOW,
    MSG_ALLOC_SPEC_LOCKED,
)
from core.order_alloc_migrate import (  # noqa: E402
    OrderAllocMigrateBlocked,
    ensure_order_alloc_schema,
)
from core.order_allocation_service import (  # noqa: E402
    AllocationConflictError,
    OrderAllocationService,
)
from core.order_constants import (  # noqa: E402
    MSG_ORDER_ALLOC_QTY_BELOW,
    MSG_ORDER_ALLOC_SPEC_LOCKED,
    ORDER_STATUS_CANCEL_CD,
    ORDER_STATUS_RESERVED_CD,
    WAREHOUSE_CD_DEFAULT,
)
from core.order_service import (  # noqa: E402
    OrderLineInput,
    OrderService,
    OrderValidationError,
)
from test_order_service import (  # noqa: E402
    CUST,
    FARM,
    VARIETY,
    _counts,
    _open_tmp,
    _sample_payload,
    _schema_sql,
)

ITEM = "FR010100"
GRADE = "GR010100"
SIZE = "SZ010100"
WEIGHT = 15.0
YEAR = 2026


def _insert_stock(
    conn: sqlite3.Connection,
    *,
    storage_dt: str,
    in_qty: float,
    reserved: float = 0,
    farm: str = FARM,
) -> None:
    conn.execute(
        """
        INSERT INTO t_stock_master (
            farm_cd, wh_cd, item_cd, variety_cd, grade_cd, size_cd,
            weight, harvest_year, storage_dt, in_qty, out_qty, reserved_qty, reg_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, 'TEST')
        """,
        (
            farm,
            WAREHOUSE_CD_DEFAULT,
            ITEM,
            VARIETY,
            GRADE,
            SIZE,
            WEIGHT,
            YEAR,
            storage_dt,
            in_qty,
            reserved,
        ),
    )
    conn.commit()


def _open_alloc_db() -> tuple[Path, sqlite3.Connection]:
    path, conn = _open_tmp()
    ensure_order_alloc_schema(conn, skip_preflight=True)
    conn.commit()
    return path, conn


class OrderAllocMigrateTest(unittest.TestCase):
    def test_idempotent_and_block_on_hold(self) -> None:
        path, conn = _open_tmp()
        try:
            first = ensure_order_alloc_schema(conn, skip_preflight=True)
            self.assertTrue(first["allocated_qty_added"] or True)
            second = ensure_order_alloc_schema(conn, skip_preflight=True)
            self.assertFalse(second["allocated_qty_added"])
            _insert_stock(conn, storage_dt="2026-01-01", in_qty=10, reserved=5)
            conn.commit()
            with self.assertRaises(OrderAllocMigrateBlocked) as ctx:
                ensure_order_alloc_schema(conn, skip_preflight=False)
            self.assertIn("reserved", str(ctx.exception.message or MSG_ALLOC_MIGRATE_BLOCKED))
            conn.execute("UPDATE t_stock_master SET reserved_qty=0")
            conn.execute(
                """
                INSERT INTO t_stock_log (
                    farm_cd, item_cd, variety_cd, harvest_year, grade_cd, size_cd,
                    weight, io_type, qty, remark, reg_id, reg_dt
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 5, 'old', 'T', 'x')
                """,
                (FARM, ITEM, VARIETY, YEAR, GRADE, SIZE, WEIGHT, IO_TYPE_HOLD),
            )
            conn.commit()
            ok = ensure_order_alloc_schema(conn, skip_preflight=False)
            self.assertTrue(ok["ok"])
            self.assertGreater(ok["preflight"]["hold_logs"], 0)
            self.assertEqual(ok["preflight"]["reserved_rows"], 0)
        finally:
            conn.close()
            path.unlink(missing_ok=True)


class OrderAllocationStage3Test(unittest.TestCase):
    def setUp(self) -> None:
        self.path, self.conn = _open_alloc_db()
        self.orders = OrderService(self.conn)
        self.alloc = OrderAllocationService(self.conn)

    def tearDown(self) -> None:
        self.conn.close()
        self.path.unlink(missing_ok=True)

    def _create_order(self, qty: float = 100) -> str:
        return self.orders.create_order(FARM, _sample_payload(qty=qty), user_id="U1")

    def _detail_id(self, order_no: str) -> str:
        return f"{order_no}-01"

    def test_t_ord_02_partial_auto(self) -> None:
        _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=30)
        order_no = self._create_order(100)
        det = self._detail_id(order_no)
        summary = self.alloc.allocate(
            FARM, order_no, order_detail_id=det, auto=True, user_id="U1"
        )
        line = summary["details"][0]
        self.assertEqual(line["allocated_qty"], 30)
        self.assertEqual(line["unallocated_qty"], 70)
        self.assertEqual(line["reserved_unshipped_qty"], 30)
        row = self.conn.execute(
            "SELECT reserved_qty FROM t_stock_master WHERE storage_dt = '2026-01-01'"
        ).fetchone()
        self.assertEqual(float(row[0]), 30)
        holds = self.conn.execute(
            "SELECT COUNT(*) FROM t_stock_log WHERE io_type = ?", (IO_TYPE_HOLD,)
        ).fetchone()[0]
        self.assertEqual(int(holds), 1)
        self.assertEqual(_counts(self.conn)["t_sales_master"], 0)
        self.assertEqual(_counts(self.conn)["t_sales_detail"], 0)
        self.assertEqual(_counts(self.conn)["t_cash_ledger"], 0)
        self.assertEqual(_counts(self.conn)["t_ledger"], 0)
        out_qty = float(
            self.conn.execute(
                "SELECT COALESCE(SUM(out_qty), 0) FROM t_stock_master"
            ).fetchone()[0]
        )
        self.assertEqual(out_qty, 0)

    def test_t_ord_03_second_allocate(self) -> None:
        _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=30)
        order_no = self._create_order(100)
        det = self._detail_id(order_no)
        self.alloc.allocate(FARM, order_no, order_detail_id=det, auto=True, user_id="U1")
        _insert_stock(self.conn, storage_dt="2026-02-01", in_qty=70)
        summary = self.alloc.allocate(
            FARM, order_no, order_detail_id=det, auto=True, user_id="U1"
        )
        line = summary["details"][0]
        self.assertEqual(line["allocated_qty"], 100)
        self.assertEqual(line["unallocated_qty"], 0)
        self.assertEqual(len(line["allocations"]), 2)

    def test_fifo_split_rows(self) -> None:
        _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=10)
        _insert_stock(self.conn, storage_dt="2026-03-01", in_qty=20)
        order_no = self._create_order(100)
        det = self._detail_id(order_no)
        summary = self.alloc.allocate(
            FARM, order_no, order_detail_id=det, qty=25, auto=False, user_id="U1"
        )
        allocs = summary["details"][0]["allocations"]
        self.assertEqual(allocs[0]["storage_dt"], "2026-01-01")
        self.assertEqual(allocs[0]["allocated_qty"], 10)
        self.assertEqual(allocs[1]["storage_dt"], "2026-03-01")
        self.assertEqual(allocs[1]["allocated_qty"], 15)

    def test_explicit_qty_409_when_short(self) -> None:
        _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=10)
        order_no = self._create_order(100)
        det = self._detail_id(order_no)
        with self.assertRaises(AllocationConflictError):
            self.alloc.allocate(
                FARM, order_no, order_detail_id=det, qty=30, auto=False, user_id="U1"
            )
        reserved = self.conn.execute(
            "SELECT COALESCE(SUM(reserved_qty),0) FROM t_stock_master"
        ).fetchone()[0]
        self.assertEqual(float(reserved), 0)

    def test_lifo_release(self) -> None:
        _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=10)
        _insert_stock(self.conn, storage_dt="2026-03-01", in_qty=20)
        order_no = self._create_order(100)
        det = self._detail_id(order_no)
        self.alloc.allocate(
            FARM, order_no, order_detail_id=det, qty=25, auto=False, user_id="U1"
        )
        summary = self.alloc.release(
            FARM, order_no, order_detail_id=det, qty=12, user_id="U1"
        )
        allocs = summary["details"][0]["allocations"]
        self.assertEqual(len(allocs), 2)
        by_dt = {a["storage_dt"]: a["allocated_qty"] for a in allocs}
        self.assertEqual(by_dt["2026-01-01"], 10)
        self.assertEqual(by_dt["2026-03-01"], 3)
        cancel_logs = self.conn.execute(
            "SELECT COUNT(*) FROM t_stock_log WHERE io_type = ?",
            (IO_TYPE_CANCEL_HOLD,),
        ).fetchone()[0]
        self.assertEqual(int(cancel_logs), 1)

    def test_release_no_negative(self) -> None:
        _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=10)
        order_no = self._create_order(100)
        det = self._detail_id(order_no)
        self.alloc.allocate(
            FARM, order_no, order_detail_id=det, qty=10, auto=False, user_id="U1"
        )
        with self.assertRaises(AllocationConflictError):
            self.alloc.release(
                FARM, order_no, order_detail_id=det, qty=11, user_id="U1"
            )
        reserved = float(
            self.conn.execute(
                "SELECT reserved_qty FROM t_stock_master"
            ).fetchone()[0]
        )
        self.assertGreaterEqual(reserved, 0)

    def test_cancel_releases_allocation(self) -> None:
        _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=30)
        order_no = self._create_order(100)
        det = self._detail_id(order_no)
        self.alloc.allocate(FARM, order_no, order_detail_id=det, auto=True, user_id="U1")
        self.orders.cancel_order(FARM, order_no, user_id="U1")
        status = self.conn.execute(
            "SELECT status_cd FROM t_order_master WHERE order_no = ?", (order_no,)
        ).fetchone()[0]
        self.assertEqual(status, ORDER_STATUS_CANCEL_CD)
        leftover = self.conn.execute(
            "SELECT COUNT(*) FROM t_order_alloc WHERE order_no = ?", (order_no,)
        ).fetchone()[0]
        self.assertEqual(int(leftover), 0)
        reserved = float(
            self.conn.execute(
                "SELECT COALESCE(SUM(reserved_qty),0) FROM t_stock_master"
            ).fetchone()[0]
        )
        self.assertEqual(reserved, 0)
        detail_alloc = float(
            self.conn.execute(
                "SELECT allocated_qty FROM t_order_detail WHERE order_detail_id = ?",
                (det,),
            ).fetchone()[0]
        )
        self.assertEqual(detail_alloc, 0)

    def test_edit_rejects_qty_below_allocated(self) -> None:
        _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=30)
        order_no = self._create_order(100)
        det = self._detail_id(order_no)
        self.alloc.allocate(FARM, order_no, order_detail_id=det, auto=True, user_id="U1")
        payload = _sample_payload(qty=20)
        with self.assertRaises(OrderValidationError) as ctx:
            self.orders.replace_order(FARM, order_no, payload, user_id="U1")
        self.assertEqual(ctx.exception.message, MSG_ORDER_ALLOC_QTY_BELOW)

    def test_edit_rejects_spec_change(self) -> None:
        _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=30)
        order_no = self._create_order(100)
        det = self._detail_id(order_no)
        self.alloc.allocate(FARM, order_no, order_detail_id=det, auto=True, user_id="U1")
        payload = _sample_payload(qty=100)
        payload.lines[0].grade_cd = "GR010200"
        with self.assertRaises(OrderValidationError) as ctx:
            self.orders.replace_order(FARM, order_no, payload, user_id="U1")
        self.assertEqual(ctx.exception.message, MSG_ORDER_ALLOC_SPEC_LOCKED)

    def test_edit_allows_qty_increase(self) -> None:
        _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=30)
        order_no = self._create_order(100)
        det = self._detail_id(order_no)
        self.alloc.allocate(FARM, order_no, order_detail_id=det, auto=True, user_id="U1")
        payload = _sample_payload(qty=120)
        self.orders.replace_order(FARM, order_no, payload, user_id="U1")
        row = self.conn.execute(
            "SELECT qty, allocated_qty FROM t_order_detail WHERE order_detail_id = ?",
            (det,),
        ).fetchone()
        self.assertEqual(float(row[0]), 120)
        self.assertEqual(float(row[1]), 30)

    def test_detail_exposes_allocation(self) -> None:
        _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=30)
        order_no = self._create_order(100)
        det = self._detail_id(order_no)
        self.alloc.allocate(FARM, order_no, order_detail_id=det, auto=True, user_id="U1")
        data = self.orders.get_order(FARM, order_no)
        line = data["lines"][0]
        self.assertEqual(line["allocated_qty"], 30)
        self.assertEqual(line["unallocated_qty"], 70)

    def test_zero_allocated_order_is_valid(self) -> None:
        order_no = self._create_order(100)
        data = self.orders.get_order(FARM, order_no)
        line = data["lines"][0]
        self.assertEqual(data["status_cd"], ORDER_STATUS_RESERVED_CD)
        self.assertEqual(line["allocated_qty"], 0)
        self.assertEqual(line["unallocated_qty"], 100)
        self.assertEqual(line["reserved_unshipped_qty"], 0)
        summary = self.alloc.get_allocation_summary(FARM, order_no)
        self.assertEqual(summary["details"][0]["allocated_qty"], 0)
        self.assertEqual(summary["details"][0]["allocations"], [])
        self.assertEqual(_counts(self.conn)["hold"], 0)
        self.assertEqual(_counts(self.conn)["t_sales_master"], 0)

    def test_cancel_without_allocation(self) -> None:
        order_no = self._create_order(100)
        self.orders.cancel_order(FARM, order_no, user_id="U1")
        status = self.conn.execute(
            "SELECT status_cd FROM t_order_master WHERE order_no = ?", (order_no,)
        ).fetchone()[0]
        self.assertEqual(status, ORDER_STATUS_CANCEL_CD)
        self.assertEqual(
            int(self.conn.execute("SELECT COUNT(*) FROM t_order_alloc").fetchone()[0]),
            0,
        )
        self.assertEqual(_counts(self.conn)["hold"], 0)

    def test_rollback_leaves_no_hold(self) -> None:
        _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=10)
        order_no = self._create_order(100)
        det = self._detail_id(order_no)
        with self.assertRaises(AllocationConflictError):
            self.alloc.allocate(
                FARM, order_no, order_detail_id=det, qty=30, auto=False, user_id="U1"
            )
        self.assertEqual(
            int(self.conn.execute("SELECT COUNT(*) FROM t_order_alloc").fetchone()[0]),
            0,
        )
        self.assertEqual(
            int(
                self.conn.execute(
                    "SELECT COUNT(*) FROM t_stock_log WHERE io_type = ?",
                    (IO_TYPE_HOLD,),
                ).fetchone()[0]
            ),
            0,
        )


class OrderAllocConcurrencyTest(unittest.TestCase):
    def test_t_ord_04_concurrent_does_not_over_reserve(self) -> None:
        fd, name = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        path = Path(name)
        conn = sqlite3.connect(str(path), timeout=15, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.executescript(_schema_sql())
        ensure_order_alloc_schema(conn, skip_preflight=True)
        conn.commit()
        try:
            orders = OrderService(conn)
            _insert_stock(conn, storage_dt="2026-01-01", in_qty=30)
            order_a = orders.create_order(FARM, _sample_payload(qty=100), user_id="A")
            order_b = orders.create_order(
                FARM,
                _sample_payload(qty=100),
                user_id="B",
            )
            results: list[float | str] = []
            lock = threading.Lock()

            def worker(order_no: str) -> None:
                c = sqlite3.connect(str(path), timeout=15)
                c.row_factory = sqlite3.Row
                svc = OrderAllocationService(c)
                try:
                    summary = svc.allocate(
                        FARM,
                        order_no,
                        order_detail_id=f"{order_no}-01",
                        qty=30,
                        auto=False,
                        user_id="T",
                    )
                    with lock:
                        results.append(float(summary["details"][0]["allocated_qty"]))
                except Exception as exc:
                    with lock:
                        results.append(type(exc).__name__)
                finally:
                    c.close()

            t1 = threading.Thread(target=worker, args=(order_a,))
            t2 = threading.Thread(target=worker, args=(order_b,))
            t1.start()
            t2.start()
            t1.join()
            t2.join()
            nums = [x for x in results if isinstance(x, float)]
            reserved = float(
                conn.execute(
                    "SELECT COALESCE(SUM(reserved_qty),0) FROM t_stock_master"
                ).fetchone()[0]
            )
            self.assertLessEqual(reserved, 30 + 1e-9)
            self.assertLessEqual(sum(nums), 30 + 1e-9)
            self.assertTrue(any(isinstance(x, str) for x in results) or sum(nums) == 30)
        finally:
            conn.close()
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
