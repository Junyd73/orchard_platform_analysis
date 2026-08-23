# -*- coding: utf-8 -*-
"""Stage7A — DEC-031 출고확정 CONFIRMED 판매 read-only."""

from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

_HERE = Path(__file__).resolve()
_SERVER = _HERE.parents[1]
_ROOT = _HERE.parents[2]
for p in (_SERVER, _ROOT):
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)

from core.order_ship_constants import SALES_STATUS_CONFIRMED  # noqa: E402
from core.pc_sales_provenance import (  # noqa: E402
    MSG_SHIPMENT_CONFIRMED_SALE_DELETE_BLOCKED,
    MSG_SHIPMENT_CONFIRMED_SALE_SAVE_BLOCKED,
    PcShipmentConfirmedSaleLockedError,
    apply_protected_confirmed_sale_ui_lock,
    assert_sale_mutable,
    fetch_sale_lock_from_db,
    is_protected_delivery_edit_blocked,
    is_shipment_confirmed_sale_locked,
)

FARM = "OR001"
SALES_NO = "20260823-01"
ORDER_NO = "ORD20260823-001"
ORDER_DETAIL_ID = "ORD20260823-001-01"
STOCK_SEQ = 42


def _schema() -> str:
    return """
        CREATE TABLE t_sales_master (
            sales_no TEXT, farm_cd TEXT, sales_dt TEXT,
            tot_sales_amt REAL, tot_paid_amt REAL, tot_unpaid_amt REAL,
            order_no TEXT, sales_status TEXT, sales_source TEXT,
            rmk TEXT, reg_id TEXT,
            PRIMARY KEY (sales_no, farm_cd)
        );
        CREATE TABLE t_sales_detail (
            sale_detail_no TEXT PRIMARY KEY,
            sales_no TEXT NOT NULL, farm_cd TEXT NOT NULL,
            order_detail_id TEXT, stock_seq INTEGER,
            item_cd TEXT, qty REAL
        );
        CREATE TABLE t_sales_delivery (
            dlvry_no TEXT PRIMARY KEY, sales_no TEXT, farm_cd TEXT
        );
        CREATE TABLE t_cash_ledger (
            paid_detail_no TEXT PRIMARY KEY, sales_no TEXT, farm_cd TEXT,
            pay_dt TEXT, pay_method_cd TEXT, pay_amt REAL, order_no TEXT
        );
        CREATE TABLE t_ledger (
            slip_no TEXT PRIMARY KEY, farm_cd TEXT, trans_amt REAL, trans_st TEXT
        );
    """


