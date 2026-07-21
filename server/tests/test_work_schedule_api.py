# -*- coding: utf-8 -*-
"""영농 일정(Schedule) Phase1 서비스 테스트 — WLS-001."""

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
# server/app 이 repo/app 보다 우선되도록 server를 앞쪽에 둔다.
for p in (_REPO, _SERVER):
    s = str(p)
    if s in sys.path:
        sys.path.remove(s)
    sys.path.insert(0, s)

from app.core.exceptions import BusinessRuleError  # noqa: E402
from app.schemas.work_schedule import WorkScheduleCreateRequest  # noqa: E402
from app.services.work_log_service import WorkLogService  # noqa: E402
from app.services.work_schedule_service import WorkScheduleService  # noqa: E402
from core.work_schedule_constants import (  # noqa: E402
    ERR_FUTURE_CONVERT,
    SCHED_STATUS_CONVERTED,
    SCHED_STATUS_PENDING,
)


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
        INSERT INTO m_common_code (farm_cd, code_cd, code_nm, parent_cd) VALUES
          ('OR001','WK010100','전정','WK01'),
          ('OR001','WK010200','방제','WK01');

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
        """
    )
    conn.commit()
    conn.close()
    return path


class WorkScheduleServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db = _build_tmp_db()
        self.svc = WorkScheduleService(self.db)
        self.work_svc = WorkLogService(db_path=self.db)

    def tearDown(self) -> None:
        self.db.unlink(missing_ok=True)

    def test_create_list_and_future_convert_blocked(self) -> None:
        today = date.today()
        future = (today + timedelta(days=3)).isoformat()
        created = self.svc.create(
            "OR001",
            WorkScheduleCreateRequest(
                work_dt=future,
                work_mid_cd="WK010200",
                title="미래 방제",
                contents="예찰 후 실시",
            ),
            user_id="tester",
        )
        sid = created.data["sched_id"]
        self.assertTrue(sid.startswith("SCH"))
        listed = self.svc.list_schedules("OR001", start_dt=future, end_dt=future)
        self.assertEqual(len(listed.data), 1)
        self.assertEqual(listed.data[0].work_main_cd, "WK01")

        with self.assertRaises(BusinessRuleError) as ctx:
            self.svc.convert_to_draft("OR001", sid, user_id="tester")
        self.assertEqual(ctx.exception.error_code, ERR_FUTURE_CONVERT)

    def test_convert_idempotent_and_rollback_on_delete(self) -> None:
        today = date.today().isoformat()
        created = self.svc.create(
            "OR001",
            WorkScheduleCreateRequest(
                work_dt=today,
                work_mid_cd="WK010100",
                work_loc_id="SITE01",
                title="전정",
            ),
            user_id="tester",
        )
        sid = created.data["sched_id"]
        r1 = self.svc.convert_to_draft("OR001", sid, user_id="tester")
        wid = r1.data.work_id
        self.assertRegex(wid, r"^\d{8}-\d{2}$")
        self.assertEqual(r1.data.prefilled_data.work_mid_cd, "WK010100")

        r2 = self.svc.convert_to_draft("OR001", sid, user_id="tester")
        self.assertEqual(r2.data.work_id, wid)

        conn = sqlite3.connect(str(self.db))
        conn.row_factory = sqlite3.Row
        st = conn.execute(
            "SELECT sched_status_cd, converted_work_id FROM t_work_schedule WHERE sched_id=?",
            (sid,),
        ).fetchone()
        conn.close()
        self.assertEqual(st["sched_status_cd"], SCHED_STATUS_CONVERTED)
        self.assertEqual(st["converted_work_id"], wid)

        # 기존 작업이 있어도 convert는 추가만 함
        created2 = self.svc.create(
            "OR001",
            WorkScheduleCreateRequest(work_dt=today, work_mid_cd="WK010200", title="방제"),
            user_id="tester",
        )
        r3 = self.svc.convert_to_draft("OR001", created2.data["sched_id"], user_id="tester")
        self.assertNotEqual(r3.data.work_id, wid)

        self.work_svc.delete_work("OR001", wid, user_id="tester")
        conn = sqlite3.connect(str(self.db))
        conn.row_factory = sqlite3.Row
        st2 = conn.execute(
            "SELECT sched_status_cd, converted_work_id FROM t_work_schedule WHERE sched_id=?",
            (sid,),
        ).fetchone()
        conn.close()
        self.assertEqual(st2["sched_status_cd"], SCHED_STATUS_PENDING)
        self.assertIsNone(st2["converted_work_id"])


if __name__ == "__main__":
    unittest.main()
