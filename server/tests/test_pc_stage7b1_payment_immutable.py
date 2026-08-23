# -*- coding: utf-8 -*-
"""Stage7B-1 — DEC-032/033/034 PC 수금 immutable + 판매 full-save cash/ledger 제거."""

from __future__ import annotations

import inspect
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
from core.sales_payment_constants import SALES_STATUS_DRAFT  # noqa: E402
from core.pc_sales_provenance import (  # noqa: E402
    MSG_SALES_AMT_BELOW_PAID,
    MSG_SALES_DELETE_HAS_PAYMENTS,
    PcSalesAmtBelowPaidError,
    PcSalesDeleteHasPaymentsError,
    PcShipmentConfirmedSaleLockedError,
    apply_payment_immutable_ui_lock,
    apply_protected_confirmed_sale_ui_lock,
    assert_no_cash_for_delete,
    assert_sale_mutable,
    assert_sales_total_not_below_paid,
    compute_master_paid_unpaid,
    fetch_actual_paid_amt,
)
from ui.pages import sales_page  # noqa: E402

FARM = "OR001"
SALES_NO = "20260823-01"
ORDER_NO = "ORD20260823-001"
METHOD = "AS010101"
SLIP_NO = "20260823-001"
PAID_NO = f"{SALES_NO}-P01"


def _schema() -> str:
    return """
        CREATE TABLE t_sales_master (
            sales_no TEXT, farm_cd TEXT, sales_dt TEXT,
            tot_sales_amt REAL, tot_ship_fee REAL, tot_item_amt REAL,
            tot_paid_amt REAL, tot_unpaid_amt REAL,
            order_no TEXT, sales_status TEXT, sales_source TEXT,
            sales_tp TEXT, custm_id TEXT, auction_fee REAL, extra_cost REAL,
            bill_yn TEXT, bill_dt TEXT, bill_no TEXT, pay_method_cd TEXT,
            status_cd TEXT, rmk TEXT, reg_id TEXT, reg_dt TEXT,
            PRIMARY KEY (sales_no, farm_cd)
        );
        CREATE TABLE t_sales_detail (
            sale_detail_no TEXT PRIMARY KEY,
            sales_no TEXT NOT NULL, farm_cd TEXT NOT NULL,
            order_detail_id TEXT, stock_seq INTEGER,
            item_cd TEXT, qty REAL, tot_sale_amt REAL
        );
        CREATE TABLE t_sales_delivery (
            dlvry_no TEXT PRIMARY KEY, sales_no TEXT, farm_cd TEXT,
            sale_detail_no TEXT
        );
        CREATE TABLE t_cash_ledger (
            paid_detail_no TEXT PRIMARY KEY,
            sales_no TEXT NOT NULL, farm_cd TEXT NOT NULL,
            pay_dt TEXT NOT NULL, pay_method_cd TEXT NOT NULL,
            pay_amt REAL DEFAULT 0, rmk TEXT, reg_id TEXT, reg_dt TEXT,
            slip_no TEXT, order_no TEXT
        );
        CREATE TABLE t_ledger (
            slip_no TEXT PRIMARY KEY, farm_cd TEXT, trans_amt REAL, trans_st TEXT,
            fingerprint TEXT
        );
        CREATE TABLE m_account_code (
            acct_cd TEXT PRIMARY KEY, acct_nm TEXT, parent_cd TEXT,
            acct_level INTEGER, use_yn TEXT
        );
    """