def _insert_master(
    conn: sqlite3.Connection,
    *,
    sales_status: str = SALES_STATUS_CONFIRMED,
    order_no: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO t_sales_master(
            sales_no, farm_cd, sales_dt, tot_sales_amt, tot_paid_amt, tot_unpaid_amt,
            order_no, sales_status, sales_source, reg_id
        ) VALUES (?,?,?,100000,0,100000,?,?,?,?)
        """,
        (SALES_NO, FARM, "2026-08-23", order_no, sales_status, "ORDER", "T"),
    )


def _insert_detail(
    conn: sqlite3.Connection,
    *,
    order_detail_id: str | None = None,
    stock_seq: int | None = None,
    sale_detail_no: str = f"{SALES_NO}-S01",
) -> None:
    conn.execute(
        """
        INSERT INTO t_sales_detail(
            sale_detail_no, sales_no, farm_cd, order_detail_id, stock_seq, item_cd, qty
        ) VALUES (?,?,?,?,?,?,?)
        """,
        (
            sale_detail_no,
            SALES_NO,
            FARM,
            order_detail_id,
            stock_seq,
            "FR010100",
            10,
        ),
    )


class Stage7aSaleLockHelperTests(unittest.TestCase):
    def test_confirmed_order_no_locked(self) -> None:
        self.assertTrue(
            is_shipment_confirmed_sale_locked(
                SALES_STATUS_CONFIRMED, ORDER_NO, []
            )
        )

    def test_confirmed_order_detail_id_only_locked(self) -> None:
        self.assertTrue(
            is_shipment_confirmed_sale_locked(
                SALES_STATUS_CONFIRMED,
                None,
                [{"order_detail_id": ORDER_DETAIL_ID, "stock_seq": None}],
            )
        )

    def test_confirmed_stock_seq_only_locked(self) -> None:
        self.assertTrue(
            is_shipment_confirmed_sale_locked(
                SALES_STATUS_CONFIRMED,
                None,
                [{"order_detail_id": None, "stock_seq": STOCK_SEQ}],
            )
        )

    def test_confirmed_direct_sale_unlocked(self) -> None:
        self.assertFalse(
            is_shipment_confirmed_sale_locked(
                SALES_STATUS_CONFIRMED,
                None,
                [{"order_detail_id": None, "stock_seq": None}],
            )
        )

    def test_draft_with_order_no_unlocked(self) -> None:
        self.assertFalse(
            is_shipment_confirmed_sale_locked(
                "DRAFT",
                ORDER_NO,
                [{"order_detail_id": ORDER_DETAIL_ID, "stock_seq": STOCK_SEQ}],
            )
        )

    def test_blank_linkage_unlocked(self) -> None:
        self.assertFalse(
            is_shipment_confirmed_sale_locked(
                SALES_STATUS_CONFIRMED,
                "   ",
                [{"order_detail_id": "", "stock_seq": 0}],
            )
        )

    def test_direct_stock_seq_only_locked(self) -> None:
        self.assertTrue(
            is_shipment_confirmed_sale_locked(
                SALES_STATUS_CONFIRMED,
                None,
                [{"order_detail_id": "", "stock_seq": STOCK_SEQ}],
            )
        )


class Stage7aSaleLockBackstopTests(unittest.TestCase):
    def setUp(self) -> None:
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(_schema())
        self.conn.commit()

    def tearDown(self) -> None:
        self.conn.close()
        try:
            os.unlink(self.path)
        except OSError:
            pass

    def _snapshot(self) -> dict:
        return {
            "master": len(self.conn.execute("SELECT * FROM t_sales_master").fetchall()),
            "detail": len(self.conn.execute("SELECT * FROM t_sales_detail").fetchall()),
            "delivery": len(self.conn.execute("SELECT * FROM t_sales_delivery").fetchall()),
            "cash": len(self.conn.execute("SELECT * FROM t_cash_ledger").fetchall()),
            "ledger": len(self.conn.execute("SELECT * FROM t_ledger").fetchall()),
        }

    def _seed_protected(self) -> None:
        _insert_master(self.conn, order_no=ORDER_NO)
        _insert_detail(self.conn)
        self.conn.commit()

    def test_fetch_from_db_order_no(self) -> None:
        _insert_master(self.conn, order_no=ORDER_NO)
        self.conn.commit()
        self.assertTrue(fetch_sale_lock_from_db(self.conn.cursor(), FARM, SALES_NO))

    def test_protected_save_blocked_no_db_change(self) -> None:
        self._seed_protected()
        before = self._snapshot()
        with self.assertRaises(PcShipmentConfirmedSaleLockedError) as ctx:
            assert_sale_mutable(self.conn.cursor(), FARM, SALES_NO, action="save")
        self.assertIn(MSG_SHIPMENT_CONFIRMED_SALE_SAVE_BLOCKED, str(ctx.exception))
        self.assertEqual(self._snapshot(), before)

    def test_protected_delete_blocked_no_db_change(self) -> None:
        self._seed_protected()
        before = self._snapshot()
        with self.assertRaises(PcShipmentConfirmedSaleLockedError) as ctx:
            assert_sale_mutable(self.conn.cursor(), FARM, SALES_NO, action="delete")
        self.assertIn(MSG_SHIPMENT_CONFIRMED_SALE_DELETE_BLOCKED, str(ctx.exception))
        self.assertEqual(self._snapshot(), before)

    def test_protected_delete_zero_rows(self) -> None:
        self._seed_protected()
        before = self._snapshot()
        try:
            assert_sale_mutable(self.conn.cursor(), FARM, SALES_NO, action="delete")
        except PcShipmentConfirmedSaleLockedError:
            pass
        after = self._snapshot()
        self.assertEqual(before["delivery"], after["delivery"])
        self.assertEqual(before["cash"], after["cash"])
        self.assertEqual(before["detail"], after["detail"])
        self.assertEqual(before["master"], after["master"])
        self.assertEqual(before["ledger"], after["ledger"])

    def test_protected_save_zero_insert(self) -> None:
        self._seed_protected()
        master_before = self.conn.execute("SELECT * FROM t_sales_master").fetchall()
        with self.assertRaises(PcShipmentConfirmedSaleLockedError):
            assert_sale_mutable(self.conn.cursor(), FARM, SALES_NO, action="save")
        master_after = self.conn.execute("SELECT * FROM t_sales_master").fetchall()
        self.assertEqual(len(master_before), len(master_after))

    def test_new_sales_no_not_blocked(self) -> None:
        assert_sale_mutable(self.conn.cursor(), FARM, "20260823-99", action="save")

    def test_ordinary_confirmed_mutable(self) -> None:
        _insert_master(self.conn, order_no=None)
        _insert_detail(self.conn, order_detail_id=None, stock_seq=None)
        self.conn.commit()
        assert_sale_mutable(self.conn.cursor(), FARM, SALES_NO, action="save")
        assert_sale_mutable(self.conn.cursor(), FARM, SALES_NO, action="delete")

    def test_draft_save_not_blocked(self) -> None:
        _insert_master(self.conn, sales_status="DRAFT", order_no=ORDER_NO)
        _insert_detail(self.conn, order_detail_id=ORDER_DETAIL_ID, stock_seq=STOCK_SEQ)
        self.conn.commit()
        assert_sale_mutable(self.conn.cursor(), FARM, SALES_NO, action="save")


class Stage7aSaleLockUiTests(unittest.TestCase):
    def _make_page_stub(self) -> SimpleNamespace:
        class Toggle:
            def __init__(self) -> None:
                self.enabled = True
                self.read_only = False

            def setEnabled(self, value: bool) -> None:
                self.enabled = value

            def setReadOnly(self, value: bool) -> None:
                self.read_only = value

        class Table:
            def __init__(self, rows: list[list[Toggle]]) -> None:
                self._rows = rows

            def rowCount(self) -> int:
                return len(self._rows)

            def cellWidget(self, row: int, col: int):
                return self._rows[row][col]

        class Hint:
            def __init__(self) -> None:
                self.text = ""
                self.visible = False

            def setText(self, value: str) -> None:
                self.text = value

            def setVisible(self, value: bool) -> None:
                self.visible = value

        item_cells = [[Toggle() for _ in range(13)]]
        pay_cells = [[Toggle() for _ in range(5)]]
        page = SimpleNamespace(
            is_protected_confirmed_sale=False,
            lbl_protected_sale_hint=Hint(),
            sales_dt=Toggle(),
            custm_nm=Toggle(),
            sales_tp=Toggle(),
            rmk=Toggle(),
            bill_no=Toggle(),
            pay_method_cd=Toggle(),
            receipt_yn=Toggle(),
            receipt_dt=Toggle(),
            auction_fee=Toggle(),
            extra_cost=Toggle(),
            btn_save=Toggle(),
            btn_delete=Toggle(),
            btn_item_add=Toggle(),
            btn_cust_search=Toggle(),
            btn_manual_reg=Toggle(),
            btn_history=Toggle(),
            btn_select_all=Toggle(),
            btn_del_row=Toggle(),
            btn_form_down=Toggle(),
            btn_excel_upload=Toggle(),
            btn_excel_down=Toggle(),
            btn_pay_add=Toggle(),
            btn_pay_edit=Toggle(),
            btn_pay_del=Toggle(),
            item_table=Table(item_cells),
            pay_table=Table(pay_cells),
            active_row=-1,
            handle_delivery_tp_change=lambda _r: None,
        )
        return page

    def test_protected_ui_disables_save_delete(self) -> None:
        page = self._make_page_stub()
        apply_protected_confirmed_sale_ui_lock(page, True)
        self.assertTrue(page.is_protected_confirmed_sale)
        self.assertFalse(page.btn_save.enabled)
        self.assertFalse(page.btn_delete.enabled)

    def test_protected_item_inputs_disabled(self) -> None:
        page = self._make_page_stub()
        apply_protected_confirmed_sale_ui_lock(page, True)
        qty = page.item_table.cellWidget(0, 6)
        price = page.item_table.cellWidget(0, 7)
        delete_btn = page.item_table.cellWidget(0, 12)
        self.assertFalse(qty.enabled)
        self.assertTrue(qty.read_only)
        self.assertFalse(price.enabled)
        self.assertFalse(delete_btn.enabled)

    def test_protected_payment_buttons_disabled(self) -> None:
        page = self._make_page_stub()
        apply_protected_confirmed_sale_ui_lock(page, True)
        self.assertFalse(page.btn_pay_add.enabled)
        self.assertFalse(page.btn_pay_edit.enabled)
        self.assertFalse(page.btn_pay_del.enabled)
        pay_amt = page.pay_table.cellWidget(0, 3)
        self.assertFalse(pay_amt.enabled)

    def test_clear_unlocks_ui(self) -> None:
        page = self._make_page_stub()
        apply_protected_confirmed_sale_ui_lock(page, True)
        apply_protected_confirmed_sale_ui_lock(page, False)
        self.assertFalse(page.is_protected_confirmed_sale)
        self.assertTrue(page.btn_save.enabled)
        self.assertTrue(page.btn_item_add.enabled)
        self.assertTrue(page.btn_pay_add.enabled)

    def test_ordinary_unlocked_ui(self) -> None:
        page = self._make_page_stub()
        apply_protected_confirmed_sale_ui_lock(page, False)
        self.assertTrue(page.btn_save.enabled)
        self.assertTrue(page.btn_delete.enabled)


def _simulate_dlvry_double_click(
    *,
    is_protected: bool,
    delivery_map: dict,
    active_row: int,
    row: int,
) -> tuple[bool, dict]:
    """SalesPage.on_dlvry_table_double_clicked guard + mutation stub."""
    if is_protected_delivery_edit_blocked(is_protected):
        return False, delivery_map
    deliveries = delivery_map.get(active_row, [])
    if not deliveries or row >= len(deliveries):
        return False, delivery_map
    updated = dict(deliveries[row])
    updated["rcv_name"] = "CHANGED"
    delivery_map[active_row][row] = updated
    return True, delivery_map


class Stage7aDeliveryBypassTests(unittest.TestCase):
    def test_protected_dlvry_double_click_no_dialog_no_map_change(self) -> None:
        delivery_map = {0: [{"rcv_name": "ORIGINAL", "delivery_qty": 1}]}
        original = {0: [{"rcv_name": "ORIGINAL", "delivery_qty": 1}]}
        opened, result = _simulate_dlvry_double_click(
            is_protected=True,
            delivery_map=delivery_map,
            active_row=0,
            row=0,
        )
        self.assertFalse(opened)
        self.assertEqual(result, original)

    def test_ordinary_direct_sale_dlvry_double_click_mutates(self) -> None:
        delivery_map = {0: [{"rcv_name": "ORIGINAL", "delivery_qty": 1}]}
        opened, result = _simulate_dlvry_double_click(
            is_protected=False,
            delivery_map=delivery_map,
            active_row=0,
            row=0,
        )
        self.assertTrue(opened)
        self.assertEqual(result[0][0]["rcv_name"], "CHANGED")

    def test_protected_delivery_edit_blocked_helper(self) -> None:
        self.assertTrue(is_protected_delivery_edit_blocked(True))
        self.assertFalse(is_protected_delivery_edit_blocked(False))


if __name__ == "__main__":
    unittest.main()
