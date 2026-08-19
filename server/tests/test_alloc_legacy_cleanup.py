# -*- coding: utf-8 -*-
"""T-ALLOC-PREFLIGHT / T-ALLOC-LEGACY — DEC-015 A안."""

from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve()
_SERVER = _HERE.parents[1]
_ROOT = _HERE.parents[2]
for p in (_SERVER, _ROOT):
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)

from core.order_alloc_constants import (  # noqa: E402
    IO_TYPE_AUDIT,
    IO_TYPE_CANCEL_HOLD,
    IO_TYPE_HOLD,
    LEGACY_HOLD_CLEANUP_ORDERS,
    TABLE_ORDER_ALLOC,
)
from core.order_alloc_legacy_cleanup import (  # noqa: E402
    LegacyHoldCleanupError,
    build_legacy_audit_remark,
    release_legacy_reserved_lock,
)
from core.order_alloc_migrate import (  # noqa: E402
    OrderAllocMigrateBlocked,
    ensure_order_alloc_schema,
)
from core.order_ship_constants import SALES_STATUS_CONFIRMED  # noqa: E402

FARM = "OR001"


def _open() -> tuple[Path, sqlite3.Connection]:
    fd, name = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    path = Path(name)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE t_order_master (
            order_no TEXT PRIMARY KEY, farm_cd TEXT, sales_status TEXT
        );
        CREATE TABLE t_order_detail (
            order_detail_id TEXT PRIMARY KEY, order_no TEXT, farm_cd TEXT, qty REAL
        );
        CREATE TABLE t_sales_master (
            sales_no TEXT, farm_cd TEXT, order_no TEXT, sales_status TEXT,
            PRIMARY KEY (sales_no, farm_cd)
        );
        CREATE TABLE t_sales_detail (
            sale_detail_no TEXT, sales_no TEXT, farm_cd TEXT, qty REAL,
            PRIMARY KEY (sale_detail_no, farm_cd)
        );
        CREATE TABLE t_stock_master (
            stock_seq INTEGER PRIMARY KEY,
            farm_cd TEXT, item_cd TEXT, variety_cd TEXT, harvest_year TEXT,
            grade_cd TEXT, size_cd TEXT, weight REAL,
            in_qty REAL, out_qty REAL, reserved_qty REAL,
            mod_id TEXT, mod_dt TEXT
        );
        CREATE TABLE t_stock_log (
            log_seq INTEGER PRIMARY KEY AUTOINCREMENT,
            farm_cd TEXT, item_cd TEXT, variety_cd TEXT, harvest_year TEXT,
            grade_cd TEXT, size_cd TEXT, weight REAL,
            io_type TEXT, qty REAL, remark TEXT, reg_id TEXT, reg_dt TEXT,
            stock_seq INTEGER, ref_type TEXT, ref_id TEXT
        );
        """
    )
    conn.commit()
    return path, conn


def _seed_legacy(conn: sqlite3.Connection, *, reserved: float = 103.0) -> None:
    conn.execute(
        """
        INSERT INTO t_stock_master (
            stock_seq, farm_cd, item_cd, variety_cd, harvest_year, grade_cd, size_cd,
            weight, in_qty, out_qty, reserved_qty
        ) VALUES (156, ?, 'FR010100', 'FR010101', '2025', 'GR010200', 'FR020101',
                  7.5, 603, 231, ?)
        """,
        (FARM, reserved),
    )
    seq = 1
    for order_no, qty in LEGACY_HOLD_CLEANUP_ORDERS:
        conn.execute(
            "INSERT INTO t_order_detail (order_detail_id, order_no, farm_cd, qty) VALUES (?,?,?,?)",
            (f"{order_no}-01", order_no, FARM, qty),
        )
        sno = f"S{seq}"
        conn.execute(
            "INSERT INTO t_sales_master (sales_no, farm_cd, order_no, sales_status) VALUES (?,?,?,?)",
            (sno, FARM, order_no, SALES_STATUS_CONFIRMED),
        )
        conn.execute(
            "INSERT INTO t_sales_detail (sale_detail_no, sales_no, farm_cd, qty) VALUES (?,?,?,?)",
            (f"{sno}-S01", sno, FARM, qty),
        )
        conn.execute(
            """
            INSERT INTO t_stock_log (
                farm_cd, item_cd, variety_cd, harvest_year, grade_cd, size_cd, weight,
                io_type, qty, remark, reg_id, reg_dt
            ) VALUES (?, 'FR010100', 'FR010101', '2025', 'GR010200', 'FR020101', 7.5,
                      ?, ?, '주문예약:'||?, 'T', 'x')
            """,
            (FARM, IO_TYPE_HOLD, qty, order_no),
        )
        seq += 1
    conn.execute(
        """
        INSERT INTO t_stock_log (
            farm_cd, item_cd, variety_cd, harvest_year, grade_cd, size_cd, weight,
            io_type, qty, remark, reg_id, reg_dt
        ) VALUES (?, 'FR010100', 'FR010101', '2025', 'GR010200', 'FR020101', 7.5,
                  ?, 19, '주문수정전 복구:ORD20260301-002', 'T', 'x')
        """,
        (FARM, IO_TYPE_CANCEL_HOLD),
    )
    conn.commit()


class AllocPreflightTest(unittest.TestCase):
    def tearDown(self) -> None:
        if getattr(self, "conn", None):
            self.conn.close()
        if getattr(self, "path", None) and self.path.is_file():
            self.path.unlink(missing_ok=True)

    def test_t_alloc_preflight_01_reserved_blocks(self) -> None:
        self.path, self.conn = _open()
        _seed_legacy(self.conn, reserved=103)
        with self.assertRaises(OrderAllocMigrateBlocked):
            ensure_order_alloc_schema(self.conn, skip_preflight=False)

    def test_t_alloc_preflight_02_historical_hold_ok(self) -> None:
        self.path, self.conn = _open()
        _seed_legacy(self.conn, reserved=0)
        stats = ensure_order_alloc_schema(self.conn, skip_preflight=False)
        self.assertTrue(stats["ok"])
        self.assertGreater(stats["preflight"]["hold_logs"], 0)

    def test_t_alloc_mig_03_04_05_schema_no_backfill(self) -> None:
        self.path, self.conn = _open()
        _seed_legacy(self.conn, reserved=0)
        ensure_order_alloc_schema(self.conn, skip_preflight=False)
        self.assertTrue(
            self.conn.execute(
                "SELECT 1 FROM sqlite_master WHERE name=?",
                (TABLE_ORDER_ALLOC,),
            ).fetchone()
        )
        n = self.conn.execute(f"SELECT COUNT(*) FROM {TABLE_ORDER_ALLOC}").fetchone()[0]
        self.assertEqual(n, 0)
        cols = {r[1] for r in self.conn.execute("PRAGMA table_info(t_order_detail)")}
        self.assertIn("allocated_qty", cols)
        zeros = self.conn.execute(
            "SELECT COUNT(*) FROM t_order_detail WHERE COALESCE(allocated_qty, 0) <> 0"
        ).fetchone()[0]
        self.assertEqual(zeros, 0)


class AllocLegacyCleanupTest(unittest.TestCase):
    def tearDown(self) -> None:
        if getattr(self, "conn", None):
            self.conn.close()
        if getattr(self, "path", None) and self.path.is_file():
            self.path.unlink(missing_ok=True)

    def test_t_alloc_legacy_01_confirmed_sum(self) -> None:
        from core.order_alloc_legacy_cleanup import verify_legacy_confirmed_lock

        self.path, self.conn = _open()
        _seed_legacy(self.conn)
        verify_legacy_confirmed_lock(self.conn.cursor())

    def test_t_alloc_legacy_02_tx_release_audit(self) -> None:
        self.path, self.conn = _open()
        _seed_legacy(self.conn)
        hold_n = self.conn.execute(
            "SELECT COUNT(*) FROM t_stock_log WHERE io_type=?", (IO_TYPE_HOLD,)
        ).fetchone()[0]
        out = release_legacy_reserved_lock(self.conn, user_id="T")
        self.assertTrue(out["ok"])
        rsv = self.conn.execute(
            "SELECT reserved_qty FROM t_stock_master WHERE stock_seq=156"
        ).fetchone()[0]
        self.assertEqual(rsv, 0)
        aud = self.conn.execute(
            "SELECT COUNT(*) FROM t_stock_log WHERE io_type=? AND stock_seq=156",
            (IO_TYPE_AUDIT,),
        ).fetchone()[0]
        self.assertEqual(aud, 1)
        remark = self.conn.execute(
            "SELECT remark FROM t_stock_log WHERE io_type=?", (IO_TYPE_AUDIT,)
        ).fetchone()[0]
        self.assertIn("ORD20260228-001", remark)
        self.assertIn("Stage6", remark)
        self.assertEqual(
            self.conn.execute(
                "SELECT COUNT(*) FROM t_stock_log WHERE io_type=?", (IO_TYPE_HOLD,)
            ).fetchone()[0],
            hold_n,
        )

    def test_t_alloc_legacy_03_audit_fail_rollback(self) -> None:
        self.path, self.conn = _open()
        _seed_legacy(self.conn)
        self.conn.execute("DROP TABLE t_stock_log")
        self.conn.commit()
        with self.assertRaises(Exception):
            release_legacy_reserved_lock(self.conn, user_id="T")
        rsv = self.conn.execute(
            "SELECT reserved_qty FROM t_stock_master WHERE stock_seq=156"
        ).fetchone()[0]
        self.assertEqual(rsv, 103)

    def test_t_alloc_legacy_04_hold_untouched(self) -> None:
        self.path, self.conn = _open()
        _seed_legacy(self.conn)
        before = [
            tuple(r)
            for r in self.conn.execute(
                "SELECT log_seq, io_type, qty, remark FROM t_stock_log "
                "WHERE io_type IN (?, ?) ORDER BY log_seq",
                (IO_TYPE_HOLD, IO_TYPE_CANCEL_HOLD),
            )
        ]
        release_legacy_reserved_lock(self.conn, user_id="T")
        after = [
            tuple(r)
            for r in self.conn.execute(
                "SELECT log_seq, io_type, qty, remark FROM t_stock_log "
                "WHERE io_type IN (?, ?) ORDER BY log_seq",
                (IO_TYPE_HOLD, IO_TYPE_CANCEL_HOLD),
            )
        ]
        self.assertEqual(before, after)

    def test_remark_builder(self) -> None:
        text = build_legacy_audit_remark()
        self.assertIn("stock_seq=156", text)
        self.assertIn("qty=103", text)


if __name__ == "__main__":
    unittest.main()
