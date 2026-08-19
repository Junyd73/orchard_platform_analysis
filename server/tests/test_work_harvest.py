# -*- coding: utf-8 -*-
"""영농일지 수확기록 — T-HARVEST-01~08."""

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
    WorkLogSaveError,
    WorkLogSavePayload,
)
from app.schemas.work_log import (  # noqa: E402
    WorkLogWorksUpsertRequest,
    WorkLogWorkUpsertItem,
)
from app.services.work_log_service import WorkLogService  # noqa: E402

FARM = "OR001"
VARIETY = "FR010101"
HARVEST_MID = "WK010300"
OTHER_MID = "WK010100"


def _build_db() -> tuple[sqlite3.Connection, Path]:
    fd, path_s = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    path = Path(path_s)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.executescript(
        f"""
        CREATE TABLE m_farm_info (
            farm_cd TEXT PRIMARY KEY, farm_nm TEXT,
            lat REAL, lon REAL, nx INTEGER, ny INTEGER
        );
        INSERT INTO m_farm_info VALUES ('{FARM}', '테스트농장', NULL, NULL, NULL, NULL);

        CREATE TABLE m_common_code (
            farm_cd TEXT, code_cd TEXT, code_nm TEXT, parent_cd TEXT
        );
        INSERT INTO m_common_code VALUES
          ('{FARM}','{OTHER_MID}','전정','WK01'),
          ('{FARM}','{HARVEST_MID}','수확','WK01'),
          ('{FARM}','{VARIETY}','신고','FR010100'),
          ('{FARM}','WO010300','완료','WO01');

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
            reg_id TEXT, reg_dt TEXT, mod_id TEXT, mod_dt TEXT, rmk TEXT
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
            use_id INTEGER PRIMARY KEY,
            farm_cd TEXT, work_id TEXT, stock_applied_yn TEXT,
            use_yn TEXT, cancel_yn TEXT
        );
        CREATE TABLE t_pesticide_use_line (
            use_line_id INTEGER PRIMARY KEY AUTOINCREMENT,
            use_id INTEGER, line_no INTEGER
        );
        CREATE TABLE t_stock_master (
            farm_cd TEXT, wh_cd TEXT, item_cd TEXT, variety_cd TEXT,
            grade_cd TEXT, size_cd TEXT, weight REAL, harvest_year INTEGER,
            storage_dt TEXT, in_qty REAL, out_qty REAL
        );
        CREATE TABLE t_stock_log (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            farm_cd TEXT, item_cd TEXT, variety_cd TEXT, harvest_year INTEGER,
            grade_cd TEXT, size_cd TEXT, weight REAL, io_type TEXT, qty REAL,
            remark TEXT, reg_id TEXT, reg_dt TEXT
        );
        """
    )
    conn.commit()
    return conn, path


class _DbShim:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def execute_query(self, query, params=()):
        cur = self.conn.cursor()
        cur.execute(query, params)
        return cur.fetchall()


def _stock_counts(conn: sqlite3.Connection) -> tuple[int, int]:
    m = conn.execute("SELECT COUNT(*) FROM t_stock_master").fetchone()[0]
    l = conn.execute("SELECT COUNT(*) FROM t_stock_log").fetchone()[0]
    return int(m), int(l)


def _detail_row(conn: sqlite3.Connection, work_id: str):
    return conn.execute(
        """
        SELECT work_mid_cd, variety_cd, harvest_container_qty
        FROM t_work_detail WHERE work_id = ?
        """,
        (work_id,),
    ).fetchone()


