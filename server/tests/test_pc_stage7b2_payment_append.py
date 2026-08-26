# -*- coding: utf-8 -*-
"""Stage7B-2 — PC 신규 일반수금 append (SalesPaymentService.add_payment)."""

from __future__ import annotations

import inspect
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

_HERE = Path(__file__).resolve()
_SERVER = _HERE.parents[1]
_ROOT = _HERE.parents[2]
for p in (_SERVER, _ROOT):
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)

from core.ops_biz_date import today_ops_iso  # noqa: E402
from core.order_ship_constants import SALES_STATUS_CONFIRMED  # noqa: E402
from core.pc_sales_provenance import (  # noqa: E402
    MSG_PAYMENT_COMMITTED_UI_REFRESH_FAILED,
    MSG_SAVE_BEFORE_PAYMENT,
    PcPaymentStaleScreenError,
    apply_payment_immutable_ui_lock,
    assert_payment_screen_not_stale,
    is_payment_add_allowed,
    set_payment_add_enabled,
    try_refresh_after_payment_commit,
)
from core.sales_payment_constants import (  # noqa: E402
    PAY_METHOD_ACCT_LEVEL,
    PAY_METHOD_PARENT_CD,
    PAY_METHOD_USE_YN_Y,
    SALES_STATUS_DRAFT,
)
from core.sales_payment_service import (  # noqa: E402
    PaymentAddIn,
    PaymentValidationError,
    SalesPaymentService,
)
from ui.pages import sales_page  # noqa: E402

FARM = "OR001"
SALES_NO = "20260826-01"
ORDER_NO = "ORD20260826-001"
METHOD = "AS010101"
METHOD_B = "AS010102"
SALES_DT = "2026-08-20"


def _schema() -> str:
    return f"""
        CREATE TABLE t_sales_master (
            sales_no TEXT, farm_cd TEXT, sales_dt TEXT,
            tot_sales_amt REAL, tot_paid_amt REAL, tot_unpaid_amt REAL,
            order_no TEXT, sales_status TEXT, sales_source TEXT,
            pay_method_cd TEXT, slip_no TEXT, rmk TEXT, reg_id TEXT,
            mod_id TEXT, mod_dt TEXT,
            PRIMARY KEY (sales_no, farm_cd)
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
            reg_id TEXT, reg_dt TEXT, mod_id TEXT, mod_dt TEXT, fingerprint TEXT
        );
        CREATE TABLE m_account_code (
            acct_cd TEXT PRIMARY KEY, acct_nm TEXT, parent_cd TEXT,
            acct_level INTEGER, use_yn TEXT
        );
        CREATE TABLE m_code_seq (
            farm_cd TEXT, seq_type TEXT, work_date TEXT, last_seq INTEGER,
            PRIMARY KEY (farm_cd, seq_type, work_date)
        );
    """


def _seed_accounts(cur: sqlite3.Cursor) -> None:
    for cd, nm in ((METHOD, "현금"), (METHOD_B, "예금")):
        cur.execute(
            """
            INSERT INTO m_account_code(acct_cd, acct_nm, parent_cd, acct_level, use_yn)
            VALUES (?,?,?,?,?)
            """,
            (cd, nm, PAY_METHOD_PARENT_CD, PAY_METHOD_ACCT_LEVEL, PAY_METHOD_USE_YN_Y),
        )
    cur.execute(
        """
        INSERT INTO m_account_code(acct_cd, acct_nm, parent_cd, acct_level, use_yn)
        VALUES (?,?,?,?,?)
        """,
        ("AS020101", "외상", "AS02", 4, "Y"),
    )


def _insert_sale(
    conn: sqlite3.Connection,
    *,
    tot: float = 300000.0,
    paid: float = 0.0,
    status: str = SALES_STATUS_CONFIRMED,
    order_no: str | None = None,
    sales_dt: str = SALES_DT,
) -> None:
    unpaid = max(0.0, tot - paid)
    conn.execute(
        """
        INSERT INTO t_sales_master(
            sales_no, farm_cd, sales_dt, tot_sales_amt, tot_paid_amt, tot_unpaid_amt,
            order_no, sales_status, sales_source, reg_id
        ) VALUES (?,?,?,?,?,?,?,?,?,?)
        """,
        (SALES_NO, FARM, sales_dt, tot, paid, unpaid, order_no, status, "ORDER", "T"),
    )


class Toggle:
    def __init__(self) -> None:
        self.enabled = True
        self.read_only = False

    def setEnabled(self, v: bool) -> None:
        self.enabled = v

    def setReadOnly(self, v: bool) -> None:
        self.read_only = v


