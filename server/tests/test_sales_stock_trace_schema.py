# -*- coding: utf-8 -*-
"""T-S5C-DDL-01~06 Stage 5C 추적 컬럼 멱등 ALTER."""

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

from core.sales_stock_trace_schema import (  # noqa: E402
    ensure_sales_stock_trace_schema,
)

FARM = "OR001"
# 실운영 상품 키: 과수 FR02 · weight kg 숫자 (SZ01 코드를 size_cd에 넣지 않음)
SIZE_DAI = "FR020102"
WEIGHT_KG = 15.0
VARIETY = "FR010101"
GRADE = "GR010100"
ITEM_PRODUCT = "FR010100"


def _cols(conn: sqlite3.Connection, table: str) -> set[str]:
    return {str(r[1]) for r in conn.execute(f"PRAGMA table_info({table})")}


def _open() -> tuple[Path, sqlite3.Connection]:
    fd, name = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    path = Path(name)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return path, conn


class SalesStockTraceSchemaTest(unittest.TestCase):
    def tearDown(self) -> None:
        conn = getattr(self, "conn", None)
        path = getattr(self, "path", None)
        if conn is not None:
            conn.close()
        if path is not None and path.is_file():
            path.unlink(missing_ok=True)

    def _base_sales_log(self, conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            CREATE TABLE t_sales_master (
                sales_no TEXT NOT NULL,
                farm_cd TEXT NOT NULL,
                sales_dt TEXT,
                sales_status TEXT,
                PRIMARY KEY (sales_no, farm_cd)
            );
            CREATE TABLE t_sales_detail (
                sale_detail_no TEXT NOT NULL,
                sales_no TEXT NOT NULL,
                farm_cd TEXT NOT NULL,
                order_detail_id TEXT,
                item_cd TEXT,
                variety_cd TEXT,
                grade_cd TEXT,
                size_cd TEXT,
                qty REAL DEFAULT 0,
                PRIMARY KEY (sale_detail_no, farm_cd)
            );
            CREATE TABLE t_stock_log (
                log_seq INTEGER PRIMARY KEY AUTOINCREMENT,
                farm_cd TEXT NOT NULL,
                item_cd TEXT,
                variety_cd TEXT,
                harvest_year TEXT,
                grade_cd TEXT,
                size_cd TEXT,
                weight REAL,
                io_type TEXT NOT NULL,
                qty REAL NOT NULL,
                remark TEXT,
                reg_id TEXT,
                reg_dt TEXT
            );
            """
        )

    def test_t_s5c_ddl_01_adds_four_columns(self) -> None:
        self.path, self.conn = _open()
        self._base_sales_log(self.conn)
        self.conn.commit()
        stats = ensure_sales_stock_trace_schema(self.conn)
        self.assertTrue(stats["ok"])
        self.assertEqual(
            set(stats["columns"]),
            {
                "t_sales_detail.stock_seq",
                "t_stock_log.stock_seq",
                "t_stock_log.ref_type",
                "t_stock_log.ref_id",
            },
        )
        self.assertIn("stock_seq", _cols(self.conn, "t_sales_detail"))
        log_cols = _cols(self.conn, "t_stock_log")
        self.assertTrue({"stock_seq", "ref_type", "ref_id"} <= log_cols)

    def test_t_s5c_ddl_02_idempotent(self) -> None:
        self.path, self.conn = _open()
        self._base_sales_log(self.conn)
        self.conn.commit()
        first = ensure_sales_stock_trace_schema(self.conn)
        second = ensure_sales_stock_trace_schema(self.conn)
        self.assertTrue(first["ok"])
        self.assertTrue(second["ok"])
        self.assertEqual(second["columns"], [])
        self.assertEqual(len(_cols(self.conn, "t_sales_detail") & {"stock_seq"}), 1)

    def test_t_s5c_ddl_03_legacy_sales_detail_null(self) -> None:
        self.path, self.conn = _open()
        self._base_sales_log(self.conn)
        self.conn.execute(
            """
            INSERT INTO t_sales_master (sales_no, farm_cd, sales_dt, sales_status)
            VALUES ('20260819-01', ?, '2026-08-19', 'CONFIRMED')
            """,
            (FARM,),
        )
        self.conn.execute(
            """
            INSERT INTO t_sales_detail (
                sale_detail_no, sales_no, farm_cd, order_detail_id,
                item_cd, variety_cd, grade_cd, size_cd, qty
            ) VALUES ('20260819-01-S01', '20260819-01', ?, 'OD001',
                      ?, ?, ?, ?, 6)
            """,
            (FARM, ITEM_PRODUCT, VARIETY, GRADE, SIZE_DAI),
        )
        self.conn.commit()
        ensure_sales_stock_trace_schema(self.conn)
        row = self.conn.execute(
            "SELECT stock_seq, size_cd, qty FROM t_sales_detail WHERE sale_detail_no = ?",
            ("20260819-01-S01",),
        ).fetchone()
        self.assertIsNone(row["stock_seq"])
        self.assertEqual(row["size_cd"], SIZE_DAI)
        self.assertEqual(float(row["qty"]), 6.0)

    def test_t_s5c_ddl_04_legacy_stock_log_null(self) -> None:
        self.path, self.conn = _open()
        self._base_sales_log(self.conn)
        self.conn.execute(
            """
            INSERT INTO t_stock_log (
                farm_cd, item_cd, variety_cd, harvest_year, grade_cd, size_cd,
                weight, io_type, qty, remark, reg_id
            ) VALUES (?, ?, ?, '2026', ?, ?, ?, 'IN', 10, '선별생산 (다이통합)', 'T')
            """,
            (FARM, ITEM_PRODUCT, VARIETY, GRADE, SIZE_DAI, WEIGHT_KG),
        )
        self.conn.commit()
        ensure_sales_stock_trace_schema(self.conn)
        row = self.conn.execute(
            "SELECT stock_seq, ref_type, ref_id, weight FROM t_stock_log"
        ).fetchone()
        self.assertIsNone(row["stock_seq"])
        self.assertIsNone(row["ref_type"])
        self.assertIsNone(row["ref_id"])
        self.assertAlmostEqual(float(row["weight"]), WEIGHT_KG)

    def test_t_s5c_ddl_05_draft_stock_seq_null(self) -> None:
        self.path, self.conn = _open()
        self._base_sales_log(self.conn)
        ensure_sales_stock_trace_schema(self.conn)
        self.conn.execute(
            """
            INSERT INTO t_sales_master (sales_no, farm_cd, sales_dt, sales_status)
            VALUES ('20260819-02', ?, '2026-08-19', 'DRAFT')
            """,
            (FARM,),
        )
        self.conn.execute(
            """
            INSERT INTO t_sales_detail (
                sale_detail_no, sales_no, farm_cd, size_cd, qty, stock_seq
            ) VALUES ('20260819-02-S01', '20260819-02', ?, ?, 3, NULL)
            """,
            (FARM, SIZE_DAI),
        )
        self.conn.commit()
        row = self.conn.execute(
            "SELECT stock_seq FROM t_sales_detail WHERE sale_detail_no = ?",
            ("20260819-02-S01",),
        ).fetchone()
        self.assertIsNone(row["stock_seq"])

    def test_t_s5c_ddl_06_stock_seq_and_natural_key_unique(self) -> None:
        self.path, self.conn = _open()
        self.conn.executescript(
            """
            CREATE TABLE t_stock_master (
                stock_seq INTEGER PRIMARY KEY AUTOINCREMENT,
                farm_cd TEXT NOT NULL, wh_cd TEXT NOT NULL, item_cd TEXT NOT NULL,
                variety_cd TEXT NOT NULL, grade_cd TEXT DEFAULT 'NONE',
                size_cd TEXT NOT NULL, weight REAL DEFAULT 0, harvest_year TEXT NOT NULL,
                in_qty REAL DEFAULT 0, reserved_qty REAL DEFAULT 0, out_qty REAL DEFAULT 0,
                storage_dt TEXT
            );
            CREATE UNIQUE INDEX idx_stock_master_unique
            ON t_stock_master(
                farm_cd, wh_cd, item_cd, variety_cd, grade_cd,
                size_cd, weight, harvest_year, storage_dt
            );
            CREATE TABLE t_sales_detail (
                sale_detail_no TEXT PRIMARY KEY, sales_no TEXT, farm_cd TEXT
            );
            CREATE TABLE t_stock_log (
                log_seq INTEGER PRIMARY KEY AUTOINCREMENT, farm_cd TEXT, io_type TEXT, qty REAL
            );
            """
        )
        self.conn.execute(
            """
            INSERT INTO t_stock_master (
                farm_cd, wh_cd, item_cd, variety_cd, grade_cd, size_cd,
                weight, harvest_year, storage_dt, in_qty
            ) VALUES (?, 'WH01', ?, ?, ?, ?, ?, '2026', '2026-08-01', 20)
            """,
            (FARM, ITEM_PRODUCT, VARIETY, GRADE, SIZE_DAI, WEIGHT_KG),
        )
        self.conn.commit()
        ensure_sales_stock_trace_schema(self.conn)
        row = self.conn.execute(
            """
            SELECT stock_seq FROM t_stock_master
            WHERE farm_cd=? AND wh_cd='WH01' AND item_cd=? AND variety_cd=?
              AND grade_cd=? AND size_cd=? AND ABS(weight-?)<1e-9
              AND harvest_year='2026' AND storage_dt='2026-08-01'
            """,
            (FARM, ITEM_PRODUCT, VARIETY, GRADE, SIZE_DAI, WEIGHT_KG),
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertGreater(int(row["stock_seq"]), 0)
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                """
                INSERT INTO t_stock_master (
                    farm_cd, wh_cd, item_cd, variety_cd, grade_cd, size_cd,
                    weight, harvest_year, storage_dt, in_qty
                ) VALUES (?, 'WH01', ?, ?, ?, ?, ?, '2026', '2026-08-01', 1)
                """,
                (FARM, ITEM_PRODUCT, VARIETY, GRADE, SIZE_DAI, WEIGHT_KG),
            )


if __name__ == "__main__":
    unittest.main()
