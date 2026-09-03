# -*- coding: utf-8 -*-
"""DEC-037 Stage B — 경락 후보 Core 조회 (mock source)."""

from __future__ import annotations

import os
import sqlite3
import sys
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve()
_SERVER = _HERE.parents[1]
_ROOT = _HERE.parents[2]
for p in (_HERE.parent, _SERVER, _ROOT):
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)

from core.auction_candidate_constants import (  # noqa: E402
    CODE_AUCTION_CANDIDATE_FARM_ORIGIN,
    CODE_AUCTION_CANDIDATE_NOT_FOUND,
    CODE_AUCTION_CANDIDATE_REALTIME_SOURCE,
    CODE_AUCTION_CANDIDATE_SETTLEMENT_SOURCE,
    CODE_AUCTION_CANDIDATE_STATUS,
    CODE_AUCTION_CANDIDATE_TRADE_DT,
    SOURCE_REALTIME,
    SOURCE_SETTLEMENT,
)
from core.auction_candidate_normalize import (  # noqa: E402
    corporation_match_key,
    farm_sigungu_key,
    origin_sigungu_key,
    parse_spec_kg,
)
from core.auction_candidate_service import (  # noqa: E402
    AuctionCandidateError,
    AuctionCandidateService,
)
from core.auction_ship_constants import AUCTION_SHIP_STATUS_CANCELLED  # noqa: E402
from core.market_price_manager import MarketApiRequestError  # noqa: E402
from test_auction_ship_service import (  # noqa: E402
    CORP,
    FARM,
    MARKET_CD,
    MARKET_NM,
    _insert_stock,
    _open_ops,
    _payload,
)
from core.auction_ship_service import AuctionShipService  # noqa: E402

OTHER_FARM = "OR999"
TRADE_DT = "2026-09-01"
FARM_ADDR = "경기도 화성시 정남면 제기길 143"


