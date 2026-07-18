# -*- coding: utf-8 -*-
"""영농일지 MVP 서비스·라우터 스모크 테스트."""

from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_SERVER = _REPO / "server"
for p in (_SERVER, _REPO):
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)

from app.core.exceptions import BusinessRuleError  # noqa: E402
from app.schemas.work_log import (  # noqa: E402
    WorkLogMasterUpsertRequest,
    WorkLogWorksUpsertRequest,
    WorkLogWorkUpsertItem,
)
from app.services.work_log_service import WorkLogService  # noqa: E402


def _build_tmp_db() -> Path:
    fd, name = tempfile.mkstemp(suffix=".db")
    import os

    os.close(fd)
    path = Path(name)
    path.unlink(missing_ok=True)
    conn = sqlite3.connect(str(path))
    conn.executescript(
        """
        CREATE TABLE m_farm_info (farm_cd TEXT PRIMARY KEY, farm_nm TEXT);
        INSERT INTO m_farm_info VALUES ('OR001', '테스트농장');

        CREATE TABLE m_common_code (
            farm_cd TEXT, code_cd TEXT, code_nm TEXT, parent_cd TEXT
        );
        INSERT INTO m_common_code VALUES
          ('OR001','WT010100','맑음','WT01'),
          ('OR001','WK010100','전정','WK01'),
          ('OR001','WO010200','진행중','WO01'),
          ('OR001','WO010300','완료','WO01');

        CREATE TABLE m_farm_site (
            site_id TEXT PRIMARY KEY, farm_cd TEXT, site_nm TEXT
        );
        INSERT INTO m_farm_site VALUES ('SITE01','OR001','뒷밭');

        CREATE TABLE t_work_master (
            work_dt TEXT PRIMARY KEY,
            day_of_week TEXT, weather_cd TEXT,
            temp_max REAL, temp_min REAL, precip REAL DEFAULT 0,
            humidity REAL, sun_rise TEXT, sun_set TEXT, sunshine_hr REAL,
            wind_max REAL, wind_min REAL, work_rmk TEXT,
            farm_cd TEXT, reg_id TEXT, reg_dt TEXT, mod_id TEXT, mod_dt TEXT
        );

        CREATE TABLE t_work_detail (
            work_id TEXT PRIMARY KEY,
            work_dt TEXT NOT NULL, farm_cd TEXT NOT NULL,
            work_main_cd TEXT DEFAULT 'WK01', work_mid_cd TEXT,
            work_loc_id TEXT, start_tm TEXT, end_tm TEXT, status_cd TEXT,
            reg_id TEXT, reg_dt TEXT, mod_id TEXT, mod_dt TEXT, rmk TEXT
        );

        CREATE TABLE t_work_resource (
            work_id TEXT, farm_cd TEXT, daily_wage REAL
        );
        CREATE TABLE t_work_expense (
            work_id TEXT, farm_cd TEXT, total_amt REAL
        );
        """
    )
    conn.commit()
    conn.close()
    return path


class WorkLogServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = _build_tmp_db()
        self.svc = WorkLogService(db_path=self.db)
        self.today = date.today().isoformat()

    def tearDown(self) -> None:
        try:
            self.db.unlink(missing_ok=True)
        except OSError:
            pass

    def test_monthly_empty(self):
        res = self.svc.get_monthly("OR001", year=date.today().year, month=date.today().month)
        self.assertTrue(res.success)
        self.assertEqual(res.summary.work_count, 0)

    def test_future_master_blocked(self):
        future = (date.today() + timedelta(days=2)).isoformat()
        with self.assertRaises(BusinessRuleError):
            self.svc.upsert_master(
                "OR001",
                future,
                WorkLogMasterUpsertRequest(work_rmk="x"),
            )

    def test_master_and_works_roundtrip(self):
        body = WorkLogMasterUpsertRequest(
            weather_cd="WT010100",
            temp_min=10,
            temp_max=22,
            work_rmk="우박 주의",
        )
        self.svc.upsert_master("OR001", self.today, body, user_id="T1")
        save = self.svc.upsert_works(
            "OR001",
            self.today,
            WorkLogWorksUpsertRequest(
                works=[
                    WorkLogWorkUpsertItem(
                        work_mid_cd="WK010100",
                        work_loc_id="SITE01",
                        start_tm="09:00",
                        end_tm="12:00",
                        status_cd="WO010200",
                        rmk="가지정리",
                    )
                ]
            ),
            user_id="T1",
        )
        self.assertEqual(len(save.work_ids), 1)
        daily = self.svc.get_daily("OR001", self.today)
        self.assertIsNotNone(daily.master)
        assert daily.master is not None
        self.assertEqual(daily.master.work_rmk, "우박 주의")
        self.assertEqual(len(daily.works), 1)
        self.assertEqual(daily.works[0].work_mid_cd, "WK010100")
        self.assertTrue(daily.works[0].work_id.endswith("-01"))

        month = self.svc.get_monthly(
            "OR001", year=date.today().year, month=date.today().month
        )
        cell = month.days.get(self.today)
        self.assertIsNotNone(cell)
        assert cell is not None
        self.assertTrue(cell.has_issue)
        self.assertTrue(cell.has_work)
        self.assertTrue(cell.has_in_progress)


if __name__ == "__main__":
    unittest.main()