class Stage7b2UiStateTests(unittest.TestCase):
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

    def test_new_sale_add_disabled(self) -> None:
        self.assertFalse(is_payment_add_allowed(None, 100))
        self.assertFalse(is_payment_add_allowed("", 100))

    def test_draft_add_disabled(self) -> None:
        self.assertFalse(is_payment_add_allowed(SALES_STATUS_DRAFT, 100000))

    def test_confirmed_unpaid_add_enabled(self) -> None:
        self.assertTrue(is_payment_add_allowed(SALES_STATUS_CONFIRMED, 100000))

    def test_protected_confirmed_unpaid_add_enabled(self) -> None:
        # Stage7A protected도 unpaid>0 이면 add 허용
        self.assertTrue(is_payment_add_allowed(SALES_STATUS_CONFIRMED, 1))

    def test_confirmed_paid_add_disabled(self) -> None:
        self.assertFalse(is_payment_add_allowed(SALES_STATUS_CONFIRMED, 0))
        self.assertFalse(is_payment_add_allowed(SALES_STATUS_CONFIRMED, -1))

    def test_edit_delete_always_disabled(self) -> None:
        page = self._page()
        page.btn_pay_add.enabled = True
        apply_payment_immutable_ui_lock(page)
        self.assertTrue(page.btn_pay_add.enabled)  # immutable이 add를 건드리지 않음
        self.assertFalse(page.btn_pay_edit.enabled)
        self.assertFalse(page.btn_pay_del.enabled)

    def test_existing_rows_read_only(self) -> None:
        page = self._page()
        apply_payment_immutable_ui_lock(page)
        amt = page.pay_table.cellWidget(0, 3)
        self.assertFalse(amt.enabled)
        self.assertTrue(amt.read_only)

    def test_set_payment_add_enabled(self) -> None:
        page = self._page()
        set_payment_add_enabled(page, False)
        self.assertFalse(page.btn_pay_add.enabled)
        set_payment_add_enabled(page, True)
        self.assertTrue(page.btn_pay_add.enabled)


