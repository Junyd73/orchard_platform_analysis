# -*- coding: utf-8 -*-
"""DEC-037 Stage B — 경락 후보 Core 조회 (mock source)."""

from __future__ import annotations

import os
import math
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
    fruit_count_bucket_label,
    internal_fruit_count_bucket,
    market_fruit_count_bucket,
    origin_sigungu_key,
    parse_spec_kg,
    settlement_box_qty,
)
from core.auction_candidate_service import (  # noqa: E402
    SKIP_QUANTITY,
    AuctionCandidateError,
    AuctionCandidateService,
    _source_key,
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
    qty: int | float = 4,
    price: int = 90000,
    amount: int | None = None,
    grade: str = "특",
    grade_cd: str = "G1",
    size: str = "10과이내",
    auction_time: str | None = None,
    market_cd: str = MARKET_CD,
    trade_date: str = TRADE_DT,
    farmer_code: str = "",
) -> dict:
    total = amount if amount is not None else int(qty) * price
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


def _kg_row(
    *,
    boxes: int = 4,
    spec: str = "7.5kg",
    price: int = 90000,
    amount: int | None = None,
    **kwargs,
) -> dict:
    """SETTLEMENT fixture — quantity는 총 kg, amount는 박스×단가."""
    kg = parse_spec_kg(spec)
    if kg is None:
        raise AssertionError(f"invalid spec for _kg_row: {spec}")
    raw = float(boxes) * float(kg)
    raw_qty: int | float = int(round(raw)) if abs(raw - round(raw)) < 1e-9 else raw
    return _row(
        qty=raw_qty,
        price=price,
        amount=boxes * price if amount is None else amount,
        spec=spec,
        **kwargs,
    )


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

    def test_fruit_count_bucket_tables(self) -> None:
        size_cds = [
            "FR020101",
            "FR020102",
            "FR020103",
            "FR020104",
            "FR020105",
            "FR020106",
            "FR020107",
        ]
        expect = {
            15.0: [20, 25, 30, 35, 40, 45, 50],
            7.5: [10, 12, 15, 17, 20, 22, 25],
            5.0: [6, 8, 10, 11, 13, 15, 16],
        }
        for weight, buckets in expect.items():
            for size_cd, bucket in zip(size_cds, buckets, strict=True):
                with self.subTest(size_cd=size_cd, weight=weight):
                    self.assertEqual(internal_fruit_count_bucket(size_cd, weight), bucket)
        self.assertEqual(internal_fruit_count_bucket("FR020101", 15), 20)
        self.assertEqual(internal_fruit_count_bucket("FR020101", 7.5), 10)
        self.assertEqual(internal_fruit_count_bucket("FR020101", 5), 6)
        self.assertIsNone(internal_fruit_count_bucket("FR020100", 15))
        self.assertIsNone(internal_fruit_count_bucket("FR020101", 10))
        self.assertIsNone(internal_fruit_count_bucket("SZ010403", 15))

    def test_market_fruit_count_bucket_labels(self) -> None:
        cases = [
            ("20개이하", 15, 20),
            ("20개 이하", 15, 20),
            ("20과이내", 15, 20),
            ("20과 이내", 15, 20),
            ("20개", 15, 20),
            ("20내", 15, 20),
            ("25내", 15, 25),
            ("30내(5단위)", 15, 30),
            ("35내", 15, 35),
            ("40내(5단위)", 15, 40),
            ("45내", 15, 45),
            ("50내", 15, 50),
            ("10과이내", 7.5, 10),
            ("12개", 7.5, 12),
            ("6과이내", 5, 6),
        ]
        for label, weight, bucket in cases:
            with self.subTest(label=label, weight=weight):
                self.assertEqual(market_fruit_count_bucket(label, weight), bucket)
        self.assertIsNone(market_fruit_count_bucket("", 15))
        self.assertIsNone(market_fruit_count_bucket("대과", 15))
        self.assertIsNone(market_fruit_count_bucket("27과", 15))
        self.assertIsNone(market_fruit_count_bucket("14과", 7.5))
        self.assertIsNone(market_fruit_count_bucket("20과", 5))
        self.assertEqual(fruit_count_bucket_label(20), "20과이내")

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
        self.settlement_rows = [_kg_row()]
        out = self._svc().list_candidates(FARM, self.sid, TRADE_DT)
        self.assertEqual(out["trade_dt"], TRADE_DT)
        self.assertEqual(len(out["items"]), 1)

    def test_invalid_trade_dt(self) -> None:
        with self.assertRaises(AuctionCandidateError) as ctx:
            self._svc().list_candidates(FARM, self.sid, "20260901")
        self.assertEqual(ctx.exception.code, CODE_AUCTION_CANDIDATE_TRADE_DT)

    def test_settlement_only_when_present(self) -> None:
        self.settlement_rows = [_kg_row(boxes=4, price=90000)]
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
        self.settlement_rows = [_kg_row(origin="이천시"), _kg_row(origin="화성시")]
        out = self._svc().list_candidates(FARM, self.sid, TRADE_DT)
        self.assertEqual(len(out["items"]), 1)
        self.assertEqual(out["items"][0]["origin_name"], "화성시")

    def test_exclude_other_corporation(self) -> None:
        self.settlement_rows = [
            _kg_row(corp="동화청과"),
            _kg_row(corp="한국청과"),
        ]
        out = self._svc().list_candidates(FARM, self.sid, TRADE_DT)
        self.assertEqual(len(out["items"]), 1)
        self.assertEqual(corporation_match_key(out["items"][0]["corporation_name"]), "한국청과")

    def test_exclude_other_variety(self) -> None:
        self.settlement_rows = [_kg_row(variety="원황"), _kg_row(variety="신고배")]
        out = self._svc().list_candidates(FARM, self.sid, TRADE_DT)
        self.assertEqual(len(out["items"]), 1)
        self.assertEqual(out["items"][0]["variety_name"], "신고배")

    def test_exclude_other_kg_and_malformed(self) -> None:
        self.settlement_rows = [
            _kg_row(spec="15kg", price=1000),
            _row(qty=30, spec="상자", price=2000, amount=8000),
            _kg_row(spec="7.5 KG", price=90000),
        ]
        out = self._svc().list_candidates(FARM, self.sid, TRADE_DT)
        self.assertEqual(len(out["items"]), 1)
        self.assertEqual(out["items"][0]["spec_kg"], 7.5)
        reasons = {row["reason"] for row in out["skipped"]}
        self.assertIn("spec", reasons)

    def test_settlement_kg_to_boxes_helper_and_7_5(self) -> None:
        cases = [
            (390, 15, 26),
            (540, 15, 36),
            (75, 15, 5),
            (285, 15, 19),
            (15, 15, 1),
            (75, 7.5, 10),
            (50, 5, 10),
        ]
        for raw, kg, boxes in cases:
            with self.subTest(raw=raw, kg=kg):
                self.assertEqual(settlement_box_qty(raw, kg), boxes)
        self.assertIsNone(settlement_box_qty(392, 15))
        self.assertIsNone(settlement_box_qty(30, None))
        self.assertIsNone(settlement_box_qty(30, 0))
        self.assertIsNone(settlement_box_qty(0, 15))
        self.assertIsNone(settlement_box_qty(-15, 15))
        # 7.5kg shipment path
        self.settlement_rows = [
            _row(qty=75, spec="7.5kg", price=90000, amount=900000, variety="신고")
        ]
        out = self._svc().list_candidates(FARM, self.sid, TRADE_DT)
        self.assertEqual(out["items"][0]["qty"], 10)
        self.assertEqual(out["items"][0]["amount"], 900000)

    def test_settlement_15kg_ops_rows(self) -> None:
        from core.auction_ship_service import AuctionShipCreateIn, AuctionShipSpecLineIn
        from test_auction_ship_service import GRADE, ITEM, SIZE, VARIETY, YEAR

        self.conn.execute(
            """
            INSERT OR REPLACE INTO t_stock_master (
                stock_seq, farm_cd, wh_cd, item_cd, variety_cd, grade_cd, size_cd,
                weight, harvest_year, storage_dt, in_qty, out_qty, reserved_qty, reg_id
            ) VALUES (901, ?, 'WH01', ?, ?, ?, ?, 15, ?, '2026-08-20', 80, 0, 0, 't')
            """,
            (FARM, ITEM, VARIETY, GRADE, SIZE, YEAR),
        )
        self.conn.commit()
        sid = str(
            AuctionShipService(self.conn).create_shipment(
                AuctionShipCreateIn(
                    farm_cd=FARM,
                    ship_dt="2026-08-25",
                    market_cd=MARKET_CD,
                    market_name=MARKET_NM,
                    corporation_name=CORP,
                    custm_id=None,
                    lines=[
                        AuctionShipSpecLineIn(
                            item_cd=ITEM,
                            variety_cd=VARIETY,
                            grade_cd=GRADE,
                            size_cd=SIZE,
                            weight=15,
                            harvest_year=YEAR,
                            wh_cd="WH01",
                            qty=26,
                        )
                    ],
                )
            )["shipment_id"]
        )
        self.settlement_rows = [
            _row(qty=390, spec="15kg", price=47000, amount=1222000, variety="신고", size="20개이하"),
            _row(qty=540, spec="15kg", price=50000, amount=1800000, variety="신고", size="25내"),
            _row(qty=75, spec="15kg", price=33000, amount=165000, variety="신고", size="30내(5단위)"),
            _row(qty=285, spec="15kg", price=44000, amount=836000, variety="신고", size="35내"),
            _row(qty=15, spec="15kg", price=16000, amount=16000, variety="신고", size="40내(5단위)"),
        ]
        out = self._svc().list_candidates(FARM, sid, TRADE_DT)
        self.assertEqual(out["source_used"], SOURCE_SETTLEMENT)
        self.assertEqual(sorted(i["qty"] for i in out["items"]), [1, 5, 19, 26, 36])
        self.assertEqual(
            sorted(i["fruit_count_bucket"] for i in out["items"]),
            [20, 25, 30, 35, 40],
        )

    def test_settlement_non_integral_and_invalid_skipped(self) -> None:
        self.settlement_rows = [
            _row(qty=392, spec="7.5kg", price=90000, amount=4704000),
            _row(qty=0, spec="7.5kg", price=90000, amount=0),
            _row(qty=-15, spec="7.5kg", price=90000, amount=90000),
            _kg_row(boxes=4, price=90000),
        ]
        out = self._svc().list_candidates(FARM, self.sid, TRADE_DT)
        self.assertEqual(len(out["items"]), 1)
        self.assertEqual(out["items"][0]["qty"], 4)
        self.assertTrue(any(s["reason"] == SKIP_QUANTITY for s in out["skipped"]))

    def test_settlement_amount_mismatch_kept(self) -> None:
        """totprc/avgprc ≠ box_qty여도 weight 기반 qty면 candidate 유지."""
        self.settlement_rows = [
            _row(qty=30, spec="7.5kg", price=90000, amount=999999),
            _kg_row(boxes=4, price=90000),
        ]
        out = self._svc().list_candidates(FARM, self.sid, TRADE_DT)
        self.assertEqual(out["source_used"], SOURCE_SETTLEMENT)
        self.assertEqual(len(out["items"]), 2)
        mismatch = next(i for i in out["items"] if i["amount"] == 999999)
        self.assertEqual(mismatch["qty"], 4)
        self.assertEqual(mismatch["unit_price"], 90000)
        self.assertFalse(any(s["reason"] == SKIP_QUANTITY for s in out["skipped"]))

    def test_settlement_avgprc_rounding_keeps_candidate(self) -> None:
        """avgprc 반올림으로 amount/price ≠ box여도 qty=weight SSOT 유지."""
        from core.auction_ship_service import AuctionShipCreateIn, AuctionShipSpecLineIn
        from test_auction_ship_service import GRADE, ITEM, SIZE, VARIETY, YEAR

        self.conn.execute(
            """
            INSERT OR REPLACE INTO t_stock_master (
                stock_seq, farm_cd, wh_cd, item_cd, variety_cd, grade_cd, size_cd,
                weight, harvest_year, storage_dt, in_qty, out_qty, reserved_qty, reg_id
            ) VALUES (903, ?, 'WH01', ?, ?, ?, ?, 15, ?, '2026-08-20', 80, 0, 0, 't')
            """,
            (FARM, ITEM, VARIETY, GRADE, SIZE, YEAR),
        )
        self.conn.commit()
        sid = str(
            AuctionShipService(self.conn).create_shipment(
                AuctionShipCreateIn(
                    farm_cd=FARM,
                    ship_dt="2026-08-25",
                    market_cd=MARKET_CD,
                    market_name=MARKET_NM,
                    corporation_name=CORP,
                    custm_id=None,
                    lines=[
                        AuctionShipSpecLineIn(
                            item_cd=ITEM,
                            variety_cd=VARIETY,
                            grade_cd=GRADE,
                            size_cd=SIZE,
                            weight=15,
                            harvest_year=YEAR,
                            wh_cd="WH01",
                            qty=26,
                        )
                    ],
                )
            )["shipment_id"]
        )
        # 1,220,000 / 46,923 ≈ 26.00004 — 정수 26과 정확히 일치하지 않음
        self.assertFalse(math.isclose(1220000 / 46923, 26.0, rel_tol=0.0, abs_tol=1e-9))
        self.settlement_rows = [
            _row(
                qty=390,
                spec="15kg",
                price=46923,
                amount=1220000,
                variety="신고",
                size="20개이하",
            )
        ]
        out = self._svc().list_candidates(FARM, sid, TRADE_DT)
        self.assertEqual(len(out["items"]), 1)
        item = out["items"][0]
        self.assertEqual(item["qty"], 26)
        self.assertEqual(item["unit_price"], 46923)
        self.assertEqual(item["amount"], 1220000)
        self.assertEqual(item["fruit_count_bucket"], 20)
        self.assertFalse(any(s["reason"] == SKIP_QUANTITY for s in out["skipped"]))

    def test_settlement_avgprc_rounding_75kg_row(self) -> None:
        from core.auction_ship_service import AuctionShipCreateIn, AuctionShipSpecLineIn
        from test_auction_ship_service import GRADE, ITEM, SIZE, VARIETY, YEAR

        self.conn.execute(
            """
            INSERT OR REPLACE INTO t_stock_master (
                stock_seq, farm_cd, wh_cd, item_cd, variety_cd, grade_cd, size_cd,
                weight, harvest_year, storage_dt, in_qty, out_qty, reserved_qty, reg_id
            ) VALUES (904, ?, 'WH01', ?, ?, ?, ?, 15, ?, '2026-08-20', 80, 0, 0, 't')
            """,
            (FARM, ITEM, VARIETY, GRADE, SIZE, YEAR),
        )
        self.conn.commit()
        sid = str(
            AuctionShipService(self.conn).create_shipment(
                AuctionShipCreateIn(
                    farm_cd=FARM,
                    ship_dt="2026-08-25",
                    market_cd=MARKET_CD,
                    market_name=MARKET_NM,
                    corporation_name=CORP,
                    custm_id=None,
                    lines=[
                        AuctionShipSpecLineIn(
                            item_cd=ITEM,
                            variety_cd=VARIETY,
                            grade_cd=GRADE,
                            size_cd=SIZE,
                            weight=15,
                            harvest_year=YEAR,
                            wh_cd="WH01",
                            qty=5,
                        )
                    ],
                )
            )["shipment_id"]
        )
        # 165000 / 33001 ≈ 4.99985 — 정수 5와 정확히 일치하지 않음
        self.assertFalse(math.isclose(165000 / 33001, 5.0, rel_tol=0.0, abs_tol=1e-9))
        self.settlement_rows = [
            _row(qty=75, spec="15kg", price=33001, amount=165000, variety="신고", size="30내")
        ]
        out = self._svc().list_candidates(FARM, sid, TRADE_DT)
        self.assertEqual(len(out["items"]), 1)
        self.assertEqual(out["items"][0]["qty"], 5)
        self.assertEqual(out["items"][0]["amount"], 165000)
        self.assertEqual(out["items"][0]["unit_price"], 33001)

    def test_settlement_all_qty_invalid_falls_back_realtime(self) -> None:
        self.settlement_rows = [_row(qty=392, spec="7.5kg", price=90000, amount=4704000)]
        self.realtime_rows = [_row(qty=2, price=88000, auction_time="09:00:00")]
        out = self._svc().list_candidates(FARM, self.sid, TRADE_DT)
        self.assertEqual(out["source_used"], SOURCE_REALTIME)
        self.assertEqual(out["items"][0]["qty"], 2)
        self.assertEqual(self.realtime_calls, 1)

    def test_realtime_qty_not_converted(self) -> None:
        self.realtime_rows = [_row(qty=4, spec="7.5kg", price=90000, auction_time="09:00:00")]
        out = self._svc().list_candidates(FARM, self.sid, TRADE_DT)
        self.assertEqual(out["source_used"], SOURCE_REALTIME)
        self.assertEqual(out["items"][0]["qty"], 4)

    def test_source_key_uses_raw_kg_not_box_qty(self) -> None:
        from core.auction_ship_service import AuctionShipCreateIn, AuctionShipSpecLineIn
        from test_auction_ship_service import GRADE, ITEM, SIZE, VARIETY, YEAR

        expected = _source_key(
            {
                "source_type": SOURCE_SETTLEMENT,
                "trade_dt": TRADE_DT,
                "market_cd": MARKET_CD,
                "corp_code": "C1",
                "corp_name": CORP,
                "variety_name": "신고",
                "spec_name": "15kg",
                "qty": 390,
                "unit_price": 47000,
                "auction_time": "",
                "origin_name": "경기 화성",
                "grade_name": "특",
                "farmer_code": "",
            }
        )
        self.conn.execute(
            """
            INSERT OR REPLACE INTO t_stock_master (
                stock_seq, farm_cd, wh_cd, item_cd, variety_cd, grade_cd, size_cd,
                weight, harvest_year, storage_dt, in_qty, out_qty, reserved_qty, reg_id
            ) VALUES (902, ?, 'WH01', ?, ?, ?, ?, 15, ?, '2026-08-20', 50, 0, 0, 't')
            """,
            (FARM, ITEM, VARIETY, GRADE, SIZE, YEAR),
        )
        self.conn.commit()
        sid = str(
            AuctionShipService(self.conn).create_shipment(
                AuctionShipCreateIn(
                    farm_cd=FARM,
                    ship_dt="2026-08-25",
                    market_cd=MARKET_CD,
                    market_name=MARKET_NM,
                    corporation_name=CORP,
                    custm_id=None,
                    lines=[
                        AuctionShipSpecLineIn(
                            item_cd=ITEM,
                            variety_cd=VARIETY,
                            grade_cd=GRADE,
                            size_cd=SIZE,
                            weight=15,
                            harvest_year=YEAR,
                            wh_cd="WH01",
                            qty=26,
                        )
                    ],
                )
            )["shipment_id"]
        )
        self.settlement_rows = [
            _row(qty=390, spec="15kg", price=47000, amount=1222000, variety="신고", size="20개이하")
        ]
        item = self._svc().list_candidates(FARM, sid, TRADE_DT)["items"][0]
        self.assertEqual(item["qty"], 26)
        self.assertEqual(item["fruit_count_bucket"], 20)
        self.assertEqual(item["source_key"], expected)

    def test_settlement_keeps_grade(self) -> None:
        self.settlement_rows = [_kg_row(grade="특", grade_cd="G1")]
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
            _kg_row(boxes=4, price=90000, farmer_code="a"),
            _kg_row(boxes=3, price=87000, farmer_code="b"),
            _kg_row(boxes=3, price=85000, farmer_code="c"),
        ]
        items = self._svc().list_candidates(FARM, self.sid, TRADE_DT)["items"]
        self.assertEqual(len(items), 3)
        self.assertEqual([i["unit_price"] for i in items], [90000, 87000, 85000])
        self.assertEqual([i["qty"] for i in items], [4, 3, 3])

    def test_source_key_deterministic_and_unique(self) -> None:
        self.settlement_rows = [
            _kg_row(boxes=4, price=90000, farmer_code="a"),
            _kg_row(boxes=3, price=87000, farmer_code="b"),
        ]
        first = self._svc().list_candidates(FARM, self.sid, TRADE_DT)["items"]
        second = self._svc().list_candidates(FARM, self.sid, TRADE_DT)["items"]
        self.assertEqual(first[0]["source_key"], second[0]["source_key"])
        self.assertNotEqual(first[0]["source_key"], first[1]["source_key"])
        self.assertNotIn("stock_seq", first[0])

    def test_cancelled_reject(self) -> None:
        AuctionShipService(self.conn).cancel_shipment(FARM, self.sid)
        self.settlement_rows = [_kg_row()]
        with self.assertRaises(AuctionCandidateError) as ctx:
            self._svc().list_candidates(FARM, self.sid, TRADE_DT)
        self.assertEqual(ctx.exception.code, CODE_AUCTION_CANDIDATE_STATUS)

    def test_other_farm_reject(self) -> None:
        with self.assertRaises(AuctionCandidateError) as ctx:
            self._svc().list_candidates(OTHER_FARM, self.sid, TRADE_DT)
        self.assertEqual(ctx.exception.code, CODE_AUCTION_CANDIDATE_NOT_FOUND)

    def test_farm_origin_missing(self) -> None:
        _ensure_farm(self.conn, address="경기도")
        self.settlement_rows = [_kg_row()]
        with self.assertRaises(AuctionCandidateError) as ctx:
            self._svc().list_candidates(FARM, self.sid, TRADE_DT)
        self.assertEqual(ctx.exception.code, CODE_AUCTION_CANDIDATE_FARM_ORIGIN)


if __name__ == "__main__":
    unittest.main()
