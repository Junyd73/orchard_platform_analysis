# -*- coding: utf-8 -*-
"""Stage 6 보완 2C — t_sales_delivery.dlvry_group_no / ship_fee 멱등 ALTER."""

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

    def tearDown(self) -> None:
        self.conn.close()
        self.path.unlink(missing_ok=True)

    def test_idempotent_add_columns_keeps_rows(self) -> None:
        first = ensure_sales_delivery_schema(self.conn)
        self.assertTrue(first["ok"])
        self.assertIn("t_sales_delivery.dlvry_group_no", first["columns"])
        self.assertIn("t_sales_delivery.ship_fee", first["columns"])
        second = ensure_sales_delivery_schema(self.conn)
        self.assertTrue(second["ok"])
        self.assertEqual(second["columns"], [])
        row = self.conn.execute(
            "SELECT rcv_name, dlvry_group_no, ship_fee FROM t_sales_delivery WHERE dlvry_no='X-D001'"
        ).fetchone()
        self.assertEqual(row[0], "기존")
        self.assertIsNone(row[1])
        self.assertIsNone(row[2])


if __name__ == "__main__":
    unittest.main()
