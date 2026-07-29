# -*- coding: utf-8 -*-
"""봉지 여부(after_bag_yn) 판정 — 영농일지·일정관리."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from core.pesticide_ai_recommend_manager import PesticideAIRecommendManager
from core.work_log_constants import (
    WORK_MID_CD_BAG,
    WORK_STATUS_CANCELLED,
    WORK_STATUS_DONE,
    WORK_STATUS_IN_PROGRESS,
    WORK_STATUS_READY,
)
from core.work_schedule_constants import (
    SCHED_STATUS_CONVERTED,
    SCHED_STATUS_PENDING,
)


class _MemDb:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.conn = sqlite3.connect(str(path))
        self.conn.row_factory = sqlite3.Row

    def execute_query(self, sql: str, params=None):
        cur = self.conn.execute(sql, params or ())
        if sql.lstrip().upper().startswith("SELECT"):
            return cur.fetchall()
        self.conn.commit()
        return []


class TestAfterBagStatus(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmp.name) / "t.db"
        self.db = _MemDb(self.db_path)
        c = self.db.conn
        c.executescript(
            """
            CREATE TABLE m_common_code (
              code_cd TEXT PRIMARY KEY, code_nm TEXT
            );
            INSERT INTO m_common_code VALUES ('WK010900', '봉지작업');
            INSERT INTO m_common_code VALUES ('WK010200', '방제살포');
            CREATE TABLE t_work_master (
              farm_cd TEXT, work_dt TEXT, work_rmk TEXT
            );
            CREATE TABLE t_work_detail (
              farm_cd TEXT, work_dt TEXT, work_mid_cd TEXT, status_cd TEXT
            );
            CREATE TABLE t_work_schedule (
              farm_cd TEXT, sched_id TEXT, work_dt TEXT, work_tm TEXT,
              work_main_cd TEXT, work_mid_cd TEXT, work_loc_id TEXT,
              title TEXT, contents TEXT, sched_status_cd TEXT,
              converted_work_id TEXT, google_event_id TEXT,
              sync_status TEXT, last_synced_at TEXT,
              reg_dt TEXT, reg_id TEXT, mod_dt TEXT, mod_id TEXT,
              PRIMARY KEY (farm_cd, sched_id)
            );
            """
        )
        self.mgr = PesticideAIRecommendManager(self.db)

    def tearDown(self) -> None:
        self.db.conn.close()
        self._tmp.cleanup()

    def _add_work(
        self, dt: str, mid: str, status: str, rmk: str = ""
    ) -> None:
        self.db.conn.execute(
            "INSERT INTO t_work_master(farm_cd, work_dt, work_rmk) VALUES (?,?,?)",
            ("OR001", dt, rmk),
        )
        self.db.conn.execute(
            "INSERT INTO t_work_detail(farm_cd, work_dt, work_mid_cd, status_cd) "
            "VALUES (?,?,?,?)",
            ("OR001", dt, mid, status),
        )
        self.db.conn.commit()

    def _add_sched(self, dt: str, mid: str, status: str, title: str = "") -> None:
        self.db.conn.execute(
            """
            INSERT INTO t_work_schedule (
              farm_cd, sched_id, work_dt, work_main_cd, work_mid_cd,
              title, contents, sched_status_cd, sync_status,
              reg_dt, reg_id, mod_dt, mod_id
            ) VALUES (?,?,?,'WK01',?,?,?,?, 'PENDING',
                      '2026-01-01','t','2026-01-01','t')
            """,
            ("OR001", f"SCH{dt}", dt, mid, title, "", status),
        )
        self.db.conn.commit()

    def test_wrong_cancel_code_not_done(self) -> None:
        # 과거 버그: WO010400(취소)를 완료로 오인 — 취소는 False
        self._add_work("2026-06-01", WORK_MID_CD_BAG, WORK_STATUS_CANCELLED)
        self.assertFalse(self.mgr.get_after_bag_status_for_year("OR001", 2026))

    def test_work_log_done_status(self) -> None:
        self._add_work("2026-06-01", WORK_MID_CD_BAG, WORK_STATUS_DONE)
        self.assertTrue(self.mgr.get_after_bag_status_for_year("OR001", 2026))

    def test_work_log_in_progress_counts(self) -> None:
        self._add_work("2026-07-01", WORK_MID_CD_BAG, WORK_STATUS_IN_PROGRESS)
        self.assertTrue(self.mgr.get_after_bag_status_for_year("OR001", 2026))

    def test_ready_status_excluded(self) -> None:
        self._add_work("2026-07-01", WORK_MID_CD_BAG, WORK_STATUS_READY)
        self.assertFalse(self.mgr.get_after_bag_status_for_year("OR001", 2026))

    def test_schedule_converted_bag(self) -> None:
        self._add_sched(
            "2026-06-15", WORK_MID_CD_BAG, SCHED_STATUS_CONVERTED, "봉지작업"
        )
        self.assertTrue(self.mgr.get_after_bag_status_for_year("OR001", 2026))

    def test_schedule_pending_not_enough(self) -> None:
        self._add_sched(
            "2026-06-15", WORK_MID_CD_BAG, SCHED_STATUS_PENDING, "봉지작업"
        )
        self.assertFalse(self.mgr.get_after_bag_status_for_year("OR001", 2026))


if __name__ == "__main__":
    unittest.main()
