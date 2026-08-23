# -*- coding: utf-8 -*-
"""판매 목록 Stage 5 FastAPI — GET /sales."""

from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

_HERE = Path(__file__).resolve()
_SERVER = _HERE.parents[1]
_ROOT = _HERE.parents[2]
for p in (_HERE.parent, _ROOT, _SERVER):
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)

_fd, _SETTINGS_SQLITE = tempfile.mkstemp(suffix=".db")
os.close(_fd)
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_NAME", "test")
os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("SQLITE_DB_PATH", _SETTINGS_SQLITE)

from fastapi.testclient import TestClient  # noqa: E402

from app.api.dependencies import get_sales_api_service  # noqa: E402
from app.main import app  # noqa: E402
from app.services.sales_api_service import SalesApiService  # noqa: E402
from core.ops_biz_date import today_ops_iso  # noqa: E402
from core.sales_payment_constants import (  # noqa: E402
    MSG_PAY_AMT_OVER_UNPAID,
    MSG_PAY_DT_BEFORE_SALES,
    MSG_PAY_DT_FUTURE,
    MSG_PAY_DT_INVALID,
    MSG_SALES_DRAFT_PAYMENT_FORBIDDEN,
    PAYMENT_STATUS_PAID,
    PAYMENT_STATUS_PARTIAL,
)
from test_sales_query_service import (  # noqa: E402
    FARM_A,
    _insert_cash,
    _insert_sale,
    _schema_sql,
)

FARM = FARM_A


def _iso_offset(iso: str, days: int) -> str:
    return (date.fromisoformat(iso) + timedelta(days=days)).isoformat()


