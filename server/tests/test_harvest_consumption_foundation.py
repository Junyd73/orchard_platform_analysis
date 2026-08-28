# -*- coding: utf-8 -*-
"""DEC-035-A — t_harvest_consumption schema · guard · work-log protection."""

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

from core.db_manager import DBManager  # noqa: E402
from core.harvest_consumption_guard import (  # noqa: E402
    assert_harvest_work_deletable,
    get_valid_consumed_qty,
    harvest_consumption_table_exists,
    validate_harvest_work_update,
)
from core.harvest_consumption_schema import (  # noqa: E402
    INDEX_CONFIRM,
    INDEX_WORK_VALID,
    TABLE_HARVEST_CONSUMPTION,
    ensure_harvest_consumption_schema,
)
from core.work_log_integrated_save_service import (  # noqa: E402
    MasterDto,
    WorkDetailDto,
    WorkLogIntegratedSaveService,
    WorkLogSaveError,
    WorkLogSavePayload,
)

FARM = "OR001"
VARIETY = "FR010101"
VARIETY2 = "FR010102"
HARVEST_MID = "WK010300"
OTHER_MID = "WK010100"
WORK_ID = "20260820-01"
CONFIRM_ID = "PRD20260828-001"


def _build_db() -> tuple[sqlite3.Connection, Path]:
    fd, path_s = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    path = Path(path_s)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.executescript(
        f"""
        CREATE TABLE m_common_code (
            farm_cd TEXT, code_cd TEXT, code_nm TEXT, parent_cd TEXT
        );
        INSERT INTO m_common_code VALUES
          ('{FARM}','{OTHER_MID}','전정','WK01'),
          ('{FARM}','{HARVEST_MID}','수확','WK01'),
          ('{FARM}','{VARIETY}','신고','FR010100'),
          ('{FARM}','{VARIETY2}','배','FR010100'),
          ('{FARM}','WO010100','준비중','WO01');

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
            variety_cd TEXT, harvest_container_qty INTEGER,
            reg_id TEXT, reg_dt TEXT, mod_id TEXT, mod_dt TEXT, rmk TEXT
        );
        CREATE TABLE t_work_resource (
            res_id INTEGER PRIMARY KEY AUTOINCREMENT,
            work_id TEXT, farm_cd TEXT
        );
        CREATE TABLE t_work_expense (
            exp_id INTEGER PRIMARY KEY AUTOINCREMENT,
            work_id TEXT, farm_cd TEXT
        );
        CREATE TABLE t_pesticide_use (
            use_id INTEGER PRIMARY KEY AUTOINCREMENT,
            farm_cd TEXT, work_id TEXT,
            stock_applied_yn TEXT, use_yn TEXT, cancel_yn TEXT
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

    def fetch_all(self, query, params=()):
        cur = self.conn.cursor()
        cur.execute(query, params)
        return cur.fetchall()


def _insert_harvest(
    conn: sqlite3.Connection,
    *,
    work_dt: str = "2026-08-20",
    qty: int = 30,
    variety: str = VARIETY,
    work_id: str = WORK_ID,
) -> None:
    conn.execute(
        """
        INSERT INTO t_work_detail (
            work_id, work_dt, farm_cd, work_main_cd, work_mid_cd,
            variety_cd, harvest_container_qty, status_cd, reg_id
        ) VALUES (?, ?, ?, 'WK01', ?, ?, ?, 'WO010100', 'T1')
        """,
        (work_id, work_dt, FARM, HARVEST_MID, variety, qty),
    )
    conn.commit()


def _insert_consumption(
    conn: sqlite3.Connection,
    *,
    work_id: str = WORK_ID,
    qty: int = 20,
    is_valid: int = 1,
    confirm_id: str = CONFIRM_ID,
) -> None:
    ensure_harvest_consumption_schema(conn)
    conn.commit()
    conn.execute(
        f"""
        INSERT INTO {TABLE_HARVEST_CONSUMPTION} (
            farm_cd, prod_confirm_id, harvest_work_id,
            consumed_container_qty, is_valid, reg_id, reg_dt
        ) VALUES (?, ?, ?, ?, ?, 'T1', datetime('now'))
        """,
        (FARM, confirm_id, work_id, qty, is_valid),
    )
    conn.commit()


def _harvest_payload(
    work_dt: str,
    qty: int,
    *,
    variety: str = VARIETY,
    work_id: str = WORK_ID,
) -> WorkLogSavePayload:
    return WorkLogSavePayload(
        master=MasterDto(work_dt=work_dt, day_of_week="수"),
        works=[
            WorkDetailDto(
                work_id=work_id,
                work_mid_cd=HARVEST_MID,
                variety_cd=variety,
                harvest_container_qty=qty,
                status_cd="WO010100",
            )
        ],
    )


class HarvestConsumptionSchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.conn, self.path = _build_db()

    def tearDown(self) -> None:
        self.conn.close()
        self.path.unlink(missing_ok=True)

    def test_schema_create_idempotent(self) -> None:
        stats1 = ensure_harvest_consumption_schema(self.conn)
        self.conn.commit()
        stats2 = ensure_harvest_consumption_schema(self.conn)
        self.conn.commit()
        self.assertTrue(stats1["ok"])
        self.assertTrue(stats2["ok"])
        self.assertTrue(harvest_consumption_table_exists(self.conn))

    def test_schema_columns_and_indexes(self) -> None:
        ensure_harvest_consumption_schema(self.conn)
        self.conn.commit()
        cols = {
            str(r[1]).lower()
            for r in self.conn.execute(f"PRAGMA table_info({TABLE_HARVEST_CONSUMPTION})")
        }
        for name in (
            "consumption_seq",
            "farm_cd",
            "prod_confirm_id",
            "harvest_work_id",
            "consumed_container_qty",
            "is_valid",
            "reg_id",
            "reg_dt",
        ):
            self.assertIn(name, cols)
        indexes = {
            str(r[0])
            for r in self.conn.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type='index' AND name NOT LIKE 'sqlite_%'
                """
            )
        }
        self.assertIn(INDEX_WORK_VALID, indexes)
        self.assertIn(INDEX_CONFIRM, indexes)

    def test_check_constraints(self) -> None:
        ensure_harvest_consumption_schema(self.conn)
        self.conn.commit()
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                f"""
                INSERT INTO {TABLE_HARVEST_CONSUMPTION} (
                    farm_cd, prod_confirm_id, harvest_work_id,
                    consumed_container_qty, is_valid, reg_dt
                ) VALUES (?, ?, ?, 0, 1, datetime('now'))
                """,
                (FARM, CONFIRM_ID, WORK_ID),
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                f"""
                INSERT INTO {TABLE_HARVEST_CONSUMPTION} (
                    farm_cd, prod_confirm_id, harvest_work_id,
                    consumed_container_qty, is_valid, reg_dt
                ) VALUES (?, ?, ?, 5, 2, datetime('now'))
                """,
                (FARM, CONFIRM_ID, WORK_ID),
            )

    def test_sum_excludes_invalid(self) -> None:
        ensure_harvest_consumption_schema(self.conn)
        _insert_consumption(self.conn, qty=12, is_valid=1)
        _insert_consumption(
            self.conn,
            qty=8,
            is_valid=0,
            confirm_id="PRD20260828-002",
        )
        total = get_valid_consumed_qty(self.conn, FARM, WORK_ID)
        self.assertEqual(total, 12)

    def test_sum_zero_when_table_missing(self) -> None:
        self.assertFalse(harvest_consumption_table_exists(self.conn))
        self.assertEqual(get_valid_consumed_qty(self.conn, FARM, WORK_ID), 0)


class HarvestConsumptionGuardUpdateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.conn, self.path = _build_db()
        _insert_harvest(self.conn, qty=30)
        _insert_consumption(self.conn, qty=20)
        self.svc = WorkLogIntegratedSaveService(_DbShim(self.conn), FARM)

    def tearDown(self) -> None:
        self.conn.close()
        self.path.unlink(missing_ok=True)

    def _save_basic(self, payload: WorkLogSavePayload) -> None:
        self.svc.save_work_log_basic("T1", payload)

    def test_qty_19_fails(self) -> None:
        with self.assertRaises(WorkLogSaveError) as ctx:
            self._save_basic(_harvest_payload("2026-08-20", 19))
        self.assertEqual(ctx.exception.code, "HARVEST_CONSUMED_QTY")

    def test_qty_20_25_40_ok(self) -> None:
        for qty in (20, 25, 40):
            with self.subTest(qty=qty):
                self._save_basic(_harvest_payload("2026-08-20", qty))
                row = self.conn.execute(
                    "SELECT harvest_container_qty FROM t_work_detail WHERE work_id=?",
                    (WORK_ID,),
                ).fetchone()
                self.assertEqual(int(row[0]), qty)

    def test_variety_change_fails(self) -> None:
        with self.assertRaises(WorkLogSaveError) as ctx:
            self._save_basic(
                _harvest_payload("2026-08-20", 30, variety=VARIETY2)
            )
        self.assertEqual(ctx.exception.code, "HARVEST_CONSUMED_VARIETY")

    def test_same_variety_ok(self) -> None:
        self._save_basic(_harvest_payload("2026-08-20", 30, variety=VARIETY))

    def test_year_change_fails(self) -> None:
        with self.assertRaises(WorkLogSaveError) as ctx:
            self._save_basic(_harvest_payload("2025-08-20", 30))
        self.assertEqual(ctx.exception.code, "HARVEST_CONSUMED_YEAR")

    def test_same_year_date_change_ok(self) -> None:
        self._save_basic(_harvest_payload("2026-08-21", 30))

    def test_no_consumption_allows_reduce(self) -> None:
        self.conn.execute(
            f"DELETE FROM {TABLE_HARVEST_CONSUMPTION} WHERE harvest_work_id=?",
            (WORK_ID,),
        )
        self.conn.commit()
        self._save_basic(_harvest_payload("2026-08-20", 10))
        row = self.conn.execute(
            "SELECT harvest_container_qty FROM t_work_detail WHERE work_id=?",
            (WORK_ID,),
        ).fetchone()
        self.assertEqual(int(row[0]), 10)

    def test_guard_failure_rolls_back_master_in_same_tx(self) -> None:
        payload = _harvest_payload("2026-08-20", 19)
        payload.master.work_rmk = "tx-rollback-marker"
        with self.assertRaises(WorkLogSaveError):
            self.svc.save_work_log_basic("T1", payload)
        master = self.conn.execute(
            "SELECT work_rmk FROM t_work_master WHERE farm_cd=? AND work_dt=?",
            (FARM, "2026-08-20"),
        ).fetchone()
        self.assertIsNone(master)
        qty = self.conn.execute(
            "SELECT harvest_container_qty FROM t_work_detail WHERE work_id=?",
            (WORK_ID,),
        ).fetchone()[0]
        self.assertEqual(int(qty), 30)


class HarvestConsumptionGuardDeleteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.conn, self.path = _build_db()
        self.svc = WorkLogIntegratedSaveService(_DbShim(self.conn), FARM)
        self.work_dt = "2026-08-20"

    def tearDown(self) -> None:
        self.conn.close()
        self.path.unlink(missing_ok=True)

    def test_deletable_guard_blocks_with_consumption(self) -> None:
        _insert_harvest(self.conn, work_dt=self.work_dt)
        _insert_consumption(self.conn)
        with self.assertRaises(WorkLogSaveError) as ctx:
            assert_harvest_work_deletable(self.conn.cursor(), FARM, WORK_ID)
        self.assertEqual(ctx.exception.code, "HARVEST_CONSUMED_BLOCK")

    def test_purge_ok_without_consumption(self) -> None:
        _insert_harvest(self.conn, work_dt=self.work_dt)
        cur = self.conn.cursor()
        assert_harvest_work_deletable(cur, FARM, WORK_ID)
        self.conn.execute(
            "DELETE FROM t_work_detail WHERE farm_cd=? AND work_id=?",
            (FARM, WORK_ID),
        )
        self.conn.commit()
        row = self.conn.execute(
            "SELECT 1 FROM t_work_detail WHERE work_id=?",
            (WORK_ID,),
        ).fetchone()
        self.assertIsNone(row)

    def test_sync_missing_delete_blocked(self) -> None:
        other_id = "20260820-02"
        _insert_harvest(self.conn, work_dt=self.work_dt, work_id=WORK_ID)
        _insert_harvest(
            self.conn,
            work_dt=self.work_dt,
            work_id=other_id,
            qty=10,
        )
        _insert_consumption(self.conn, work_id=WORK_ID)
        payload = WorkLogSavePayload(
            master=MasterDto(work_dt=self.work_dt, day_of_week="수"),
            works=[
                WorkDetailDto(
                    work_id=other_id,
                    work_mid_cd=HARVEST_MID,
                    variety_cd=VARIETY,
                    harvest_container_qty=10,
                    status_cd="WO010100",
                )
            ],
        )
        with self.assertRaises(WorkLogSaveError) as ctx:
            self.svc._save_core(
                "T1",
                payload,
                include_finance_and_pest=False,
                sync_delete_missing=True,
            )
        self.assertEqual(ctx.exception.code, "HARVEST_CONSUMED_BLOCK")
        self.assertIsNotNone(
            self.conn.execute(
                "SELECT 1 FROM t_work_detail WHERE work_id=?",
                (WORK_ID,),
            ).fetchone()
        )

    def test_bulk_date_delete_blocked(self) -> None:
        _insert_harvest(self.conn, work_dt=self.work_dt)
        _insert_consumption(self.conn)
        payload = WorkLogSavePayload(
            master=MasterDto(work_dt=self.work_dt, day_of_week="수"),
            works=[],
        )
        with self.assertRaises(WorkLogSaveError) as ctx:
            self.svc._save_core(
                "T1",
                payload,
                include_finance_and_pest=False,
                sync_delete_missing=True,
            )
        self.assertEqual(ctx.exception.code, "HARVEST_CONSUMED_BLOCK")

    def test_delete_rollback_leaves_related_rows(self) -> None:
        _insert_harvest(self.conn, work_dt=self.work_dt)
        _insert_consumption(self.conn)
        self.conn.execute(
            "INSERT INTO t_work_resource (work_id, farm_cd) VALUES (?, ?)",
            (WORK_ID, FARM),
        )
        self.conn.commit()
        before = self.conn.execute(
            "SELECT COUNT(*) FROM t_work_resource WHERE work_id=?",
            (WORK_ID,),
        ).fetchone()[0]
        with self.assertRaises(WorkLogSaveError):
            assert_harvest_work_deletable(self.conn.cursor(), FARM, WORK_ID)
        after = self.conn.execute(
            "SELECT COUNT(*) FROM t_work_resource WHERE work_id=?",
            (WORK_ID,),
        ).fetchone()[0]
        self.assertEqual(int(before), int(after))


class HarvestConsumptionLegacyDbManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.conn, self.path = _build_db()
        _insert_harvest(self.conn, qty=30)
        _insert_consumption(self.conn, qty=20)
        self.db = DBManager.__new__(DBManager)
        self.db.conn = self.conn

    def tearDown(self) -> None:
        self.conn.close()
        self.path.unlink(missing_ok=True)

    def test_save_work_details_blocks_qty_below_consumed(self) -> None:
        ok = self.db.save_work_details(
            "2026-08-20",
            FARM,
            [
                {
                    "mid_cd": HARVEST_MID,
                    "loc_id": None,
                    "start_tm": "09:00",
                    "end_tm": "10:00",
                    "status": "WO010100",
                    "variety_cd": VARIETY,
                    "harvest_container_qty": 19,
                }
            ],
            "T1",
        )
        self.assertFalse(ok)
        row = self.conn.execute(
            "SELECT harvest_container_qty FROM t_work_detail WHERE work_id=?",
            (WORK_ID,),
        ).fetchone()
        self.assertEqual(int(row[0]), 30)


if __name__ == "__main__":
    unittest.main()
