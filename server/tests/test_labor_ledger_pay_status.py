# -*- coding: utf-8 -*-
"""인건비 회계전표: pay_status + 금액 기준 (worker_type 무관).

비용집계(EMP/TEMP만)와 회계전표 정책은 분리 유지.
"""

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

from core.account_manager import AccountManager  # noqa: E402
from core.work_log_constants import LABOR_ACCT_CD  # noqa: E402
from core.work_log_integrated_save_service import (  # noqa: E402
    ExpenseRowDto,
    LaborRowDto,
    MasterDto,
    WorkDetailDto,
    WorkLogIntegratedSaveService,
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
        CREATE TABLE m_partner (
            pt_id INTEGER PRIMARY KEY,
            farm_cd TEXT, pt_nm TEXT, worker_type_cd TEXT,
            base_price REAL DEFAULT 0, use_yn TEXT DEFAULT 'Y'
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
        """
    )
    partners = [
        (1, "EMP", "고용1"),
        (2, "TEMP", "일용1"),
        (3, "OWNER", "농장주"),
        (4, "FAMILY", "가족1"),
    ]
    for pt_id, wtc, nm in partners:
        cur.execute(
            "INSERT INTO m_partner(pt_id, farm_cd, pt_nm, worker_type_cd) VALUES (?,?,?,?)",
            (pt_id, "OR001", nm, wtc),
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


class TestLaborLedgerPayStatus(unittest.TestCase):
    def setUp(self):
        AccountManager._shared_seq_cache.clear()
        self.conn, self.path = _make_db()
        self.db = _DbShim(self.conn)
        self.svc = WorkLogIntegratedSaveService(self.db, "OR001")
        self.work_dt = "2026-08-10"
        self.work_id = "20260810-04"

    def tearDown(self):
        self.conn.close()
        try:
            self.path.unlink(missing_ok=True)
        except OSError:
            pass

    def _payload(
        self,
        *,
        labor_rows=None,
        expense_rows=None,
        removed_res_ids=None,
        removed_exp_ids=None,
    ) -> WorkLogSavePayload:
        return WorkLogSavePayload(
            master=MasterDto(work_dt=self.work_dt, day_of_week="월"),
            works=[
                WorkDetailDto(
                    work_id=self.work_id,
                    work_mid_cd="WK010400",
                    work_mid_nm="예초작업",
                    status_cd="WO010300",
                    rmk="예초",
                )
            ],
            labor_work_id=self.work_id,
            expense_work_id=self.work_id,
            labor_rows=list(labor_rows or []),
            expense_rows=list(expense_rows or []),
            removed_res_ids=list(removed_res_ids or []),
            removed_exp_ids=list(removed_exp_ids or []),
            worker_nm="tester",
            worker_id="tester",
        )

    def _active_res_slips(self):
        return self.db.fetch_all(
            """
            SELECT slip_no, trans_amt, trans_st, ref_id, acct_cd
            FROM t_ledger
            WHERE ref_id LIKE ?
              AND trans_st = '10'
            ORDER BY slip_no
            """,
            (f"RES-{self.work_id}-%",),
        )

    def _active_exp_slips(self):
        return self.db.fetch_all(
            """
            SELECT slip_no, trans_amt, trans_st, ref_id, acct_cd
            FROM t_ledger
            WHERE ref_id LIKE ?
              AND trans_st = '10'
            ORDER BY slip_no
            """,
            (f"EXP-{self.work_id}-%",),
        )

    def _resource_rows(self):
        return self.db.fetch_all(
            "SELECT emp_cd, daily_wage, pay_status, slip_no FROM t_work_resource WHERE work_id=?",
            (self.work_id,),
        )

    def test_paid_all_worker_types_create_ledger(self):
        """EMP/TEMP/OWNER/FAMILY 지급(Y, 금액>0) → 전표 생성."""
        cases = [
            ("1", "EMP", 10000),
            ("2", "TEMP", 20000),
            ("3", "OWNER", 10000),
            ("4", "FAMILY", 15000),
        ]
        for emp_cd, wtc, wage in cases:
            with self.subTest(worker_type=wtc):
                AccountManager._shared_seq_cache.clear()
                self.tearDown()
                self.setUp()
                self.work_id = f"20260810-{emp_cd.zfill(2)}"
                self.svc.save_integrated(
                    "tester",
                    self._payload(
                        labor_rows=[
                            LaborRowDto(
                                status="INS",
                                emp_cd=emp_cd,
                                emp_nm=wtc,
                                man_hour=1.0,
                                daily_wage=float(wage),
                                pay_method_cd="AS010101",
                                pay_status="Y",
                            )
                        ]
                    ),
                )
                slips = self._active_res_slips()
                self.assertEqual(len(slips), 1, msg=f"{wtc} 전표 1건")
                self.assertEqual(float(slips[0][1]), -float(wage))
                self.assertEqual(
                    slips[0][3], f"RES-{self.work_id}-{LABOR_ACCT_CD}_AS010101"
                )
                res = self._resource_rows()
                self.assertEqual(len(res), 1)
                self.assertTrue(res[0][3], msg=f"{wtc} slip_no 연결")

    def test_unpaid_all_worker_types_no_ledger(self):
        """각 유형 미지급 → 전표 미생성."""
        for emp_cd, wtc in (("1", "EMP"), ("2", "TEMP"), ("3", "OWNER"), ("4", "FAMILY")):
            with self.subTest(worker_type=wtc):
                AccountManager._shared_seq_cache.clear()
                self.tearDown()
                self.setUp()
                self.work_id = f"20260811-{emp_cd.zfill(2)}"
                self.svc.save_integrated(
                    "tester",
                    self._payload(
                        labor_rows=[
                            LaborRowDto(
                                status="INS",
                                emp_cd=emp_cd,
                                emp_nm=wtc,
                                man_hour=1.0,
                                daily_wage=10000.0,
                                pay_method_cd="AS010101",
                                pay_status="N",
                            )
                        ]
                    ),
                )
                self.assertEqual(self._active_res_slips(), [])
                res = self._resource_rows()
                self.assertEqual(len(res), 1)
                self.assertIsNone(res[0][3])

    def test_zero_wage_paid_no_ledger(self):
        """pay_status=Y 이지만 0원 → 전표 미생성, slip_no 없음."""
        self.svc.save_integrated(
            "tester",
            self._payload(
                labor_rows=[
                    LaborRowDto(
                        status="INS",
                        emp_cd="3",
                        emp_nm="OWNER",
                        man_hour=1.0,
                        daily_wage=0.0,
                        pay_method_cd="AS010101",
                        pay_status="Y",
                    )
                ]
            ),
        )
        self.assertEqual(self._active_res_slips(), [])
        res = self._resource_rows()
        self.assertEqual(len(res), 1)
        self.assertEqual(float(res[0][1]), 0.0)
        self.assertIsNone(res[0][3])

    def test_zero_expense_paid_no_ledger(self):
        """경비 pay_status=Y + 0원 → 0원 전표 미생성."""
        self.svc.save_integrated(
            "tester",
            self._payload(
                expense_rows=[
                    ExpenseRowDto(
                        status="INS",
                        acct_cd="EX020201",
                        item_nm="점심10000",
                        amt=0.0,
                        pay_method_cd="AS010101",
                        pay_status="Y",
                    )
                ]
            ),
        )
        self.assertEqual(self._active_exp_slips(), [])
        exp = self.db.fetch_all(
            "SELECT total_amt, pay_status, slip_no FROM t_work_expense WHERE work_id=?",
            (self.work_id,),
        )
        self.assertEqual(len(exp), 1)
        self.assertEqual(float(exp[0][0]), 0.0)
        self.assertEqual(exp[0][1], "Y")
        self.assertIsNone(exp[0][2])

    def test_owner_paid_matches_aug10_policy(self):
        """2026-08-10 OWNER 10,000 지급 = 정상 전표 (역분개 대상 아님)."""
        self.svc.save_integrated(
            "tester",
            self._payload(
                labor_rows=[
                    LaborRowDto(
                        status="INS",
                        emp_cd="3",
                        emp_nm="김헌웅",
                        man_hour=1.0,
                        daily_wage=10000.0,
                        pay_method_cd="AS010101",
                        pay_status="Y",
                    )
                ]
            ),
        )
        slips = self._active_res_slips()
        self.assertEqual(len(slips), 1)
        self.assertEqual(float(slips[0][1]), -10000.0)
        self.assertEqual(slips[0][2], "10")

    def test_existing_paid_slip_stable_on_resave(self):
        """기존 정상 전표: 동일 payload 재저장 시 불필요 역분개 없음."""
        self.svc.save_integrated(
            "tester",
            self._payload(
                labor_rows=[
                    LaborRowDto(
                        status="INS",
                        emp_cd="1",
                        emp_nm="EMP",
                        man_hour=1.0,
                        daily_wage=80000.0,
                        pay_method_cd="AS010101",
                        pay_status="Y",
                    )
                ]
            ),
        )
        first = self._active_res_slips()
        self.assertEqual(len(first), 1)
        slip_no = first[0][0]
        res_id = self.db.fetch_all(
            "SELECT res_id FROM t_work_resource WHERE work_id=?", (self.work_id,)
        )[0][0]

        self.svc.save_integrated(
            "tester",
            self._payload(
                labor_rows=[
                    LaborRowDto(
                        status="ORG",
                        res_id=int(res_id),
                        emp_cd="1",
                        emp_nm="EMP",
                        man_hour=1.0,
                        daily_wage=80000.0,
                        pay_method_cd="AS010101",
                        pay_status="Y",
                        orig_data={
                            "res_id": int(res_id),
                            "slip_no": slip_no,
                            "pay_method_cd": "AS010101",
                            "pay_status": "Y",
                            "daily_wage": 80000,
                            "emp_cd": "1",
                            "acct_cd": LABOR_ACCT_CD,
                        },
                    )
                ]
            ),
        )
        second = self._active_res_slips()
        self.assertEqual(len(second), 1)
        self.assertEqual(second[0][0], slip_no)
        cancelled = self.db.fetch_all(
            "SELECT COUNT(*) FROM t_ledger WHERE ref_id LIKE ? AND trans_st IN ('80','90')",
            (f"RES-{self.work_id}-%",),
        )[0][0]
        self.assertEqual(cancelled, 0)

    def test_remove_labor_reverses_ledger(self):
        """인건비 삭제 시 기존 역분개 로직 정상."""
        self.svc.save_integrated(
            "tester",
            self._payload(
                labor_rows=[
                    LaborRowDto(
                        status="INS",
                        emp_cd="3",
                        emp_nm="OWNER",
                        man_hour=1.0,
                        daily_wage=10000.0,
                        pay_method_cd="AS010101",
                        pay_status="Y",
                    )
                ]
            ),
        )
        res_id = int(
            self.db.fetch_all(
                "SELECT res_id FROM t_work_resource WHERE work_id=?", (self.work_id,)
            )[0][0]
        )
        slip_no = self._active_res_slips()[0][0]

        self.svc.save_integrated(
            "tester",
            self._payload(labor_rows=[], removed_res_ids=[res_id]),
        )
        self.assertEqual(self._active_res_slips(), [])
        st = self.db.fetch_all(
            "SELECT trans_st FROM t_ledger WHERE slip_no=?", (slip_no,)
        )[0][0]
        self.assertEqual(st, "90")
        rev = self.db.fetch_all(
            "SELECT trans_st, trans_amt, parent_slip_no FROM t_ledger WHERE parent_slip_no=?",
            (slip_no,),
        )
        self.assertEqual(len(rev), 1)
        self.assertEqual(rev[0][0], "80")
        self.assertEqual(float(rev[0][1]), 10000.0)

    def test_cost_aggregation_still_excludes_owner_family(self):
        """비용집계 SQL은 EMP/TEMP만 — 회계 정책과 혼용하지 않음."""
        # PyQt6 없는 환경에서도 검증: 소스 상수·헬퍼 문자열 확인
        db_src = Path(_REPO, "core/db_manager.py").read_text(encoding="utf-8")
        self.assertIn(
            'PARTNER_WORKER_TYPES_IN_LABOR_TOTAL = ("EMP", "TEMP")',
            db_src,
        )
        self.assertIn("_partner_in_labor_total_sql", db_src)
        # 집계 헬퍼는 EMP/TEMP만 포함하고 OWNER/FAMILY는 넣지 않음
        helper_start = db_src.index("def _partner_in_labor_total_sql")
        helper_snip = db_src[helper_start : helper_start + 400]
        self.assertIn("PARTNER_WORKER_TYPES_IN_LABOR_TOTAL", helper_snip)
        self.assertNotIn("OWNER", helper_snip)
        self.assertNotIn("FAMILY", helper_snip)

        acct_src = Path(_REPO, "core/account_manager.py").read_text(encoding="utf-8")
        self.assertNotIn("IN ('EMP', 'TEMP')", acct_src)
        self.assertIn("worker_type과 무관", acct_src)


if __name__ == "__main__":
    unittest.main()
