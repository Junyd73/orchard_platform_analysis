# -*- coding: utf-8 -*-
"""DEC-037 Stage B — 경락 후보 REST."""

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

from app.api.dependencies import get_auction_candidate_api_service  # noqa: E402
from app.main import app  # noqa: E402
from app.services.auction_candidate_api_service import AuctionCandidateApiService  # noqa: E402
from core.auction_candidate_constants import (  # noqa: E402
    CODE_AUCTION_CANDIDATE_NOT_FOUND,
    SOURCE_SETTLEMENT,
)
from test_auction_candidate_service import (  # noqa: E402
    FARM,
    OTHER_FARM,
    TRADE_DT,
    _create_ship,
    _ensure_farm,
    _row,
)
from test_auction_ship_service import _open_ops  # noqa: E402


def _url(farm: str, shipment_id: str) -> str:
    return f"/api/v1/farms/{farm}/auction-shipments/{shipment_id}/auction-candidates"


class AuctionCandidateApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.path, self.conn = _open_ops()
        _ensure_farm(self.conn)
        self.sid = _create_ship(self.conn)
        self.settlement_rows = [_row()]
        self.realtime_calls = 0

        def settlement(trade_dt: str, market_cd: str):
            return list(self.settlement_rows)

        def realtime(trade_dt: str, market_cd: str):
            self.realtime_calls += 1
            return []

        self.svc = AuctionCandidateApiService(
            self.path,
            settlement_fetch=settlement,
            realtime_fetch=realtime,
        )
        app.dependency_overrides[get_auction_candidate_api_service] = lambda: self.svc
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.pop(get_auction_candidate_api_service, None)
        self.conn.close()
        self.path.unlink(missing_ok=True)

    def test_response_contract(self) -> None:
        res = self.client.get(_url(FARM, self.sid), params={"trade_dt": TRADE_DT})
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertEqual(body["shipment_id"], self.sid)
        self.assertEqual(body["trade_dt"], TRADE_DT)
        self.assertEqual(body["source_used"], SOURCE_SETTLEMENT)
        self.assertEqual(len(body["items"]), 1)
        item = body["items"][0]
        self.assertNotIn("stock_seq", item)
        self.assertNotIn("skipped", body)
        self.assertIn("source_key", item)
        self.assertIn("requires_grade_input", item)
        self.assertEqual(self.realtime_calls, 0)

    def test_missing_trade_dt(self) -> None:
        res = self.client.get(_url(FARM, self.sid))
        self.assertEqual(res.status_code, 422)

    def test_other_farm_404(self) -> None:
        res = self.client.get(_url(OTHER_FARM, self.sid), params={"trade_dt": TRADE_DT})
        self.assertEqual(res.status_code, 404, res.text)
        self.assertEqual(res.json()["error_code"], CODE_AUCTION_CANDIDATE_NOT_FOUND)


if __name__ == "__main__":
    unittest.main()
