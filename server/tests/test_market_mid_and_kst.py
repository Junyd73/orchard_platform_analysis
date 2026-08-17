# -*- coding: utf-8 -*-
"""배 중분류 API 조건 · 품종 선별 · 알림 created_at KST."""

from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import time
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

_SERVER = Path(__file__).resolve().parents[1]
_REPO = _SERVER.parent
for p in (_REPO, _SERVER):
    s = str(p)
    if s in sys.path:
        sys.path.remove(s)
sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(_SERVER))

os.environ["ORCHARD_NOTIFICATION_SCHEDULER"] = "0"


class PearMidItemCodeTest(unittest.TestCase):
    def test_append_mid_class_omits_sclsf(self) -> None:
        from core.market_price_manager import (
            PEAR_MID_ITEM_CODE,
            _MarketApiBase,
        )

        class _T(_MarketApiBase):
            pass

        mgr = _T()
        params: dict = {}
        mgr._append_item_code_conditions(params, PEAR_MID_ITEM_CODE)
        self.assertEqual(params.get("cond[gds_lclsf_cd::EQ]"), "06")
        self.assertEqual(params.get("cond[gds_mclsf_cd::EQ]"), "02")
        self.assertNotIn("cond[gds_sclsf_cd::EQ]", params)

    def test_append_three_part_keeps_sclsf(self) -> None:
        from core.market_price_manager import _MarketApiBase

        class _T(_MarketApiBase):
            pass

        mgr = _T()
        params: dict = {}
        mgr._append_item_code_conditions(params, "06-02-01")
        self.assertEqual(params.get("cond[gds_sclsf_cd::EQ]"), "01")


class VarietyFocusTest(unittest.TestCase):
    def test_select_focus_includes_top_even_if_not_interest(self) -> None:
        from app.agents.market_agent import (
            build_corp_packets,
            select_focus_varieties,
            summarize_variety_prices,
        )

        rows = [
            {
                "variety_name": "원황",
                "spec_name": "15kg 상자",
                "corp_name": "농협가락(공)",
                "quantity": 10,
                "auction_price": 100000,
            },
            {
                "variety_name": "원황(배)",
                "spec_name": "15kg 상자",
                "corp_name": "중앙청과",
                "quantity": 5,
                "auction_price": 52000,
            },
            {
                "variety_name": "신화",
                "spec_name": "15kg 상자",
                "corp_name": "농협가락(공)",
                "quantity": 8,
                "auction_price": 72000,
            },
            {
                "variety_name": "배(신화)",
                "spec_name": "15kg 상자",
                "corp_name": "동화청과",
                "quantity": 3,
                "auction_price": 50000,
            },
            {
                "variety_name": "신고",
                "spec_name": "15kg 파렛트",
                "corp_name": "서울청과",
                "quantity": 42,
                "auction_price": 44000,
            },
        ]
        summaries = summarize_variety_prices(rows)
        names = [r["variety"] for r in summaries]
        self.assertEqual(names[0], "원황")
        self.assertIn("신화", names)
        self.assertIn("신고", names)
        # 배(신화)는 신화로 합쳐져 별도 키 없음
        self.assertNotIn("배(신화)", names)
        sinhwa = next(r for r in summaries if r["variety"] == "신화")
        self.assertEqual(sinhwa["max_price"], 72000)
        self.assertEqual(sinhwa["row_count"], 2)

        focus = select_focus_varieties(summaries)
        focus_names = [r["variety"] for r in focus]
        self.assertIn("신고", focus_names)
        self.assertIn("원황", focus_names)
        self.assertIn("신화", focus_names)  # TOP3
        self.assertTrue(
            any(r.get("role") == "interest+daily_top" for r in focus if r["variety"] == "원황")
        )

        # 신화가 최고가인 경우 daily_top으로 포함
        rows2 = [
            {
                "variety_name": "신화",
                "spec_name": "15kg",
                "corp_name": "농협가락(공)",
                "quantity": 1,
                "auction_price": 200000,
            },
            {
                "variety_name": "신고",
                "spec_name": "15kg",
                "corp_name": "서울청과",
                "quantity": 1,
                "auction_price": 40000,
            },
        ]
        focus2 = select_focus_varieties(summarize_variety_prices(rows2))
        self.assertEqual([r["variety"] for r in focus2], ["신고", "신화"])
        self.assertEqual(focus2[1]["role"], "daily_top")

        # 신고 법인 패킷 회귀 + focus_varieties 포함
        packet = build_corp_packets(rows)
        self.assertEqual(packet["variety"], "신고")
        self.assertTrue(packet["corps"])
        self.assertGreaterEqual(len(packet["focus_varieties"]), 2)
        body_names = {v["variety"] for v in packet["focus_varieties"]}
        self.assertIn("신고", body_names)
        self.assertIn("원황", body_names)

    def test_top3_ignores_outlier_spec_and_corp(self) -> None:
        from app.agents.market_agent import (
            select_focus_varieties,
            summarize_variety_prices,
        )

        rows = [
            {
                "variety_name": "신고",
                "spec_name": "15kg 상자",
                "corp_name": "서울청과",
                "quantity": 40,
                "auction_price": 44000,
            },
            {
                "variety_name": "원황",
                "spec_name": "15kg 상자",
                "corp_name": "농협가락(공)",
                "quantity": 10,
                "auction_price": 100000,
            },
            {
                "variety_name": "신화",
                "spec_name": "15kg 상자",
                "corp_name": "농협가락(공)",
                "quantity": 5,
                "auction_price": 72000,
            },
            # 이상치: 1kg · 비대상 법인 · qty1 — TOP3 왜곡 금지
            {
                "variety_name": "신화",
                "spec_name": "1kg 망",
                "corp_name": "기타법인",
                "quantity": 1,
                "auction_price": 999999,
            },
        ]
        summaries = summarize_variety_prices(rows)
        by_name = {r["variety"]: r["max_price"] for r in summaries}
        self.assertEqual(by_name.get("신화"), 72000)
        self.assertNotEqual(by_name.get("신화"), 999999)
        focus = select_focus_varieties(summaries)
        top = focus[0] if focus and focus[0].get("role") == "interest+daily_top" else None
        # 원황이 daily top
        won = next(r for r in focus if r["variety"] == "원황")
        self.assertEqual(won["max_price"], 100000)
        sinhwa = next(r for r in focus if r["variety"] == "신화")
        self.assertEqual(sinhwa["max_price"], 72000)


