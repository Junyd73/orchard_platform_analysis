# -*- coding: utf-8 -*-
"""Stage 5C OrderShipService.confirm — T-SHIP / TRACE / SSOT / TX."""

from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

_HERE = Path(__file__).resolve()
_SERVER = _HERE.parents[1]
_ROOT = _HERE.parents[2]
for p in (_SERVER, _ROOT):
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)

from core.ops_biz_date import today_ops_iso  # noqa: E402
from core.order_alloc_migrate import ensure_order_alloc_schema  # noqa: E402
from core.sales_class_schema import ensure_sales_class_schema  # noqa: E402
from core.order_allocation_service import OrderAllocationService  # noqa: E402


def _prepare_sales_class_schema(conn: sqlite3.Connection) -> None:
    """ship 테스트용 m_common_code 최소 컬럼 보강 후 ensure_sales_class_schema."""
    for col in ("reg_id", "reg_dt", "mod_id", "mod_dt"):
        try:
            conn.execute(f"ALTER TABLE m_common_code ADD COLUMN {col} TEXT")
        except sqlite3.OperationalError:
            pass
    stats = ensure_sales_class_schema(conn)
    if not stats.get("ok"):
        raise RuntimeError(f"ensure_sales_class_schema failed: {stats.get('reason')}")

from core.order_constants import (  # noqa: E402
    ORDER_STATUS_DELIVERED_CD,
    ORDER_STATUS_PREP_CD,
    ORDER_STATUS_RESERVED_CD,
    WAREHOUSE_CD_DEFAULT,
)
from core.order_service import (  # noqa: E402
    OrderDeliveryInput,
    OrderLineInput,
    OrderSaveInput,
    OrderService,
)
from core.order_ship_constants import (  # noqa: E402
    SALES_STATUS_CONFIRMED,
    SHIP_MODE_DIRECT,
    SHIP_MODE_STOCK,
    STOCK_STATUS_DONE,
)
from core.order_ship_service import (  # noqa: E402
    OrderShipService,
    ShipConfirmIn,
    ShipConflictError,
    ShipError,
    ShipLineIn,
    ShipValidationError,
)
from core.sales_stock_trace_schema import REF_TYPE_SALE  # noqa: E402

FARM = "OR001"
CUST = "C001"
ITEM = "FR010100"
VARIETY = "FR010101"
GRADE = "GR010100"
SIZE = "FR020102"
WEIGHT = 15.0
YEAR = 2026
WH = WAREHOUSE_CD_DEFAULT


