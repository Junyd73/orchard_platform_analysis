# -*- coding: utf-8 -*-
"""재고 증감 — 가용 한도 · 사유 코드 · 판매 OUT과 분리."""

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

from core.stock_adjust_constants import (  # noqa: E402
    IO_TYPE_IN,
    IO_TYPE_OUT,
    PARENT_ADJUST_REASON,
    REASON_COUNT_DIFF,
    REASON_DAMAGE,
    REASON_DISPOSE,
    REASON_GIFT,
    REASON_OTHER,
    REASON_RETURN,
    REF_TYPE_ADJUST,
    reason_allows_io,
)
from core.stock_adjust_service import (  # noqa: E402
    StockAdjustError,
    StockAdjustIn,
    StockAdjustService,
    ensure_adjust_reason_codes,
)

FARM = "OR001"


def _open() -> tuple[Path, sqlite3.Connection]:
    fd, name = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    path = Path(name)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE m_common_code (
            farm_cd TEXT, code_cd TEXT, code_nm TEXT, parent_cd TEXT, use_yn TEXT
        );
        CREATE TABLE t_stock_master (
            stock_seq INTEGER PRIMARY KEY AUTOINCREMENT,
            farm_cd TEXT, wh_cd TEXT, item_cd TEXT, variety_cd TEXT,
            grade_cd TEXT, size_cd TEXT, weight REAL, harvest_year INTEGER,
            storage_dt TEXT, in_qty REAL, out_qty REAL, reserved_qty REAL,
            reg_id TEXT, mod_id TEXT, mod_dt TEXT
        );
        CREATE TABLE t_stock_log (
            log_seq INTEGER PRIMARY KEY AUTOINCREMENT,
            farm_cd TEXT, item_cd TEXT, variety_cd TEXT, harvest_year INTEGER,
            grade_cd TEXT, size_cd TEXT, weight REAL, io_type TEXT, qty REAL,
            remark TEXT, reg_id TEXT, reg_dt TEXT,
            stock_seq INTEGER, ref_type TEXT, ref_id TEXT
        );
        """
    )
    conn.execute(
        """
        INSERT INTO t_stock_master (
            farm_cd, wh_cd, item_cd, variety_cd, grade_cd, size_cd, weight,
            harvest_year, storage_dt, in_qty, out_qty, reserved_qty, reg_id
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (FARM, "WH01", "FR010100", "FR010101", "GR010100", "FR020101", 15,
         2026, "2026-08-01", 10, 0, 3, "T"),
    )
    conn.commit()
    return path, conn


def _payload(**over: object) -> StockAdjustIn:
    data = dict(
        farm_cd=FARM,
        wh_cd="WH01",
        item_cd="FR010100",
        variety_cd="FR010101",
        grade_cd="GR010100",
        size_cd="FR020101",
        weight=15,
        harvest_year=2026,
        storage_dt="2026-08-01",
        io_type=IO_TYPE_OUT,
        qty=2,
        reason_cd=REASON_DISPOSE,
    )
    data.update(over)
    return StockAdjustIn(**data)  # type: ignore[arg-type]


class StockAdjustServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.path, self.conn = _open()
        self.svc = StockAdjustService(self.conn)

    def tearDown(self) -> None:
        self.conn.close()
        self.path.unlink(missing_ok=True)

    def test_ensure_seeds_six_reason_codes(self) -> None:
        ensure_adjust_reason_codes(self.conn, FARM)
        rows = self.conn.execute(
            "SELECT code_cd, code_nm FROM m_common_code WHERE parent_cd=? ORDER BY code_cd",
            (PARENT_ADJUST_REASON,),
        ).fetchall()
        names = {r["code_cd"]: r["code_nm"] for r in rows}
        self.assertEqual(
            names,
            {
                REASON_DISPOSE: "폐기",
                REASON_DAMAGE: "파손",
                REASON_GIFT: "증정",
                REASON_RETURN: "반품",
                REASON_COUNT_DIFF: "실사차이",
                REASON_OTHER: "기타",
            },
        )

    def test_t2_dispose_out(self) -> None:
        self.svc.adjust(_payload(qty=7, reason_cd=REASON_DISPOSE), user_id="U1")
        row = self.conn.execute("SELECT out_qty FROM t_stock_master").fetchone()
        self.assertEqual(row["out_qty"], 7)

    def test_t3_damage_out(self) -> None:
        self.svc.adjust(_payload(reason_cd=REASON_DAMAGE), user_id="U1")
        self.assertEqual(self.conn.execute("SELECT out_qty FROM t_stock_master").fetchone()["out_qty"], 2)

    def test_t4_gift_out(self) -> None:
        self.svc.adjust(_payload(reason_cd=REASON_GIFT), user_id="U1")
        self.assertEqual(self.conn.execute("SELECT out_qty FROM t_stock_master").fetchone()["out_qty"], 2)

    def test_t5_return_in(self) -> None:
        self.svc.adjust(
            _payload(io_type=IO_TYPE_IN, qty=4, reason_cd=REASON_RETURN),
            user_id="U1",
        )
        self.assertEqual(self.conn.execute("SELECT in_qty FROM t_stock_master").fetchone()["in_qty"], 14)

    def test_t6_count_diff_in(self) -> None:
        self.svc.adjust(
            _payload(io_type=IO_TYPE_IN, qty=4, reason_cd=REASON_COUNT_DIFF),
            user_id="U1",
        )
        self.assertEqual(self.conn.execute("SELECT in_qty FROM t_stock_master").fetchone()["in_qty"], 14)

    def test_t7_count_diff_out(self) -> None:
        self.svc.adjust(_payload(reason_cd=REASON_COUNT_DIFF), user_id="U1")
        self.assertEqual(self.conn.execute("SELECT out_qty FROM t_stock_master").fetchone()["out_qty"], 2)

    def test_t8_other_in_and_out(self) -> None:
        self.svc.adjust(_payload(io_type=IO_TYPE_IN, qty=1, reason_cd=REASON_OTHER), user_id="U1")
        self.svc.adjust(_payload(qty=1, reason_cd=REASON_OTHER), user_id="U1")
        row = self.conn.execute("SELECT in_qty, out_qty FROM t_stock_master").fetchone()
        self.assertEqual(row["in_qty"], 11)
        self.assertEqual(row["out_qty"], 1)

    def test_t9_dispose_damage_gift_reject_in(self) -> None:
        for cd in (REASON_DISPOSE, REASON_DAMAGE, REASON_GIFT):
            with self.assertRaises(StockAdjustError) as ctx:
                self.svc.adjust(_payload(io_type=IO_TYPE_IN, qty=1, reason_cd=cd), user_id="U1")
            self.assertEqual(ctx.exception.code, "ADJUST_DIR")

    def test_return_rejects_out(self) -> None:
        with self.assertRaises(StockAdjustError) as ctx:
            self.svc.adjust(_payload(reason_cd=REASON_RETURN), user_id="U1")
        self.assertEqual(ctx.exception.code, "ADJUST_DIR")

    def test_t10_rejects_over_available_with_reserved(self) -> None:
        with self.assertRaises(StockAdjustError) as ctx:
            self.svc.adjust(_payload(qty=8), user_id="U1")
        self.assertEqual(ctx.exception.code, "STOCK_UNAVAILABLE")
        reserved = self.conn.execute("SELECT reserved_qty FROM t_stock_master").fetchone()["reserved_qty"]
        self.assertEqual(reserved, 3)

    def test_t11_log_uses_code_name_not_only_code(self) -> None:
        self.svc.adjust(_payload(qty=2, reason_cd=REASON_DAMAGE), user_id="U1")
        log = self.conn.execute(
            "SELECT io_type, ref_type, ref_id, remark FROM t_stock_log"
        ).fetchone()
        self.assertEqual(log["io_type"], IO_TYPE_OUT)
        self.assertEqual(log["ref_type"], REF_TYPE_ADJUST)
        self.assertEqual(log["ref_id"], REASON_DAMAGE)
        self.assertIn("파손", log["remark"])
        self.assertNotIn("AD010102", log["remark"])

    def test_t11b_count_diff_includes_memo_in_remark(self) -> None:
        self.svc.adjust(
            _payload(io_type=IO_TYPE_IN, qty=2, reason_cd=REASON_COUNT_DIFF, memo="메모텍스트"),
            user_id="U1",
        )
        log = self.conn.execute(
            "SELECT ref_id, remark FROM t_stock_log"
        ).fetchone()
        self.assertEqual(log["ref_id"], REASON_COUNT_DIFF)
        self.assertIn("실사차이", log["remark"])
        self.assertIn("메모텍스트", log["remark"])
        self.assertIn(" · ", log["remark"])

    def test_t14_count_diff_out_respects_reserved(self) -> None:
        # 현재 avail = in(10) - out(0) - reserved(3) = 7
        # 허용 범위 내 감소: OUT 4 (final avail = 3)
        self.svc.adjust(
            _payload(io_type=IO_TYPE_OUT, qty=4, reason_cd=REASON_COUNT_DIFF),
            user_id="U1",
        )
        row = self.conn.execute(
            "SELECT out_qty, reserved_qty FROM t_stock_master"
        ).fetchone()
        self.assertEqual(row["out_qty"], 4)
        self.assertEqual(row["reserved_qty"], 3)

        # 침범 감소: OUT 8 (needed qty > avail 7) -> 실패, reserved 유지
        with self.assertRaises(StockAdjustError) as ctx:
            self.svc.adjust(
                _payload(io_type=IO_TYPE_OUT, qty=8, reason_cd=REASON_COUNT_DIFF),
                user_id="U1",
            )
        self.assertEqual(ctx.exception.code, "STOCK_UNAVAILABLE")
        reserved = self.conn.execute(
            "SELECT reserved_qty FROM t_stock_master"
        ).fetchone()["reserved_qty"]
        self.assertEqual(reserved, 3)

    def test_t12_pc_dispose_still_uses_core(self) -> None:
        src = (_REPO / "ui" / "pages" / "stock_page.py").read_text(encoding="utf-8")
        self.assertIn("StockAdjustService", src)
        self.assertIn("REASON_DISPOSE", src)
        self.assertIn("dispose_raw_material", src)
        self.assertTrue(reason_allows_io(REASON_DISPOSE, IO_TYPE_OUT))

    def test_t15_pc_audit_history_query_compatible(self) -> None:
        src = (_REPO / "ui" / "pages" / "stock_page.py").read_text(encoding="utf-8")
        self.assertIn("l.io_type = 'AUDIT'", src)
        self.assertIn("l.ref_type", src)
        self.assertIn("l.ref_id", src)
        self.assertIn("REF_TYPE_ADJUST", src)
        self.assertIn("REASON_COUNT_DIFF", src)

    def test_t16_pc_audit_physical_qty_and_increase_allowed(self) -> None:
        src = (_REPO / "ui" / "pages" / "stock_page.py").read_text(encoding="utf-8")
        # diff 계산 기준은 reserved_qty 제외 물리재고(in-out)
        self.assertIn("physical_qty = in_qty - out_qty", src)
        # 증가 실사를 위해 available_qty 상한에 걸리지 않도록 별도 Dialog max 확장
        self.assertIn("QInputDialog.getInt", src)
        self.assertIn("max=99999", src)

    def test_reason_allows_io_map(self) -> None:
        self.assertTrue(reason_allows_io(REASON_DISPOSE, IO_TYPE_OUT))
        self.assertFalse(reason_allows_io(REASON_DISPOSE, IO_TYPE_IN))
        self.assertTrue(reason_allows_io(REASON_RETURN, IO_TYPE_IN))
        self.assertFalse(reason_allows_io(REASON_RETURN, IO_TYPE_OUT))

    def test_by_spec_out_splits_fifo_oldest_first(self) -> None:
        from core.stock_adjust_service import StockAdjustBySpecIn

        self.conn.execute(
            """
            INSERT INTO t_stock_master (
                farm_cd, wh_cd, item_cd, variety_cd, grade_cd, size_cd, weight,
                harvest_year, storage_dt, in_qty, out_qty, reserved_qty, reg_id
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (FARM, "WH01", "FR010100", "FR010101", "GR010100", "FR020101", 15,
             2026, "2026-08-20", 15, 0, 0, "T"),
        )
        self.conn.commit()
        # 기존 row: 2026-08-01 avail=7 (in10-out0-res3)
        out = self.svc.adjust_by_sale_spec(
            StockAdjustBySpecIn(
                farm_cd=FARM,
                wh_cd="WH01",
                item_cd="FR010100",
                variety_cd="FR010101",
                grade_cd="GR010100",
                size_cd="FR020101",
                weight=15,
                harvest_year=2026,
                io_type=IO_TYPE_OUT,
                qty=10,
                reason_cd=REASON_DISPOSE,
            ),
            user_id="U1",
        )
        self.assertTrue(out["ok"])
        rows = self.conn.execute(
            """
            SELECT storage_dt, out_qty, reserved_qty FROM t_stock_master
            WHERE farm_cd=? AND item_cd='FR010100'
            ORDER BY storage_dt ASC
            """,
            (FARM,),
        ).fetchall()
        self.assertEqual(float(rows[0]["out_qty"]), 7.0)  # oldest fully drained available
        self.assertEqual(float(rows[0]["reserved_qty"]), 3.0)  # reserved untouched
        self.assertEqual(float(rows[1]["out_qty"]), 3.0)  # remainder on newer

    def test_by_spec_out_rejects_over_total_available(self) -> None:
        from core.stock_adjust_service import StockAdjustBySpecIn, StockAdjustError

        with self.assertRaises(StockAdjustError) as ctx:
            self.svc.adjust_by_sale_spec(
                StockAdjustBySpecIn(
                    farm_cd=FARM,
                    wh_cd="WH01",
                    item_cd="FR010100",
                    variety_cd="FR010101",
                    grade_cd="GR010100",
                    size_cd="FR020101",
                    weight=15,
                    harvest_year=2026,
                    io_type=IO_TYPE_OUT,
                    qty=8,
                    reason_cd=REASON_DISPOSE,
                ),
                user_id="U1",
            )
        self.assertEqual(ctx.exception.code, "STOCK_UNAVAILABLE")

    def test_by_spec_in_targets_newest_existing_lot(self) -> None:
        from core.stock_adjust_service import StockAdjustBySpecIn

        self.conn.execute(
            """
            INSERT INTO t_stock_master (
                farm_cd, wh_cd, item_cd, variety_cd, grade_cd, size_cd, weight,
                harvest_year, storage_dt, in_qty, out_qty, reserved_qty, reg_id
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (FARM, "WH01", "FR010100", "FR010101", "GR010100", "FR020101", 15,
             2026, "2026-08-20", 5, 0, 0, "T"),
        )
        self.conn.commit()
        self.svc.adjust_by_sale_spec(
            StockAdjustBySpecIn(
                farm_cd=FARM,
                wh_cd="WH01",
                item_cd="FR010100",
                variety_cd="FR010101",
                grade_cd="GR010100",
                size_cd="FR020101",
                weight=15,
                harvest_year=2026,
                io_type=IO_TYPE_IN,
                qty=4,
                reason_cd=REASON_RETURN,
            ),
            user_id="U1",
        )
        rows = {
            str(r["storage_dt"]): float(r["in_qty"])
            for r in self.conn.execute(
                "SELECT storage_dt, in_qty FROM t_stock_master WHERE farm_cd=?",
                (FARM,),
            ).fetchall()
        }
        self.assertEqual(rows["2026-08-01"], 10.0)
        self.assertEqual(rows["2026-08-20"], 9.0)


if __name__ == "__main__":
    unittest.main()
