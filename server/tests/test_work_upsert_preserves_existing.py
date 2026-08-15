# -*- coding: utf-8 -*-
"""신규 일정(upsert_works / save_work_log_basic) 저장 시 기존 작업 보존."""

from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import date, timedelta
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
from app.schemas.work_log import (  # noqa: E402
    WorkLogWorkUpsertItem,
    WorkLogWorksUpsertRequest,
)
from app.services.work_log_service import WorkLogService  # noqa: E402


def _build_db() -> tuple[sqlite3.Connection, Path]:
    fd, path_s = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    path = Path(path_s)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
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
          ('OR001','WK010100','전정','WK01'),
          ('OR001','WK010200','방제','WK01'),
          ('OR001','WK010300','시비','WK01'),
          ('OR001','WO010100','준비중','WO01'),
          ('OR001','WO010200','진행중','WO01'),
          ('OR001','WO010300','완료','WO01');

        CREATE TABLE m_farm_site (
            site_id TEXT PRIMARY KEY, farm_cd TEXT, site_nm TEXT
        );
        CREATE TABLE m_partner (
            pt_id TEXT, farm_cd TEXT, worker_type_cd TEXT, pt_nm TEXT
        );
        CREATE TABLE m_account_code (
            acct_cd TEXT PRIMARY KEY, acct_nm TEXT
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
            reg_id TEXT, reg_dt TEXT, mod_id TEXT, mod_dt TEXT, rmk TEXT,
            google_event_id TEXT, sync_status TEXT
        );
        CREATE TABLE t_work_resource (
            res_id INTEGER PRIMARY KEY,
            work_id TEXT, farm_cd TEXT, emp_cd TEXT,
            daily_wage REAL, man_hour REAL DEFAULT 0,
            pay_method_cd TEXT, pay_status TEXT, slip_no TEXT
        );
        CREATE TABLE t_work_expense (
            exp_id INTEGER PRIMARY KEY,
            work_id TEXT, farm_cd TEXT, total_amt REAL,
            acct_cd TEXT, item_nm TEXT, pay_method_cd TEXT,
            pay_status TEXT, trans_dt TEXT, slip_no TEXT
        );
        CREATE TABLE t_pesticide_use (
            use_id INTEGER PRIMARY KEY AUTOINCREMENT,
            farm_cd TEXT, use_dt TEXT, site_id INTEGER,
            worker_nm TEXT, worker_id TEXT, work_type_nm TEXT, rmk TEXT,
            stock_applied_yn TEXT DEFAULT 'N',
            stock_applied_dt TEXT, stock_applied_by TEXT,
            cancel_yn TEXT NOT NULL DEFAULT 'N',
            use_yn TEXT DEFAULT 'Y', work_id TEXT,
            reg_id TEXT, reg_dt TEXT, mod_id TEXT, mod_dt TEXT
        );
        CREATE TABLE t_pesticide_use_line (
            use_line_id INTEGER PRIMARY KEY AUTOINCREMENT,
            use_id INTEGER, line_no INTEGER, item_id INTEGER,
            item_nm_snapshot TEXT, spec_nm_snapshot TEXT,
            use_qty INTEGER, purpose_nm TEXT, line_rmk TEXT,
            reg_id TEXT, mod_id TEXT
        );
        CREATE TABLE t_pesticide_stock_hist (
            hist_id INTEGER PRIMARY KEY AUTOINCREMENT,
            farm_cd TEXT, item_id INTEGER, trans_type TEXT,
            ref_table TEXT, ref_id INTEGER, ref_line_id INTEGER,
            qty_delta INTEGER, qty_after INTEGER, trans_dt TEXT,
            rmk TEXT, reg_id TEXT, reg_dt TEXT
        );
        CREATE TABLE m_pesticide_item (
            item_id INTEGER PRIMARY KEY, farm_cd TEXT, item_nm TEXT,
            qty_piece INTEGER, use_yn TEXT DEFAULT 'Y',
            mod_id TEXT, mod_dt TEXT
        );
        CREATE TABLE t_ledger (
            slip_no TEXT PRIMARY KEY, farm_cd TEXT, trans_dt TEXT,
            trans_type_cd TEXT, acct_cd TEXT, trans_amt REAL, rmk TEXT,
            ref_id TEXT, parent_slip_no TEXT, trans_st TEXT,
            reg_id TEXT, reg_dt TEXT, mod_id TEXT, mod_dt TEXT
        );
        CREATE TABLE t_weather_cache (
            farm_cd TEXT, weather_dt TEXT, weather_json TEXT, reg_dt TEXT,
            PRIMARY KEY (farm_cd, weather_dt)
        );
        """
    )
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

    def fetch_all(self, sql: str, params=None):
        return self.conn.execute(sql, params or []).fetchall()

    def transaction(self):
        return _Txn(self.conn)


class _Txn:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def __enter__(self):
        self.conn.execute("BEGIN IMMEDIATE")
        return self.conn.cursor()

    def __exit__(self, exc_type, exc, tb):
        if exc_type:
            self.conn.rollback()
        else:
            self.conn.commit()
        return False


def _count(conn: sqlite3.Connection, work_dt: str, farm: str = "OR001") -> int:
    return int(
        conn.execute(
            "SELECT count(*) FROM t_work_detail WHERE work_dt=? AND farm_cd=?",
            (work_dt, farm),
        ).fetchone()[0]
    )


def _ids(conn: sqlite3.Connection, work_dt: str, farm: str = "OR001") -> set[str]:
    rows = conn.execute(
        "SELECT work_id FROM t_work_detail WHERE work_dt=? AND farm_cd=?",
        (work_dt, farm),
    ).fetchall()
    return {str(r["work_id"]) for r in rows}


class TestBasicSaveDoesNotDeleteMissing(unittest.TestCase):
    """save_work_log_basic: payload 누락 항목을 삭제하지 않음."""

    def setUp(self) -> None:
        self.conn, self.db_path = _build_db()
        self.svc = WorkLogIntegratedSaveService(MockDb(self.conn), "OR001")
        self.DT = (date.today() + timedelta(days=5)).isoformat()
        self.digits = self.DT.replace("-", "")
        self.master = MasterDto(work_dt=self.DT, day_of_week="수")

    def tearDown(self) -> None:
        self.conn.close()
        try:
            self.db_path.unlink(missing_ok=True)
        except OSError:
            pass

    def _save(self, works: list[WorkDetailDto]) -> None:
        self.svc.save_work_log_basic(
            "TEST",
            WorkLogSavePayload(master=self.master, works=works),
        )

    def test_abc_sequential_full_payload(self) -> None:
        a = f"{self.digits}-01"
        b = f"{self.digits}-02"
        c = f"{self.digits}-03"
        self._save([WorkDetailDto(work_id=a, work_mid_cd="WK010200", rmk="A")])
        self._save(
            [
                WorkDetailDto(work_id=a, work_mid_cd="WK010200", rmk="A"),
                WorkDetailDto(work_id=b, work_mid_cd="WK010300", rmk="B"),
            ]
        )
        self._save(
            [
                WorkDetailDto(work_id=a, work_mid_cd="WK010200", rmk="A"),
                WorkDetailDto(work_id=b, work_mid_cd="WK010300", rmk="B"),
                WorkDetailDto(work_id=c, work_mid_cd="WK010100", rmk="C"),
            ]
        )
        self.assertEqual(_ids(self.conn, self.DT), {a, b, c})

    def test_only_new_sent_preserves_existing(self) -> None:
        """모바일이 신규 1건만 보내도 기존 A/B가 DB에서 삭제되지 않음."""
        a = f"{self.digits}-01"
        b = f"{self.digits}-02"
        self._save(
            [
                WorkDetailDto(work_id=a, work_mid_cd="WK010200", rmk="A"),
                WorkDetailDto(work_id=b, work_mid_cd="WK010300", rmk="B"),
            ]
        )
        self.assertEqual(_count(self.conn, self.DT), 2)
        # 신규 C만 전송 (기존 누락) — basic은 삭제하지 않음
        self._save(
            [WorkDetailDto(work_id=f"{self.digits}-03", work_mid_cd="WK010100", rmk="C")]
        )
        self.assertEqual(_count(self.conn, self.DT), 3)
        self.assertEqual(
            _ids(self.conn, self.DT),
            {a, b, f"{self.digits}-03"},
        )

    def test_integrated_still_sync_deletes(self) -> None:
        """PC integrated는 누락 행 삭제(기존 계약) 유지."""
        a = f"{self.digits}-01"
        b = f"{self.digits}-02"
        self._save(
            [
                WorkDetailDto(work_id=a, work_mid_cd="WK010200"),
                WorkDetailDto(work_id=b, work_mid_cd="WK010300"),
            ]
        )
        # 과거일로 강제 (integrated는 미래 거부지만 core 직접 호출)
        past = (date.today() - timedelta(days=3)).isoformat()
        master = MasterDto(work_dt=past, day_of_week="월")
        dig = past.replace("-", "")
        a2, b2 = f"{dig}-01", f"{dig}-02"
        self.svc.save_work_log_basic(
            "TEST",
            WorkLogSavePayload(
                master=master,
                works=[
                    WorkDetailDto(work_id=a2, work_mid_cd="WK010200"),
                    WorkDetailDto(work_id=b2, work_mid_cd="WK010300"),
                ],
            ),
        )
        self.svc.save_integrated(
            "TEST",
            WorkLogSavePayload(
                master=master,
                works=[WorkDetailDto(work_id=a2, work_mid_cd="WK010200")],
                labor_work_id=a2,
            ),
        )
        self.assertEqual(_ids(self.conn, past), {a2})


class TestUpsertWorksApiPreserves(unittest.TestCase):
    """WorkLogService.upsert_works — A→B→C 및 신규-only 전송."""

    def setUp(self) -> None:
        self.conn, self.db_path = _build_db()
        self.conn.close()
        self.svc = WorkLogService(db_path=self.db_path)
        self.DT = (date.today() + timedelta(days=7)).isoformat()
        self.digits = self.DT.replace("-", "")

    def tearDown(self) -> None:
        try:
            self.db_path.unlink(missing_ok=True)
        except OSError:
            pass

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(str(self.db_path))
        c.row_factory = sqlite3.Row
        return c

    def test_sequential_abc_and_monthly_count(self) -> None:
        for mid, rmk in (
            ("WK010200", "A"),
            ("WK010300", "B"),
            ("WK010100", "C"),
        ):
            # 매번 신규만 추가 전송(기존 누락) — 버그 재현 경로
            self.svc.upsert_works(
                "OR001",
                self.DT,
                WorkLogWorksUpsertRequest(
                    works=[
                        WorkLogWorkUpsertItem(
                            work_mid_cd=mid,
                            start_tm="09:00",
                            end_tm="10:00",
                            rmk=rmk,
                        )
                    ]
                ),
                user_id="T1",
            )
        conn = self._conn()
        try:
            self.assertEqual(_count(conn, self.DT), 3)
            ids = _ids(conn, self.DT)
            self.assertEqual(len(ids), 3)
            self.assertTrue(all(i.startswith(self.digits + "-") for i in ids))
        finally:
            conn.close()

        y, m, _ = (int(x) for x in self.DT.split("-"))
        month = self.svc.get_monthly("OR001", year=y, month=m)
        cell = month.days.get(self.DT)
        self.assertIsNotNone(cell)
        assert cell is not None
        self.assertEqual(cell.work_count, 3)

    def test_new_id_does_not_overwrite_01(self) -> None:
        first = self.svc.upsert_works(
            "OR001",
            self.DT,
            WorkLogWorksUpsertRequest(
                works=[WorkLogWorkUpsertItem(work_mid_cd="WK010200", rmk="A")]
            ),
            user_id="T1",
        )
        self.assertEqual(first.work_ids[0], f"{self.digits}-01")
        second = self.svc.upsert_works(
            "OR001",
            self.DT,
            WorkLogWorksUpsertRequest(
                works=[WorkLogWorkUpsertItem(work_mid_cd="WK010300", rmk="B")]
            ),
            user_id="T1",
        )
        self.assertEqual(second.work_ids[0], f"{self.digits}-02")
        daily = self.svc.get_daily("OR001", self.DT)
        self.assertEqual(len(daily.works), 2)
        rmks = {w.rmk for w in daily.works}
        self.assertEqual(rmks, {"A", "B"})

    def test_duplicate_work_id_in_payload_reallocates(self) -> None:
        """payload에 C가 B와 같은 work_id를 가져도 B 보존·C는 새 seq."""
        a = self.svc.upsert_works(
            "OR001",
            self.DT,
            WorkLogWorksUpsertRequest(
                works=[WorkLogWorkUpsertItem(work_mid_cd="WK010200", rmk="A")]
            ),
            user_id="T1",
        )
        self.assertEqual(a.work_ids[0], f"{self.digits}-01")
        self.svc.upsert_works(
            "OR001",
            self.DT,
            WorkLogWorksUpsertRequest(
                works=[
                    WorkLogWorkUpsertItem(
                        work_id=f"{self.digits}-01", work_mid_cd="WK010200", rmk="A"
                    ),
                    WorkLogWorkUpsertItem(work_mid_cd="WK010300", rmk="B"),
                ]
            ),
            user_id="T1",
        )
        self.svc.upsert_works(
            "OR001",
            self.DT,
            WorkLogWorksUpsertRequest(
                works=[
                    WorkLogWorkUpsertItem(
                        work_id=f"{self.digits}-01", work_mid_cd="WK010200", rmk="A"
                    ),
                    WorkLogWorkUpsertItem(
                        work_id=f"{self.digits}-02", work_mid_cd="WK010200", rmk="B"
                    ),
                    WorkLogWorkUpsertItem(
                        work_id=f"{self.digits}-02", work_mid_cd="WK010200", rmk="C"
                    ),
                ]
            ),
            user_id="T1",
        )
        daily = self.svc.get_daily("OR001", self.DT)
        rmks = {w.rmk: w.work_id for w in daily.works}
        self.assertEqual(set(rmks), {"A", "B", "C"})
        self.assertEqual(rmks["B"], f"{self.digits}-02")
        self.assertEqual(rmks["C"], f"{self.digits}-03")
        y, m, _ = (int(x) for x in self.DT.split("-"))
        cell = self.svc.get_monthly("OR001", year=y, month=m).days.get(self.DT)
        self.assertIsNotNone(cell)
        assert cell is not None
        self.assertEqual(cell.work_count, 3)
        # 준비중 + 동일 mid 라도 work_items 3건 (캘린더 일정 필터)
        self.assertEqual(len(cell.work_items), 3)

    def test_explicit_delete_only_target(self) -> None:
        self.svc.upsert_works(
            "OR001",
            self.DT,
            WorkLogWorksUpsertRequest(
                works=[
                    WorkLogWorkUpsertItem(work_mid_cd="WK010200", rmk="A"),
                ]
            ),
            user_id="T1",
        )
        self.svc.upsert_works(
            "OR001",
            self.DT,
            WorkLogWorksUpsertRequest(
                works=[WorkLogWorkUpsertItem(work_mid_cd="WK010300", rmk="B")]
            ),
            user_id="T1",
        )
        daily = self.svc.get_daily("OR001", self.DT)
        a_id = next(w.work_id for w in daily.works if w.rmk == "A")
        b_id = next(w.work_id for w in daily.works if w.rmk == "B")
        self.svc.delete_work("OR001", a_id, user_id="T1")
        daily2 = self.svc.get_daily("OR001", self.DT)
        self.assertEqual([w.work_id for w in daily2.works], [b_id])


if __name__ == "__main__":
    unittest.main()
