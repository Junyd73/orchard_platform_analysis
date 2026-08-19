# -*- coding: utf-8 -*-
"""T-ORD-01 주문 Stage 2 — 재고 0 저장, 판매/HOLD/회계 미생성."""

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

from core.ops_biz_date import today_ops, today_ops_iso  # noqa: E402
from core.order_constants import (  # noqa: E402
    MSG_ORDER_CANCEL_FORBIDDEN,
    MSG_ORDER_LOCKED_CANCEL,
    MSG_ORDER_LOCKED_DELIVERED,
    MSG_ORDER_QTY_LOCKED,
    ORDER_STATUS_CANCEL_CD,
    ORDER_STATUS_CONFIRMED_CD,
    ORDER_STATUS_DELIVERED_CD,
    ORDER_STATUS_PREP_CD,
    ORDER_STATUS_RESERVED_CD,
    WAREHOUSE_CD_DEFAULT,
)
from core.order_service import (  # noqa: E402
    OrderDeliveryInput,
    OrderHasSalesError,
    OrderLineInput,
    OrderSaveInput,
    OrderService,
    OrderValidationError,
    item_cd_from_variety,
)


FARM = "OR001"
CUST = "C001"
VARIETY = "FR010101"


def _schema_sql() -> str:
    return """
        CREATE TABLE m_customer (
            custm_id TEXT, farm_cd TEXT, custm_nm TEXT, mobile TEXT,
            zip_cd TEXT, addr1 TEXT, addr2 TEXT, custm_tp TEXT, rmk TEXT,
            use_yn TEXT DEFAULT 'Y',
            reg_id TEXT, reg_dt TEXT, mod_id TEXT, mod_dt TEXT
        );
        CREATE TABLE m_common_code (
            farm_cd TEXT, code_cd TEXT, code_nm TEXT, parent_cd TEXT, use_yn TEXT DEFAULT 'Y'
        );
        CREATE TABLE t_order_master (
            order_no TEXT, farm_cd TEXT, order_dt TEXT, custm_id TEXT,
            status_cd TEXT, stock_status TEXT,
            tot_order_amt REAL, tot_ship_fee REAL, tot_pay_amt REAL,
            rmk TEXT, reg_id TEXT, reg_dt TEXT, mod_id TEXT, mod_dt TEXT,
            season_type_cd TEXT, pre_pay_amt REAL, sales_no TEXT
        );
        CREATE TABLE t_order_detail (
            order_detail_id TEXT, order_no TEXT, farm_cd TEXT,
            item_cd TEXT, variety_cd TEXT, grade_cd TEXT, size_cd TEXT,
            weight REAL, qty REAL, unit_price REAL, item_amt REAL,
            wh_cd TEXT, reg_id TEXT, reg_dt TEXT, dlvry_tp TEXT, harvest_year INTEGER
        );
        CREATE TABLE t_order_delivery (
            order_dlvry_id TEXT, order_no TEXT, farm_cd TEXT, order_detail_id TEXT,
            snd_name TEXT, snd_tel TEXT, snd_addr TEXT,
            rcv_name TEXT, rcv_tel TEXT, rcv_addr TEXT,
            dlvry_qty REAL, dlvry_msg TEXT, delivery_tp_cd TEXT, planned_dt TEXT, reg_dt TEXT
        );
        CREATE TABLE t_sales_master (
            sales_no TEXT, farm_cd TEXT, order_no TEXT
        );
        CREATE TABLE t_sales_detail (
            sale_detail_no TEXT, sales_no TEXT, farm_cd TEXT, order_detail_id TEXT
        );
        CREATE TABLE t_sales_delivery (
            dlvry_no TEXT, sales_no TEXT, farm_cd TEXT
        );
        CREATE TABLE t_stock_master (
            farm_cd TEXT, wh_cd TEXT, item_cd TEXT, variety_cd TEXT,
            grade_cd TEXT, size_cd TEXT, weight REAL, harvest_year INTEGER,
            storage_dt TEXT, in_qty REAL DEFAULT 0, out_qty REAL DEFAULT 0,
            reserved_qty REAL DEFAULT 0, reg_id TEXT
        );
        CREATE TABLE t_stock_log (
            farm_cd TEXT, item_cd TEXT, variety_cd TEXT, harvest_year INTEGER,
            grade_cd TEXT, size_cd TEXT, weight REAL, io_type TEXT, qty REAL,
            remark TEXT, reg_id TEXT, reg_dt TEXT
        );
        CREATE TABLE t_cash_ledger (
            cash_id INTEGER PRIMARY KEY, farm_cd TEXT, ref_id TEXT, amt REAL
        );
        CREATE TABLE t_ledger (
            slip_no TEXT, farm_cd TEXT, ref_id TEXT, amt REAL
        );
        INSERT INTO m_customer (custm_id, farm_cd, custm_nm, mobile, use_yn)
        VALUES ('C001', 'OR001', '테스트고객', '010-0000-0000', 'Y');
        INSERT INTO m_common_code (farm_cd, code_cd, code_nm, parent_cd)
        VALUES
            ('OR001', 'ST010100', '예약접수', 'ST01'),
            ('OR001', 'ST010200', '주문확정', 'ST01'),
            ('OR001', 'ST010300', '배송준비', 'ST01'),
            ('OR001', 'ST010400', '배송완료', 'ST01'),
            ('OR001', 'ST010500', '취소', 'ST01'),
            ('OR001', 'FR010101', '신고배', 'FR010100'),
            ('OR001', 'GR010100', '특', 'GR01'),
            ('OR001', 'SZ010100', '15kg', 'SZ01'),
            ('OR001', 'LO010100', '방문수령', 'LO01'),
            ('OR001', 'LO010200', '택배', 'LO01');
    """