class VarietyNormalizeSsotTest(unittest.TestCase):
    def test_normalize_aliases(self) -> None:
        from core.market_variety_normalize import normalize_variety_name
        from core.services.market_analysis_service import MarketAnalysisService

        cases = [
            ("원황(배)", "원황"),
            ("배(원황)", "원황"),
            ("배(신화)", "신화"),
            ("신화배", "신화"),
            ("신고(배)", "신고"),
        ]
        for raw, expect in cases:
            self.assertEqual(normalize_variety_name(raw), expect, msg=raw)
            class _T:
                normalize_variety = MarketAnalysisService.normalize_variety

            self.assertEqual(_T().normalize_variety(raw), expect)

    def test_settlement_merges_sinhwa_aliases(self) -> None:
        from app.services.observation_ai_db_bridge import ServerDbBridge
        from core.services.market_analysis_service import MarketAnalysisService

        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        mas = MarketAnalysisService(ServerDbBridge(conn))
        mas._ensure_tables()
        rows = [
            {
                "trade_date": "2026-08-15",
                "variety_name": "신화",
                "market_name": "가락",
                "corp_name": "농협가락(공)",
                "grade_name": "특",
                "size_name": "",
                "spec_name": "15kg 상자",
                "unit_price": 72000,
                "quantity": 8,
                "item_name": "배",
                "__source": "sale",
            },
            {
                "trade_date": "2026-08-15",
                "variety_name": "배(신화)",
                "market_name": "가락",
                "corp_name": "동화청과",
                "grade_name": "특",
                "size_name": "",
                "spec_name": "15kg 상자",
                "unit_price": 50000,
                "quantity": 3,
                "item_name": "배",
                "__source": "sale",
            },
            {
                "trade_date": "2026-08-15",
                "variety_name": "원황(배)",
                "market_name": "가락",
                "corp_name": "중앙청과",
                "grade_name": "특",
                "size_name": "",
                "spec_name": "15kg 상자",
                "unit_price": 52000,
                "quantity": 5,
                "item_name": "배",
                "__source": "sale",
            },
        ]
        mas.insert_settlement_data(rows)
        norms = {
            r["normalized_variety"]
            for r in mas.db.execute_query(
                "SELECT DISTINCT normalized_variety FROM market_price_settlement"
            )
        }
        self.assertEqual(norms, {"신화", "원황"})
        mas.build_summary_for_date("2026-08-15")
        summary_names = {
            r["normalized_variety"]
            for r in mas.get_summary("2026-08-15", "2026-08-15", None, "가락")
        }
        self.assertEqual(summary_names, {"신화", "원황"})


class ItemCodeReverseMapTest(unittest.TestCase):
    def test_mid_class_does_not_infer_singo(self) -> None:
        from core.market_price_service import MarketPriceService

        class _Fake:
            pass

        svc = MarketPriceService(_Fake())
        self.assertEqual(svc._find_variety_name_by_item_code("06-02"), "")
        self.assertEqual(svc._find_variety_name_by_item_code("0602"), "")
        self.assertEqual(svc._find_variety_name_by_item_code("06-02-01"), "신고")
        self.assertEqual(svc._find_variety_name_by_item_code("06-02-03"), "화산")
        # legacy (market_code, item_code=06-02) → variety_name 빈 문자열
        q = svc._build_query_params("2026-08-15", "110001", "06-02")
        self.assertEqual(q["item_code"], "06-02")
        self.assertEqual(q["variety_name"], "")
        # 명시적 품종명 경로는 신고 유지
        q2 = svc._build_query_params("2026-08-15", "신고", "가락")
        self.assertEqual(q2["variety_name"], "신고")
        self.assertEqual(q2["item_code"], "06-02")
        # 3단 코드 명시 전달 시 passthrough
        q3 = svc._build_query_params(
            "2026-08-15", "신고", "가락", item_code="06-02-01"
        )
        self.assertEqual(q3["item_code"], "06-02-01")
        self.assertEqual(q3["variety_name"], "신고")


