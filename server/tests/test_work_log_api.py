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
        CREATE TABLE m_farm_info (
            farm_cd TEXT PRIMARY KEY, farm_nm TEXT,
            lat REAL, lon REAL, nx INTEGER, ny INTEGER
        );
        INSERT INTO m_farm_info VALUES ('OR001', '테스트농장', NULL, NULL, NULL, NULL);

        CREATE TABLE m_common_code (
            farm_cd TEXT, code_cd TEXT, code_nm TEXT, parent_cd TEXT
        );
        INSERT INTO m_common_code VALUES
          ('OR001','WT010100','맑음','WT01'),
          ('OR001','WK010100','전정','WK01'),
          ('OR001','WO010100','준비중','WO01'),
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
            res_id INTEGER PRIMARY KEY,
            work_id TEXT, farm_cd TEXT, emp_cd TEXT,
            daily_wage REAL, man_hour REAL DEFAULT 0,
            pay_method_cd TEXT, pay_status TEXT, slip_no TEXT
        );
        CREATE TABLE m_partner (
            pt_id TEXT, farm_cd TEXT, worker_type_cd TEXT, pt_nm TEXT
        );
        CREATE TABLE t_work_expense (
            exp_id INTEGER PRIMARY KEY,
            work_id TEXT, farm_cd TEXT, total_amt REAL,
            acct_cd TEXT, item_nm TEXT, pay_method_cd TEXT,
            pay_status TEXT, trans_dt TEXT, slip_no TEXT
        );
        CREATE TABLE m_account_code (
            acct_cd TEXT PRIMARY KEY, acct_nm TEXT
        );
        CREATE TABLE t_pesticide_use (
            use_id INTEGER PRIMARY KEY,
            farm_cd TEXT, work_id TEXT, stock_applied_yn TEXT,
            use_yn TEXT, cancel_yn TEXT
        );
        CREATE TABLE t_pesticide_use_line (
            use_id INTEGER, line_no INTEGER
        );
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


