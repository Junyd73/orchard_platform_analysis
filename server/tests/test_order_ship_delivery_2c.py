# -*- coding: utf-8 -*-
"""Stage 6 보완 2C — STOCK DIRECT 다배송지 C1~C18."""

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

from core.order_alloc_migrate import ensure_order_alloc_schema  # noqa: E402
from core.order_ship_constants import SHIP_MODE_DIRECT, SHIP_MODE_STOCK  # noqa: E402
from core.order_ship_delivery import ShipDeliveryAllocIn  # noqa: E402
from core.order_ship_service import (  # noqa: E402
    OrderShipService,
    ShipConfirmIn,
    ShipError,
    ShipLineIn,
    ShipValidationError,
)
from core.order_allocation_service import OrderAllocationService  # noqa: E402
from core.order_service import (  # noqa: E402
    OrderDeliveryInput,
    OrderLineInput,
    OrderSaveInput,
    OrderService,
)
from core.ops_biz_date import today_ops_iso  # noqa: E402
from core.sales_delivery_schema import ensure_sales_delivery_schema  # noqa: E402

FARM = "OR001"
WH = "WH01"
ITEM = "FR010100"
VARIETY = "FR010101"
GRADE = "GR010100"
SIZE = "FR020101"
WEIGHT = 15.0
YEAR = 2026
CUST = "C1"


def _schema_sql() -> str:
    return """
        CREATE TABLE m_customer (
            farm_cd TEXT, custm_id TEXT, custm_nm TEXT, mobile TEXT, use_yn TEXT DEFAULT 'Y',
            PRIMARY KEY (farm_cd, custm_id)
        );
        INSERT INTO m_customer VALUES ('OR001', 'C1', '테스트', '010', 'Y');
        CREATE TABLE m_common_code (
            farm_cd TEXT, code_cd TEXT, code_nm TEXT, parent_cd TEXT, use_yn TEXT DEFAULT 'Y'
        );
        INSERT INTO m_common_code (farm_cd, code_cd, code_nm, parent_cd) VALUES
            ('OR001', 'LO010100', '방문수령', 'LO01'),
            ('OR001', 'LO010200', '택배', 'LO01'),
            ('OR001', 'SS010100', '시즌', 'SS01');
        CREATE TABLE t_order_master (
            order_no TEXT, farm_cd TEXT, order_dt TEXT, custm_id TEXT,
            season_type_cd TEXT, status_cd TEXT, stock_status TEXT,
            tot_order_amt REAL, tot_ship_fee REAL, tot_pay_amt REAL,
            pre_pay_amt REAL, rmk TEXT, reg_id TEXT, reg_dt TEXT,
            sales_no TEXT, mod_id TEXT, mod_dt TEXT,
            PRIMARY KEY (order_no, farm_cd)
        );
        CREATE TABLE t_order_detail (
            order_detail_id TEXT, order_no TEXT, farm_cd TEXT,
            item_cd TEXT, variety_cd TEXT, grade_cd TEXT, size_cd TEXT,
            weight REAL, qty REAL, unit_price REAL, item_amt REAL,
            wh_cd TEXT, reg_id TEXT, reg_dt TEXT, dlvry_tp TEXT, harvest_year INTEGER
        );
        CREATE TABLE t_order_delivery (
            order_dlvry_id TEXT, order_detail_id TEXT, order_no TEXT, farm_cd TEXT,
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
        CREATE TABLE t_cash_ledger (cash_id INTEGER PRIMARY KEY, farm_cd TEXT);
        CREATE TABLE t_ledger (slip_no TEXT, farm_cd TEXT);
    """


def _open() -> tuple[Path, sqlite3.Connection]:
    fd, name = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    path = Path(name)
    conn = sqlite3.connect(str(path), timeout=15)
    conn.row_factory = sqlite3.Row
    conn.executescript(_schema_sql())
    ensure_order_alloc_schema(conn, skip_preflight=True)
    ensure_sales_delivery_schema(conn)
    conn.commit()
    return path, conn


