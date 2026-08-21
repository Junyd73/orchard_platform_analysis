# -*- coding: utf-8 -*-
"""Stage4 — 출고 시 선입금 자동배분 (OrderShip + SalesPayment)."""

from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
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

from core.account_manager import AccountManager  # noqa: E402
from core.ops_biz_date import today_ops_iso  # noqa: E402
from core.order_alloc_migrate import ensure_order_alloc_schema  # noqa: E402
from core.order_allocation_service import OrderAllocationService  # noqa: E402
from core.order_constants import WAREHOUSE_CD_DEFAULT  # noqa: E402
from core.order_service import (  # noqa: E402
    OrderDeliveryInput,
    OrderLineInput,
    OrderSaveInput,
    OrderService,
)
from core.order_ship_constants import (  # noqa: E402
    MSG_PREPAY_METHOD_REQUIRED_FOR_SHIPMENT,
    SALES_STATUS_CONFIRMED,
    SHIP_MODE_DIRECT,
    SHIP_MODE_STOCK,
)
from core.order_ship_service import (  # noqa: E402
    OrderShipService,
    ShipConfirmIn,
    ShipLineIn,
    ShipValidationError,
)
from core.sales_payment_constants import MSG_PAY_METHOD_INVALID  # noqa: E402
from core.sales_payment_service import PaymentAddIn, SalesPaymentService  # noqa: E402

