# -*- coding: utf-8 -*-
"""스케줄러 CronTrigger Asia/Seoul — OS UTC에서도 KST wall hour."""

from __future__ import annotations

import os
import time
import unittest
from zoneinfo import ZoneInfo


class SchedulerTimezoneKstTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ["TZ"] = "UTC"
        time.tzset()
        os.environ["ORCHARD_NOTIFICATION_SCHEDULER"] = "1"
        os.environ["ORCHARD_PREFETCH_SCHEDULER"] = "1"

    def test_cron_triggers_use_asia_seoul(self) -> None:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger

        from app.core.ops_biz_date import OPS_TZ_NAME
        from app.scheduler import (
            PREFETCH_MARKET_HOUR,
            PREFETCH_MARKET_MINUTE,
            PREFETCH_MID_DOW,
            PREFETCH_MID_HOUR,
            PREFETCH_MID_MINUTE,
            PREFETCH_PSIS_DOW,
            PREFETCH_PSIS_HOUR,
            PREFETCH_PSIS_MINUTE,
            PREFETCH_SMART_SPRAY_HOUR,
            PREFETCH_SMART_SPRAY_MINUTE,
            PREFETCH_WEATHER_HOUR,
            PREFETCH_WEATHER_MINUTE,
            PEST_COLD_DOW,
            PEST_COLD_MONTHS,
            PEST_HOUR,
            PEST_WARM_DOW,
            PEST_WARM_MONTHS,
        )

        self.assertEqual(OPS_TZ_NAME, "Asia/Seoul")

        # production registration pattern (timezone explicit on every CronTrigger)
        specs = [
            ("noti_weather", CronTrigger(timezone=OPS_TZ_NAME, hour="6,12,18", minute=0), {6, 12, 18}),
            ("noti_market_09", CronTrigger(timezone=OPS_TZ_NAME, hour=9, minute=0), {9}),
            ("noti_market_16", CronTrigger(timezone=OPS_TZ_NAME, hour=16, minute=0), {16}),
            ("noti_internal", CronTrigger(timezone=OPS_TZ_NAME, hour=20, minute=0), {20}),
            (
                "noti_pest_warm",
                CronTrigger(
                    timezone=OPS_TZ_NAME,
                    month=PEST_WARM_MONTHS,
                    day_of_week=PEST_WARM_DOW,
                    hour=PEST_HOUR,
                    minute=0,
                ),
                {PEST_HOUR},
            ),
            (
                "noti_pest_cold",
                CronTrigger(
                    timezone=OPS_TZ_NAME,
                    month=PEST_COLD_MONTHS,
                    day_of_week=PEST_COLD_DOW,
                    hour=PEST_HOUR,
                    minute=0,
                ),
                {PEST_HOUR},
            ),
            (
                "prefetch_weather_month",
                CronTrigger(
                    timezone=OPS_TZ_NAME,
                    hour=PREFETCH_WEATHER_HOUR,
                    minute=PREFETCH_WEATHER_MINUTE,
                ),
                {PREFETCH_WEATHER_HOUR},
            ),
            (
                "prefetch_market_settlement",
                CronTrigger(
                    timezone=OPS_TZ_NAME,
                    day_of_week="mon-fri",
                    hour=PREFETCH_MARKET_HOUR,
                    minute=PREFETCH_MARKET_MINUTE,
                ),
                {PREFETCH_MARKET_HOUR},
            ),
            (
                "prefetch_mid_forecast",
                CronTrigger(
                    timezone=OPS_TZ_NAME,
                    day_of_week=PREFETCH_MID_DOW,
                    hour=PREFETCH_MID_HOUR,
                    minute=PREFETCH_MID_MINUTE,
                ),
                {PREFETCH_MID_HOUR},
            ),
            (
                "prefetch_psis_cache",
                CronTrigger(
                    timezone=OPS_TZ_NAME,
                    day_of_week=PREFETCH_PSIS_DOW,
                    hour=PREFETCH_PSIS_HOUR,
                    minute=PREFETCH_PSIS_MINUTE,
                ),
                {PREFETCH_PSIS_HOUR},
            ),
            (
                "prefetch_smart_spray",
                CronTrigger(
                    timezone=OPS_TZ_NAME,
                    hour=PREFETCH_SMART_SPRAY_HOUR,
                    minute=PREFETCH_SMART_SPRAY_MINUTE,
                ),
                {PREFETCH_SMART_SPRAY_HOUR},
            ),
        ]

        sched = BackgroundScheduler(timezone=OPS_TZ_NAME)
        for jid, trig, _hours in specs:
            self.assertEqual(str(trig.timezone), "Asia/Seoul", msg=jid)
            sched.add_job(lambda: None, trig, id=jid, replace_existing=True)

        sched.start()
        try:
            kst = ZoneInfo("Asia/Seoul")
            utc = ZoneInfo("UTC")
            for jid, _trig, expected_hours in specs:
                job = sched.get_job(jid)
                self.assertIsNotNone(job)
                self.assertEqual(str(job.trigger.timezone), "Asia/Seoul", msg=jid)
                nrt = job.next_run_time
                self.assertIsNotNone(nrt, msg=jid)
                assert nrt is not None
                kst_dt = nrt.astimezone(kst)
                utc_dt = nrt.astimezone(utc)
                self.assertIn(kst_dt.hour, expected_hours, msg=f"{jid} KST={kst_dt}")
                # UTC/KST 변환 일치 (같은 절대 시각)
                self.assertEqual(kst_dt.astimezone(utc), utc_dt)
                # 구버그: timezone 미지정 시 UTC wall == intended hour → KST는 +9
                if jid == "noti_weather":
                    self.assertNotEqual(
                        utc_dt.hour,
                        6,
                        msg="weather must not fire at UTC 06 (= KST 15)",
                    )
                    self.assertIn(kst_dt.hour, (6, 12, 18))
                if jid == "noti_market_09":
                    self.assertEqual(kst_dt.hour, 9)
                    self.assertEqual(utc_dt.hour, 0)  # KST 09 = UTC 00
                if jid == "noti_market_16":
                    self.assertEqual(kst_dt.hour, 16)
                    self.assertEqual(utc_dt.hour, 7)  # KST 16 = UTC 07
        finally:
            sched.shutdown(wait=False)

    def test_scheduler_module_registers_tz_on_all_jobs(self) -> None:
        """start_notification_scheduler 실제 등록 job의 trigger timezone."""
        import tempfile
        from pathlib import Path

        from app.scheduler import (
            get_notification_scheduler,
            start_notification_scheduler,
            stop_notification_scheduler,
        )

        stop_notification_scheduler()
        fd, name = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        path = Path(name)
        path.unlink(missing_ok=True)
        try:
            sched = start_notification_scheduler(path)
            self.assertIsNotNone(sched)
            assert sched is not None
            self.assertEqual(str(sched.timezone), "Asia/Seoul")
            jobs = sched.get_jobs()
            self.assertGreaterEqual(len(jobs), 6)
            for job in jobs:
                self.assertEqual(
                    str(job.trigger.timezone),
                    "Asia/Seoul",
                    msg=job.id,
                )
            self.assertIs(get_notification_scheduler(), sched)
        finally:
            stop_notification_scheduler()
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