def _insert_sale(
    conn: sqlite3.Connection,
    *,
    tot_sales_amt: float = 300000.0,
    tot_paid_amt: float = 0.0,
    tot_unpaid_amt: float = 300000.0,
    sales_status: str = SALES_STATUS_CONFIRMED,
    order_no: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO t_sales_master(
            sales_no, farm_cd, sales_dt, tot_sales_amt, tot_ship_fee, tot_item_amt,
            tot_paid_amt, tot_unpaid_amt, order_no, sales_status, sales_source,
            sales_tp, reg_id
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            SALES_NO,
            FARM,
            "2026-08-23",
            tot_sales_amt,
            0,
            tot_sales_amt,
            tot_paid_amt,
            tot_unpaid_amt,
            order_no,
            sales_status,
            "ORDER",
            "10",
            "T",
        ),
    )
    conn.execute(
        """
        INSERT INTO t_sales_detail(
            sale_detail_no, sales_no, farm_cd, item_cd, qty, tot_sale_amt
        ) VALUES (?,?,?,?,?,?)
        """,
        (f"{SALES_NO}-S01", SALES_NO, FARM, "FR010100", 10, tot_sales_amt),
    )
    conn.execute(
        """
        INSERT INTO t_sales_delivery(
            dlvry_no, sales_no, farm_cd, sale_detail_no
        ) VALUES (?,?,?,?)
        """,
        (f"{SALES_NO}-D001", SALES_NO, FARM, f"{SALES_NO}-S01"),
    )


def _insert_cash(
    conn: sqlite3.Connection,
    *,
    pay_amt: float = 100000.0,
    order_no: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO t_cash_ledger(
            paid_detail_no, sales_no, farm_cd, pay_dt, pay_method_cd,
            pay_amt, slip_no, rmk, reg_id, order_no
        ) VALUES (?,?,?,?,?,?,?,?,?,?)
        """,
        (
            PAID_NO,
            SALES_NO,
            FARM,
            "2026-08-23",
            METHOD,
            pay_amt,
            SLIP_NO,
            "test",
            "T",
            order_no,
        ),
    )
    conn.execute(
        """
        INSERT INTO t_ledger(slip_no, farm_cd, trans_amt, trans_st, fingerprint)
        VALUES (?,?,?,?,?)
        """,
        (SLIP_NO, FARM, pay_amt, "10", "fp-test-001"),
    )


def _snapshot(conn: sqlite3.Connection) -> dict[str, list[tuple]]:
    cur = conn.cursor()
    out: dict[str, list[tuple]] = {}
    for table in (
        "t_sales_master",
        "t_sales_detail",
        "t_sales_delivery",
        "t_cash_ledger",
        "t_ledger",
    ):
        cur.execute(f"SELECT * FROM {table} ORDER BY rowid")
        out[table] = [tuple(r) for r in cur.fetchall()]
    return out


def _stage7b1_resave_master(
    conn: sqlite3.Connection,
    *,
    new_total: float,
) -> None:
    """Stage7B-1 execute_full_save 핵심 — master/detail/delivery만, cash/ledger 무변경."""
    actual_paid = fetch_actual_paid_amt(conn, FARM, SALES_NO)
    assert_sales_total_not_below_paid(new_total, actual_paid)
    tot_paid, tot_unpaid = compute_master_paid_unpaid(new_total, actual_paid)
    cur = conn.cursor()
    cur.execute(
        "SELECT order_no, sales_dt, sales_status, sales_source, sales_tp, reg_id FROM t_sales_master WHERE farm_cd=? AND sales_no=?",
        (FARM, SALES_NO),
    )
    row = cur.fetchone()
    assert row is not None
    order_no = row[0]
    cur.execute("DELETE FROM t_sales_delivery WHERE farm_cd=? AND sales_no=?", (FARM, SALES_NO))
    cur.execute("DELETE FROM t_sales_detail WHERE farm_cd=? AND sales_no=?", (FARM, SALES_NO))
    cur.execute("DELETE FROM t_sales_master WHERE farm_cd=? AND sales_no=?", (FARM, SALES_NO))
    cur.execute(
        """
        INSERT INTO t_sales_master(
            sales_no, farm_cd, sales_dt, tot_sales_amt, tot_ship_fee, tot_item_amt,
            tot_paid_amt, tot_unpaid_amt, order_no, sales_status, sales_source,
            sales_tp, reg_id
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            SALES_NO,
            FARM,
            row[1],
            new_total,
            0,
            new_total,
            tot_paid,
            tot_unpaid,
            order_no,
            row[2],
            row[3],
            row[4],
            row[5],
        ),
    )
    cur.execute(
        """
        INSERT INTO t_sales_detail(
            sale_detail_no, sales_no, farm_cd, item_cd, qty, tot_sale_amt
        ) VALUES (?,?,?,?,?,?)
        """,
        (f"{SALES_NO}-S01", SALES_NO, FARM, "FR010100", 10, new_total),
    )
    cur.execute(
        """
        INSERT INTO t_sales_delivery(
            dlvry_no, sales_no, farm_cd, sale_detail_no
        ) VALUES (?,?,?,?)
        """,
        (f"{SALES_NO}-D001", SALES_NO, FARM, f"{SALES_NO}-S01"),
    )
    conn.commit()