def _open_tmp() -> tuple[Path, sqlite3.Connection]:
    fd, name = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    path = Path(name)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.executescript(_schema_sql())
    conn.commit()
    return path, conn


def _sample_payload(*, qty: float = 100, pre_pay: float = 30000) -> OrderSaveInput:
    return OrderSaveInput(
        custm_id=CUST,
        order_dt=None,
        season_type_cd="SS010100",
        pre_pay_amt=pre_pay,
        rmk="재고0 선주문",
        lines=[
            OrderLineInput(
                variety_cd=VARIETY,
                weight=15,
                grade_cd="GR010100",
                size_cd="SZ010100",
                qty=qty,
                unit_price=25000,
                harvest_year=2026,
                warehouse_cd=WAREHOUSE_CD_DEFAULT,
                deliveries=[
                    OrderDeliveryInput(
                        delivery_tp_cd="LO010100",
                        qty=qty,
                        planned_dt=today_ops_iso(),
                        rcv_name="수령인",
                        rcv_tel="010-1111-2222",
                    )
                ],
            )
        ],
    )


def _counts(conn: sqlite3.Connection) -> dict[str, int]:
    cur = conn.cursor()
    out = {}
    for table in (
        "t_order_master",
        "t_order_detail",
        "t_order_delivery",
        "t_sales_master",
        "t_sales_detail",
        "t_sales_delivery",
        "t_stock_log",
        "t_cash_ledger",
        "t_ledger",
    ):
        out[table] = cur.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    out["hold"] = cur.execute(
        "SELECT COUNT(*) FROM t_stock_log WHERE io_type = 'HOLD'"
    ).fetchone()[0]
    out["reserved"] = cur.execute(
        "SELECT COALESCE(SUM(reserved_qty), 0) FROM t_stock_master"
    ).fetchone()[0]
    cur.close()
    return out


