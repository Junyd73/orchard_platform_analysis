# -*- coding: utf-8 -*-
"""T-STOCK-MOB-01~13: 재고 조회 + 이력 검증."""

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
    ProductionConfirmIn,
    ProductionLineIn,
    ProductionService,
    RawStockConsumptionIn,
)
from core.stock_constants import (  # noqa: E402
    INPUT_SOURCE_HARVEST,
    INPUT_SOURCE_RAW_STOCK,
    ITEM_JUICE,
    ITEM_PRODUCT,
    ITEM_RAW,
    PROD_TYPE_PACK,
    PROD_TYPE_PROCESS,
)
from core.work_log_constants import WORK_STATUS_DONE  # noqa: E402

FARM     = "OR001"
WH       = "WH01"
VARIETY  = "FR010101"
GRADE    = "GR010100"
GRADE2   = "GR010200"
SIZE     = "FR020101"
RAW_SIZE = "CT010100"
HARVEST_MID  = "WK010300"
WORK_HARVEST = "W-H-001"


def _build_db() -> tuple[sqlite3.Connection, Path]:
    fd, path_s = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = sqlite3.connect(path_s)
    conn.row_factory = sqlite3.Row
    conn.executescript(f"""
        CREATE TABLE m_common_code (
            farm_cd TEXT, code_cd TEXT, code_nm TEXT, parent_cd TEXT
        );
        INSERT INTO m_common_code VALUES
          ('{FARM}', '{VARIETY}',   '신고',  'FR010100'),
          ('{FARM}', '{GRADE}',     '특',    'GR01'),
          ('{FARM}', '{GRADE2}',    '상',    'GR01'),
          ('{FARM}', '{SIZE}',      '25과',  'FR020100'),
          ('{FARM}', '{RAW_SIZE}',  '중과',  'CT01'),
          ('{FARM}', '{ITEM_PRODUCT}', '배 상품', NULL),
          ('{FARM}', '{ITEM_RAW}',     '원물',   NULL),
          ('{FARM}', '{ITEM_JUICE}',   '배즙',   NULL),
          ('{FARM}', '{HARVEST_MID}',  '수확',   'WK01'),
          ('{FARM}', '{WORK_STATUS_DONE}', '완료', 'WO01');

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

        CREATE TABLE t_stock_log (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            farm_cd TEXT, item_cd TEXT, variety_cd TEXT, harvest_year INTEGER,
            grade_cd TEXT, size_cd TEXT, weight REAL, io_type TEXT, qty REAL,
            remark TEXT, reg_id TEXT, reg_dt TEXT
        );
    """)
    return conn, Path(path_s)


def _insert_raw(conn, qty_in=270):
    conn.execute(
        f"""INSERT OR IGNORE INTO t_stock_master
        VALUES ('{FARM}','{WH}','{ITEM_RAW}','{VARIETY}','NONE','{RAW_SIZE}',20.0,2026,
                '2025-10-01',{qty_in},0,0,'U1',NULL,NULL)"""
    )
    conn.commit()


def _raw_payload(use_qty: int, lines) -> ProductionConfirmIn:
    return ProductionConfirmIn(
        farm_cd=FARM,
        prod_type=PROD_TYPE_PACK,
        input_source=INPUT_SOURCE_RAW_STOCK,
        variety_cd=VARIETY, wh_cd=WH, pack_weight=15.0,
        lines=lines,
        raw_consumptions=[RawStockConsumptionIn(
            wh_cd=WH, variety_cd=VARIETY, size_cd=RAW_SIZE,
            weight=20.0, harvest_year=2026, storage_dt="2025-10-01",
            qty=use_qty,
        )],
    )


