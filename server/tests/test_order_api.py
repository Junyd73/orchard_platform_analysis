# -*- coding: utf-8 -*-
"""주문 Stage 2 FastAPI — GET 목록/상세, POST 등록, PUT 수정."""

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
from core.ops_biz_date import today_ops_iso  # noqa: E402
from core.order_constants import (  # noqa: E402
    MSG_ORDER_CANCEL_FORBIDDEN,
    MSG_ORDER_LOCKED_DELIVERED,
    ORDER_STATUS_CANCEL_CD,
    ORDER_STATUS_CONFIRMED_CD,
    ORDER_STATUS_DELIVERED_CD,
    ORDER_STATUS_PREP_CD,
    ORDER_STATUS_RESERVED_CD,
)
from test_order_service import _schema_sql  # noqa: E402


FARM = "OR001"


def _tmp_db() -> Path:
    fd, name = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    path = Path(name)
    conn = sqlite3.connect(str(path))
    conn.executescript(_schema_sql())
    conn.commit()
    conn.close()
    return path


class OrderApiStage2Test(unittest.TestCase):
    def setUp(self) -> None:
        self.path = _tmp_db()
        self.svc = OrderApiService(self.path)
        app.dependency_overrides[get_order_api_service] = lambda: self.svc
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.pop(get_order_api_service, None)
        self.path.unlink(missing_ok=True)

    def _body(self, qty: float = 100) -> dict:
        return {
            "custm_id": "C001",
            "pre_pay_amt": 10000,
            "rmk": "api",
            "lines": [
                {
                    "variety_cd": "FR010101",
                    "weight": 15,
                    "grade_cd": "GR010100",
                    "size_cd": "SZ010100",
                    "qty": qty,
                    "unit_price": 20000,
                    "harvest_year": 2026,
                    "deliveries": [
                        {
                            "delivery_tp_cd": "LO010100",
                            "qty": qty,
                            "rcv_name": "수령",
                        }
                    ],
                }
            ],
        }

    def test_post_get_list_and_side_effects(self) -> None:
        empty = self.client.get(f"/api/v1/farms/{FARM}/orders")
        self.assertEqual(empty.status_code, 200)
        self.assertEqual(empty.json()["items"], [])
        self.assertEqual(empty.json()["total"], 0)
        self.assertEqual(empty.json()["page"], 1)
        self.assertEqual(empty.json()["page_size"], 20)

        created = self.client.post(
            f"/api/v1/farms/{FARM}/orders",
            json=self._body(),
            headers={"X-User-Id": "MOBILE"},
        )
        self.assertEqual(created.status_code, 200, created.text)
        body = created.json()
        self.assertEqual(body["status_cd"], ORDER_STATUS_RESERVED_CD)
        self.assertEqual(body["order_dt"], today_ops_iso())
        order_no = body["order_no"]

        listed = self.client.get(f"/api/v1/farms/{FARM}/orders")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(len(listed.json()["items"]), 1)
        self.assertEqual(listed.json()["items"][0]["order_no"], order_no)
        self.assertEqual(listed.json()["total"], 1)

        detail = self.client.get(f"/api/v1/farms/{FARM}/orders/{order_no}")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(len(detail.json()["lines"]), 1)

        conn = sqlite3.connect(str(self.path))
        try:
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM t_sales_master").fetchone()[0], 0
            )
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM t_stock_log").fetchone()[0], 0
            )
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM t_ledger").fetchone()[0], 0
            )
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM t_cash_ledger").fetchone()[0], 0
            )
        finally:
            conn.close()

        customers = self.client.get(f"/api/v1/farms/{FARM}/customers")
        self.assertEqual(customers.status_code, 200)
        self.assertEqual(customers.json()[0]["custm_id"], "C001")

    def test_post_customer_and_order_regression(self) -> None:
        created = self.client.post(
            f"/api/v1/farms/{FARM}/customers",
            json={"custm_nm": "신규", "mobile": "010-3333-4444", "addr1": "서울"},
            headers={"X-User-Id": "MOBILE"},
        )
        self.assertEqual(created.status_code, 200, created.text)
        body = created.json()
        self.assertTrue(body["custm_id"].startswith("C"))
        self.assertEqual(body["custm_nm"], "신규")

        listed = self.client.get(f"/api/v1/farms/{FARM}/customers")
        ids = [c["custm_id"] for c in listed.json()]
        self.assertIn(body["custm_id"], ids)

        order_body = self._body()
        order_body["custm_id"] = body["custm_id"]
        order = self.client.post(
            f"/api/v1/farms/{FARM}/orders",
            json=order_body,
            headers={"X-User-Id": "MOBILE"},
        )
        self.assertEqual(order.status_code, 200, order.text)
        conn = sqlite3.connect(str(self.path))
        try:
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM t_sales_master").fetchone()[0], 0
            )
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM t_stock_log").fetchone()[0], 0
            )
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM t_ledger").fetchone()[0], 0
            )
        finally:
            conn.close()

    def test_post_customer_validation(self) -> None:
        res = self.client.post(
            f"/api/v1/farms/{FARM}/customers",
            json={"custm_nm": " ", "mobile": "010"},
            headers={"X-User-Id": "MOBILE"},
        )
        self.assertIn(res.status_code, (400, 409, 422))

    def test_missing_order_404(self) -> None:
        res = self.client.get(f"/api/v1/farms/{FARM}/orders/ORD20990101-001")
        self.assertEqual(res.status_code, 404)

    def test_post_parcel_n_deliveries(self) -> None:
        body = self._body(qty=10)
        body["lines"][0]["dlvry_tp"] = "LO010200"
        body["lines"][0]["deliveries"] = [
            {
                "delivery_tp_cd": "LO010200",
                "qty": q,
                "rcv_name": f"수령{i}",
                "rcv_tel": f"010-1111-{i:04d}",
                "rcv_addr": f"서울 {i}",
            }
            for i, q in enumerate((3, 2, 5), start=1)
        ]
        created = self.client.post(
            f"/api/v1/farms/{FARM}/orders",
            json=body,
            headers={"X-User-Id": "MOBILE"},
        )
        self.assertEqual(created.status_code, 200, created.text)
        lines = created.json()["lines"]
        self.assertEqual(len(lines), 1)
        self.assertEqual(len(lines[0]["deliveries"]), 3)
        det_ids = {d["order_detail_id"] for d in lines[0]["deliveries"]}
        self.assertEqual(len(det_ids), 1)
        conn = sqlite3.connect(str(self.path))
        try:
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM t_order_delivery").fetchone()[0], 3
            )
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM t_sales_master").fetchone()[0], 0
            )
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM t_stock_log").fetchone()[0], 0
            )
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM t_ledger").fetchone()[0], 0
            )
        finally:
            conn.close()


    def test_put_replace_and_lock(self) -> None:
        created = self.client.post(
            f"/api/v1/farms/{FARM}/orders",
            json=self._body(qty=10),
            headers={"X-User-Id": "MOBILE"},
        )
        self.assertEqual(created.status_code, 200, created.text)
        order_no = created.json()["order_no"]
        body = self._body(qty=12)
        updated = self.client.put(
            f"/api/v1/farms/{FARM}/orders/{order_no}",
            json=body,
            headers={"X-User-Id": "MOBILE"},
        )
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()["lines"][0]["qty"], 12)
        self.assertEqual(updated.json()["lines"][0]["variety_nm"], "신고배")
        conn = sqlite3.connect(str(self.path))
        try:
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM t_sales_master").fetchone()[0], 0
            )
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM t_stock_log").fetchone()[0], 0
            )
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM t_ledger").fetchone()[0], 0
            )
            conn.execute(
                "UPDATE t_order_master SET status_cd = ? WHERE order_no = ?",
                (ORDER_STATUS_DELIVERED_CD, order_no),
            )
            conn.commit()
        finally:
            conn.close()
        locked = self.client.put(
            f"/api/v1/farms/{FARM}/orders/{order_no}",
            json=self._body(qty=12),
            headers={"X-User-Id": "MOBILE"},
        )
        self.assertEqual(locked.status_code, 400, locked.text)
        self.assertIn(MSG_ORDER_LOCKED_DELIVERED, locked.text)

    def test_post_cancel_and_lock(self) -> None:
        created = self.client.post(
            f"/api/v1/farms/{FARM}/orders",
            json=self._body(qty=4),
            headers={"X-User-Id": "MOBILE"},
        )
        self.assertEqual(created.status_code, 200, created.text)
        order_no = created.json()["order_no"]
        canceled = self.client.post(
            f"/api/v1/farms/{FARM}/orders/{order_no}/cancel",
            json={},
            headers={"X-User-Id": "MOBILE"},
        )
        self.assertEqual(canceled.status_code, 200, canceled.text)
        body = canceled.json()
        self.assertEqual(body["status_cd"], ORDER_STATUS_CANCEL_CD)
        self.assertEqual(body["status_nm"], "취소")
        self.assertEqual(len(body["lines"]), 1)
        self.assertEqual(len(body["lines"][0]["deliveries"]), 1)
        again = self.client.post(
            f"/api/v1/farms/{FARM}/orders/{order_no}/cancel",
            json={},
            headers={"X-User-Id": "MOBILE"},
        )
        self.assertEqual(again.status_code, 400, again.text)
        self.assertIn(MSG_ORDER_CANCEL_FORBIDDEN, again.text)
        conn = sqlite3.connect(str(self.path))
        try:
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM t_order_detail").fetchone()[0], 1
            )
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM t_sales_master").fetchone()[0], 0
            )
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM t_stock_log").fetchone()[0], 0
            )
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM t_ledger").fetchone()[0], 0
            )
        finally:
            conn.close()

        other = self.client.post(
            f"/api/v1/farms/{FARM}/orders",
            json=self._body(qty=1),
            headers={"X-User-Id": "MOBILE"},
        )
        other_no = other.json()["order_no"]
        conn = sqlite3.connect(str(self.path))
        try:
            conn.execute(
                "UPDATE t_order_master SET status_cd = ? WHERE order_no = ?",
                (ORDER_STATUS_PREP_CD, other_no),
            )
            conn.commit()
        finally:
            conn.close()
        blocked = self.client.post(
            f"/api/v1/farms/{FARM}/orders/{other_no}/cancel",
            json={},
            headers={"X-User-Id": "MOBILE"},
        )
        self.assertEqual(blocked.status_code, 400, blocked.text)
        self.assertIn(MSG_ORDER_CANCEL_FORBIDDEN, blocked.text)

    def test_list_orders_query_paging(self) -> None:
        conn = sqlite3.connect(str(self.path))
        try:
            conn.execute(
                """
                INSERT INTO m_customer (custm_id, farm_cd, custm_nm, mobile, use_yn)
                VALUES ('C002', 'OR001', '박상희', '010-2222-3333', 'Y')
                """
            )
            rows = [
                ("ORD20260115-001", "20260115", "C002", ORDER_STATUS_RESERVED_CD),
                ("ORD20260301-001", "2026-03-01", "C001", ORDER_STATUS_CONFIRMED_CD),
                ("ORD20260801-001", "2026-08-01", "C001", ORDER_STATUS_RESERVED_CD),
            ]
            for order_no, order_dt, custm_id, status in rows:
                conn.execute(
                    """
                    INSERT INTO t_order_master (
                        order_no, farm_cd, order_dt, custm_id, status_cd, stock_status,
                        tot_order_amt, tot_ship_fee, tot_pay_amt, pre_pay_amt, sales_no, rmk
                    ) VALUES (?, ?, ?, ?, ?, 'N', 1000, 0, 1000, 0, '', '')
                    """,
                    (order_no, FARM, order_dt, custm_id, status),
                )
            conn.commit()
        finally:
            conn.close()

        listed = self.client.get(
            f"/api/v1/farms/{FARM}/orders",
            params={"from_date": "2026-01-01", "to_date": "2026-12-31", "page_size": 20},
        )
        self.assertEqual(listed.status_code, 200, listed.text)
        body = listed.json()
        self.assertEqual(body["total"], 3)
        self.assertEqual(body["page"], 1)
        self.assertEqual(body["page_size"], 20)
        self.assertEqual(body["items"][0]["order_no"], "ORD20260801-001")

        page1 = self.client.get(
            f"/api/v1/farms/{FARM}/orders",
            params={
                "from_date": "2026-01-01",
                "to_date": "2026-12-31",
                "page": 1,
                "page_size": 2,
            },
        )
        self.assertEqual(len(page1.json()["items"]), 2)
        page2 = self.client.get(
            f"/api/v1/farms/{FARM}/orders",
            params={
                "from_date": "2026-01-01",
                "to_date": "2026-12-31",
                "page": 2,
                "page_size": 2,
            },
        )
        self.assertEqual(len(page2.json()["items"]), 1)
        self.assertEqual(page2.json()["page"], 2)

        by_status = self.client.get(
            f"/api/v1/farms/{FARM}/orders",
            params={"status_cd": ORDER_STATUS_CONFIRMED_CD},
        )
        self.assertEqual(by_status.json()["total"], 1)
        self.assertEqual(by_status.json()["items"][0]["status_nm"], "주문확정")

        by_kw = self.client.get(
            f"/api/v1/farms/{FARM}/orders",
            params={"keyword": "박상희"},
        )
        self.assertEqual(by_kw.json()["total"], 1)
        by_no = self.client.get(
            f"/api/v1/farms/{FARM}/orders",
            params={"keyword": "ORD20260801-001"},
        )
        self.assertEqual(by_no.json()["items"][0]["order_no"], "ORD20260801-001")


if __name__ == "__main__":
    unittest.main()