def _insert_stock(
    conn: sqlite3.Connection,
    *,
    storage_dt: str,
    in_qty: float,
    reserved: float = 0,
    out_qty: float = 0,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO t_stock_master (
            farm_cd, wh_cd, item_cd, variety_cd, grade_cd, size_cd,
            weight, harvest_year, storage_dt, in_qty, out_qty, reserved_qty, reg_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'T')
        """,
        (FARM, WH, ITEM, VARIETY, GRADE, SIZE, WEIGHT, YEAR, storage_dt, in_qty, out_qty, reserved),
    )
    conn.commit()
    return int(cur.lastrowid)


def _alloc(
    qty: float,
    *,
    name: str,
    tel: str = "010-0000-0000",
    addr: str = "서울시 테스트",
    fee: float = 0,
    msg: str = "",
    order_dlvry_id: str = "",
) -> ShipDeliveryAllocIn:
    """배송배분 1건. order_dlvry_id는 주문 배송지 연결(Step3)에서만 채운다."""
    return ShipDeliveryAllocIn(
        qty=qty,
        rcv_name=name,
        rcv_tel=tel,
        rcv_addr=addr,
        dlvry_msg=msg,
        ship_fee=fee,
        order_dlvry_id=order_dlvry_id,
    )


def _confirm_direct(
    conn: sqlite3.Connection,
    *,
    qty: float,
    allocs: list[ShipDeliveryAllocIn] | None,
    ship_fee: float | None = None,
    unit_price: float = 1000,
) -> dict:
    fee = ship_fee if ship_fee is not None else (
        sum(float(a.ship_fee or 0) for a in (allocs or []))
    )
    return OrderShipService(conn).confirm(
        ShipConfirmIn(
            farm_cd=FARM,
            ship_mode=SHIP_MODE_DIRECT,
            sales_dt="2026-08-20",
            custm_id=CUST,
            user_id="T",
            dlvry_tp="LO010200",
            ship_fee=fee,
            snd_name="삼육농원",
            snd_tel="010-0000-0000",
            snd_addr="과수원주소",
            lines=[
                ShipLineIn(
                    qty=qty,
                    item_cd=ITEM,
                    variety_cd=VARIETY,
                    grade_cd=GRADE,
                    size_cd=SIZE,
                    weight=WEIGHT,
                    harvest_year=YEAR,
                    wh_cd=WH,
                    unit_price=unit_price,
                    delivery_allocations=allocs,
                )
            ],
        )
    )


class ShipDelivery2CTest(unittest.TestCase):
    def setUp(self) -> None:
        self.path, self.conn = _open()

    def tearDown(self) -> None:
        self.conn.close()
        self.path.unlink(missing_ok=True)

    def test_c1_three_dest_success(self) -> None:
        _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=10)
        out = _confirm_direct(
            self.conn,
            qty=3,
            allocs=[
                _alloc(1, name="홍", fee=1000),
                _alloc(1, name="김", fee=2000),
                _alloc(1, name="이", fee=3000),
            ],
        )
        self.assertTrue(out["ok"])
        sales_no = out["sales_no"]
        master = self.conn.execute(
            "SELECT tot_ship_fee FROM t_sales_master WHERE sales_no=?", (sales_no,)
        ).fetchone()
        self.assertAlmostEqual(float(master["tot_ship_fee"]), 6000)
        dels = self.conn.execute(
            "SELECT * FROM t_sales_delivery WHERE sales_no=? ORDER BY dlvry_no",
            (sales_no,),
        ).fetchall()
        self.assertEqual(len(dels), 3)
        groups = {d["dlvry_group_no"] for d in dels}
        self.assertEqual(len(groups), 3)
        for d in dels:
            self.assertEqual(d["snd_name"], "삼육농원")
            self.assertEqual(d["snd_tel"], "010-0000-0000")
            self.assertEqual(d["snd_addr"], "과수원주소")

    def test_c1b_sender_required(self) -> None:
        _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=5)
        with self.assertRaises(ShipValidationError) as ctx:
            OrderShipService(self.conn).confirm(
                ShipConfirmIn(
                    farm_cd=FARM,
                    ship_mode=SHIP_MODE_DIRECT,
                    sales_dt="2026-08-20",
                    custm_id=CUST,
                    user_id="T",
                    dlvry_tp="LO010200",
                    ship_fee=0,
                    snd_name="",
                    snd_tel="",
                    lines=[
                        ShipLineIn(
                            qty=1,
                            item_cd=ITEM,
                            variety_cd=VARIETY,
                            grade_cd=GRADE,
                            size_cd=SIZE,
                            weight=WEIGHT,
                            harvest_year=YEAR,
                            wh_cd=WH,
                            unit_price=1000,
                            delivery_allocations=[_alloc(1, name="홍")],
                        )
                    ],
                )
            )
        self.assertEqual(getattr(ctx.exception, "code", ""), "SENDER_REQUIRED")

    def test_c1c_sender_addr_required(self) -> None:
        seq = _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=5)
        with self.assertRaises(ShipValidationError) as ctx:
            OrderShipService(self.conn).confirm(
                ShipConfirmIn(
                    farm_cd=FARM,
                    ship_mode=SHIP_MODE_DIRECT,
                    sales_dt="2026-08-20",
                    custm_id=CUST,
                    user_id="T",
                    dlvry_tp="LO010200",
                    ship_fee=0,
                    snd_name="삼육농원",
                    snd_tel="010-0000-0000",
                    snd_addr="",
                    lines=[
                        ShipLineIn(
                            qty=1,
                            item_cd=ITEM,
                            variety_cd=VARIETY,
                            grade_cd=GRADE,
                            size_cd=SIZE,
                            weight=WEIGHT,
                            harvest_year=YEAR,
                            wh_cd=WH,
                            unit_price=1000,
                            delivery_allocations=[_alloc(1, name="홍")],
                        )
                    ],
                )
            )
        self.assertEqual(getattr(ctx.exception, "code", ""), "SENDER_REQUIRED")
        self._assert_no_sale_side_effects(seq)
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM t_sales_delivery").fetchone()[0], 0
        )

    def test_c2_a2_b1_success(self) -> None:
        _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=10)
        out = _confirm_direct(
            self.conn,
            qty=3,
            allocs=[_alloc(2, name="A", fee=4000), _alloc(1, name="B", fee=0)],
        )
        self.assertTrue(out["ok"])
        fee = self.conn.execute(
            "SELECT SUM(ship_fee) FROM t_sales_delivery WHERE sales_no=?",
            (out["sales_no"],),
        ).fetchone()[0]
        self.assertAlmostEqual(float(fee), 4000)

    def test_c3_under_reject(self) -> None:
        _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=10)
        with self.assertRaises(ShipValidationError):
            _confirm_direct(
                self.conn,
                qty=3,
                allocs=[_alloc(1, name="A"), _alloc(1, name="B")],
            )
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM t_sales_master").fetchone()[0], 0
        )
        self.assertEqual(
            self.conn.execute("SELECT SUM(out_qty) FROM t_stock_master").fetchone()[0] or 0,
            0,
        )

    def test_c4_over_reject(self) -> None:
        _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=10)
        with self.assertRaises(ShipValidationError):
            _confirm_direct(
                self.conn,
                qty=3,
                allocs=[_alloc(2, name="A"), _alloc(2, name="B")],
            )

    def test_c5_missing_name(self) -> None:
        _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=10)
        with self.assertRaises(ShipValidationError):
            _confirm_direct(
                self.conn,
                qty=1,
                allocs=[_alloc(1, name="")],
            )

    def test_c6_missing_addr(self) -> None:
        _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=10)
        with self.assertRaises(ShipValidationError):
            _confirm_direct(
                self.conn,
                qty=1,
                allocs=[_alloc(1, name="홍", addr="")],
            )

    def test_c7_neg_fee_pydantic_or_core(self) -> None:
        _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=10)
        with self.assertRaises(ShipValidationError):
            _confirm_direct(
                self.conn,
                qty=1,
                allocs=[
                    ShipDeliveryAllocIn(
                        qty=1,
                        rcv_name="홍",
                        rcv_tel="010",
                        rcv_addr="서울",
                        ship_fee=-1,
                    )
                ],
                ship_fee=-1,
            )

    def test_c8_validation_no_side_effects(self) -> None:
        seq = _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=5)
        with self.assertRaises(ShipValidationError):
            _confirm_direct(self.conn, qty=3, allocs=[_alloc(1, name="A")])
        row = self.conn.execute(
            "SELECT out_qty FROM t_stock_master WHERE stock_seq=?", (seq,)
        ).fetchone()
        self.assertEqual(float(row["out_qty"]), 0)
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM t_sales_detail").fetchone()[0], 0
        )

    def test_c9_c10_fifo_bridge_same_group(self) -> None:
        """FIFO 1+2 / 배송 A2+B1 — A가 경계를 넘어도 동일 dlvry_group_no."""
        s1 = _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=1)
        s2 = _insert_stock(self.conn, storage_dt="2026-01-02", in_qty=5)
        out = _confirm_direct(
            self.conn,
            qty=3,
            allocs=[_alloc(2, name="A", fee=8000), _alloc(1, name="B", fee=1000)],
        )
        sales_no = out["sales_no"]
        details = self.conn.execute(
            """
            SELECT sale_detail_no, stock_seq, qty, ship_fee
            FROM t_sales_detail WHERE sales_no=? ORDER BY sale_detail_no
            """,
            (sales_no,),
        ).fetchall()
        self.assertEqual(len(details), 2)
        self.assertEqual(int(details[0]["stock_seq"]), s1)
        self.assertAlmostEqual(float(details[0]["qty"]), 1)
        self.assertEqual(int(details[1]["stock_seq"]), s2)
        self.assertAlmostEqual(float(details[1]["qty"]), 2)
        # line fee on first FIFO detail only
        self.assertAlmostEqual(float(details[0]["ship_fee"]), 9000)
        self.assertAlmostEqual(float(details[1]["ship_fee"]), 0)

        dels = self.conn.execute(
            """
            SELECT sale_detail_no, dlvry_qty, dlvry_group_no, ship_fee, rcv_name
            FROM t_sales_delivery WHERE sales_no=? ORDER BY dlvry_no
            """,
            (sales_no,),
        ).fetchall()
        a_rows = [d for d in dels if d["rcv_name"] == "A"]
        self.assertEqual(len(a_rows), 2)
        self.assertEqual(a_rows[0]["dlvry_group_no"], a_rows[1]["dlvry_group_no"])
        self.assertAlmostEqual(sum(float(r["dlvry_qty"]) for r in a_rows), 2)
        self.assertAlmostEqual(sum(float(r["ship_fee"]) for r in a_rows), 8000)
        b_rows = [d for d in dels if d["rcv_name"] == "B"]
        self.assertEqual(len(b_rows), 1)
        self.assertAlmostEqual(float(b_rows[0]["ship_fee"]), 1000)

        master = self.conn.execute(
            "SELECT tot_ship_fee FROM t_sales_master WHERE sales_no=?", (sales_no,)
        ).fetchone()
        self.assertAlmostEqual(float(master["tot_ship_fee"]), 9000)
        det_fee = sum(float(d["ship_fee"] or 0) for d in details)
        del_fee = sum(float(d["ship_fee"] or 0) for d in dels)
        self.assertAlmostEqual(det_fee, float(master["tot_ship_fee"]))
        self.assertAlmostEqual(del_fee, float(master["tot_ship_fee"]))

    def test_c11_reserved_protected(self) -> None:
        _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=3, reserved=3)
        from core.order_ship_service import ShipConflictError

        with self.assertRaises(ShipConflictError):
            _confirm_direct(
                self.conn,
                qty=1,
                allocs=[_alloc(1, name="홍")],
            )

    def test_c16_legacy_single_delivery(self) -> None:
        _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=5)
        out = OrderShipService(self.conn).confirm(
            ShipConfirmIn(
                farm_cd=FARM,
                ship_mode=SHIP_MODE_DIRECT,
                sales_dt="2026-08-20",
                custm_id=CUST,
                user_id="T",
                dlvry_tp="LO010200",
                ship_fee=4000,
                rcv_name="홍길동",
                rcv_tel="010",
                rcv_addr="서울",
                dlvry_msg="문앞",
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
                        delivery_allocations=None,
                    )
                ],
            )
        )
        sales_no = out["sales_no"]
        master = self.conn.execute(
            "SELECT tot_ship_fee FROM t_sales_master WHERE sales_no=?", (sales_no,)
        ).fetchone()
        self.assertAlmostEqual(float(master["tot_ship_fee"]), 4000)
        detail = self.conn.execute(
            "SELECT ship_fee FROM t_sales_detail WHERE sales_no=?", (sales_no,)
        ).fetchone()
        self.assertAlmostEqual(float(detail["ship_fee"]), 4000)
        d = self.conn.execute(
            "SELECT rcv_name, dlvry_group_no FROM t_sales_delivery WHERE sales_no=?",
            (sales_no,),
        ).fetchone()
        self.assertEqual(d["rcv_name"], "홍길동")

    def test_c17_direct_fifo_no_alloc(self) -> None:
        s1 = _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=1)
        s2 = _insert_stock(self.conn, storage_dt="2026-01-02", in_qty=5)
        out = OrderShipService(self.conn).confirm(
            ShipConfirmIn(
                farm_cd=FARM,
                ship_mode=SHIP_MODE_DIRECT,
                sales_dt="2026-08-20",
                custm_id=CUST,
                user_id="T",
                dlvry_tp="LO010100",
                ship_fee=0,
                lines=[
                    ShipLineIn(
                        qty=3,
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
        details = out["sales_details"]
        self.assertEqual(len(details), 2)
        self.assertEqual(int(details[0]["stock_seq"]), s1)
        self.assertEqual(int(details[1]["stock_seq"]), s2)

    def test_c18_order_stock_ship_regression(self) -> None:
        _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=10)
        order_no = OrderService(self.conn).create_order(
            FARM,
            OrderSaveInput(
                custm_id=CUST,
                order_dt=None,
                season_type_cd="SS010100",
                pre_pay_amt=0,
                lines=[
                    OrderLineInput(
                        variety_cd=VARIETY,
                        weight=WEIGHT,
                        grade_cd=GRADE,
                        size_cd=SIZE,
                        qty=5,
                        unit_price=1000,
                        harvest_year=YEAR,
                        warehouse_cd=WH,
                        item_cd=ITEM,
                        deliveries=[
                            OrderDeliveryInput(
                                delivery_tp_cd="LO010100",
                                qty=5,
                                planned_dt=today_ops_iso(),
                            )
                        ],
                    )
                ],
            ),
            user_id="T",
        )
        OrderService(self.conn).confirm_order(FARM, order_no, user_id="T")
        OrderAllocationService(self.conn).allocate(
            FARM,
            order_no,
            order_detail_id=f"{order_no}-01",
            qty=3,
            auto=False,
            user_id="T",
        )
        out = OrderShipService(self.conn).confirm(
            ShipConfirmIn(
                farm_cd=FARM,
                ship_mode=SHIP_MODE_STOCK,
                order_no=order_no,
                sales_dt="2026-08-20",
                user_id="T",
                lines=[
                    ShipLineIn(
                        qty=2,
                        order_detail_id=f"{order_no}-01",
                        unit_price=1000,
                    )
                ],
            )
        )
        self.assertTrue(out["ok"])
        self.assertEqual(len(out["sales_details"]), 1)

    def _assert_no_sale_side_effects(self, seq: int) -> None:
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM t_sales_master").fetchone()[0], 0
        )
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM t_sales_detail").fetchone()[0], 0
        )
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM t_stock_log").fetchone()[0], 0
        )
        row = self.conn.execute(
            "SELECT out_qty FROM t_stock_master WHERE stock_seq=?", (seq,)
        ).fetchone()
        self.assertEqual(float(row["out_qty"]), 0)

    def test_p1_missing_delivery_table_fail_closed(self) -> None:
        seq = _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=5)
        self.conn.execute("DROP TABLE t_sales_delivery")
        self.conn.commit()
        with self.assertRaises(ShipError) as ctx:
            _confirm_direct(
                self.conn,
                qty=1,
                allocs=[_alloc(1, name="홍")],
            )
        self.assertEqual(getattr(ctx.exception, "code", ""), "SCHEMA_PRECONDITION")
        self._assert_no_sale_side_effects(seq)

    def test_p2_missing_dlvry_group_no_fail_closed(self) -> None:
        seq = _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=5)
        self.conn.execute("DROP TABLE t_sales_delivery")
        self.conn.execute(
            """
            CREATE TABLE t_sales_delivery (
                dlvry_no TEXT, sale_detail_no TEXT, sales_no TEXT, farm_cd TEXT,
                rcv_name TEXT, rcv_tel TEXT, rcv_addr TEXT,
                dlvry_qty REAL, dlvry_msg TEXT, ship_fee REAL,
                PRIMARY KEY (dlvry_no, farm_cd)
            )
            """
        )
        self.conn.commit()
        with self.assertRaises(ShipError) as ctx:
            _confirm_direct(
                self.conn,
                qty=1,
                allocs=[_alloc(1, name="홍")],
            )
        self.assertEqual(getattr(ctx.exception, "code", ""), "SCHEMA_PRECONDITION")
        self._assert_no_sale_side_effects(seq)

    def test_p3_missing_ship_fee_col_fail_closed(self) -> None:
        seq = _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=5)
        self.conn.execute("DROP TABLE t_sales_delivery")
        self.conn.execute(
            """
            CREATE TABLE t_sales_delivery (
                dlvry_no TEXT, sale_detail_no TEXT, sales_no TEXT, farm_cd TEXT,
                rcv_name TEXT, rcv_tel TEXT, rcv_addr TEXT,
                dlvry_qty REAL, dlvry_msg TEXT, dlvry_group_no TEXT,
                PRIMARY KEY (dlvry_no, farm_cd)
            )
            """
        )
        self.conn.commit()
        with self.assertRaises(ShipError) as ctx:
            _confirm_direct(
                self.conn,
                qty=1,
                allocs=[_alloc(1, name="홍")],
            )
        self.assertEqual(getattr(ctx.exception, "code", ""), "SCHEMA_PRECONDITION")
        self._assert_no_sale_side_effects(seq)

    def test_p5_missing_snd_cols_fail_closed(self) -> None:
        seq = _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=5)
        self.conn.execute("DROP TABLE t_sales_delivery")
        self.conn.execute(
            """
            CREATE TABLE t_sales_delivery (
                dlvry_no TEXT, sale_detail_no TEXT, sales_no TEXT, farm_cd TEXT,
                rcv_name TEXT, rcv_tel TEXT, rcv_addr TEXT,
                dlvry_qty REAL, dlvry_msg TEXT, dlvry_group_no TEXT, ship_fee REAL,
                PRIMARY KEY (dlvry_no, farm_cd)
            )
            """
        )
        self.conn.commit()
        with self.assertRaises(ShipError) as ctx:
            _confirm_direct(
                self.conn,
                qty=1,
                allocs=[_alloc(1, name="홍")],
            )
        self.assertEqual(getattr(ctx.exception, "code", ""), "SCHEMA_PRECONDITION")
        self._assert_no_sale_side_effects(seq)

    def test_p4_legacy_without_multi_columns_still_ok(self) -> None:
        """legacy(null allocations): delivery table optional columns 없어도 기존처럼 성공."""
        _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=5)
        self.conn.execute("DROP TABLE t_sales_delivery")
        self.conn.execute(
            """
            CREATE TABLE t_sales_delivery (
                dlvry_no TEXT, sale_detail_no TEXT, sales_no TEXT, farm_cd TEXT,
                rcv_name TEXT, rcv_tel TEXT, rcv_addr TEXT,
                dlvry_qty REAL, dlvry_msg TEXT, reg_id TEXT,
                PRIMARY KEY (dlvry_no, farm_cd)
            )
            """
        )
        self.conn.commit()
        out = OrderShipService(self.conn).confirm(
            ShipConfirmIn(
                farm_cd=FARM,
                ship_mode=SHIP_MODE_DIRECT,
                sales_dt="2026-08-20",
                custm_id=CUST,
                user_id="T",
                dlvry_tp="LO010200",
                ship_fee=1000,
                rcv_name="홍길동",
                rcv_tel="010",
                rcv_addr="서울",
                lines=[
                    ShipLineIn(
                        qty=1,
                        item_cd=ITEM,
                        variety_cd=VARIETY,
                        grade_cd=GRADE,
                        size_cd=SIZE,
                        weight=WEIGHT,
                        harvest_year=YEAR,
                        wh_cd=WH,
                        unit_price=1000,
                        delivery_allocations=None,
                    )
                ],
            )
        )
        self.assertTrue(out["ok"])
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM t_sales_master").fetchone()[0], 1
        )
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM t_sales_delivery").fetchone()[0], 1
        )


if __name__ == "__main__":
    unittest.main()
