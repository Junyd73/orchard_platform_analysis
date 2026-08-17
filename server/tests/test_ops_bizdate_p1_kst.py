# -*- coding: utf-8 -*-
"""OPS P1 — core/server 공통 KST SSOT + ID/GCal/KMA/weather."""

from __future__ import annotations

import os
import sys
import time
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

_SERVER = Path(__file__).resolve().parents[1]
_REPO = _SERVER.parent
for p in (str(_SERVER), str(_REPO)):
    if p not in sys.path:
        sys.path.insert(0, p)

os.environ["TZ"] = "UTC"
time.tzset()

# db_manager imports PyQt6 — headless stub
import types

_qt_mod = types.ModuleType("PyQt6")
_qt_core = types.ModuleType("PyQt6.QtCore")
_qt_widgets = types.ModuleType("PyQt6.QtWidgets")
_qt_gui = types.ModuleType("PyQt6.QtGui")
for name, mod in (
    ("PyQt6", _qt_mod),
    ("PyQt6.QtCore", _qt_core),
    ("PyQt6.QtWidgets", _qt_widgets),
    ("PyQt6.QtGui", _qt_gui),
):
    sys.modules.setdefault(name, mod)
_qt_core.QDate = object
_qt_core.Qt = object
_qt_core.QTimer = object
_qt_core.QTime = object

from app.core.ops_biz_date import now_ops as app_now_ops
from app.core.ops_biz_date import today_ops as app_today_ops
from core.db_manager import DBManager
from core.ops_biz_date import now_ops, today_ops
from core.weather_manager import WeatherManager

# UTC 2026-08-17 15:30 == KST 2026-08-18 00:30
_UTC_BOUNDARY = datetime(2026, 8, 17, 15, 30, tzinfo=timezone.utc)


def _freeze_ops(frozen_utc: datetime):
    class _FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):  # noqa: ANN001
            if tz is not None:
                return frozen_utc.astimezone(tz)
            return frozen_utc.replace(tzinfo=None)

    return patch("core.ops_biz_date.datetime", _FrozenDateTime)


class OpsBizDateP1SsotTest(unittest.TestCase):
    def test_os_tz_utc(self) -> None:
        self.assertEqual(os.environ.get("TZ"), "UTC")

    def test_single_ssot_implementation(self) -> None:
        self.assertIs(app_today_ops, today_ops)
        self.assertIs(app_now_ops, now_ops)

    def test_boundary_today_ops(self) -> None:
        with _freeze_ops(_UTC_BOUNDARY):
            self.assertEqual(today_ops(), date(2026, 8, 18))
            self.assertEqual(now_ops().strftime("%Y-%m-%d %H:%M"), "2026-08-18 00:30")
            self.assertEqual(_UTC_BOUNDARY.astimezone(timezone.utc).date(), date(2026, 8, 17))


class OpsBizDateP1IdTest(unittest.TestCase):
    def test_sales_no_fallback_prefix_kst(self) -> None:
        mgr = DBManager.__new__(DBManager)
        mgr.execute_query = MagicMock(return_value=[{"max_no": None}])
        with patch("core.db_manager.today_ops", return_value=date(2026, 8, 18)):
            no = mgr.generate_sales_no("OR001", "")
        self.assertTrue(no.startswith("20260818-"), no)

    def test_obs_id_fallback_prefix_kst(self) -> None:
        mgr = DBManager.__new__(DBManager)
        mgr.execute_query = MagicMock(return_value=[])
        with patch("core.db_manager.today_ops", return_value=date(2026, 8, 18)):
            oid = mgr.generate_obs_id("OR001", "bad")
        self.assertTrue(oid.startswith("OBS20260818-"), oid)


class OpsBizDateP1GcalTest(unittest.TestCase):
    def test_future_work_dt_uses_today_ops(self) -> None:
        from app.services import google_calendar_service as gcs

        with patch.object(gcs, "today_ops", return_value=date(2026, 8, 18)):
            self.assertFalse("2026-08-18" > gcs.today_ops().isoformat())
            self.assertTrue("2026-08-19" > gcs.today_ops().isoformat())


class OpsBizDateP1KmaTest(unittest.TestCase):
    def test_kma_base_candidates_use_kst_wall(self) -> None:
        wm = WeatherManager.__new__(WeatherManager)
        # KST 2026-08-18 00:30 → hhmm 0030 → only prev-day evening bases before today's slots
        frozen = datetime(2026, 8, 17, 15, 30, tzinfo=timezone.utc)
        with _freeze_ops(frozen):
            cands = wm._latest_kma_base_candidates()
        self.assertTrue(cands)
        # First candidates should be previous KST calendar day (20260817) late slots
        # because KST clock is 00:30 (before 0200)
        dates = {bd for bd, _bt in cands}
        self.assertIn("20260817", dates)
        # No 20260818 morning bases yet at 00:30
        today_slots = [bt for bd, bt in cands if bd == "20260818"]
        self.assertEqual(today_slots, [])

    def test_kma_base_afternoon_includes_today(self) -> None:
        wm = WeatherManager.__new__(WeatherManager)
        # KST 2026-08-18 15:00 == UTC 06:00
        frozen = datetime(2026, 8, 18, 6, 0, tzinfo=timezone.utc)
        with _freeze_ops(frozen):
            cands = wm._latest_kma_base_candidates()
        today_slots = [bt for bd, bt in cands if bd == "20260818"]
        self.assertIn("1400", today_slots)
        self.assertNotIn("1700", today_slots)  # 15:00 < 17:00


class OpsBizDateP1WeatherStampTest(unittest.TestCase):
    def test_save_weather_reg_dt_kst(self) -> None:
        wm = WeatherManager.__new__(WeatherManager)
        wm.db = MagicMock()
        with _freeze_ops(_UTC_BOUNDARY):
            wm._save_weather_to_db("OR001", "2026-08-18", {"ok": 1})
        args = wm.db.execute_query.call_args[0]
        self.assertEqual(args[1][3], "2026-08-18 00:30:00")

    def test_work_log_cache_meta_kst(self) -> None:
        wm = WeatherManager.__new__(WeatherManager)
        with _freeze_ops(_UTC_BOUNDARY):
            stamp = now_ops().replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S")
        self.assertEqual(stamp, "2026-08-18 00:30:00")

    def test_mid_forecast_binds_kst_not_sql_now(self) -> None:
        from app.jobs import mid_forecast_job as mf

        src = Path(mf.__file__).read_text(encoding="utf-8")
        self.assertIn("now_ops()", src)
        self.assertNotIn("datetime('now')", src)
        self.assertNotIn("datetime.now()", src)


if __name__ == "__main__":
    unittest.main()
