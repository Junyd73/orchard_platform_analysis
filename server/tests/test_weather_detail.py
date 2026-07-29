# -*- coding: utf-8 -*-
"""날씨 상세 조립 단위 테스트 — 외부 API 호출 없음."""

from __future__ import annotations

import sys
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

_REPO = Path(__file__).resolve().parents[2]
_SERVER = _REPO / "server"
for p in (_REPO, _SERVER):
    s = str(p)
    if s in sys.path:
        sys.path.remove(s)
    sys.path.insert(0, s)

from core.weather_manager import (  # noqa: E402
    MOBILE_DETAIL_SUN_MARKER_SUNRISE,
    MOBILE_DETAIL_SUN_MARKER_SUNSET,
    WeatherManager,
)


def _slot(ds: str, tm: str, **kwargs):
    base = {
        "date": ds,
        "time": tm,
        "pop": 10,
        "pcp": 0.0,
        "wsd": 2.0,
        "tmp": 25.0,
        "reh": 60,
        "sky": 1,
        "pty": 0,
    }
    base.update(kwargs)
    return base


class MobileWeatherDetailUnitTest(unittest.TestCase):
    def setUp(self) -> None:
        self.wm = WeatherManager(db_manager=None)
        self.today = date.today().isoformat()
        self.tomorrow = (date.today() + timedelta(days=1)).isoformat()

    def test_filter_hourly_includes_current_hour(self):
        now = datetime.now().replace(minute=10, second=0, microsecond=0)
        hh = now.strftime("%H%M")
        next_h = (now + timedelta(hours=1)).strftime("%H%M")
        next_d = (now + timedelta(hours=1)).strftime("%Y-%m-%d")
        slots = [
            _slot(self.today, hh, tmp=20),
            _slot(next_d, next_h, tmp=21),
            _slot(self.today, "0000", tmp=5),
        ]
        out = self.wm._filter_hourly_slots(slots, now=now, hours=24)
        times = {(s["date"], s["time"]) for s in out}
        self.assertIn((self.today, hh), times)
        self.assertNotIn((self.today, "0000"), times)

    def test_hourly_timeline_inserts_sun_markers(self):
        slots = [_slot(self.today, "0600", tmp=18), _slot(self.today, "1800", tmp=26)]
        sun = [
            {"at": f"{self.today}T05:42:00", "kind": MOBILE_DETAIL_SUN_MARKER_SUNRISE},
            {"at": f"{self.today}T19:30:00", "kind": MOBILE_DETAIL_SUN_MARKER_SUNSET},
        ]
        rows = self.wm._build_hourly_timeline(slots, sun)
        kinds = [r["kind"] for r in rows]
        self.assertEqual(kinds.count("sun"), 2)
        self.assertEqual(kinds.count("hour"), 2)
        self.assertEqual(rows[0]["marker"], MOBILE_DETAIL_SUN_MARKER_SUNRISE)
        self.assertEqual(rows[-1]["marker"], MOBILE_DETAIL_SUN_MARKER_SUNSET)

    def test_build_weekly_am_pm_prefers_short_then_mid(self):
        slots = [
            _slot(self.today, "0900", pop=20, pcp=0.0, wsd=1.5, tmp=22),
            _slot(self.today, "1500", pop=40, pcp=1.0, wsd=3.0, tmp=28),
        ]
        mid_day = (date.today() + timedelta(days=5)).isoformat()
        mid_raw = {
            "ok": True,
            "land": {f"rnSt5Am": 30, f"rnSt5Pm": 70},
            "ta": {f"taMin5": 18.0, f"taMax5": 29.0},
        }
        # summarize uses n in 4..10 relative to today — day index 5 → rnSt5*
        with patch.object(self.wm, "get_mid_forecast", return_value=mid_raw):
            weekly = self.wm.build_weekly_am_pm(
                nx=60,
                ny=120,
                lat=37.0,
                lon=127.0,
                start_date=self.today,
                days=7,
                slots=slots,
            )
        self.assertEqual(len(weekly), 7)
        today_row = weekly[0]
        self.assertEqual(today_row["source"], "short")
        self.assertEqual(today_row["am"]["precip_prob_pct"], 20)
        self.assertEqual(today_row["pm"]["precip_prob_pct"], 40)
        mid_row = next(r for r in weekly if r["date"] == mid_day)
        self.assertEqual(mid_row["source"], "mid")
        self.assertEqual(mid_row["am"]["precip_prob_pct"], 30)
        self.assertEqual(mid_row["pm"]["precip_prob_pct"], 70)
        self.assertEqual(mid_row["icon"], "rain")

    def test_build_mobile_weather_detail_shape(self):
        daily = {
            "temp_min": 20.0,
            "temp_max": 30.0,
            "humidity": 55.0,
            "wind_max": 3.2,
            "precip": 0.0,
            "weather_cd": "WT010100",
            "sun_rise": "05:40",
            "sun_set": "19:45",
        }
        slots = [
            _slot(self.today, datetime.now().strftime("%H00"), tmp=27, pop=15, reh=50),
            _slot(self.tomorrow, "0900", pop=25, tmp=24),
            _slot(self.tomorrow, "1500", pop=35, tmp=29),
        ]
        with (
            patch.object(self.wm, "get_weather", return_value=daily),
            patch.object(self.wm, "get_short_forecast_slots", return_value=slots),
            patch.object(self.wm, "get_mid_forecast", return_value={"ok": False}),
        ):
            payload = self.wm.build_mobile_weather_detail(
                nx=60,
                ny=120,
                lat=37.2,
                lon=127.1,
                target_date=self.today,
                location_label="테스트농장",
            )
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["location"], "테스트농장")
        self.assertEqual(payload["current"]["weather_cd"], "WT010100")
        self.assertIsInstance(payload["hourly"], list)
        self.assertEqual(len(payload["weekly"]), 7)
        self.assertIn("updated_at", payload)


if __name__ == "__main__":
    unittest.main()
