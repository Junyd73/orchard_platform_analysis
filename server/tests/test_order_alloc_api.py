# -*- coding: utf-8 -*-
"""배정 API Stage 3A."""

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

from app.api.dependencies import get_order_api_service  # noqa: E402
from app.main import app  # noqa: E402
from app.services.order_api_service import OrderApiService  # noqa: E402
from core.order_alloc_migrate import ensure_order_alloc_schema  # noqa: E402
from core.order_constants import WAREHOUSE_CD_DEFAULT  # noqa: E402
from test_order_service import _schema_sql  # noqa: E402

FARM = "OR001"


def _tmp_db() -> Path:
    fd, name = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    path = Path(name)
    conn = sqlite3.connect(str(path))
    conn.executescript(_schema_sql())
    ensure_order_alloc_schema(conn, skip_preflight=True)
    conn.execute(
        """
        INSERT INTO t_stock_master (
            farm_cd, wh_cd, item_cd, variety_cd, grade_cd, size_cd,
            weight, harvest_year, storage_dt, in_qty, out_qty, reserved_qty, reg_id
        ) VALUES (?, ?, 'FR010100', 'FR010101', 'GR010100', 'SZ010100',
                  15, 2026, '2026-01-01', 30, 0, 0, 'T')
        """,
        (FARM, WAREHOUSE_CD_DEFAULT),
    )
    conn.commit()
    conn.close()
    return path


class OrderAllocApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.path = _tmp_db()
        self.svc = OrderApiService(self.path)
        app.dependency_overrides[get_order_api_service] = lambda: self.svc
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.pop(get_order_api_service, None)
        self.path.unlink(missing_ok=True)

    def _create(self) -> str:
        body = {
            "custm_id": "C001",
            "lines": [
                {
                    "variety_cd": "FR010101",
                    "weight": 15,
                    "grade_cd": "GR010100",
                    "size_cd": "SZ010100",
                    "qty": 100,
                    "unit_price": 1000,
                    "harvest_year": 2026,
                    "deliveries": [
                        {"delivery_tp_cd": "LO010100", "qty": 100}
                    ],
                }
            ],
        }
        res = self.client.post(f"/api/v1/farms/{FARM}/orders", json=body)
        self.assertEqual(res.status_code, 200, res.text)
        return res.json()["order_no"]

    def test_auto_allocate_and_fruit_stock(self) -> None:
        order_no = self._create()
        det = f"{order_no}-01"
        res = self.client.post(
            f"/api/v1/farms/{FARM}/orders/{order_no}/allocations",
            json={"order_detail_id": det, "auto": True},
        )
        self.assertEqual(res.status_code, 200, res.text)
        line = res.json()["details"][0]
        self.assertEqual(line["allocated_qty"], 30)
        stock = self.client.get(f"/api/v1/farms/{FARM}/fruit-stock")
        self.assertEqual(stock.status_code, 200)
        self.assertEqual(stock.json()[0]["available_qty"], 0)
        got = self.client.get(f"/api/v1/farms/{FARM}/orders/{order_no}/allocations")
        self.assertEqual(got.status_code, 200)
        rel = self.client.post(
            f"/api/v1/farms/{FARM}/orders/{order_no}/allocations/release",
            json={"order_detail_id": det, "qty": 10},
        )
        self.assertEqual(rel.status_code, 200, rel.text)
        self.assertEqual(rel.json()["details"][0]["allocated_qty"], 20)

    def test_order_ok_without_allocate_call(self) -> None:
        order_no = self._create()
        res = self.client.get(f"/api/v1/farms/{FARM}/orders/{order_no}")
        self.assertEqual(res.status_code, 200, res.text)
        line = res.json()["lines"][0]
        self.assertEqual(line["allocated_qty"], 0)
        self.assertEqual(line["unallocated_qty"], 100)
        listed = self.client.get(f"/api/v1/farms/{FARM}/orders")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()["total"], 1)
        alloc = self.client.get(
            f"/api/v1/farms/{FARM}/orders/{order_no}/allocations"
        )
        self.assertEqual(alloc.status_code, 200, alloc.text)
        self.assertEqual(alloc.json()["details"][0]["allocated_qty"], 0)
        self.assertEqual(alloc.json()["details"][0]["allocations"], [])