class TestStockMob(unittest.TestCase):

    def setUp(self):
        self.conn, self.path = _build_db()
        self.svc   = ProductionService(self.conn)
        self.alloc = OrderAllocationService(self.conn)

    def tearDown(self):
        self.conn.close()
        self.path.unlink(missing_ok=True)

    # ── T-STOCK-MOB-01: 원물 270통 조회 ─────────────────────────────
    def test_01_raw_270(self):
        _insert_raw(self.conn, 270)
        rows = self.alloc.get_available_stock(FARM, item_cd=ITEM_RAW)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["available_qty"], 270.0)

    # ── T-STOCK-MOB-02: 원물 사용 30 후 240 표시 ────────────────────
    def test_02_raw_after_use(self):
        _insert_raw(self.conn, 270)
        lines = [ProductionLineIn(grade_cd=GRADE, size_cd=SIZE, qty=10, weight=15.0)]
        self.svc.confirm("U1", _raw_payload(30, lines))
        rows = self.alloc.get_available_stock(FARM, item_cd=ITEM_RAW)
        self.assertEqual(rows[0]["available_qty"], 240.0)

    # ── T-STOCK-MOB-03: 생산 IN 후 상품 재고 반영 ───────────────────
    def test_03_product_in_after_production(self):
        lines = [
            ProductionLineIn(grade_cd=GRADE,  size_cd=SIZE, qty=10, weight=15.0),
            ProductionLineIn(grade_cd=GRADE2, size_cd=SIZE, qty=5,  weight=7.5),
        ]
        payload = ProductionConfirmIn(
            farm_cd=FARM, prod_type=PROD_TYPE_PACK,
            input_source=INPUT_SOURCE_HARVEST,
            variety_cd=VARIETY, wh_cd=WH, pack_weight=0,
            harvest_work_id=WORK_HARVEST, lines=lines, raw_consumptions=[],
        )
        self.svc.confirm("U1", payload)
        rows = self.alloc.get_available_stock(FARM, item_cd=ITEM_PRODUCT)
        total_in = sum(r["real_qty"] for r in rows)
        self.assertEqual(total_in, 15.0)  # 10 + 5

    # ── T-STOCK-MOB-04: 현재/배정/가용 계산 ─────────────────────────
    def test_04_qty_calc(self):
        # 상품 in_qty=30, reserved=10
        self.conn.execute(
            f"""INSERT INTO t_stock_master VALUES
            ('{FARM}','{WH}','{ITEM_PRODUCT}','{VARIETY}',
             '{GRADE}','{SIZE}',15.0,2026,'2026-08-19',30,0,10,'U1',NULL,NULL)"""
        )
        self.conn.commit()
        rows = self.alloc.get_available_stock(FARM, item_cd=ITEM_PRODUCT)
        r = rows[0]
        self.assertEqual(r["real_qty"], 30.0)
        self.assertEqual(r["reserved_qty"], 10.0)
        self.assertEqual(r["available_qty"], 20.0)

    # ── T-STOCK-MOB-05: HOLD 후 가용 감소 ──────────────────────────
    def test_05_hold_reduces_available(self):
        self.conn.execute(
            f"""INSERT INTO t_stock_master VALUES
            ('{FARM}','{WH}','{ITEM_PRODUCT}','{VARIETY}',
             '{GRADE}','{SIZE}',15.0,2026,'2026-08-19',10,0,0,'U1',NULL,NULL)"""
        )
        self.conn.commit()
        # 직접 reserved_qty 증가 (allocation TX 대용)
        self.conn.execute(
            "UPDATE t_stock_master SET reserved_qty=4 WHERE farm_cd=? AND item_cd=?",
            (FARM, ITEM_PRODUCT),
        )
        self.conn.commit()
        rows = self.alloc.get_available_stock(FARM, item_cd=ITEM_PRODUCT)
        self.assertEqual(rows[0]["available_qty"], 6.0)

    # ── T-STOCK-MOB-06: RELEASE 후 가용 복원 ───────────────────────
    def test_06_release_restores_available(self):
        self.conn.execute(
            f"""INSERT INTO t_stock_master VALUES
            ('{FARM}','{WH}','{ITEM_PRODUCT}','{VARIETY}',
             '{GRADE}','{SIZE}',15.0,2026,'2026-08-19',10,0,4,'U1',NULL,NULL)"""
        )
        self.conn.commit()
        self.conn.execute(
            "UPDATE t_stock_master SET reserved_qty=0 WHERE farm_cd=? AND item_cd=?",
            (FARM, ITEM_PRODUCT),
        )
        self.conn.commit()
        rows = self.alloc.get_available_stock(FARM, item_cd=ITEM_PRODUCT)
        self.assertEqual(rows[0]["available_qty"], 10.0)

    # ── T-STOCK-MOB-07: 소진재고 기본 숨김 ─────────────────────────
    def test_07_zero_hidden_by_default(self):
        self.conn.execute(
            f"""INSERT INTO t_stock_master VALUES
            ('{FARM}','{WH}','{ITEM_PRODUCT}','{VARIETY}',
             '{GRADE}','{SIZE}',15.0,2026,'2026-08-19',0,0,0,'U1',NULL,NULL)"""
        )
        self.conn.commit()
        rows = self.alloc.get_available_stock(FARM, item_cd=ITEM_PRODUCT, include_zero=False)
        self.assertEqual(len(rows), 0)

    # ── T-STOCK-MOB-08: 소진 포함 필터 ────────────────────────────
    def test_08_include_zero(self):
        self.conn.execute(
            f"""INSERT INTO t_stock_master VALUES
            ('{FARM}','{WH}','{ITEM_PRODUCT}','{VARIETY}',
             '{GRADE}','{SIZE}',15.0,2026,'2026-08-19',0,0,0,'U1',NULL,NULL)"""
        )
        self.conn.commit()
        rows = self.alloc.get_available_stock(FARM, item_cd=ITEM_PRODUCT, include_zero=True)
        self.assertEqual(len(rows), 1)

    # ── T-STOCK-MOB-09: 상품 variety/weight/size/grade 표시 ────────
    def test_09_product_nm_fields(self):
        self.conn.execute(
            f"""INSERT INTO t_stock_master VALUES
            ('{FARM}','{WH}','{ITEM_PRODUCT}','{VARIETY}',
             '{GRADE}','{SIZE}',15.0,2026,'2026-08-19',10,0,0,'U1',NULL,NULL)"""
        )
        self.conn.commit()
        rows = self.alloc.get_available_stock(FARM, item_cd=ITEM_PRODUCT)
        r = rows[0]
        self.assertEqual(r["variety_nm"], "신고")
        self.assertEqual(r["grade_nm"],   "특")
        self.assertEqual(r["size_nm"],    "25과")
        self.assertEqual(r["item_nm"],    "배 상품")

    # ── T-STOCK-MOB-10: 원물 variety/구분/입고일 표시 ──────────────
    def test_10_raw_nm_fields(self):
        _insert_raw(self.conn, 270)
        rows = self.alloc.get_available_stock(FARM, item_cd=ITEM_RAW)
        r = rows[0]
        self.assertEqual(r["variety_nm"], "신고")
        self.assertEqual(r["size_nm"],    "중과")  # CT010100 → 중과
        self.assertEqual(r["storage_dt"], "2025-10-01")

    # ── T-STOCK-MOB-11: 배즙 박스 단위 (item_cd=FR010200) ──────────
    def test_11_juice_item(self):
        self.conn.execute(
            f"""INSERT INTO t_stock_master VALUES
            ('{FARM}','{WH}','{ITEM_JUICE}','{VARIETY}',
             'NONE','NONE',0.0,2026,'2026-08-19',25,0,5,'U1',NULL,NULL)"""
        )
        self.conn.commit()
        rows = self.alloc.get_available_stock(FARM, item_cd=ITEM_JUICE)
        r = rows[0]
        self.assertEqual(r["real_qty"],      25.0)
        self.assertEqual(r["reserved_qty"],   5.0)
        self.assertEqual(r["available_qty"], 20.0)

    # ── T-STOCK-MOB-12: 재고 log 최신순 조회 ───────────────────────
    def test_12_logs_latest_first(self):
        _insert_raw(self.conn, 270)
        lines = [ProductionLineIn(grade_cd=GRADE, size_cd=SIZE, qty=10, weight=15.0)]
        self.svc.confirm("U1", _raw_payload(30, lines))
        logs = self.alloc.list_stock_logs(FARM, item_cd=ITEM_PRODUCT)
        self.assertGreater(len(logs), 0)
        # log_id 내림차순 확인
        ids = [l["log_id"] for l in logs]
        self.assertEqual(ids, sorted(ids, reverse=True))

    # ── T-STOCK-MOB-13: 생산 후 재고 반영 (IN + OUT 일치) ──────────
    def test_13_production_reflected_in_stock(self):
        _insert_raw(self.conn, 270)
        lines = [
            ProductionLineIn(grade_cd=GRADE,  size_cd=SIZE, qty=10, weight=15.0),
            ProductionLineIn(grade_cd=GRADE2, size_cd=SIZE, qty=5,  weight=7.5),
        ]
        self.svc.confirm("U1", _raw_payload(30, lines))
        # 원물 차감 확인
        raw_rows = self.alloc.get_available_stock(FARM, item_cd=ITEM_RAW)
        self.assertEqual(raw_rows[0]["available_qty"], 240.0)
        # 상품 IN 확인
        prod_rows = self.alloc.get_available_stock(FARM, item_cd=ITEM_PRODUCT)
        total_product = sum(r["real_qty"] for r in prod_rows)
        self.assertEqual(total_product, 15.0)


if __name__ == "__main__":
    unittest.main()