class Toggle:
    def __init__(self) -> None:
        self.enabled = True
        self.read_only = False

    def setEnabled(self, v: bool) -> None:
        self.enabled = v

    def setReadOnly(self, v: bool) -> None:
        self.read_only = v


class Stage7b1HelperTests(unittest.TestCase):
    def setUp(self) -> None:
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(_schema())
        self.conn.execute(
            """
            INSERT INTO m_account_code(acct_cd, acct_nm, parent_cd, acct_level, use_yn)
            VALUES (?,?,?,?,?)
            """,
            (METHOD, "테스트계좌", "AS01", 4, "Y"),
        )
        self.conn.commit()

    def tearDown(self) -> None:
        self.conn.close()
        try:
            os.unlink(self.path)
        except OSError:
            pass

    def test_actual_paid_ssot_from_cash(self) -> None:
        _insert_sale(self.conn, tot_paid_amt=99999)
        _insert_cash(self.conn, pay_amt=100000)
        self.conn.commit()
        self.assertEqual(fetch_actual_paid_amt(self.conn, FARM, SALES_NO), 100000.0)

    def test_new_sale_actual_paid_zero(self) -> None:
        self.assertEqual(fetch_actual_paid_amt(self.conn, FARM, "NEW-001"), 0.0)

    def test_dec034_block_before_mutation(self) -> None:
        _insert_sale(self.conn)
        _insert_cash(self.conn, pay_amt=100000)
        self.conn.commit()
        before = _snapshot(self.conn)
        with self.assertRaises(PcSalesAmtBelowPaidError) as ctx:
            _stage7b1_resave_master(self.conn, new_total=99000)
        self.assertIn(MSG_SALES_AMT_BELOW_PAID, str(ctx.exception))
        after = _snapshot(self.conn)
        self.assertEqual(before, after)

    def test_reduce_to_250k_allowed(self) -> None:
        _insert_sale(self.conn)
        _insert_cash(self.conn, pay_amt=100000)
        self.conn.commit()
        _stage7b1_resave_master(self.conn, new_total=250000)
        cur = self.conn.cursor()
        cur.execute(
            "SELECT tot_sales_amt, tot_paid_amt, tot_unpaid_amt FROM t_sales_master WHERE sales_no=?",
            (SALES_NO,),
        )
        row = cur.fetchone()
        self.assertEqual(float(row[0]), 250000.0)
        self.assertEqual(float(row[1]), 100000.0)
        self.assertEqual(float(row[2]), 150000.0)

    def test_cash_and_ledger_preserved_on_save(self) -> None:
        _insert_sale(self.conn)
        _insert_cash(self.conn, pay_amt=100000, order_no=ORDER_NO)
        self.conn.commit()
        cash_before = _snapshot(self.conn)["t_cash_ledger"]
        ledger_before = _snapshot(self.conn)["t_ledger"]
        _stage7b1_resave_master(self.conn, new_total=280000)
        cash_after = _snapshot(self.conn)["t_cash_ledger"]
        ledger_after = _snapshot(self.conn)["t_ledger"]
        self.assertEqual(cash_before, cash_after)
        self.assertEqual(ledger_before, ledger_after)
        self.assertEqual(cash_after[0][0], PAID_NO)
        self.assertEqual(cash_after[0][10], ORDER_NO)
        self.assertEqual(cash_after[0][9], SLIP_NO)

    def test_new_sale_master_paid_unpaid(self) -> None:
        paid, unpaid = compute_master_paid_unpaid(50000, 0)
        self.assertEqual(paid, 0.0)
        self.assertEqual(unpaid, 50000.0)

    def test_delete_blocked_when_cash_exists(self) -> None:
        _insert_sale(self.conn)
        _insert_cash(self.conn)
        self.conn.commit()
        with self.assertRaises(PcSalesDeleteHasPaymentsError) as ctx:
            assert_no_cash_for_delete(self.conn.cursor(), FARM, SALES_NO)
        self.assertIn(MSG_SALES_DELETE_HAS_PAYMENTS, str(ctx.exception))

    def test_delete_allowed_without_cash(self) -> None:
        _insert_sale(self.conn)
        self.conn.commit()
        assert_no_cash_for_delete(self.conn.cursor(), FARM, SALES_NO)

    def test_draft_sale_cash_untouched_by_resave(self) -> None:
        _insert_sale(self.conn, sales_status=SALES_STATUS_DRAFT)
        _insert_cash(self.conn, pay_amt=50000)
        self.conn.commit()
        before = _snapshot(self.conn)["t_cash_ledger"]
        _stage7b1_resave_master(self.conn, new_total=200000)
        after = _snapshot(self.conn)["t_cash_ledger"]
        self.assertEqual(before, after)

    def test_protected_sale_save_still_blocked(self) -> None:
        _insert_sale(self.conn, order_no=ORDER_NO)
        self.conn.commit()
        with self.assertRaises(PcShipmentConfirmedSaleLockedError):
            assert_sale_mutable(self.conn.cursor(), FARM, SALES_NO, action="save")


