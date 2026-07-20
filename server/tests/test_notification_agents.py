# -*- coding: utf-8 -*-
"""알림 Agent Phase3 — dedupe·시세 패킷·API 스킵 테스트."""

from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

_SERVER = Path(__file__).resolve().parents[1]
_REPO = _SERVER.parent
for p in (_REPO, _SERVER):
    s = str(p)
    if s in sys.path:
        sys.path.remove(s)
sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(_SERVER))

os.environ["ORCHARD_NOTIFICATION_SCHEDULER"] = "0"

from core.notification_schema import (  # noqa: E402
    NOTI_TYPE_MARKET_CD,
    NOTI_TYPE_WEATHER_CD,
    ensure_notification_schema,
)
from app.agents.market_agent import build_corp_packets, run_market_agent  # noqa: E402
from app.agents.notification_writer import try_create_notification  # noqa: E402
from app.agents.weather_agent import run_weather_agent  # noqa: E402


def _build_tmp_db() -> Path:
    fd, name = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    path = Path(name)
    path.unlink(missing_ok=True)
    conn = sqlite3.connect(str(path))
    conn.executescript(
        """
        CREATE TABLE m_farm_info (
            farm_cd TEXT PRIMARY KEY, farm_nm TEXT,
            lat REAL, lon REAL, nx INTEGER, ny INTEGER
        );
        INSERT INTO m_farm_info VALUES ('OR001', '테스트농장', 37.2, 126.8, 60, 120);

        CREATE TABLE m_common_code (
            farm_cd TEXT, code_cd TEXT, code_nm TEXT NOT NULL,
            parent_cd TEXT, use_yn TEXT DEFAULT 'Y',
            reg_id TEXT, reg_dt TEXT, mod_id TEXT, mod_dt TEXT,
            PRIMARY KEY (farm_cd, code_cd)
        );

        CREATE TABLE t_work_detail (
            work_id TEXT, farm_cd TEXT, work_dt TEXT,
            work_mid_cd TEXT, status_cd TEXT
        );
        INSERT INTO t_work_detail VALUES
          ('W1', 'OR001', date('now','localtime'), 'WK010100', 'WO010100');
        """
    )
    conn.commit()
    conn.close()
    ensure_notification_schema(path)
    return path


class NotificationAgentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = _build_tmp_db()

    def tearDown(self) -> None:
        try:
            self.db.unlink(missing_ok=True)
        except OSError:
            pass

    def test_nt011000_seeded(self) -> None:
        conn = sqlite3.connect(str(self.db))
        row = conn.execute(
            "SELECT code_nm FROM m_common_code WHERE farm_cd='OR001' AND code_cd=?",
            (NOTI_TYPE_MARKET_CD,),
        ).fetchone()
        conn.close()
        self.assertIsNotNone(row)
        self.assertIn("시세", row[0])

    def test_dedupe_key_cooldown(self) -> None:
        kwargs = dict(
            farm_cd="OR001",
            noti_type_cd=NOTI_TYPE_WEATHER_CD,
            title="[서리 경고] 테스트",
            body="body",
            payload={},
            dedupe_key="WX:OR001:20260720:frost",
        )
        first = try_create_notification(self.db, **kwargs)
        second = try_create_notification(self.db, **kwargs)
        self.assertIsNotNone(first)
        self.assertIsNone(second)
        conn = sqlite3.connect(str(self.db))
        cnt = conn.execute(
            "SELECT COUNT(*) FROM t_notification WHERE farm_cd='OR001' AND dedupe_key=?",
            ("WX:OR001:20260720:frost",),
        ).fetchone()[0]
        conn.close()
        self.assertEqual(cnt, 1)

    def test_weather_agent_creates_and_dedupes(self) -> None:
        def fake_wx(_farm):
            return {
                "temp_min": -1.0,
                "temp_max": 34.0,
                "max_pop": 80,
                "max_wind": 12.0,
                "rain_amount": 5.0,
                "humidity": 70,
            }

        r1 = run_weather_agent(self.db, fetch_weather=fake_wx)
        r2 = run_weather_agent(self.db, fetch_weather=fake_wx)
        # daily + frost + rain + heat + wind
        self.assertGreaterEqual(r1["created"], 5)
        self.assertEqual(r2["created"], 0)
        conn = sqlite3.connect(str(self.db))
        types = {
            row[0]
            for row in conn.execute(
                "SELECT DISTINCT noti_type_cd FROM t_notification WHERE farm_cd='OR001'"
            )
        }
        keys = {
            row[0]
            for row in conn.execute(
                "SELECT dedupe_key FROM t_notification WHERE farm_cd='OR001'"
            )
        }
        conn.close()
        self.assertIn(NOTI_TYPE_WEATHER_CD, types)
        self.assertTrue(any(":daily_summary" in k for k in keys))

    def test_weather_daily_summary_includes_rain_amount(self) -> None:
        import json

        def fake_wx(_farm):
            return {
                "temp_min": 12.0,
                "temp_max": 24.0,
                "max_pop": 20,
                "max_wind": 2.0,
                "rain_amount": 4.5,
                "humidity": 55,
            }

        result = run_weather_agent(self.db, fetch_weather=fake_wx)
        self.assertGreaterEqual(result["created"], 1)
        conn = sqlite3.connect(str(self.db))
        row = conn.execute(
            """
            SELECT title, payload_json, dedupe_key FROM t_notification
            WHERE farm_cd='OR001' AND dedupe_key LIKE '%:daily_summary'
            """
        ).fetchone()
        conn.close()
        self.assertIsNotNone(row)
        self.assertIn("영농 기상", row[0])
        payload = json.loads(row[1])
        weather = payload.get("weather") or {}
        self.assertEqual(weather.get("rain_amount"), 4.5)
        self.assertIn("rain_prob", weather)
        self.assertIn("temp_min", weather)
        self.assertIn("temp_max", weather)

    def test_weather_heavy_rain_by_amount(self) -> None:
        def fake_wx(_farm):
            return {
                "temp_min": 18.0,
                "temp_max": 26.0,
                "max_pop": 40,
                "max_wind": 3.0,
                "rain_amount": 35.0,
                "humidity": 80,
            }

        result = run_weather_agent(self.db, fetch_weather=fake_wx)
        self.assertGreaterEqual(result["created"], 2)  # daily + rain
        conn = sqlite3.connect(str(self.db))
        titles = [
            r[0]
            for r in conn.execute(
                "SELECT title FROM t_notification WHERE farm_cd='OR001'"
            )
        ]
        conn.close()
        self.assertTrue(any("방제 연기" in t for t in titles))

    def test_market_corp_packet_structure(self) -> None:
        rows = [
            {
                "variety_name": "신고",
                "spec_name": "15kg",
                "corp_name": "서울청과",
                "quantity": 10,
                "avg_price": 40000,
                "max_price": 45000,
            },
            {
                "variety_name": "신고",
                "spec_name": "7.5kg",
                "corp_name": "한국청과",
                "quantity": 5,
                "avg_price": 22000,
                "max_price": 25000,
            },
            {
                "variety_name": "신고",
                "spec_name": "15kg",
                "corp_name": "동화청과",
                "quantity": 8,
                "avg_price": 41000,
                "max_price": 43000,
            },
            {
                "variety_name": "신고",
                "spec_name": "15kg",
                "corp_name": "중앙청과",
                "quantity": 3,
                "avg_price": 39000,
                "max_price": 42000,
            },
        ]
        prev = [
            {
                "variety_name": "신고",
                "spec_name": "15kg",
                "corp_name": "서울청과",
                "quantity": 4,
                "avg_price": 38000,
                "max_price": 40000,
            }
        ]
        packet = build_corp_packets(rows, prev_rows=prev)
        self.assertEqual(packet["variety"], "신고")
        self.assertEqual(set(packet["specs"]), {"15kg", "7.5kg"})
        by_name = {c["corp_name"]: c for c in packet["corps"]}
        self.assertIn("서울청과", by_name)
        self.assertEqual(by_name["서울청과"]["box_qty"], 10)
        self.assertEqual(by_name["서울청과"]["max_price"], 45000)
        self.assertEqual(by_name["서울청과"]["avg_price"], 40000)
        self.assertEqual(by_name["서울청과"]["qty_change_vs_prev"], 6)
        for key in ("box_qty", "max_price", "avg_price"):
            self.assertIn(key, by_name["한국청과"])

    def test_market_api_failure_skips(self) -> None:
        def boom(_d: str):
            raise RuntimeError("api down")

        result = run_market_agent(self.db, fetch_sale=boom)
        self.assertTrue(result["ok"])
        self.assertEqual(result["created"], 0)
        self.assertGreaterEqual(result["skipped"], 1)

    def test_market_signal_with_inject(self) -> None:
        from datetime import date

        today = date.today().isoformat()

        def fetch2(d: str):
            price = 55000 if d == today else 40000
            return [
                {
                    "variety_name": "신고",
                    "spec_name": "15kg",
                    "corp_name": "서울청과",
                    "quantity": 10,
                    "avg_price": price,
                    "max_price": price + 1000,
                }
            ]

        result = run_market_agent(self.db, fetch_sale=fetch2, trade_date=today)
        self.assertIn("packet", result)
        self.assertTrue(result["packet"]["corps"])
        self.assertGreaterEqual(result["created"], 1)
        conn = sqlite3.connect(str(self.db))
        row = conn.execute(
            "SELECT noti_type_cd, payload_json FROM t_notification WHERE noti_type_cd=?",
            (NOTI_TYPE_MARKET_CD,),
        ).fetchone()
        conn.close()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], NOTI_TYPE_MARKET_CD)
        self.assertNotIn('"route"', row[1] or "")


if __name__ == "__main__":
    unittest.main()