class NotificationCreatedAtKstTest(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["TZ"] = "UTC"
        time.tzset()
        fd, name = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.db = Path(name)
        self.db.unlink(missing_ok=True)
        conn = sqlite3.connect(str(self.db))
        conn.executescript(
            """
            CREATE TABLE m_farm_info (
                farm_cd TEXT PRIMARY KEY, farm_nm TEXT,
                lat REAL, lon REAL, nx INTEGER, ny INTEGER
            );
            INSERT INTO m_farm_info VALUES ('OR001', '테스트', 37.2, 126.8, 60, 120);
            CREATE TABLE m_common_code (
                farm_cd TEXT, code_cd TEXT, code_nm TEXT NOT NULL,
                parent_cd TEXT, use_yn TEXT DEFAULT 'Y',
                reg_id TEXT, reg_dt TEXT, mod_id TEXT, mod_dt TEXT,
                PRIMARY KEY (farm_cd, code_cd)
            );
            """
        )
        conn.commit()
        conn.close()
        from core.notification_schema import ensure_notification_schema

        ensure_notification_schema(self.db)

    def tearDown(self) -> None:
        self.db.unlink(missing_ok=True)

    def test_created_at_uses_kst_wall_clock(self) -> None:
        from app.agents.notification_writer import try_create_notification
        from core.notification_schema import NOTI_TYPE_WEATHER_CD

        # UTC 2026-08-16 21:30 → KST 2026-08-17 06:30
        frozen = datetime(2026, 8, 16, 21, 30, 0, tzinfo=ZoneInfo("UTC"))

        class _FrozenDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                if tz is None:
                    return frozen.replace(tzinfo=None)
                return frozen.astimezone(tz)

        with patch("app.core.ops_biz_date.datetime", _FrozenDateTime):
            from app.core.ops_biz_date import now_ops

            self.assertEqual(now_ops().strftime("%Y-%m-%d %H:%M"), "2026-08-17 06:30")
            nid = try_create_notification(
                self.db,
                farm_cd="OR001",
                noti_type_cd=NOTI_TYPE_WEATHER_CD,
                title="kst",
                body="body",
                payload={},
                dedupe_key="WX:OR001:kst_test",
            )
        self.assertIsNotNone(nid)
        conn = sqlite3.connect(str(self.db))
        row = conn.execute(
            "SELECT reg_dt, event_at, noti_id FROM t_notification WHERE noti_id=?",
            (nid,),
        ).fetchone()
        conn.close()
        self.assertIsNotNone(row)
        reg_dt, event_at, noti_id = row
        self.assertTrue(str(reg_dt).startswith("2026-08-17 06:30"), reg_dt)
        self.assertTrue(str(event_at).startswith("2026-08-17 06:30"), event_at)
        self.assertTrue(str(noti_id).startswith("NTF20260817-"), noti_id)

    def test_market_slot_fallback_kst(self) -> None:
        from app.agents.market_agent import _resolve_market_slot

        # UTC 01:00 = KST 10:00 → slot 09
        frozen = datetime(2026, 8, 17, 1, 0, 0, tzinfo=ZoneInfo("UTC"))

        class _FrozenDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                if tz is None:
                    return frozen.replace(tzinfo=None)
                return frozen.astimezone(tz)

        with patch("app.core.ops_biz_date.datetime", _FrozenDateTime):
            self.assertEqual(_resolve_market_slot(None), "09")

        # UTC 08:00 = KST 17:00 → slot 16
        frozen2 = datetime(2026, 8, 17, 8, 0, 0, tzinfo=ZoneInfo("UTC"))

        class _Frozen2(datetime):
            @classmethod
            def now(cls, tz=None):
                if tz is None:
                    return frozen2.replace(tzinfo=None)
                return frozen2.astimezone(tz)

        with patch("app.core.ops_biz_date.datetime", _Frozen2):
            self.assertEqual(_resolve_market_slot(None), "16")


class SettlementPrefetchMidCodeTest(unittest.TestCase):
    def test_default_item_code_is_pear_mid(self) -> None:
        from app.jobs.market_settlement_job import DEFAULT_ITEM_CODE
        from core.market_price_manager import PEAR_MID_ITEM_CODE

        self.assertEqual(DEFAULT_ITEM_CODE, PEAR_MID_ITEM_CODE)
        self.assertEqual(DEFAULT_ITEM_CODE, "06-02")


if __name__ == "__main__":
    unittest.main()
