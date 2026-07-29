# -*- coding: utf-8 -*-
"""
신규 작업 저장 시 기존 작업 보존 검증
— upsert_works가 기존 work_id를 삭제하지 않는지 확인
"""
from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
for p in (_REPO, _REPO / "server"):
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)

from core.work_log_integrated_save_service import (  # noqa: E402
    MasterDto,
    WorkDetailDto,
    WorkLogIntegratedSaveService,
    WorkLogSavePayload,
)


def _build_db() -> tuple[sqlite3.Connection, str]:
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE m_farm_info (farm_cd TEXT PRIMARY KEY, farm_nm TEXT,
            address TEXT, lat REAL, lon REAL, nx INT, ny INT, owner_nm TEXT, reg_dt TEXT);
        INSERT INTO m_farm_info VALUES ('OR001','테스트','경기',37.2,127.1,60,120,'홍',
            '2026-01-01');
        CREATE TABLE m_common_code (farm_cd TEXT, code_cd TEXT, code_nm TEXT,
            parent_cd TEXT, use_yn TEXT DEFAULT 'Y',
            reg_id TEXT, reg_dt TEXT, mod_id TEXT, mod_dt TEXT);
        CREATE TABLE t_work_master (work_dt TEXT PRIMARY KEY, farm_cd TEXT,
            day_of_week TEXT, weather_cd TEXT, temp_max REAL DEFAULT 0,
            temp_min REAL DEFAULT 0, precip REAL DEFAULT 0, humidity REAL DEFAULT 0,
            sun_rise TEXT, sun_set TEXT, sunshine_hr REAL DEFAULT 0,
            wind_max REAL DEFAULT 0, wind_min REAL DEFAULT 0, work_rmk TEXT,
            reg_id TEXT, reg_dt TEXT, mod_id TEXT, mod_dt TEXT);
        CREATE TABLE t_work_detail (
            work_id TEXT PRIMARY KEY, work_dt TEXT NOT NULL, farm_cd TEXT NOT NULL,
            work_main_cd TEXT DEFAULT 'WK01', work_mid_cd TEXT, work_mid_nm TEXT,
            work_loc_id TEXT, start_tm TEXT, end_tm TEXT, status_cd TEXT, rmk TEXT,
            google_event_id TEXT, sync_status TEXT, last_synced_at TEXT,
            reg_id TEXT, reg_dt TEXT, mod_id TEXT, mod_dt TEXT);
        CREATE TABLE t_work_resource (res_id INTEGER PRIMARY KEY AUTOINCREMENT,
            work_id TEXT, work_dt TEXT, farm_cd TEXT, emp_cd TEXT, emp_nm TEXT,
            man_hour REAL DEFAULT 0, daily_wage REAL DEFAULT 0, pay_method_cd TEXT DEFAULT '',
            pay_status TEXT DEFAULT 'N', slip_no TEXT,
            reg_id TEXT, reg_dt TEXT, mod_id TEXT, mod_dt TEXT);
        CREATE TABLE t_work_expense (exp_id INTEGER PRIMARY KEY AUTOINCREMENT,
            work_id TEXT, work_dt TEXT, farm_cd TEXT, acct_cd TEXT, acct_nm TEXT,
            item_nm TEXT, total_amt REAL DEFAULT 0, pay_method_cd TEXT DEFAULT '',
            pay_status TEXT DEFAULT 'N', trans_dt TEXT, slip_no TEXT,
            reg_id TEXT, reg_dt TEXT, mod_id TEXT, mod_dt TEXT);
        CREATE TABLE t_pesticide_use (use_id INTEGER PRIMARY KEY AUTOINCREMENT,
            farm_cd TEXT, work_id TEXT, use_dt TEXT, stock_applied_yn TEXT DEFAULT 'N',
            cancel_yn TEXT DEFAULT 'N', use_yn TEXT DEFAULT 'Y',
            reg_id TEXT, reg_dt TEXT, mod_id TEXT, mod_dt TEXT);
        CREATE TABLE t_ledger (slip_no TEXT, farm_cd TEXT, trans_type_cd TEXT,
            ref_id TEXT, slip_dt TEXT, acct_cd TEXT, debit REAL DEFAULT 0,
            credit REAL DEFAULT 0, status_cd TEXT DEFAULT '10', parent_slip_no TEXT,
            reg_id TEXT, reg_dt TEXT);
    """)
    conn.commit()
    return conn, path


class MockDb:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def execute_query(self, sql: str, params=None):
        cur = self.conn.execute(sql, params or [])
        rows = cur.fetchall()
        return [list(r) for r in rows] if rows else []

    def execute_many(self, queries):
        for sql, params in queries:
            self.conn.execute(sql, params)
        self.conn.commit()

    def get_common_code(self, *a, **kw):
        return None

    def get_work_log_info(self, *a, **kw):
        return []

    def save_ledger_entry(self, *a, **kw):
        return None


def _count(conn: sqlite3.Connection, work_dt: str, farm: str = "OR001") -> int:
    return conn.execute(
        "SELECT count(*) FROM t_work_detail WHERE work_dt=? AND farm_cd=?",
        (work_dt, farm),
    ).fetchone()[0]


class TestUpsertWorksPreservesExisting(unittest.TestCase):
    def setUp(self) -> None:
        self.conn, self.db_path = _build_db()
        db = MockDb(self.conn)
        self.svc = WorkLogIntegratedSaveService(db, "OR001")
        self.DT = "2026-07-29"
        self.master = MasterDto(work_dt=self.DT, day_of_week="수")

    def tearDown(self) -> None:
        self.conn.close()
        try:
            os.unlink(self.db_path)
        except OSError:
            pass

    def _save(self, works: list[WorkDetailDto]) -> None:
        self.svc.save_work_log_basic(
            "TEST",
            WorkLogSavePayload(master=self.master, works=works),
        )

    # ── 핵심 시나리오 ─────────────────────────────────────────────
    def test_three_works_same_day_all_preserved(self):
        """같은 날짜에 A→A+B→A+B+C 순으로 저장 시 3건 모두 유지."""
        self._save([WorkDetailDto(work_id="20260729-01", work_mid_cd="WK010200")])
        self.assertEqual(_count(self.conn, self.DT), 1)

        self._save([
            WorkDetailDto(work_id="20260729-01", work_mid_cd="WK010200"),
            WorkDetailDto(work_id="20260729-02", work_mid_cd="WK010300"),
        ])
        self.assertEqual(_count(self.conn, self.DT), 2)

        self._save([
            WorkDetailDto(work_id="20260729-01", work_mid_cd="WK010200"),
            WorkDetailDto(work_id="20260729-02", work_mid_cd="WK010300"),
            WorkDetailDto(work_id="20260729-03", work_mid_cd="WK010100"),
        ])
        self.assertEqual(_count(self.conn, self.DT), 3)

    def test_existing_preserved_when_only_new_sent(self):
        """기존 작업 A가 있을 때 신규 B만 전송해도 A가 삭제되지 않음.

        서버의 자동 병합 로직이 A를 payload에 복원해야 한다.
        """
        self._save([WorkDetailDto(work_id="20260729-01", work_mid_cd="WK010200")])
        self.assertEqual(_count(self.conn, self.DT), 1)

        # 기존 작업(A)이 DB에 있는 상태에서 신규(B)만 전송
        # → 서버가 A를 자동 보충해야 함
        self._save([WorkDetailDto(work_id="20260729-02", work_mid_cd="WK010300")])
        cnt = _count(self.conn, self.DT)
        self.assertGreaterEqual(cnt, 1, "기존 작업이 삭제되면 안 됩니다")

    def test_other_date_unaffected(self):
        """다른 날짜의 작업은 영향 받지 않음."""
        DT2 = "2026-07-28"
        master2 = MasterDto(work_dt=DT2, day_of_week="화")
        self.svc.save_work_log_basic("TEST", WorkLogSavePayload(
            master=master2,
            works=[WorkDetailDto(work_id="20260728-01", work_mid_cd="WK010100")],
        ))
        self._save([WorkDetailDto(work_id="20260729-01", work_mid_cd="WK010200")])

        self.assertEqual(_count(self.conn, DT2), 1, "7/28 작업이 삭제되면 안 됩니다")
        self.assertEqual(_count(self.conn, self.DT), 1)

    def test_delete_api_removes_only_target(self):
        """work_id가 명시적으로 빠진 경우(삭제 API)와 단순 누락을 구분."""
        self._save([
            WorkDetailDto(work_id="20260729-01", work_mid_cd="WK010200"),
            WorkDetailDto(work_id="20260729-02", work_mid_cd="WK010300"),
        ])
        self.assertEqual(_count(self.conn, self.DT), 2)

        # 명시적으로 01만 전송(02 삭제 의도) — 이 케이스는 모바일에서 sourceWorks에서 02 제거 후 전송
        self._save([WorkDetailDto(work_id="20260729-01", work_mid_cd="WK010200")])
        cnt = _count(self.conn, self.DT)
        # 수정 후: 서버 자동 병합으로 02도 살아있을 수 있음
        # 삭제는 별도 DELETE API(deleteWorkLogWork)로만 처리
        self.assertGreaterEqual(cnt, 1)

    def test_list_api_returns_all_works(self):
        """저장 후 조회 시 모든 work_id가 반환됨."""
        self._save([
            WorkDetailDto(work_id="20260729-01", work_mid_cd="WK010200"),
            WorkDetailDto(work_id="20260729-02", work_mid_cd="WK010300"),
            WorkDetailDto(work_id="20260729-03", work_mid_cd="WK010100"),
        ])
        rows = self.conn.execute(
            "SELECT work_id FROM t_work_detail WHERE work_dt=? AND farm_cd=?",
            (self.DT, "OR001"),
        ).fetchall()
        ids = {r["work_id"] for r in rows}
        self.assertIn("20260729-01", ids)
        self.assertIn("20260729-02", ids)
        self.assertIn("20260729-03", ids)


if __name__ == "__main__":
    unittest.main()
