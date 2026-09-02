# -*- coding: utf-8 -*-
"""DEC-036-C1 — auction lookup API tests."""

from __future__ import annotations

import json
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

from app.api.dependencies import get_auction_lookup_api_service  # noqa: E402
from app.main import app  # noqa: E402
from app.services.auction_lookup_api_service import AuctionLookupApiService  # noqa: E402
from core.auction_lookup_service import (  # noqa: E402
    AUCTION_DEFAULT_CORP_INCHEON_SAMSAN,
    AUCTION_MARKET_DISPLAY_NAME_BY_CD,
    CODE_AUCTION_LOOKUP_INVALID_MARKET,
)
from core.market_price_manager import MARKET_CODE_BY_NAME  # noqa: E402
from test_auction_ship_service import _open_ops  # noqa: E402

MARKETS_URL = "/api/v1/auction-markets"
CORP_URL = "/api/v1/auction-corporations"


def _open_lookup_db() -> tuple[Path, object]:
    path, conn = _open_ops()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS market_price_settlement (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_date TEXT NOT NULL,
            product_name TEXT,
            variety TEXT,
            normalized_variety TEXT,
            market TEXT,
            corporation TEXT,
            grade TEXT,
            size TEXT,
            spec TEXT,
            price INTEGER DEFAULT 0,
            quantity INTEGER DEFAULT 0,
            created_at TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS m_customer (
            custm_id TEXT, farm_cd TEXT, custm_nm TEXT, use_yn TEXT DEFAULT 'Y'
        )
        """
    )
    conn.commit()
    return path, conn


class AuctionLookupApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.path, self.conn = _open_lookup_db()
        self.svc = AuctionLookupApiService(self.path)
        app.dependency_overrides[get_auction_lookup_api_service] = lambda: self.svc
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.pop(get_auction_lookup_api_service, None)
        self.conn.close()
        self.path.unlink(missing_ok=True)

    def test_t_auc_lookup_01_markets(self) -> None:
        res = self.client.get(MARKETS_URL)
        self.assertEqual(res.status_code, 200, res.text)
        items = res.json()["items"]
        self.assertEqual(len(items), len(MARKET_CODE_BY_NAME))
        codes = {row["market_cd"] for row in items}
        self.assertEqual(codes, set(MARKET_CODE_BY_NAME.values()))

    def test_t_auc_lookup_02_market_pairs(self) -> None:
        res = self.client.get(MARKETS_URL)
        by_code = {row["market_cd"]: row["market_name"] for row in res.json()["items"]}
        for code, expected_name in AUCTION_MARKET_DISPLAY_NAME_BY_CD.items():
            self.assertEqual(by_code[code], expected_name)

    def test_t_auc_lookup_03_market_no_duplicates(self) -> None:
        res = self.client.get(MARKETS_URL)
        codes = [row["market_cd"] for row in res.json()["items"]]
        self.assertEqual(len(codes), len(set(codes)))

    def test_t_auc_lookup_04_market_no_extra_fields(self) -> None:
        res = self.client.get(MARKETS_URL)
        payload = json.dumps(res.json())
        self.assertNotIn("price", payload)
        self.assertNotIn("settlement", payload)

    def test_t_auc_lookup_05_no_external_http(self) -> None:
        import core.auction_lookup_service as mod

        source = Path(mod.__file__).read_text(encoding="utf-8")
        self.assertNotIn("requests", source)
        self.assertNotIn("httpx", source)
        self.assertNotIn("fetch(", source)

    def test_t_auc_lookup_06_corporations_distinct(self) -> None:
        self.conn.executemany(
            """
            INSERT INTO market_price_settlement (
                trade_date, market, corporation, normalized_variety, price, quantity
            ) VALUES (?, ?, ?, '신고', 1000, 1)
            """,
            [
                ("2026-08-31", "서울가락", "한국청과㈜"),
                ("2026-08-31", "서울가락", "한국청과㈜"),
                ("2026-08-31", "서울가락", "서울청과㈜"),
            ],
        )
        self.conn.commit()
        res = self.client.get(CORP_URL, params={"market_cd": "110001"})
        self.assertEqual(res.status_code, 200, res.text)
        names = [row["corporation_name"] for row in res.json()["items"]]
        self.assertEqual(names, ["서울청과㈜", "한국청과㈜"])

    def test_t_auc_lookup_07_corporation_dedup(self) -> None:
        self.conn.execute(
            """
            INSERT INTO market_price_settlement (
                trade_date, market, corporation, normalized_variety, price, quantity
            ) VALUES ('2026-08-31', '서울가락', ' 동화청과㈜ ', '신고', 1000, 1)
            """
        )
        self.conn.execute(
            """
            INSERT INTO market_price_settlement (
                trade_date, market, corporation, normalized_variety, price, quantity
            ) VALUES ('2026-08-31', '서울가락', '동화청과㈜', '신고', 1000, 1)
            """
        )
        self.conn.commit()
        res = self.client.get(CORP_URL, params={"market_cd": "110001"})
        self.assertEqual(len(res.json()["items"]), 1)

    def test_t_auc_lookup_08_custm_id_mapped(self) -> None:
        self.conn.execute(
            """
            INSERT INTO market_price_settlement (
                trade_date, market, corporation, normalized_variety, price, quantity
            ) VALUES ('2026-08-31', '서울가락', '한국청과㈜', '신고', 1000, 1)
            """
        )
        self.conn.execute(
            """
            INSERT INTO m_customer (custm_id, farm_cd, custm_nm, use_yn)
            VALUES ('C001', 'OR001', '한국청과㈜', 'Y')
            """
        )
        self.conn.commit()
        res = self.client.get(CORP_URL, params={"market_cd": "110001"})
        item = res.json()["items"][0]
        self.assertEqual(item["corporation_name"], "한국청과㈜")
        self.assertEqual(item["custm_id"], "C001")

    def test_t_auc_lookup_09_custm_id_null_when_unmapped(self) -> None:
        self.conn.execute(
            """
            INSERT INTO market_price_settlement (
                trade_date, market, corporation, normalized_variety, price, quantity
            ) VALUES ('2026-08-31', '서울가락', '미등록법인', '신고', 1000, 1)
            """
        )
        self.conn.commit()
        res = self.client.get(CORP_URL, params={"market_cd": "110001"})
        item = res.json()["items"][0]
        self.assertEqual(item["corporation_name"], "미등록법인")
        self.assertIsNone(item["custm_id"])

    def test_t_auc_lookup_10_empty_items(self) -> None:
        res = self.client.get(CORP_URL, params={"market_cd": "110001"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["items"], [])

    def test_t_auc_lookup_11_no_settlement_table(self) -> None:
        self.conn.execute("DROP TABLE IF EXISTS market_price_settlement")
        self.conn.commit()
        res = self.client.get(CORP_URL, params={"market_cd": "110001"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["items"], [])

    def test_t_auc_lookup_12_invalid_market(self) -> None:
        res = self.client.get(CORP_URL, params={"market_cd": "999999"})
        self.assertEqual(res.status_code, 400, res.text)
        self.assertEqual(res.json()["error_code"], CODE_AUCTION_LOOKUP_INVALID_MARKET)

    def test_t_auc_lookup_alias_market_match(self) -> None:
        self.conn.execute(
            """
            INSERT INTO market_price_settlement (
                trade_date, market, corporation, normalized_variety, price, quantity
            ) VALUES ('2026-08-31', '서울가락', '테스트법인', '신고', 1000, 1)
            """
        )
        self.conn.commit()
        res = self.client.get(CORP_URL, params={"market_cd": "110001"})
        self.assertEqual(len(res.json()["items"]), 1)

    def test_t_auc_lookup_13_incheon_samsan_market_label(self) -> None:
        res = self.client.get(MARKETS_URL)
        by_code = {row["market_cd"]: row["market_name"] for row in res.json()["items"]}
        self.assertEqual(by_code["230001"], "인천삼산")
        self.assertNotIn("부평", by_code.values())

    def test_t_auc_lookup_14_incheon_samsan_corp_fallback(self) -> None:
        res = self.client.get(CORP_URL, params={"market_cd": "230001"})
        self.assertEqual(res.status_code, 200, res.text)
        items = res.json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["corporation_name"], AUCTION_DEFAULT_CORP_INCHEON_SAMSAN)
        self.assertIsNone(items[0]["custm_id"])

    def test_t_auc_lookup_15_incheon_samsan_corp_fallback_no_table(self) -> None:
        self.conn.execute("DROP TABLE IF EXISTS market_price_settlement")
        self.conn.commit()
        res = self.client.get(CORP_URL, params={"market_cd": "230001"})
        self.assertEqual(res.status_code, 200, res.text)
        items = res.json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["corporation_name"], AUCTION_DEFAULT_CORP_INCHEON_SAMSAN)


if __name__ == "__main__":
    unittest.main()
