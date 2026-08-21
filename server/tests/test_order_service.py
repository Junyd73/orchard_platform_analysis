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
from core.order_ship_constants import SALES_STATUS_CONFIRMED  # noqa: E402


FARM = "OR001"
CUST = "C001"
VARIETY = "FR010101"
VARIETY_2 = "FR010102"
GRADE = "GR010100"
GRADE_2 = "GR010200"
SPEC = "SZ010100"
SPEC_2 = "SZ010200"
DLVRY_VISIT = "LO010100"
DLVRY_PARCEL = "LO010200"
SALES_STATUS_DRAFT = "DRAFT"


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
            sales_no TEXT, farm_cd TEXT, order_no TEXT, sales_status TEXT
        );
        CREATE TABLE t_sales_detail (
            sale_detail_no TEXT, sales_no TEXT, farm_cd TEXT, order_detail_id TEXT,
            qty REAL DEFAULT 0
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
            ('OR001', 'FR010102', '원황배', 'FR010100'),
            ('OR001', 'GR010100', '특', 'GR01'),
            ('OR001', 'GR010200', '상', 'GR01'),
            ('OR001', 'SZ010100', '15kg', 'SZ01'),
            ('OR001', 'SZ010200', '7.5kg', 'SZ01'),
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
        self.assertAlmostEqual(float(detail["lines"][0]["confirmed_shipped_qty"]), 0)
        self.assertAlmostEqual(float(detail["lines"][0]["remaining_order_qty"]), 2)

    def test_a6_get_order_unshipped_remaining_equals_qty(self) -> None:
        order_no = self.svc.create_order(FARM, _sample_payload(qty=10), user_id="TEST")
        detail = self.svc.get_order(FARM, order_no)
        line = detail["lines"][0]
        self.assertAlmostEqual(float(line["confirmed_shipped_qty"]), 0)
        self.assertAlmostEqual(float(line["remaining_order_qty"]), 10)

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
        order_no = self.svc.create_order(FARM, short, user_id="TEST")
        n = self.conn.execute(
            "SELECT COUNT(*) FROM t_order_delivery WHERE order_no = ?",
            (order_no,),
        ).fetchone()[0]
        self.assertEqual(n, 3)
        empty = _sample_payload(qty=10)
        empty.lines = [self._parcel_line([], line_qty=10)]
        empty_no = self.svc.create_order(FARM, empty, user_id="TEST")
        n0 = self.conn.execute(
            "SELECT COUNT(*) FROM t_order_delivery WHERE order_no = ?",
            (empty_no,),
        ).fetchone()[0]
        self.assertEqual(n0, 0)
        over = _sample_payload(qty=10)
        over.lines = [self._parcel_line([3, 2, 7], line_qty=10)]
        with self.assertRaises(OrderValidationError):
            self.svc.create_order(FARM, over, user_id="TEST")
        incomplete = _sample_payload(qty=10)
        incomplete.lines = [
            OrderLineInput(
                variety_cd=VARIETY,
                weight=15,
                grade_cd="GR010100",
                size_cd="SZ010100",
                qty=10,
                unit_price=25000,
                harvest_year=2026,
                warehouse_cd=WAREHOUSE_CD_DEFAULT,
                dlvry_tp="LO010200",
                deliveries=[
                    OrderDeliveryInput(
                        delivery_tp_cd="LO010200",
                        qty=5,
                        rcv_name="",
                        rcv_tel="010",
                        rcv_addr="addr",
                    )
                ],
            )
        ]
        with self.assertRaises(OrderValidationError):
            self.svc.create_order(FARM, incomplete, user_id="TEST")

    def test_confirm_order_reserved_only(self) -> None:
        order_no = self.svc.create_order(FARM, _sample_payload(qty=2), user_id="TEST")
        before = _counts(self.conn)
        self.svc.confirm_order(FARM, order_no, user_id="TEST")
        detail = self.svc.get_order(FARM, order_no)
        self.assertEqual(detail["status_cd"], ORDER_STATUS_CONFIRMED_CD)
        self.assertEqual(_counts(self.conn), before)
        with self.assertRaises(OrderValidationError) as ctx:
            self.svc.confirm_order(FARM, order_no, user_id="TEST")
        self.assertEqual(ctx.exception.code, "ORDER_CONFIRM_FORBIDDEN")
        self._set_status(order_no, ORDER_STATUS_DELIVERED_CD)
        with self.assertRaises(OrderValidationError):
            self.svc.confirm_order(FARM, order_no, user_id="TEST")
        self._set_status(order_no, ORDER_STATUS_CANCEL_CD)
        with self.assertRaises(OrderValidationError):
            self.svc.confirm_order(FARM, order_no, user_id="TEST")
        self.assertEqual(_counts(self.conn)["t_sales_master"], 0)
        self.assertEqual(_counts(self.conn)["hold"], 0)

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
        self.svc.replace_order(FARM, order_no, short, user_id="TEST")
        rows2 = self.conn.execute(
            "SELECT dlvry_qty FROM t_order_delivery WHERE order_no = ? ORDER BY order_dlvry_id",
            (order_no,),
        ).fetchall()
        self.assertEqual([float(r["dlvry_qty"]) for r in rows2], [3.0, 2.0, 3.0])
        over = _sample_payload(qty=10)
        over.lines = [self._parcel_line([3, 2, 7], line_qty=10)]
        with self.assertRaises(OrderValidationError):
            self.svc.replace_order(FARM, order_no, over, user_id="TEST")
        kept = self.conn.execute(
            "SELECT COUNT(*) FROM t_order_delivery WHERE order_no = ?",
            (order_no,),
        ).fetchone()[0]
        self.assertEqual(kept, 3)

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


class OrderListCompactTest(unittest.TestCase):
    """목록 2줄 compact — 대표상품·배송유형·출고/잔여 bulk 집계."""

    def setUp(self) -> None:
        self.path, self.conn = _open_tmp()
        self.svc = OrderService(self.conn)

    def tearDown(self) -> None:
        self.conn.close()
        self.path.unlink(missing_ok=True)

    def _line(
        self,
        *,
        qty: float,
        variety_cd: str = VARIETY,
        grade_cd: str = GRADE,
        size_cd: str = SPEC,
        weight: float = 15,
        dlvry_tp: str = DLVRY_VISIT,
    ) -> OrderLineInput:
        parcel = dlvry_tp == DLVRY_PARCEL
        return OrderLineInput(
            variety_cd=variety_cd,
            weight=weight,
            grade_cd=grade_cd,
            size_cd=size_cd,
            qty=qty,
            unit_price=25000,
            harvest_year=2026,
            warehouse_cd=WAREHOUSE_CD_DEFAULT,
            dlvry_tp=dlvry_tp,
            deliveries=[
                OrderDeliveryInput(
                    delivery_tp_cd=dlvry_tp,
                    qty=qty,
                    rcv_name="수령인",
                    rcv_tel="010-1111-2222",
                    rcv_addr="경기 하남시 1" if parcel else "",
                )
            ],
        )

    def _create(self, lines: list[OrderLineInput]) -> str:
        payload = _sample_payload(qty=1, pre_pay=0)
        payload.lines = lines
        return self.svc.create_order(FARM, payload, user_id="TEST")

    def _first_item(self, order_no: str) -> dict:
        listed = self.svc.list_orders(FARM, keyword=order_no)
        self.assertEqual(listed["total"], 1)
        return listed["items"][0]

    def _add_sale(
        self,
        order_no: str,
        *,
        seq: int,
        detail_seq: int = 1,
        qty: float,
        sales_status: str = SALES_STATUS_CONFIRMED,
    ) -> None:
        """주문에 연결된 판매 1건을 직접 넣는다 (출고 서비스 비의존)."""
        sales_no = f"{order_no}-S{seq:02d}"
        self.conn.execute(
            "INSERT INTO t_sales_master (sales_no, farm_cd, order_no, sales_status)"
            " VALUES (?, ?, ?, ?)",
            (sales_no, FARM, order_no, sales_status),
        )
        self.conn.execute(
            "INSERT INTO t_sales_detail (sale_detail_no, sales_no, farm_cd,"
            " order_detail_id, qty) VALUES (?, ?, ?, ?, ?)",
            (f"{sales_no}-01", sales_no, FARM, f"{order_no}-{detail_seq:02d}", qty),
        )
        self.conn.commit()

    def test_single_line_representative_fields(self) -> None:
        order_no = self._create([self._line(qty=30)])
        item = self._first_item(order_no)
        self.assertEqual(item["line_count"], 1)
        self.assertEqual(item["rep_item_cd"], item_cd_from_variety(VARIETY))
        self.assertEqual(item["rep_variety_cd"], VARIETY)
        self.assertEqual(item["rep_variety_nm"], "신고배")
        self.assertEqual(item["rep_grade_cd"], GRADE)
        self.assertEqual(item["rep_grade_nm"], "특")
        self.assertEqual(item["rep_size_cd"], SPEC)
        self.assertEqual(item["rep_size_nm"], "15kg")
        self.assertAlmostEqual(float(item["rep_weight"]), 15)
        self.assertAlmostEqual(float(item["total_qty"]), 30)

    def test_multi_line_rep_is_first_detail_and_outer_fields(self) -> None:
        order_no = self._create(
            [
                self._line(qty=10),
                self._line(qty=7, variety_cd=VARIETY_2, grade_cd=GRADE_2),
                self._line(qty=3, size_cd=SPEC_2, weight=7.5),
            ]
        )
        item = self._first_item(order_no)
        self.assertEqual(item["line_count"], 3)
        # 대표는 order_detail_id 최소값(-01) 이며 나머지 라인 규격이 섞이지 않는다
        first = self.conn.execute(
            "SELECT order_detail_id, variety_cd, grade_cd, size_cd, weight"
            " FROM t_order_detail WHERE order_no = ? ORDER BY order_detail_id",
            (order_no,),
        ).fetchall()[0]
        self.assertEqual(first["order_detail_id"], f"{order_no}-01")
        self.assertEqual(item["rep_variety_cd"], first["variety_cd"])
        self.assertEqual(item["rep_grade_cd"], first["grade_cd"])
        self.assertEqual(item["rep_size_cd"], first["size_cd"])
        self.assertAlmostEqual(float(item["rep_weight"]), float(first["weight"]))
        self.assertEqual(item["rep_variety_nm"], "신고배")
        self.assertEqual(item["rep_grade_nm"], "특")
        # outer(주문 단위) 필드는 라인 합계/주문 상태를 따른다
        self.assertAlmostEqual(float(item["total_qty"]), 20)
        self.assertEqual(item["order_no"], order_no)
        self.assertEqual(item["customer"], "테스트고객")
        self.assertEqual(item["status_cd"], ORDER_STATUS_RESERVED_CD)
        self.assertAlmostEqual(float(item["remaining_order_qty"]), 20)

    def test_single_delivery_tp_count_is_one(self) -> None:
        order_no = self._create([self._line(qty=5), self._line(qty=5)])
        item = self._first_item(order_no)
        self.assertEqual(item["delivery_tp_count"], 1)
        self.assertEqual(item["delivery_tp_cd"], DLVRY_VISIT)
        self.assertEqual(item["delivery_tp_nm"], "방문수령")

    def test_mixed_delivery_tp_count_over_one_hides_single_name(self) -> None:
        order_no = self._create(
            [self._line(qty=5), self._line(qty=5, dlvry_tp=DLVRY_PARCEL)]
        )
        item = self._first_item(order_no)
        self.assertEqual(item["delivery_tp_count"], 2)
        self.assertEqual(item["delivery_tp_cd"], "")
        self.assertEqual(item["delivery_tp_nm"], "")

    def test_unshipped_30_has_zero_shipped_and_full_remaining(self) -> None:
        order_no = self._create([self._line(qty=30)])
        item = self._first_item(order_no)
        self.assertAlmostEqual(float(item["confirmed_shipped_qty"]), 0)
        self.assertAlmostEqual(float(item["remaining_order_qty"]), 30)

    def test_partial_ship_10_of_30(self) -> None:
        order_no = self._create([self._line(qty=30)])
        self._add_sale(order_no, seq=1, qty=10)
        item = self._first_item(order_no)
        self.assertAlmostEqual(float(item["confirmed_shipped_qty"]), 10)
        self.assertAlmostEqual(float(item["remaining_order_qty"]), 20)

    def test_complete_ship_30_of_30(self) -> None:
        order_no = self._create([self._line(qty=30)])
        self._add_sale(order_no, seq=1, qty=10)
        self._add_sale(order_no, seq=2, qty=20)
        item = self._first_item(order_no)
        self.assertAlmostEqual(float(item["confirmed_shipped_qty"]), 30)
        self.assertAlmostEqual(float(item["remaining_order_qty"]), 0)

    def test_non_confirmed_sales_excluded_from_shipped(self) -> None:
        order_no = self._create([self._line(qty=30)])
        self._add_sale(order_no, seq=1, qty=10)
        self._add_sale(order_no, seq=2, qty=20, sales_status=SALES_STATUS_DRAFT)
        item = self._first_item(order_no)
        self.assertAlmostEqual(float(item["confirmed_shipped_qty"]), 10)
        self.assertAlmostEqual(float(item["remaining_order_qty"]), 20)

    def test_bulk_enrich_keeps_each_order_isolated(self) -> None:
        visit = self._create([self._line(qty=30)])
        mixed = self._create(
            [self._line(qty=4, dlvry_tp=DLVRY_PARCEL), self._line(qty=6)]
        )
        self._add_sale(visit, seq=1, qty=30)
        listed = self.svc.list_orders(FARM)
        by_no = {r["order_no"]: r for r in listed["items"]}
        self.assertEqual(listed["total"], 2)
        self.assertAlmostEqual(float(by_no[visit]["remaining_order_qty"]), 0)
        self.assertEqual(by_no[visit]["delivery_tp_count"], 1)
        self.assertAlmostEqual(float(by_no[mixed]["confirmed_shipped_qty"]), 0)
        self.assertAlmostEqual(float(by_no[mixed]["remaining_order_qty"]), 10)
        self.assertEqual(by_no[mixed]["delivery_tp_count"], 2)


if __name__ == "__main__":
    unittest.main()
