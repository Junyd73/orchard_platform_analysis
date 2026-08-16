# -*- coding: utf-8 -*-
"""작업 삭제 cascade — 인력/경비 역분개·농약 복원·사진 soft."""

from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import unittest
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
for p in (_REPO, _REPO / "server"):
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)

from core.work_log_constants import PAY_STATUS_Y  # noqa: E402
from core.work_log_integrated_save_service import (  # noqa: E402
    ExpenseRowDto,
    LaborRowDto,
    MasterDto,
    PesticideLineDto,
    WorkDetailDto,
    WorkLogIntegratedSaveService,
    WorkLogSavePayload,
)
from app.services.work_log_service import WorkLogService  # noqa: E402


def _make_db() -> tuple[sqlite3.Connection, Path]:
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
        INSERT INTO m_farm_info VALUES ('OR001', '테스트', NULL, NULL, NULL, NULL);

        CREATE TABLE m_common_code (
            farm_cd TEXT, code_cd TEXT, code_nm TEXT, parent_cd TEXT
        );
        INSERT INTO m_common_code VALUES
          ('OR001','WK010200','방제','WK01'),
          ('OR001','WK010100','전정','WK01'),
          ('OR001','WK010800','비료/영양제','WK01'),
          ('OR001','WO010100','준비중','WO01'),
          ('OR001','WO010300','완료','WO01');

        CREATE TABLE m_farm_site (
            site_id TEXT PRIMARY KEY, farm_cd TEXT, site_nm TEXT
        );
        CREATE TABLE m_partner (
            farm_cd TEXT, pt_id TEXT, pt_nm TEXT, worker_type_cd TEXT
        );
        INSERT INTO m_partner VALUES ('OR001','E1','홍길동','EMP');

        CREATE TABLE m_account_code (
            acct_cd TEXT PRIMARY KEY, acct_nm TEXT, acct_level INTEGER, use_yn TEXT
        );
        INSERT INTO m_account_code VALUES ('AS010101','현금',4,'Y');
        INSERT INTO m_account_code VALUES ('EX010101','소모품',4,'Y');

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
            google_event_id TEXT, sync_status TEXT,
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
            pest_category_nm TEXT DEFAULT '',
            qty_piece INTEGER, use_yn TEXT DEFAULT 'Y',
            mod_id TEXT, mod_dt TEXT
        );
        INSERT INTO m_pesticide_item VALUES
          (1,'OR001','테스트약','살충제',100,'Y',NULL,NULL),
          (2,'OR001','루츠','영양제',50,'Y',NULL,NULL);

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
        CREATE TABLE t_work_photo (
            farm_cd TEXT NOT NULL,
            photo_id TEXT NOT NULL,
            work_id TEXT NOT NULL,
            file_path TEXT, thumb_path TEXT, use_yn TEXT DEFAULT 'Y',
            mod_id TEXT, mod_dt TEXT,
            PRIMARY KEY (farm_cd, photo_id)
        );
        CREATE TABLE t_weather_cache (
            farm_cd TEXT, weather_dt TEXT, weather_json TEXT, reg_dt TEXT,
            PRIMARY KEY (farm_cd, weather_dt)
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


class TestPurgeWorkRelatedCore(unittest.TestCase):
    def setUp(self):
        self.conn, self.path = _make_db()
        self.db = _DbShim(self.conn)
        self.svc = WorkLogIntegratedSaveService(self.db, "OR001")
        self.work_dt = (date.today() - timedelta(days=2)).isoformat()
        dig = self.work_dt.replace("-", "")
        self.work_id = f"{dig}-01"
        self.other_id = f"{dig}-02"

    def tearDown(self):
        self.conn.close()
        try:
            self.path.unlink(missing_ok=True)
        except OSError:
            pass

    def _qty(self) -> int:
        return int(
            self.db.execute_query(
                "SELECT qty_piece FROM m_pesticide_item WHERE item_id=1"
            )[0][0]
        )

    def _seed_detail(self, wid: str, mid: str = "WK010200") -> None:
        self.conn.execute(
            """
            INSERT INTO t_work_detail(
                work_id, work_dt, farm_cd, work_main_cd, work_mid_cd, status_cd
            ) VALUES (?,?,?,?,?,?)
            """,
            (wid, self.work_dt, "OR001", "WK01", mid, "WO010300"),
        )
        self.conn.commit()

    def test_labor_expense_ledger_and_pesticide_and_photo(self):
        self._seed_detail(self.work_id)
        self._seed_detail(self.other_id, "WK010100")
        self.svc.save_integrated(
            "tester",
            WorkLogSavePayload(
                master=MasterDto(work_dt=self.work_dt, day_of_week="월"),
                works=[
                    WorkDetailDto(
                        work_id=self.work_id,
                        work_mid_cd="WK010200",
                        work_mid_nm="방제",
                        pesticide_lines=[
                            PesticideLineDto(
                                item_id=1, use_qty=4, item_nm_snapshot="테스트약"
                            )
                        ],
                    ),
                    WorkDetailDto(
                        work_id=self.other_id,
                        work_mid_cd="WK010100",
                        work_mid_nm="전정",
                    ),
                ],
                labor_work_id=self.work_id,
                expense_work_id=self.work_id,
                labor_rows=[
                    LaborRowDto(
                        status="INS",
                        emp_cd="E1",
                        emp_nm="홍길동",
                        man_hour=8,
                        daily_wage=80000,
                        pay_method_cd="AS010101",
                        pay_status=PAY_STATUS_Y,
                    )
                ],
                expense_rows=[
                    ExpenseRowDto(
                        status="INS",
                        acct_cd="EX010101",
                        item_nm="장갑",
                        amt=5000,
                        pay_method_cd="AS010101",
                        pay_status=PAY_STATUS_Y,
                    )
                ],
                worker_nm="tester",
                worker_id="tester",
            ),
        )
        self.assertEqual(self._qty(), 96)
        self.conn.execute(
            """
            INSERT INTO t_work_photo(farm_cd, photo_id, work_id, file_path, use_yn)
            VALUES ('OR001','P1',?,'/tmp/a.jpg','Y')
            """,
            (self.work_id,),
        )
        # 다른 작업 전표 — 삭제 후에도 유지되어야 함
        other_slip = f"{self.work_dt.replace('-', '')}-999"
        self.conn.execute(
            """
            INSERT INTO t_ledger(
                slip_no, farm_cd, trans_dt, trans_type_cd, acct_cd, trans_amt,
                rmk, ref_id, trans_st, reg_id, reg_dt
            ) VALUES (?,?,?,'SPEND','EX010101',-3000,'타작업',?,'10','seed',
                      datetime('now','localtime'))
            """,
            (
                other_slip,
                "OR001",
                self.work_dt,
                f"EXP-{self.other_id}-EX010101_AS010101",
            ),
        )
        self.conn.commit()

        originals = self.db.execute_query(
            """
            SELECT slip_no, ref_id, trans_amt, trans_st
            FROM t_ledger
            WHERE farm_cd=? AND trans_st='10'
              AND (ref_id LIKE ? OR ref_id LIKE ?)
            ORDER BY slip_no
            """,
            ("OR001", f"RES-{self.work_id}-%", f"EXP-{self.work_id}-%"),
        )
        self.assertGreaterEqual(len(originals), 2)
        orig_map = {str(r[0]): (str(r[1]), float(r[2])) for r in originals}
        orig_sum = sum(float(r[2]) for r in originals)

        self.svc.purge_work_related("tester", self.work_id, self.work_dt)

        self.assertEqual(
            self.db.execute_query(
                "SELECT count(*) FROM t_work_detail WHERE work_id=?",
                (self.work_id,),
            )[0][0],
            0,
        )
        self.assertEqual(
            self.db.execute_query(
                "SELECT count(*) FROM t_work_detail WHERE work_id=?",
                (self.other_id,),
            )[0][0],
            1,
        )
        self.assertEqual(
            self.db.execute_query(
                "SELECT count(*) FROM t_work_resource WHERE work_id=?",
                (self.work_id,),
            )[0][0],
            0,
        )
        self.assertEqual(
            self.db.execute_query(
                "SELECT count(*) FROM t_work_expense WHERE work_id=?",
                (self.work_id,),
            )[0][0],
            0,
        )

        # 원전표: trans_st 10 → 90
        for slip_no, (ref_id, amt) in orig_map.items():
            st = self.db.execute_query(
                "SELECT trans_st FROM t_ledger WHERE slip_no=?",
                (slip_no,),
            )[0][0]
            self.assertEqual(str(st), "90", f"원전표 {slip_no} 미취소")

            # 역분개: parent_slip_no=원전표, trans_st=80, 금액 부호 반전
            # (AccountManager.get_reversal_queries: ref_id 자리에 원 slip_no 기록)
            rev = self.db.execute_query(
                """
                SELECT slip_no, trans_amt, trans_st, ref_id, parent_slip_no
                FROM t_ledger
                WHERE parent_slip_no=? AND trans_st='80'
                """,
                (slip_no,),
            )
            self.assertEqual(len(rev), 1, f"역분개 없음: {slip_no}")
            self.assertEqual(float(rev[0][1]), -float(amt))
            self.assertEqual(str(rev[0][4]), slip_no)

        # 금액 상쇄: 원전표(90)+역분개(80) 쌍 합 = 0
        pair_net = 0.0
        for slip_no, (_ref, amt) in orig_map.items():
            rows = self.db.execute_query(
                """
                SELECT trans_amt FROM t_ledger
                WHERE slip_no=? OR parent_slip_no=?
                """,
                (slip_no, slip_no),
            )
            pair_net += sum(float(r[0]) for r in rows)
        self.assertEqual(pair_net, 0.0)
        self.assertNotEqual(float(orig_sum), 0.0)
        # 활성(10) 잔존 없음
        active_res = self.db.execute_query(
            "SELECT count(*) FROM t_ledger WHERE trans_st='10' AND ref_id LIKE ?",
            (f"RES-{self.work_id}-%",),
        )[0][0]
        active_exp = self.db.execute_query(
            "SELECT count(*) FROM t_ledger WHERE trans_st='10' AND ref_id LIKE ?",
            (f"EXP-{self.work_id}-%",),
        )[0][0]
        self.assertEqual(int(active_res), 0)
        self.assertEqual(int(active_exp), 0)

        # 다른 작업 전표 영향 없음
        other_st = self.db.execute_query(
            "SELECT trans_st, trans_amt FROM t_ledger WHERE slip_no=?",
            (other_slip,),
        )[0]
        self.assertEqual(str(other_st[0]), "10")
        self.assertEqual(float(other_st[1]), -3000.0)

        self.assertEqual(self._qty(), 100)
        use = self.db.execute_query(
            "SELECT cancel_yn, stock_applied_yn FROM t_pesticide_use WHERE work_id=?",
            (self.work_id,),
        )[0]
        self.assertEqual(str(use[0]), "Y")
        photo = self.db.execute_query(
            "SELECT use_yn FROM t_work_photo WHERE photo_id='P1'"
        )[0][0]
        self.assertEqual(str(photo), "N")


class TestWorkLogServiceDeleteCascade(unittest.TestCase):
    def setUp(self):
        self.conn, self.path = _make_db()
        self.conn.close()
        self.svc = WorkLogService(db_path=self.path)
        self.DT = (date.today() + timedelta(days=9)).isoformat()
        self.digits = self.DT.replace("-", "")
        self.wid = f"{self.digits}-01"

    def tearDown(self):
        try:
            self.path.unlink(missing_ok=True)
        except OSError:
            pass

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(str(self.path))
        c.row_factory = sqlite3.Row
        return c

    def test_preview_and_delete_preparing_schedule(self):
        from app.schemas.work_log import (
            WorkLogWorkUpsertItem,
            WorkLogWorksUpsertRequest,
        )

        self.svc.upsert_works(
            "OR001",
            self.DT,
            WorkLogWorksUpsertRequest(
                works=[
                    WorkLogWorkUpsertItem(
                        work_mid_cd="WK010100",
                        rmk="준비중일정",
                        start_tm="09:00",
                        end_tm="10:00",
                    )
                ]
            ),
            user_id="T1",
        )
        preview = self.svc.get_delete_preview("OR001", self.wid)
        self.assertEqual(preview.work_id, self.wid)
        self.assertFalse(preview.has_related)
        self.assertEqual(preview.labor_count, 0)
        self.svc.delete_work("OR001", self.wid, user_id="T1")
        conn = self._conn()
        try:
            n = conn.execute(
                "SELECT count(*) FROM t_work_detail WHERE work_id=?",
                (self.wid,),
            ).fetchone()[0]
            self.assertEqual(n, 0)
        finally:
            conn.close()


class TestDeletePreviewFertilizerSplit(unittest.TestCase):
    """삭제 미리보기: 영양제→비료 / 그 외→농약 분리."""

    def setUp(self):
        self.conn, self.path = _make_db()
        self.db = _DbShim(self.conn)
        self.core = WorkLogIntegratedSaveService(self.db, "OR001")
        self.api = WorkLogService(db_path=self.path)
        self.work_dt = "2026-08-10"

    def tearDown(self):
        self.conn.close()
        try:
            self.path.unlink(missing_ok=True)
        except OSError:
            pass

    def test_fertilizer_work_preview_lists_nutrient_as_fertilizer(self):
        wid = "20260810-F1"
        self.core.save_integrated(
            "tester",
            WorkLogSavePayload(
                master=MasterDto(work_dt=self.work_dt, day_of_week="월"),
                works=[
                    WorkDetailDto(
                        work_id=wid,
                        work_mid_cd="WK010800",
                        work_mid_nm="비료/영양제",
                        status_cd="WO010300",
                        pesticide_lines=[
                            PesticideLineDto(
                                item_id=2,
                                use_qty=1,
                                item_nm_snapshot="루츠",
                            )
                        ],
                    )
                ],
                labor_work_id=wid,
                expense_work_id=wid,
                worker_nm="tester",
                worker_id="tester",
            ),
        )
        preview = self.api.get_delete_preview("OR001", wid)
        self.assertEqual(preview.fertilizer_count, 1)
        self.assertEqual(preview.fertilizer_item_names, ["루츠"])
        self.assertEqual(preview.pesticide_count, 0)
        self.assertEqual(preview.pesticide_item_names, [])
        self.assertTrue(preview.is_fertilizer_work)
        self.assertTrue(preview.has_related)

    def test_pesticide_work_preview_lists_spray_as_pesticide(self):
        wid = "20260810-P1"
        self.core.save_integrated(
            "tester",
            WorkLogSavePayload(
                master=MasterDto(work_dt=self.work_dt, day_of_week="월"),
                works=[
                    WorkDetailDto(
                        work_id=wid,
                        work_mid_cd="WK010200",
                        work_mid_nm="방제",
                        status_cd="WO010300",
                        pesticide_lines=[
                            PesticideLineDto(
                                item_id=1,
                                use_qty=1,
                                item_nm_snapshot="테스트약",
                            )
                        ],
                    )
                ],
                labor_work_id=wid,
                expense_work_id=wid,
                worker_nm="tester",
                worker_id="tester",
            ),
        )
        preview = self.api.get_delete_preview("OR001", wid)
        self.assertEqual(preview.pesticide_count, 1)
        self.assertEqual(preview.pesticide_item_names, ["테스트약"])
        self.assertEqual(preview.fertilizer_count, 0)
        self.assertEqual(preview.fertilizer_item_names, [])
        self.assertFalse(preview.is_fertilizer_work)


if __name__ == "__main__":
    unittest.main()
