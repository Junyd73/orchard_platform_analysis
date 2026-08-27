# -*- coding: utf-8 -*-
"""S4A — 무주문 직접판매 판매분류(SA01/SA02) + route SA030100."""

from __future__ import annotations

import os
import sqlite3
import sys
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve()
_SERVER = _HERE.parents[1]
_ROOT = _HERE.parents[2]
_TESTS = _HERE.parent
for p in (_TESTS, _SERVER, _ROOT):
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)

from core.ops_biz_date import today_ops_iso  # noqa: E402
from core.order_service import (  # noqa: E402
    OrderDeliveryInput,
    OrderLineInput,
    OrderSaveInput,
    OrderService,
)
from core.order_ship_constants import (  # noqa: E402
    CODE_DIRECT_SALES_CATEGORY_INVALID,
    CODE_DIRECT_SALES_CATEGORY_REQUIRED,
    CODE_DIRECT_SALES_TYPE_INVALID,
    CODE_DIRECT_SALES_TYPE_REQUIRED,
    MSG_SCHEMA_PRECONDITION,
    SALES_SOURCE_ORDER,
    SHIP_MODE_DIRECT,
    SHIP_MODE_STOCK,
)
from core.order_ship_service import (  # noqa: E402
    OrderShipService,
    ShipConfirmIn,
    ShipError,
    ShipLineIn,
    ShipValidationError,
)
from core.sales_class_constants import (  # noqa: E402
    DEFAULT_DIRECT_SALES_CATEGORY_CD,
    DEFAULT_DIRECT_SALES_TYPE_CD,
    SALES_CATEGORY_AUCTION,
    SALES_CATEGORY_CHUSEOK,
    SALES_CATEGORY_NORMAL,
    SALES_CATEGORY_SEOLLAL,
    SALES_ROUTE_DIRECT,
    SALES_ROUTE_ORDER_SHIP,
    SALES_TYPE_EXPORT,
    SALES_TYPE_RETAIL,
    SALES_TYPE_WHOLESALE,
)
from test_order_ship_service import (  # noqa: E402
    CUST,
    FARM,
    GRADE,
    ITEM,
    SIZE,
    VARIETY,
    WEIGHT,
    WH,
    YEAR,
    _allocate,
    _insert_stock,
    _open,
)

METHOD = "AS010101"


def _sale_class(conn: sqlite3.Connection, sales_no: str) -> sqlite3.Row:
    return conn.execute(
        """
        SELECT sales_type_cd, sales_category_cd, sales_route_cd,
               sales_tp, sales_source, order_no
          FROM t_sales_master
         WHERE farm_cd = ? AND sales_no = ?
        """,
        (FARM, sales_no),
    ).fetchone()


def _snapshot(conn: sqlite3.Connection) -> dict[str, int]:
    def c(sql: str) -> int:
        return int(conn.execute(sql).fetchone()[0])

    return {
        "sales": c("SELECT COUNT(*) FROM t_sales_master"),
        "detail": c("SELECT COUNT(*) FROM t_sales_detail"),
        "delivery": c("SELECT COUNT(*) FROM t_sales_delivery"),
        "out_qty": c("SELECT COALESCE(SUM(out_qty),0) FROM t_stock_master"),
        "stock_log": c("SELECT COUNT(*) FROM t_stock_log"),
        "cash": c("SELECT COUNT(*) FROM t_cash_ledger"),
        "ledger": c("SELECT COUNT(*) FROM t_ledger"),
    }


def _direct_ship(
    conn: sqlite3.Connection,
    *,
    qty: float = 2,
    sales_type_cd: str | None = DEFAULT_DIRECT_SALES_TYPE_CD,
    sales_category_cd: str | None = DEFAULT_DIRECT_SALES_CATEGORY_CD,
) -> dict:
    return OrderShipService(conn).confirm(
        ShipConfirmIn(
            farm_cd=FARM,
            ship_mode=SHIP_MODE_DIRECT,
            order_no=None,
            custm_id=CUST,
            sales_dt="2026-08-26",
            user_id="T",
            sales_type_cd=sales_type_cd,
            sales_category_cd=sales_category_cd,
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
                    unit_price=1000,
                )
            ],
        )
    )


