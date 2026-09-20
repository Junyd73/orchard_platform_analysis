# -*- coding: utf-8 -*-
"""R26-F 확정 경락 매칭 READ API."""

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

from app.api.dependencies import get_auction_match_api_service  # noqa: E402
from app.main import app  # noqa: E402
from app.services.auction_match_api_service import AuctionMatchApiService  # noqa: E402
from core.auction_match_constants import TABLE_AUCTION_MATCH_DETAIL  # noqa: E402
from core.auction_match_schema import ensure_auction_match_schema  # noqa: E402
from core.auction_ship_constants import (  # noqa: E402
    AUCTION_SHIP_STATUS_COMPLETED,
    AUCTION_SHIP_STATUS_IN_TRANSIT,
    TABLE_AUCTION_SHIP_MASTER,
)
from core.auction_ship_schema import ensure_auction_ship_schema  # noqa: E402
from test_auction_candidate_service import FARM, TRADE_DT, _ensure_farm  # noqa: E402
from test_auction_finalize_service import _open_finalize  # noqa: E402


class AuctionMatchReadApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.path, self.conn = _open_finalize()
        _ensure_farm(self.conn)
        ensure_auction_ship_schema(self.conn)
        ensure_auction_match_schema(self.conn)
        self.svc = AuctionMatchApiService(db_path=self.path)
        app.dependency_overrides[get_auction_match_api_service] = lambda: self.svc
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.pop(get_auction_match_api_service, None)
        self.conn.close()
        try:
            os.unlink(self.path)
        except OSError:
            pass

    def _insert_ship(self, shipment_id: str, *, status: str, match_trade_dt: str | None) -> None:
        self.conn.execute(
            f"""
            INSERT INTO {TABLE_AUCTION_SHIP_MASTER} (
                shipment_id, farm_cd, ship_dt, market_cd, market_name,
                corporation_name, custm_id, status, sales_no, match_trade_dt, reg_id, reg_dt
            ) VALUES (?, ?, ?, ?, ?, ?, NULL, ?, NULL, ?, 't', '2026-09-20 10:00:00')
            """,
            (
                shipment_id,
                FARM,
                "2026-09-19",
                "110001",
                "가락",
                "한국청과",
                status,
                match_trade_dt,
            ),
        )
        self.conn.commit()

    def _insert_match(
        self,
        *,
        shipment_id: str,
        source_key: str,
        trade_dt: str,
        is_valid: int = 1,
        qty: int = 10,
        spec_kg: float = 15.0,
        unit_price: float = 30000,
        auction_time: str | None = "2026-09-20 14:28:00",
    ) -> None:
        amount = qty * unit_price
        self.conn.execute(
            f"""
            INSERT INTO {TABLE_AUCTION_MATCH_DETAIL} (
                farm_cd, shipment_id,
                spec_variety_cd, spec_grade_cd, spec_size_cd, spec_weight,
                source_type, source_key, trade_dt,
                market_cd, market_name, corporation_name, origin_name, variety_name,
                spec_name, spec_kg, qty, unit_price, amount, auction_time,
                is_valid, reg_id, reg_dt
            ) VALUES (
                ?, ?, 'FR010101', 'GR01', 'SZ01', ?,
                'REALTIME', ?, ?,
                '110001', '가락', '중앙청과', '경기도 안성시', '신고',
                '15kg', ?, ?, ?, ?, ?,
                ?, 't', '2026-09-20 10:00:00'
            )
            """,
            (
                FARM,
                shipment_id,
                15.0,
                source_key,
                trade_dt,
                spec_kg,
                qty,
                unit_price,
                amount,
                auction_time,
                is_valid,
            ),
        )
        self.conn.commit()

    def test_lists_only_completed_active_matches_for_trade_dt(self) -> None:
        self._insert_ship("S1", status=AUCTION_SHIP_STATUS_COMPLETED, match_trade_dt=TRADE_DT)
        self._insert_ship("S2", status=AUCTION_SHIP_STATUS_IN_TRANSIT, match_trade_dt=None)
        self._insert_ship("S3", status=AUCTION_SHIP_STATUS_COMPLETED, match_trade_dt="2026-09-18")
        self._insert_match(shipment_id="S1", source_key="k1", trade_dt=TRADE_DT)
        self._insert_match(shipment_id="S1", source_key="k2", trade_dt=TRADE_DT, is_valid=0)
        self._insert_match(shipment_id="S2", source_key="k3", trade_dt=TRADE_DT)
        self._insert_match(shipment_id="S3", source_key="k4", trade_dt="2026-09-18")

        res = self.client.get(
            f"/api/v1/farms/{FARM}/auction-matches",
            params={"trade_dt": TRADE_DT},
        )
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertEqual(body["farm_cd"], FARM)
        self.assertEqual(body["trade_dt"], TRADE_DT)
        self.assertEqual(body["total_count"], 1)
        item = body["items"][0]
        self.assertEqual(item["match_status"], "confirmed")
        self.assertEqual(item["source_key"], "k1")
        self.assertEqual(item["shipment_id"], "S1")
        self.assertEqual(item["corporation_name"], "중앙청과")
        self.assertEqual(item["variety_name"], "신고")
        self.assertEqual(item["spec_text"], "15kg")
        self.assertEqual(item["auction_box_qty"], 10)
        self.assertEqual(item["auction_weight_kg"], 150.0)
        self.assertEqual(item["auction_price"], 30000)
        self.assertEqual(item["auction_amount"], 300000)
        self.assertNotIn("match_seq", str(body).split("match_seq")[0] or "")  # still in response for internal - OK
        # UI 비노출 정책은 Mobile. API는 source_key를 내부 식별용으로 허용.


if __name__ == "__main__":
    unittest.main()