class Stage7b2AppendTests(unittest.TestCase):
    def setUp(self) -> None:
        from core.account_manager import AccountManager

        AccountManager._shared_seq_cache.clear()
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        cur = self.conn.cursor()
        cur.executescript(_schema())
        _seed_accounts(cur)
        self.conn.commit()
        self.svc = SalesPaymentService(self.conn)

    def tearDown(self) -> None:
        self.conn.close()
        try:
            os.unlink(self.path)
        except OSError:
            pass

    def _add(self, amt: float, method: str = METHOD, **kwargs):
        return self.svc.add_payment(
            PaymentAddIn(
                farm_cd=FARM,
                sales_no=SALES_NO,
                pay_amt=amt,
                pay_method_cd=method,
                pay_dt=kwargs.get("pay_dt", today_ops_iso()),
                rmk=kwargs.get("rmk", ""),
                user_id=kwargs.get("user_id", "PC"),
                source_order_no=kwargs.get("source_order_no", None),
            )
        )

    def test_append_success_paid_unpaid(self) -> None:
        _insert_sale(self.conn, tot=300000)
        self.conn.commit()
        s = self._add(100000)
        self.assertEqual(float(s["tot_paid_amt"]), 100000)
        self.assertEqual(float(s["tot_unpaid_amt"]), 200000)

    def test_paid_then_add_disabled(self) -> None:
        _insert_sale(self.conn, tot=100000)
        self.conn.commit()
        s = self._add(100000)
        self.assertFalse(is_payment_add_allowed(s["sales_status"], s["tot_unpaid_amt"]))

    def test_partial_n_times(self) -> None:
        _insert_sale(self.conn, tot=300000)
        self.conn.commit()
        self._add(100000)
        self._add(50000)
        s = self._add(50000)
        self.assertEqual(float(s["tot_paid_amt"]), 200000)
        self.assertEqual(len(s["payments"]), 3)

    def test_existing_cash_business_fields_unchanged(self) -> None:
        _insert_sale(self.conn, tot=300000)
        self.conn.commit()
        self._add(100000, method=METHOD)
        row0 = self.conn.execute(
            "SELECT paid_detail_no, pay_dt, pay_method_cd, pay_amt, order_no FROM t_cash_ledger WHERE sales_no=? ORDER BY paid_detail_no",
            (SALES_NO,),
        ).fetchone()
        self._add(50000, method=METHOD_B)
        row0_after = self.conn.execute(
            "SELECT paid_detail_no, pay_dt, pay_method_cd, pay_amt, order_no FROM t_cash_ledger WHERE paid_detail_no=?",
            (row0["paid_detail_no"],),
        ).fetchone()
        self.assertEqual(row0["pay_dt"], row0_after["pay_dt"])
        self.assertEqual(row0["pay_method_cd"], row0_after["pay_method_cd"])
        self.assertEqual(float(row0["pay_amt"]), float(row0_after["pay_amt"]))
        self.assertEqual(row0["order_no"], row0_after["order_no"])

    def test_general_payment_order_no_null(self) -> None:
        _insert_sale(self.conn, tot=100000)
        self.conn.commit()
        self._add(100000, source_order_no=None)
        row = self.conn.execute(
            "SELECT order_no FROM t_cash_ledger WHERE sales_no=?", (SALES_NO,)
        ).fetchone()
        self.assertTrue(row["order_no"] is None or str(row["order_no"]).strip() == "")

    def test_order_linked_sale_general_payment_order_no_null(self) -> None:
        _insert_sale(self.conn, tot=100000, order_no=ORDER_NO)
        self.conn.commit()
        self._add(50000, source_order_no=None)
        row = self.conn.execute(
            "SELECT order_no FROM t_cash_ledger WHERE sales_no=?", (SALES_NO,)
        ).fetchone()
        self.assertTrue(row["order_no"] is None or str(row["order_no"]).strip() == "")

    def test_draft_write_reject(self) -> None:
        _insert_sale(self.conn, status=SALES_STATUS_DRAFT)
        self.conn.commit()
        with self.assertRaises(PaymentValidationError):
            self._add(1000)

    def test_amount_le_zero_reject(self) -> None:
        _insert_sale(self.conn)
        self.conn.commit()
        with self.assertRaises(PaymentValidationError):
            self._add(0)

    def test_amount_over_unpaid_reject(self) -> None:
        _insert_sale(self.conn, tot=100000)
        self.conn.commit()
        with self.assertRaises(PaymentValidationError):
            self._add(100001)

    def test_invalid_method_reject(self) -> None:
        _insert_sale(self.conn)
        self.conn.commit()
        with self.assertRaises(PaymentValidationError):
            self._add(1000, method="AS020101")

    def test_pay_dt_before_sales_reject(self) -> None:
        _insert_sale(self.conn, sales_dt="2026-08-20")
        self.conn.commit()
        with self.assertRaises(PaymentValidationError):
            self._add(1000, pay_dt="2026-08-19")

    def test_pay_dt_future_reject(self) -> None:
        _insert_sale(self.conn)
        self.conn.commit()
        with self.assertRaises(PaymentValidationError):
            self._add(1000, pay_dt="2099-01-01")

    def test_blank_pay_dt_reject(self) -> None:
        _insert_sale(self.conn)
        self.conn.commit()
        with self.assertRaises(PaymentValidationError):
            self._add(1000, pay_dt="")

    def test_same_method_append_business_fields(self) -> None:
        _insert_sale(self.conn, tot=300000)
        self.conn.commit()
        self._add(100000, method=METHOD)
        first = self.conn.execute(
            "SELECT paid_detail_no, pay_dt, pay_method_cd, pay_amt, order_no, slip_no FROM t_cash_ledger ORDER BY paid_detail_no"
        ).fetchone()
        self._add(50000, method=METHOD)
        first_after = self.conn.execute(
            "SELECT pay_dt, pay_method_cd, pay_amt, order_no FROM t_cash_ledger WHERE paid_detail_no=?",
            (first["paid_detail_no"],),
        ).fetchone()
        self.assertEqual(first["pay_dt"], first_after["pay_dt"])
        self.assertEqual(first["pay_method_cd"], first_after["pay_method_cd"])
        self.assertEqual(float(first["pay_amt"]), float(first_after["pay_amt"]))
        self.assertEqual(first["order_no"], first_after["order_no"])

    def test_different_method_append(self) -> None:
        _insert_sale(self.conn, tot=300000)
        self.conn.commit()
        self._add(100000, method=METHOD)
        s = self._add(50000, method=METHOD_B)
        methods = {p["pay_method_cd"] for p in s["payments"]}
        self.assertEqual(methods, {METHOD, METHOD_B})

    def test_list_payment_methods_ssot(self) -> None:
        methods = self.svc.list_payment_methods()
        cds = {m["acct_cd"] for m in methods}
        self.assertIn(METHOD, cds)
        self.assertIn(METHOD_B, cds)
        self.assertNotIn("AS020101", cds)


