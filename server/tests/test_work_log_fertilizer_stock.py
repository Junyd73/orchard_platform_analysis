# -*- coding: utf-8 -*-
"""영농일지 비료(영양제) 재고 연동 — 농약 경로 재사용·카테고리 검증."""

from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from core.pesticide_manager import PEST_CATEGORY_NUTRIENT  # noqa: E402
from core.work_log_integrated_save_service import (  # noqa: E402
    MasterDto,
    PesticideLineDto,
    WorkDetailDto,
    WorkLogIntegratedSaveService,
    WorkLogSaveError,
    WorkLogSavePayload,
)


def _make_db() -> tuple[sqlite3.Connection, Path]:
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    path = Path(tmp.name)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE t_work_master (
            work_dt TEXT PRIMARY KEY,
            day_of_week TEXT, weather_cd TEXT,
            temp_max REAL, temp_min REAL, precip REAL, humidity REAL,
            sun_rise TEXT, sun_set TEXT, sunshine_hr REAL,
            wind_max REAL, wind_min REAL, work_rmk TEXT,
            farm_cd TEXT, reg_id TEXT, reg_dt TEXT, mod_id TEXT, mod_dt TEXT
        );
        CREATE TABLE t_work_detail (
            work_id TEXT PRIMARY KEY,
            work_dt TEXT, farm_cd TEXT, work_main_cd TEXT, work_mid_cd TEXT,
            work_loc_id TEXT, rmk TEXT, start_tm TEXT, end_tm TEXT, status_cd TEXT,
            reg_id TEXT, reg_dt TEXT, mod_id TEXT, mod_dt TEXT
        );
        CREATE TABLE t_work_resource (
            res_id INTEGER PRIMARY KEY AUTOINCREMENT,
            work_id TEXT, farm_cd TEXT, trans_dt TEXT, emp_cd TEXT,
            man_hour REAL, daily_wage REAL, meal_cost REAL, other_cost REAL,
            pay_method_cd TEXT, pay_status TEXT, slip_no TEXT,
            reg_id TEXT, reg_dt TEXT, mod_id TEXT, mod_dt TEXT
        );
        CREATE TABLE t_work_expense (
            exp_id INTEGER PRIMARY KEY AUTOINCREMENT,
            farm_cd TEXT, work_id TEXT, trans_dt TEXT, acct_cd TEXT, item_nm TEXT,
            qty REAL, unit_price REAL, total_amt REAL,
            pay_method_cd TEXT, pay_status TEXT, slip_no TEXT,
            reg_id TEXT, reg_dt TEXT, mod_id TEXT, mod_dt TEXT
        );
        CREATE TABLE t_ledger (
            slip_no TEXT PRIMARY KEY, farm_cd TEXT, trans_dt TEXT,
            trans_type_cd TEXT, acct_cd TEXT, trans_amt REAL, rmk TEXT,
            ref_id TEXT, parent_slip_no TEXT, trans_st TEXT,
            reg_id TEXT, reg_dt TEXT, mod_id TEXT, mod_dt TEXT
        );
        CREATE TABLE m_pesticide_item (
            item_id INTEGER PRIMARY KEY, farm_cd TEXT, item_nm TEXT,
            spec_nm TEXT, pest_category_nm TEXT DEFAULT '',
            qty_piece INTEGER, use_yn TEXT DEFAULT 'Y',
            mod_id TEXT, mod_dt TEXT
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
        """
    )
    cur.execute(
        """
        INSERT INTO m_pesticide_item(
            item_id, farm_cd, item_nm, pest_category_nm, qty_piece, use_yn
        ) VALUES (1,'OR001','살충A','살충제',10,'Y')
        """
    )
    cur.execute(
        """
        INSERT INTO m_pesticide_item(
            item_id, farm_cd, item_nm, pest_category_nm, qty_piece, use_yn
        ) VALUES (2,'OR001','영양B',?,20,'Y')
        """,
        (PEST_CATEGORY_NUTRIENT,),
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
        return self.execute_query(query, params)

    def transaction(self):
        @contextmanager
        def _ctx():
            prev = self.conn.isolation_level
            try:
                self.conn.isolation_level = None
                self.conn.row_factory = sqlite3.Row
                cur = self.conn.cursor()
                cur.execute("BEGIN IMMEDIATE")
                yield cur
                self.conn.commit()
            except Exception:
                try:
                    self.conn.rollback()
                except sqlite3.Error:
                    pass
                raise
            finally:
                self.conn.isolation_level = prev if prev is not None else ""

        return _ctx()


class TestWorkLogFertilizerStock(unittest.TestCase):
    def setUp(self):
        self.conn, self.path = _make_db()
        self.db = _DbShim(self.conn)
        self.svc = WorkLogIntegratedSaveService(self.db, "OR001")
        self.work_dt = "2026-08-10"

    def tearDown(self):
        self.conn.close()
        try:
            self.path.unlink(missing_ok=True)
        except OSError:
            pass

    def _qty(self, item_id: int) -> int:
        return int(
            self.db.execute_query(
                "SELECT qty_piece FROM m_pesticide_item WHERE item_id=?",
                (item_id,),
            )[0][0]
        )

    def _fert_payload(self, work_id: str, item_id: int, qty: int):
        return WorkLogSavePayload(
            master=MasterDto(work_dt=self.work_dt, day_of_week="월"),
            works=[
                WorkDetailDto(
                    work_id=work_id,
                    work_mid_cd="WK010800",
                    work_mid_nm="비료/영양제작업",
                    status_cd="WO010300",
                    pesticide_lines=[
                        PesticideLineDto(
                            item_id=item_id,
                            use_qty=qty,
                            item_nm_snapshot="영양B",
                        )
                    ],
                )
            ],
            labor_work_id=work_id,
            expense_work_id=work_id,
            worker_nm="tester",
            worker_id="tester",
        )

    def _pest_payload(self, work_id: str, item_id: int, qty: int):
        return WorkLogSavePayload(
            master=MasterDto(work_dt=self.work_dt, day_of_week="월"),
            works=[
                WorkDetailDto(
                    work_id=work_id,
                    work_mid_cd="WK010200",
                    work_mid_nm="방제살포",
                    status_cd="WO010300",
                    pesticide_lines=[
                        PesticideLineDto(
                            item_id=item_id,
                            use_qty=qty,
                            item_nm_snapshot="X",
                        )
                    ],
                )
            ],
            labor_work_id=work_id,
            expense_work_id=work_id,
            worker_nm="tester",
            worker_id="tester",
        )

    def test_fertilizer_deducts_nutrient_stock(self):
        before = self._qty(2)
        self.svc.save_integrated(
            "tester", self._fert_payload("20260810-F1", 2, 3)
        )
        self.assertEqual(self._qty(2), before - 3)
        use = self.db.execute_query(
            """
            SELECT use_id, stock_applied_yn, cancel_yn
            FROM t_pesticide_use WHERE work_id=?
            """,
            ("20260810-F1",),
        )
        self.assertEqual(len(use), 1)
        self.assertEqual(str(use[0][1]), "Y")
        self.assertEqual(str(use[0][2]), "N")

    def test_fertilizer_rejects_spray_item(self):
        with self.assertRaises(WorkLogSaveError) as ctx:
            self.svc.save_integrated(
                "tester", self._fert_payload("20260810-F2", 1, 1)
            )
        self.assertEqual(ctx.exception.code, "FERTILIZER_CATEGORY_MISMATCH")
        self.assertEqual(self._qty(1), 10)

    def test_pesticide_rejects_nutrient_item(self):
        with self.assertRaises(WorkLogSaveError) as ctx:
            self.svc.save_integrated(
                "tester", self._pest_payload("20260810-P1", 2, 1)
            )
        self.assertEqual(ctx.exception.code, "PESTICIDE_CATEGORY_MISMATCH")
        self.assertEqual(self._qty(2), 20)

    def test_pesticide_still_deducts_spray(self):
        self.svc.save_integrated(
            "tester", self._pest_payload("20260810-P2", 1, 2)
        )
        self.assertEqual(self._qty(1), 8)

    def test_cancel_restores_fertilizer_stock(self):
        self.svc.save_integrated(
            "tester", self._fert_payload("20260810-F3", 2, 4)
        )
        self.assertEqual(self._qty(2), 16)
        uid = int(
            self.db.execute_query(
                "SELECT use_id FROM t_pesticide_use WHERE work_id=?",
                ("20260810-F3",),
            )[0][0]
        )
        r = self.svc.cancel_pesticide_use("tester", use_id=uid)
        self.assertTrue(r.ok)
        self.assertEqual(self._qty(2), 20)

    def test_other_work_rejects_stock_lines(self):
        payload = WorkLogSavePayload(
            master=MasterDto(work_dt=self.work_dt, day_of_week="월"),
            works=[
                WorkDetailDto(
                    work_id="20260810-X1",
                    work_mid_cd="WK010400",
                    work_mid_nm="예초작업",
                    status_cd="WO010300",
                    pesticide_lines=[
                        PesticideLineDto(
                            item_id=1, use_qty=1, item_nm_snapshot="살충A"
                        )
                    ],
                )
            ],
            labor_work_id="20260810-X1",
            expense_work_id="20260810-X1",
            worker_nm="tester",
            worker_id="tester",
        )
        with self.assertRaises(WorkLogSaveError) as ctx:
            self.svc.save_integrated("tester", payload)
        self.assertEqual(ctx.exception.code, "STOCK_WORK_TYPE_MISMATCH")
        self.assertEqual(self._qty(1), 10)

    def test_fertilizer_ok_even_if_is_pesticide_flag_wrong(self):
        """회귀: API가 pest_lines 있으면 is_pesticide=True로 넣던 오인 방지."""
        payload = self._fert_payload("20260810-F5", 2, 2)
        payload.works[0].is_pesticide = True
        before = self._qty(2)
        self.svc.save_integrated("tester", payload)
        self.assertEqual(self._qty(2), before - 2)

    def test_purge_restores_fertilizer_stock(self):
        self.svc.save_integrated(
            "tester", self._fert_payload("20260810-F4", 2, 5)
        )
        self.assertEqual(self._qty(2), 15)
        self.svc.purge_work_related("tester", "20260810-F4", self.work_dt)
        self.assertEqual(self._qty(2), 20)
        use = self.db.execute_query(
            """
            SELECT cancel_yn, stock_applied_yn
            FROM t_pesticide_use WHERE work_id=?
            """,
            ("20260810-F4",),
        )
        self.assertEqual(str(use[0][0]), "Y")
        self.assertEqual(str(use[0][1]), "N")


class TestListPesticideItemsKind(unittest.TestCase):
    def test_kind_filter_sql_helpers(self):
        from core.pesticide_manager import (
            sql_item_is_nutrient,
            sql_item_not_nutrient,
        )

        self.assertIn("영양제", sql_item_is_nutrient("m"))
        self.assertIn("!=", sql_item_not_nutrient("m"))


if __name__ == "__main__":
    unittest.main()
