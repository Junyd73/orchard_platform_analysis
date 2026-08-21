# -*- coding: utf-8 -*-
"""개발순서 3 — 판매 추가수금 Core (SalesPaymentService)."""

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

from core.account_manager import AccountManager  # noqa: E402
from core.ops_biz_date import today_ops_iso  # noqa: E402
from core.order_ship_constants import SALES_STATUS_CONFIRMED  # noqa: E402
from core.sales_payment_constants import (  # noqa: E402
    COLLECTION_STATUS_PAID,
    COLLECTION_STATUS_PARTIAL,
    COLLECTION_STATUS_UNPAID,
    MSG_PAY_AMT_INVALID,
    MSG_PAY_AMT_OVER_UNPAID,
    MSG_PAY_METHOD_INVALID,
    MSG_SALES_DRAFT_PAYMENT_FORBIDDEN,
    MSG_SALES_NOT_FOUND,
    SALES_STATUS_DRAFT,
)
from core.sales_payment_service import (  # noqa: E402
    PaymentAddIn,
    PaymentNotFoundError,
    PaymentValidationError,
    SalesPaymentService,
)


FARM = "OR001"
FARM_B = "OR002"
SALES_A = "20260821-01"
SALES_B = "20260821-02"
SALES_DT = "2026-08-21"


def _schema_sql() -> str:
    return """
        CREATE TABLE m_account_code (
            acct_cd TEXT PRIMARY KEY, acct_nm TEXT, acct_level INTEGER,
            parent_cd TEXT, use_yn TEXT DEFAULT 'Y'
        );
        CREATE TABLE t_sales_master (
            sales_no TEXT NOT NULL, farm_cd TEXT NOT NULL,
            sales_dt TEXT, sales_status TEXT,
            tot_sales_amt REAL DEFAULT 0,
            tot_paid_amt REAL DEFAULT 0,
            tot_unpaid_amt REAL DEFAULT 0,
            pay_method_cd TEXT, slip_no TEXT,
            order_no TEXT,
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
            reg_id TEXT, reg_dt TEXT, mod_id TEXT, mod_dt TEXT
        );
    """


def _seed_accounts(cur: sqlite3.Cursor) -> None:
    rows = [
        ("AS010101", "현금 (시재)", 4, "AS0101", "Y"),
        ("AS010102", "농협은행", 4, "AS0101", "Y"),
        ("AS010103", "국민은행", 4, "AS0101", "Y"),
        ("AS020101", "외상매출금", 4, "AS0102", "Y"),
        ("AS020102", "미수금", 4, "AS0102", "Y"),
        ("AS010199", "비활성현금", 4, "AS0101", "N"),
    ]
    cur.executemany(
        "INSERT INTO m_account_code(acct_cd, acct_nm, acct_level, parent_cd, use_yn) "
        "VALUES (?,?,?,?,?)",
        rows,
    )


def _insert_sales(
    cur: sqlite3.Cursor,
    *,
    sales_no: str = SALES_A,
    farm_cd: str = FARM,
    status: str = SALES_STATUS_CONFIRMED,
    tot: float = 300000,
    paid: float | None = None,
    unpaid: float | None = None,
) -> None:
    p = 0.0 if paid is None else paid
    u = (tot - p) if unpaid is None else unpaid
    cur.execute(
        """
        INSERT INTO t_sales_master(
            sales_no, farm_cd, sales_dt, sales_status,
            tot_sales_amt, tot_paid_amt, tot_unpaid_amt
        ) VALUES (?,?,?,?,?,?,?)
        """,
        (sales_no, farm_cd, SALES_DT, status, tot, p, u),
    )


class SalesPaymentServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        AccountManager._shared_seq_cache.clear()
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        cur = self.conn.cursor()
        cur.executescript(_schema_sql())
        _seed_accounts(cur)
        self.conn.commit()
        self.svc = SalesPaymentService(self.conn)

    def tearDown(self) -> None:
        self.conn.close()
        try:
            os.unlink(self.path)
        except OSError:
            pass

    def _add(
        self,
        amt: float,
        method: str = "AS010102",
        *,
        sales_no: str = SALES_A,
        farm_cd: str = FARM,
        **kwargs,
    ):
        return self.svc.add_payment(
            PaymentAddIn(
                farm_cd=farm_cd,
                sales_no=sales_no,
                pay_amt=amt,
                pay_method_cd=method,
                pay_dt=kwargs.get("pay_dt", today_ops_iso()),
                rmk=kwargs.get("rmk", ""),
                user_id=kwargs.get("user_id", "t"),
            )
        )

    def _cash_rows(self, sales_no: str = SALES_A, farm_cd: str = FARM):
        return self.conn.execute(
            """
            SELECT paid_detail_no, pay_method_cd, pay_amt, slip_no, order_no
              FROM t_cash_ledger
             WHERE farm_cd=? AND sales_no=?
             ORDER BY paid_detail_no
            """,
            (farm_cd, sales_no),
        ).fetchall()

    def _ledger_active(self, sales_no: str = SALES_A):
        return self.conn.execute(
            """
            SELECT slip_no, acct_cd, trans_amt, trans_type_cd, trans_st, ref_id
              FROM t_ledger
             WHERE ref_id LIKE ?
               AND trans_st = '10'
             ORDER BY slip_no
            """,
            (f"SALE-{sales_no}-%",),
        ).fetchall()

    def _master(self, sales_no: str = SALES_A, farm_cd: str = FARM):
        return self.conn.execute(
            """
            SELECT tot_paid_amt, tot_unpaid_amt, pay_method_cd, slip_no
              FROM t_sales_master WHERE farm_cd=? AND sales_no=?
            """,
            (farm_cd, sales_no),
        ).fetchone()

    # --- basic ---
    def test_01_sales_not_found(self):
        with self.assertRaises(PaymentNotFoundError):
            self._add(1000)

    def test_02_draft_forbidden(self):
        _insert_sales(self.conn.cursor(), status=SALES_STATUS_DRAFT)
        self.conn.commit()
        with self.assertRaises(PaymentValidationError) as ctx:
            self._add(1000)
        self.assertIn(MSG_SALES_DRAFT_PAYMENT_FORBIDDEN, str(ctx.exception))
        self.assertEqual(len(self._cash_rows()), 0)
        self.assertEqual(len(self._ledger_active()), 0)

    def test_03_confirmed_ok(self):
        _insert_sales(self.conn.cursor())
        self.conn.commit()
        out = self._add(100000, "AS010101")
        self.assertEqual(out["tot_paid_amt"], 100000)
        self.assertEqual(out["tot_unpaid_amt"], 200000)
        self.assertEqual(out["collection_status"], COLLECTION_STATUS_PARTIAL)

    def test_04_zero_rejected(self):
        _insert_sales(self.conn.cursor())
        self.conn.commit()
        with self.assertRaises(PaymentValidationError) as ctx:
            self._add(0)
        self.assertIn(MSG_PAY_AMT_INVALID, str(ctx.exception))

    def test_05_negative_rejected(self):
        _insert_sales(self.conn.cursor())
        self.conn.commit()
        with self.assertRaises(PaymentValidationError):
            self._add(-1)

    def test_06_over_unpaid_rejected(self):
        _insert_sales(self.conn.cursor())
        self.conn.commit()
        with self.assertRaises(PaymentValidationError) as ctx:
            self._add(300001)
        self.assertIn(MSG_PAY_AMT_OVER_UNPAID, str(ctx.exception))

    # --- accounts ---
    def test_07_08_09_cash_methods_ok(self):
        _insert_sales(self.conn.cursor())
        self.conn.commit()
        self._add(10000, "AS010101")
        self._add(10000, "AS010102")
        self._add(10000, "AS010103")
        self.assertEqual(len(self._cash_rows()), 3)

    def test_10_11_receivable_rejected(self):
        _insert_sales(self.conn.cursor())
        self.conn.commit()
        for bad in ("AS020101", "AS020102"):
            with self.assertRaises(PaymentValidationError) as ctx:
                self._add(1000, bad)
            self.assertIn(MSG_PAY_METHOD_INVALID, str(ctx.exception))

    def test_12_unknown_account_rejected(self):
        _insert_sales(self.conn.cursor())
        self.conn.commit()
        with self.assertRaises(PaymentValidationError):
            self._add(1000, "AS019999")

    def test_13_inactive_rejected(self):
        _insert_sales(self.conn.cursor())
        self.conn.commit()
        with self.assertRaises(PaymentValidationError):
            self._add(1000, "AS010199")

    # --- partial / full ---
    def test_14_15_16_partial_then_full(self):
        _insert_sales(self.conn.cursor())
        self.conn.commit()
        s1 = self._add(100000, "AS010102")
        self.assertEqual(s1["tot_paid_amt"], 100000)
        self.assertEqual(s1["tot_unpaid_amt"], 200000)
        s2 = self._add(50000, "AS010102")
        self.assertEqual(s2["tot_paid_amt"], 150000)
        self.assertEqual(s2["tot_unpaid_amt"], 150000)
        s3 = self._add(150000, "AS010101")
        self.assertEqual(s3["tot_paid_amt"], 300000)
        self.assertEqual(s3["tot_unpaid_amt"], 0)
        self.assertEqual(s3["collection_status"], COLLECTION_STATUS_PAID)

    def test_17_18_cash_ssot_repairs_stale_master(self):
        cur = self.conn.cursor()
        _insert_sales(cur, paid=999999, unpaid=-1)  # 잘못된 master
        self.conn.commit()
        out = self._add(100000, "AS010101")
        m = self._master()
        self.assertEqual(out["tot_paid_amt"], 100000)
        self.assertEqual(float(m["tot_paid_amt"]), 100000)
        self.assertEqual(float(m["tot_unpaid_amt"]), 200000)
        cash_sum = sum(float(r["pay_amt"]) for r in self._cash_rows())
        self.assertEqual(cash_sum, float(m["tot_paid_amt"]))

    def test_19_paid_detail_append_no_renumber(self):
        _insert_sales(self.conn.cursor())
        self.conn.commit()
        self._add(100000, "AS010102")
        self._add(50000, "AS010102")
        self._add(50000, "AS010101")
        ids = [r["paid_detail_no"] for r in self._cash_rows()]
        self.assertEqual(
            ids,
            [
                f"{SALES_A}-P01",
                f"{SALES_A}-P02",
                f"{SALES_A}-P03",
            ],
        )

    def test_20_first_payment_ledger(self):
        _insert_sales(self.conn.cursor())
        self.conn.commit()
        self._add(100000, "AS010102")
        active = self._ledger_active()
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0]["trans_type_cd"], "REVENUE")
        self.assertEqual(active[0]["acct_cd"], "AS010102")
        self.assertEqual(float(active[0]["trans_amt"]), 100000)
        self.assertEqual(active[0]["trans_st"], "10")
        cash = self._cash_rows()[0]
        self.assertEqual(cash["slip_no"], active[0]["slip_no"])
        self.assertIsNone(cash["order_no"])

    def test_21_same_method_slip_remap(self):
        _insert_sales(self.conn.cursor())
        self.conn.commit()
        self._add(100000, "AS010102")
        first_slip = self._cash_rows()[0]["slip_no"]
        self._add(50000, "AS010102")
        cash = self._cash_rows()
        self.assertEqual(len(cash), 2)
        self.assertEqual(cash[0]["paid_detail_no"], f"{SALES_A}-P01")
        self.assertEqual(cash[1]["paid_detail_no"], f"{SALES_A}-P02")
        self.assertEqual(cash[0]["slip_no"], cash[1]["slip_no"])
        self.assertNotEqual(cash[0]["slip_no"], first_slip)

        old = self.conn.execute(
            "SELECT trans_st FROM t_ledger WHERE slip_no=?", (first_slip,)
        ).fetchone()
        self.assertEqual(old["trans_st"], "90")
        rev = self.conn.execute(
            """
            SELECT trans_st, trans_amt, parent_slip_no FROM t_ledger
             WHERE parent_slip_no=? AND trans_st='80'
            """,
            (first_slip,),
        ).fetchone()
        self.assertIsNotNone(rev)
        self.assertEqual(float(rev["trans_amt"]), -100000)
        active = self._ledger_active()
        self.assertEqual(len(active), 1)
        self.assertEqual(float(active[0]["trans_amt"]), 150000)
        self.assertEqual(active[0]["slip_no"], cash[0]["slip_no"])

    def test_22_other_method_keeps_existing_slip(self):
        _insert_sales(self.conn.cursor())
        self.conn.commit()
        self._add(100000, "AS010102")
        nh_slip = self._cash_rows()[0]["slip_no"]
        self._add(50000, "AS010101")
        cash = self._cash_rows()
        self.assertEqual(cash[0]["slip_no"], nh_slip)
        self.assertNotEqual(cash[1]["slip_no"], nh_slip)
        active = self._ledger_active()
        self.assertEqual(len(active), 2)
        by_acct = {r["acct_cd"]: float(r["trans_amt"]) for r in active}
        self.assertEqual(by_acct["AS010102"], 100000)
        self.assertEqual(by_acct["AS010101"], 50000)
        cancelled = self.conn.execute(
            "SELECT COUNT(*) AS c FROM t_ledger WHERE trans_st IN ('80','90')"
        ).fetchone()["c"]
        self.assertEqual(cancelled, 0)

    def test_23_mid_failure_rollback(self):
        _insert_sales(self.conn.cursor())
        self.conn.execute(
            """
            CREATE TRIGGER trg_fail_cash_ins
            BEFORE INSERT ON t_cash_ledger
            BEGIN
              SELECT RAISE(ABORT, 'forced failure');
            END;
            """
        )
        self.conn.commit()
        with self.assertRaises(sqlite3.Error):
            self._add(100000, "AS010102")
        self.assertEqual(len(self._cash_rows()), 0)
        m = self._master()
        self.assertEqual(float(m["tot_paid_amt"]), 0)
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) AS c FROM t_ledger").fetchone()["c"],
            0,
        )

    def test_24_25_isolation(self):
        cur = self.conn.cursor()
        _insert_sales(cur, sales_no=SALES_A, farm_cd=FARM)
        _insert_sales(cur, sales_no=SALES_B, farm_cd=FARM, tot=50000)
        _insert_sales(cur, sales_no=SALES_A, farm_cd=FARM_B, tot=90000)
        self.conn.commit()
        self._add(100000, "AS010101", sales_no=SALES_A, farm_cd=FARM)
        self.assertEqual(len(self._cash_rows(SALES_B)), 0)
        self.assertEqual(len(self._cash_rows(SALES_A, FARM_B)), 0)
        self.assertEqual(float(self._master(SALES_B)["tot_paid_amt"]), 0)
        self.assertEqual(float(self._master(SALES_A, FARM_B)["tot_paid_amt"]), 0)

    def test_26_order_no_null(self):
        _insert_sales(self.conn.cursor())
        self.conn.commit()
        self._add(100000)
        self.assertIsNone(self._cash_rows()[0]["order_no"])

    def test_29_caller_owned_tx_external_rollback(self):
        _insert_sales(self.conn.cursor())
        self.conn.commit()
        cur = self.conn.cursor()
        cur.execute("BEGIN IMMEDIATE")
        self.svc.add_payment_in_tx(
            cur,
            PaymentAddIn(
                farm_cd=FARM,
                sales_no=SALES_A,
                pay_amt=100000,
                pay_method_cd="AS010102",
                user_id="t",
            ),
        )
        self.conn.rollback()
        self.assertEqual(len(self._cash_rows()), 0)
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) AS c FROM t_ledger").fetchone()["c"],
            0,
        )
        self.assertEqual(float(self._master()["tot_paid_amt"]), 0)

    def test_existing_n_payments_append(self):
        """운영형 N회 수금 상태에서 append — 기존 ID 유지."""
        cur = self.conn.cursor()
        _insert_sales(cur, tot=950000, paid=800000, unpaid=150000)
        # 기존 3행 + 기존 slip (fingerprint용)
        cur.execute(
            """
            INSERT INTO t_ledger(
                slip_no, farm_cd, trans_dt, trans_type_cd, acct_cd, trans_amt,
                rmk, ref_id, trans_st, reg_id, reg_dt
            ) VALUES
            ('20260821-001', ?, ?, 'REVENUE', 'AS010101', 600000, 'x',
             'SALE-20260821-01-AS010101_AS010101', '10', 't', datetime('now')),
            ('20260821-002', ?, ?, 'REVENUE', 'AS010102', 200000, 'x',
             'SALE-20260821-01-AS010102_AS010102', '10', 't', datetime('now'))
            """,
            (FARM, SALES_DT, FARM, SALES_DT),
        )
        for pd, method, amt, slip in (
            (f"{SALES_A}-P01", "AS010101", 350000, "20260821-001"),
            (f"{SALES_A}-P02", "AS010101", 250000, "20260821-001"),
            (f"{SALES_A}-P03", "AS010102", 200000, "20260821-002"),
        ):
            cur.execute(
                """
                INSERT INTO t_cash_ledger(
                    paid_detail_no, sales_no, farm_cd, pay_dt, pay_method_cd,
                    pay_amt, slip_no, reg_id, order_no
                ) VALUES (?,?,?,?,?,?,?,?,NULL)
                """,
                (pd, SALES_A, FARM, SALES_DT, method, amt, slip, "t"),
            )
        self.conn.commit()
        AccountManager._shared_seq_cache.clear()

        out = self._add(150000, "AS010103")
        ids = [r["paid_detail_no"] for r in self._cash_rows()]
        self.assertEqual(
            ids,
            [
                f"{SALES_A}-P01",
                f"{SALES_A}-P02",
                f"{SALES_A}-P03",
                f"{SALES_A}-P04",
            ],
        )
        self.assertEqual(out["tot_paid_amt"], 950000)
        self.assertEqual(out["tot_unpaid_amt"], 0)
        self.assertEqual(out["collection_status"], COLLECTION_STATUS_PAID)
        # 기존 농협/현금 그룹은 dirty 아니면 slip 유지 가능; 국민만 신규
        cash = {r["paid_detail_no"]: r for r in self._cash_rows()}
        self.assertIsNotNone(cash[f"{SALES_A}-P04"]["slip_no"])
        self.assertIsNone(cash[f"{SALES_A}-P04"]["order_no"])

    def test_summary_unpaid_status(self):
        _insert_sales(self.conn.cursor())
        self.conn.commit()
        s = self.svc.get_payment_summary(FARM, SALES_A)
        self.assertEqual(s["collection_status"], COLLECTION_STATUS_UNPAID)
        self.assertEqual(s["payments"], [])

    def test_master_pay_method_slip_not_updated(self):
        cur = self.conn.cursor()
        _insert_sales(cur)
        cur.execute(
            "UPDATE t_sales_master SET pay_method_cd='KEEP', slip_no='KEEP' "
            "WHERE sales_no=? AND farm_cd=?",
            (SALES_A, FARM),
        )
        self.conn.commit()
        self._add(100000, "AS010101")
        m = self._master()
        self.assertEqual(m["pay_method_cd"], "KEEP")
        self.assertEqual(m["slip_no"], "KEEP")


if __name__ == "__main__":
    unittest.main()
