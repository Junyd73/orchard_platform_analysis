# -*- coding: utf-8 -*-
"""Stage 5C 판매출고 confirm API — T-SHIP-API-01~10."""

from __future__ import annotations

import os
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

from app.api.dependencies import get_order_ship_api_service  # noqa: E402
from app.main import app  # noqa: E402
from app.services.order_ship_api_service import OrderShipApiService  # noqa: E402
from core.order_constants import ORDER_STATUS_PREP_CD  # noqa: E402
from core.order_ship_constants import (  # noqa: E402
    SALES_STATUS_CONFIRMED,
    SHIP_MODE_DIRECT,
    SHIP_MODE_STOCK,
)
from test_order_ship_service import (  # noqa: E402
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
    _order,
)

URL = f"/api/v1/farms/{FARM}/shipments/confirm"


def _line(
    *,
    qty: float,
    order_detail_id: str | None = None,
    unit_price: float = 1000,
) -> dict:
    return {
        "qty": qty,
        "order_detail_id": order_detail_id,
        "item_cd": ITEM,
        "variety_cd": VARIETY,
        "grade_cd": GRADE,
        "size_cd": SIZE,
        "weight": WEIGHT,
        "harvest_year": YEAR,
        "wh_cd": WH,
        "unit_price": unit_price,
    }


class OrderShipApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.path, self.conn = _open()
        self.svc = OrderShipApiService(self.path)
        app.dependency_overrides[get_order_ship_api_service] = lambda: self.svc
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.pop(get_order_ship_api_service, None)
        self.conn.close()
        self.path.unlink(missing_ok=True)

    def _post(self, body: dict):
        return self.client.post(URL, json=body, headers={"X-User-Id": "T"})

    def test_t_ship_api_01_order_stock(self) -> None:
        _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=10)
        order_no = _order(self.conn, 10)
        _allocate(self.conn, order_no, 10)
        res = self._post(
            {
                "ship_mode": SHIP_MODE_STOCK,
                "sales_dt": "2026-08-19",
                "order_no": order_no,
                "lines": [_line(qty=6, order_detail_id=f"{order_no}-01")],
            }
        )
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertTrue(body["ok"])
        self.assertTrue(body["sales_no"])
        self.assertEqual(body["sales_status"], SALES_STATUS_CONFIRMED)
        self.assertEqual(body["ship_mode"], SHIP_MODE_STOCK)
        self.assertEqual(body["order_no"], order_no)
        self.assertEqual(len(body["details"]), 1)
        self.assertAlmostEqual(float(body["details"][0]["qty"]), 6)
        self.assertIsNotNone(body["details"][0]["stock_seq"])
        self.assertEqual(body["order_status"], ORDER_STATUS_PREP_CD)

    def test_t_ship_api_02_order_direct(self) -> None:
        _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=15)
        order_no = _order(self.conn, 10)
        res = self._post(
            {
                "ship_mode": SHIP_MODE_DIRECT,
                "sales_dt": "2026-08-19",
                "order_no": order_no,
                "lines": [_line(qty=6, order_detail_id=f"{order_no}-01")],
            }
        )
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertEqual(body["ship_mode"], SHIP_MODE_DIRECT)
        self.assertEqual(body["order_no"], order_no)
        self.assertAlmostEqual(float(body["remaining_order_qty"]), 4)

    def test_t_ship_api_03_no_order_direct(self) -> None:
        _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=10)
        res = self._post(
            {
                "ship_mode": SHIP_MODE_DIRECT,
                "sales_dt": "2026-08-19",
                "lines": [_line(qty=3)],
            }
        )
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertIsNone(body["order_no"])
        self.assertIsNone(body["order_status"])
        self.assertEqual(len(body["details"]), 1)
        self.assertTrue(body["sales_no"])

    def test_t_ship_api_04_no_order_stock(self) -> None:
        _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=10)
        res = self._post(
            {
                "ship_mode": SHIP_MODE_STOCK,
                "sales_dt": "2026-08-19",
                "lines": [_line(qty=1)],
            }
        )
        self.assertEqual(res.status_code, 400, res.text)
        self.assertEqual(res.json()["error_code"], "SHIP_STOCK_REQUIRES_ORDER")

    def test_t_ship_api_05_over_ship(self) -> None:
        _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=15)
        order_no = _order(self.conn, 10)
        res = self._post(
            {
                "ship_mode": SHIP_MODE_DIRECT,
                "order_no": order_no,
                "lines": [_line(qty=11, order_detail_id=f"{order_no}-01")],
            }
        )
        self.assertEqual(res.status_code, 409, res.text)
        self.assertEqual(res.json()["error_code"], "ORDER_OVER_SHIP")

    def test_t_ship_api_06_direct_short(self) -> None:
        _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=3)
        res = self._post(
            {
                "ship_mode": SHIP_MODE_DIRECT,
                "lines": [_line(qty=4)],
            }
        )
        self.assertEqual(res.status_code, 409, res.text)
        self.assertEqual(res.json()["error_code"], "STOCK_UNAVAILABLE")

    def test_t_ship_api_07_alloc_short(self) -> None:
        _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=10)
        order_no = _order(self.conn, 10)
        _allocate(self.conn, order_no, 6)
        res = self._post(
            {
                "ship_mode": SHIP_MODE_STOCK,
                "order_no": order_no,
                "lines": [_line(qty=7, order_detail_id=f"{order_no}-01")],
            }
        )
        self.assertEqual(res.status_code, 409, res.text)
        self.assertEqual(res.json()["error_code"], "ALLOC_OVER_SHIP")

    def test_t_ship_api_08_schema_precondition(self) -> None:
        self.conn.execute("DROP TABLE t_order_alloc")
        self.conn.commit()
        _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=10)
        order_no = _order(self.conn, 10)
        res = self._post(
            {
                "ship_mode": SHIP_MODE_STOCK,
                "order_no": order_no,
                "lines": [_line(qty=1, order_detail_id=f"{order_no}-01")],
            }
        )
        self.assertEqual(res.status_code, 409, res.text)
        self.assertEqual(res.json()["error_code"], "SCHEMA_PRECONDITION")

    def test_t_ship_api_09_fifo_two_rows(self) -> None:
        s1 = _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=6)
        s2 = _insert_stock(self.conn, storage_dt="2026-02-01", in_qty=4)
        order_no = _order(self.conn, 10)
        _allocate(self.conn, order_no, 10)
        res = self._post(
            {
                "ship_mode": SHIP_MODE_STOCK,
                "order_no": order_no,
                "lines": [_line(qty=10, order_detail_id=f"{order_no}-01")],
            }
        )
        self.assertEqual(res.status_code, 200, res.text)
        details = res.json()["details"]
        self.assertEqual(len(details), 2)
        self.assertEqual(int(details[0]["stock_seq"]), s1)
        self.assertAlmostEqual(float(details[0]["qty"]), 6)
        self.assertEqual(int(details[1]["stock_seq"]), s2)
        self.assertAlmostEqual(float(details[1]["qty"]), 4)
        self.assertNotIn("stock_seq", _line(qty=1))

    def test_t_ship_api_10_rollback(self) -> None:
        seq = _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=3)
        res = self._post(
            {
                "ship_mode": SHIP_MODE_DIRECT,
                "lines": [_line(qty=4)],
            }
        )
        self.assertEqual(res.status_code, 409, res.text)
        self.conn.commit()
        out_qty = float(
            self.conn.execute(
                "SELECT COALESCE(SUM(out_qty),0) FROM t_stock_master WHERE stock_seq=?",
                (seq,),
            ).fetchone()[0]
        )
        sales = self.conn.execute("SELECT COUNT(*) FROM t_sales_master").fetchone()[0]
        self.assertAlmostEqual(out_qty, 0)
        self.assertEqual(sales, 0)

    def test_stock_seq_rejected_in_request(self) -> None:
        _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=10)
        body = {
            "ship_mode": SHIP_MODE_DIRECT,
            "lines": [{**_line(qty=1), "stock_seq": 99}],
        }
        res = self._post(body)
        self.assertEqual(res.status_code, 422, res.text)


if __name__ == "__main__":
    unittest.main()
