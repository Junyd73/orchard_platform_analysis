# -*- coding: utf-8 -*-
"""t_sales_delivery.dlvry_group_no / ship_fee / order_dlvry_id 멱등 ALTER.

Stage 6 보완 2C + Step3 §22(주문 배송지 연결).
"""

from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.sales_delivery_schema import ensure_sales_delivery_schema  # noqa: E402


class SalesDeliverySchemaTest(unittest.TestCase):
    def setUp(self) -> None:
        fd, name = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.path = Path(name)
        self.conn = sqlite3.connect(str(self.path))

    def tearDown(self) -> None:
        self.conn.close()
        self.path.unlink(missing_ok=True)

    def _create_base_delivery(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE t_sales_delivery (
                dlvry_no TEXT, sale_detail_no TEXT, sales_no TEXT, farm_cd TEXT,
                rcv_name TEXT, rcv_tel TEXT, rcv_addr TEXT,
                dlvry_qty REAL, dlvry_msg TEXT, reg_id TEXT,
                PRIMARY KEY (dlvry_no, farm_cd)
            );
            INSERT INTO t_sales_delivery (
                dlvry_no, sale_detail_no, sales_no, farm_cd, rcv_name, dlvry_qty, reg_id
            ) VALUES ('X-D001', 'X-S01', 'X', 'OR001', '기존', 1, 'T');
            """
        )
        self.conn.commit()

    def test_s1_table_missing_ok_false(self) -> None:
        stats = ensure_sales_delivery_schema(self.conn)
        self.assertFalse(stats["ok"])
        self.assertEqual(stats["reason"], "table_missing")
        self.assertEqual(stats["columns"], [])

    def _columns(self) -> set[str]:
        return {
            str(r[1]).strip().lower()
            for r in self.conn.execute("PRAGMA table_info(t_sales_delivery)")
        }

    def test_s2_add_all_columns(self) -> None:
        self._create_base_delivery()
        first = ensure_sales_delivery_schema(self.conn)
        self.assertTrue(first["ok"])
        self.assertIn("t_sales_delivery.dlvry_group_no", first["columns"])
        self.assertIn("t_sales_delivery.ship_fee", first["columns"])
        self.assertIn("t_sales_delivery.order_dlvry_id", first["columns"])
        self.assertIn("order_dlvry_id", self._columns())

    def test_s3_add_missing_columns_only(self) -> None:
        """이미 있는 dlvry_group_no는 건너뛰고 ship_fee·order_dlvry_id만 추가."""
        self.conn.executescript(
            """
            CREATE TABLE t_sales_delivery (
                dlvry_no TEXT, sale_detail_no TEXT, sales_no TEXT, farm_cd TEXT,
                rcv_name TEXT, dlvry_qty REAL, reg_id TEXT, dlvry_group_no TEXT,
                PRIMARY KEY (dlvry_no, farm_cd)
            );
            """
        )
        self.conn.commit()
        stats = ensure_sales_delivery_schema(self.conn)
        self.assertTrue(stats["ok"])
        self.assertEqual(
            stats["columns"],
            ["t_sales_delivery.ship_fee", "t_sales_delivery.order_dlvry_id"],
        )

    def test_s3b_add_order_dlvry_id_only(self) -> None:
        """2C까지 적용된 스키마 → Step3 컬럼 1개만 추가."""
        self.conn.executescript(
            """
            CREATE TABLE t_sales_delivery (
                dlvry_no TEXT, sale_detail_no TEXT, sales_no TEXT, farm_cd TEXT,
                rcv_name TEXT, dlvry_qty REAL, reg_id TEXT,
                dlvry_group_no TEXT, ship_fee REAL,
                PRIMARY KEY (dlvry_no, farm_cd)
            );
            """
        )
        self.conn.commit()
        stats = ensure_sales_delivery_schema(self.conn)
        self.assertTrue(stats["ok"])
        self.assertEqual(stats["columns"], ["t_sales_delivery.order_dlvry_id"])

    def test_s4_s5_idempotent_when_present(self) -> None:
        self._create_base_delivery()
        ensure_sales_delivery_schema(self.conn)
        second = ensure_sales_delivery_schema(self.conn)
        self.assertTrue(second["ok"])
        self.assertEqual(second["columns"], [])
        third = ensure_sales_delivery_schema(self.conn)
        self.assertTrue(third["ok"])
        self.assertEqual(third["columns"], [])
        row = self.conn.execute(
            """
            SELECT rcv_name, dlvry_group_no, ship_fee, order_dlvry_id
            FROM t_sales_delivery WHERE dlvry_no='X-D001'
            """
        ).fetchone()
        # backfill 없음: 기존 행은 신규 컬럼 전부 NULL 유지
        self.assertEqual(row[0], "기존")
        self.assertIsNone(row[1])
        self.assertIsNone(row[2])
        self.assertIsNone(row[3])


if __name__ == "__main__":
    unittest.main()