def _extend_write_schema(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(t_cash_ledger)")
    cash_cols = {row[1] for row in cur.fetchall()}
    for col, ddl in (
        ("rmk", "ALTER TABLE t_cash_ledger ADD COLUMN rmk TEXT"),
        ("reg_id", "ALTER TABLE t_cash_ledger ADD COLUMN reg_id TEXT"),
        ("reg_dt", "ALTER TABLE t_cash_ledger ADD COLUMN reg_dt TEXT"),
    ):
        if col not in cash_cols:
            cur.execute(ddl)
    cur.execute("PRAGMA table_info(t_sales_master)")
    master_cols = {row[1] for row in cur.fetchall()}
    for col, ddl in (
        ("mod_id", "ALTER TABLE t_sales_master ADD COLUMN mod_id TEXT"),
        ("mod_dt", "ALTER TABLE t_sales_master ADD COLUMN mod_dt TEXT"),
    ):
        if col not in master_cols:
            cur.execute(ddl)


def _ledger_schema_sql() -> str:
    return """
        CREATE TABLE IF NOT EXISTS t_ledger (
            slip_no TEXT PRIMARY KEY, farm_cd TEXT NOT NULL, trans_dt TEXT,
            trans_type_cd TEXT, acct_cd TEXT, trans_amt REAL, rmk TEXT,
            ref_id TEXT, parent_slip_no TEXT, trans_st TEXT DEFAULT '10',
            reg_id TEXT, reg_dt TEXT, mod_id TEXT, mod_dt TEXT
        );
    """


def _tmp_db() -> Path:
    fd, name = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    path = Path(name)
    conn = sqlite3.connect(str(path))
    conn.executescript(_schema_sql())
    cur = conn.cursor()
    _insert_sale(cur, sales_no="20260822-01", tot=950000)
    _insert_cash(cur, paid_detail_no="P1", sales_no="20260822-01", pay_amt=800000)
    conn.commit()
    conn.close()
    return path


class SalesApiStage5Test(unittest.TestCase):
    def setUp(self) -> None:
        self.path = _tmp_db()
        self.svc = SalesApiService(self.path)
        app.dependency_overrides[get_sales_api_service] = lambda: self.svc
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.pop(get_sales_api_service, None)
        self.path.unlink(missing_ok=True)

    def test_get_sales_list(self) -> None:
        res = self.client.get(f"/api/v1/farms/{FARM}/sales")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["total"], 1)
        self.assertEqual(body["page"], 1)
        self.assertEqual(body["page_size"], 20)
        item = body["items"][0]
        self.assertEqual(item["sales_no"], "20260822-01")
        self.assertEqual(item["paid_amt"], 800000)
        self.assertEqual(item["payment_status"], "PARTIAL")

    def test_get_sales_query_filters(self) -> None:
        res = self.client.get(
            f"/api/v1/farms/{FARM}/sales",
            params={
                "from_date": "2026-08-01",
                "to_date": "2026-08-31",
                "payment_status": "PARTIAL",
                "page": 1,
                "page_size": 20,
            },
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["total"], 1)

    def test_invalid_from_date_returns_400(self) -> None:
        res = self.client.get(
            f"/api/v1/farms/{FARM}/sales",
            params={"from_date": "abc"},
        )
        self.assertEqual(res.status_code, 400)

    def test_invalid_to_date_returns_400(self) -> None:
        res = self.client.get(
            f"/api/v1/farms/{FARM}/sales",
            params={"to_date": "2026-99-99"},
        )
        self.assertEqual(res.status_code, 400)

    def test_valid_date_range_returns_200(self) -> None:
        res = self.client.get(
            f"/api/v1/farms/{FARM}/sales",
            params={"from_date": "2026-08-01", "to_date": "2026-08-31"},
        )
        self.assertEqual(res.status_code, 200)

    def test_get_sale_detail(self) -> None:
        res = self.client.get(f"/api/v1/farms/{FARM}/sales/20260822-01")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["sales_no"], "20260822-01")
        self.assertEqual(body["paid_amt"], 800000)
        self.assertEqual(body["payment_status"], "PARTIAL")

    def test_get_sale_detail_not_found(self) -> None:
        res = self.client.get(f"/api/v1/farms/{FARM}/sales/NO-SUCH")
        self.assertEqual(res.status_code, 404)

    def test_get_sale_payments(self) -> None:
        res = self.client.get(f"/api/v1/farms/{FARM}/sales/20260822-01/payments")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["sales_no"], "20260822-01")
        self.assertEqual(body["paid_amt"], 800000)
        self.assertEqual(body["unpaid_amt"], 150000)
        self.assertEqual(body["payment_status"], "PARTIAL")
        self.assertEqual(len(body["payments"]), 1)
        p = body["payments"][0]
        self.assertEqual(p["payment_source"], "GENERAL")
        self.assertIsNone(p["source_order_no"])
        self.assertEqual(p["pay_method_nm"], "현금 (시재)")
        self.assertNotIn("collection_status", body)
        self.assertNotIn("slip_no", p)

    def test_get_sale_payments_not_found(self) -> None:
        res = self.client.get(f"/api/v1/farms/{FARM}/sales/NO-SUCH/payments")
        self.assertEqual(res.status_code, 404)

    def test_get_sale_payments_provenance_and_n_rows(self) -> None:
        conn = sqlite3.connect(str(self.path))
        cur = conn.cursor()
        _insert_sale(
            cur,
            sales_no="20260822-02",
            tot=200000,
            order_no="ORD20260822-001",
        )
        _insert_cash(
            cur,
            paid_detail_no="20260822-02-P01",
            sales_no="20260822-02",
            pay_amt=50000,
            pay_method_cd="AS010102",
            order_no="ORD20260822-001",
            slip_no="SL-SAME",
        )
        _insert_cash(
            cur,
            paid_detail_no="20260822-02-P02",
            sales_no="20260822-02",
            pay_amt=30000,
            pay_method_cd="AS010102",
            slip_no="SL-SAME",
        )
        conn.commit()
        conn.close()
        res = self.client.get(f"/api/v1/farms/{FARM}/sales/20260822-02/payments")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(len(body["payments"]), 2)
        self.assertEqual(body["payments"][0]["payment_source"], "ORDER_PREPAY")
        self.assertEqual(body["payments"][0]["source_order_no"], "ORD20260822-001")
        self.assertEqual(body["payments"][1]["payment_source"], "GENERAL")
        self.assertEqual(body["payments"][0]["pay_method_nm"], "농협은행")
        self.assertEqual(body["paid_amt"], 80000)

    def test_get_sale_payments_draft(self) -> None:
        conn = sqlite3.connect(str(self.path))
        cur = conn.cursor()
        _insert_sale(cur, sales_no="20260822-D", tot=100000, sales_status="DRAFT")
        conn.commit()
        conn.close()
        res = self.client.get(f"/api/v1/farms/{FARM}/sales/20260822-D/payments")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertIsNone(body["payment_status"])
        self.assertEqual(body["payments"], [])