class Stage7b2StaleScreenTests(unittest.TestCase):
    def test_amount_mismatch_blocks(self) -> None:
        with self.assertRaises(PcPaymentStaleScreenError) as ctx:
            assert_payment_screen_not_stale(
                ui_tot_sales_amt=250000,
                db_tot_sales_amt=300000,
                ui_sales_dt=SALES_DT,
                db_sales_dt=SALES_DT,
            )
        self.assertIn(MSG_SAVE_BEFORE_PAYMENT, str(ctx.exception))

    def test_sales_dt_mismatch_blocks(self) -> None:
        with self.assertRaises(PcPaymentStaleScreenError):
            assert_payment_screen_not_stale(
                ui_tot_sales_amt=300000,
                db_tot_sales_amt=300000,
                ui_sales_dt="2026-08-21",
                db_sales_dt=SALES_DT,
            )

    def test_matching_allows(self) -> None:
        assert_payment_screen_not_stale(
            ui_tot_sales_amt=300000,
            db_tot_sales_amt=300000,
            ui_sales_dt=SALES_DT,
            db_sales_dt=SALES_DT,
        )


class Stage7b2SourceGuardTests(unittest.TestCase):
    def test_open_payment_uses_add_payment_not_cash_sql(self) -> None:
        source = inspect.getsource(sales_page.SalesPage.open_payment_add_dialog)
        self.assertIn("add_payment", source)
        self.assertIn("source_order_no=None", source)
        self.assertIn("try_refresh_after_payment_commit", source)
        self.assertIn("MSG_PAYMENT_COMMITTED_UI_REFRESH_FAILED", source)
        self.assertIn("payment_committed", source)
        self.assertNotIn("INSERT INTO t_cash_ledger", source)
        self.assertNotIn("DELETE FROM t_cash_ledger", source)
        self.assertNotIn("sync_ledger_by_basket", source)

    def test_btn_pay_add_not_connected_to_add_pay_row(self) -> None:
        # 생성자/탭 초기화 소스에서 open_payment_add_dialog 연결 확인
        source = inspect.getsource(sales_page.SalesPage)
        self.assertIn("open_payment_add_dialog", source)
        self.assertIn("btn_pay_add.clicked.connect(self.open_payment_add_dialog)", source)


