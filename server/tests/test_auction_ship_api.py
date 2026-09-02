# -*- coding: utf-8 -*-
"""DEC-036-B — auction shipment REST API tests."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
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

from app.api.dependencies import get_auction_ship_api_service  # noqa: E402
from app.main import app  # noqa: E402
from app.services.auction_ship_api_service import AuctionShipApiService  # noqa: E402
from core.auction_ship_constants import (  # noqa: E402
    AUCTION_SHIP_STATUS_IN_TRANSIT,
    CODE_AUCTION_SHIP_QTY_UNAVAILABLE,
    CODE_AUCTION_SHIP_SCHEMA,
    CODE_AUCTION_SHIP_STOCK_SCHEMA,
    TABLE_AUCTION_SHIP_DETAIL,
    TABLE_AUCTION_SHIP_MASTER,
)
from core.auction_ship_schema import ensure_auction_ship_schema  # noqa: E402
from test_auction_ship_service import (  # noqa: E402
    CORP,
    FARM,
    ITEM,
    MARKET_CD,
    MARKET_NM,
    VARIETY,
    WAREHOUSE_CD_DEFAULT,
    WEIGHT,
    YEAR,
    _insert_stock,
    _insert_stock_legacy,
    _open_legacy_auction,
    _open_ops,
    _payload,
    _spec_line,
)
from test_order_service import _open_tmp  # noqa: E402

OTHER_FARM = "OR999"


def _url(farm: str = FARM) -> str:
    return f"/api/v1/farms/{farm}/auction-shipments"


def _line(qty: float, *, size_cd: str = "FR020101") -> dict:
    return {
        "wh_cd": WAREHOUSE_CD_DEFAULT,
        "item_cd": ITEM,
        "variety_cd": VARIETY,
        "grade_cd": "GR010100",
        "size_cd": size_cd,
        "weight": WEIGHT,
        "harvest_year": YEAR,
        "qty": qty,
    }


def _body(*qtys: float, size_cd: str = "FR020101") -> dict:
    return {
        "ship_dt": "2026-08-31",
        "market_cd": MARKET_CD,
        "market_name": MARKET_NM,
        "corporation_name": CORP,
        "lines": [_line(q, size_cd=size_cd) for q in qtys],
    }


class AuctionShipApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.path, self.conn = _open_ops()
        self.svc = AuctionShipApiService(self.path)
        app.dependency_overrides[get_auction_ship_api_service] = lambda: self.svc
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.pop(get_auction_ship_api_service, None)
        self.conn.close()
        self.path.unlink(missing_ok=True)

    def _post(self, body: dict, farm: str = FARM):
        return self.client.post(
            _url(farm),
            json=body,
            headers={"X-User-Id": "MOBILE"},
        )

    def _get(self, farm: str = FARM):
        return self.client.get(_url(farm))

    def test_t_auc_api_01_single_spec_create(self) -> None:
        _insert_stock(self.conn, storage_dt="2025-10-01", in_qty=20)
        res = self._post(_body(10))
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertTrue(body["shipment_id"].startswith("AUC"))
        self.assertEqual(body["status"], AUCTION_SHIP_STATUS_IN_TRANSIT)
        self.assertAlmostEqual(body["total_shipped_qty"], 10.0)
        self.assertEqual(body["spec_count"], 1)
        self.assertNotIn("stock_seq", body)
        reg_id = self.conn.execute(
            f"SELECT reg_id FROM {TABLE_AUCTION_SHIP_MASTER} LIMIT 1"
        ).fetchone()[0]
        self.assertEqual(reg_id, "MOBILE")

    def test_t_auc_api_02_multi_spec_create(self) -> None:
        _insert_stock(self.conn, storage_dt="2025-10-01", in_qty=10)
        self.conn.execute(
            """
            INSERT INTO t_stock_master (
                farm_cd, wh_cd, item_cd, variety_cd, grade_cd, size_cd,
                weight, harvest_year, storage_dt, in_qty, out_qty, reserved_qty, reg_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 'TEST')
            """,
            (
                FARM, WAREHOUSE_CD_DEFAULT, ITEM, VARIETY, "GR010100", "FR020102",
                WEIGHT, YEAR, "2025-10-01", 15,
            ),
        )
        self.conn.commit()
        res = self._post(
            {
                "ship_dt": "2026-08-31",
                "market_cd": MARKET_CD,
                "market_name": MARKET_NM,
                "corporation_name": CORP,
                "lines": [_line(5), _line(7, size_cd="FR020102")],
            }
        )
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertEqual(body["spec_count"], 2)
        self.assertAlmostEqual(body["total_shipped_qty"], 12.0)
        detail_cnt = self.conn.execute(
            f"SELECT COUNT(*) FROM {TABLE_AUCTION_SHIP_DETAIL}"
        ).fetchone()[0]
        self.assertEqual(detail_cnt, 2)

    def test_t_auc_api_03_fifo_split_no_stock_seq_in_response(self) -> None:
        _insert_stock(self.conn, storage_dt="2025-10-01", in_qty=6, stock_seq=101)
        _insert_stock(self.conn, storage_dt="2025-10-02", in_qty=10, stock_seq=205)
        res = self._post(_body(8))
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertEqual(body["spec_count"], 1)
        self.assertEqual(body["total_line_count"], 2)
        self.assertNotIn("stock_seq", json.dumps(body))
        rows = self.conn.execute(
            f"SELECT stock_seq, farm_shipped_qty FROM {TABLE_AUCTION_SHIP_DETAIL} ORDER BY line_seq"
        ).fetchall()
        self.assertEqual(int(rows[0][0]), 101)
        self.assertAlmostEqual(float(rows[0][1]), 6.0)
        self.assertEqual(int(rows[1][0]), 205)
        self.assertAlmostEqual(float(rows[1][1]), 2.0)

    def test_t_auc_api_04_over_available_reject(self) -> None:
        _insert_stock(self.conn, storage_dt="2025-10-01", in_qty=10)
        before_master = self.conn.execute(
            f"SELECT COUNT(*) FROM {TABLE_AUCTION_SHIP_MASTER}"
        ).fetchone()[0]
        res = self._post(_body(11))
        self.assertEqual(res.status_code, 409, res.text)
        self.assertEqual(res.json()["error_code"], CODE_AUCTION_SHIP_QTY_UNAVAILABLE)
        after_master = self.conn.execute(
            f"SELECT COUNT(*) FROM {TABLE_AUCTION_SHIP_MASTER}"
        ).fetchone()[0]
        self.assertEqual(before_master, after_master)

    def test_t_auc_api_05_auction_schema_missing(self) -> None:
        self.conn.execute(f"DROP TABLE IF EXISTS {TABLE_AUCTION_SHIP_DETAIL}")
        self.conn.execute(f"DROP TABLE IF EXISTS {TABLE_AUCTION_SHIP_MASTER}")
        self.conn.commit()
        _insert_stock(self.conn, storage_dt="2025-10-01", in_qty=20)
        res = self._post(_body(10))
        self.assertEqual(res.status_code, 409, res.text)
        self.assertEqual(res.json()["error_code"], CODE_AUCTION_SHIP_SCHEMA)

    def test_t_auc_api_06_stock_seq_schema_missing(self) -> None:
        app.dependency_overrides.pop(get_auction_ship_api_service, None)
        self.conn.close()
        self.path.unlink(missing_ok=True)

        path, conn = _open_legacy_auction()
        self.path = path
        self.conn = conn
        self.svc = AuctionShipApiService(path)
        app.dependency_overrides[get_auction_ship_api_service] = lambda: self.svc
        _insert_stock_legacy(conn, storage_dt="2025-10-01", in_qty=20)
        res = self.client.post(
            _url(),
            json=_body(10),
            headers={"X-User-Id": "MOBILE"},
        )
        self.assertEqual(res.status_code, 409, res.text)
        self.assertEqual(res.json()["error_code"], CODE_AUCTION_SHIP_STOCK_SCHEMA)

    def test_t_auc_api_07_forbid_extra_stock_seq(self) -> None:
        _insert_stock(self.conn, storage_dt="2025-10-01", in_qty=20)
        body = _body(10)
        body["lines"][0]["stock_seq"] = 999
        res = self._post(body)
        self.assertEqual(res.status_code, 422, res.text)

    def test_t_auc_api_08_list_in_transit(self) -> None:
        _insert_stock(self.conn, storage_dt="2025-10-01", in_qty=30)
        self.assertEqual(self._post(_body(10)).status_code, 200)
        self.assertEqual(self._post(_body(5)).status_code, 200)
        res = self._get()
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertEqual(body["total"], 2)
        self.assertEqual(len(body["items"]), 2)
        for item in body["items"]:
            self.assertEqual(item["status"], AUCTION_SHIP_STATUS_IN_TRANSIT)
            self.assertNotIn("stock_seq", item)

    def test_t_auc_api_09_farm_isolation(self) -> None:
        _insert_stock(self.conn, storage_dt="2025-10-01", in_qty=20)
        self._post(_body(10))
        res = self._get(OTHER_FARM)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["total"], 0)

    def test_t_auc_api_10_list_sort(self) -> None:
        _insert_stock(self.conn, storage_dt="2025-10-01", in_qty=50)
        self._post({**_body(5), "ship_dt": "2026-08-29"})
        self._post({**_body(6), "ship_dt": "2026-08-31"})
        self._post({**_body(7), "ship_dt": "2026-08-30"})
        res = self._get()
        items = res.json()["items"]
        ship_dts = [item["ship_dt"] for item in items]
        self.assertEqual(ship_dts, sorted(ship_dts, reverse=True))

    def test_t_auc_api_11_total_shipped_qty(self) -> None:
        _insert_stock(self.conn, storage_dt="2025-10-01", in_qty=20, stock_seq=101)
        _insert_stock(self.conn, storage_dt="2025-10-02", in_qty=20, stock_seq=205)
        self._post(_body(8))
        res = self._get()
        item = res.json()["items"][0]
        self.assertAlmostEqual(item["total_shipped_qty"], 8.0)

    def test_t_auc_api_12_list_no_stock_seq(self) -> None:
        _insert_stock(self.conn, storage_dt="2025-10-01", in_qty=10)
        self._post(_body(4))
        res = self._get()
        self.assertNotIn("stock_seq", json.dumps(res.json()))

    def test_t_auc_api_13_list_without_schema_empty(self) -> None:
        app.dependency_overrides.pop(get_auction_ship_api_service, None)
        self.conn.close()
        self.path.unlink(missing_ok=True)

        path, conn = _open_tmp()
        self.path = path
        self.conn = conn
        self.svc = AuctionShipApiService(path)
        app.dependency_overrides[get_auction_ship_api_service] = lambda: self.svc
        res = self.client.get(_url())
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertEqual(body["total"], 0)
        self.assertEqual(body["items"], [])

    def test_t_auc_api_concurrency(self) -> None:
        _insert_stock(self.conn, storage_dt="2025-10-01", in_qty=10)
        results: list[str] = []
        lock = threading.Lock()

        def worker() -> None:
            c = TestClient(app)
            res = c.post(
                _url(),
                json=_body(7),
                headers={"X-User-Id": "MOBILE"},
            )
            with lock:
                if res.status_code == 200:
                    results.append("ok")
                else:
                    results.append(res.json().get("error_code", "err"))

        t1 = threading.Thread(target=worker)
        t2 = threading.Thread(target=worker)
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        self.assertEqual(results.count("ok"), 1)
        self.assertEqual(results.count(CODE_AUCTION_SHIP_QTY_UNAVAILABLE), 1)


class AuctionShipApiSmokeTests(unittest.TestCase):
    def test_health_and_openapi(self) -> None:
        path, conn = _open_ops()
        try:
            svc = AuctionShipApiService(path)
            app.dependency_overrides[get_auction_ship_api_service] = lambda: svc
            client = TestClient(app)
            health = client.get("/api/v1/health")
            self.assertEqual(health.status_code, 200)
            openapi = client.get("/openapi.json")
            self.assertEqual(openapi.status_code, 200)
            paths = openapi.json().get("paths", {})
            self.assertIn("/api/v1/farms/{farm_cd}/auction-shipments", paths)
            post_props = paths["/api/v1/farms/{farm_cd}/auction-shipments"]["post"]
            req_schema = post_props["requestBody"]["content"]["application/json"]["schema"]
            props = openapi.json()["components"]["schemas"][
                req_schema["$ref"].split("/")[-1]
            ]["properties"]
            self.assertNotIn("stock_seq", props)
        finally:
            app.dependency_overrides.pop(get_auction_ship_api_service, None)
            conn.close()
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