class OrderServiceStage2Test(unittest.TestCase):
    def setUp(self) -> None:
        self.path, self.conn = _open_tmp()
        self.svc = OrderService(self.conn)

    def tearDown(self) -> None:
        self.conn.close()
        self.path.unlink(missing_ok=True)

    def test_t_ord_01_stock_zero_saves_order_only(self) -> None:
        before = _counts(self.conn)
        self.assertEqual(before["t_stock_log"], 0)
        self.assertEqual(before["reserved"], 0)

        order_no = self.svc.create_order(FARM, _sample_payload(), user_id="TEST")
        self.assertTrue(order_no.startswith("ORD"))
        self.assertRegex(order_no, r"^ORD\d{8}-\d{3}$")

        after = _counts(self.conn)
        self.assertEqual(after["t_order_master"], 1)
        self.assertEqual(after["t_order_detail"], 1)
        self.assertEqual(after["t_order_delivery"], 1)
        self.assertEqual(after["t_sales_master"], 0)
        self.assertEqual(after["t_sales_detail"], 0)
        self.assertEqual(after["t_sales_delivery"], 0)
        self.assertEqual(after["hold"], 0)
        self.assertEqual(after["t_stock_log"], 0)
        self.assertEqual(after["reserved"], 0)
        self.assertEqual(after["t_cash_ledger"], 0)
        self.assertEqual(after["t_ledger"], 0)

        row = self.conn.execute(
            "SELECT status_cd, order_dt, sales_no, pre_pay_amt FROM t_order_master WHERE order_no = ?",
            (order_no,),
        ).fetchone()
        self.assertEqual(row["status_cd"], ORDER_STATUS_RESERVED_CD)
        self.assertEqual(row["order_dt"], today_ops_iso())
        self.assertEqual(str(row["sales_no"] or ""), "")
        self.assertEqual(float(row["pre_pay_amt"]), 30000)

        det = self.conn.execute(
            "SELECT item_cd, qty FROM t_order_detail WHERE order_no = ?",
            (order_no,),
        ).fetchone()
        self.assertEqual(det["item_cd"], item_cd_from_variety(VARIETY))
        self.assertEqual(float(det["qty"]), 100)

    def test_list_and_get_order(self) -> None:
        order_no = self.svc.create_order(FARM, _sample_payload(qty=2), user_id="TEST")
        listed = self.svc.list_orders(FARM)
        self.assertEqual(listed["total"], 1)
        self.assertEqual(listed["page"], 1)
        self.assertEqual(listed["page_size"], 20)
        self.assertEqual(len(listed["items"]), 1)
        self.assertEqual(listed["items"][0]["order_no"], order_no)
        self.assertEqual(listed["items"][0]["status_cd"], ORDER_STATUS_RESERVED_CD)
        self.assertEqual(listed["items"][0]["status_nm"], "예약접수")
        self.assertEqual(listed["items"][0]["customer"], "테스트고객")
        self.assertNotIn("allocated_qty", listed["items"][0])
        self.assertNotIn("fulfillment", listed["items"][0])

        detail = self.svc.get_order(FARM, order_no)
        self.assertEqual(detail["status_cd"], ORDER_STATUS_RESERVED_CD)
        self.assertEqual(len(detail["lines"]), 1)
        self.assertEqual(len(detail["lines"][0]["deliveries"]), 1)
        self.assertEqual(detail["order_dt"], today_ops_iso())
        self.assertEqual(detail["lines"][0]["variety_nm"], "신고배")
        self.assertEqual(detail["lines"][0]["grade_nm"], "특")
        self.assertEqual(detail["lines"][0]["dlvry_tp_nm"] or detail["lines"][0]["deliveries"][0]["delivery_tp_nm"], "방문수령")

    def test_replace_rejects_sales_linked_order(self) -> None:
        order_no = self.svc.create_order(FARM, _sample_payload(qty=1), user_id="TEST")
        self.conn.execute(
            "UPDATE t_order_master SET sales_no = ? WHERE order_no = ?",
            ("20260817-01", order_no),
        )
        self.conn.commit()
        with self.assertRaises(OrderHasSalesError):
            self.svc.replace_order(FARM, order_no, _sample_payload(qty=1), user_id="TEST")
        self.assertEqual(_counts(self.conn)["t_sales_master"], 0)
        self.assertEqual(_counts(self.conn)["hold"], 0)

    def test_seq_increments_same_day(self) -> None:
        a = self.svc.create_order(FARM, _sample_payload(qty=1), user_id="TEST")
        b = self.svc.create_order(FARM, _sample_payload(qty=1), user_id="TEST")
        self.assertNotEqual(a, b)
        self.assertTrue(b.endswith("-002"))
        ymd = today_ops().strftime("%Y%m%d")
        self.assertTrue(a.startswith(f"ORD{ymd}-"))

    def _parcel_line(self, qtys: list[float], *, line_qty: float | None = None) -> OrderLineInput:
        qty = float(sum(qtys) if line_qty is None else line_qty)
        dests = [
            OrderDeliveryInput(
                delivery_tp_cd="LO010200",
                qty=q,
                rcv_name=f"수령{i}",
                rcv_tel=f"010-0000-{i:04d}",
                rcv_addr=f"경기 하남시 {i}",
            )
            for i, q in enumerate(qtys, start=1)
        ]
        return OrderLineInput(
            variety_cd=VARIETY,
            weight=15,
            grade_cd="GR010100",
            size_cd="SZ010100",
            qty=qty,
            unit_price=25000,
            harvest_year=2026,
            warehouse_cd=WAREHOUSE_CD_DEFAULT,
            dlvry_tp="LO010200",
            deliveries=dests,
        )

    def test_parcel_split_3_2_5_saves_n_deliveries(self) -> None:
        payload = _sample_payload(qty=10)
        payload.lines = [self._parcel_line([3, 2, 5])]
        order_no = self.svc.create_order(FARM, payload, user_id="TEST")
        rows = self.conn.execute(
            """
            SELECT order_detail_id, dlvry_qty, rcv_name
            FROM t_order_delivery WHERE order_no = ? ORDER BY order_dlvry_id
            """,
            (order_no,),
        ).fetchall()
        self.assertEqual(len(rows), 3)
        self.assertEqual([float(r["dlvry_qty"]) for r in rows], [3.0, 2.0, 5.0])
        self.assertEqual(len({r["order_detail_id"] for r in rows}), 1)
        after = _counts(self.conn)
        self.assertEqual(after["t_sales_master"], 0)
        self.assertEqual(after["hold"], 0)
        self.assertEqual(after["t_ledger"], 0)

    def test_parcel_ten_singles(self) -> None:
        payload = _sample_payload(qty=10)
        payload.lines = [self._parcel_line([1] * 10)]
        order_no = self.svc.create_order(FARM, payload, user_id="TEST")
        n = self.conn.execute(
            "SELECT COUNT(*) FROM t_order_delivery WHERE order_no = ?",
            (order_no,),
        ).fetchone()[0]
        self.assertEqual(n, 10)

    def test_parcel_sum_mismatch_rejected(self) -> None:
        short = _sample_payload(qty=10)
        short.lines = [self._parcel_line([3, 2, 3], line_qty=10)]
        with self.assertRaises(OrderValidationError):
            self.svc.create_order(FARM, short, user_id="TEST")
        over = _sample_payload(qty=10)
        over.lines = [self._parcel_line([3, 2, 7], line_qty=10)]
        with self.assertRaises(OrderValidationError):
            self.svc.create_order(FARM, over, user_id="TEST")
        self.assertEqual(_counts(self.conn)["t_order_master"], 0)
        self.assertEqual(_counts(self.conn)["t_order_delivery"], 0)

    def test_two_lines_independent_deliveries(self) -> None:
        payload = _sample_payload(qty=10)
        payload.lines = [
            self._parcel_line([3, 7]),
            self._parcel_line([2, 3]),
        ]
        order_no = self.svc.create_order(FARM, payload, user_id="TEST")
        rows = self.conn.execute(
            """
            SELECT order_detail_id, COUNT(*) AS n, SUM(dlvry_qty) AS qty
            FROM t_order_delivery WHERE order_no = ?
            GROUP BY order_detail_id ORDER BY order_detail_id
            """,
            (order_no,),
        ).fetchall()
        self.assertEqual(len(rows), 2)
        self.assertEqual(int(rows[0]["n"]), 2)
        self.assertEqual(float(rows[0]["qty"]), 10.0)
        self.assertEqual(int(rows[1]["n"]), 2)
        self.assertEqual(float(rows[1]["qty"]), 5.0)
        self.assertNotEqual(rows[0]["order_detail_id"], rows[1]["order_detail_id"])
        self.assertEqual(_counts(self.conn)["t_sales_master"], 0)
        self.assertEqual(_counts(self.conn)["hold"], 0)


    def _set_status(self, order_no: str, status_cd: str) -> None:
        self.conn.execute(
            "UPDATE t_order_master SET status_cd = ? WHERE order_no = ?",
            (status_cd, order_no),
        )
        self.conn.commit()

    def test_replace_reserved_qty_and_no_sales_hold_ledger(self) -> None:
        order_no = self.svc.create_order(FARM, _sample_payload(qty=10), user_id="TEST")
        self.svc.replace_order(FARM, order_no, _sample_payload(qty=12), user_id="TEST")
        det = self.conn.execute(
            "SELECT qty FROM t_order_detail WHERE order_no = ?",
            (order_no,),
        ).fetchone()
        self.assertEqual(float(det["qty"]), 12)
        after = _counts(self.conn)
        self.assertEqual(after["t_order_master"], 1)
        self.assertEqual(after["t_order_detail"], 1)
        self.assertEqual(after["t_sales_master"], 0)
        self.assertEqual(after["hold"], 0)
        self.assertEqual(after["t_ledger"], 0)
        self.assertEqual(after["t_cash_ledger"], 0)

    def test_replace_add_and_remove_line(self) -> None:
        order_no = self.svc.create_order(FARM, _sample_payload(qty=2), user_id="TEST")
        added = _sample_payload(qty=2)
        added.lines = [
            added.lines[0],
            OrderLineInput(
                variety_cd=VARIETY,
                weight=15,
                grade_cd="GR010100",
                size_cd="SZ010100",
                qty=3,
                unit_price=25000,
                harvest_year=2026,
                warehouse_cd=WAREHOUSE_CD_DEFAULT,
                deliveries=[
                    OrderDeliveryInput(
                        delivery_tp_cd="LO010100",
                        qty=3,
                        rcv_name="수령2",
                        rcv_tel="010-2222-3333",
                    )
                ],
            ),
        ]
        self.svc.replace_order(FARM, order_no, added, user_id="TEST")
        n = self.conn.execute(
            "SELECT COUNT(*) FROM t_order_detail WHERE order_no = ?",
            (order_no,),
        ).fetchone()[0]
        self.assertEqual(n, 2)
        self.svc.replace_order(FARM, order_no, _sample_payload(qty=2), user_id="TEST")
        n = self.conn.execute(
            "SELECT COUNT(*) FROM t_order_detail WHERE order_no = ?",
            (order_no,),
        ).fetchone()[0]
        self.assertEqual(n, 1)
        self.assertEqual(_counts(self.conn)["t_sales_master"], 0)

    def test_replace_parcel_dests_and_mismatch(self) -> None:
        payload = _sample_payload(qty=10)
        payload.lines = [self._parcel_line([3, 2, 5])]
        order_no = self.svc.create_order(FARM, payload, user_id="TEST")
        changed = _sample_payload(qty=10)
        changed.lines = [self._parcel_line([4, 6])]
        self.svc.replace_order(FARM, order_no, changed, user_id="TEST")
        rows = self.conn.execute(
            "SELECT dlvry_qty FROM t_order_delivery WHERE order_no = ? ORDER BY order_dlvry_id",
            (order_no,),
        ).fetchall()
        self.assertEqual([float(r["dlvry_qty"]) for r in rows], [4.0, 6.0])
        short = _sample_payload(qty=10)
        short.lines = [self._parcel_line([3, 2, 3], line_qty=10)]
        with self.assertRaises(OrderValidationError):
            self.svc.replace_order(FARM, order_no, short, user_id="TEST")
        over = _sample_payload(qty=10)
        over.lines = [self._parcel_line([3, 2, 7], line_qty=10)]
        with self.assertRaises(OrderValidationError):
            self.svc.replace_order(FARM, order_no, over, user_id="TEST")
        kept = self.conn.execute(
            "SELECT COUNT(*) FROM t_order_delivery WHERE order_no = ?",
            (order_no,),
        ).fetchone()[0]
        self.assertEqual(kept, 2)

    def test_replace_rejects_delivered_and_cancel(self) -> None:
        order_no = self.svc.create_order(FARM, _sample_payload(qty=1), user_id="TEST")
        self._set_status(order_no, ORDER_STATUS_DELIVERED_CD)
        with self.assertRaises(OrderValidationError) as delivered:
            self.svc.replace_order(FARM, order_no, _sample_payload(qty=1), user_id="TEST")
        self.assertEqual(str(delivered.exception.message), MSG_ORDER_LOCKED_DELIVERED)
        self._set_status(order_no, ORDER_STATUS_CANCEL_CD)
        with self.assertRaises(OrderValidationError) as canceled:
            self.svc.replace_order(FARM, order_no, _sample_payload(qty=1), user_id="TEST")
        self.assertEqual(str(canceled.exception.message), MSG_ORDER_LOCKED_CANCEL)
        qty = self.conn.execute(
            "SELECT qty FROM t_order_detail WHERE order_no = ?",
            (order_no,),
        ).fetchone()["qty"]
        self.assertEqual(float(qty), 1)

    def test_replace_rejects_confirmed_qty_change(self) -> None:
        order_no = self.svc.create_order(FARM, _sample_payload(qty=2), user_id="TEST")
        self._set_status(order_no, ORDER_STATUS_CONFIRMED_CD)
        with self.assertRaises(OrderValidationError) as exc:
            self.svc.replace_order(FARM, order_no, _sample_payload(qty=5), user_id="TEST")
        self.assertEqual(str(exc.exception.message), MSG_ORDER_QTY_LOCKED)
        qty = self.conn.execute(
            "SELECT qty FROM t_order_detail WHERE order_no = ?",
            (order_no,),
        ).fetchone()["qty"]
        self.assertEqual(float(qty), 2)

    def test_cancel_reserved_and_confirmed_preserve_rows(self) -> None:
        reserved = self.svc.create_order(FARM, _sample_payload(qty=3), user_id="TEST")
        before = _counts(self.conn)
        self.svc.cancel_order(FARM, reserved, user_id="TEST")
        row = self.conn.execute(
            "SELECT status_cd FROM t_order_master WHERE order_no = ?",
            (reserved,),
        ).fetchone()
        self.assertEqual(row["status_cd"], ORDER_STATUS_CANCEL_CD)
        after = _counts(self.conn)
        self.assertEqual(after["t_order_master"], before["t_order_master"])
        self.assertEqual(after["t_order_detail"], before["t_order_detail"])
        self.assertEqual(after["t_order_delivery"], before["t_order_delivery"])
        self.assertEqual(after["t_sales_master"], 0)
        self.assertEqual(after["hold"], 0)
        self.assertEqual(after["t_stock_log"], 0)
        self.assertEqual(after["reserved"], 0)
        self.assertEqual(after["t_cash_ledger"], 0)
        self.assertEqual(after["t_ledger"], 0)
        detail = self.svc.get_order(FARM, reserved)
        self.assertEqual(detail["status_cd"], ORDER_STATUS_CANCEL_CD)
        self.assertEqual(detail["status_nm"], "취소")
        self.assertEqual(len(detail["lines"]), 1)
        self.assertEqual(len(detail["lines"][0]["deliveries"]), 1)

        confirmed = self.svc.create_order(FARM, _sample_payload(qty=2), user_id="TEST")
        self._set_status(confirmed, ORDER_STATUS_CONFIRMED_CD)
        self.svc.cancel_order(FARM, confirmed, user_id="TEST")
        st = self.conn.execute(
            "SELECT status_cd FROM t_order_master WHERE order_no = ?",
            (confirmed,),
        ).fetchone()["status_cd"]
        self.assertEqual(st, ORDER_STATUS_CANCEL_CD)

    def test_cancel_rejects_prep_delivered_and_already_canceled(self) -> None:
        order_no = self.svc.create_order(FARM, _sample_payload(qty=1), user_id="TEST")
        for status in (
            ORDER_STATUS_PREP_CD,
            ORDER_STATUS_DELIVERED_CD,
            ORDER_STATUS_CANCEL_CD,
        ):
            self._set_status(order_no, status)
            with self.assertRaises(OrderValidationError) as exc:
                self.svc.cancel_order(FARM, order_no, user_id="TEST")
            self.assertEqual(str(exc.exception.message), MSG_ORDER_CANCEL_FORBIDDEN)
        kept = self.conn.execute(
            "SELECT COUNT(*) FROM t_order_detail WHERE order_no = ?",
            (order_no,),
        ).fetchone()[0]
        self.assertEqual(kept, 1)

    def _put_master(
        self,
        order_no: str,
        order_dt: str,
        *,
        status_cd: str = ORDER_STATUS_RESERVED_CD,
        custm_id: str = CUST,
        amt: float = 1000,
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO t_order_master (
                order_no, farm_cd, order_dt, custm_id, status_cd, stock_status,
                tot_order_amt, tot_ship_fee, tot_pay_amt, pre_pay_amt, sales_no, rmk
            ) VALUES (?, ?, ?, ?, ?, 'N', ?, 0, ?, 0, '', '')
            """,
            (order_no, FARM, order_dt, custm_id, status_cd, amt, amt),
        )
        self.conn.commit()

    def test_list_orders_filters_paging_and_legacy_dates(self) -> None:
        self.conn.execute(
            """
            INSERT INTO m_customer (custm_id, farm_cd, custm_nm, mobile, use_yn)
            VALUES ('C002', 'OR001', '박상희', '010-2222-3333', 'Y')
            """
        )
        self.conn.commit()
        self._put_master("ORD20251231-001", "2025-12-31")
        self._put_master("ORD20260115-001", "20260115", custm_id="C002")
        self._put_master("ORD20260301-001", "2026-03-01", status_cd=ORDER_STATUS_CONFIRMED_CD)
        self._put_master("ORD20260801-001", "2026-08-01")
        self._put_master("ORD20260801-002", "2026-08-01", status_cd=ORDER_STATUS_CANCEL_CD)

        year = self.svc.list_orders(FARM)
        self.assertEqual(year["total"], 4)
        nos = [r["order_no"] for r in year["items"]]
        self.assertNotIn("ORD20251231-001", nos)
        self.assertEqual(nos[0], "ORD20260801-002")
        self.assertEqual(nos[1], "ORD20260801-001")
        self.assertEqual(year["items"][2]["order_dt"], "2026-03-01")
        self.assertEqual(year["items"][3]["order_dt"], "2026-01-15")

        period = self.svc.list_orders(
            FARM, from_date="2026-01-01", to_date="2026-01-31"
        )
        self.assertEqual(period["total"], 1)
        self.assertEqual(period["items"][0]["order_no"], "ORD20260115-001")

        by_status = self.svc.list_orders(
            FARM, status_cd=ORDER_STATUS_CONFIRMED_CD
        )
        self.assertEqual(by_status["total"], 1)
        self.assertEqual(by_status["items"][0]["order_no"], "ORD20260301-001")

        by_name = self.svc.list_orders(FARM, keyword="박상희")
        self.assertEqual(by_name["total"], 1)
        self.assertEqual(by_name["items"][0]["customer"], "박상희")

        by_no = self.svc.list_orders(FARM, keyword="ORD20260801-001")
        self.assertEqual(by_no["total"], 1)
        self.assertEqual(by_no["items"][0]["order_no"], "ORD20260801-001")

        combo = self.svc.list_orders(
            FARM,
            from_date="2026-08-01",
            to_date="2026-08-31",
            status_cd=ORDER_STATUS_RESERVED_CD,
            keyword="ORD20260801",
        )
        self.assertEqual(combo["total"], 1)
        self.assertEqual(combo["items"][0]["order_no"], "ORD20260801-001")

        empty = self.svc.list_orders(
            FARM, from_date="2024-01-01", to_date="2024-12-31"
        )
        self.assertEqual(empty["total"], 0)
        self.assertEqual(empty["items"], [])

        page1 = self.svc.list_orders(FARM, page=1, page_size=2)
        self.assertEqual(page1["total"], 4)
        self.assertEqual(page1["page"], 1)
        self.assertEqual(page1["page_size"], 2)
        self.assertEqual(len(page1["items"]), 2)
        page2 = self.svc.list_orders(FARM, page=2, page_size=2)
        self.assertEqual(len(page2["items"]), 2)
        self.assertEqual(page2["items"][0]["order_no"], "ORD20260301-001")
        after_filter = self.svc.list_orders(
            FARM, status_cd=ORDER_STATUS_CANCEL_CD, page=3, page_size=20
        )
        self.assertEqual(after_filter["page"], 3)
        self.assertEqual(after_filter["total"], 1)
        self.assertEqual(after_filter["items"], [])

        sized = self.svc.list_orders(FARM, page_size=20)
        self.assertEqual(sized["page_size"], 20)
        self.assertEqual(len(sized["items"]), 4)

        before = _counts(self.conn)
        self.assertEqual(before["t_sales_master"], 0)
        self.assertEqual(before["hold"], 0)
        self.assertEqual(before["t_ledger"], 0)


if __name__ == "__main__":
    unittest.main()
