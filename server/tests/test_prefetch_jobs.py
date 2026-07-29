# -*- coding: utf-8 -*-
"""SCH-001 Prefetch Job 단위 테스트 (외부 API 미호출)."""

from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path


def _build_tmp_db() -> Path:
    fd, name = tempfile.mkstemp(suffix=".db")
    import os

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
        INSERT INTO m_farm_info VALUES
          ('OR001', '테스트', 37.2, 126.8, 60, 120);

        CREATE TABLE t_weather_cache (
            farm_cd TEXT,
            weather_dt TEXT,
            weather_json TEXT,
            reg_dt TEXT,
            PRIMARY KEY (farm_cd, weather_dt)
        );
        """
    )
    conn.commit()
    conn.close()
    return path


class PrefetchWeatherMonthTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db = _build_tmp_db()

    def tearDown(self) -> None:
        self.db.unlink(missing_ok=True)

    def test_skips_cache_and_counts_api(self) -> None:
        from app.jobs.weather_month_job import run_weather_month_prefetch

        calls: list[str] = []

        def fake_fetch(farm, work_dt: str):
            calls.append(work_dt)
            if work_dt.endswith("01"):
                return {"ok": True, "source": "API", "data": {"weather_cd": "WT010100"}}
            return {"ok": True, "source": "캐시", "data": {"weather_cd": "WT010100"}}

        today = date(2026, 7, 25)
        result = run_weather_month_prefetch(
            self.db, today=today, fetch_day=fake_fetch
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["farms"], 1)
        self.assertGreater(result["fetched"], 0)
        self.assertGreater(result["skipped"], 0)
        self.assertEqual(len(calls), result["fetched"] + result["skipped"])


class PrefetchMarketSettlementTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db = _build_tmp_db()

    def tearDown(self) -> None:
        self.db.unlink(missing_ok=True)

    def test_fetches_only_missing_summary_dates(self) -> None:
        from app.jobs.market_settlement_job import (
            MAX_SALE_FETCH_PER_RUN,
            run_market_settlement_prefetch,
        )

        fetched_dates: list[str] = []

        def fake_sale(dt: str, mk: str, it: str):
            fetched_dates.append(dt)
            return [
                {
                    "__source": "sale",
                    "trade_date": dt,
                    "product_name": "배",
                    "variety": "신고",
                    "market": "가락",
                    "corporation": "테스트법인",
                    "grade": "특",
                    "size": "15과",
                    "spec": "15kg",
                    "price": 40000,
                    "quantity": 10,
                }
            ]

        today = date(2026, 7, 25)
        result = run_market_settlement_prefetch(
            self.db, today=today, sale_fetcher=fake_sale
        )
        self.assertTrue(result["ok"])
        self.assertLessEqual(len(fetched_dates), MAX_SALE_FETCH_PER_RUN)
        self.assertGreater(result["imported"], 0)
        self.assertGreater(result["summary_built"], 0)


class PrefetchMidForecastTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db = _build_tmp_db()

    def tearDown(self) -> None:
        self.db.unlink(missing_ok=True)

    def test_stores_mid_sentinel(self) -> None:
        from app.jobs.mid_forecast_job import (
            MID_FORECAST_CACHE_DT,
            run_mid_forecast_prefetch,
        )

        result = run_mid_forecast_prefetch(
            self.db, fetch_mid=lambda lat, lon: {"wf3Am": "맑음", "regId": "11B00000"}
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["fetched"], 1)
        conn = sqlite3.connect(str(self.db))
        row = conn.execute(
            "SELECT weather_json FROM t_weather_cache WHERE weather_dt=?",
            (MID_FORECAST_CACHE_DT,),
        ).fetchone()
        conn.close()
        self.assertIsNotNone(row)
        payload = json.loads(row[0])
        self.assertEqual(payload.get("kind"), "mid")


class PrefetchPsisTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db = _build_tmp_db()

    def tearDown(self) -> None:
        self.db.unlink(missing_ok=True)

    def test_skips_when_no_crops(self) -> None:
        from app.jobs.psis_cache_job import run_psis_cache_prefetch

        def sync(_db, farm_cd: str):
            raise ValueError("활성 작물 없음")

        result = run_psis_cache_prefetch(self.db, sync_farm=sync)
        self.assertTrue(result["ok"])
        self.assertEqual(result["skipped"], 1)
        self.assertEqual(result["fetched"], 0)


class SchedulerPrefetchRegistrationTest(unittest.TestCase):
    def test_prefetch_job_constants(self) -> None:
        from app.scheduler import (
            PREFETCH_MARKET_HOUR,
            PREFETCH_MID_DOW,
            PREFETCH_PSIS_DOW,
            PREFETCH_WEATHER_HOUR,
            PREFETCH_WEATHER_MINUTE,
        )

        self.assertEqual(PREFETCH_WEATHER_HOUR, 5)
        self.assertEqual(PREFETCH_WEATHER_MINUTE, 30)
        self.assertEqual(PREFETCH_MARKET_HOUR, 18)
        self.assertEqual(PREFETCH_MID_DOW, "mon,wed,fri")
        self.assertEqual(PREFETCH_PSIS_DOW, "sun")


if __name__ == "__main__":
    unittest.main()
