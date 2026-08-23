# -*- coding: utf-8 -*-
"""판매 목록 Core — Stage 5 read-only."""

from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve()
_ROOT = _HERE.parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.sales_query_constants import (  # noqa: E402
    MSG_SALES_DATE_INVALID,
    PAYMENT_STATUS_PAID,
    PAYMENT_STATUS_PARTIAL,
    PAYMENT_STATUS_UNPAID,
)
from core.sales_query_service import (  # noqa: E402
    SalesQueryService,
    SalesQueryValidationError,
    compute_payment_status,
)
from core.order_ship_constants import SALES_STATUS_CONFIRMED  # noqa: E402
from core.sales_payment_constants import SALES_STATUS_DRAFT  # noqa: E402

FARM_A = "OR001"
FARM_B = "OR002"


def _schema_sql() -> str:
    return """
        CREATE TABLE m_customer (
            custm_id TEXT, farm_cd TEXT, custm_nm TEXT, mobile TEXT, use_yn TEXT
        );
        CREATE TABLE m_common_code (
            farm_cd TEXT, code_cd TEXT, code_nm TEXT, parent_cd TEXT
        );
        CREATE TABLE t_sales_master (
            sales_no TEXT NOT NULL, farm_cd TEXT NOT NULL,
            sales_dt TEXT, sales_status TEXT, sales_source TEXT,
            custm_id TEXT, order_no TEXT,
            tot_sales_amt REAL DEFAULT 0,
            tot_paid_amt REAL DEFAULT 0,
            tot_unpaid_amt REAL DEFAULT 0,
            PRIMARY KEY (sales_no, farm_cd)
        );
        CREATE TABLE t_sales_detail (
            sale_detail_no TEXT, sales_no TEXT, farm_cd TEXT,
            item_cd TEXT, variety_cd TEXT, grade_cd TEXT, size_cd TEXT,
            weight REAL, qty REAL,
            PRIMARY KEY (sale_detail_no, farm_cd)
        );
        CREATE TABLE t_cash_ledger (
            paid_detail_no TEXT PRIMARY KEY,
            sales_no TEXT NOT NULL, farm_cd TEXT NOT NULL,
            pay_dt TEXT NOT NULL, pay_method_cd TEXT NOT NULL,
            pay_amt REAL DEFAULT 0, slip_no TEXT, order_no TEXT
        );
        INSERT INTO m_customer (custm_id, farm_cd, custm_nm, use_yn) VALUES
            ('C001', 'OR001', '홍길동', 'Y'),
            ('C002', 'OR001', '김고객', 'Y'),
            ('C001', 'OR002', '다른농장', 'Y');
        INSERT INTO m_common_code (farm_cd, code_cd, code_nm, parent_cd) VALUES
            ('OR001', 'FR010101', '신고', 'FR010100'),
            ('OR001', 'GR010100', '특', 'GR01'),
            ('OR001', 'SZ010100', '20과', 'SZ01');
    """


def _open_db() -> tuple[Path, sqlite3.Connection]:
    fd, name = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    path = Path(name)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.executescript(_schema_sql())
    conn.commit()
    return path, conn


def _insert_sale(
    cur: sqlite3.Cursor,
    *,
    sales_no: str,
    farm_cd: str = FARM_A,
    sales_dt: str = "2026-08-22",
    sales_status: str = SALES_STATUS_CONFIRMED,
    sales_source: str = "ORDER",
    custm_id: str = "C001",
    order_no: str | None = None,
    tot: float = 100000,
    master_paid: float = 0,
    master_unpaid: float | None = None,
) -> None:
    unpaid = tot - master_paid if master_unpaid is None else master_unpaid
    cur.execute(
        """
        INSERT INTO t_sales_master(
            sales_no, farm_cd, sales_dt, sales_status, sales_source,
            custm_id, order_no, tot_sales_amt, tot_paid_amt, tot_unpaid_amt
        ) VALUES (?,?,?,?,?,?,?,?,?,?)
        """,
        (
            sales_no,
            farm_cd,
            sales_dt,
            sales_status,
            sales_source,
            custm_id,
            order_no,
            tot,
            master_paid,
            unpaid,
        ),
    )


