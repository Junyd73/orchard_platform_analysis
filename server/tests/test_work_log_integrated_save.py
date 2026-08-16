# -*- coding: utf-8 -*-
"""영농일지 통합 저장 — 농약 cancel_yn·멱등·교체 TX·Ledger 보완 테스트."""

from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from core.pesticide_manager import PesticideManager  # noqa: E402
from core.work_log_integrated_save_service import (  # noqa: E402
    ExpenseRowDto,
    LaborRowDto,
    MasterDto,
    PesticideLineDto,
    PesticideReplacePayload,
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
        CREATE TABLE m_partner (
            farm_cd TEXT, pt_id TEXT, pt_nm TEXT, worker_type_cd TEXT
        );
        CREATE TABLE m_pesticide_item (
            item_id INTEGER PRIMARY KEY, farm_cd TEXT, item_nm TEXT,
            qty_piece INTEGER, use_yn TEXT DEFAULT 'Y',
            pest_category_nm TEXT DEFAULT '',
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
        "INSERT INTO m_partner(farm_cd, pt_id, pt_nm, worker_type_cd) VALUES (?,?,?,?)",
        ("OR001", "E1", "홍길동", "EMP"),
    )
    cur.execute(
        "INSERT INTO m_pesticide_item(item_id, farm_cd, item_nm, qty_piece, use_yn) VALUES (1,'OR001','테스트약',100,'Y')"
    )
    cur.execute(
        "INSERT INTO m_pesticide_item(item_id, farm_cd, item_nm, qty_piece, use_yn) VALUES (2,'OR001','보조약',50,'Y')"
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


class TestWorkLogIntegratedSave(unittest.TestCase):
    def setUp(self):
        self.conn, self.path = _make_db()
        self.db = _DbShim(self.conn)
        self.svc = WorkLogIntegratedSaveService(self.db, "OR001")
        self.work_dt = "2026-07-18"
        self.work_id = "20260718-01"

    def tearDown(self):
        self.conn.close()
        try:
            self.path.unlink(missing_ok=True)
        except OSError:
            pass

    def _qty(self, item_id: int = 1) -> int:
        return int(
            self.db.execute_query(
                "SELECT qty_piece FROM m_pesticide_item WHERE item_id=?",
                (item_id,),
            )[0][0]
        )

    def _use_row(self, use_id: int | None = None):
        if use_id is None:
            rows = self.db.execute_query(
                """
                SELECT use_id, stock_applied_yn, cancel_yn
                FROM t_pesticide_use WHERE work_id=? ORDER BY use_id DESC LIMIT 1
                """,
                (self.work_id,),
            )
        else:
            rows = self.db.execute_query(
                """
                SELECT use_id, stock_applied_yn, cancel_yn
                FROM t_pesticide_use WHERE use_id=?
                """,
                (use_id,),
            )
        return rows[0] if rows else None

    def _base_payload(self, **kwargs) -> WorkLogSavePayload:
        works = kwargs.pop("works", None)
        if works is None:
            works = [
                WorkDetailDto(
                    work_id=self.work_id,
                    work_mid_cd="WK010200",
                    work_mid_nm="방제",
                    pesticide_lines=kwargs.pop("pest_lines", []),
                    replace_pesticide_use_id=kwargs.pop(
                        "replace_pesticide_use_id", None
                    ),
                )
            ]
        else:
            kwargs.pop("pest_lines", None)
            kwargs.pop("replace_pesticide_use_id", None)
        return WorkLogSavePayload(
            master=MasterDto(work_dt=self.work_dt, day_of_week="토"),
            works=works,
            labor_work_id=kwargs.pop("labor_work_id", self.work_id),
            expense_work_id=kwargs.pop("expense_work_id", self.work_id),
            labor_rows=kwargs.pop("labor_rows", []),
            expense_rows=kwargs.pop("expense_rows", []),
            worker_nm="tester",
            worker_id="tester",
        )

    def _save_pest(self, qty: int = 3) -> int:
        self.svc.save_integrated(
            "tester",
            self._base_payload(
                pest_lines=[
                    PesticideLineDto(
                        item_id=1, use_qty=qty, item_nm_snapshot="테스트약"
                    )
                ]
            ),
        )
        row = self._use_row()
        assert row is not None
        return int(row[0])

    # 1·2: 신규 확정 + 재전송 멱등
    def test_01_02_pesticide_save_and_idempotent_resave(self):
        self._save_pest(3)
        self.assertEqual(self._qty(), 97)
        row = self._use_row()
        self.assertEqual(str(row[1]), "Y")
        self.assertEqual(str(row[2]), "N")
        self.svc.save_integrated(
            "tester",
            self._base_payload(
                pest_lines=[
                    PesticideLineDto(
                        item_id=1, use_qty=3, item_nm_snapshot="테스트약"
                    )
                ]
            ),
        )
        self.assertEqual(self._qty(), 97)

    # 3·4: 취소 + 재취소
    def test_03_04_cancel_and_recancel_idempotent(self):
        use_id = self._save_pest(5)
        self.assertEqual(self._qty(), 95)
        r1 = self.svc.cancel_pesticide_use("tester", use_id=use_id)
        self.assertTrue(r1.ok)
        self.assertEqual(self._qty(), 100)
        row = self._use_row(use_id)
        self.assertEqual(str(row[1]), "N")
        self.assertEqual(str(row[2]), "Y")
        r2 = self.svc.cancel_pesticide_use("tester", use_id=use_id)
        self.assertFalse(r2.ok)
        self.assertEqual(self._qty(), 100)

    # 5: 확정 농약 수정 저장 (복원+신규차감)
    def test_05_replace_restores_and_redebits(self):
        use_id = self._save_pest(5)
        self.assertEqual(self._qty(), 95)
        result = self.svc.replace_pesticide_use(
            "tester",
            use_id,
            PesticideReplacePayload(
                use_dt=self.work_dt,
                work_id=self.work_id,
                worker_nm="tester",
                worker_id="tester",
                work_type_nm="방제",
                lines=[
                    PesticideLineDto(
                        item_id=1, use_qty=2, item_nm_snapshot="테스트약"
                    )
                ],
            ),
        )
        self.assertTrue(result.ok)
        self.assertEqual(self._qty(), 98)  # 100-2
        old = self._use_row(use_id)
        self.assertEqual(str(old[2]), "Y")
        active = self.db.execute_query(
            """
            SELECT stock_applied_yn, cancel_yn FROM t_pesticide_use
            WHERE work_id=? AND IFNULL(cancel_yn,'N')!='Y'
            """,
            (self.work_id,),
        )
        self.assertEqual(len(active), 1)
        self.assertEqual(str(active[0][0]), "Y")

    # 6: 수정 화면 진입만으로는 DB/재고 변경 없음 (서비스 미호출 계약)
    def test_06_edit_begin_without_save_no_db_change(self):
        use_id = self._save_pest(4)
        qty_before = self._qty()
        row_before = self._use_row(use_id)
        # UI edit begin = 로컬 플래그만. Core 미호출.
        self.assertEqual(self._qty(), qty_before)
        row_after = self._use_row(use_id)
        self.assertEqual(row_before[1], row_after[1])
        self.assertEqual(row_before[2], row_after[2])

    # 7: 수정 저장 중 실패 → 전체 rollback
    def test_07_replace_failure_rolls_back(self):
        use_id = self._save_pest(5)
        qty_before = self._qty()

        real_save = PesticideManager.save_and_apply_use_on_cursor

        def _boom(self, *args, **kwargs):
            raise WorkLogSaveError("의도적 실패", code="TEST_FAIL")

        with patch.object(PesticideManager, "save_and_apply_use_on_cursor", _boom):
            result = self.svc.replace_pesticide_use(
                "tester",
                use_id,
                PesticideReplacePayload(
                    use_dt=self.work_dt,
                    work_id=self.work_id,
                    lines=[
                        PesticideLineDto(
                            item_id=1, use_qty=1, item_nm_snapshot="테스트약"
                        )
                    ],
                ),
            )
        self.assertFalse(result.ok)
        self.assertEqual(self._qty(), qty_before)
        row = self._use_row(use_id)
        self.assertEqual(str(row[1]), "Y")
        self.assertEqual(str(row[2]), "N")
        # 원본 메서드 복원 확인용 참조 유지
        self.assertTrue(callable(real_save))

    # 8: 작업 전체 농약 취소 — 전건 또는 rollback
    def test_08_cancel_all_for_work(self):
        use_id = self._save_pest(3)
        # 동일 work에 두 번째 사용문서 수동 추가
        pest = PesticideManager(self.db)
        with self.db.transaction() as cur:
            uid2, errs = pest.save_and_apply_use_on_cursor(
                cur,
                "OR001",
                "tester",
                None,
                self.work_dt,
                None,
                "tester",
                "tester",
                "방제",
                "test",
                [{"item_id": 2, "use_qty": 5, "item_nm_snapshot": "보조약"}],
                work_id=self.work_id,
            )
            self.assertIsNotNone(uid2)
            self.assertFalse(errs)
        self.assertEqual(self._qty(1), 97)
        self.assertEqual(self._qty(2), 45)

        result = self.svc.cancel_all_pesticide_uses_for_work("tester", self.work_id)
        self.assertTrue(result.ok)
        self.assertEqual(self._qty(1), 100)
        self.assertEqual(self._qty(2), 50)
        # 재호출: 대상 없음 → 성공(멱등)
        result2 = self.svc.cancel_all_pesticide_uses_for_work("tester", self.work_id)
        self.assertTrue(result2.ok)
        self.assertEqual(self._qty(1), 100)

        # rollback: 두 건 중 두 번째 실패 시 전체 유지
        self._save_pest(2)
        with self.db.transaction() as cur:
            pest.save_and_apply_use_on_cursor(
                cur,
                "OR001",
                "tester",
                None,
                self.work_dt,
                None,
                "tester",
                "tester",
                "방제",
                "test",
                [{"item_id": 2, "use_qty": 3, "item_nm_snapshot": "보조약"}],
                work_id=self.work_id,
            )
        qty1, qty2 = self._qty(1), self._qty(2)
        calls = {"n": 0}
        real_cancel = PesticideManager.cancel_use_restore_stock_on_cursor

        def _cancel_fail_second(self_pm, cur, farm_cd, user_id, uid, **kw):
            calls["n"] += 1
            if calls["n"] >= 2:
                return False, ["의도적 취소 실패"]
            return real_cancel(self_pm, cur, farm_cd, user_id, uid, **kw)

        with patch.object(
            PesticideManager, "cancel_use_restore_stock_on_cursor", _cancel_fail_second
        ):
            bad = self.svc.cancel_all_pesticide_uses_for_work("tester", self.work_id)
        self.assertFalse(bad.ok)
        self.assertEqual(self._qty(1), qty1)
        self.assertEqual(self._qty(2), qty2)
        _ = use_id  # silence lint

    # 9·10·11: pay_status Ledger / 멱등
    def test_09_10_11_ledger_pay_status_and_idempotent(self):
        payload = self._base_payload(
            expense_rows=[
                ExpenseRowDto(
                    status="INS",
                    acct_cd="EX020201",
                    item_nm="자재",
                    amt=10000,
                    pay_method_cd="AS010101",
                    pay_status="Y",
                ),
                ExpenseRowDto(
                    status="INS",
                    acct_cd="EX020202",
                    item_nm="미지급",
                    amt=5000,
                    pay_method_cd="AS010101",
                    pay_status="N",
                ),
            ]
        )
        self.svc.save_integrated("tester", payload)
        slips = self.db.execute_query(
            "SELECT acct_cd, trans_amt FROM t_ledger WHERE farm_cd=? AND trans_st='10'",
            ("OR001",),
        )
        self.assertEqual(len(slips), 1)
        self.assertEqual(slips[0][0], "EX020201")

        # 동일 경비 ORG 재저장 → 중복 없음
        exp = self.db.execute_query(
            "SELECT exp_id, slip_no FROM t_work_expense WHERE work_id=? AND acct_cd=?",
            (self.work_id, "EX020201"),
        )
        eid = int(exp[0][0])
        payload2 = self._base_payload(
            expense_rows=[
                ExpenseRowDto(
                    status="ORG",
                    exp_id=eid,
                    acct_cd="EX020201",
                    item_nm="자재",
                    amt=10000,
                    pay_method_cd="AS010101",
                    pay_status="Y",
                    orig_data={"exp_id": eid, "slip_no": exp[0][1]},
                ),
                ExpenseRowDto(
                    status="ORG",
                    acct_cd="EX020202",
                    item_nm="미지급",
                    amt=5000,
                    pay_method_cd="AS010101",
                    pay_status="N",
                ),
            ]
        )
        # 두 번째 경비도 ORG로
        exp2 = self.db.execute_query(
            "SELECT exp_id FROM t_work_expense WHERE work_id=? AND acct_cd=?",
            (self.work_id, "EX020202"),
        )
        payload2.expense_rows[1].exp_id = int(exp2[0][0])
        payload2.expense_rows[1].status = "ORG"
        self.svc.save_integrated("tester", payload2)
        active = self.db.execute_query(
            "SELECT COUNT(*) FROM t_ledger WHERE farm_cd=? AND trans_st='10'",
            ("OR001",),
        )
        self.assertEqual(int(active[0][0]), 1)

    # 12: 동일 payload → 동일 결과 (Core 단일 경로)
    def test_12_same_payload_same_db(self):
        p = self._base_payload(
            pest_lines=[
                PesticideLineDto(item_id=1, use_qty=7, item_nm_snapshot="테스트약")
            ],
            labor_rows=[
                LaborRowDto(
                    status="INS",
                    emp_cd="E1",
                    emp_nm="홍길동",
                    man_hour=8,
                    daily_wage=80000,
                    pay_method_cd="AS010101",
                    pay_status="Y",
                )
            ],
        )
        self.svc.save_integrated("tester", p)
        snap = (
            self._qty(),
            int(
                self.db.execute_query(
                    "SELECT COUNT(*) FROM t_ledger WHERE farm_cd=? AND trans_st='10'",
                    ("OR001",),
                )[0][0]
            ),
            int(
                self.db.execute_query(
                    "SELECT COUNT(*) FROM t_pesticide_use WHERE work_id=? AND cancel_yn='N'",
                    (self.work_id,),
                )[0][0]
            ),
        )
        self.svc.save_integrated("tester", p)
        snap2 = (
            self._qty(),
            int(
                self.db.execute_query(
                    "SELECT COUNT(*) FROM t_ledger WHERE farm_cd=? AND trans_st='10'",
                    ("OR001",),
                )[0][0]
            ),
            int(
                self.db.execute_query(
                    "SELECT COUNT(*) FROM t_pesticide_use WHERE work_id=? AND cancel_yn='N'",
                    (self.work_id,),
                )[0][0]
            ),
        )
        self.assertEqual(snap, snap2)

    def test_basic_save_skips_pest_and_ledger(self):
        payload = self._base_payload(
            pest_lines=[
                PesticideLineDto(item_id=1, use_qty=3, item_nm_snapshot="테스트약")
            ],
            expense_rows=[
                ExpenseRowDto(
                    status="INS",
                    acct_cd="EX020201",
                    item_nm="자재",
                    amt=10000,
                    pay_method_cd="AS010101",
                    pay_status="Y",
                )
            ],
        )
        self.svc.save_work_log_basic("tester", payload)
        self.assertEqual(self._qty(), 100)
        slips = self.db.execute_query("SELECT COUNT(*) FROM t_ledger")
        self.assertEqual(int(slips[0][0]), 0)
        works = self.db.execute_query(
            "SELECT work_id FROM t_work_detail WHERE work_id=?",
            (self.work_id,),
        )
        self.assertEqual(len(works), 1)

    def test_integrated_replace_via_payload_flag(self):
        use_id = self._save_pest(5)
        self.svc.save_integrated(
            "tester",
            self._base_payload(
                pest_lines=[
                    PesticideLineDto(
                        item_id=1, use_qty=1, item_nm_snapshot="테스트약"
                    )
                ],
                replace_pesticide_use_id=use_id,
            ),
        )
        self.assertEqual(self._qty(), 99)
        old = self._use_row(use_id)
        self.assertEqual(str(old[2]), "Y")


if __name__ == "__main__":
    unittest.main()