def _schema_sql() -> str:
    return f"""
        CREATE TABLE m_customer (
            custm_id TEXT, farm_cd TEXT, custm_nm TEXT, mobile TEXT, use_yn TEXT DEFAULT 'Y'
        );
        INSERT INTO m_customer (custm_id, farm_cd, custm_nm, mobile, use_yn)
        VALUES ('{CUST}', '{FARM}', '테스트', '010-0000-0000', 'Y');
        CREATE TABLE m_common_code (
            farm_cd TEXT, code_cd TEXT, code_nm TEXT, parent_cd TEXT, use_yn TEXT DEFAULT 'Y'
        );
        INSERT INTO m_common_code (farm_cd, code_cd, code_nm, parent_cd) VALUES
            ('{FARM}', 'ST010100', '예약접수', 'ST01'),
            ('{FARM}', 'ST010200', '주문확정', 'ST01'),
            ('{FARM}', 'ST010300', '배송준비', 'ST01'),
            ('{FARM}', 'ST010400', '배송완료', 'ST01'),
            ('{FARM}', 'SA01', '판매유형', NULL),
            ('{FARM}', 'SA010100', '소매', 'SA01'),
            ('{FARM}', 'SA010200', '도매', 'SA01'),
            ('{FARM}', 'SA010300', '수출', 'SA01'),
            ('{FARM}', 'SS01', '시즌가격', NULL),
            ('{FARM}', 'SS010100', '설날', 'SS01'),
            ('{FARM}', 'SS010200', '추석', 'SS01'),
            ('{FARM}', 'SS010300', '일반', 'SS01'),
            ('{FARM}', 'FR010101', '신고', 'FR010100'),
            ('{FARM}', '{GRADE}', '특', 'GR01'),
            ('{FARM}', '{SIZE}', '15kg', 'FR020100'),
            ('{FARM}', 'LO010100', '방문', 'LO01');
        CREATE TABLE t_order_master (
            order_no TEXT PRIMARY KEY, farm_cd TEXT, order_dt TEXT, custm_id TEXT,
            status_cd TEXT, stock_status TEXT,
            tot_order_amt REAL, tot_ship_fee REAL, tot_pay_amt REAL,
            rmk TEXT, reg_id TEXT, reg_dt TEXT, mod_id TEXT, mod_dt TEXT,
            sales_type_cd TEXT, season_type_cd TEXT, pre_pay_amt REAL, pre_pay_method_cd TEXT, sales_no TEXT
        );
        CREATE TABLE t_order_detail (
            order_detail_id TEXT PRIMARY KEY, order_no TEXT, farm_cd TEXT,
            item_cd TEXT, variety_cd TEXT, grade_cd TEXT, size_cd TEXT,
            weight REAL, qty REAL, unit_price REAL, item_amt REAL,
            reserved_qty REAL DEFAULT 0, out_qty REAL DEFAULT 0,
            wh_cd TEXT, reg_id TEXT, reg_dt TEXT, dlvry_tp TEXT, harvest_year INTEGER
        );
        CREATE TABLE t_order_delivery (
            order_dlvry_id TEXT, order_no TEXT, farm_cd TEXT, order_detail_id TEXT,
            snd_name TEXT, snd_tel TEXT, snd_addr TEXT,
            rcv_name TEXT, rcv_tel TEXT, rcv_addr TEXT,
            dlvry_qty REAL, dlvry_msg TEXT, delivery_tp_cd TEXT, planned_dt TEXT, reg_dt TEXT
        );
        CREATE TABLE t_sales_master (
            sales_no TEXT, farm_cd TEXT, sales_dt TEXT, sales_tp TEXT, custm_id TEXT,
            tot_sales_amt REAL, tot_ship_fee REAL, tot_item_amt REAL,
            tot_paid_amt REAL, tot_unpaid_amt REAL, status_cd TEXT, rmk TEXT,
            reg_id TEXT, reg_dt TEXT, order_no TEXT,
            sales_status TEXT, sales_source TEXT,
            mod_id TEXT, mod_dt TEXT,
            PRIMARY KEY (sales_no, farm_cd)
        );
        CREATE TABLE t_sales_detail (
            sale_detail_no TEXT, sales_no TEXT, farm_cd TEXT,
            item_cd TEXT, variety_cd TEXT, grade_cd TEXT, size_cd TEXT,
            qty REAL, unit_price REAL, tot_item_amt REAL, ship_fee REAL DEFAULT 0,
            tot_sale_amt REAL, tot_paid_amt REAL, tot_unpaid_amt REAL,
            dlvry_tp TEXT, order_detail_id TEXT, wh_cd TEXT, stock_seq INTEGER,
            reg_id TEXT, reg_dt TEXT,
            PRIMARY KEY (sale_detail_no, farm_cd)
        );
        CREATE TABLE t_sales_delivery (
            dlvry_no TEXT, sale_detail_no TEXT, sales_no TEXT, farm_cd TEXT,
            snd_name TEXT, snd_tel TEXT, snd_addr TEXT,
            rcv_name TEXT, rcv_tel TEXT, rcv_addr TEXT,
            dlvry_qty REAL, dlvry_msg TEXT, ship_no TEXT, ship_dt TEXT,
            reg_id TEXT, reg_dt TEXT,
            PRIMARY KEY (dlvry_no, farm_cd)
        );
        CREATE TABLE t_stock_master (
            stock_seq INTEGER PRIMARY KEY AUTOINCREMENT,
            farm_cd TEXT NOT NULL, wh_cd TEXT NOT NULL, item_cd TEXT NOT NULL,
            variety_cd TEXT NOT NULL, grade_cd TEXT, size_cd TEXT,
            weight REAL, harvest_year INTEGER, storage_dt TEXT,
            in_qty REAL DEFAULT 0, out_qty REAL DEFAULT 0, reserved_qty REAL DEFAULT 0,
            reg_id TEXT, mod_id TEXT, mod_dt TEXT
        );
        CREATE UNIQUE INDEX idx_stock_master_unique ON t_stock_master(
            farm_cd, wh_cd, item_cd, variety_cd, grade_cd,
            size_cd, weight, harvest_year, storage_dt
        );
        CREATE TABLE t_stock_log (
            log_seq INTEGER PRIMARY KEY AUTOINCREMENT,
            farm_cd TEXT, item_cd TEXT, variety_cd TEXT, harvest_year INTEGER,
            grade_cd TEXT, size_cd TEXT, weight REAL, io_type TEXT, qty REAL,
            remark TEXT, reg_id TEXT, reg_dt TEXT,
            stock_seq INTEGER, ref_type TEXT, ref_id TEXT
        );
        CREATE TABLE m_account_code (
            acct_cd TEXT PRIMARY KEY, acct_nm TEXT, acct_level INTEGER,
            parent_cd TEXT, use_yn TEXT DEFAULT 'Y'
        );
        CREATE TABLE t_cash_ledger (
            paid_detail_no TEXT PRIMARY KEY,
            sales_no TEXT NOT NULL, farm_cd TEXT NOT NULL,
            pay_dt TEXT NOT NULL, pay_method_cd TEXT NOT NULL,
            pay_amt REAL DEFAULT 0, rmk TEXT, reg_id TEXT, reg_dt TEXT,
            slip_no TEXT, order_no TEXT
        );
        CREATE TABLE t_ledger (
            slip_no TEXT PRIMARY KEY, farm_cd TEXT NOT NULL, trans_dt TEXT,
            trans_type_cd TEXT, acct_cd TEXT, trans_amt REAL, rmk TEXT,
            ref_id TEXT, parent_slip_no TEXT, trans_st TEXT DEFAULT '10',
            reg_id TEXT, reg_dt TEXT, mod_id TEXT, mod_dt TEXT
        );
    """


