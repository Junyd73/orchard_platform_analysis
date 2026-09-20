# -*- coding: utf-8 -*-
"""R26-B GET /api/v1/market-auctions — mock 기반."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta
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
os.environ["ORCHARD_DEBUG_MARKET_VERIFY"] = "0"

from fastapi.testclient import TestClient  # noqa: E402

from app.api.dependencies import get_market_auction_api_service  # noqa: E402
from app.main import app  # noqa: E402
from app.services.market_auction_api_service import MarketAuctionApiService  # noqa: E402
from core.market_auction_query import (  # noqa: E402
    REALTIME_AUCTION_SELECTABLE_FIELDS,
    SOURCE_REALTIME,
    MemoryAuctionCache,
    MarketAuctionQueryService,
    collect_pages,
)
from core.market_price_manager import MarketApiRequestError  # noqa: E402
from core.ops_biz_date import OPS_TZ  # noqa: E402

URL = "/api/v1/market-auctions"
TODAY = date(2026, 9, 20)
PAST = date(2026, 9, 18)
FUTURE = date(2026, 9, 21)
NOW0 = datetime(2026, 9, 20, 14, 45, 33, tzinfo=OPS_TZ)


def _rt(**over) -> dict:
    row = {
        "trd_clcln_ymd": TODAY.isoformat(),
        "scsbd_dt": "2026-09-20 14:28:00",
        "mdfcn_dt": "2026-09-20 14:28:01",
        "spm_no": "S1",
        "auctn_seq": "1",
        "whsl_mrkt_cd": "110001",
        "whsl_mrkt_nm": "서울가락도매시장",
        "corp_cd": "11000105",
        "corp_nm": "한국청과㈜",
        "plor_cd": "410000",
        "plor_nm": "경기도 화성시",
        "gds_sclsf_cd": "01",
        "gds_sclsf_nm": "신고",
        "unit_qty": "15",
        "unit_nm": "kg",
        "qty": "20",
        "scsbd_prc": "52000",
    }
    row.update(over)
    return row


class MarketAuctionApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fetch_calls: list[tuple[str, str, str]] = []
        self.raw_rows: list[dict] = [_rt()]
        self.fail_next = False
        self.now = NOW0
        cache = MemoryAuctionCache()

        def paged_fetch(source: str, trade_date: str, market_cd: str):
            self.fetch_calls.append((source, trade_date, market_cd))
            if self.fail_next:
                self.fail_next = False
                raise MarketApiRequestError("upstream down", status=500)
            return list(self.raw_rows)

        self.query = MarketAuctionQueryService(
            paged_fetch=paged_fetch,
            cache=cache,
            clock=lambda: TODAY,
            now=lambda: self.now,
            ttl_sec=60,
        )
        self.svc = MarketAuctionApiService(self.query)
        app.dependency_overrides[get_market_auction_api_service] = lambda: self.svc
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.pop(get_market_auction_api_service, None)

    def _get(self, **params):
        return self.client.get(URL, params=params)

    def test_01_today_uses_realtime_source(self) -> None:
        res = self._get(trade_date=TODAY.isoformat())
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(self.fetch_calls[0][0], SOURCE_REALTIME)
        self.assertNotIn("source_type", res.json())
        self.assertNotIn("source", res.json())

    def test_02_past_uses_realtime_source(self) -> None:
        self.raw_rows = [_rt(trd_clcln_ymd=PAST.isoformat(), scsbd_dt="2026-09-18 10:00:00")]
        res = self._get(trade_date=PAST.isoformat())
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(self.fetch_calls[0][0], SOURCE_REALTIME)
        item = res.json()["items"][0]
        self.assertEqual(item["auction_time"], "2026-09-18 10:00:00")

    def test_03_future_rejected(self) -> None:
        res = self._get(trade_date=FUTURE.isoformat())
        self.assertEqual(res.status_code, 400, res.text)
        body = res.json()
        self.assertEqual(body["error_code"], "MARKET_AUCTION_FUTURE_DATE")
        self.assertEqual(self.fetch_calls, [])

    def test_04_realtime_box_kg_amount(self) -> None:
        res = self._get(trade_date=TODAY.isoformat())
        item = res.json()["items"][0]
        self.assertEqual(item["auction_box_qty"], "20")
        self.assertEqual(item["auction_weight_kg"], "300")
        self.assertEqual(item["auction_amount"], 1_040_000)
        self.assertEqual(item["auction_price"], 52_000)
        self.assertEqual(item["spec_text"], "15kg")
        self.assertEqual(item["origin_name"], "경기도 화성시")

    def test_05_past_uses_realtime_qty_price(self) -> None:
        self.raw_rows = [
            _rt(
                trd_clcln_ymd=PAST.isoformat(),
                scsbd_dt="2026-09-18 08:22:00",
                qty="36",
                unit_qty="15",
                scsbd_prc="43000",
            ),
        ]
        res = self._get(trade_date=PAST.isoformat())
        item = res.json()["items"][0]
        self.assertEqual(item["auction_box_qty"], "36")
        self.assertEqual(item["auction_weight_kg"], "540")
        self.assertEqual(item["auction_price"], 43_000)
        self.assertEqual(item["auction_amount"], 1_548_000)
        self.assertEqual(item["auction_time"], "2026-09-18 08:22:00")

    def test_06_corporation_origin_variety_filter(self) -> None:
        self.raw_rows = [
            _rt(),
            _rt(
                spm_no="S2",
                auctn_seq="2",
                corp_cd="11000101",
                corp_nm="동화청과",
                plor_cd="420000",
                plor_nm="충청남도 천안시",
                gds_sclsf_cd="02",
                gds_sclsf_nm="원황",
                qty="10",
                scsbd_prc="40000",
            ),
        ]
        res = self._get(
            trade_date=TODAY.isoformat(),
            corporation_cd="11000105",
            origin_cd="410000",
            variety="신고",
        )
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertEqual(body["total_count"], 1)
        self.assertEqual(body["items"][0]["corporation_cd"], "11000105")
        self.assertEqual(body["items"][0]["variety_name"], "신고")

    def test_06b_origin_cd_comma_or_filter(self) -> None:
        self.raw_rows = [
            _rt(),
            _rt(
                spm_no="S2",
                auctn_seq="2",
                corp_cd="11000101",
                corp_nm="동화청과",
                plor_cd="420000",
                plor_nm="충청남도 천안시",
                gds_sclsf_cd="02",
                gds_sclsf_nm="원황",
                qty="10",
                scsbd_prc="40000",
            ),
            _rt(
                spm_no="S3",
                auctn_seq="3",
                plor_cd="430000",
                plor_nm="전라북도 익산시",
                qty="5",
                scsbd_prc="30000",
            ),
        ]
        res = self._get(
            trade_date=TODAY.isoformat(),
            origin_cd="410000,420000",
        )
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertEqual(body["total_count"], 2)
        origins = {item["origin_cd"] for item in body["items"]}
        self.assertEqual(origins, {"410000", "420000"})

    def test_07_summary_uses_filtered_full_set(self) -> None:
        self.raw_rows = [
            _rt(spm_no="A", auctn_seq="1", qty="20", scsbd_prc="52000"),
            _rt(
                spm_no="B",
                auctn_seq="2",
                corp_cd="11000101",
                corp_nm="동화청과",
                qty="10",
                scsbd_prc="40000",
            ),
        ]
        res = self._get(trade_date=TODAY.isoformat(), corporation_cd="11000105")
        body = res.json()
        self.assertEqual(body["total_count"], 1)
        self.assertEqual(body["summary"]["auction_box_qty"], "20")
        self.assertEqual(body["summary"]["auction_weight_kg"], "300")
        self.assertEqual(body["summary"]["auction_amount"], 1_040_000)

    def test_08_page_size_50_has_more(self) -> None:
        self.raw_rows = [
            _rt(
                spm_no=f"S{i}",
                auctn_seq=str(i),
                scsbd_dt=f"2026-09-20 14:{i % 50:02d}:00",
                qty="1",
                scsbd_prc="1000",
            )
            for i in range(60)
        ]
        res = self._get(trade_date=TODAY.isoformat(), page=1, page_size=50)
        body = res.json()
        self.assertEqual(body["total_count"], 60)
        self.assertEqual(body["page_size"], 50)
        self.assertEqual(len(body["items"]), 50)
        self.assertTrue(body["has_more"])
        self.assertEqual(body["summary"]["auction_box_qty"], "60")
        res2 = self._get(trade_date=TODAY.isoformat(), page=2, page_size=50)
        body2 = res2.json()
        self.assertEqual(len(body2["items"]), 10)
        self.assertFalse(body2["has_more"])

    def test_09_external_multi_page_fetch(self) -> None:
        pages = {
            1: ([_rt(spm_no=f"P1-{i}", auctn_seq=str(i)) for i in range(1000)], 1001),
            2: ([_rt(spm_no="P2-0", auctn_seq="0")], 1001),
        }
        seen: list[int] = []

        def request_page(page_no: int, page_size: int):
            seen.append(page_no)
            self.assertEqual(page_size, 1000)
            return pages[page_no]

        rows = collect_pages(request_page, page_size=1000, max_pages=50)
        self.assertEqual(seen, [1, 2])
        self.assertEqual(len(rows), 1001)

    def test_10_identity_key_dedupe(self) -> None:
        self.raw_rows = [
            _rt(qty="20"),
            _rt(qty="99", scsbd_prc="1"),
        ]
        res = self._get(trade_date=TODAY.isoformat())
        body = res.json()
        self.assertEqual(body["total_count"], 1)
        self.assertEqual(body["items"][0]["auction_box_qty"], "20")

    def test_11_zero_rows_http_200(self) -> None:
        self.raw_rows = []
        res = self._get(trade_date=TODAY.isoformat())
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertEqual(body["total_count"], 0)
        self.assertEqual(body["items"], [])
        self.assertEqual(body["summary"]["auction_box_qty"], "0")
        self.assertEqual(body["summary"]["auction_weight_kg"], "0")
        self.assertEqual(body["summary"]["auction_amount"], 0)
        dumped = json.dumps(body, ensure_ascii=False)
        self.assertNotIn("휴장", dumped)
        self.assertNotIn("휴장", res.text)

    def test_12_cache_hit(self) -> None:
        first = self._get(trade_date=TODAY.isoformat())
        second = self._get(trade_date=TODAY.isoformat())
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(len(self.fetch_calls), 1)
        self.assertFalse(first.json()["cache_hit"])
        self.assertTrue(second.json()["cache_hit"])
        self.assertFalse(second.json()["stale"])

    def test_13_refresh_bypasses_cache(self) -> None:
        self._get(trade_date=TODAY.isoformat())
        res = self._get(trade_date=TODAY.isoformat(), refresh=True)
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(len(self.fetch_calls), 2)
        self.assertFalse(res.json()["cache_hit"])
        self.assertFalse(res.json()["stale"])

    def test_14_expired_cache_stale_fallback(self) -> None:
        self._get(trade_date=TODAY.isoformat())
        self.now = NOW0 + timedelta(seconds=90)
        self.fail_next = True
        res = self._get(trade_date=TODAY.isoformat())
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertTrue(body["stale"])
        self.assertFalse(body["cache_hit"])
        self.assertEqual(body["total_count"], 1)

    def test_15_external_fail_without_cache_is_502(self) -> None:
        self.fail_next = True
        res = self._get(trade_date=TODAY.isoformat())
        self.assertEqual(res.status_code, 502, res.text)
        self.assertEqual(res.json()["error_code"], "MARKET_AUCTION_SOURCE")

    def test_16_does_not_expose_grade_size(self) -> None:
        self.raw_rows = [_rt(grd_nm="특", sz_nm="15과", grd_cd="01", sz_cd="01")]
        res = self._get(trade_date=TODAY.isoformat())
        item = res.json()["items"][0]
        self.assertNotIn("grade_name", item)
        self.assertNotIn("size_name", item)
        self.assertNotIn("grade_cd", item)
        self.assertNotIn("size_cd", item)
        dumped = json.dumps(item, ensure_ascii=False)
        self.assertNotIn("grd_nm", dumped)
        self.assertNotIn("sz_nm", dumped)
        self.assertNotIn("spm_no", dumped)
        self.assertNotIn("auctn_seq", dumped)

    def test_16b_past_also_realtime_no_grade_size(self) -> None:
        self.raw_rows = [
            _rt(
                trd_clcln_ymd=PAST.isoformat(),
                scsbd_dt="2026-09-18 08:21:00",
                grd_nm="특",
                sz_nm="20개이하",
            ),
        ]
        res = self._get(trade_date=PAST.isoformat())
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(self.fetch_calls[0][0], SOURCE_REALTIME)
        item = res.json()["items"][0]
        self.assertNotIn("grade_name", item)
        self.assertNotIn("size_name", item)
        self.assertEqual(item["auction_time"], "2026-09-18 08:21:00")

    def test_realtime_selectable_has_identity_fields(self) -> None:
        required = {
            "spm_no",
            "auctn_seq",
            "scsbd_dt",
            "mdfcn_dt",
            "whsl_mrkt_cd",
            "whsl_mrkt_nm",
            "corp_cd",
            "corp_nm",
            "plor_cd",
            "plor_nm",
            "gds_sclsf_cd",
            "gds_sclsf_nm",
            "unit_qty",
            "unit_nm",
            "qty",
            "scsbd_prc",
        }
        self.assertTrue(required.issubset(set(REALTIME_AUCTION_SELECTABLE_FIELDS)))

    def test_duplicate_external_page_stops(self) -> None:
        def request_page(page_no: int, page_size: int):
            return [_rt()], 5000

        rows = collect_pages(request_page, page_size=1000, max_pages=50)
        self.assertEqual(len(rows), 1)


if __name__ == "__main__":
    unittest.main()
