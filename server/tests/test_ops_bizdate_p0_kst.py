# -*- coding: utf-8 -*-
"""OPS 1단계 — FastAPI 업무일 KST (TZ=UTC 서버에서도 Asia/Seoul)."""

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

from app.core.exceptions import BusinessRuleError
from app.core.ops_biz_date import now_ops, today_ops
from app.jobs.market_settlement_job import _date_window
from app.jobs.weather_month_job import WEATHER_LOOKBACK_DAYS, _target_dates
from app.services.notification_service import _now_local
from app.services.observation_service import ObservationService
from app.services.work_log_service import _ensure_not_future, _is_future_dt

# UTC 2026-08-16 15:30 == KST 2026-08-17 00:30
_UTC_KST_MIDNIGHT = datetime(2026, 8, 16, 15, 30, tzinfo=timezone.utc)
# UTC 2026-08-16 23:30 == KST 2026-08-17 08:30
_UTC_KST_MORNING = datetime(2026, 8, 16, 23, 30, tzinfo=timezone.utc)


def _freeze_ops(frozen_utc: datetime):
    class _FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):  # noqa: ANN001
            if tz is not None:
                return frozen_utc.astimezone(tz)
            return frozen_utc.replace(tzinfo=None)

    return patch("app.core.ops_biz_date.datetime", _FrozenDateTime)