FARM = "OR001"
FARM_B = "OR002"
CUST = "C001"
ITEM = "FR010100"
VARIETY = "FR010101"
GRADE = "GR010100"
SIZE = "FR020102"
WEIGHT = 15.0
YEAR = 2026
WH = WAREHOUSE_CD_DEFAULT
METHOD = "AS010101"
SALES_DT = "2026-08-21"


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
            ('{FARM}', 'FR010101', '신고', 'FR010100'),
            ('{FARM}', '{GRADE}', '특', 'GR01'),
            ('{FARM}', '{SIZE}', '15kg', 'FR020100'),
            ('{FARM}', 'LO010100', '방문', 'LO01');
        CREATE TABLE m_account_code (
            acct_cd TEXT PRIMARY KEY, acct_nm TEXT, acct_level INTEGER,
            parent_cd TEXT, use_yn TEXT DEFAULT 'Y'
        );
        INSERT INTO m_account_code(acct_cd, acct_nm, acct_level, parent_cd, use_yn) VALUES
            ('AS010101', '현금', 4, 'AS0101', 'Y'),
            ('AS010102', '농협', 4, 'AS0101', 'Y'),
            ('AS020101', '외상매출금', 4, 'AS0102', 'Y'),
            ('AS010199', '비활성', 4, 'AS0101', 'N');
        CREATE TABLE t_order_master (
            order_no TEXT PRIMARY KEY, farm_cd TEXT, order_dt TEXT, custm_id TEXT,
            status_cd TEXT, stock_status TEXT,
            tot_order_amt REAL, tot_ship_fee REAL, tot_pay_amt REAL,
            rmk TEXT, reg_id TEXT, reg_dt TEXT, mod_id TEXT, mod_dt TEXT,
            season_type_cd TEXT, pre_pay_amt REAL, pre_pay_method_cd TEXT, sales_no TEXT
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
    AccountManager._shared_seq_cache.clear()
    fd, name = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    path = Path(name)
    conn = sqlite3.connect(str(path), timeout=15)
    conn.row_factory = sqlite3.Row
    conn.executescript(_schema_sql())
    ensure_order_alloc_schema(conn, skip_preflight=True)
    conn.commit()
    return path, conn


def _order(
    conn: sqlite3.Connection,
    *,
    qty: float = 30,
    unit_price: float = 10000,
    pre_pay_amt: float = 0,
    pre_pay_method_cd: str | None = None,
    confirm: bool = True,
) -> str:
    svc = OrderService(conn)
    order_no = svc.create_order(
        FARM,
        OrderSaveInput(
            custm_id=CUST,
            order_dt=None,
            season_type_cd="SS010100",
            pre_pay_amt=pre_pay_amt,
            pre_pay_method_cd=pre_pay_method_cd,
            lines=[
                OrderLineInput(
                    variety_cd=VARIETY,
                    weight=WEIGHT,
                    grade_cd=GRADE,
                    size_cd=SIZE,
                    qty=qty,
                    unit_price=unit_price,
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
    if confirm:
        svc.confirm_order(FARM, order_no, user_id="T")
    return order_no


def _insert_stock(
    conn: sqlite3.Connection, in_qty: float, storage_dt: str = "2026-01-01"
) -> int:
    cur = conn.execute(
        """
        INSERT INTO t_stock_master (
            farm_cd, wh_cd, item_cd, variety_cd, grade_cd, size_cd,
            weight, harvest_year, storage_dt, in_qty, out_qty, reserved_qty, reg_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 'T')
        """,
        (FARM, WH, ITEM, VARIETY, GRADE, SIZE, WEIGHT, YEAR, storage_dt, in_qty),
    )
    conn.commit()
    return int(cur.lastrowid)


def _allocate(conn: sqlite3.Connection, order_no: str, qty: float | None = None) -> None:
    OrderAllocationService(conn).allocate(
        FARM,
        order_no,
        order_detail_id=f"{order_no}-01",
        qty=qty,
        auto=qty is None,
        user_id="T",
    )


def _available_qty(conn: sqlite3.Connection) -> float:
    row = conn.execute(
        """
        SELECT COALESCE(SUM(
            COALESCE(in_qty,0) - COALESCE(out_qty,0) - COALESCE(reserved_qty,0)
        ), 0)
          FROM t_stock_master
         WHERE farm_cd=? AND wh_cd=? AND item_cd=? AND variety_cd=?
           AND grade_cd=? AND size_cd=? AND ABS(weight-?)<1e-9 AND harvest_year=?
        """,
        (FARM, WH, ITEM, VARIETY, GRADE, SIZE, WEIGHT, YEAR),
    ).fetchone()
    return float(row[0])


def _ensure_stock(conn: sqlite3.Connection, qty: float) -> None:
    """DIRECT 출고용 비가용 부족분 보충 (별도 storage_dt로 UNIQUE 회피)."""
    need = float(qty) - _available_qty(conn)
    if need > 1e-9:
        n = int(conn.execute("SELECT COUNT(*) FROM t_stock_master").fetchone()[0])
        day = (n % 28) + 1
        _insert_stock(conn, need, storage_dt=f"2026-01-{day:02d}")


def _ship(
    conn: sqlite3.Connection,
    *,
    mode: str,
    qty: float,
    unit_price: float,
    order_no: str | None = None,
    det: str | None = None,
    sales_dt: str = SALES_DT,
    custm_id: str | None = None,
) -> dict:
    if mode == SHIP_MODE_DIRECT:
        _ensure_stock(conn, qty)
    line = ShipLineIn(
        qty=qty,
        order_detail_id=det,
        item_cd=ITEM,
        variety_cd=VARIETY,
        grade_cd=GRADE,
        size_cd=SIZE,
        weight=WEIGHT,
        harvest_year=YEAR,
        wh_cd=WH,
        unit_price=unit_price,
    )
    kwargs: dict = {
        "farm_cd": FARM,
        "ship_mode": mode,
        "order_no": order_no,
        "sales_dt": sales_dt,
        "user_id": "T",
        "lines": [line],
    }
    if custm_id:
        kwargs["custm_id"] = custm_id
    return OrderShipService(conn).confirm(ShipConfirmIn(**kwargs))


def _master(conn: sqlite3.Connection, sales_no: str) -> sqlite3.Row:
    return conn.execute(
        """
        SELECT sales_no, order_no, sales_dt, tot_sales_amt, tot_paid_amt, tot_unpaid_amt,
               sales_status
          FROM t_sales_master WHERE farm_cd=? AND sales_no=?
        """,
        (FARM, sales_no),
    ).fetchone()


def _cash(conn: sqlite3.Connection, sales_no: str | None = None) -> list[sqlite3.Row]:
    if sales_no:
        return conn.execute(
            """
            SELECT * FROM t_cash_ledger
             WHERE farm_cd=? AND sales_no=?
             ORDER BY paid_detail_no
            """,
            (FARM, sales_no),
        ).fetchall()
    return conn.execute(
        "SELECT * FROM t_cash_ledger WHERE farm_cd=? ORDER BY paid_detail_no",
        (FARM,),
    ).fetchall()


def _ledger_active(conn: sqlite3.Connection, sales_no: str) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT * FROM t_ledger
         WHERE farm_cd=? AND ref_id LIKE ? AND trans_st='10'
         ORDER BY slip_no
        """,
        (FARM, f"SALE-{sales_no}-%"),
    ).fetchall()


class OrderShipPrepayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.path, self.conn = _open()

    def tearDown(self) -> None:
        self.conn.close()
        self.path.unlink(missing_ok=True)

    def test_01_prepay_zero_no_cash(self) -> None:
        order_no = _order(self.conn, qty=5, unit_price=1000, pre_pay_amt=0)
        out = _ship(
            self.conn,
            mode=SHIP_MODE_DIRECT,
            qty=5,
            unit_price=1000,
            order_no=order_no,
            det=f"{order_no}-01",
        )
        self.assertEqual(len(_cash(self.conn, out["sales_no"])), 0)
        m = _master(self.conn, out["sales_no"])
        self.assertEqual(float(m["tot_paid_amt"]), 0)
        self.assertEqual(float(m["tot_unpaid_amt"]), 5000)

    def test_02_prepay_applies_cash_ledger(self) -> None:
        order_no = _order(
            self.conn,
            qty=5,
            unit_price=10000,
            pre_pay_amt=50000,
            pre_pay_method_cd=METHOD,
        )
        out = _ship(
            self.conn,
            mode=SHIP_MODE_DIRECT,
            qty=5,
            unit_price=10000,
            order_no=order_no,
            det=f"{order_no}-01",
        )
        cash = _cash(self.conn, out["sales_no"])
        self.assertEqual(len(cash), 1)
        self.assertEqual(float(cash[0]["pay_amt"]), 50000)
        self.assertEqual(cash[0]["order_no"], order_no)
        self.assertEqual(cash[0]["pay_method_cd"], METHOD)
        led = _ledger_active(self.conn, out["sales_no"])
        self.assertEqual(len(led), 1)
        self.assertEqual(led[0]["trans_type_cd"], "REVENUE")
        self.assertEqual(led[0]["acct_cd"], METHOD)
        m = _master(self.conn, out["sales_no"])
        self.assertEqual(float(m["tot_paid_amt"]), 50000)
        self.assertEqual(float(m["tot_unpaid_amt"]), 0)

    def test_03_prepay_gt_sale_caps_at_sale(self) -> None:
        order_no = _order(
            self.conn,
            qty=8,
            unit_price=10000,
            pre_pay_amt=200000,
            pre_pay_method_cd=METHOD,
        )
        out = _ship(
            self.conn,
            mode=SHIP_MODE_DIRECT,
            qty=8,
            unit_price=10000,
            order_no=order_no,
            det=f"{order_no}-01",
        )
        m = _master(self.conn, out["sales_no"])
        self.assertEqual(float(m["tot_sales_amt"]), 80000)
        self.assertEqual(float(m["tot_paid_amt"]), 80000)
        self.assertEqual(float(m["tot_unpaid_amt"]), 0)
        self.assertLessEqual(float(m["tot_paid_amt"]), float(m["tot_sales_amt"]))

    def test_04_prepay_lt_sale_partial(self) -> None:
        order_no = _order(
            self.conn,
            qty=10,
            unit_price=10000,
            pre_pay_amt=40000,
            pre_pay_method_cd=METHOD,
        )
        out = _ship(
            self.conn,
            mode=SHIP_MODE_DIRECT,
            qty=10,
            unit_price=10000,
            order_no=order_no,
            det=f"{order_no}-01",
        )
        m = _master(self.conn, out["sales_no"])
        self.assertEqual(float(m["tot_paid_amt"]), 40000)
        self.assertEqual(float(m["tot_unpaid_amt"]), 60000)

    def test_05_sequential_three_ships(self) -> None:
        """150k → 100k / 50k / 0."""
        order_no = _order(
            self.conn,
            qty=30,
            unit_price=10000,
            pre_pay_amt=150000,
            pre_pay_method_cd=METHOD,
        )
        s1 = _ship(
            self.conn,
            mode=SHIP_MODE_DIRECT,
            qty=10,
            unit_price=10000,
            order_no=order_no,
            det=f"{order_no}-01",
        )
        m1 = _master(self.conn, s1["sales_no"])
        self.assertEqual(float(m1["tot_paid_amt"]), 100000)
        self.assertEqual(float(m1["tot_unpaid_amt"]), 0)

        s2 = _ship(
            self.conn,
            mode=SHIP_MODE_DIRECT,
            qty=12,
            unit_price=10000,
            order_no=order_no,
            det=f"{order_no}-01",
        )
        m2 = _master(self.conn, s2["sales_no"])
        self.assertEqual(float(m2["tot_paid_amt"]), 50000)
        self.assertEqual(float(m2["tot_unpaid_amt"]), 70000)

        # 이전 판매 불변
        m1b = _master(self.conn, s1["sales_no"])
        self.assertEqual(float(m1b["tot_paid_amt"]), 100000)
        self.assertEqual(len(_cash(self.conn, s1["sales_no"])), 1)

        s3 = _ship(
            self.conn,
            mode=SHIP_MODE_DIRECT,
            qty=8,
            unit_price=10000,
            order_no=order_no,
            det=f"{order_no}-01",
        )
        m3 = _master(self.conn, s3["sales_no"])
        self.assertEqual(float(m3["tot_paid_amt"]), 0)
        self.assertEqual(float(m3["tot_unpaid_amt"]), 80000)
        self.assertEqual(len(_cash(self.conn, s3["sales_no"])), 0)

    def test_06_07_remaining_zero_no_extra_cash_prev_unchanged(self) -> None:
        order_no = _order(
            self.conn,
            qty=20,
            unit_price=10000,
            pre_pay_amt=100000,
            pre_pay_method_cd=METHOD,
        )
        s1 = _ship(
            self.conn,
            mode=SHIP_MODE_DIRECT,
            qty=10,
            unit_price=10000,
            order_no=order_no,
            det=f"{order_no}-01",
        )
        cash1_before = [dict(r) for r in _cash(self.conn, s1["sales_no"])]
        led1_before = [dict(r) for r in _ledger_active(self.conn, s1["sales_no"])]
        m1_before = dict(_master(self.conn, s1["sales_no"]))

        s2 = _ship(
            self.conn,
            mode=SHIP_MODE_DIRECT,
            qty=10,
            unit_price=10000,
            order_no=order_no,
            det=f"{order_no}-01",
        )
        self.assertEqual(len(_cash(self.conn, s2["sales_no"])), 0)
        self.assertEqual([dict(r) for r in _cash(self.conn, s1["sales_no"])], cash1_before)
        self.assertEqual(
            [dict(r) for r in _ledger_active(self.conn, s1["sales_no"])], led1_before
        )
        self.assertEqual(dict(_master(self.conn, s1["sales_no"])), m1_before)

    def test_08_auto_prepay_cash_order_no(self) -> None:
        order_no = _order(
            self.conn,
            qty=3,
            unit_price=10000,
            pre_pay_amt=30000,
            pre_pay_method_cd=METHOD,
        )
        out = _ship(
            self.conn,
            mode=SHIP_MODE_DIRECT,
            qty=3,
            unit_price=10000,
            order_no=order_no,
            det=f"{order_no}-01",
        )
        self.assertEqual(_cash(self.conn, out["sales_no"])[0]["order_no"], order_no)

    def test_09_ordinary_payment_order_no_null(self) -> None:
        order_no = _order(
            self.conn,
            qty=10,
            unit_price=10000,
            pre_pay_amt=30000,
            pre_pay_method_cd=METHOD,
        )
        s1 = _ship(
            self.conn,
            mode=SHIP_MODE_DIRECT,
            qty=10,
            unit_price=10000,
            order_no=order_no,
            det=f"{order_no}-01",
        )
        SalesPaymentService(self.conn).add_payment(
            PaymentAddIn(
                farm_cd=FARM,
                sales_no=s1["sales_no"],
                pay_amt=10000,
                pay_method_cd="AS010102",
                pay_dt=SALES_DT,
                user_id="T",
            )
        )
        rows = _cash(self.conn, s1["sales_no"])
        self.assertEqual(rows[0]["order_no"], order_no)
        self.assertIsNone(rows[1]["order_no"])

    def test_10_ordinary_excluded_from_remaining(self) -> None:
        order_no = _order(
            self.conn,
            qty=20,
            unit_price=10000,
            pre_pay_amt=100000,
            pre_pay_method_cd=METHOD,
        )
        s1 = _ship(
            self.conn,
            mode=SHIP_MODE_DIRECT,
            qty=5,
            unit_price=10000,
            order_no=order_no,
            det=f"{order_no}-01",
        )
        self.assertEqual(float(_master(self.conn, s1["sales_no"])["tot_paid_amt"]), 50000)
        # 일반수금 형태로 order_no NULL cash를 대량 삽입해도 applied_prepay에서 제외
        self.conn.execute(
            """
            INSERT INTO t_cash_ledger(
                paid_detail_no, sales_no, farm_cd, pay_dt, pay_method_cd,
                pay_amt, order_no, reg_id
            ) VALUES (?, ?, ?, ?, ?, 99999, NULL, 'T')
            """,
            (f"{s1['sales_no']}-PX", s1["sales_no"], FARM, SALES_DT, "AS010102"),
        )
        self.conn.commit()
        s2 = _ship(
            self.conn,
            mode=SHIP_MODE_DIRECT,
            qty=5,
            unit_price=10000,
            order_no=order_no,
            det=f"{order_no}-01",
        )
        self.assertEqual(float(_master(self.conn, s2["sales_no"])["tot_paid_amt"]), 50000)
        self.assertEqual(_cash(self.conn, s2["sales_no"])[0]["order_no"], order_no)

    def test_11_other_order_cash_excluded(self) -> None:
        o1 = _order(
            self.conn,
            qty=10,
            unit_price=10000,
            pre_pay_amt=100000,
            pre_pay_method_cd=METHOD,
        )
        o2 = _order(
            self.conn,
            qty=5,
            unit_price=10000,
            pre_pay_amt=50000,
            pre_pay_method_cd=METHOD,
        )
        _ship(
            self.conn,
            mode=SHIP_MODE_DIRECT,
            qty=5,
            unit_price=10000,
            order_no=o2,
            det=f"{o2}-01",
        )
        s1 = _ship(
            self.conn,
            mode=SHIP_MODE_DIRECT,
            qty=10,
            unit_price=10000,
            order_no=o1,
            det=f"{o1}-01",
        )
        self.assertEqual(float(_master(self.conn, s1["sales_no"])["tot_paid_amt"]), 100000)

    def test_12_other_farm_cash_excluded(self) -> None:
        order_no = _order(
            self.conn,
            qty=10,
            unit_price=10000,
            pre_pay_amt=100000,
            pre_pay_method_cd=METHOD,
        )
        # 타 farm의 동일 order_no cash (오염)
        self.conn.execute(
            """
            INSERT INTO t_sales_master(
                sales_no, farm_cd, sales_dt, tot_sales_amt, tot_paid_amt, tot_unpaid_amt,
                order_no, sales_status
            ) VALUES ('20260821-99', ?, ?, 100000, 100000, 0, ?, ?)
            """,
            (FARM_B, SALES_DT, order_no, SALES_STATUS_CONFIRMED),
        )
        self.conn.execute(
            """
            INSERT INTO t_cash_ledger(
                paid_detail_no, sales_no, farm_cd, pay_dt, pay_method_cd,
                pay_amt, order_no, reg_id
            ) VALUES ('20260821-99-P01', '20260821-99', ?, ?, ?, 100000, ?, 'x')
            """,
            (FARM_B, SALES_DT, METHOD, order_no),
        )
        self.conn.commit()
        out = _ship(
            self.conn,
            mode=SHIP_MODE_DIRECT,
            qty=10,
            unit_price=10000,
            order_no=order_no,
            det=f"{order_no}-01",
        )
        self.assertEqual(float(_master(self.conn, out["sales_no"])["tot_paid_amt"]), 100000)

    def test_13_draft_sale_cash_excluded(self) -> None:
        order_no = _order(
            self.conn,
            qty=10,
            unit_price=10000,
            pre_pay_amt=100000,
            pre_pay_method_cd=METHOD,
        )
        self.conn.execute(
            """
            INSERT INTO t_sales_master(
                sales_no, farm_cd, sales_dt, tot_sales_amt, tot_paid_amt, tot_unpaid_amt,
                order_no, sales_status
            ) VALUES ('DRAFT-01', ?, ?, 100000, 100000, 0, ?, 'DRAFT')
            """,
            (FARM, SALES_DT, order_no),
        )
        self.conn.execute(
            """
            INSERT INTO t_cash_ledger(
                paid_detail_no, sales_no, farm_cd, pay_dt, pay_method_cd,
                pay_amt, order_no, reg_id
            ) VALUES ('DRAFT-01-P01', 'DRAFT-01', ?, ?, ?, 100000, ?, 'x')
            """,
            (FARM, SALES_DT, METHOD, order_no),
        )
        self.conn.commit()
        out = _ship(
            self.conn,
            mode=SHIP_MODE_DIRECT,
            qty=10,
            unit_price=10000,
            order_no=order_no,
            det=f"{order_no}-01",
        )
        self.assertEqual(float(_master(self.conn, out["sales_no"])["tot_paid_amt"]), 100000)

    def test_15_stock_plus_order_applies(self) -> None:
        _insert_stock(self.conn, 10)
        order_no = _order(
            self.conn,
            qty=10,
            unit_price=10000,
            pre_pay_amt=50000,
            pre_pay_method_cd=METHOD,
        )
        _allocate(self.conn, order_no, 10)
        out = _ship(
            self.conn,
            mode=SHIP_MODE_STOCK,
            qty=10,
            unit_price=10000,
            order_no=order_no,
            det=f"{order_no}-01",
        )
        self.assertEqual(float(_master(self.conn, out["sales_no"])["tot_paid_amt"]), 50000)
        self.assertEqual(_cash(self.conn, out["sales_no"])[0]["order_no"], order_no)

    def test_16_direct_plus_order_applies(self) -> None:
        order_no = _order(
            self.conn,
            qty=4,
            unit_price=10000,
            pre_pay_amt=20000,
            pre_pay_method_cd=METHOD,
        )
        out = _ship(
            self.conn,
            mode=SHIP_MODE_DIRECT,
            qty=4,
            unit_price=10000,
            order_no=order_no,
            det=f"{order_no}-01",
        )
        self.assertEqual(len(_cash(self.conn, out["sales_no"])), 1)

    def test_17_direct_no_order_no_prepay(self) -> None:
        out = _ship(
            self.conn,
            mode=SHIP_MODE_DIRECT,
            qty=3,
            unit_price=10000,
            order_no=None,
            custm_id=CUST,
        )
        self.assertIsNone(out.get("order_no"))
        self.assertEqual(len(_cash(self.conn, out["sales_no"])), 0)
        m = _master(self.conn, out["sales_no"])
        self.assertEqual(float(m["tot_paid_amt"]), 0)

    def test_18_remaining_gt0_method_null_blocks(self) -> None:
        # 컬럼 NULL 강제 (create_order는 method 필수이므로 직접 UPDATE)
        order_no = _order(
            self.conn,
            qty=5,
            unit_price=10000,
            pre_pay_amt=50000,
            pre_pay_method_cd=METHOD,
        )
        self.conn.execute(
            "UPDATE t_order_master SET pre_pay_method_cd=NULL WHERE order_no=?",
            (order_no,),
        )
        self.conn.commit()
        with self.assertRaises(ShipValidationError) as ctx:
            _ship(
                self.conn,
                mode=SHIP_MODE_DIRECT,
                qty=5,
                unit_price=10000,
                order_no=order_no,
                det=f"{order_no}-01",
            )
        self.assertIn(MSG_PREPAY_METHOD_REQUIRED_FOR_SHIPMENT, str(ctx.exception))
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM t_sales_master").fetchone()[0],
            0,
        )
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM t_cash_ledger").fetchone()[0],
            0,
        )

    def test_19_remaining_zero_method_null_ok(self) -> None:
        order_no = _order(
            self.conn,
            qty=5,
            unit_price=10000,
            pre_pay_amt=0,
            pre_pay_method_cd=None,
        )
        self.conn.execute(
            "UPDATE t_order_master SET pre_pay_method_cd=NULL WHERE order_no=?",
            (order_no,),
        )
        self.conn.commit()
        out = _ship(
            self.conn,
            mode=SHIP_MODE_DIRECT,
            qty=5,
            unit_price=10000,
            order_no=order_no,
            det=f"{order_no}-01",
        )
        self.assertTrue(out["ok"])
        self.assertEqual(len(_cash(self.conn, out["sales_no"])), 0)

    def test_20_inactive_or_receivable_method_fails(self) -> None:
        order_no = _order(
            self.conn,
            qty=5,
            unit_price=10000,
            pre_pay_amt=50000,
            pre_pay_method_cd=METHOD,
        )
        self.conn.execute(
            "UPDATE t_order_master SET pre_pay_method_cd=? WHERE order_no=?",
            ("AS020101", order_no),
        )
        self.conn.commit()
        with self.assertRaises(ShipValidationError) as ctx:
            _ship(
                self.conn,
                mode=SHIP_MODE_DIRECT,
                qty=5,
                unit_price=10000,
                order_no=order_no,
                det=f"{order_no}-01",
            )
        self.assertIn(MSG_PAY_METHOD_INVALID, str(ctx.exception))

        self.conn.execute(
            "UPDATE t_order_master SET pre_pay_method_cd=? WHERE order_no=?",
            ("AS010199", order_no),
        )
        self.conn.commit()
        with self.assertRaises(ShipValidationError):
            _ship(
                self.conn,
                mode=SHIP_MODE_DIRECT,
                qty=5,
                unit_price=10000,
                order_no=order_no,
                det=f"{order_no}-01",
            )

    def test_21_22_23_accounting_dates_and_paid_sum(self) -> None:
        order_no = _order(
            self.conn,
            qty=5,
            unit_price=10000,
            pre_pay_amt=30000,
            pre_pay_method_cd=METHOD,
        )
        out = _ship(
            self.conn,
            mode=SHIP_MODE_DIRECT,
            qty=5,
            unit_price=10000,
            order_no=order_no,
            det=f"{order_no}-01",
            sales_dt="2026-07-15",
        )
        cash = _cash(self.conn, out["sales_no"])[0]
        led = _ledger_active(self.conn, out["sales_no"])[0]
        self.assertEqual(cash["pay_dt"], "2026-07-15")
        self.assertEqual(led["trans_dt"], "2026-07-15")
        self.assertEqual(led["trans_type_cd"], "REVENUE")
        m = _master(self.conn, out["sales_no"])
        cash_sum = sum(float(r["pay_amt"]) for r in _cash(self.conn, out["sales_no"]))
        self.assertEqual(float(m["tot_paid_amt"]), cash_sum)
        self.assertEqual(float(m["tot_unpaid_amt"]), float(m["tot_sales_amt"]) - cash_sum)

    def test_24_ordinary_coexist_slip_remap_keeps_provenance(self) -> None:
        order_no = _order(
            self.conn,
            qty=10,
            unit_price=10000,
            pre_pay_amt=40000,
            pre_pay_method_cd=METHOD,
        )
        out = _ship(
            self.conn,
            mode=SHIP_MODE_DIRECT,
            qty=10,
            unit_price=10000,
            order_no=order_no,
            det=f"{order_no}-01",
        )
        SalesPaymentService(self.conn).add_payment(
            PaymentAddIn(
                farm_cd=FARM,
                sales_no=out["sales_no"],
                pay_amt=20000,
                pay_method_cd=METHOD,
                pay_dt=SALES_DT,
                user_id="T",
            )
        )
        rows = _cash(self.conn, out["sales_no"])
        self.assertEqual(rows[0]["order_no"], order_no)
        self.assertIsNone(rows[1]["order_no"])
        self.assertEqual(rows[0]["slip_no"], rows[1]["slip_no"])

    def test_25_prepay_failure_full_rollback(self) -> None:
        _insert_stock(self.conn, 10)
        order_no = _order(
            self.conn,
            qty=10,
            unit_price=10000,
            pre_pay_amt=50000,
            pre_pay_method_cd=METHOD,
        )
        _allocate(self.conn, order_no, 10)
        stock_before = dict(
            self.conn.execute("SELECT * FROM t_stock_master").fetchone()
        )
        alloc_before = dict(
            self.conn.execute("SELECT * FROM t_order_alloc").fetchone()
        )
        order_before = dict(
            self.conn.execute(
                "SELECT status_cd, stock_status, sales_no FROM t_order_master WHERE order_no=?",
                (order_no,),
            ).fetchone()
        )
        log_before = self.conn.execute("SELECT COUNT(*) FROM t_stock_log").fetchone()[0]

        with patch.object(
            SalesPaymentService,
            "add_payment_in_tx",
            side_effect=RuntimeError("prepay boom"),
        ):
            with self.assertRaises(RuntimeError):
                _ship(
                    self.conn,
                    mode=SHIP_MODE_STOCK,
                    qty=10,
                    unit_price=10000,
                    order_no=order_no,
                    det=f"{order_no}-01",
                )

        self.assertEqual(
            dict(self.conn.execute("SELECT * FROM t_stock_master").fetchone()),
            stock_before,
        )
        self.assertEqual(
            dict(self.conn.execute("SELECT * FROM t_order_alloc").fetchone()),
            alloc_before,
        )
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM t_stock_log").fetchone()[0],
            log_before,
        )
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM t_sales_master").fetchone()[0],
            0,
        )
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM t_sales_detail").fetchone()[0],
            0,
        )
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM t_sales_delivery").fetchone()[0],
            0,
        )
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM t_cash_ledger").fetchone()[0],
            0,
        )
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM t_ledger").fetchone()[0],
            0,
        )
        self.assertEqual(
            dict(
                self.conn.execute(
                    "SELECT status_cd, stock_status, sales_no FROM t_order_master WHERE order_no=?",
                    (order_no,),
                ).fetchone()
            ),
            order_before,
        )

    def test_26_retry_no_double_prepay(self) -> None:
        order_no = _order(
            self.conn,
            qty=5,
            unit_price=10000,
            pre_pay_amt=50000,
            pre_pay_method_cd=METHOD,
        )
        out = _ship(
            self.conn,
            mode=SHIP_MODE_DIRECT,
            qty=5,
            unit_price=10000,
            order_no=order_no,
            det=f"{order_no}-01",
        )
        cash_cnt = len(_cash(self.conn))
        with self.assertRaises(Exception):
            _ship(
                self.conn,
                mode=SHIP_MODE_DIRECT,
                qty=5,
                unit_price=10000,
                order_no=order_no,
                det=f"{order_no}-01",
            )
        self.assertEqual(len(_cash(self.conn)), cash_cnt)
        self.assertEqual(len(_cash(self.conn, out["sales_no"])), 1)


if __name__ == "__main__":
    unittest.main()