def _insert_detail(
    cur: sqlite3.Cursor,
    *,
    sale_detail_no: str,
    sales_no: str,
    farm_cd: str = FARM_A,
    item_cd: str = "FR010100",
    variety_cd: str = "FR010101",
    grade_cd: str = "GR010100",
    size_cd: str = "SZ010100",
    weight: float = 15,
) -> None:
    cur.execute(
        """
        INSERT INTO t_sales_detail(
            sale_detail_no, sales_no, farm_cd, item_cd,
            variety_cd, grade_cd, size_cd, weight, qty
        ) VALUES (?,?,?,?,?,?,?,?,?)
        """,
        (
            sale_detail_no,
            sales_no,
            farm_cd,
            item_cd,
            variety_cd,
            grade_cd,
            size_cd,
            weight,
            1,
        ),
    )


def _insert_cash(
    cur: sqlite3.Cursor,
    *,
    paid_detail_no: str,
    sales_no: str,
    farm_cd: str = FARM_A,
    pay_amt: float,
) -> None:
    cur.execute(
        """
        INSERT INTO t_cash_ledger(
            paid_detail_no, sales_no, farm_cd, pay_dt, pay_method_cd, pay_amt
        ) VALUES (?,?,?,?,?,?)
        """,
        (paid_detail_no, sales_no, farm_cd, "2026-08-22", "AS010101", pay_amt),
    )


class SalesQueryServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.path, self.conn = _open_db()
        self.svc = SalesQueryService(self.conn)

    def tearDown(self) -> None:
        self.conn.close()
        self.path.unlink(missing_ok=True)

    def test_farm_scope(self) -> None:
        cur = self.conn.cursor()
        _insert_sale(cur, sales_no="20260822-01", farm_cd=FARM_A)
        _insert_sale(cur, sales_no="20260822-01", farm_cd=FARM_B, custm_id="C001")
        self.conn.commit()
        res = self.svc.list_sales(FARM_A)
        self.assertEqual(res["total"], 1)
        self.assertEqual(res["items"][0]["sales_no"], "20260822-01")

    def test_multi_farm_same_sales_no_isolated(self) -> None:
        cur = self.conn.cursor()
        _insert_sale(cur, sales_no="S-SAME", farm_cd=FARM_A, tot=100000)
        _insert_sale(cur, sales_no="S-SAME", farm_cd=FARM_B, tot=200000, custm_id="C001")
        _insert_cash(cur, paid_detail_no="P-A", sales_no="S-SAME", farm_cd=FARM_A, pay_amt=40000)
        _insert_cash(cur, paid_detail_no="P-B", sales_no="S-SAME", farm_cd=FARM_B, pay_amt=80000)
        self.conn.commit()
        a = self.svc.list_sales(FARM_A)["items"][0]
        b = self.svc.list_sales(FARM_B)["items"][0]
        self.assertEqual(a["paid_amt"], 40000)
        self.assertEqual(b["paid_amt"], 80000)

    def test_confirmed_and_draft_listed(self) -> None:
        cur = self.conn.cursor()
        _insert_sale(cur, sales_no="C-01", sales_status=SALES_STATUS_CONFIRMED)
        _insert_sale(cur, sales_no="D-01", sales_status=SALES_STATUS_DRAFT)
        self.conn.commit()
        res = self.svc.list_sales(FARM_A)
        self.assertEqual(res["total"], 2)
        statuses = {row["sales_status"] for row in res["items"]}
        self.assertEqual(statuses, {SALES_STATUS_CONFIRMED, SALES_STATUS_DRAFT})

    def test_sales_status_filter(self) -> None:
        cur = self.conn.cursor()
        _insert_sale(cur, sales_no="C-01", sales_status=SALES_STATUS_CONFIRMED)
        _insert_sale(cur, sales_no="D-01", sales_status=SALES_STATUS_DRAFT)
        self.conn.commit()
        res = self.svc.list_sales(FARM_A, sales_status=SALES_STATUS_DRAFT)
        self.assertEqual(res["total"], 1)
        self.assertEqual(res["items"][0]["sales_no"], "D-01")

    def test_payment_filters(self) -> None:
        cur = self.conn.cursor()
        _insert_sale(cur, sales_no="U-01", tot=100000)
        _insert_sale(cur, sales_no="P-01", tot=100000)
        _insert_sale(cur, sales_no="F-01", tot=100000)
        _insert_cash(cur, paid_detail_no="U-P1", sales_no="U-01", pay_amt=0)
        _insert_cash(cur, paid_detail_no="P-P1", sales_no="P-01", pay_amt=40000)
        _insert_cash(cur, paid_detail_no="F-P1", sales_no="F-01", pay_amt=100000)
        self.conn.commit()
        unpaid = self.svc.list_sales(FARM_A, payment_status=PAYMENT_STATUS_UNPAID)
        partial = self.svc.list_sales(FARM_A, payment_status=PAYMENT_STATUS_PARTIAL)
        paid = self.svc.list_sales(FARM_A, payment_status=PAYMENT_STATUS_PAID)
        self.assertEqual({r["sales_no"] for r in unpaid["items"]}, {"U-01"})
        self.assertEqual({r["sales_no"] for r in partial["items"]}, {"P-01"})
        self.assertEqual({r["sales_no"] for r in paid["items"]}, {"F-01"})

    def test_payment_filter_excludes_draft(self) -> None:
        cur = self.conn.cursor()
        _insert_sale(cur, sales_no="D-01", sales_status=SALES_STATUS_DRAFT, tot=100000)
        self.conn.commit()
        res = self.svc.list_sales(FARM_A, payment_status=PAYMENT_STATUS_UNPAID)
        self.assertEqual(res["total"], 0)

    def test_cash_sum_statuses(self) -> None:
        cur = self.conn.cursor()
        _insert_sale(cur, sales_no="U-01", tot=950000)
        _insert_sale(cur, sales_no="P-01", tot=950000)
        _insert_sale(cur, sales_no="F-01", tot=950000)
        _insert_cash(cur, paid_detail_no="P1", sales_no="P-01", pay_amt=350000)
        _insert_cash(cur, paid_detail_no="P2", sales_no="P-01", pay_amt=450000)
        _insert_cash(cur, paid_detail_no="F1", sales_no="F-01", pay_amt=950000)
        self.conn.commit()
        by_no = {r["sales_no"]: r for r in self.svc.list_sales(FARM_A)["items"]}
        self.assertEqual(by_no["U-01"]["payment_status"], PAYMENT_STATUS_UNPAID)
        self.assertEqual(by_no["P-01"]["payment_status"], PAYMENT_STATUS_PARTIAL)
        self.assertEqual(by_no["P-01"]["paid_amt"], 800000)
        self.assertEqual(by_no["F-01"]["payment_status"], PAYMENT_STATUS_PAID)

    def test_master_paid_ignored_cash_is_ssot(self) -> None:
        cur = self.conn.cursor()
        _insert_sale(
            cur,
            sales_no="M-01",
            tot=100000,
            master_paid=99999,
            master_unpaid=1,
        )
        _insert_cash(cur, paid_detail_no="C1", sales_no="M-01", pay_amt=10000)
        self.conn.commit()
        row = self.svc.list_sales(FARM_A)["items"][0]
        self.assertEqual(row["paid_amt"], 10000)
        self.assertEqual(row["unpaid_amt"], 90000)
        self.assertEqual(row["payment_status"], PAYMENT_STATUS_PARTIAL)

    def test_legacy_ymd_date_filter(self) -> None:
        cur = self.conn.cursor()
        _insert_sale(cur, sales_no="L-01", sales_dt="20260128")
        self.conn.commit()
        res = self.svc.list_sales(
            FARM_A, from_date="2026-01-01", to_date="2026-01-31"
        )
        self.assertEqual(res["total"], 1)
        self.assertEqual(res["items"][0]["sales_dt"], "2026-01-28")

    def test_iso_date_filter(self) -> None:
        cur = self.conn.cursor()
        _insert_sale(cur, sales_no="I-01", sales_dt="2026-08-15")
        _insert_sale(cur, sales_no="I-02", sales_dt="2026-07-01")
        self.conn.commit()
        res = self.svc.list_sales(
            FARM_A, from_date="2026-08-01", to_date="2026-08-31"
        )
        self.assertEqual(res["total"], 1)
        self.assertEqual(res["items"][0]["sales_no"], "I-01")

    def test_keyword_search(self) -> None:
        cur = self.conn.cursor()
        _insert_sale(cur, sales_no="20260822-01", custm_id="C001", order_no="ORD001")
        _insert_sale(cur, sales_no="20260822-02", custm_id="C002", order_no=None)
        self.conn.commit()
        by_cust = self.svc.list_sales(FARM_A, keyword="홍길")
        by_sales = self.svc.list_sales(FARM_A, keyword="20260822-02")
        by_order = self.svc.list_sales(FARM_A, keyword="ORD001")
        self.assertEqual(by_cust["total"], 1)
        self.assertEqual(by_sales["items"][0]["sales_no"], "20260822-02")
        self.assertEqual(by_order["items"][0]["sales_no"], "20260822-01")

    def test_pagination_and_sort(self) -> None:
        cur = self.conn.cursor()
        for idx, dt in enumerate(["2026-08-01", "2026-08-03", "2026-08-02"], start=1):
            _insert_sale(cur, sales_no=f"2026080{idx}-01", sales_dt=dt)
        self.conn.commit()
        page1 = self.svc.list_sales(FARM_A, page=1, page_size=2)
        page2 = self.svc.list_sales(FARM_A, page=2, page_size=2)
        self.assertEqual(page1["total"], 3)
        self.assertEqual(len(page1["items"]), 2)
        self.assertEqual(len(page2["items"]), 1)
        ordered = [r["sales_no"] for r in page1["items"]] + [
            r["sales_no"] for r in page2["items"]
        ]
        self.assertEqual(ordered[0], "20260802-01")
        self.assertEqual(ordered[1], "20260803-01")

    def test_one_row_per_sale_with_multiple_details(self) -> None:
        cur = self.conn.cursor()
        _insert_sale(cur, sales_no="MULTI-01", tot=200000)
        _insert_detail(cur, sale_detail_no="MULTI-01-S01", sales_no="MULTI-01")
        _insert_detail(cur, sale_detail_no="MULTI-01-S02", sales_no="MULTI-01")
        _insert_cash(cur, paid_detail_no="C1", sales_no="MULTI-01", pay_amt=50000)
        _insert_cash(cur, paid_detail_no="C2", sales_no="MULTI-01", pay_amt=30000)
        self.conn.commit()
        res = self.svc.list_sales(FARM_A)
        self.assertEqual(res["total"], 1)
        row = res["items"][0]
        self.assertEqual(row["paid_amt"], 80000)
        self.assertEqual(row["rep_variety_nm"], "신고")

    def test_rep_detail_deterministic(self) -> None:
        cur = self.conn.cursor()
        _insert_sale(cur, sales_no="REP-01")
        _insert_detail(
            cur,
            sale_detail_no="REP-01-S02",
            sales_no="REP-01",
            variety_cd="FR010102",
        )
        _insert_detail(
            cur,
            sale_detail_no="REP-01-S01",
            sales_no="REP-01",
            variety_cd="FR010101",
        )
        self.conn.commit()
        row = self.svc.list_sales(FARM_A)["items"][0]
        self.assertEqual(row["rep_variety_cd"], "FR010101")
        self.assertEqual(row["rep_variety_nm"], "신고")

    def test_draft_payment_status_null(self) -> None:
        self.assertIsNone(
            compute_payment_status(SALES_STATUS_DRAFT, 100000, 0)
        )

    def test_zero_total_zero_paid_unpaid_filter_exclusive(self) -> None:
        cur = self.conn.cursor()
        _insert_sale(cur, sales_no="Z-01", tot=0)
        self.conn.commit()
        row = self.svc.list_sales(FARM_A)["items"][0]
        self.assertEqual(
            compute_payment_status(SALES_STATUS_CONFIRMED, 0, 0),
            PAYMENT_STATUS_UNPAID,
        )
        self.assertEqual(row["payment_status"], PAYMENT_STATUS_UNPAID)
        unpaid = self.svc.list_sales(FARM_A, payment_status=PAYMENT_STATUS_UNPAID)
        partial = self.svc.list_sales(FARM_A, payment_status=PAYMENT_STATUS_PARTIAL)
        paid = self.svc.list_sales(FARM_A, payment_status=PAYMENT_STATUS_PAID)
        self.assertEqual({r["sales_no"] for r in unpaid["items"]}, {"Z-01"})
        self.assertEqual(partial["total"], 0)
        self.assertEqual(paid["total"], 0)

    def test_payment_filter_mutual_exclusive(self) -> None:
        cur = self.conn.cursor()
        cases = [
            ("U-01", 100000, 0, PAYMENT_STATUS_UNPAID),
            ("P-01", 100000, 40000, PAYMENT_STATUS_PARTIAL),
            ("F-01", 100000, 100000, PAYMENT_STATUS_PAID),
            ("O-01", 100000, 120000, PAYMENT_STATUS_PAID),
        ]
        for sales_no, tot, paid, expected in cases:
            _insert_sale(cur, sales_no=sales_no, tot=tot)
            if paid:
                _insert_cash(
                    cur,
                    paid_detail_no=f"{sales_no}-P1",
                    sales_no=sales_no,
                    pay_amt=paid,
                )
            self.assertEqual(
                compute_payment_status(SALES_STATUS_CONFIRMED, tot, paid),
                expected,
            )
        self.conn.commit()
        by_filter = {
            PAYMENT_STATUS_UNPAID: self.svc.list_sales(
                FARM_A, payment_status=PAYMENT_STATUS_UNPAID
            ),
            PAYMENT_STATUS_PARTIAL: self.svc.list_sales(
                FARM_A, payment_status=PAYMENT_STATUS_PARTIAL
            ),
            PAYMENT_STATUS_PAID: self.svc.list_sales(
                FARM_A, payment_status=PAYMENT_STATUS_PAID
            ),
        }
        self.assertEqual(
            {r["sales_no"] for r in by_filter[PAYMENT_STATUS_UNPAID]["items"]},
            {"U-01"},
        )
        self.assertEqual(
            {r["sales_no"] for r in by_filter[PAYMENT_STATUS_PARTIAL]["items"]},
            {"P-01"},
        )
        self.assertEqual(
            {r["sales_no"] for r in by_filter[PAYMENT_STATUS_PAID]["items"]},
            {"F-01", "O-01"},
        )
        seen: set[str] = set()
        for flt, res in by_filter.items():
            for row in res["items"]:
                sno = row["sales_no"]
                self.assertNotIn(sno, seen, f"{sno} duplicated in {flt}")
                seen.add(sno)

    def test_draft_excluded_from_payment_filters(self) -> None:
        cur = self.conn.cursor()
        for idx, paid in enumerate((0, 50000, 100000), start=1):
            _insert_sale(
                cur,
                sales_no=f"D-{idx}",
                sales_status=SALES_STATUS_DRAFT,
                tot=100000,
            )
            if paid:
                _insert_cash(
                    cur,
                    paid_detail_no=f"D-{idx}-P1",
                    sales_no=f"D-{idx}",
                    pay_amt=paid,
                )
        self.conn.commit()
        for flt in (
            PAYMENT_STATUS_UNPAID,
            PAYMENT_STATUS_PARTIAL,
            PAYMENT_STATUS_PAID,
        ):
            res = self.svc.list_sales(FARM_A, payment_status=flt)
            self.assertEqual(res["total"], 0)

    def test_invalid_from_date_raises(self) -> None:
        with self.assertRaises(SalesQueryValidationError) as ctx:
            self.svc.list_sales(FARM_A, from_date="abc")
        self.assertEqual(ctx.exception.message, MSG_SALES_DATE_INVALID)

    def test_invalid_to_date_raises(self) -> None:
        with self.assertRaises(SalesQueryValidationError) as ctx:
            self.svc.list_sales(FARM_A, to_date="2026-99-99")
        self.assertEqual(ctx.exception.message, MSG_SALES_DATE_INVALID)

    def test_invalid_filters(self) -> None:
        with self.assertRaises(SalesQueryValidationError):
            self.svc.list_sales(FARM_A, sales_status="PAID")
        with self.assertRaises(SalesQueryValidationError):
            self.svc.list_sales(FARM_A, payment_status="DRAFT")


if __name__ == "__main__":
    unittest.main()