class SalesApiStage6CPostTest(unittest.TestCase):
    def setUp(self) -> None:
        fd, name = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.path = Path(name)
        conn = sqlite3.connect(str(self.path))
        conn.executescript(_schema_sql())
        conn.executescript(_ledger_schema_sql())
        _extend_write_schema(conn)
        cur = conn.cursor()
        self.today = today_ops_iso()
        self.sales_dt = _iso_offset(self.today, -1)
        _insert_sale(
            cur,
            sales_no="20260822-PAY",
            sales_dt=self.sales_dt,
            tot=100000,
        )
        conn.commit()
        conn.close()
        self.svc = SalesApiService(self.path)
        app.dependency_overrides[get_sales_api_service] = lambda: self.svc
        self.client = TestClient(app)
        self.url = f"/api/v1/farms/{FARM}/sales/20260822-PAY/payments"

    def tearDown(self) -> None:
        app.dependency_overrides.pop(get_sales_api_service, None)
        self.path.unlink(missing_ok=True)

    def _post(self, payload: dict, *, user: str | None = "TESTUSER") -> object:
        headers = {"X-User-Id": user} if user is not None else {}
        return self.client.post(self.url, json=payload, headers=headers)

    def test_post_confirmed_ok(self) -> None:
        res = self._post(
            {"pay_dt": self.today, "pay_amt": 40000, "pay_method_cd": "AS010101"}
        )
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["paid_amt"], 40000)
        self.assertEqual(body["unpaid_amt"], 60000)
        self.assertEqual(body["payment_status"], PAYMENT_STATUS_PARTIAL)
        self.assertEqual(len(body["payments"]), 1)
        self.assertEqual(body["payments"][0]["payment_source"], "GENERAL")
        self.assertIsNone(body["payments"][0]["source_order_no"])

    def test_post_default_user_mobile(self) -> None:
        res = self._post(
            {"pay_dt": self.today, "pay_amt": 10000, "pay_method_cd": "AS010102"},
            user=None,
        )
        self.assertEqual(res.status_code, 200)
        conn = sqlite3.connect(str(self.path))
        reg_id = conn.execute(
            "SELECT reg_id FROM t_cash_ledger WHERE sales_no='20260822-PAY'"
        ).fetchone()[0]
        conn.close()
        self.assertEqual(reg_id, "MOBILE")

    def test_post_draft_400(self) -> None:
        conn = sqlite3.connect(str(self.path))
        cur = conn.cursor()
        _insert_sale(cur, sales_no="20260822-DR", sales_status="DRAFT", tot=50000)
        conn.commit()
        conn.close()
        res = self.client.post(
            f"/api/v1/farms/{FARM}/sales/20260822-DR/payments",
            json={"pay_dt": self.today, "pay_amt": 1000, "pay_method_cd": "AS010101"},
            headers={"X-User-Id": "T"},
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn(MSG_SALES_DRAFT_PAYMENT_FORBIDDEN, res.json()["detail"])

    def test_post_overpay_400(self) -> None:
        res = self._post(
            {"pay_dt": self.today, "pay_amt": 200000, "pay_method_cd": "AS010101"}
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn(MSG_PAY_AMT_OVER_UNPAID, res.json()["detail"])

    def test_post_invalid_method_400(self) -> None:
        res = self._post(
            {"pay_dt": self.today, "pay_amt": 1000, "pay_method_cd": "AS020101"}
        )
        self.assertEqual(res.status_code, 400)

    def test_post_before_sales_date_400(self) -> None:
        res = self._post(
            {
                "pay_dt": _iso_offset(self.sales_dt, -1),
                "pay_amt": 1000,
                "pay_method_cd": "AS010101",
            }
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn(MSG_PAY_DT_BEFORE_SALES, res.json()["detail"])

    def test_post_future_date_400(self) -> None:
        res = self._post(
            {
                "pay_dt": _iso_offset(self.today, 1),
                "pay_amt": 1000,
                "pay_method_cd": "AS010101",
            }
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn(MSG_PAY_DT_FUTURE, res.json()["detail"])

    def test_post_blank_pay_dt_400(self) -> None:
        res = self._post(
            {"pay_dt": "", "pay_amt": 1000, "pay_method_cd": "AS010101"}
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn(MSG_PAY_DT_INVALID, res.json()["detail"])

    def test_post_not_found_404(self) -> None:
        res = self.client.post(
            f"/api/v1/farms/{FARM}/sales/NO-SUCH/payments",
            json={"pay_dt": self.today, "pay_amt": 1000, "pay_method_cd": "AS010101"},
            headers={"X-User-Id": "T"},
        )
        self.assertEqual(res.status_code, 404)

    def test_post_full_payment(self) -> None:
        res = self._post(
            {"pay_dt": self.today, "pay_amt": 100000, "pay_method_cd": "AS010101"}
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["payment_status"], PAYMENT_STATUS_PAID)
        self.assertEqual(res.json()["unpaid_amt"], 0)

    def test_post_second_payment_appends(self) -> None:
        r1 = self._post(
            {"pay_dt": self.today, "pay_amt": 30000, "pay_method_cd": "AS010101"}
        )
        self.assertEqual(r1.status_code, 200)
        r2 = self._post(
            {"pay_dt": self.today, "pay_amt": 20000, "pay_method_cd": "AS010101"}
        )
        self.assertEqual(r2.status_code, 200)
        body = r2.json()
        self.assertEqual(len(body["payments"]), 2)
        self.assertEqual(body["paid_amt"], 50000)

    def test_get_payments_regression(self) -> None:
        self._post(
            {"pay_dt": self.today, "pay_amt": 25000, "pay_method_cd": "AS010103"}
        )
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["paid_amt"], 25000)


if __name__ == "__main__":
    unittest.main()