class Stage7b1ExecuteFullSaveSourceTests(unittest.TestCase):
    def test_no_cash_ledger_mutation_in_execute_full_save(self) -> None:
        source = inspect.getsource(sales_page.SalesPage.execute_full_save)
        self.assertNotIn("sync_ledger_by_basket", source)
        self.assertNotIn("DELETE FROM t_cash_ledger", source)
        self.assertNotIn("INSERT INTO t_cash_ledger", source)
        self.assertNotIn("pay_basket", source)


class Stage7b1UiLockTests(unittest.TestCase):
    class _Table:
        def __init__(self, cells: dict[tuple[int, int], Toggle]) -> None:
            self._cells = cells

        def rowCount(self) -> int:
            return max((r for r, _ in self._cells), default=-1) + 1

        def cellWidget(self, r: int, c: int) -> Toggle | None:
            return self._cells.get((r, c))

    def _page(self) -> SimpleNamespace:
        pay_cells = {(0, c): Toggle() for c in range(5)}
        return SimpleNamespace(
            btn_pay_add=Toggle(),
            btn_pay_edit=Toggle(),
            btn_pay_del=Toggle(),
            pay_table=self._Table(pay_cells),
        )

    def test_payment_buttons_always_disabled(self) -> None:
        page = self._page()
        apply_payment_immutable_ui_lock(page)
        self.assertFalse(page.btn_pay_add.enabled)
        self.assertFalse(page.btn_pay_edit.enabled)
        self.assertFalse(page.btn_pay_del.enabled)

    def test_existing_pay_rows_read_only(self) -> None:
        page = self._page()
        apply_payment_immutable_ui_lock(page)
        amt = page.pay_table.cellWidget(0, 3)
        self.assertFalse(amt.enabled)
        self.assertTrue(amt.read_only)

    def test_ordinary_sale_save_enabled_but_pay_disabled(self) -> None:
        page = self._page()
        page.btn_save = Toggle()
        apply_protected_confirmed_sale_ui_lock(page, False)
        apply_payment_immutable_ui_lock(page)
        self.assertTrue(page.btn_save.enabled)
        self.assertFalse(page.btn_pay_add.enabled)


if __name__ == "__main__":
    unittest.main()
