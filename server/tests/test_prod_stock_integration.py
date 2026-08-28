# -*- coding: utf-8 -*-
"""T-PROD-STOCK-INT-01~08: 생산확정 ↔ 재고조회 연결."""

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

from core.order_allocation_service import OrderAllocationService  # noqa: E402
from core.production_service import (  # noqa: E402
    HarvestConsumptionIn,
    ProductionConfirmIn,
    ProductionError,
    ProductionLineIn,
    ProductionService,
    RawStockConsumptionIn,
)
from core.harvest_consumption_schema import ensure_harvest_consumption_schema  # noqa: E402
from core.sales_stock_trace_schema import ensure_sales_stock_trace_schema  # noqa: E402
from core.stock_constants import (  # noqa: E402
    INPUT_SOURCE_HARVEST,
    INPUT_SOURCE_RAW_STOCK,
    ITEM_PRODUCT,
    ITEM_RAW,
    PROD_TYPE_PACK,
    REMARK_PACK_IN,
    REMARK_RAW_OUT,
)
from core.work_log_constants import WORK_STATUS_DONE  # noqa: E402

FARM = "OR001"
WH = "WH01"
VARIETY = "FR010101"
GRADE = "GR010100"
GRADE2 = "GR010200"
SIZE = "FR020101"
RAW_DAE = "CT010100"
RAW_SO = "CT010200"
HARVEST_MID = "WK010300"
WORK_HARVEST = "W-H-INT"


def _build_db() -> tuple[sqlite3.Connection, Path]:
    fd, path_s = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = sqlite3.connect(path_s)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        f"""
        CREATE TABLE m_common_code (
            farm_cd TEXT, code_cd TEXT, code_nm TEXT, parent_cd TEXT
        );
        INSERT INTO m_common_code VALUES
          ('{FARM}','{VARIETY}','신고','FR010100'),
          ('{FARM}','{GRADE}','특','GR01'),
          ('{FARM}','{GRADE2}','상','GR01'),
          ('{FARM}','{SIZE}','25과','FR020100'),
          ('{FARM}','{RAW_DAE}','대과','CT01'),
          ('{FARM}','{RAW_SO}','소과','CT01'),
          ('{FARM}','{ITEM_PRODUCT}','배 상품',NULL),
          ('{FARM}','{ITEM_RAW}','원물',NULL),
          ('{FARM}','{HARVEST_MID}','수확','WK01'),
          ('{FARM}','{WORK_STATUS_DONE}','완료','WO01');

        CREATE TABLE t_work_detail (
            work_id TEXT PRIMARY KEY,
            work_dt TEXT NOT NULL, farm_cd TEXT NOT NULL,
            work_mid_cd TEXT, variety_cd TEXT,
            harvest_container_qty INTEGER,
            status_cd TEXT, reg_id TEXT, mod_id TEXT, mod_dt TEXT
        );
        INSERT INTO t_work_detail VALUES
          ('{WORK_HARVEST}','2026-08-19','{FARM}','{HARVEST_MID}',
           '{VARIETY}', 12, 'WO010100', 'U1', NULL, NULL);

        CREATE TABLE t_stock_master (
            farm_cd TEXT, wh_cd TEXT, item_cd TEXT, variety_cd TEXT,
            grade_cd TEXT, size_cd TEXT, weight REAL, harvest_year INTEGER,
            storage_dt TEXT, in_qty REAL DEFAULT 0, out_qty REAL DEFAULT 0,
            reserved_qty REAL DEFAULT 0, reg_id TEXT, mod_id TEXT, mod_dt TEXT
        );
        INSERT INTO t_stock_master VALUES
          ('{FARM}','{WH}','{ITEM_RAW}','{VARIETY}','NONE','{RAW_DAE}',20.0,2026,
           '2025-10-01',270,0,0,'U1',NULL,NULL),
          ('{FARM}','{WH}','{ITEM_RAW}','{VARIETY}','NONE','{RAW_SO}',20.0,2026,
           '2025-10-01',390,0,0,'U1',NULL,NULL);

        CREATE TABLE t_stock_log (
            log_seq INTEGER PRIMARY KEY AUTOINCREMENT,
            farm_cd TEXT, item_cd TEXT, variety_cd TEXT, harvest_year INTEGER,
            grade_cd TEXT, size_cd TEXT, weight REAL, io_type TEXT, qty REAL,
            remark TEXT, reg_id TEXT, reg_dt TEXT
        );
        """
    )
    ensure_harvest_consumption_schema(conn)
    ensure_sales_stock_trace_schema(conn)
    conn.commit()
    return conn, Path(path_s)