def _insert_work_with_resources(
    db: Path,
    *,
    work_dt: str,
    work_id: str,
    work_mid_cd: str = "WK010100",
    resources: list[tuple[str, float, float]],
) -> None:
    """resources: (emp_cd, man_hour, daily_wage)"""
    conn = sqlite3.connect(str(db))
    conn.execute(
        """
        INSERT OR IGNORE INTO t_work_master (
            work_dt, farm_cd, weather_cd, work_rmk
        ) VALUES (?, 'OR001', 'WT010100', '')
        """,
        (work_dt,),
    )
    conn.execute(
        """
        INSERT INTO t_work_detail (
            work_id, work_dt, farm_cd, work_main_cd, work_mid_cd, status_cd
        ) VALUES (?, ?, 'OR001', 'WK01', ?, 'WO010300')
        """,
        (work_id, work_dt, work_mid_cd),
    )
    for emp_cd, man_hour, wage in resources:
        conn.execute(
            """
            INSERT INTO t_work_resource (
                work_id, farm_cd, emp_cd, man_hour, daily_wage
            ) VALUES (?, 'OR001', ?, ?, ?)
            """,
            (work_id, emp_cd, man_hour, wage),
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO m_partner (pt_id, farm_cd, worker_type_cd)
            VALUES (?, 'OR001', 'EMP')
            """,
            (emp_cd,),
        )
    conn.commit()
    conn.close()


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

    def test_monthly_unique_people_and_hours(self):
        """동일인 다작업=1명, man_hour 합산."""
        dt = self.today
        y, m, _ = (int(x) for x in dt.split("-"))
        _insert_work_with_resources(
            self.db,
            work_dt=dt,
            work_id=f"{dt.replace('-', '')}-01",
            resources=[("E1", 4.0, 50000), ("E2", 3.0, 40000)],
        )
        _insert_work_with_resources(
            self.db,
            work_dt=dt,
            work_id=f"{dt.replace('-', '')}-02",
            work_mid_cd="WK010200",
            resources=[("E1", 3.0, 30000)],
        )
        month = self.svc.get_monthly("OR001", year=y, month=m)
        cell = month.days.get(dt)
        self.assertIsNotNone(cell)
        assert cell is not None
        self.assertEqual(cell.resource_count, 2)  # E1, E2
        self.assertEqual(cell.labor_hour_sum, 10.0)  # 4+3+3
        self.assertEqual(month.summary.resource_count, 2)
        self.assertEqual(month.summary.labor_hour_sum, 10.0)
        self.assertEqual(month.summary.pesticide_count, 1)

    def test_monthly_includes_adjacent_grid_days(self):
        """6월 뷰 하단 7/1~ 패딩 일자도 days에 포함 (요약은 6월만)."""
        conn = sqlite3.connect(str(self.db))
        conn.execute(
            """
            INSERT INTO t_work_detail (
                work_id, work_dt, farm_cd, work_main_cd, work_mid_cd, status_cd
            ) VALUES
              ('20260615-01', '2026-06-15', 'OR001', 'WK01', 'WK010100', 'WO010300'),
              ('20260701-01', '2026-07-01', 'OR001', 'WK01', 'WK010100', 'WO010100'),
              ('20260702-01', '2026-07-02', 'OR001', 'WK01', 'WK010100', 'WO010100')
            """
        )
        conn.commit()
        conn.close()
        month = self.svc.get_monthly("OR001", year=2026, month=6)
        self.assertIn("2026-06-15", month.days)
        self.assertIn("2026-07-01", month.days)
        self.assertIn("2026-07-02", month.days)
        self.assertEqual(month.summary.work_count, 1)
        self.assertEqual(month.summary.work_day_count, 1)

    def test_monthly_weather_from_cache_without_master(self):
        """영농일지 없어도 t_weather_cache면 월간 셀에 기상 표시."""
        dt = "2026-07-02"
        conn = sqlite3.connect(str(self.db))
        conn.execute(
            """
            INSERT INTO t_weather_cache (farm_cd, weather_dt, weather_json, reg_dt)
            VALUES (
              'OR001', ?,
              '{"weather_cd":"WT010100","weather_nm":"맑음","temp_min":12,"temp_max":28}',
              '2026-07-02 09:00:00'
            )
            """,
            (dt,),
        )
        conn.commit()
        conn.close()
        month = self.svc.get_monthly("OR001", year=2026, month=7)
        cell = month.days.get(dt)
        self.assertIsNotNone(cell)
        assert cell is not None
        self.assertEqual(cell.weather_cd, "WT010100")
        self.assertEqual(cell.weather_nm, "맑음")
        self.assertFalse(cell.has_work)
        self.assertEqual(month.summary.work_count, 0)

    def test_monthly_master_weather_not_overwritten_by_cache(self):
        """t_work_master 기상이 있으면 캐시로 덮어쓰지 않음."""
        dt = "2026-07-03"
        conn = sqlite3.connect(str(self.db))
        conn.execute(
            """
            INSERT INTO t_work_master (work_dt, farm_cd, weather_cd, work_rmk)
            VALUES (?, 'OR001', 'WT010100', '')
            """,
            (dt,),
        )
        conn.execute(
            """
            INSERT INTO t_weather_cache (farm_cd, weather_dt, weather_json, reg_dt)
            VALUES (
              'OR001', ?,
              '{"weather_cd":"WT010200","weather_nm":"흐림"}',
              '2026-07-03 09:00:00'
            )
            """,
            (dt,),
        )
        conn.commit()
        conn.close()
        month = self.svc.get_monthly("OR001", year=2026, month=7)
        cell = month.days.get(dt)
        self.assertIsNotNone(cell)
        assert cell is not None
        self.assertEqual(cell.weather_cd, "WT010100")
        self.assertEqual(cell.weather_nm, "맑음")

    def test_weather_fetch_requires_location(self):
        with self.assertRaises(BusinessRuleError) as ctx:
            self.svc.fetch_weather("OR001", self.today)
        self.assertIn("위치", str(ctx.exception.message))

    def test_weather_fetch_future_blocked(self):
        future = (date.today() + timedelta(days=2)).isoformat()
        with self.assertRaises(BusinessRuleError):
            self.svc.fetch_weather("OR001", future)

    def test_future_works_preparing_ok(self):
        from app.services.work_log_service import (  # noqa: WPS433
            MSG_FUTURE_DETAIL,
            MSG_FUTURE_STATUS,
            STATUS_PREPARING_CD,
        )
        from app.schemas.work_log import WorkLogIntegratedSaveRequest  # noqa: WPS433

        future = (date.today() + timedelta(days=2)).isoformat()
        save = self.svc.upsert_works(
            "OR001",
            future,
            WorkLogWorksUpsertRequest(
                works=[
                    WorkLogWorkUpsertItem(
                        work_mid_cd="WK010100",
                        start_tm="09:00",
                        status_cd=None,
                        rmk="미래 준비",
                    )
                ]
            ),
            user_id="T1",
        )
        self.assertEqual(len(save.work_ids), 1)
        daily = self.svc.get_daily("OR001", future)
        self.assertEqual(len(daily.works), 1)
        self.assertEqual(daily.works[0].status_cd, STATUS_PREPARING_CD)

        with self.assertRaises(BusinessRuleError) as ctx:
            self.svc.upsert_works(
                "OR001",
                future,
                WorkLogWorksUpsertRequest(
                    works=[
                        WorkLogWorkUpsertItem(
                            work_id=save.work_ids[0],
                            work_mid_cd="WK010100",
                            status_cd="WO010200",
                        )
                    ]
                ),
                user_id="T1",
            )
        self.assertIn("준비중", str(ctx.exception.message))
        self.assertEqual(ctx.exception.message, MSG_FUTURE_STATUS)

        with self.assertRaises(BusinessRuleError) as ctx2:
            self.svc.save_integrated(
                "OR001",
                future,
                WorkLogIntegratedSaveRequest(works=[]),
                user_id="T1",
            )
        self.assertEqual(ctx2.exception.message, MSG_FUTURE_DETAIL)


if __name__ == "__main__":
    unittest.main()
