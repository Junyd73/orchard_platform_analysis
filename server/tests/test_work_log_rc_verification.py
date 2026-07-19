# -*- coding: utf-8 -*-
"""영농일지 통합 저장 RC(Release Candidate) 검증 스위트.

Business Logic 변경 없이 진입 경로·TX·Migration·동시성·회귀를 검증한다.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

_REPO = Path(__file__).resolve().parents[2]
_SERVER = _REPO / "server"
# server/app 이 저장소 루트 app/ 보다 우선되도록 server를 앞에 둔다.
_s_repo, _s_server = str(_REPO), str(_SERVER)
if _s_repo in sys.path:
    sys.path.remove(_s_repo)
if _s_server in sys.path:
    sys.path.remove(_s_server)
sys.path.insert(0, _s_repo)
sys.path.insert(0, _s_server)

from core.account_manager import AccountManager  # noqa: E402
from core.db_manager import DBManager  # noqa: E402
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

FARM = "OR001"
WORK_DT = "2026-07-18"
WORK_ID = "20260718-01"
USER = "rc_tester"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
def _schema_sql(*, with_cancel_yn: bool = True) -> str:
    cancel_col = (
        "cancel_yn TEXT NOT NULL DEFAULT 'N'," if with_cancel_yn else ""
    )
    return f"""
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
        CREATE TABLE t of_work_expense_PLACEHOLDER;
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
        CREATE TABLE m_farm_info (
            farm_cd TEXT PRIMARY KEY, farm_nm TEXT,
            lat REAL, lon REAL, nx INTEGER, ny INTEGER
        );
        CREATE TABLE m_pesticide_item (
            item_id INTEGER PRIMARY KEY, farm_cd TEXT, item_nm TEXT,
            qty_piece INTEGER, use_yn TEXT DEFAULT 'Y',
            mod_id TEXT, mod_dt TEXT
        );
        CREATE TABLE t_pesticide_use (
            use_id INTEGER PRIMARY KEY AUTOINCREMENT,
            farm_cd TEXT, use_dt TEXT, site_id INTEGER,
            worker_nm TEXT, worker_id TEXT, work_type_nm TEXT, rmk TEXT,
            stock_applied_yn TEXT DEFAULT 'N',
            stock_applied_dt TEXT, stock_applied_by TEXT,
            {cancel_col}
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


def _make_db(*, with_cancel_yn: bool = True) -> tuple[sqlite3.Connection, Path]:
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    path = Path(tmp.name)
    conn = sqlite3.connect(str(path), timeout=30.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    sql = _schema_sql(with_cancel_yn=with_cancel_yn).replace(
        "CREATE TABLE t of_work_expense_PLACEHOLDER;", ""
    )
    conn.executescript(sql)
    conn.execute(
        "INSERT INTO m_partner(farm_cd, pt_id, pt_nm, worker_type_cd) VALUES (?,?,?,?)",
        (FARM, "E1", "홍길동", "EMP"),
    )
    conn.execute(
        "INSERT INTO m_farm_info(farm_cd, farm_nm, lat, lon, nx, ny) VALUES (?,?,?,?,?,?)",
        (FARM, "테스트", 35.0, 128.0, 1, 1),
    )
    conn.execute(
        "INSERT INTO m_pesticide_item(item_id, farm_cd, item_nm, qty_piece, use_yn) "
        "VALUES (1,?,?,100,'Y')",
        (FARM, "테스트약"),
    )
    conn.execute(
        "INSERT INTO m_pesticide_item(item_id, farm_cd, item_nm, qty_piece, use_yn) "
        "VALUES (2,?,?,50,'Y')",
        (FARM, "보조약"),
    )
    conn.commit()
    return conn, path


class _DbShim:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.begin_calls = 0
        self.commit_calls = 0
        self.rollback_calls = 0

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
                self.begin_calls += 1
                cur.execute("BEGIN IMMEDIATE")
                yield cur
                self.conn.commit()
                self.commit_calls += 1
            except Exception:
                try:
                    self.conn.rollback()
                    self.rollback_calls += 1
                except sqlite3.Error:
                    pass
                raise
            finally:
                self.conn.isolation_level = prev if prev is not None else ""

        return _ctx()


def _clear_slip_cache() -> None:
    AccountManager._shared_seq_cache.clear()


def _snapshot(conn: sqlite3.Connection) -> dict:
    """정합성 비교용 스냅샷(시각 컬럼 제외)."""
    cur = conn.cursor()

    def rows(sql: str, params=()):
        cur.execute(sql, params)
        cols = [d[0] for d in cur.description]
        skip = {"reg_dt", "mod_dt", "stock_applied_dt", "stock_applied_by"}
        out = []
        for r in cur.fetchall():
            d = {
                c: r[i]
                for i, c in enumerate(cols)
                if c not in skip
            }
            out.append(tuple(sorted(d.items())))
        return sorted(out)

    qty = cur.execute(
        "SELECT item_id, qty_piece FROM m_pesticide_item ORDER BY item_id"
    ).fetchall()
    active_use = cur.execute(
        """
        SELECT COUNT(*) FROM t_pesticide_use
        WHERE IFNULL(cancel_yn,'N')!='Y' AND IFNULL(stock_applied_yn,'N')='Y'
        """
    ).fetchone()[0]
    cancel_use = cur.execute(
        "SELECT COUNT(*) FROM t_pesticide_use WHERE IFNULL(cancel_yn,'N')='Y'"
    ).fetchone()[0]
    ledger_active = cur.execute(
        "SELECT COUNT(*), IFNULL(SUM(trans_amt),0) FROM t_ledger WHERE trans_st='10'"
    ).fetchone()
    slips = [
        r[0]
        for r in cur.execute(
            "SELECT slip_no FROM t_ledger WHERE trans_st='10' ORDER BY slip_no"
        ).fetchall()
    ]
    return {
        "master": rows(
            "SELECT work_dt, day_of_week, weather_cd, farm_cd, work_rmk FROM t_work_master"
        ),
        "detail": rows(
            "SELECT work_id, work_dt, farm_cd, work_mid_cd, rmk FROM t_work_detail"
        ),
        "resource": rows(
            "SELECT work_id, emp_cd, man_hour, daily_wage, pay_status, slip_no "
            "FROM t_work_resource"
        ),
        "expense": rows(
            "SELECT work_id, acct_cd, total_amt, pay_status, slip_no FROM t_work_expense"
        ),
        "use": rows(
            "SELECT farm_cd, work_id, stock_applied_yn, IFNULL(cancel_yn,'N'), use_yn "
            "FROM t_pesticide_use"
        ),
        "use_line": rows(
            "SELECT use_id, item_id, use_qty FROM t_pesticide_use_line ORDER BY use_id, line_no"
        ),
        "stock_hist": rows(
            "SELECT item_id, trans_type, qty_delta, qty_after, ref_id "
            "FROM t_pesticide_stock_hist"
        ),
        "ledger": rows(
            "SELECT slip_no, acct_cd, trans_amt, ref_id, trans_st FROM t_ledger"
        ),
        "qty": list(qty),
        "active_use": int(active_use),
        "cancel_use": int(cancel_use),
        "ledger_cnt": int(ledger_active[0]),
        "ledger_amt": float(ledger_active[1]),
        "slips": slips,
    }


def _base_payload(**kwargs) -> WorkLogSavePayload:
    pest = kwargs.pop("pest_qty", 3)
    return WorkLogSavePayload(
        master=MasterDto(work_dt=WORK_DT, day_of_week="토", weather_cd="WT010100"),
        works=[
            WorkDetailDto(
                work_id=WORK_ID,
                work_mid_cd="WK010200",
                work_mid_nm="방제",
                pesticide_lines=[
                    PesticideLineDto(
                        item_id=1, use_qty=pest, item_nm_snapshot="테스트약"
                    )
                ],
                replace_pesticide_use_id=kwargs.pop("replace_uid", None),
            )
        ],
        labor_work_id=WORK_ID,
        expense_work_id=WORK_ID,
        labor_rows=kwargs.pop(
            "labor_rows",
            [
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
        ),
        expense_rows=kwargs.pop(
            "expense_rows",
            [
                ExpenseRowDto(
                    status="INS",
                    acct_cd="EX020201",
                    item_nm="자재",
                    amt=10000,
                    pay_method_cd="AS010101",
                    pay_status="Y",
                )
            ],
        ),
        worker_nm=USER,
        worker_id=USER,
    )


# ---------------------------------------------------------------------------
# 1. PC 수정 진입
# ---------------------------------------------------------------------------
class TestRc01PcEditBegin(unittest.TestCase):
    def test_pc_edit_begin_no_service_calls_and_no_db_change(self):
        from ui.pages.work_log_page import WorkLogPage

        conn, path = _make_db()
        self.addCleanup(lambda: (conn.close(), path.unlink(missing_ok=True)))
        db = _DbShim(conn)
        svc = WorkLogIntegratedSaveService(db, FARM)
        # 확정 사용 1건
        svc.save_integrated(USER, _base_payload(pest_qty=4))
        before = _snapshot(conn)
        use_id = int(
            conn.execute(
                "SELECT use_id FROM t_pesticide_use WHERE work_id=?", (WORK_ID,)
            ).fetchone()[0]
        )

        page = MagicMock()
        page.selected_work_id = WORK_ID
        page._pesticide_cache = {
            WORK_ID: {"stock_applied_yn": "Y", "use_id": use_id}
        }
        page._pesticide_replace_use_id = None
        page.work_log_save_svc = MagicMock(wraps=svc)
        page._update_pesticide_tab_state = MagicMock()

        with patch("ui.pages.work_log_page.QMessageBox"):
            WorkLogPage._on_pesticide_edit_begin(page)

        page.work_log_save_svc.cancel_pesticide_use.assert_not_called()
        page.work_log_save_svc.replace_pesticide_use.assert_not_called()
        page.work_log_save_svc.save_integrated.assert_not_called()
        self.assertEqual(page._pesticide_replace_use_id, use_id)
        self.assertEqual(_snapshot(conn), before)


# ---------------------------------------------------------------------------
# 3. PC ↔ FastAPI 진입 경로 동일성
# ---------------------------------------------------------------------------
class TestRc03PcFastapiParity(unittest.TestCase):
    def _run_pc_entry(self, db_path: Path) -> None:
        """Case A: WorkLogPage.save_all_integrated_data → Core."""
        from ui.pages.work_log_page import WorkLogPage

        _clear_slip_cache()
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        db = _DbShim(conn)
        svc = WorkLogIntegratedSaveService(db, FARM)

        mid = MagicMock()
        mid.currentData.return_value = "WK010200"
        mid.currentText.return_value = "방제"
        loc = MagicMock()
        loc.currentData.return_value = None
        rmk = MagicMock()
        rmk.text.return_value = ""
        st = MagicMock()
        st.time.return_value.toString.return_value = "09:00"
        en = MagicMock()
        en.time.return_value.toString.return_value = "12:00"
        st_cd = MagicMock()
        st_cd.currentData.return_value = ""

        date_obj = MagicMock()
        date_obj.toString.return_value = WORK_DT
        date_obj.dayOfWeek.return_value = 6  # 토

        page = MagicMock()
        page.work_log_save_svc = svc
        page.my_user_id = USER
        page.session = {"user_nm": USER}
        page.date_edit.date.return_value = date_obj
        page.table_work.rowCount.return_value = 1
        page.table_work.cellWidget.side_effect = lambda r, c: {
            1: mid,
            2: loc,
            3: rmk,
            4: st,
            5: en,
            6: st_cd,
        }[c]
        page._ensure_work_date_not_future.return_value = True
        page._flush_pesticide_ui_to_cache = MagicMock()
        page._gen_work_id.return_value = WORK_ID
        page._get_active_detail_work_id.return_value = WORK_ID
        page._get_current_selected_work_id.return_value = WORK_ID
        page.selected_work_id = WORK_ID
        page._is_pesticide_work_row.return_value = True
        page._collect_pesticide_lines_from_ui.return_value = [
            {
                "item_id": 1,
                "use_qty": 3,
                "item_nm_snapshot": "테스트약",
                "spec_nm_snapshot": "",
                "purpose_nm": "",
                "line_rmk": "",
            }
        ]
        page._pesticide_replace_use_id = None
        page._collect_labor_dto_from_ui.return_value = (
            [
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
            [],
        )
        page._collect_expense_dto_from_ui.return_value = (
            [
                ExpenseRowDto(
                    status="INS",
                    acct_cd="EX020201",
                    item_nm="자재",
                    amt=10000,
                    pay_method_cd="AS010101",
                    pay_status="Y",
                )
            ],
            [],
        )
        page.combo_weather.currentData.return_value = "WT010100"
        page.txt_issue.toPlainText.return_value = ""
        page.weather_widgets = {}
        page._bootstrap_pesticide_cache_from_db = MagicMock()
        page.load_res_data = MagicMock()
        page.load_work_expenses = MagicMock()
        page._switch_pesticide_for_selected = MagicMock()
        page.invalidate_monthly_cache = MagicMock()
        page.refresh_monthly_overview = MagicMock()
        page.removed_res_ids = []
        page.removed_exp_ids = []

        with patch("ui.pages.work_log_page.QMessageBox"):
            WorkLogPage.save_all_integrated_data(page)
        conn.close()

    def _run_api_entry(self, db_path: Path) -> None:
        """Case B: FastAPI WorkLogService.save_integrated (= router 진입)."""
        server_root = str(_SERVER)
        # 루트 app/ 섀도잉 방지
        while server_root in sys.path:
            sys.path.remove(server_root)
        sys.path.insert(0, server_root)
        from app.schemas.work_log import (  # noqa: WPS433
            WorkLogExpenseUpsertItem,
            WorkLogIntegratedSaveRequest,
            WorkLogLaborUpsertItem,
            WorkLogMasterUpsertRequest,
            WorkLogPesticideLineUpsert,
            WorkLogWorkIntegratedItem,
        )
        from app.services.work_log_service import WorkLogService  # noqa: WPS433

        _clear_slip_cache()
        body = WorkLogIntegratedSaveRequest(
            master=WorkLogMasterUpsertRequest(
                day_of_week="토", weather_cd="WT010100"
            ),
            works=[
                WorkLogWorkIntegratedItem(
                    work_id=WORK_ID,
                    work_mid_cd="WK010200",
                    work_mid_nm="방제",
                    pesticide_lines=[
                        WorkLogPesticideLineUpsert(
                            item_id=1, use_qty=3, item_nm_snapshot="테스트약"
                        )
                    ],
                )
            ],
            labor_work_id=WORK_ID,
            expense_work_id=WORK_ID,
            labor_rows=[
                WorkLogLaborUpsertItem(
                    status="INS",
                    emp_cd="E1",
                    emp_nm="홍길동",
                    man_hour=8,
                    daily_wage=80000,
                    pay_method_cd="AS010101",
                    pay_status="Y",
                )
            ],
            expense_rows=[
                WorkLogExpenseUpsertItem(
                    status="INS",
                    acct_cd="EX020201",
                    item_nm="자재",
                    amt=10000,
                    pay_method_cd="AS010101",
                    pay_status="Y",
                )
            ],
            worker_nm=USER,
        )
        WorkLogService(db_path=db_path).save_integrated(
            FARM, WORK_DT, body, user_id=USER
        )

    def test_pc_and_fastapi_same_db_result(self):
        conn_a, path_a = _make_db()
        conn_a.close()
        conn_b, path_b = _make_db()
        conn_b.close()
        self.addCleanup(lambda: path_a.unlink(missing_ok=True))
        self.addCleanup(lambda: path_b.unlink(missing_ok=True))

        self._run_pc_entry(path_a)
        self._run_api_entry(path_b)

        conn_sa = sqlite3.connect(str(path_a))
        conn_sb = sqlite3.connect(str(path_b))
        try:
            snap_a = _snapshot(conn_sa)
            snap_b = _snapshot(conn_sb)
        finally:
            conn_sa.close()
            conn_sb.close()

        for key in (
            "master",
            "detail",
            "resource",
            "expense",
            "use",
            "use_line",
            "stock_hist",
            "ledger",
            "qty",
            "active_use",
            "cancel_use",
            "ledger_cnt",
            "ledger_amt",
            "slips",
        ):
            self.assertEqual(snap_a[key], snap_b[key], msg=f"mismatch: {key}")
        for slip in snap_a["slips"]:
            self.assertRegex(slip, r"^\d{8}-\d{3}$")


# ---------------------------------------------------------------------------
# 4. Transaction Rollback (단계별)
# ---------------------------------------------------------------------------
class TestRc04RollbackStages(unittest.TestCase):
    def setUp(self):
        _clear_slip_cache()
        self.conn, self.path = _make_db()
        self.db = _DbShim(self.conn)
        self.svc = WorkLogIntegratedSaveService(self.db, FARM)
        self.svc.save_integrated(USER, _base_payload(pest_qty=5))
        self.use_id = int(
            self.conn.execute(
                "SELECT use_id FROM t_pesticide_use WHERE work_id=?", (WORK_ID,)
            ).fetchone()[0]
        )
        self.before = _snapshot(self.conn)

    def tearDown(self):
        self.conn.close()
        self.path.unlink(missing_ok=True)

    def _assert_fully_restored(self):
        self.assertEqual(_snapshot(self.conn), self.before)

    def test_fail_after_stock_restore(self):
        real = PesticideManager.cancel_use_restore_stock_on_cursor

        def _wrap(self_pm, cur, *a, **kw):
            ok, errs = real(self_pm, cur, *a, **kw)
            if ok:
                raise WorkLogSaveError("RC fail after restore", code="RC_R1")
            return ok, errs

        with patch.object(PesticideManager, "cancel_use_restore_stock_on_cursor", _wrap):
            r = self.svc.replace_pesticide_use(
                USER,
                self.use_id,
                PesticideReplacePayload(
                    use_dt=WORK_DT,
                    work_id=WORK_ID,
                    lines=[
                        PesticideLineDto(
                            item_id=1, use_qty=1, item_nm_snapshot="테스트약"
                        )
                    ],
                ),
            )
        self.assertFalse(r.ok)
        self._assert_fully_restored()

    def test_fail_after_new_use_save(self):
        real_save = PesticideManager.save_use_full_on_cursor

        def _wrap(self_pm, *a, **kw):
            uid = real_save(self_pm, *a, **kw)
            raise WorkLogSaveError("RC fail after use save", code="RC_R2")

        with patch.object(PesticideManager, "save_use_full_on_cursor", _wrap):
            r = self.svc.replace_pesticide_use(
                USER,
                self.use_id,
                PesticideReplacePayload(
                    use_dt=WORK_DT,
                    work_id=WORK_ID,
                    lines=[
                        PesticideLineDto(
                            item_id=1, use_qty=1, item_nm_snapshot="테스트약"
                        )
                    ],
                ),
            )
        self.assertFalse(r.ok)
        self._assert_fully_restored()

    def test_fail_after_new_stock_debit(self):
        real = PesticideManager.apply_use_to_stock_on_cursor

        def _wrap(self_pm, *a, **kw):
            ok, errs = real(self_pm, *a, **kw)
            if ok:
                raise WorkLogSaveError("RC fail after debit", code="RC_R3")
            return ok, errs

        with patch.object(PesticideManager, "apply_use_to_stock_on_cursor", _wrap):
            r = self.svc.replace_pesticide_use(
                USER,
                self.use_id,
                PesticideReplacePayload(
                    use_dt=WORK_DT,
                    work_id=WORK_ID,
                    lines=[
                        PesticideLineDto(
                            item_id=1, use_qty=1, item_nm_snapshot="테스트약"
                        )
                    ],
                ),
            )
        self.assertFalse(r.ok)
        self._assert_fully_restored()

    def test_fail_after_ledger_in_integrated_save(self):
        """통합 저장 TX 중 Ledger SQL 실행 직후 실패 → 전체 rollback."""
        before = _snapshot(self.conn)
        payload = WorkLogSavePayload(
            master=MasterDto(work_dt="2026-07-19", day_of_week="일"),
            works=[
                WorkDetailDto(
                    work_id="20260719-01",
                    work_mid_cd="WK010100",
                    work_mid_nm="전정",
                    pesticide_lines=[],
                )
            ],
            labor_work_id="20260719-01",
            expense_work_id="20260719-01",
            labor_rows=[],
            expense_rows=[
                ExpenseRowDto(
                    status="INS",
                    acct_cd="EX020201",
                    item_nm="자재2",
                    amt=3000,
                    pay_method_cd="AS010101",
                    pay_status="Y",
                )
            ],
            worker_nm=USER,
            worker_id=USER,
        )
        real_exec = WorkLogIntegratedSaveService._execute_transaction

        def _exec_fail_after_ledger(self_svc, queries, cursor_ops=None):
            def _run(cur):
                for query, params in queries:
                    cur.execute(query, params)
                    if "INSERT INTO t_ledger" in str(query):
                        raise WorkLogSaveError(
                            "RC fail after ledger", code="RC_R4"
                        )
                for op in cursor_ops or []:
                    op(cur)

            txn = getattr(self_svc.db, "transaction", None)
            if callable(txn):
                with txn() as cur:
                    _run(cur)
                return
            real_exec(self_svc, queries, cursor_ops)

        with patch.object(
            WorkLogIntegratedSaveService,
            "_execute_transaction",
            _exec_fail_after_ledger,
        ):
            with self.assertRaises(WorkLogSaveError):
                self.svc.save_integrated(USER, payload)
        self.assertEqual(
            _snapshot(self.conn)["active_use"], before["active_use"]
        )
        self.assertEqual(_snapshot(self.conn)["qty"], before["qty"])
        self.assertEqual(
            int(
                self.conn.execute(
                    "SELECT COUNT(*) FROM t_work_detail WHERE work_id='20260719-01'"
                ).fetchone()[0]
            ),
            0,
        )
        self.assertEqual(
            int(
                self.conn.execute(
                    "SELECT COUNT(*) FROM t_ledger WHERE ref_id LIKE '%20260719%'"
                ).fetchone()[0]
            ),
            0,
        )


# ---------------------------------------------------------------------------
# 5. AccountManager TX 참여
# ---------------------------------------------------------------------------
class TestRc05AccountManagerTx(unittest.TestCase):
    def test_account_manager_no_begin_commit_rollback_and_writes_in_txn(self):
        import inspect

        src = inspect.getsource(AccountManager)
        self.assertNotIn("BEGIN", src.upper().replace("BEGINNING", ""))
        # 메서드 본문에 commit/rollback 호출 없음
        self.assertNotRegex(src, r"\bcommit\s*\(")
        self.assertNotRegex(src, r"\brollback\s*\(")

        conn, path = _make_db()
        self.addCleanup(lambda: (conn.close(), path.unlink(missing_ok=True)))
        db = _DbShim(conn)
        svc = WorkLogIntegratedSaveService(db, FARM)

        _clear_slip_cache()
        before_begin = db.begin_calls
        svc.save_integrated(USER, _base_payload())
        self.assertGreater(db.begin_calls, before_begin)
        self.assertEqual(db.begin_calls, db.commit_calls)
        self.assertGreater(db.commit_calls, 0)
        self.assertGreater(
            int(
                conn.execute(
                    "SELECT COUNT(*) FROM t_ledger WHERE trans_st='10'"
                ).fetchone()[0]
            ),
            0,
        )
        # 계획 단계(fingerprint) 읽기는 TX 밖 SQL 조립, 쓰기는 동일 transaction() 커밋.


# ---------------------------------------------------------------------------
# 6. Migration
# ---------------------------------------------------------------------------
class TestRc06Migration(unittest.TestCase):
    def test_new_db_has_cancel_yn_and_saves(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        path = Path(tmp.name)
        path.unlink(missing_ok=True)
        self.addCleanup(lambda: path.unlink(missing_ok=True))
        mgr = DBManager(str(path))
        self.addCleanup(lambda: mgr.conn.close() if mgr.conn else None)
        cols = {
            r[1]
            for r in mgr.conn.execute(
                "PRAGMA table_info(t_pesticide_use)"
            ).fetchall()
        }
        self.assertIn("cancel_yn", cols)
        # DBManager 스키마 + RC 최소 시드(파트너·품목·작업 테이블 보장)
        mgr.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS m_partner (
                farm_cd TEXT, pt_id TEXT, pt_nm TEXT, worker_type_cd TEXT
            );
            CREATE TABLE IF NOT EXISTS t_work_master (
                work_dt TEXT PRIMARY KEY,
                day_of_week TEXT, weather_cd TEXT,
                temp_max REAL, temp_min REAL, precip REAL, humidity REAL,
                sun_rise TEXT, sun_set TEXT, sunshine_hr REAL,
                wind_max REAL, wind_min REAL, work_rmk TEXT,
                farm_cd TEXT, reg_id TEXT, reg_dt TEXT, mod_id TEXT, mod_dt TEXT
            );
            CREATE TABLE IF NOT EXISTS t_work_detail (
                work_id TEXT PRIMARY KEY,
                work_dt TEXT, farm_cd TEXT, work_main_cd TEXT, work_mid_cd TEXT,
                work_loc_id TEXT, rmk TEXT, start_tm TEXT, end_tm TEXT, status_cd TEXT,
                reg_id TEXT, reg_dt TEXT, mod_id TEXT, mod_dt TEXT
            );
            CREATE TABLE IF NOT EXISTS t_work_resource (
                res_id INTEGER PRIMARY KEY AUTOINCREMENT,
                work_id TEXT, farm_cd TEXT, trans_dt TEXT, emp_cd TEXT,
                man_hour REAL, daily_wage REAL, meal_cost REAL, other_cost REAL,
                pay_method_cd TEXT, pay_status TEXT, slip_no TEXT,
                reg_id TEXT, reg_dt TEXT, mod_id TEXT, mod_dt TEXT
            );
            CREATE TABLE IF NOT EXISTS t_work_expense (
                exp_id INTEGER PRIMARY KEY AUTOINCREMENT,
                farm_cd TEXT, work_id TEXT, trans_dt TEXT, acct_cd TEXT, item_nm TEXT,
                qty REAL, unit_price REAL, total_amt REAL,
                pay_method_cd TEXT, pay_status TEXT, slip_no TEXT,
                reg_id TEXT, reg_dt TEXT, mod_id TEXT, mod_dt TEXT
            );
            CREATE TABLE IF NOT EXISTS t_ledger (
                slip_no TEXT PRIMARY KEY, farm_cd TEXT, trans_dt TEXT,
                trans_type_cd TEXT, acct_cd TEXT, trans_amt REAL, rmk TEXT,
                ref_id TEXT, parent_slip_no TEXT, trans_st TEXT,
                reg_id TEXT, reg_dt TEXT, mod_id TEXT, mod_dt TEXT
            );
            """
        )
        mgr.conn.execute(
            "INSERT OR IGNORE INTO m_partner(farm_cd, pt_id, pt_nm, worker_type_cd) "
            "VALUES (?,?,?,?)",
            (FARM, "E1", "홍길동", "EMP"),
        )
        exists = mgr.conn.execute(
            "SELECT 1 FROM m_pesticide_item WHERE item_id=1 AND farm_cd=?",
            (FARM,),
        ).fetchone()
        if not exists:
            mgr.conn.execute(
                "INSERT INTO m_pesticide_item(item_id, farm_cd, item_nm, qty_piece, use_yn) "
                "VALUES (1,?,?,100,'Y')",
                (FARM, "테스트약"),
            )
        mgr.conn.commit()
        svc = WorkLogIntegratedSaveService(mgr, FARM)
        _clear_slip_cache()
        svc.save_integrated(
            USER, _base_payload(pest_qty=2, labor_rows=[], expense_rows=[])
        )
        row = mgr.conn.execute(
            "SELECT stock_applied_yn, cancel_yn FROM t_pesticide_use WHERE work_id=?",
            (WORK_ID,),
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(str(row[0]), "Y")
        self.assertEqual(str(row[1]), "N")

    def test_legacy_db_migrates_preserving_rows(self):
        conn, path = _make_db(with_cancel_yn=False)
        conn.execute(
            """
            INSERT INTO t_pesticide_use(
                farm_cd, use_dt, stock_applied_yn, use_yn, work_id, reg_id
            ) VALUES (?,?, 'Y','Y',?,?)
            """,
            (FARM, WORK_DT, WORK_ID, USER),
        )
        conn.commit()
        before_cnt = conn.execute("SELECT COUNT(*) FROM t_pesticide_use").fetchone()[0]
        conn.close()

        mgr = DBManager(str(path))
        self.addCleanup(lambda: (mgr.conn.close(), path.unlink(missing_ok=True)))
        cols = {
            r[1]
            for r in mgr.conn.execute(
                "PRAGMA table_info(t_pesticide_use)"
            ).fetchall()
        }
        self.assertIn("cancel_yn", cols)
        after_cnt = mgr.conn.execute(
            "SELECT COUNT(*) FROM t_pesticide_use"
        ).fetchone()[0]
        self.assertEqual(before_cnt, after_cnt)
        yn = mgr.conn.execute(
            "SELECT IFNULL(cancel_yn,'N') FROM t_pesticide_use LIMIT 1"
        ).fetchone()[0]
        self.assertEqual(str(yn), "N")

    def test_migration_idempotent(self):
        conn, path = _make_db(with_cancel_yn=False)
        conn.close()
        mgr = DBManager(str(path))
        self.addCleanup(lambda: (mgr.conn.close(), path.unlink(missing_ok=True)))
        # 두 번 호출
        mgr._migrate_pesticide_use_cancel_yn()
        mgr._migrate_pesticide_use_cancel_yn()
        cnt = mgr.conn.execute("SELECT COUNT(*) FROM t_pesticide_use").fetchone()[0]
        self.assertEqual(int(cnt), 0)


# ---------------------------------------------------------------------------
# 7. 동시성
# ---------------------------------------------------------------------------
class TestRc07Concurrency(unittest.TestCase):
    def test_concurrent_cancel_and_replace_no_corruption(self):
        conn, path = _make_db()
        conn.close()
        # file-backed for multi-connection
        conn1 = sqlite3.connect(str(path), timeout=30.0, check_same_thread=False)
        conn1.row_factory = sqlite3.Row
        db1 = _DbShim(conn1)
        svc1 = WorkLogIntegratedSaveService(db1, FARM)
        _clear_slip_cache()
        svc1.save_integrated(USER, _base_payload(pest_qty=5, labor_rows=[], expense_rows=[]))
        use_id = int(
            conn1.execute(
                "SELECT use_id FROM t_pesticide_use WHERE work_id=?", (WORK_ID,)
            ).fetchone()[0]
        )
        conn1.close()

        errors: list[str] = []
        results: list[str] = []

        def do_cancel():
            try:
                c = sqlite3.connect(str(path), timeout=30.0, check_same_thread=False)
                c.row_factory = sqlite3.Row
                s = WorkLogIntegratedSaveService(_DbShim(c), FARM)
                r = s.cancel_pesticide_use(USER, use_id=use_id)
                results.append(f"cancel:{r.ok}")
                c.close()
            except Exception as e:
                errors.append(f"cancel:{e}")

        def do_replace():
            try:
                time.sleep(0.01)
                c = sqlite3.connect(str(path), timeout=30.0, check_same_thread=False)
                c.row_factory = sqlite3.Row
                s = WorkLogIntegratedSaveService(_DbShim(c), FARM)
                r = s.replace_pesticide_use(
                    USER,
                    use_id,
                    PesticideReplacePayload(
                        use_dt=WORK_DT,
                        work_id=WORK_ID,
                        lines=[
                            PesticideLineDto(
                                item_id=1, use_qty=2, item_nm_snapshot="테스트약"
                            )
                        ],
                    ),
                )
                results.append(f"replace:{r.ok}")
                c.close()
            except Exception as e:
                errors.append(f"replace:{e}")

        t1 = threading.Thread(target=do_cancel)
        t2 = threading.Thread(target=do_replace)
        t1.start()
        t2.start()
        t1.join(timeout=60)
        t2.join(timeout=60)
        self.assertFalse(errors, msg=str(errors))

        c = sqlite3.connect(str(path))
        self.addCleanup(lambda: (c.close(), path.unlink(missing_ok=True)))
        qty = int(
            c.execute(
                "SELECT qty_piece FROM m_pesticide_item WHERE item_id=1"
            ).fetchone()[0]
        )
        self.assertGreaterEqual(qty, 0)
        active = int(
            c.execute(
                """
                SELECT COUNT(*) FROM t_pesticide_use
                WHERE IFNULL(cancel_yn,'N')!='Y'
                  AND IFNULL(stock_applied_yn,'N')='Y'
                """
            ).fetchone()[0]
        )
        # 취소 성공이면 0, replace 성공이면 1 — 둘 다 성공해 중복 복원되면 안 됨
        self.assertIn(active, (0, 1))
        # 재고: 초기 100, 사용 5 → 95. 취소만이면 100, replace(2)면 98
        self.assertIn(qty, (98, 100))
        # 복원 hist가 과도하지 않음(취소 1회 수준)
        restore_cnt = int(
            c.execute(
                "SELECT COUNT(*) FROM t_pesticide_stock_hist WHERE qty_delta > 0"
            ).fetchone()[0]
        )
        self.assertLessEqual(restore_cnt, 2)


# ---------------------------------------------------------------------------
# 8. 100회 반복
# ---------------------------------------------------------------------------
class TestRc08RepeatStability(unittest.TestCase):
    def test_100_resaves_stable(self):
        conn, path = _make_db()
        self.addCleanup(lambda: (conn.close(), path.unlink(missing_ok=True)))
        db = _DbShim(conn)
        svc = WorkLogIntegratedSaveService(db, FARM)
        _clear_slip_cache()
        payload = _base_payload(pest_qty=3)
        svc.save_integrated(USER, payload)
        # ORG 재저장용으로 재조회
        res = conn.execute(
            "SELECT res_id, slip_no FROM t_work_resource WHERE work_id=?",
            (WORK_ID,),
        ).fetchone()
        exp = conn.execute(
            "SELECT exp_id, slip_no FROM t_work_expense WHERE work_id=?",
            (WORK_ID,),
        ).fetchone()
        payload2 = WorkLogSavePayload(
            master=payload.master,
            works=payload.works,
            labor_work_id=WORK_ID,
            expense_work_id=WORK_ID,
            labor_rows=[
                LaborRowDto(
                    status="ORG",
                    res_id=int(res[0]),
                    emp_cd="E1",
                    emp_nm="홍길동",
                    man_hour=8,
                    daily_wage=80000,
                    pay_method_cd="AS010101",
                    pay_status="Y",
                    orig_data={"res_id": int(res[0]), "slip_no": res[1]},
                )
            ],
            expense_rows=[
                ExpenseRowDto(
                    status="ORG",
                    exp_id=int(exp[0]),
                    acct_cd="EX020201",
                    item_nm="자재",
                    amt=10000,
                    pay_method_cd="AS010101",
                    pay_status="Y",
                    orig_data={"exp_id": int(exp[0]), "slip_no": exp[1]},
                )
            ],
            worker_nm=USER,
            worker_id=USER,
        )
        base = _snapshot(conn)
        for i in range(100):
            svc.save_integrated(USER, payload2)
        after = _snapshot(conn)
        self.assertEqual(after["qty"], base["qty"])
        self.assertEqual(after["ledger_cnt"], base["ledger_cnt"])
        self.assertEqual(after["active_use"], base["active_use"])
        self.assertEqual(after["ledger_amt"], base["ledger_amt"])


# ---------------------------------------------------------------------------
# 9. 운영 DB 복사본 회귀
# ---------------------------------------------------------------------------
class TestRc09OpsDbCopy(unittest.TestCase):
    def test_ops_db_copy_migrate_and_save_no_damage(self):
        src = _REPO / "orchard_platform.db"
        if not src.is_file():
            self.skipTest("orchard_platform.db 없음")
        fd, tmp_name = tempfile.mkstemp(suffix="_rc_copy.db")
        os.close(fd)
        tmp = Path(tmp_name)
        shutil.copy2(src, tmp)
        mgr_holder: dict = {"mgr": None}

        def _cleanup():
            m = mgr_holder.get("mgr")
            if m and m.conn:
                try:
                    m.conn.close()
                except Exception:
                    pass
            tmp.unlink(missing_ok=True)

        self.addCleanup(_cleanup)

        # before counts (원본 복사본)
        c0 = sqlite3.connect(str(tmp))
        before = {
            "ledger": c0.execute("SELECT COUNT(*) FROM t_ledger").fetchone()[0],
            "use": c0.execute(
                "SELECT COUNT(*) FROM t_pesticide_use"
            ).fetchone()[0]
            if c0.execute(
                "SELECT 1 FROM sqlite_master WHERE name='t_pesticide_use'"
            ).fetchone()
            else 0,
            "detail": c0.execute(
                "SELECT COUNT(*) FROM t_work_detail"
            ).fetchone()[0]
            if c0.execute(
                "SELECT 1 FROM sqlite_master WHERE name='t_work_detail'"
            ).fetchone()
            else 0,
        }
        # 기존 farm
        farm_row = c0.execute(
            "SELECT farm_cd FROM m_farm_info LIMIT 1"
        ).fetchone()
        c0.close()
        if not farm_row:
            self.skipTest("m_farm_info 없음")
        farm = str(farm_row[0])

        mgr = DBManager(str(tmp))
        mgr_holder["mgr"] = mgr
        cols = {
            r[1]
            for r in mgr.conn.execute(
                "PRAGMA table_info(t_pesticide_use)"
            ).fetchall()
        }
        self.assertIn("cancel_yn", cols)

        after_mig_use = mgr.conn.execute(
            "SELECT COUNT(*) FROM t_pesticide_use"
        ).fetchone()[0]
        self.assertEqual(int(after_mig_use), int(before["use"]))

        rc_dt = "2020-01-02"
        rc_wid = "20200102-01"
        item = mgr.conn.execute(
            "SELECT item_id, qty_piece FROM m_pesticide_item "
            "WHERE farm_cd=? AND use_yn='Y' LIMIT 1",
            (farm,),
        ).fetchone()
        if not item:
            self.skipTest("농약 품목 없음")
        item_id = int(item[0])
        qty_before = int(item[1] or 0)
        if qty_before < 2:
            self.skipTest("재고 부족")

        orig_size = src.stat().st_size
        orig_mtime = src.stat().st_mtime

        _clear_slip_cache()
        svc = WorkLogIntegratedSaveService(mgr, farm)
        payload = WorkLogSavePayload(
            master=MasterDto(work_dt=rc_dt, day_of_week="목"),
            works=[
                WorkDetailDto(
                    work_id=rc_wid,
                    work_mid_cd="WK010200",
                    work_mid_nm="방제",
                    pesticide_lines=[
                        PesticideLineDto(
                            item_id=item_id,
                            use_qty=1,
                            item_nm_snapshot="rc",
                        )
                    ],
                )
            ],
            labor_work_id=rc_wid,
            expense_work_id=rc_wid,
            labor_rows=[],
            expense_rows=[],
            worker_nm=USER,
            worker_id=USER,
        )
        svc.save_integrated(USER, payload)
        qty_after = int(
            mgr.conn.execute(
                "SELECT qty_piece FROM m_pesticide_item WHERE item_id=?",
                (item_id,),
            ).fetchone()[0]
        )
        self.assertEqual(qty_after, qty_before - 1)
        use_after = mgr.conn.execute(
            "SELECT COUNT(*) FROM t_pesticide_use"
        ).fetchone()[0]
        self.assertEqual(int(use_after), int(before["use"]) + 1)
        self.assertEqual(src.stat().st_size, orig_size)
        self.assertEqual(src.stat().st_mtime, orig_mtime)
        mgr.conn.close()
        mgr_holder["mgr"] = None


# ---------------------------------------------------------------------------
# 10. 장애 복구
# ---------------------------------------------------------------------------
class TestRc10CrashRecovery(unittest.TestCase):
    def test_exception_mid_save_leaves_no_partial(self):
        conn, path = _make_db()
        self.addCleanup(lambda: (conn.close(), path.unlink(missing_ok=True)))
        db = _DbShim(conn)
        svc = WorkLogIntegratedSaveService(db, FARM)
        _clear_slip_cache()
        svc.save_integrated(USER, _base_payload(pest_qty=4))
        before = _snapshot(conn)

        real = PesticideManager.save_and_apply_use_on_cursor

        def boom(*a, **kw):
            raise RuntimeError("simulated crash")

        # 교체 중 크래시
        use_id = int(
            conn.execute(
                "SELECT use_id FROM t_pesticide_use WHERE work_id=?", (WORK_ID,)
            ).fetchone()[0]
        )
        with patch.object(PesticideManager, "save_and_apply_use_on_cursor", boom):
            r = svc.replace_pesticide_use(
                USER,
                use_id,
                PesticideReplacePayload(
                    use_dt=WORK_DT,
                    work_id=WORK_ID,
                    lines=[
                        PesticideLineDto(
                            item_id=1, use_qty=1, item_nm_snapshot="테스트약"
                        )
                    ],
                ),
            )
        self.assertFalse(r.ok)
        self.assertEqual(_snapshot(conn), before)

        # 재연결 시뮬레이션
        conn2 = sqlite3.connect(str(path))
        conn2.row_factory = sqlite3.Row
        snap2 = _snapshot(conn2)
        conn2.close()
        self.assertEqual(snap2["qty"], before["qty"])
        self.assertEqual(snap2["active_use"], before["active_use"])
        self.assertEqual(snap2["ledger_cnt"], before["ledger_cnt"])
        self.assertEqual(snap2["cancel_use"], before["cancel_use"])


if __name__ == "__main__":
    unittest.main()