def _raw(size_cd: str, qty: int) -> RawStockConsumptionIn:
    return RawStockConsumptionIn(
        wh_cd=WH, variety_cd=VARIETY, size_cd=size_cd,
        weight=20.0, harvest_year=2026, storage_dt="2025-10-01", qty=qty,
    )


def _pack_payload(*, raws, lines, src=INPUT_SOURCE_RAW_STOCK, harvest=None, harvest_qty: int = 12):
    harvest_rows: list[HarvestConsumptionIn] = []
    if harvest:
        harvest_rows = [HarvestConsumptionIn(work_id=harvest, qty=harvest_qty)]
    return ProductionConfirmIn(
        farm_cd=FARM,
        prod_type=PROD_TYPE_PACK,
        input_source=src,
        variety_cd=VARIETY,
        wh_cd=WH,
        pack_weight=0.0,
        lines=lines,
        raw_consumptions=raws,
        harvest_consumptions=harvest_rows,
    )


def _avail(svc: OrderAllocationService, item_cd: str, **extra):
    rows = svc.get_available_stock(FARM, item_cd=item_cd, include_zero=True)
    if extra:
        rows = [r for r in rows if all(r.get(k) == v for k, v in extra.items())]
    return rows


class TestProdStockIntegration(unittest.TestCase):
    def setUp(self):
        self.conn, self.path = _build_db()
        self.prod = ProductionService(self.conn)
        self.stock = OrderAllocationService(self.conn)

    def tearDown(self):
        self.conn.close()
        self.path.unlink(missing_ok=True)

    def test_int_01_multi_raw_out_and_product_in(self):
        """T-PROD-STOCK-INT-01: 대과30+소과60 → 240/330, 상품 특10+상5, log 4건."""
        lines = [
            ProductionLineIn(grade_cd=GRADE, size_cd=SIZE, qty=10, weight=15.0),
            ProductionLineIn(grade_cd=GRADE2, size_cd=SIZE, qty=5, weight=15.0),
        ]
        self.prod.confirm("U1", _pack_payload(
            raws=[_raw(RAW_DAE, 30), _raw(RAW_SO, 60)],
            lines=lines,
        ))
        dae = _avail(self.stock, ITEM_RAW, size_cd=RAW_DAE)[0]
        so = _avail(self.stock, ITEM_RAW, size_cd=RAW_SO)[0]
        self.assertEqual(dae["available_qty"], 240.0)
        self.assertEqual(so["available_qty"], 330.0)
        prods = _avail(self.stock, ITEM_PRODUCT)
        by_grade = {r["grade_cd"]: r["real_qty"] for r in prods}
        self.assertEqual(by_grade[GRADE], 10.0)
        self.assertEqual(by_grade[GRADE2], 5.0)
        for r in prods:
            self.assertEqual(r["harvest_year"], 2026)
        logs = self.conn.execute(
            "SELECT io_type, qty, remark FROM t_stock_log ORDER BY log_seq"
        ).fetchall()
        kinds = [(r[0], int(r[1]), r[2]) for r in logs]
        self.assertEqual(kinds.count(("OUT", 30, REMARK_RAW_OUT)), 1)
        self.assertEqual(kinds.count(("OUT", 60, REMARK_RAW_OUT)), 1)
        self.assertEqual(kinds.count(("IN", 10, REMARK_PACK_IN)), 1)
        self.assertEqual(kinds.count(("IN", 5, REMARK_PACK_IN)), 1)

    def test_int_02_zero_qty_not_out(self):
        """T-PROD-STOCK-INT-02: qty=0 원물은 OUT 없음."""
        lines = [ProductionLineIn(grade_cd=GRADE, size_cd=SIZE, qty=10, weight=15.0)]
        self.prod.confirm("U1", _pack_payload(
            raws=[_raw(RAW_DAE, 30), _raw(RAW_SO, 0)],
            lines=lines,
        ))
        self.assertEqual(_avail(self.stock, ITEM_RAW, size_cd=RAW_DAE)[0]["available_qty"], 240.0)
        self.assertEqual(_avail(self.stock, ITEM_RAW, size_cd=RAW_SO)[0]["available_qty"], 390.0)
        so_out = self.conn.execute(
            "SELECT COUNT(*) FROM t_stock_log WHERE item_cd=? AND size_cd=? AND io_type='OUT'",
            (ITEM_RAW, RAW_SO),
        ).fetchone()[0]
        self.assertEqual(so_out, 0)

    def test_int_03_second_raw_exceed_rolls_back(self):
        """T-PROD-STOCK-INT-03: 두 번째 원물 초과 시 전체 rollback."""
        lines = [ProductionLineIn(grade_cd=GRADE, size_cd=SIZE, qty=10, weight=15.0)]
        with self.assertRaises(ProductionError) as ctx:
            self.prod.confirm("U1", _pack_payload(
                raws=[_raw(RAW_DAE, 30), _raw(RAW_SO, 999)],
                lines=lines,
            ))
        self.assertEqual(ctx.exception.code, "RAW_EXCEED")
        self.assertEqual(_avail(self.stock, ITEM_RAW, size_cd=RAW_DAE)[0]["available_qty"], 270.0)
        self.assertEqual(_avail(self.stock, ITEM_RAW, size_cd=RAW_SO)[0]["available_qty"], 390.0)
        self.assertEqual(len(_avail(self.stock, ITEM_PRODUCT)), 0)

    def test_int_04_harvest_no_raw_out(self):
        """T-PROD-STOCK-INT-04: HARVEST는 원물 OUT 없음 + 상품 IN."""
        lines = [ProductionLineIn(grade_cd=GRADE, size_cd=SIZE, qty=8, weight=15.0)]
        self.prod.confirm("U1", _pack_payload(
            raws=[],
            lines=lines,
            src=INPUT_SOURCE_HARVEST,
            harvest=WORK_HARVEST,
        ))
        self.assertEqual(_avail(self.stock, ITEM_RAW, size_cd=RAW_DAE)[0]["available_qty"], 270.0)
        self.assertEqual(_avail(self.stock, ITEM_PRODUCT)[0]["real_qty"], 8.0)

    def test_int_05_get_available_stock_after_confirm(self):
        """T-PROD-STOCK-INT-05: 확정 직후 get_available_stock이 최신."""
        lines = [ProductionLineIn(grade_cd=GRADE, size_cd=SIZE, qty=10, weight=15.0)]
        self.prod.confirm("U1", _pack_payload(raws=[_raw(RAW_DAE, 30)], lines=lines))
        row = _avail(self.stock, ITEM_PRODUCT)[0]
        self.assertEqual(row["real_qty"], 10.0)
        self.assertEqual(row["reserved_qty"], 0.0)
        self.assertEqual(row["available_qty"], 10.0)

    def test_int_06_hold_reduces_available(self):
        """T-PROD-STOCK-INT-06: 생산 row에 HOLD(reserved) 후 가용 감소."""
        lines = [ProductionLineIn(grade_cd=GRADE, size_cd=SIZE, qty=10, weight=15.0)]
        self.prod.confirm("U1", _pack_payload(raws=[_raw(RAW_DAE, 30)], lines=lines))
        row = _avail(self.stock, ITEM_PRODUCT)[0]
        self.conn.execute(
            """
            UPDATE t_stock_master SET reserved_qty = 4
            WHERE farm_cd=? AND item_cd=? AND variety_cd=? AND grade_cd=?
              AND size_cd=? AND ABS(weight-?) < 1e-9 AND harvest_year=? AND storage_dt=?
            """,
            (
                FARM, ITEM_PRODUCT, row["variety_cd"], row["grade_cd"],
                row["size_cd"], row["weight"], row["harvest_year"], row["storage_dt"],
            ),
        )
        self.conn.commit()
        after = _avail(self.stock, ITEM_PRODUCT)[0]
        self.assertEqual(after["real_qty"], 10.0)
        self.assertEqual(after["reserved_qty"], 4.0)
        self.assertEqual(after["available_qty"], 6.0)

    def test_int_07_release_restores_available(self):
        """T-PROD-STOCK-INT-07: reserved 해제 후 가용 복원."""
        lines = [ProductionLineIn(grade_cd=GRADE, size_cd=SIZE, qty=10, weight=15.0)]
        self.prod.confirm("U1", _pack_payload(raws=[_raw(RAW_DAE, 30)], lines=lines))
        row = _avail(self.stock, ITEM_PRODUCT)[0]
        self.conn.execute(
            "UPDATE t_stock_master SET reserved_qty=4 WHERE farm_cd=? AND item_cd=?",
            (FARM, ITEM_PRODUCT),
        )
        self.conn.commit()
        self.conn.execute(
            "UPDATE t_stock_master SET reserved_qty=0 WHERE farm_cd=? AND item_cd=?",
            (FARM, ITEM_PRODUCT),
        )
        self.conn.commit()
        after = _avail(self.stock, ITEM_PRODUCT)[0]
        self.assertEqual(after["storage_dt"], row["storage_dt"])
        self.assertEqual(after["available_qty"], 10.0)

    def test_int_08_production_and_query_same_natural_key(self):
        """T-PROD-STOCK-INT-08: 생산 IN key = get_available_stock key."""
        lines = [ProductionLineIn(grade_cd=GRADE, size_cd=SIZE, qty=10, weight=15.0)]
        self.prod.confirm("U1", _pack_payload(raws=[_raw(RAW_DAE, 30)], lines=lines))
        row = _avail(self.stock, ITEM_PRODUCT)[0]
        self.assertEqual(row["item_cd"], ITEM_PRODUCT)
        self.assertEqual(row["variety_cd"], VARIETY)
        self.assertEqual(row["grade_cd"], GRADE)
        self.assertEqual(row["size_cd"], SIZE)
        self.assertAlmostEqual(row["weight"], 15.0)
        self.assertEqual(row["harvest_year"], 2026)
        master = self.conn.execute(
            """
            SELECT COUNT(*) FROM t_stock_master
            WHERE farm_cd=? AND item_cd=? AND variety_cd=? AND grade_cd=?
              AND size_cd=? AND ABS(weight-15.0)<1e-9
            """,
            (FARM, ITEM_PRODUCT, VARIETY, GRADE, SIZE),
        ).fetchone()[0]
        self.assertEqual(master, 1)

    def test_int_log_query_without_storage_dt_column(self):
        """이력 조회가 t_stock_log.storage_dt 없이 동작."""
        lines = [ProductionLineIn(grade_cd=GRADE, size_cd=SIZE, qty=10, weight=15.0)]
        self.prod.confirm("U1", _pack_payload(raws=[_raw(RAW_DAE, 30)], lines=lines))
        logs = self.stock.list_stock_logs(
            FARM, item_cd=ITEM_PRODUCT, variety_cd=VARIETY,
            grade_cd=GRADE, size_cd=SIZE, weight=15.0, storage_dt="2026-08-19",
        )
        self.assertGreaterEqual(len(logs), 1)
        self.assertEqual(logs[0]["io_type_nm"], "생산입고")
        raw_logs = self.stock.list_stock_logs(FARM, item_cd=ITEM_RAW, size_cd=RAW_DAE)
        self.assertEqual(raw_logs[0]["io_type_nm"], "원물사용")


if __name__ == "__main__":
    unittest.main()
