# -*- coding: utf-8 -*-
"""예정→실적 이관 · schedule API 410 — 예정·실적 통합."""

from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

_SERVER = Path(__file__).resolve().parents[1]
_REPO = _SERVER.parent
for p in (_REPO, _SERVER):
    s = str(p)
    if s in sys.path:
        sys.path.remove(s)
    sys.path.insert(0, s)

from core.work_schedule_constants import (  # noqa: E402
    SCHED_STATUS_CONVERTED,
    SCHED_STATUS_PENDING,
)
from core.work_schedule_migrate import migrate_work_schedules_to_work_detail  # noqa: E402
from core.work_schedule_schema import ensure_work_schedule_schema  # noqa: E402


def _build_tmp_db() -> Path:
    fd, name = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    path = Path(name)
    path.unlink(missing_ok=True)
    conn = sqlite3.connect(str(path))
    conn.executescript(
        """
        CREATE TABLE m_farm_info (
            farm_cd TEXT PRIMARY KEY, farm_nm TEXT
        );
        INSERT INTO m_farm_info VALUES ('OR001', '테스트농장');

        CREATE TABLE m_common_code (
            farm_cd TEXT, code_cd TEXT, code_nm TEXT, parent_cd TEXT,
            use_yn TEXT DEFAULT 'Y',
            reg_id TEXT, reg_dt TEXT, mod_id TEXT, mod_dt TEXT
        );

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
            google_event_id TEXT, sync_status TEXT, last_synced_at TEXT,
            reg_id TEXT, reg_dt TEXT, mod_id TEXT, mod_dt TEXT, rmk TEXT
        );
        """
    )
    conn.commit()
    conn.close()
    ensure_work_schedule_schema(path)
    return path


class WorkScheduleMigrateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db = _build_tmp_db()
        self.future = (date.today() + timedelta(days=3)).isoformat()

    def tearDown(self) -> None:
        try:
            self.db.unlink(missing_ok=True)
        except OSError:
            pass

    def test_migrate_pending_to_preparing_work(self):
        conn = sqlite3.connect(str(self.db))
        conn.row_factory = sqlite3.Row
        conn.execute(
            """
            INSERT INTO t_work_schedule (
                farm_cd, sched_id, work_dt, work_tm, work_main_cd, work_mid_cd,
                work_loc_id, title, contents, sched_status_cd,
                converted_work_id, google_event_id, sync_status, last_synced_at,
                reg_dt, reg_id, mod_dt, mod_id
            ) VALUES (
                'OR001', 'SCH20260101-001', ?, '09:00', 'WK01', 'WK010100',
                NULL, '전정 예정', '메모', ?,
                NULL, 'gev-1', 'SYNCED', datetime('now','localtime'),
                datetime('now','localtime'), 'T', datetime('now','localtime'), 'T'
            )
            """,
            (self.future, SCHED_STATUS_PENDING),
        )
        conn.commit()
        conn.close()

        stats = migrate_work_schedules_to_work_detail(self.db)
        self.assertTrue(stats["ok"], stats.get("reason"))
        self.assertEqual(stats["migrated"], 1)

        conn = sqlite3.connect(str(self.db))
        conn.row_factory = sqlite3.Row
        work = conn.execute(
            "SELECT * FROM t_work_detail WHERE farm_cd='OR001'"
        ).fetchone()
        self.assertIsNotNone(work)
        assert work is not None
        self.assertEqual(work["status_cd"], "WO010100")
        self.assertEqual(work["google_event_id"], "gev-1")
        self.assertIn("전정 예정", work["rmk"] or "")
        self.assertEqual(work["start_tm"], "09:00")

        sched = conn.execute(
            "SELECT sched_status_cd, converted_work_id FROM t_work_schedule"
        ).fetchone()
        assert sched is not None
        self.assertEqual(sched["sched_status_cd"], SCHED_STATUS_CONVERTED)
        self.assertEqual(sched["converted_work_id"], work["work_id"])
        conn.close()

        # 멱등: 재실행 시 skip
        stats2 = migrate_work_schedules_to_work_detail(self.db)
        self.assertTrue(stats2["ok"])
        self.assertEqual(stats2["migrated"], 0)


if __name__ == "__main__":
    unittest.main()