def _open() -> tuple[Path, sqlite3.Connection]:
    fd, name = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    path = Path(name)
    conn = sqlite3.connect(str(path), timeout=15)
    conn.row_factory = sqlite3.Row
    conn.executescript(_schema_sql())
    ensure_order_alloc_schema(conn, skip_preflight=True)
    _prepare_sales_class_schema(conn)
    conn.commit()
    return path, conn


def _insert_stock(
    conn: sqlite3.Connection,
    *,
    storage_dt: str,
    in_qty: float,
    reserved: float = 0,
    out_qty: float = 0,
    item_cd: str = ITEM,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO t_stock_master (
            farm_cd, wh_cd, item_cd, variety_cd, grade_cd, size_cd,
            weight, harvest_year, storage_dt, in_qty, out_qty, reserved_qty, reg_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'T')
        """,
        (FARM, WH, item_cd, VARIETY, GRADE, SIZE, WEIGHT, YEAR, storage_dt, in_qty, out_qty, reserved),
    )
    conn.commit()
    return int(cur.lastrowid)


def _order(conn: sqlite3.Connection, qty: float = 10) -> str:
    svc = OrderService(conn)
    order_no = svc.create_order(
        FARM,
        OrderSaveInput(
            custm_id=CUST,
            order_dt=None,
            sales_type_cd="SA010100",
            season_type_cd="SS010100",
            pre_pay_amt=0,
            lines=[
                OrderLineInput(
                    variety_cd=VARIETY,
                    weight=WEIGHT,
                    grade_cd=GRADE,
                    size_cd=SIZE,
                    qty=qty,
                    unit_price=1000,
                    harvest_year=YEAR,
                    warehouse_cd=WH,
                    item_cd=ITEM,
                    deliveries=[
                        OrderDeliveryInput(
                            delivery_tp_cd="LO010100",
                            qty=qty,
                            planned_dt=today_ops_iso(),
                        )
                    ],
                )
            ],
        ),
        user_id="T",
    )
    svc.confirm_order(FARM, order_no, user_id="T")
    return order_no


def _order_reserved(conn: sqlite3.Connection, qty: float = 10) -> str:
    svc = OrderService(conn)
    return svc.create_order(
        FARM,
        OrderSaveInput(
            custm_id=CUST,
            order_dt=None,
            sales_type_cd="SA010100",
            season_type_cd="SS010100",
            pre_pay_amt=0,
            lines=[
                OrderLineInput(
                    variety_cd=VARIETY,
                    weight=WEIGHT,
                    grade_cd=GRADE,
                    size_cd=SIZE,
                    qty=qty,
                    unit_price=1000,
                    harvest_year=YEAR,
                    warehouse_cd=WH,
                    item_cd=ITEM,
                    deliveries=[
                        OrderDeliveryInput(
                            delivery_tp_cd="LO010100",
                            qty=qty,
                            planned_dt=today_ops_iso(),
                        )
                    ],
                )
            ],
        ),
        user_id="T",
    )


def _allocate(conn: sqlite3.Connection, order_no: str, qty: float | None = None) -> None:
    OrderAllocationService(conn).allocate(
        FARM,
        order_no,
        order_detail_id=f"{order_no}-01",
        qty=qty,
        auto=qty is None,
        user_id="T",
    )


def _ship(
    conn: sqlite3.Connection,
    *,
    mode: str,
    qty: float,
    order_no: str | None = None,
    det: str | None = None,
    item_cd: str = ITEM,
    **extra: object,
) -> dict:
    from core.sales_class_constants import (
        DEFAULT_DIRECT_SALES_CATEGORY_CD,
        DEFAULT_DIRECT_SALES_TYPE_CD,
    )

    line = ShipLineIn(
        qty=qty,
        order_detail_id=det,
        item_cd=item_cd,
        variety_cd=VARIETY,
        grade_cd=GRADE,
        size_cd=SIZE,
        weight=WEIGHT,
        harvest_year=YEAR,
        wh_cd=WH,
        unit_price=1000,
    )
    if not order_no:
        extra.setdefault("sales_type_cd", DEFAULT_DIRECT_SALES_TYPE_CD)
        extra.setdefault("sales_category_cd", DEFAULT_DIRECT_SALES_CATEGORY_CD)
    return OrderShipService(conn).confirm(
        ShipConfirmIn(
            farm_cd=FARM,
            ship_mode=mode,
            order_no=order_no,
            sales_dt="2026-08-19",
            user_id="T",
            lines=[line],
            **extra,  # type: ignore[arg-type]
        )
    )


def _stock_row(conn: sqlite3.Connection, seq: int) -> sqlite3.Row:
    return conn.execute(
        "SELECT * FROM t_stock_master WHERE stock_seq = ?", (seq,)
    ).fetchone()


def _alloc_row(conn: sqlite3.Connection, order_no: str) -> sqlite3.Row:
    return conn.execute(
        "SELECT * FROM t_order_alloc WHERE order_no = ? ORDER BY alloc_id",
        (order_no,),
    ).fetchone()


class OrderShipServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.path, self.conn = _open()

    def tearDown(self) -> None:
        self.conn.close()
        self.path.unlink(missing_ok=True)

    def test_t_ship_01_stock_partial(self) -> None:
        seq = _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=10)
        order_no = _order(self.conn, 10)
        _allocate(self.conn, order_no, 10)
        out = _ship(
            self.conn, mode=SHIP_MODE_STOCK, qty=6,
            order_no=order_no, det=f"{order_no}-01",
        )
        self.assertTrue(out["ok"])
        alloc = _alloc_row(self.conn, order_no)
        self.assertAlmostEqual(float(alloc["allocated_qty"]), 10)
        self.assertAlmostEqual(float(alloc["shipped_qty"]), 6)
        row = _stock_row(self.conn, seq)
        self.assertAlmostEqual(float(row["reserved_qty"]), 4)
        self.assertAlmostEqual(float(row["out_qty"]), 6)
        self.assertAlmostEqual(float(out["sales_details"][0]["qty"]), 6)

    def test_t_ship_02_stock_fifo_two_rows(self) -> None:
        s1 = _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=6)
        s2 = _insert_stock(self.conn, storage_dt="2026-02-01", in_qty=4)
        order_no = _order(self.conn, 10)
        _allocate(self.conn, order_no, 10)
        out = _ship(
            self.conn, mode=SHIP_MODE_STOCK, qty=10,
            order_no=order_no, det=f"{order_no}-01",
        )
        dets = out["sales_details"]
        self.assertEqual(len(dets), 2)
        self.assertEqual(int(dets[0]["stock_seq"]), s1)
        self.assertAlmostEqual(float(dets[0]["qty"]), 6)
        self.assertEqual(int(dets[1]["stock_seq"]), s2)
        self.assertAlmostEqual(float(dets[1]["qty"]), 4)

    def test_t_ship_03_partial_status_prep(self) -> None:
        _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=10)
        order_no = _order(self.conn, 10)
        _allocate(self.conn, order_no, 10)
        out = _ship(
            self.conn, mode=SHIP_MODE_STOCK, qty=6,
            order_no=order_no, det=f"{order_no}-01",
        )
        self.assertEqual(out["order_status_cd"], ORDER_STATUS_PREP_CD)
        st = self.conn.execute(
            "SELECT status_cd, stock_status FROM t_order_master WHERE order_no=?",
            (order_no,),
        ).fetchone()
        self.assertEqual(st["status_cd"], ORDER_STATUS_PREP_CD)
        self.assertNotEqual(st["stock_status"], STOCK_STATUS_DONE)

    def test_t_ship_04_second_ship_completes(self) -> None:
        _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=10)
        order_no = _order(self.conn, 10)
        _allocate(self.conn, order_no, 10)
        _ship(self.conn, mode=SHIP_MODE_STOCK, qty=6, order_no=order_no, det=f"{order_no}-01")
        out = _ship(
            self.conn, mode=SHIP_MODE_STOCK, qty=4,
            order_no=order_no, det=f"{order_no}-01",
        )
        self.assertEqual(out["order_status_cd"], ORDER_STATUS_DELIVERED_CD)
        st = self.conn.execute(
            "SELECT status_cd, stock_status FROM t_order_master WHERE order_no=?",
            (order_no,),
        ).fetchone()
        self.assertEqual(st["status_cd"], ORDER_STATUS_DELIVERED_CD)
        self.assertEqual(st["stock_status"], STOCK_STATUS_DONE)

    def test_t_ship_05_order_direct_leaves_alloc(self) -> None:
        seq = _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=15)
        order_no = _order(self.conn, 10)
        before = self.conn.execute(
            "SELECT COUNT(*) FROM t_order_alloc WHERE order_no=?", (order_no,)
        ).fetchone()[0]
        out = _ship(
            self.conn, mode=SHIP_MODE_DIRECT, qty=6,
            order_no=order_no, det=f"{order_no}-01",
        )
        after = self.conn.execute(
            "SELECT COUNT(*) FROM t_order_alloc WHERE order_no=?", (order_no,)
        ).fetchone()[0]
        self.assertEqual(before, 0)
        self.assertEqual(after, 0)
        row = _stock_row(self.conn, seq)
        self.assertAlmostEqual(float(row["out_qty"]), 6)
        self.assertAlmostEqual(float(row["reserved_qty"]), 0)
        self.assertAlmostEqual(float(out["remaining_order"][0]["confirmed_shipped_qty"]), 6)

    def test_t_ship_06_no_order_direct(self) -> None:
        seq = _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=10)
        orders_before = self.conn.execute("SELECT COUNT(*) FROM t_order_master").fetchone()[0]
        out = _ship(self.conn, mode=SHIP_MODE_DIRECT, qty=3)
        self.assertIsNone(out["order_no"])
        self.assertIsNone(out["order_status_cd"])
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM t_order_master").fetchone()[0],
            orders_before,
        )
        self.assertAlmostEqual(float(_stock_row(self.conn, seq)["out_qty"]), 3)
        master = self.conn.execute(
            "SELECT order_no, sales_status FROM t_sales_master WHERE sales_no=?",
            (out["sales_no"],),
        ).fetchone()
        self.assertIsNone(master["order_no"])
        self.assertEqual(master["sales_status"], SALES_STATUS_CONFIRMED)

    def test_t_ship_07_no_order_stock_rejected(self) -> None:
        _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=10)
        with self.assertRaises(ShipValidationError) as ctx:
            _ship(self.conn, mode=SHIP_MODE_STOCK, qty=1)
        self.assertEqual(ctx.exception.code, "SHIP_STOCK_REQUIRES_ORDER")

    def test_t_ship_08_direct_fifo_two_rows(self) -> None:
        s1 = _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=5)
        s2 = _insert_stock(self.conn, storage_dt="2026-03-01", in_qty=5)
        out = _ship(self.conn, mode=SHIP_MODE_DIRECT, qty=8)
        dets = out["sales_details"]
        self.assertEqual(len(dets), 2)
        self.assertEqual(int(dets[0]["stock_seq"]), s1)
        self.assertAlmostEqual(float(dets[0]["qty"]), 5)
        self.assertEqual(int(dets[1]["stock_seq"]), s2)
        self.assertAlmostEqual(float(dets[1]["qty"]), 3)

    def test_t_ship_09_order_over_ship_rollback(self) -> None:
        seq = _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=15)
        order_no = _order(self.conn, 10)
        with self.assertRaises(ShipConflictError) as ctx:
            _ship(
                self.conn, mode=SHIP_MODE_DIRECT, qty=11,
                order_no=order_no, det=f"{order_no}-01",
            )
        self.assertEqual(ctx.exception.code, "ORDER_OVER_SHIP")
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM t_sales_master").fetchone()[0], 0)
        self.assertAlmostEqual(float(_stock_row(self.conn, seq)["out_qty"]), 0)

    def test_t_ship_10_alloc_over_rollback(self) -> None:
        seq = _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=10)
        order_no = _order(self.conn, 10)
        _allocate(self.conn, order_no, 6)
        with self.assertRaises(ShipConflictError) as ctx:
            _ship(
                self.conn, mode=SHIP_MODE_STOCK, qty=7,
                order_no=order_no, det=f"{order_no}-01",
            )
        self.assertEqual(ctx.exception.code, "ALLOC_OVER_SHIP")
        self.assertAlmostEqual(float(_alloc_row(self.conn, order_no)["shipped_qty"]), 0)
        self.assertAlmostEqual(float(_stock_row(self.conn, seq)["out_qty"]), 0)

    def test_t_ship_11_direct_short_rollback(self) -> None:
        seq = _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=3)
        with self.assertRaises(ShipConflictError) as ctx:
            _ship(self.conn, mode=SHIP_MODE_DIRECT, qty=4)
        self.assertEqual(ctx.exception.code, "STOCK_UNAVAILABLE")
        self.assertAlmostEqual(float(_stock_row(self.conn, seq)["out_qty"]), 0)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM t_sales_master").fetchone()[0], 0)

    def test_t_ship_12_multiline_second_fails(self) -> None:
        _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=5)
        order_no = _order(self.conn, 10)
        svc = OrderShipService(self.conn)
        with self.assertRaises(ShipConflictError):
            svc.confirm(
                ShipConfirmIn(
                    farm_cd=FARM,
                    ship_mode=SHIP_MODE_DIRECT,
                    order_no=order_no,
                    sales_dt="2026-08-19",
                    user_id="T",
                    lines=[
                        ShipLineIn(
                            qty=2, order_detail_id=f"{order_no}-01",
                            item_cd=ITEM, variety_cd=VARIETY, grade_cd=GRADE,
                            size_cd=SIZE, weight=WEIGHT, harvest_year=YEAR, wh_cd=WH,
                        ),
                        ShipLineIn(
                            qty=20, order_detail_id=f"{order_no}-01",
                            item_cd=ITEM, variety_cd=VARIETY, grade_cd=GRADE,
                            size_cd=SIZE, weight=WEIGHT, harvest_year=YEAR, wh_cd=WH,
                        ),
                    ],
                )
            )
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM t_sales_master").fetchone()[0], 0)
        self.assertAlmostEqual(
            float(self.conn.execute("SELECT COALESCE(SUM(out_qty),0) FROM t_stock_master").fetchone()[0]),
            0,
        )

    def test_t_ship_trace_01_02_03(self) -> None:
        s1 = _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=6)
        s2 = _insert_stock(self.conn, storage_dt="2026-02-01", in_qty=4)
        order_no = _order(self.conn, 10)
        _allocate(self.conn, order_no, 10)
        out = _ship(
            self.conn, mode=SHIP_MODE_STOCK, qty=10,
            order_no=order_no, det=f"{order_no}-01",
        )
        for d in out["sales_details"]:
            row = self.conn.execute(
                "SELECT stock_seq FROM t_sales_detail WHERE sale_detail_no=?",
                (d["sale_detail_no"],),
            ).fetchone()
            self.assertEqual(int(row["stock_seq"]), int(d["stock_seq"]))
            log = self.conn.execute(
                "SELECT io_type, stock_seq, ref_type, ref_id, qty FROM t_stock_log WHERE ref_id=?",
                (d["sale_detail_no"],),
            ).fetchone()
            self.assertEqual(log["io_type"], "OUT")
            self.assertEqual(int(log["stock_seq"]), int(d["stock_seq"]))
            self.assertEqual(log["ref_type"], REF_TYPE_SALE)
            self.assertEqual(log["ref_id"], d["sale_detail_no"])
        self.assertEqual({int(out["sales_details"][0]["stock_seq"]), int(out["sales_details"][1]["stock_seq"])}, {s1, s2})

    def test_t_ship_ssot_01_draft_excluded(self) -> None:
        _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=20)
        order_no = _order(self.conn, 10)
        det = f"{order_no}-01"
        self.conn.execute(
            """
            INSERT INTO t_sales_master (sales_no, farm_cd, sales_dt, sales_status, order_no)
            VALUES ('DRAFT-1', ?, '2026-08-01', 'DRAFT', ?)
            """,
            (FARM, order_no),
        )
        self.conn.execute(
            """
            INSERT INTO t_sales_detail (
                sale_detail_no, sales_no, farm_cd, order_detail_id, qty, size_cd
            ) VALUES ('DRAFT-1-S01', 'DRAFT-1', ?, ?, 9, ?)
            """,
            (FARM, det, SIZE),
        )
        self.conn.commit()
        out = _ship(self.conn, mode=SHIP_MODE_DIRECT, qty=6, order_no=order_no, det=det)
        self.assertAlmostEqual(float(out["remaining_order"][0]["confirmed_shipped_qty"]), 6)

    def test_t_ship_ssot_02_ignores_order_detail_out_qty(self) -> None:
        _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=20)
        order_no = _order(self.conn, 10)
        det = f"{order_no}-01"
        self.conn.execute(
            "UPDATE t_order_detail SET out_qty = 9 WHERE order_detail_id=?", (det,)
        )
        self.conn.commit()
        out = _ship(self.conn, mode=SHIP_MODE_DIRECT, qty=6, order_no=order_no, det=det)
        self.assertAlmostEqual(float(out["remaining_order"][0]["confirmed_shipped_qty"]), 6)
        self.assertAlmostEqual(float(out["remaining_order"][0]["remaining_order_qty"]), 4)

    def test_a1_get_order_remaining_after_partial_ship(self) -> None:
        _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=20)
        order_no = _order(self.conn, 10)
        det = f"{order_no}-01"
        _ship(self.conn, mode=SHIP_MODE_DIRECT, qty=6, order_no=order_no, det=det)
        detail = OrderService(self.conn).get_order(FARM, order_no)
        line = detail["lines"][0]
        self.assertAlmostEqual(float(line["confirmed_shipped_qty"]), 6)
        self.assertAlmostEqual(float(line["remaining_order_qty"]), 4)

    def test_t_ship_ssot_03_allocated_kept(self) -> None:
        _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=10)
        order_no = _order(self.conn, 10)
        _allocate(self.conn, order_no, 10)
        _ship(self.conn, mode=SHIP_MODE_STOCK, qty=6, order_no=order_no, det=f"{order_no}-01")
        alloc = _alloc_row(self.conn, order_no)
        self.assertAlmostEqual(float(alloc["allocated_qty"]), 10)
        self.assertAlmostEqual(float(alloc["shipped_qty"]), 6)
        d_alloc = self.conn.execute(
            "SELECT allocated_qty FROM t_order_detail WHERE order_no=?", (order_no,)
        ).fetchone()
        self.assertAlmostEqual(float(d_alloc["allocated_qty"]), 10)

    def test_t_ship_tx_01_fail_after_stock_rolls_back(self) -> None:
        seq = _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=10)
        order_no = _order(self.conn, 10)
        _allocate(self.conn, order_no, 10)
        svc = OrderShipService(self.conn)
        with patch.object(OrderShipService, "_insert_sales_master", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                svc.confirm(
                    ShipConfirmIn(
                        farm_cd=FARM,
                        ship_mode=SHIP_MODE_STOCK,
                        order_no=order_no,
                        sales_dt="2026-08-19",
                        user_id="T",
                        lines=[ShipLineIn(qty=6, order_detail_id=f"{order_no}-01")],
                    )
                )
        self.assertAlmostEqual(float(_alloc_row(self.conn, order_no)["shipped_qty"]), 0)
        self.assertAlmostEqual(float(_stock_row(self.conn, seq)["out_qty"]), 0)
        self.assertAlmostEqual(float(_stock_row(self.conn, seq)["reserved_qty"]), 10)

    def test_t_ship_tx_02_log_fail_rolls_back(self) -> None:
        seq = _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=10)
        svc = OrderShipService(self.conn)
        with patch.object(OrderShipService, "_insert_stock_log", side_effect=RuntimeError("log")):
            with self.assertRaises(RuntimeError):
                svc.confirm(
                    ShipConfirmIn(
                        farm_cd=FARM,
                        ship_mode=SHIP_MODE_DIRECT,
                        sales_dt="2026-08-19",
                        user_id="T",
                        sales_type_cd="SA010100",
                        sales_category_cd="SA020100",
                        lines=[
                            ShipLineIn(
                                qty=2, item_cd=ITEM, variety_cd=VARIETY, grade_cd=GRADE,
                                size_cd=SIZE, weight=WEIGHT, harvest_year=YEAR, wh_cd=WH,
                            )
                        ],
                    )
                )
        self.assertAlmostEqual(float(_stock_row(self.conn, seq)["out_qty"]), 0)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM t_sales_master").fetchone()[0], 0)

    def test_t_ship_tx_03_detail_fail_rolls_back(self) -> None:
        seq = _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=10)
        svc = OrderShipService(self.conn)
        with patch.object(OrderShipService, "_insert_sales_detail", side_effect=RuntimeError("det")):
            with self.assertRaises(RuntimeError):
                svc.confirm(
                    ShipConfirmIn(
                        farm_cd=FARM,
                        ship_mode=SHIP_MODE_DIRECT,
                        sales_dt="2026-08-19",
                        user_id="T",
                        sales_type_cd="SA010100",
                        sales_category_cd="SA020100",
                        lines=[
                            ShipLineIn(
                                qty=2, item_cd=ITEM, variety_cd=VARIETY, grade_cd=GRADE,
                                size_cd=SIZE, weight=WEIGHT, harvest_year=YEAR, wh_cd=WH,
                            )
                        ],
                    )
                )
        self.assertAlmostEqual(float(_stock_row(self.conn, seq)["out_qty"]), 0)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM t_sales_master").fetchone()[0], 0)

    def test_t_ship_tx_04_concurrent_no_over_out(self) -> None:
        _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=10)
        self.conn.commit()
        results: list[object] = []
        lock = threading.Lock()

        def worker(qty: float) -> None:
            c = sqlite3.connect(str(self.path), timeout=15)
            c.row_factory = sqlite3.Row
            try:
                OrderShipService(c).confirm(
                    ShipConfirmIn(
                        farm_cd=FARM,
                        ship_mode=SHIP_MODE_DIRECT,
                        sales_dt="2026-08-19",
                        user_id="T",
                        sales_type_cd="SA010100",
                        sales_category_cd="SA020100",
                        lines=[
                            ShipLineIn(
                                qty=qty, item_cd=ITEM, variety_cd=VARIETY, grade_cd=GRADE,
                                size_cd=SIZE, weight=WEIGHT, harvest_year=YEAR, wh_cd=WH,
                            )
                        ],
                    )
                )
                with lock:
                    results.append("ok")
            except Exception as exc:
                with lock:
                    results.append(type(exc).__name__)
            finally:
                c.close()

        t1 = threading.Thread(target=worker, args=(8,))
        t2 = threading.Thread(target=worker, args=(5,))
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        out_qty = float(
            self.conn.execute("SELECT COALESCE(SUM(out_qty),0) FROM t_stock_master").fetchone()[0]
        )
        self.assertLessEqual(out_qty, 10 + 1e-9)
        self.assertTrue("ok" in results)
        self.assertTrue(any(x != "ok" for x in results) or out_qty <= 10)

    def test_schema_precondition_stock(self) -> None:
        self.conn.execute("DROP TABLE t_order_alloc")
        self.conn.commit()
        _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=10)
        order_no = _order(self.conn, 10)
        with self.assertRaises(ShipError) as ctx:
            _ship(
                self.conn, mode=SHIP_MODE_STOCK, qty=1,
                order_no=order_no, det=f"{order_no}-01",
            )
        self.assertEqual(ctx.exception.code, "SCHEMA_PRECONDITION")

    def test_reserved_ship_blocked(self) -> None:
        from core.order_ship_constants import CODE_SHIP_ORDER_NOT_CONFIRMED

        _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=10)
        order_no = _order_reserved(self.conn, 10)
        st = self.conn.execute(
            "SELECT status_cd FROM t_order_master WHERE order_no=?", (order_no,)
        ).fetchone()["status_cd"]
        self.assertEqual(st, ORDER_STATUS_RESERVED_CD)
        before = {
            "sales": self.conn.execute("SELECT COUNT(*) FROM t_sales_master").fetchone()[0],
            "detail": self.conn.execute("SELECT COUNT(*) FROM t_sales_detail").fetchone()[0],
            "delivery": self.conn.execute("SELECT COUNT(*) FROM t_sales_delivery").fetchone()[0],
            "log": self.conn.execute("SELECT COUNT(*) FROM t_stock_log").fetchone()[0],
            "out": self.conn.execute("SELECT COALESCE(SUM(out_qty),0) FROM t_stock_master").fetchone()[0],
            "rsv": self.conn.execute(
                "SELECT COALESCE(SUM(reserved_qty),0) FROM t_stock_master"
            ).fetchone()[0],
        }
        with self.assertRaises(ShipValidationError) as ctx:
            _ship(
                self.conn, mode=SHIP_MODE_DIRECT, qty=1,
                order_no=order_no, det=f"{order_no}-01",
            )
        self.assertEqual(ctx.exception.code, CODE_SHIP_ORDER_NOT_CONFIRMED)
        after = {
            "sales": self.conn.execute("SELECT COUNT(*) FROM t_sales_master").fetchone()[0],
            "detail": self.conn.execute("SELECT COUNT(*) FROM t_sales_detail").fetchone()[0],
            "delivery": self.conn.execute("SELECT COUNT(*) FROM t_sales_delivery").fetchone()[0],
            "log": self.conn.execute("SELECT COUNT(*) FROM t_stock_log").fetchone()[0],
            "out": self.conn.execute("SELECT COALESCE(SUM(out_qty),0) FROM t_stock_master").fetchone()[0],
            "rsv": self.conn.execute(
                "SELECT COALESCE(SUM(reserved_qty),0) FROM t_stock_master"
            ).fetchone()[0],
        }
        self.assertEqual(before, after)

    def test_direct_doraji_does_not_consume_plain_juice(self) -> None:
        from core.stock_constants import ITEM_JUICE_DORAJI, ITEM_JUICE_PLAIN

        plain_seq = _insert_stock(
            self.conn, storage_dt="2026-01-01", in_qty=10, item_cd=ITEM_JUICE_PLAIN,
        )
        doraji_seq = _insert_stock(
            self.conn, storage_dt="2026-02-01", in_qty=8, item_cd=ITEM_JUICE_DORAJI,
        )
        _ship(self.conn, mode=SHIP_MODE_DIRECT, qty=3, item_cd=ITEM_JUICE_DORAJI)
        self.assertEqual(_stock_row(self.conn, plain_seq)["out_qty"], 0)
        self.assertEqual(_stock_row(self.conn, doraji_seq)["out_qty"], 3)

    def test_direct_parcel_persists_ship_fee_and_delivery(self) -> None:
        """T18~T23: 운영 schema 컬럼 기준 배송비·배송상세 저장."""
        _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=10)
        _insert_stock(self.conn, storage_dt="2026-01-02", in_qty=10)
        out = OrderShipService(self.conn).confirm(
            ShipConfirmIn(
                farm_cd=FARM,
                ship_mode=SHIP_MODE_DIRECT,
                sales_dt="2026-08-19",
                custm_id="C1",
                user_id="T",
                dlvry_tp="LO010200",
                ship_fee=4000,
                rcv_name="홍길동",
                rcv_tel="010-1111-2222",
                rcv_addr="서울시 테스트구 1",
                dlvry_msg="문 앞",
                sales_type_cd="SA010100",
                sales_category_cd="SA020100",
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
                    ),
                    ShipLineIn(
                        qty=3,
                        item_cd=ITEM,
                        variety_cd=VARIETY,
                        grade_cd=GRADE,
                        size_cd=SIZE,
                        weight=WEIGHT,
                        harvest_year=YEAR,
                        wh_cd=WH,
                        unit_price=2000,
                    ),
                ],
            )
        )
        sales_no = out["sales_no"]
        master = self.conn.execute(
            "SELECT tot_ship_fee, tot_item_amt, tot_sales_amt FROM t_sales_master WHERE sales_no=?",
            (sales_no,),
        ).fetchone()
        self.assertAlmostEqual(float(master["tot_ship_fee"]), 4000)
        self.assertAlmostEqual(float(master["tot_item_amt"]), 2 * 1000 + 3 * 2000)
        self.assertAlmostEqual(float(master["tot_sales_amt"]), float(master["tot_item_amt"]) + 4000)

        details = self.conn.execute(
            """
            SELECT sale_detail_no, qty, ship_fee, dlvry_tp
            FROM t_sales_detail WHERE sales_no=? ORDER BY sale_detail_no
            """,
            (sales_no,),
        ).fetchall()
        self.assertEqual(len(details), 2)
        self.assertEqual(str(details[0]["dlvry_tp"]), "LO010200")
        self.assertEqual(str(details[1]["dlvry_tp"]), "LO010200")
        self.assertAlmostEqual(float(details[0]["ship_fee"]), 4000)
        self.assertAlmostEqual(float(details[1]["ship_fee"]), 0)
        fee_sum = sum(float(r["ship_fee"] or 0) for r in details)
        self.assertAlmostEqual(fee_sum, 4000)

        deliveries = self.conn.execute(
            """
            SELECT rcv_name, rcv_tel, rcv_addr, dlvry_msg, sale_detail_no
            FROM t_sales_delivery WHERE sales_no=? ORDER BY sale_detail_no
            """,
            (sales_no,),
        ).fetchall()
        self.assertEqual(len(deliveries), 2)
        self.assertEqual(deliveries[0]["rcv_name"], "홍길동")
        self.assertEqual(deliveries[0]["rcv_tel"], "010-1111-2222")
        self.assertEqual(deliveries[0]["rcv_addr"], "서울시 테스트구 1")
        self.assertEqual(deliveries[0]["dlvry_msg"], "문 앞")


if __name__ == "__main__":
    unittest.main()