class TestWorkHarvestCore(unittest.TestCase):
    """Core save_work_log_basic — validation·NULL·재고 미연동."""

    def setUp(self) -> None:
        self.conn, self.db_path = _build_db()
        self.svc = WorkLogIntegratedSaveService(_DbShim(self.conn), FARM)
        self.work_dt = (date.today() - timedelta(days=1)).isoformat()
        self.digits = self.work_dt.replace("-", "")
        self.master = MasterDto(work_dt=self.work_dt, day_of_week="월")

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

    def test_harvest_01_non_harvest_ok(self) -> None:
        wid = f"{self.digits}-01"
        self._save([WorkDetailDto(work_id=wid, work_mid_cd=OTHER_MID, rmk="전정")])
        row = _detail_row(self.conn, wid)
        self.assertEqual(row["work_mid_cd"], OTHER_MID)
        self.assertIsNone(row["variety_cd"])
        self.assertIsNone(row["harvest_container_qty"])

    def test_harvest_02_save_harvest_125(self) -> None:
        wid = f"{self.digits}-01"
        self._save(
            [
                WorkDetailDto(
                    work_id=wid,
                    work_mid_cd=HARVEST_MID,
                    variety_cd=VARIETY,
                    harvest_container_qty=125,
                )
            ]
        )
        row = _detail_row(self.conn, wid)
        self.assertEqual(row["variety_cd"], VARIETY)
        self.assertEqual(int(row["harvest_container_qty"]), 125)

    def test_harvest_04_zero_or_negative_rejected(self) -> None:
        wid = f"{self.digits}-01"
        for qty in (0, -1):
            with self.subTest(qty=qty):
                with self.assertRaises(WorkLogSaveError):
                    self._save(
                        [
                            WorkDetailDto(
                                work_id=wid,
                                work_mid_cd=HARVEST_MID,
                                variety_cd=VARIETY,
                                harvest_container_qty=qty,
                            )
                        ]
                    )

    def test_harvest_05_missing_variety_rejected(self) -> None:
        with self.assertRaises(WorkLogSaveError):
            self._save(
                [
                    WorkDetailDto(
                        work_id=f"{self.digits}-01",
                        work_mid_cd=HARVEST_MID,
                        harvest_container_qty=10,
                    )
                ]
            )

    def test_harvest_06_harvest_to_other_clears_fields(self) -> None:
        wid = f"{self.digits}-01"
        self._save(
            [
                WorkDetailDto(
                    work_id=wid,
                    work_mid_cd=HARVEST_MID,
                    variety_cd=VARIETY,
                    harvest_container_qty=50,
                )
            ]
        )
        self._save([WorkDetailDto(work_id=wid, work_mid_cd=OTHER_MID, rmk="전정")])
        row = _detail_row(self.conn, wid)
        self.assertEqual(row["work_mid_cd"], OTHER_MID)
        self.assertIsNone(row["variety_cd"])
        self.assertIsNone(row["harvest_container_qty"])

    def test_harvest_07_other_to_harvest_requires_fields(self) -> None:
        wid = f"{self.digits}-01"
        self._save([WorkDetailDto(work_id=wid, work_mid_cd=OTHER_MID)])
        with self.assertRaises(WorkLogSaveError):
            self._save([WorkDetailDto(work_id=wid, work_mid_cd=HARVEST_MID)])

    def test_harvest_08_no_stock_change(self) -> None:
        self.conn.execute(
            """
            INSERT INTO t_stock_master (
                farm_cd, wh_cd, item_cd, variety_cd, grade_cd, size_cd,
                weight, harvest_year, storage_dt, in_qty, out_qty
            ) VALUES (?, 'WH01', 'RAW', ?, 'NONE', 'SZ01', 20.0, 2026, ?, 10, 0)
            """,
            (FARM, VARIETY, self.work_dt),
        )
        self.conn.execute(
            """
            INSERT INTO t_stock_log (
                farm_cd, item_cd, variety_cd, harvest_year, grade_cd, size_cd,
                weight, io_type, qty, remark, reg_id, reg_dt
            ) VALUES (?, 'RAW', ?, 2026, 'NONE', 'SZ01', 20.0, 'IN', 10, 'seed', 'T', 'now')
            """,
            (FARM, VARIETY),
        )
        self.conn.commit()
        before = _stock_counts(self.conn)
        self._save(
            [
                WorkDetailDto(
                    work_id=f"{self.digits}-01",
                    work_mid_cd=HARVEST_MID,
                    variety_cd=VARIETY,
                    harvest_container_qty=125,
                )
            ]
        )
        after = _stock_counts(self.conn)
        self.assertEqual(before, after)


class TestWorkHarvestApi(unittest.TestCase):
    """WorkLogService — 조회·upsert 경로."""

    def setUp(self) -> None:
        self.conn, self.db_path = _build_db()
        self.conn.close()
        self.svc = WorkLogService(db_path=self.db_path)
        self.work_dt = (date.today() - timedelta(days=2)).isoformat()
        self.digits = self.work_dt.replace("-", "")

    def tearDown(self) -> None:
        try:
            self.db_path.unlink(missing_ok=True)
        except OSError:
            pass

    def test_harvest_03_get_daily_restores(self) -> None:
        res = self.svc.upsert_works(
            FARM,
            self.work_dt,
            WorkLogWorksUpsertRequest(
                works=[
                    WorkLogWorkUpsertItem(
                        work_mid_cd=HARVEST_MID,
                        variety_cd=VARIETY,
                        harvest_container_qty=125,
                        status_cd="WO010300",
                    )
                ]
            ),
            user_id="T1",
        )
        wid = res.work_ids[0]
        daily = self.svc.get_daily(FARM, self.work_dt)
        w = next(x for x in daily.works if x.work_id == wid)
        self.assertEqual(w.variety_cd, VARIETY)
        self.assertEqual(w.harvest_container_qty, 125)
        self.assertTrue(w.variety_nm)


if __name__ == "__main__":
    unittest.main()