def _create_classified_order(
    conn: sqlite3.Connection,
    *,
    sales_type_cd: str,
    season_type_cd: str,
    qty: float = 10,
) -> str:
    svc = OrderService(conn)
    order_no = svc.create_order(
        FARM,
        OrderSaveInput(
            custm_id=CUST,
            order_dt=None,
            sales_type_cd=sales_type_cd,
            season_type_cd=season_type_cd,
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


def _set_use_yn(conn: sqlite3.Connection, code_cd: str, use_yn: str) -> None:
    conn.execute(
        "UPDATE m_common_code SET use_yn=? WHERE farm_cd=? AND code_cd=?",
        (use_yn, FARM, code_cd),
    )
    conn.commit()


class OrderShipSalesClassS4ATest(unittest.TestCase):
    def setUp(self) -> None:
        self.path, self.conn = _open()
        _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=100)

    def tearDown(self) -> None:
        self.conn.close()
        try:
            os.unlink(self.path)
        except OSError:
            pass

    def _assert_direct(
        self,
        sales_no: str,
        *,
        sales_type: str,
        category: str,
    ) -> None:
        row = _sale_class(self.conn, sales_no)
        self.assertIsNotNone(row)
        self.assertEqual(row["sales_type_cd"], sales_type)
        self.assertEqual(row["sales_category_cd"], category)
        self.assertEqual(row["sales_route_cd"], SALES_ROUTE_DIRECT)
        self.assertIsNone(row["order_no"])
        self.assertEqual(row["sales_source"], SALES_SOURCE_ORDER)
        self.assertEqual(row["sales_tp"], "NORMAL")

    def test_t1_retail_normal(self) -> None:
        out = _direct_ship(
            self.conn,
            sales_type_cd=SALES_TYPE_RETAIL,
            sales_category_cd=SALES_CATEGORY_NORMAL,
        )
        self._assert_direct(
            out["sales_no"],
            sales_type=SALES_TYPE_RETAIL,
            category=SALES_CATEGORY_NORMAL,
        )

    def test_t2_wholesale_normal(self) -> None:
        out = _direct_ship(
            self.conn,
            sales_type_cd=SALES_TYPE_WHOLESALE,
            sales_category_cd=SALES_CATEGORY_NORMAL,
        )
        self._assert_direct(
            out["sales_no"],
            sales_type=SALES_TYPE_WHOLESALE,
            category=SALES_CATEGORY_NORMAL,
        )

    def test_t3_export_normal(self) -> None:
        out = _direct_ship(
            self.conn,
            sales_type_cd=SALES_TYPE_EXPORT,
            sales_category_cd=SALES_CATEGORY_NORMAL,
        )
        self._assert_direct(
            out["sales_no"],
            sales_type=SALES_TYPE_EXPORT,
            category=SALES_CATEGORY_NORMAL,
        )

    def test_t4_retail_chuseok(self) -> None:
        out = _direct_ship(
            self.conn,
            sales_type_cd=SALES_TYPE_RETAIL,
            sales_category_cd=SALES_CATEGORY_CHUSEOK,
        )
        self._assert_direct(
            out["sales_no"],
            sales_type=SALES_TYPE_RETAIL,
            category=SALES_CATEGORY_CHUSEOK,
        )

    def test_t5_retail_seollal(self) -> None:
        out = _direct_ship(
            self.conn,
            sales_type_cd=SALES_TYPE_RETAIL,
            sales_category_cd=SALES_CATEGORY_SEOLLAL,
        )
        self._assert_direct(
            out["sales_no"],
            sales_type=SALES_TYPE_RETAIL,
            category=SALES_CATEGORY_SEOLLAL,
        )

    def test_t6_type_blank(self) -> None:
        before = _snapshot(self.conn)
        with self.assertRaises(ShipValidationError) as ctx:
            _direct_ship(self.conn, sales_type_cd="", sales_category_cd=SALES_CATEGORY_NORMAL)
        self.assertEqual(ctx.exception.code, CODE_DIRECT_SALES_TYPE_REQUIRED)
        self.assertEqual(before, _snapshot(self.conn))

    def test_t7_type_unknown(self) -> None:
        before = _snapshot(self.conn)
        with self.assertRaises(ShipValidationError) as ctx:
            _direct_ship(
                self.conn,
                sales_type_cd="SA019999",
                sales_category_cd=SALES_CATEGORY_NORMAL,
            )
        self.assertEqual(ctx.exception.code, CODE_DIRECT_SALES_TYPE_INVALID)
        self.assertEqual(before, _snapshot(self.conn))

    def test_t8_type_use_yn_n(self) -> None:
        _set_use_yn(self.conn, SALES_TYPE_RETAIL, "N")
        before = _snapshot(self.conn)
        with self.assertRaises(ShipValidationError) as ctx:
            _direct_ship(
                self.conn,
                sales_type_cd=SALES_TYPE_RETAIL,
                sales_category_cd=SALES_CATEGORY_NORMAL,
            )
        self.assertEqual(ctx.exception.code, CODE_DIRECT_SALES_TYPE_INVALID)
        self.assertEqual(before, _snapshot(self.conn))

    def test_t9_category_blank(self) -> None:
        before = _snapshot(self.conn)
        with self.assertRaises(ShipValidationError) as ctx:
            _direct_ship(self.conn, sales_type_cd=SALES_TYPE_RETAIL, sales_category_cd="")
        self.assertEqual(ctx.exception.code, CODE_DIRECT_SALES_CATEGORY_REQUIRED)
        self.assertEqual(before, _snapshot(self.conn))

    def test_t10_category_unknown(self) -> None:
        before = _snapshot(self.conn)
        with self.assertRaises(ShipValidationError) as ctx:
            _direct_ship(
                self.conn,
                sales_type_cd=SALES_TYPE_RETAIL,
                sales_category_cd="SA029999",
            )
        self.assertEqual(ctx.exception.code, CODE_DIRECT_SALES_CATEGORY_INVALID)
        self.assertEqual(before, _snapshot(self.conn))

    def test_t11_category_auction(self) -> None:
        before = _snapshot(self.conn)
        with self.assertRaises(ShipValidationError) as ctx:
            _direct_ship(
                self.conn,
                sales_type_cd=SALES_TYPE_RETAIL,
                sales_category_cd=SALES_CATEGORY_AUCTION,
            )
        self.assertEqual(ctx.exception.code, CODE_DIRECT_SALES_CATEGORY_INVALID)
        self.assertEqual(before, _snapshot(self.conn))

    def test_t12_category_use_yn_n(self) -> None:
        _set_use_yn(self.conn, SALES_CATEGORY_NORMAL, "N")
        before = _snapshot(self.conn)
        with self.assertRaises(ShipValidationError) as ctx:
            _direct_ship(
                self.conn,
                sales_type_cd=SALES_TYPE_RETAIL,
                sales_category_cd=SALES_CATEGORY_NORMAL,
            )
        self.assertEqual(ctx.exception.code, CODE_DIRECT_SALES_CATEGORY_INVALID)
        self.assertEqual(before, _snapshot(self.conn))

    def test_t13_schema_precondition_rollback(self) -> None:
        before = _snapshot(self.conn)
        self.conn.execute("DROP TABLE m_common_code")
        self.conn.commit()
        with self.assertRaises(ShipError) as ctx:
            _direct_ship(self.conn)
        self.assertEqual(ctx.exception.code, "SCHEMA_PRECONDITION")
        self.assertEqual(str(ctx.exception.message), MSG_SCHEMA_PRECONDITION)
        self.assertEqual(before, _snapshot(self.conn))

    def test_t14_order_direct_ignores_client_class(self) -> None:
        no = _create_classified_order(
            self.conn, sales_type_cd=SALES_TYPE_WHOLESALE, season_type_cd="SS010200"
        )
        out = OrderShipService(self.conn).confirm(
            ShipConfirmIn(
                farm_cd=FARM,
                ship_mode=SHIP_MODE_DIRECT,
                order_no=no,
                sales_dt="2026-08-26",
                user_id="T",
                sales_type_cd=SALES_TYPE_RETAIL,
                sales_category_cd=SALES_CATEGORY_NORMAL,
                lines=[
                    ShipLineIn(
                        qty=2,
                        order_detail_id=f"{no}-01",
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
        row = _sale_class(self.conn, out["sales_no"])
        self.assertEqual(row["sales_type_cd"], SALES_TYPE_WHOLESALE)
        self.assertEqual(row["sales_category_cd"], SALES_CATEGORY_CHUSEOK)
        self.assertEqual(row["sales_route_cd"], SALES_ROUTE_ORDER_SHIP)

    def test_t15_stock_with_order_s2c(self) -> None:
        no = _create_classified_order(
            self.conn, sales_type_cd=SALES_TYPE_EXPORT, season_type_cd="SS010300"
        )
        _allocate(self.conn, no, 10)
        out = OrderShipService(self.conn).confirm(
            ShipConfirmIn(
                farm_cd=FARM,
                ship_mode=SHIP_MODE_STOCK,
                order_no=no,
                sales_dt="2026-08-26",
                user_id="T",
                sales_type_cd=SALES_TYPE_RETAIL,
                sales_category_cd=SALES_CATEGORY_CHUSEOK,
                lines=[
                    ShipLineIn(
                        qty=3,
                        order_detail_id=f"{no}-01",
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
        row = _sale_class(self.conn, out["sales_no"])
        self.assertEqual(row["sales_type_cd"], SALES_TYPE_EXPORT)
        self.assertEqual(row["sales_category_cd"], SALES_CATEGORY_NORMAL)
        self.assertEqual(row["sales_route_cd"], SALES_ROUTE_ORDER_SHIP)

    def test_t16_prepay_regression(self) -> None:
        self.conn.execute(
            """
            INSERT OR IGNORE INTO m_account_code (acct_cd, acct_nm, acct_level, parent_cd, use_yn)
            VALUES (?, '현금', 4, 'AS0101', 'Y')
            """,
            (METHOD,),
        )
        self.conn.commit()
        svc = OrderService(self.conn)
        order_no = svc.create_order(
            FARM,
            OrderSaveInput(
                custm_id=CUST,
                order_dt=None,
                sales_type_cd=SALES_TYPE_RETAIL,
                season_type_cd="SS010300",
                pre_pay_amt=5000,
                pre_pay_method_cd=METHOD,
                lines=[
                    OrderLineInput(
                        variety_cd=VARIETY,
                        weight=WEIGHT,
                        grade_cd=GRADE,
                        size_cd=SIZE,
                        qty=10,
                        unit_price=1000,
                        harvest_year=YEAR,
                        warehouse_cd=WH,
                        item_cd=ITEM,
                        deliveries=[
                            OrderDeliveryInput(
                                delivery_tp_cd="LO010100",
                                qty=10,
                                planned_dt=today_ops_iso(),
                            )
                        ],
                    )
                ],
            ),
            user_id="T",
        )
        svc.confirm_order(FARM, order_no, user_id="T")
        out = OrderShipService(self.conn).confirm(
            ShipConfirmIn(
                farm_cd=FARM,
                ship_mode=SHIP_MODE_DIRECT,
                order_no=order_no,
                sales_dt="2026-08-26",
                user_id="T",
                lines=[
                    ShipLineIn(
                        qty=5,
                        order_detail_id=f"{order_no}-01",
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
        cash_n = self.conn.execute(
            "SELECT COUNT(*) FROM t_cash_ledger WHERE sales_no=?",
            (out["sales_no"],),
        ).fetchone()[0]
        self.assertGreaterEqual(int(cash_n), 1)
        row = _sale_class(self.conn, out["sales_no"])
        self.assertEqual(row["sales_route_cd"], SALES_ROUTE_ORDER_SHIP)

    def test_t17_sales_source_unchanged(self) -> None:
        out = _direct_ship(self.conn)
        row = _sale_class(self.conn, out["sales_no"])
        self.assertEqual(row["sales_source"], SALES_SOURCE_ORDER)

    def test_t18_sales_tp_unchanged(self) -> None:
        out = _direct_ship(self.conn)
        row = _sale_class(self.conn, out["sales_no"])
        self.assertEqual(row["sales_tp"], "NORMAL")


if __name__ == "__main__":
    unittest.main()