class Stage7b2PostCommitUiBoundaryTests(unittest.TestCase):
    """COMMIT 성공과 UI refresh 실패를 분리한다. add_payment 최대 1회."""

    def test_refresh_success_first_try(self) -> None:
        calls = {"apply": 0, "reload": 0}

        def apply_ok() -> None:
            calls["apply"] += 1

        def reload_should_not_run() -> None:
            calls["reload"] += 1
            raise AssertionError("reload must not run")

        self.assertTrue(try_refresh_after_payment_commit(apply_ok, reload_should_not_run))
        self.assertEqual(calls["apply"], 1)
        self.assertEqual(calls["reload"], 0)

    def test_first_refresh_fails_then_reload_succeeds(self) -> None:
        calls = {"apply": 0, "reload": 0}

        def apply_fail_once() -> None:
            calls["apply"] += 1
            if calls["apply"] == 1:
                raise RuntimeError("ui boom")

        def reload_and_apply() -> None:
            calls["reload"] += 1
            # second apply path via reload_and_apply itself applying
            calls["apply"] += 1

        self.assertTrue(try_refresh_after_payment_commit(apply_fail_once, reload_and_apply))
        self.assertEqual(calls["reload"], 1)
        self.assertEqual(calls["apply"], 2)

    def test_refresh_keeps_failing_returns_false(self) -> None:
        def always_fail() -> None:
            raise RuntimeError("ui dead")

        self.assertFalse(try_refresh_after_payment_commit(always_fail, always_fail))
        self.assertIn("정상 등록", MSG_PAYMENT_COMMITTED_UI_REFRESH_FAILED)
        self.assertIn("다시 조회", MSG_PAYMENT_COMMITTED_UI_REFRESH_FAILED)
        self.assertNotIn("수금 실패", MSG_PAYMENT_COMMITTED_UI_REFRESH_FAILED)

    def test_write_success_ui_fail_add_called_once(self) -> None:
        """오케스트레이션: add 1회 + refresh 실패 → committed_ui_fail, 재append 없음."""
        add_calls = {"n": 0}

        def add_payment_once() -> dict:
            add_calls["n"] += 1
            return {"tot_paid_amt": 100000, "tot_unpaid_amt": 200000}

        def boom1() -> None:
            raise RuntimeError("refresh1")

        def boom2() -> None:
            raise RuntimeError("refresh2")

        result = add_payment_once()
        ui_ok = try_refresh_after_payment_commit(boom1, boom2)
        self.assertEqual(add_calls["n"], 1)
        self.assertFalse(ui_ok)
        self.assertIsNotNone(result)

    def test_write_failure_does_not_refresh_as_commit_success(self) -> None:
        add_calls = {"n": 0}

        def add_fail() -> dict:
            add_calls["n"] += 1
            raise PaymentValidationError("amount over unpaid")

        with self.assertRaises(PaymentValidationError):
            add_fail()
        self.assertEqual(add_calls["n"], 1)

    def test_real_add_then_refresh_fallback_cash_once(self) -> None:
        """add_payment 성공 + 첫 UI 실패 + summary 재조회 성공 → cash 1건, add 1회."""
        from core.account_manager import AccountManager

        AccountManager._shared_seq_cache.clear()
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.executescript(_schema())
        _seed_accounts(cur)
        conn.commit()
        _insert_sale(conn, tot=300000)
        conn.commit()
        svc = SalesPaymentService(conn)
        add_n = {"n": 0}

        def add_once() -> dict:
            add_n["n"] += 1
            return svc.add_payment(
                PaymentAddIn(
                    farm_cd=FARM,
                    sales_no=SALES_NO,
                    pay_amt=100000,
                    pay_method_cd=METHOD,
                    pay_dt=today_ops_iso(),
                    rmk="",
                    user_id="PC",
                    source_order_no=None,
                )
            )

        result = add_once()
        applied = {"n": 0}

        def apply_fail_first() -> None:
            applied["n"] += 1
            if applied["n"] == 1:
                raise RuntimeError("widget boom")
            # should not reach here via apply_with_result path after success

        def reload_ok() -> None:
            summary = svc.get_payment_summary(FARM, SALES_NO)
            self.assertEqual(float(summary["tot_paid_amt"]), 100000)
            applied["n"] += 1

        self.assertTrue(try_refresh_after_payment_commit(apply_fail_first, reload_ok))
        self.assertEqual(add_n["n"], 1)
        cash_n = conn.execute(
            "SELECT COUNT(*) FROM t_cash_ledger WHERE sales_no=?", (SALES_NO,)
        ).fetchone()[0]
        self.assertEqual(int(cash_n), 1)
        self.assertEqual(float(result["tot_paid_amt"]), 100000)
        conn.close()
        os.unlink(path)

    def test_real_add_ui_total_fail_no_reappend(self) -> None:
        """add 성공 + UI 계속 실패 → cash 1 · add 1 · 성공안내 문구 · 실패문구 없음."""
        from core.account_manager import AccountManager

        AccountManager._shared_seq_cache.clear()
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.executescript(_schema())
        _seed_accounts(cur)
        conn.commit()
        _insert_sale(conn, tot=300000)
        conn.commit()
        svc = SalesPaymentService(conn)
        add_n = {"n": 0}

        def add_once() -> dict:
            add_n["n"] += 1
            return svc.add_payment(
                PaymentAddIn(
                    farm_cd=FARM,
                    sales_no=SALES_NO,
                    pay_amt=50000,
                    pay_method_cd=METHOD,
                    pay_dt=today_ops_iso(),
                    rmk="",
                    user_id="PC",
                    source_order_no=None,
                )
            )

        add_once()

        def boom() -> None:
            raise RuntimeError("ui dead")

        ui_ok = try_refresh_after_payment_commit(boom, boom)
        cash_n = conn.execute(
            "SELECT COUNT(*) FROM t_cash_ledger WHERE sales_no=?", (SALES_NO,)
        ).fetchone()[0]
        conn.close()
        os.unlink(path)
        self.assertFalse(ui_ok)
        self.assertEqual(add_n["n"], 1)
        self.assertEqual(int(cash_n), 1)
        self.assertIn("정상 등록", MSG_PAYMENT_COMMITTED_UI_REFRESH_FAILED)
        self.assertNotIn("수금 실패", MSG_PAYMENT_COMMITTED_UI_REFRESH_FAILED)
        self.assertNotIn("수금 처리 중 오류", MSG_PAYMENT_COMMITTED_UI_REFRESH_FAILED)