def _ensure_farm(conn: sqlite3.Connection, *, address: str = FARM_ADDR, farm: str = FARM) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS m_farm_info (
            farm_cd TEXT PRIMARY KEY, farm_nm TEXT, address TEXT
        )
        """
    )
    conn.execute(
        "INSERT OR REPLACE INTO m_farm_info (farm_cd, farm_nm, address) VALUES (?, ?, ?)",
        (farm, "테스트농장", address),
    )
    conn.commit()


def _create_ship(conn: sqlite3.Connection, *, qty: float = 2) -> str:
    _insert_stock(conn, storage_dt="2026-08-28", in_qty=20, stock_seq=202)
    return str(AuctionShipService(conn).create_shipment(_payload(qty))["shipment_id"])


def _row(
    *,
    origin: str = "경기 화성",
    corp: str = CORP,
    variety: str = "신고",
    spec: str = "7.5kg",
    qty: int = 4,
    price: int = 90000,
    amount: int | None = None,
    grade: str = "특",
    grade_cd: str = "G1",
    size: str = "15과",
    auction_time: str | None = None,
    market_cd: str = MARKET_CD,
    trade_date: str = TRADE_DT,
    farmer_code: str = "",
) -> dict:
    total = amount if amount is not None else qty * price
    return {
        "trade_date": trade_date,
        "market_code": market_cd,
        "market_name": MARKET_NM,
        "corp_code": "C1",
        "corp_name": corp,
        "variety_name": variety,
        "grade_name": grade,
        "grade_code": grade_cd,
        "size_name": size,
        "spec_name": spec,
        "quantity": qty,
        "avg_price": price,
        "auction_price": price,
        "total_amount": total,
        "origin_name": origin,
        "farmer_name": origin,
        "auction_time": auction_time,
        "farmer_code": farmer_code,
    }


class AuctionCandidateNormalizeTest(unittest.TestCase):
    def test_farm_hwaseong_address(self) -> None:
        self.assertEqual(farm_sigungu_key(FARM_ADDR), "화성")

    def test_origin_aliases(self) -> None:
        self.assertEqual(origin_sigungu_key("경기 화성"), "화성")
        self.assertEqual(origin_sigungu_key("화성시"), "화성")
        self.assertEqual(origin_sigungu_key("경기도 화성시"), "화성")

    def test_other_sigungu_not_equal(self) -> None:
        self.assertNotEqual(origin_sigungu_key("이천시"), farm_sigungu_key(FARM_ADDR))

    def test_corp_marks(self) -> None:
        self.assertEqual(corporation_match_key("㈜중앙청과"), corporation_match_key("중앙청과"))
        self.assertEqual(corporation_match_key("(주)중앙청과"), corporation_match_key("중앙청과"))

    def test_kg_parse(self) -> None:
        self.assertEqual(parse_spec_kg("15"), None)
        self.assertEqual(parse_spec_kg("15kg"), 15.0)
        self.assertEqual(parse_spec_kg("15.0 kg"), 15.0)
        self.assertEqual(parse_spec_kg("15 KG"), 15.0)
        self.assertEqual(parse_spec_kg("7.5kg"), 7.5)
        self.assertNotEqual(parse_spec_kg("7.5kg"), parse_spec_kg("15kg"))


class AuctionCandidateServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.path, self.conn = _open_ops()
        _ensure_farm(self.conn)
        self.sid = _create_ship(self.conn)
        self.settlement_calls = 0
        self.realtime_calls = 0
        self.settlement_rows: list[dict] = []
        self.realtime_rows: list[dict] = []

    def tearDown(self) -> None:
        self.conn.close()
        self.path.unlink(missing_ok=True)

    def _svc(self) -> AuctionCandidateService:
        def settlement(trade_dt: str, market_cd: str):
            self.settlement_calls += 1
            self.assertEqual(trade_dt, TRADE_DT)
            self.assertEqual(market_cd, MARKET_CD)
            return list(self.settlement_rows)

        def realtime(trade_dt: str, market_cd: str):
            self.realtime_calls += 1
            self.assertEqual(trade_dt, TRADE_DT)
            return list(self.realtime_rows)

        return AuctionCandidateService(
            self.conn,
            settlement_fetch=settlement,
            realtime_fetch=realtime,
        )

    def test_trade_dt_single_day(self) -> None:
        self.settlement_rows = [_row()]
        out = self._svc().list_candidates(FARM, self.sid, TRADE_DT)
        self.assertEqual(out["trade_dt"], TRADE_DT)
        self.assertEqual(len(out["items"]), 1)

    def test_invalid_trade_dt(self) -> None:
        with self.assertRaises(AuctionCandidateError) as ctx:
            self._svc().list_candidates(FARM, self.sid, "20260901")
        self.assertEqual(ctx.exception.code, CODE_AUCTION_CANDIDATE_TRADE_DT)

    def test_settlement_only_when_present(self) -> None:
        self.settlement_rows = [_row(qty=4, price=90000)]
        self.realtime_rows = [_row(qty=1, price=1, auction_time="09:00:00")]
        out = self._svc().list_candidates(FARM, self.sid, TRADE_DT)
        self.assertEqual(out["source_used"], SOURCE_SETTLEMENT)
        self.assertEqual(self.settlement_calls, 1)
        self.assertEqual(self.realtime_calls, 0)
        self.assertEqual(out["items"][0]["qty"], 4)

    def test_settlement_zero_falls_back_realtime(self) -> None:
        self.settlement_rows = []
        self.realtime_rows = [_row(auction_time="10:11:12")]
        out = self._svc().list_candidates(FARM, self.sid, TRADE_DT)
        self.assertEqual(out["source_used"], SOURCE_REALTIME)
        self.assertEqual(self.realtime_calls, 1)
        self.assertTrue(out["items"][0]["requires_grade_input"])

    def test_settlement_error_not_empty(self) -> None:
        def boom(trade_dt: str, market_cd: str):
            raise MarketApiRequestError("timeout")

        def realtime(trade_dt: str, market_cd: str):
            self.fail("realtime must not run on settlement error")

        svc = AuctionCandidateService(
            self.conn, settlement_fetch=boom, realtime_fetch=realtime
        )
        with self.assertRaises(AuctionCandidateError) as ctx:
            svc.list_candidates(FARM, self.sid, TRADE_DT)
        self.assertEqual(ctx.exception.code, CODE_AUCTION_CANDIDATE_SETTLEMENT_SOURCE)

    def test_realtime_error(self) -> None:
        def empty(_a, _b):
            return []

        def boom(_a, _b):
            raise MarketApiRequestError("auth")

        svc = AuctionCandidateService(
            self.conn, settlement_fetch=empty, realtime_fetch=boom
        )
        with self.assertRaises(AuctionCandidateError) as ctx:
            svc.list_candidates(FARM, self.sid, TRADE_DT)
        self.assertEqual(ctx.exception.code, CODE_AUCTION_CANDIDATE_REALTIME_SOURCE)

    def test_both_empty(self) -> None:
        out = self._svc().list_candidates(FARM, self.sid, TRADE_DT)
        self.assertEqual(out["source_used"], SOURCE_REALTIME)
        self.assertEqual(out["items"], [])

    def test_exclude_other_sigungu(self) -> None:
        self.settlement_rows = [_row(origin="이천시"), _row(origin="화성시")]
        out = self._svc().list_candidates(FARM, self.sid, TRADE_DT)
        self.assertEqual(len(out["items"]), 1)
        self.assertEqual(out["items"][0]["origin_name"], "화성시")

    def test_exclude_other_corporation(self) -> None:
        self.settlement_rows = [
            _row(corp="동화청과"),
            _row(corp="한국청과"),
        ]
        out = self._svc().list_candidates(FARM, self.sid, TRADE_DT)
        self.assertEqual(len(out["items"]), 1)
        self.assertEqual(corporation_match_key(out["items"][0]["corporation_name"]), "한국청과")

    def test_exclude_other_variety(self) -> None:
        self.settlement_rows = [_row(variety="원황"), _row(variety="신고배")]
        out = self._svc().list_candidates(FARM, self.sid, TRADE_DT)
        self.assertEqual(len(out["items"]), 1)
        self.assertEqual(out["items"][0]["variety_name"], "신고배")

    def test_exclude_other_kg_and_malformed(self) -> None:
        self.settlement_rows = [
            _row(spec="15kg", price=1000),
            _row(spec="상자", price=2000),
            _row(spec="7.5 KG", price=90000),
        ]
        out = self._svc().list_candidates(FARM, self.sid, TRADE_DT)
        self.assertEqual(len(out["items"]), 1)
        self.assertEqual(out["items"][0]["spec_kg"], 7.5)
        reasons = {row["reason"] for row in out["skipped"]}
        self.assertIn("spec", reasons)

    def test_settlement_keeps_grade(self) -> None:
        self.settlement_rows = [_row(grade="특", grade_cd="G1")]
        item = self._svc().list_candidates(FARM, self.sid, TRADE_DT)["items"][0]
        self.assertEqual(item["grade_name"], "특")
        self.assertEqual(item["grade_cd"], "G1")
        self.assertFalse(item["requires_grade_input"])

    def test_realtime_grade_not_inferred(self) -> None:
        self.realtime_rows = [_row(grade="특", grade_cd="G1", auction_time="09:01:02")]
        item = self._svc().list_candidates(FARM, self.sid, TRADE_DT)["items"][0]
        self.assertIsNone(item["grade_name"])
        self.assertIsNone(item["grade_cd"])
        self.assertTrue(item["requires_grade_input"])

    def test_keep_n_price_rows(self) -> None:
        self.settlement_rows = [
            _row(qty=4, price=90000, farmer_code="a"),
            _row(qty=3, price=87000, farmer_code="b"),
            _row(qty=3, price=85000, farmer_code="c"),
        ]
        items = self._svc().list_candidates(FARM, self.sid, TRADE_DT)["items"]
        self.assertEqual(len(items), 3)
        self.assertEqual([i["unit_price"] for i in items], [90000, 87000, 85000])

    def test_source_key_deterministic_and_unique(self) -> None:
        self.settlement_rows = [
            _row(qty=4, price=90000, farmer_code="a"),
            _row(qty=3, price=87000, farmer_code="b"),
        ]
        first = self._svc().list_candidates(FARM, self.sid, TRADE_DT)["items"]
        second = self._svc().list_candidates(FARM, self.sid, TRADE_DT)["items"]
        self.assertEqual(first[0]["source_key"], second[0]["source_key"])
        self.assertNotEqual(first[0]["source_key"], first[1]["source_key"])
        self.assertNotIn("stock_seq", first[0])

    def test_cancelled_reject(self) -> None:
        AuctionShipService(self.conn).cancel_shipment(FARM, self.sid)
        self.settlement_rows = [_row()]
        with self.assertRaises(AuctionCandidateError) as ctx:
            self._svc().list_candidates(FARM, self.sid, TRADE_DT)
        self.assertEqual(ctx.exception.code, CODE_AUCTION_CANDIDATE_STATUS)

    def test_other_farm_reject(self) -> None:
        with self.assertRaises(AuctionCandidateError) as ctx:
            self._svc().list_candidates(OTHER_FARM, self.sid, TRADE_DT)
        self.assertEqual(ctx.exception.code, CODE_AUCTION_CANDIDATE_NOT_FOUND)

    def test_farm_origin_missing(self) -> None:
        _ensure_farm(self.conn, address="경기도")
        self.settlement_rows = [_row()]
        with self.assertRaises(AuctionCandidateError) as ctx:
            self._svc().list_candidates(FARM, self.sid, TRADE_DT)
        self.assertEqual(ctx.exception.code, CODE_AUCTION_CANDIDATE_FARM_ORIGIN)


if __name__ == "__main__":
    unittest.main()
