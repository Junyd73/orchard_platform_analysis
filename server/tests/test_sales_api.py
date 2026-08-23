# -*- coding: utf-8 -*-
"""판매 목록 Stage 5 FastAPI — GET /sales."""

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
from test_sales_query_service import (  # noqa: E402
    FARM_A,
    _insert_cash,
    _insert_sale,
    _schema_sql,
)

FARM = FARM_A


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


if __name__ == "__main__":
    unittest.main()
