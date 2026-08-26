# -*- coding: utf-8 -*-
"""S2C — 주문 출고 시 판매분류(SA01/SA02/SA03) 자동승계."""

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
_TESTS = _HERE.parent
for p in (_TESTS, _SERVER, _ROOT):
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)

from core.ops_biz_date import today_ops_iso  # noqa: E402
from core.order_allocation_service import OrderAllocationService  # noqa: E402
from core.order_constants import WAREHOUSE_CD_DEFAULT  # noqa: E402
from core.order_service import (  # noqa: E402
    OrderDeliveryInput,
    OrderLineInput,
    OrderSaveInput,
    OrderService,
)
from core.order_ship_constants import (  # noqa: E402
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
)
from core.sales_class_constants import (  # noqa: E402
    SALES_CATEGORY_CHUSEOK,
    SALES_CATEGORY_NORMAL,
    SALES_CATEGORY_SEOLLAL,
    SALES_ROUTE_ORDER_SHIP,
    SALES_TYPE_EXPORT,
    SALES_TYPE_RETAIL,
    SALES_TYPE_WHOLESALE,
)
from core.sales_class_schema import ensure_sales_class_schema  # noqa: E402
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


def _ship_order(
    conn: sqlite3.Connection,
    *,
    order_no: str,
    qty: float,
    mode: str = SHIP_MODE_DIRECT,
) -> dict:
    return OrderShipService(conn).confirm(
        ShipConfirmIn(
            farm_cd=FARM,
            ship_mode=mode,
            order_no=order_no,
            sales_dt="2026-08-26",
            user_id="T",
            lines=[
                ShipLineIn(
                    qty=qty,
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


def _create_classified_order(
    conn: sqlite3.Connection,
    *,
    sales_type_cd: str,
    season_type_cd: str,
    qty: float = 10,
    pre_pay: float = 0,
    pre_pay_method_cd: str | None = None,
) -> str:
    svc = OrderService(conn)
    order_no = svc.create_order(
        FARM,
        OrderSaveInput(
            custm_id=CUST,
            order_dt=None,
            sales_type_cd=sales_type_cd,
            season_type_cd=season_type_cd,
            pre_pay_amt=pre_pay,
            pre_pay_method_cd=pre_pay_method_cd,
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


def _snapshot(conn: sqlite3.Connection) -> dict[str, int]:
    def c(sql: str) -> int:
        return int(conn.execute(sql).fetchone()[0])

    return {
        "sales": c("SELECT COUNT(*) FROM t_sales_master"),
        "detail": c("SELECT COUNT(*) FROM t_sales_detail"),
        "out_qty": c("SELECT COALESCE(SUM(out_qty),0) FROM t_stock_master"),
        "stock_log": c("SELECT COUNT(*) FROM t_stock_log"),
        "alloc": c(
            "SELECT COUNT(*) FROM t_order_alloc"
            if conn.execute(
                "SELECT 1 FROM sqlite_master WHERE name='t_order_alloc'"
            ).fetchone()
            else "SELECT 0"
        ),
        "cash": c("SELECT COUNT(*) FROM t_cash_ledger"),
        "ledger": c("SELECT COUNT(*) FROM t_ledger"),
        "order_status": c(
            "SELECT COUNT(*) FROM t_order_master WHERE status_cd='ST010300'"
        ),
    }


class OrderShipSalesClassS2CTest(unittest.TestCase):
    def setUp(self) -> None:
        self.path, self.conn = _open()
        _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=100)

    def tearDown(self) -> None:
        self.conn.close()
        try:
            os.unlink(self.path)
        except OSError:
            pass

    def _assert_class(
        self,
        sales_no: str,
        *,
        sales_type: str | None,
        category: str | None,
        route: str | None,
    ) -> None:
        row = _sale_class(self.conn, sales_no)
        self.assertIsNotNone(row)
        self.assertEqual(row["sales_type_cd"], sales_type)
        self.assertEqual(row["sales_category_cd"], category)
        self.assertEqual(row["sales_route_cd"], route)
        self.assertEqual(row["sales_source"], SALES_SOURCE_ORDER)
        self.assertEqual(row["sales_tp"], "NORMAL")

    def test_t1_retail_normal(self) -> None:
        no = _create_classified_order(
            self.conn, sales_type_cd=SALES_TYPE_RETAIL, season_type_cd="SS010300"
        )
        out = _ship_order(self.conn, order_no=no, qty=2)
        self._assert_class(
            out["sales_no"],
            sales_type=SALES_TYPE_RETAIL,
            category=SALES_CATEGORY_NORMAL,
            route=SALES_ROUTE_ORDER_SHIP,
        )

    def test_t2_retail_chuseok(self) -> None:
        no = _create_classified_order(
            self.conn, sales_type_cd=SALES_TYPE_RETAIL, season_type_cd="SS010200"
        )
        out = _ship_order(self.conn, order_no=no, qty=2)
        self._assert_class(
            out["sales_no"],
            sales_type=SALES_TYPE_RETAIL,
            category=SALES_CATEGORY_CHUSEOK,
            route=SALES_ROUTE_ORDER_SHIP,
        )

    def test_t3_retail_seollal(self) -> None:
        no = _create_classified_order(
            self.conn, sales_type_cd=SALES_TYPE_RETAIL, season_type_cd="SS010100"
        )
        out = _ship_order(self.conn, order_no=no, qty=2)
        self._assert_class(
            out["sales_no"],
            sales_type=SALES_TYPE_RETAIL,
            category=SALES_CATEGORY_SEOLLAL,
            route=SALES_ROUTE_ORDER_SHIP,
        )

    def test_t4_wholesale_normal(self) -> None:
        no = _create_classified_order(
            self.conn, sales_type_cd=SALES_TYPE_WHOLESALE, season_type_cd="SS010300"
        )
        out = _ship_order(self.conn, order_no=no, qty=2)
        self._assert_class(
            out["sales_no"],
            sales_type=SALES_TYPE_WHOLESALE,
            category=SALES_CATEGORY_NORMAL,
            route=SALES_ROUTE_ORDER_SHIP,
        )

    def test_t5_export_normal(self) -> None:
        no = _create_classified_order(
            self.conn, sales_type_cd=SALES_TYPE_EXPORT, season_type_cd="SS010300"
        )
        out = _ship_order(self.conn, order_no=no, qty=2)
        self._assert_class(
            out["sales_no"],
            sales_type=SALES_TYPE_EXPORT,
            category=SALES_CATEGORY_NORMAL,
            route=SALES_ROUTE_ORDER_SHIP,
        )

    def test_t6_partial_ships_same_class(self) -> None:
        no = _create_classified_order(
            self.conn,
            sales_type_cd=SALES_TYPE_RETAIL,
            season_type_cd="SS010200",
            qty=10,
        )
        s1 = _ship_order(self.conn, order_no=no, qty=3)
        s2 = _ship_order(self.conn, order_no=no, qty=4)
        self._assert_class(
            s1["sales_no"],
            sales_type=SALES_TYPE_RETAIL,
            category=SALES_CATEGORY_CHUSEOK,
            route=SALES_ROUTE_ORDER_SHIP,
        )
        self._assert_class(
            s2["sales_no"],
            sales_type=SALES_TYPE_RETAIL,
            category=SALES_CATEGORY_CHUSEOK,
            route=SALES_ROUTE_ORDER_SHIP,
        )

    def test_t7_stock_mode_order_route(self) -> None:
        no = _create_classified_order(
            self.conn, sales_type_cd=SALES_TYPE_RETAIL, season_type_cd="SS010300", qty=10
        )
        _allocate(self.conn, no, qty=5)
        out = _ship_order(self.conn, order_no=no, qty=3, mode=SHIP_MODE_STOCK)
        self._assert_class(
            out["sales_no"],
            sales_type=SALES_TYPE_RETAIL,
            category=SALES_CATEGORY_NORMAL,
            route=SALES_ROUTE_ORDER_SHIP,
        )

    def test_t8_direct_with_order_route(self) -> None:
        no = _create_classified_order(
            self.conn, sales_type_cd=SALES_TYPE_WHOLESALE, season_type_cd="SS010300"
        )
        out = _ship_order(self.conn, order_no=no, qty=2, mode=SHIP_MODE_DIRECT)
        self._assert_class(
            out["sales_no"],
            sales_type=SALES_TYPE_WHOLESALE,
            category=SALES_CATEGORY_NORMAL,
            route=SALES_ROUTE_ORDER_SHIP,
        )

    def test_t9_direct_no_order_null_class(self) -> None:
        out = OrderShipService(self.conn).confirm(
            ShipConfirmIn(
                farm_cd=FARM,
                ship_mode=SHIP_MODE_DIRECT,
                order_no=None,
                custm_id=CUST,
                sales_dt="2026-08-26",
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
        self._assert_class(
            out["sales_no"], sales_type=None, category=None, route=None
        )
        row = _sale_class(self.conn, out["sales_no"])
        self.assertIsNone(row["order_no"])

    def test_t10_legacy_null_sales_type(self) -> None:
        no = _create_classified_order(
            self.conn, sales_type_cd=SALES_TYPE_RETAIL, season_type_cd="SS010300"
        )
        self.conn.execute(
            "UPDATE t_order_master SET sales_type_cd=NULL WHERE farm_cd=? AND order_no=?",
            (FARM, no),
        )
        self.conn.commit()
        out = _ship_order(self.conn, order_no=no, qty=2)
        self._assert_class(
            out["sales_no"],
            sales_type=None,
            category=SALES_CATEGORY_NORMAL,
            route=SALES_ROUTE_ORDER_SHIP,
        )

    def test_t10b_unknown_sales_type_becomes_null(self) -> None:
        """unknown nonblank SA01 외 코드는 추정 없이 NULL 승계. 출고는 정상."""
        no = _create_classified_order(
            self.conn, sales_type_cd=SALES_TYPE_RETAIL, season_type_cd="SS010200"
        )
        self.conn.execute(
            "UPDATE t_order_master SET sales_type_cd='SA019999' WHERE farm_cd=? AND order_no=?",
            (FARM, no),
        )
        self.conn.commit()
        out = _ship_order(self.conn, order_no=no, qty=2)
        self.assertTrue(out["ok"])
        self._assert_class(
            out["sales_no"],
            sales_type=None,
            category=SALES_CATEGORY_CHUSEOK,
            route=SALES_ROUTE_ORDER_SHIP,
        )
        row = _sale_class(self.conn, out["sales_no"])
        self.assertIsNone(row["sales_type_cd"])
        self.assertEqual(row["order_no"], no)

    def test_t11_legacy_blank_season(self) -> None:
        no = _create_classified_order(
            self.conn, sales_type_cd=SALES_TYPE_RETAIL, season_type_cd="SS010300"
        )
        self.conn.execute(
            "UPDATE t_order_master SET season_type_cd='' WHERE farm_cd=? AND order_no=?",
            (FARM, no),
        )
        self.conn.commit()
        out = _ship_order(self.conn, order_no=no, qty=2)
        self._assert_class(
            out["sales_no"],
            sales_type=SALES_TYPE_RETAIL,
            category=None,
            route=SALES_ROUTE_ORDER_SHIP,
        )

    def test_t12_unknown_season_no_guess(self) -> None:
        no = _create_classified_order(
            self.conn, sales_type_cd=SALES_TYPE_RETAIL, season_type_cd="SS010300"
        )
        self.conn.execute(
            "UPDATE t_order_master SET season_type_cd='SS019999' WHERE farm_cd=? AND order_no=?",
            (FARM, no),
        )
        self.conn.commit()
        out = _ship_order(self.conn, order_no=no, qty=2)
        self._assert_class(
            out["sales_no"],
            sales_type=SALES_TYPE_RETAIL,
            category=None,
            route=SALES_ROUTE_ORDER_SHIP,
        )

    def test_t13_t14_schema_precondition_rollback(self) -> None:
        no = _create_classified_order(
            self.conn, sales_type_cd=SALES_TYPE_RETAIL, season_type_cd="SS010300"
        )
        before = _snapshot(self.conn)
        status_before = self.conn.execute(
            "SELECT status_cd FROM t_order_master WHERE order_no=?", (no,)
        ).fetchone()[0]
        # 분류 컬럼 제거(재생성) — SQLite는 DROP COLUMN 지원 버전에 따라 다름 → 테이블 재빌드
        self.conn.executescript(
            """
            CREATE TABLE t_sales_master__tmp AS
            SELECT sales_no, farm_cd, sales_dt, sales_tp, custm_id,
                   tot_sales_amt, tot_ship_fee, tot_item_amt,
                   tot_paid_amt, tot_unpaid_amt, status_cd, rmk,
                   reg_id, reg_dt, order_no, sales_status, sales_source
              FROM t_sales_master;
            DROP TABLE t_sales_master;
            ALTER TABLE t_sales_master__tmp RENAME TO t_sales_master;
            """
        )
        self.conn.commit()
        with self.assertRaises(ShipError) as ctx:
            _ship_order(self.conn, order_no=no, qty=2)
        self.assertEqual(str(ctx.exception.message), MSG_SCHEMA_PRECONDITION)
        after = _snapshot(self.conn)
        self.assertEqual(before, after)
        status_after = self.conn.execute(
            "SELECT status_cd FROM t_order_master WHERE order_no=?", (no,)
        ).fetchone()[0]
        self.assertEqual(status_before, status_after)

    def test_t15_prepay_still_applies(self) -> None:
        # m_account_code for method — ship_service schema may lack AS codes; prepay test has them.
        # Ensure method exists for this DB.
        self.conn.execute(
            """
            INSERT OR IGNORE INTO m_account_code (acct_cd, acct_nm, acct_level, parent_cd, use_yn)
            VALUES (?, '현금', 4, 'AS0101', 'Y')
            """,
            (METHOD,),
        )
        self.conn.commit()
        no = _create_classified_order(
            self.conn,
            sales_type_cd=SALES_TYPE_RETAIL,
            season_type_cd="SS010300",
            qty=10,
            pre_pay=5000,
            pre_pay_method_cd=METHOD,
        )
        out = _ship_order(self.conn, order_no=no, qty=5)
        self._assert_class(
            out["sales_no"],
            sales_type=SALES_TYPE_RETAIL,
            category=SALES_CATEGORY_NORMAL,
            route=SALES_ROUTE_ORDER_SHIP,
        )
        m = self.conn.execute(
            "SELECT tot_paid_amt, tot_unpaid_amt FROM t_sales_master WHERE sales_no=?",
            (out["sales_no"],),
        ).fetchone()
        self.assertEqual(float(m["tot_paid_amt"]), 5000)
        self.assertEqual(float(m["tot_unpaid_amt"]), 0)
        cash_n = self.conn.execute(
            "SELECT COUNT(*) FROM t_cash_ledger WHERE sales_no=?", (out["sales_no"],)
        ).fetchone()[0]
        self.assertEqual(int(cash_n), 1)

    def test_t16_t17_source_and_tp_unchanged(self) -> None:
        no = _create_classified_order(
            self.conn, sales_type_cd=SALES_TYPE_RETAIL, season_type_cd="SS010300"
        )
        out = _ship_order(self.conn, order_no=no, qty=1)
        row = _sale_class(self.conn, out["sales_no"])
        self.assertEqual(row["sales_source"], SALES_SOURCE_ORDER)
        self.assertEqual(row["sales_tp"], "NORMAL")


if __name__ == "__main__":
    unittest.main()