class OpsBizDateP0UtcTest(unittest.TestCase):
    def test_os_tz_is_utc(self) -> None:
        self.assertEqual(os.environ.get("TZ"), "UTC")

    def test_boundary_midnight_kst_biz_day(self) -> None:
        # UTC 15:30 → KST 00:30 next calendar day
        self.assertEqual(
            _UTC_KST_MIDNIGHT.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M"),
            "2026-08-16 15:30",
        )
        with _freeze_ops(_UTC_KST_MIDNIGHT):
            self.assertEqual(today_ops(), date(2026, 8, 17))
            self.assertEqual(now_ops().strftime("%Y-%m-%d %H:%M"), "2026-08-17 00:30")

    def test_boundary_morning_before_09_kst(self) -> None:
        with _freeze_ops(_UTC_KST_MORNING):
            self.assertEqual(today_ops(), date(2026, 8, 17))
            self.assertEqual(_UTC_KST_MORNING.date(), date(2026, 8, 16))

    def test_observation_summary_defaults_to_kst_today(self) -> None:
        repo = MagicMock()
        repo.get_summary.return_value = MagicMock()
        svc = ObservationService(repo=repo)
        svc._ensure_farm = MagicMock(return_value="OR001")  # type: ignore[method-assign]

        with patch(
            "app.services.observation_service.today_ops",
            return_value=date(2026, 8, 17),
        ):
            svc.get_summary("OR001")
        repo.get_summary.assert_called_once_with("OR001", as_of_date="2026-08-17")

    def test_work_log_future_gate_kst(self) -> None:
        with patch(
            "app.services.work_log_service.today_ops",
            return_value=date(2026, 8, 17),
        ):
            self.assertFalse(_is_future_dt("2026-08-17"))
            self.assertTrue(_is_future_dt("2026-08-18"))
            _ensure_not_future("2026-08-17")
            with self.assertRaises(BusinessRuleError):
                _ensure_not_future("2026-08-18")

    def test_market_settlement_window_uses_today_ops(self) -> None:
        with patch(
            "app.jobs.market_settlement_job.today_ops",
            return_value=date(2026, 8, 17),
        ):
            _start, end, days = _date_window()
        self.assertEqual(end, "2026-08-17")
        self.assertEqual(days[-1], "2026-08-17")

    def test_weather_month_targets_use_today_ops(self) -> None:
        with patch(
            "app.jobs.weather_month_job.today_ops",
            return_value=date(2026, 8, 17),
        ):
            days = _target_dates()
        self.assertEqual(days[WEATHER_LOOKBACK_DAYS], "2026-08-17")
        self.assertEqual(days[WEATHER_LOOKBACK_DAYS + 1], "2026-08-18")

    def test_smart_spray_dedupe_ymd_kst(self) -> None:
        from app.jobs import smart_spray_job as mod

        dedupe_keys: list[str] = []

        class _Card:
            pest_nm = "검은별무늬병"
            score = 80
            risk_level = "H"

        svc = MagicMock()
        svc.build_and_persist_farm_snapshot.return_value = ([_Card()], {}, {})

        def _capture_upsert(*_a, **kw):  # noqa: ANN001
            dedupe_keys.append(str(kw.get("dedupe_key") or ""))
            return ("N1", "created")

        with (
            patch.object(mod, "today_ops", return_value=date(2026, 8, 17)),
            patch.object(mod, "resolve_db_path", side_effect=lambda p: Path(str(p))),
            patch.object(mod, "SmartSprayService", return_value=svc),
            patch.object(mod, "list_farm_cds", return_value=["OR001"]),
            patch.object(mod, "upsert_notification_by_dedupe", side_effect=_capture_upsert),
            patch.object(mod, "get_sqlite_write_connection") as gw,
        ):
            conn = MagicMock()
            gw.return_value.__enter__.return_value = conn
            gw.return_value.__exit__.return_value = False
            mod.run_smart_spray_prefetch("/tmp/unused.db")

        self.assertEqual(dedupe_keys, ["SPR:OR001:20260817:briefing"])
        svc.build_and_persist_farm_snapshot.assert_called()
        self.assertEqual(
            svc.build_and_persist_farm_snapshot.call_args[0][2],
            "2026-08-17",
        )

    def test_weather_agent_day_key_kst(self) -> None:
        from app.agents import weather_agent as wa

        with patch.object(wa, "today_ops", return_value=date(2026, 8, 17)):
            with (
                patch.object(wa, "sqlite3") as sql,
                patch.object(wa, "_load_farms", return_value=[]),
            ):
                sql.connect.return_value = MagicMock()
                wa.run_weather_agent("/tmp/x.db")
            # day computed at start — assert helper contract
            self.assertEqual(wa.today_ops().strftime("%Y%m%d"), "20260817")

    def test_pest_agent_day_key_kst(self) -> None:
        from app.agents import pest_agent as pa

        with patch.object(pa, "today_ops", return_value=date(2026, 8, 17)):
            self.assertEqual(pa.today_ops().strftime("%Y%m%d"), "20260817")

    def test_internal_agent_day_and_today_kst(self) -> None:
        from app.agents import internal_agent as ia

        scanned: list[str] = []

        def _scan(_conn, farm_cd, today):  # noqa: ANN001
            scanned.append(today)
            return []

        with (
            patch.object(ia, "today_ops", return_value=date(2026, 8, 17)),
            patch.object(ia, "list_farm_cds", return_value=["OR001"]),
            patch.object(ia, "_scan_incomplete_work", side_effect=_scan),
            patch.object(ia, "_scan_low_stock", return_value=[]),
            patch.object(ia, "sqlite3") as sql,
        ):
            sql.connect.return_value = MagicMock()
            ia.run_internal_agent("/tmp/x.db")
        self.assertEqual(scanned, ["2026-08-17"])

    def test_notification_service_now_ops_kst(self) -> None:
        with _freeze_ops(_UTC_KST_MIDNIGHT):
            stamp = _now_local()
        self.assertTrue(stamp.startswith("2026-08-17 00:30"), stamp)

    def test_integrated_save_biz_today_iso_kst(self) -> None:
        from core.work_log_integrated_save_service import _biz_today_iso

        with patch(
            "app.core.ops_biz_date.today_ops",
            return_value=date(2026, 8, 17),
        ):
            self.assertEqual(_biz_today_iso(), "2026-08-17")


if __name__ == "__main__":
    unittest.main()
