# -*- coding: utf-8 -*-
"""생산확정 Stage P — T-PROD-01~13."""

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

from core.production_service import (  # noqa: E402
    ProductionConfirmIn,
    ProductionError,
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

FARM = "OR001"
VARIETY = "FR010101"
WH = "WH01"
SIZE_DAI = "FR020101"
GRADE = "GR010100"
RAW_SIZE = "CT010100"
HARVEST_MID = "WK010300"
WORK_HARVEST = "W-HARV-001"


def _build_db() -> tuple[sqlite3.Connection, Path]:
    fd, path_s = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    path = Path(path_s)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.executescript(
        f"""
        CREATE TABLE m_common_code (
            farm_cd TEXT, code_cd TEXT, code_nm TEXT, parent_cd TEXT
        );
        INSERT INTO m_common_code VALUES
          ('{FARM}','{VARIETY}','신고','FR010100'),
          ('{FARM}','{GRADE}','특','GR01'),
          ('{FARM}','{SIZE_DAI}','18과','FR020100'),
          ('{FARM}','{RAW_SIZE}','20kg통','CT01'),
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
          ('{FARM}','{WH}','{ITEM_RAW}','{VARIETY}','NONE','{RAW_SIZE}',20.0,2026,
           '2026-08-10',5,0,0,'U1',NULL,NULL);

        CREATE TABLE t_stock_log (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            farm_cd TEXT, item_cd TEXT, variety_cd TEXT, harvest_year INTEGER,
            grade_cd TEXT, size_cd TEXT, weight REAL, io_type TEXT, qty REAL,
            remark TEXT, reg_id TEXT, reg_dt TEXT
        );
        """
    )
    return conn, path


def _stock_qty(conn: sqlite3.Connection, item_cd: str) -> tuple[float, float]:
    row = conn.execute(
        """
        SELECT COALESCE(SUM(in_qty),0), COALESCE(SUM(out_qty),0)
        FROM t_stock_master WHERE farm_cd=? AND item_cd=?
        """,
        (FARM, item_cd),
    ).fetchone()
    return float(row[0]), float(row[0])


def _product_in_qty(conn: sqlite3.Connection) -> float:
    row = conn.execute(
        f"SELECT COALESCE(SUM(in_qty),0) FROM t_stock_master WHERE farm_cd=? AND item_cd=?",
        (FARM, ITEM_PRODUCT),
    ).fetchone()
    return float(row[0])


def _raw_out_qty(conn: sqlite3.Connection) -> float:
    row = conn.execute(
        f"SELECT COALESCE(SUM(out_qty),0) FROM t_stock_master WHERE farm_cd=? AND item_cd=?",
        (FARM, ITEM_RAW),
    ).fetchone()
    return float(row[0])


class ProductionServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.conn, self.path = _build_db()
        self.svc = ProductionService(self.conn)

    def tearDown(self) -> None:
        self.conn.close()
        self.path.unlink(missing_ok=True)

    def test_t_prod_01_raw_stock_pack(self) -> None:
        payload = ProductionConfirmIn(
            farm_cd=FARM,
            prod_type=PROD_TYPE_PACK,
            input_source=INPUT_SOURCE_RAW_STOCK,
            variety_cd=VARIETY,
            wh_cd=WH,
            pack_weight=15.0,
            lines=[ProductionLineIn(grade_cd=GRADE, size_cd=SIZE_DAI, qty=3)],
            raw_consumptions=[
                RawStockConsumptionIn(
                    wh_cd=WH,
                    variety_cd=VARIETY,
                    size_cd=RAW_SIZE,
                    weight=20.0,
                    harvest_year=2026,
                    storage_dt="2026-08-10",
                    qty=2,
                )
            ],
        )
        res = self.svc.confirm("U1", payload)
        self.assertTrue(res["ok"])
        self.assertEqual(_raw_out_qty(self.conn), 2.0)
        self.assertEqual(_product_in_qty(self.conn), 3.0)
        out_logs = self.conn.execute(
            "SELECT COUNT(*) FROM t_stock_log WHERE item_cd=? AND io_type='OUT'",
            (ITEM_RAW,),
        ).fetchone()[0]
        in_logs = self.conn.execute(
            "SELECT COUNT(*) FROM t_stock_log WHERE item_cd=? AND io_type='IN'",
            (ITEM_PRODUCT,),
        ).fetchone()[0]
        self.assertEqual(out_logs, 1)
        self.assertEqual(in_logs, 1)

    def test_t_prod_02_harvest_pack_no_raw_out(self) -> None:
        payload = ProductionConfirmIn(
            farm_cd=FARM,
            prod_type=PROD_TYPE_PACK,
            input_source=INPUT_SOURCE_HARVEST,
            variety_cd=VARIETY,
            pack_weight=15.0,
            harvest_work_id=WORK_HARVEST,
            lines=[ProductionLineIn(grade_cd=GRADE, size_cd=SIZE_DAI, qty=2)],
        )
        self.svc.confirm("U1", payload)
        self.assertEqual(_raw_out_qty(self.conn), 0.0)
        self.assertEqual(_product_in_qty(self.conn), 2.0)

    def test_t_prod_03_raw_stock_process(self) -> None:
        payload = ProductionConfirmIn(
            farm_cd=FARM,
            prod_type=PROD_TYPE_PROCESS,
            input_source=INPUT_SOURCE_RAW_STOCK,
            variety_cd=VARIETY,
            juice_qty=4,
            raw_consumptions=[
                RawStockConsumptionIn(
                    wh_cd=WH,
                    variety_cd=VARIETY,
                    size_cd=RAW_SIZE,
                    weight=20.0,
                    harvest_year=2026,
                    storage_dt="2026-08-10",
                    qty=1,
                )
            ],
        )
        self.svc.confirm("U1", payload)
        juice_in = self.conn.execute(
            f"SELECT COALESCE(SUM(in_qty),0) FROM t_stock_master WHERE item_cd=?",
            (ITEM_JUICE,),
        ).fetchone()[0]
        self.assertEqual(float(juice_in), 4.0)
        self.assertEqual(_raw_out_qty(self.conn), 1.0)

    def test_t_prod_04_failure_rollback(self) -> None:
        payload = ProductionConfirmIn(
            farm_cd=FARM,
            prod_type=PROD_TYPE_PACK,
            input_source=INPUT_SOURCE_RAW_STOCK,
            variety_cd=VARIETY,
            pack_weight=15.0,
            lines=[ProductionLineIn(grade_cd=GRADE, size_cd=SIZE_DAI, qty=1)],
            raw_consumptions=[
                RawStockConsumptionIn(
                    wh_cd=WH,
                    variety_cd=VARIETY,
                    size_cd=RAW_SIZE,
                    weight=20.0,
                    harvest_year=2026,
                    storage_dt="2099-01-01",
                    qty=1,
                )
            ],
        )
        with self.assertRaises(ProductionError):
            self.svc.confirm("U1", payload)
        self.assertEqual(_raw_out_qty(self.conn), 0.0)
        self.assertEqual(_product_in_qty(self.conn), 0.0)

    def test_t_prod_05_full_product_stock(self) -> None:
        payload = ProductionConfirmIn(
            farm_cd=FARM,
            prod_type=PROD_TYPE_PACK,
            input_source=INPUT_SOURCE_HARVEST,
            variety_cd=VARIETY,
            pack_weight=15.0,
            harvest_work_id=WORK_HARVEST,
            lines=[
                ProductionLineIn(grade_cd=GRADE, size_cd=SIZE_DAI, qty=5),
                ProductionLineIn(grade_cd=GRADE, size_cd=SIZE_DAI, qty=0),
            ],
        )
        res = self.svc.confirm("U1", payload)
        self.assertEqual(len(res["prefill_lines"]), 1)
        self.assertEqual(_product_in_qty(self.conn), 5.0)

    def test_t_prod_06_prefill_does_not_rollback(self) -> None:
        payload = ProductionConfirmIn(
            farm_cd=FARM,
            prod_type=PROD_TYPE_HARVEST if False else PROD_TYPE_PACK,
            input_source=INPUT_SOURCE_HARVEST,
            variety_cd=VARIETY,
            pack_weight=15.0,
            harvest_work_id=WORK_HARVEST,
            lines=[ProductionLineIn(grade_cd=GRADE, size_cd=SIZE_DAI, qty=1)],
        )
        res = self.svc.confirm("U1", payload)
        prefill = res["prefill_lines"]
        self.assertEqual(len(prefill), 1)
        self.assertEqual(prefill[0]["qty"], 1.0)
        self.assertEqual(_product_in_qty(self.conn), 1.0)

    def test_t_prod_07_prefill_fields(self) -> None:
        payload = ProductionConfirmIn(
            farm_cd=FARM,
            prod_type=PROD_TYPE_PACK,
            input_source=INPUT_SOURCE_HARVEST,
            variety_cd=VARIETY,
            pack_weight=15.0,
            harvest_work_id=WORK_HARVEST,
            lines=[ProductionLineIn(grade_cd=GRADE, size_cd=SIZE_DAI, qty=2)],
        )
        ln = self.svc.confirm("U1", payload)["prefill_lines"][0]
        self.assertEqual(ln["item_cd"], ITEM_PRODUCT)
        self.assertEqual(ln["variety_cd"], VARIETY)
        self.assertEqual(ln["grade_cd"], GRADE)
        self.assertEqual(ln["size_cd"], SIZE_DAI)
        self.assertEqual(ln["weight"], 15.0)
        self.assertEqual(ln["qty"], 2.0)
        self.assertEqual(ln["work_id"], WORK_HARVEST)

    def test_t_prod_08_harvest_record_unchanged(self) -> None:
        before = self.conn.execute(
            "SELECT harvest_container_qty FROM t_work_detail WHERE work_id=?",
            (WORK_HARVEST,),
        ).fetchone()[0]
        payload = ProductionConfirmIn(
            farm_cd=FARM,
            prod_type=PROD_TYPE_PACK,
            input_source=INPUT_SOURCE_HARVEST,
            variety_cd=VARIETY,
            pack_weight=15.0,
            harvest_work_id=WORK_HARVEST,
            lines=[ProductionLineIn(grade_cd=GRADE, size_cd=SIZE_DAI, qty=9)],
        )
        self.svc.confirm("U1", payload)
        after = self.conn.execute(
            "SELECT harvest_container_qty FROM t_work_detail WHERE work_id=?",
            (WORK_HARVEST,),
        ).fetchone()[0]
        self.assertEqual(before, after)
        self.assertEqual(after, 12)

    def test_t_prod_09_no_harvest_kg_conversion(self) -> None:
        rows = self.svc.list_harvest_records(FARM)
        self.assertEqual(rows[0]["harvest_container_qty"], 12)
        self.assertNotIn("kg", str(rows[0]).lower())

    def test_t_prod_10_process_juice_box_unit(self) -> None:
        payload = ProductionConfirmIn(
            farm_cd=FARM,
            prod_type=PROD_TYPE_PROCESS,
            input_source=INPUT_SOURCE_RAW_STOCK,
            variety_cd=VARIETY,
            juice_qty=7,
            raw_consumptions=[
                RawStockConsumptionIn(
                    wh_cd=WH,
                    variety_cd=VARIETY,
                    size_cd=RAW_SIZE,
                    weight=20.0,
                    harvest_year=2026,
                    storage_dt="2026-08-10",
                    qty=1,
                )
            ],
        )
        ln = self.svc.confirm("U1", payload)["prefill_lines"][0]
        self.assertEqual(ln["item_cd"], ITEM_JUICE)
        self.assertEqual(ln["qty"], 7.0)

    def test_harvest_process_blocked(self) -> None:
        with self.assertRaises(ProductionError):
            self.svc.confirm(
                "U1",
                ProductionConfirmIn(
                    farm_cd=FARM,
                    prod_type=PROD_TYPE_PROCESS,
                    input_source=INPUT_SOURCE_HARVEST,
                    variety_cd=VARIETY,
                    harvest_work_id=WORK_HARVEST,
                    juice_qty=1,
                ),
            )

    # ══════════════════════════════════════════════════════════════════════════
    # T-PROD-MULTI — 다중 중량/과수/등급 N:N:N 생산결과
    # ══════════════════════════════════════════════════════════════════════════

    def _multi_payload(self, lines, source=INPUT_SOURCE_HARVEST):
        """다중 line payload 헬퍼."""
        return ProductionConfirmIn(
            farm_cd=FARM,
            prod_type=PROD_TYPE_PACK,
            input_source=source,
            variety_cd=VARIETY,
            wh_cd=WH,
            pack_weight=0.0,   # line별 weight 사용
            harvest_work_id=WORK_HARVEST if source == INPUT_SOURCE_HARVEST else None,
            lines=lines,
        )

    def test_multi_01_two_weights(self) -> None:
        """T-PROD-MULTI-01: 15kg + 7.5kg 두 weight 동시 생산."""
        SIZE2 = SIZE_DAI  # 재사용
        lines = [
            ProductionLineIn(grade_cd=GRADE, size_cd=SIZE_DAI, qty=10, weight=15.0),
            ProductionLineIn(grade_cd=GRADE, size_cd=SIZE2, qty=5, weight=7.5),
        ]
        res = self.svc.confirm("U1", self._multi_payload(lines))
        self.assertTrue(res["ok"])
        total_in = _product_in_qty(self.conn)
        self.assertEqual(total_in, 15.0)

    def test_multi_02_two_sizes_same_weight(self) -> None:
        """T-PROD-MULTI-02: 15kg 아래 SIZE_DAI + SIZE2 동시 생산."""
        SIZE2 = "FR020102"
        self.conn.execute(
            f"INSERT OR IGNORE INTO m_common_code VALUES ('{FARM}','{SIZE2}','20과','FR020100')"
        )
        self.conn.commit()
        lines = [
            ProductionLineIn(grade_cd=GRADE, size_cd=SIZE_DAI, qty=8, weight=15.0),
            ProductionLineIn(grade_cd=GRADE, size_cd=SIZE2, qty=7, weight=15.0),
        ]
        res = self.svc.confirm("U1", self._multi_payload(lines))
        self.assertTrue(res["ok"])
        self.assertEqual(_product_in_qty(self.conn), 15.0)

    def test_multi_03_multi_grades(self) -> None:
        """T-PROD-MULTI-03: 같은 size 아래 골드특/특 다중 등급."""
        GRADE2 = "GR010200"
        self.conn.execute(
            f"INSERT OR IGNORE INTO m_common_code VALUES ('{FARM}','{GRADE2}','상','GR01')"
        )
        self.conn.commit()
        lines = [
            ProductionLineIn(grade_cd=GRADE, size_cd=SIZE_DAI, qty=10, weight=15.0),
            ProductionLineIn(grade_cd=GRADE2, size_cd=SIZE_DAI, qty=7, weight=15.0),
        ]
        res = self.svc.confirm("U1", self._multi_payload(lines))
        self.assertTrue(res["ok"])
        self.assertEqual(_product_in_qty(self.conn), 17.0)

    def test_multi_04_all_in_stock(self) -> None:
        """T-PROD-MULTI-04: N개 결과가 모두 t_stock_master IN."""
        lines = [
            ProductionLineIn(grade_cd=GRADE, size_cd=SIZE_DAI, qty=5, weight=15.0),
            ProductionLineIn(grade_cd=GRADE, size_cd=SIZE_DAI, qty=3, weight=7.5),
        ]
        self.svc.confirm("U1", self._multi_payload(lines))
        rows = self.conn.execute(
            "SELECT weight, COALESCE(SUM(in_qty),0) FROM t_stock_master"
            " WHERE item_cd=? GROUP BY weight ORDER BY weight",
            (ITEM_PRODUCT,),
        ).fetchall()
        weights = {float(r[0]): float(r[1]) for r in rows}
        self.assertEqual(weights.get(15.0), 5.0)
        self.assertEqual(weights.get(7.5), 3.0)

    def test_multi_05_rollback_on_failure(self) -> None:
        """T-PROD-MULTI-05: 한 row 실패 시 전체 rollback."""
        # 첫 번째 줄은 성공, 두 번째는 weight=0으로 실패 유발
        lines = [
            ProductionLineIn(grade_cd=GRADE, size_cd=SIZE_DAI, qty=5, weight=15.0),
            ProductionLineIn(grade_cd=GRADE, size_cd=SIZE_DAI, qty=3, weight=0.0),  # weight 0 → error
        ]
        with self.assertRaises(Exception):
            self.svc.confirm("U1", self._multi_payload(lines))
        # rollback → product IN이 없어야 함
        self.assertEqual(_product_in_qty(self.conn), 0.0)

    def test_multi_06_duplicate_weight_same_size_grade_blocked(self) -> None:
        """T-PROD-MULTI-06: 동일 weight+size+grade 중복 차단."""
        from core.production_service import ProductionError as PE
        lines = [
            ProductionLineIn(grade_cd=GRADE, size_cd=SIZE_DAI, qty=5, weight=15.0),
            ProductionLineIn(grade_cd=GRADE, size_cd=SIZE_DAI, qty=3, weight=15.0),
        ]
        with self.assertRaises(PE):
            self.svc.confirm("U1", self._multi_payload(lines))

    def test_multi_07_duplicate_weight_size_different_grade_ok(self) -> None:
        """T-PROD-MULTI-07: 같은 weight+size라도 grade 다르면 허용."""
        GRADE2 = "GR010200"
        self.conn.execute(
            f"INSERT OR IGNORE INTO m_common_code VALUES ('{FARM}','{GRADE2}','상','GR01')"
        )
        self.conn.commit()
        lines = [
            ProductionLineIn(grade_cd=GRADE,  size_cd=SIZE_DAI, qty=5, weight=15.0),
            ProductionLineIn(grade_cd=GRADE2, size_cd=SIZE_DAI, qty=3, weight=15.0),
        ]
        res = self.svc.confirm("U1", self._multi_payload(lines))
        self.assertTrue(res["ok"])

    def test_multi_08_zero_qty_not_stored(self) -> None:
        """T-PROD-MULTI-08: qty=0 row는 저장되지 않는다."""
        lines = [
            ProductionLineIn(grade_cd=GRADE, size_cd=SIZE_DAI, qty=5, weight=15.0),
            ProductionLineIn(grade_cd=GRADE, size_cd=SIZE_DAI, qty=0, weight=7.5),
        ]
        self.svc.confirm("U1", self._multi_payload(lines))
        cnt = self.conn.execute(
            "SELECT COUNT(*) FROM t_stock_log WHERE item_cd=? AND io_type='IN'",
            (ITEM_PRODUCT,),
        ).fetchone()[0]
        self.assertEqual(cnt, 1)   # qty=0 저장 없음

    def test_multi_09_prefill_contains_all_lines(self) -> None:
        """T-PROD-MULTI-09: prefill_lines가 생산결과 N건을 모두 포함."""
        GRADE2 = "GR010200"
        self.conn.execute(
            f"INSERT OR IGNORE INTO m_common_code VALUES ('{FARM}','{GRADE2}','상','GR01')"
        )
        self.conn.commit()
        lines = [
            ProductionLineIn(grade_cd=GRADE,  size_cd=SIZE_DAI, qty=5, weight=15.0),
            ProductionLineIn(grade_cd=GRADE2, size_cd=SIZE_DAI, qty=3, weight=7.5),
        ]
        res = self.svc.confirm("U1", self._multi_payload(lines))
        self.assertEqual(len(res["prefill_lines"]), 2)

    def test_multi_10_backward_compat_pack_weight(self) -> None:
        """T-PROD-MULTI-10: 기존 pack_weight 방식(line.weight=0)도 동작."""
        payload = ProductionConfirmIn(
            farm_cd=FARM,
            prod_type=PROD_TYPE_PACK,
            input_source=INPUT_SOURCE_HARVEST,
            variety_cd=VARIETY,
            pack_weight=15.0,      # 구버전 방식
            harvest_work_id=WORK_HARVEST,
            lines=[ProductionLineIn(grade_cd=GRADE, size_cd=SIZE_DAI, qty=4)],  # weight 미설정
        )
        res = self.svc.confirm("U1", payload)
        self.assertTrue(res["ok"])
        self.assertEqual(_product_in_qty(self.conn), 4.0)

    # ── T-PROD-HARVEST-01: Stage H row 생성 후 GET 200 + 해당 record ──────────
    def test_harvest_01_list_returns_staged_row(self) -> None:
        """2026-08-19 / VARIETY / 12상자 row가 반환된다."""
        rows = self.svc.list_harvest_records(FARM)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["work_id"], WORK_HARVEST)
        self.assertEqual(rows[0]["work_dt"], "2026-08-19")
        self.assertEqual(rows[0]["variety_cd"], VARIETY)
        self.assertEqual(int(rows[0]["harvest_container_qty"]), 12)

    # ── T-PROD-HARVEST-02: 수확기록 없음 → 200 + [] ───────────────────────────
    def test_harvest_02_empty_farm_returns_empty_list(self) -> None:
        """다른 farm_cd 조회 시 빈 리스트."""
        rows = self.svc.list_harvest_records("OTHER_FARM")
        self.assertEqual(rows, [])

    # ── T-PROD-HARVEST-03: variety_nm JOIN 정상 ─────────────────────────────
    def test_harvest_03_variety_nm_join(self) -> None:
        """m_common_code JOIN으로 variety_nm이 채워진다."""
        rows = self.svc.list_harvest_records(FARM)
        self.assertEqual(rows[0]["variety_nm"], "신고")

    # ── T-PROD-HARVEST-04: variety_cd 자동결정 (service 측 검증) ─────────────
    def test_harvest_04_variety_cd_present(self) -> None:
        """수확기록에 variety_cd가 포함된다 (프론트 자동연결 근거)."""
        rows = self.svc.list_harvest_records(FARM)
        self.assertEqual(rows[0]["variety_cd"], VARIETY)

    # ── T-PROD-HARVEST-05: 0상자 row는 결과에서 제외 ────────────────────────
    def test_harvest_05_zero_qty_excluded(self) -> None:
        """harvest_container_qty=0 행은 조회 결과에서 제외된다."""
        self.conn.execute(
            f"INSERT INTO t_work_detail VALUES"
            f" ('W-ZERO','2026-08-18','{FARM}','{HARVEST_MID}','{VARIETY}',0,'WO010100','U1',NULL,NULL)"
        )
        self.conn.commit()
        rows = self.svc.list_harvest_records(FARM)
        ids = [r["work_id"] for r in rows]
        self.assertNotIn("W-ZERO", ids)
        self.assertIn(WORK_HARVEST, ids)


def _make_raw_payload(conn, farm, raw_qty: int) -> "ProductionConfirmIn":
    """RAW_STOCK 생산확정 payload 빌더 (테스트용)."""
    conn.execute(
        f"""INSERT OR IGNORE INTO t_stock_master
        VALUES ('{farm}','{WH}','{ITEM_RAW}','{VARIETY}','NONE','{RAW_SIZE}',20.0,2026,
                '2025-10-01',270,0,0,'U1',NULL,NULL)"""
    )
    conn.commit()
    return ProductionConfirmIn(
        farm_cd=farm,
        prod_type=PROD_TYPE_PACK,
        input_source=INPUT_SOURCE_RAW_STOCK,
        variety_cd=VARIETY,
        wh_cd=WH,
        pack_weight=15.0,
        lines=[
            ProductionLineIn(grade_cd=GRADE, size_cd=SIZE_DAI, qty=10, weight=15.0),
            ProductionLineIn(grade_cd=GRADE, size_cd=SIZE_DAI, qty=5,  weight=7.5),
        ],
        raw_consumptions=[
            RawStockConsumptionIn(
                wh_cd=WH, variety_cd=VARIETY, size_cd=RAW_SIZE,
                weight=20.0, harvest_year=2026, storage_dt="2025-10-01",
                qty=raw_qty,
            )
        ],
    )


class TestRawUse(unittest.TestCase):
    """T-PROD-RAWUSE-01~10: 원물 사용수량 처리 검증."""

    def setUp(self):
        self.conn, self.path = _build_db()
        # 잔여 270통 원물 추가
        self.conn.execute(
            f"""INSERT OR IGNORE INTO t_stock_master
            VALUES ('{FARM}','{WH}','{ITEM_RAW}','{VARIETY}','NONE','{RAW_SIZE}',20.0,2026,
                    '2025-10-01',270,0,0,'U1',NULL,NULL)"""
        )
        self.conn.commit()
        self.svc = ProductionService(self.conn)

    def tearDown(self):
        self.conn.close()
        self.path.unlink(missing_ok=True)

    def _payload(self, use_qty: int, lines=None):
        if lines is None:
            lines = [
                ProductionLineIn(grade_cd=GRADE, size_cd=SIZE_DAI, qty=10, weight=15.0),
                ProductionLineIn(grade_cd=GRADE, size_cd=SIZE_DAI, qty=5,  weight=7.5),
            ]
        return ProductionConfirmIn(
            farm_cd=FARM,
            prod_type=PROD_TYPE_PACK,
            input_source=INPUT_SOURCE_RAW_STOCK,
            variety_cd=VARIETY,
            wh_cd=WH,
            pack_weight=15.0,
            lines=lines,
            raw_consumptions=[
                RawStockConsumptionIn(
                    wh_cd=WH, variety_cd=VARIETY, size_cd=RAW_SIZE,
                    weight=20.0, harvest_year=2026, storage_dt="2025-10-01",
                    qty=use_qty,
                )
            ],
        )

    def test_rawuse_01_normal_use_decreases_raw(self):
        """T-PROD-RAWUSE-01: 30통 사용 → 원물 out_qty=30, avail=240."""
        self.svc.confirm("U1", self._payload(30))
        row = self.conn.execute(
            "SELECT out_qty FROM t_stock_master WHERE farm_cd=? AND item_cd=? AND storage_dt='2025-10-01'",
            (FARM, ITEM_RAW),
        ).fetchone()
        self.assertEqual(int(row[0]), 30)

    def test_rawuse_02_zero_use_blocked(self):
        """T-PROD-RAWUSE-02: qty=0 사용수량은 RAW validation에서 차단."""
        from core.production_service import ProductionError as PE
        payload = self._payload(0)
        with self.assertRaises(PE) as ctx:
            self.svc.confirm("U1", payload)
        self.assertEqual(ctx.exception.code, "RAW")

    def test_rawuse_03_exceed_available_blocked(self):
        """T-PROD-RAWUSE-03: 잔여(270) 초과(271) 차단."""
        from core.production_service import ProductionError as PE
        payload = self._payload(271)
        with self.assertRaises(PE) as ctx:
            self.svc.confirm("U1", payload)
        self.assertEqual(ctx.exception.code, "RAW_EXCEED")

    def test_rawuse_04_stock_log_out_created(self):
        """T-PROD-RAWUSE-04: OUT 30통 → t_stock_log OUT 1건."""
        self.svc.confirm("U1", self._payload(30))
        cnt = self.conn.execute(
            "SELECT COUNT(*) FROM t_stock_log WHERE item_cd=? AND io_type='OUT' AND qty=30",
            (ITEM_RAW,),
        ).fetchone()[0]
        self.assertEqual(cnt, 1)

    def test_rawuse_05_all_product_lines_in(self):
        """T-PROD-RAWUSE-05: 생산결과 N라인 전량 IN 확인."""
        self.svc.confirm("U1", self._payload(30))
        cnt = self.conn.execute(
            "SELECT COUNT(*) FROM t_stock_log WHERE item_cd=? AND io_type='IN'",
            (ITEM_PRODUCT,),
        ).fetchone()[0]
        self.assertEqual(cnt, 2)  # 15kg 10박스, 7.5kg 5박스

    def test_rawuse_06_rollback_on_raw_exceed(self):
        """T-PROD-RAWUSE-06: 잔여 초과(271) → RAW_EXCEED 에러, 원물 out_qty 변화 없음."""
        from core.production_service import ProductionError as PE
        payload = self._payload(271)
        with self.assertRaises(PE) as ctx:
            self.svc.confirm("U1", payload)
        self.assertEqual(ctx.exception.code, "RAW_EXCEED")
        # rollback 확인: out_qty 변화 없음
        row = self.conn.execute(
            "SELECT out_qty FROM t_stock_master WHERE farm_cd=? AND item_cd=? AND storage_dt='2025-10-01'",
            (FARM, ITEM_RAW),
        ).fetchone()
        self.assertEqual(int(row[0]), 0)

    def test_rawuse_07_save_stock_no_extra_in(self):
        """T-PROD-RAWUSE-07: 생산확정 후 재고로 저장 = 추가 IN 없음."""
        self.svc.confirm("U1", self._payload(30))
        cnt_before = self.conn.execute(
            "SELECT COUNT(*) FROM t_stock_log WHERE item_cd=? AND io_type='IN'",
            (ITEM_PRODUCT,),
        ).fetchone()[0]
        # "재고로 저장"은 UI 동작이므로 DB 재호출 없음 → count 유지
        cnt_after = self.conn.execute(
            "SELECT COUNT(*) FROM t_stock_log WHERE item_cd=? AND io_type='IN'",
            (ITEM_PRODUCT,),
        ).fetchone()[0]
        self.assertEqual(cnt_before, cnt_after)

    def test_rawuse_08_prefill_n_lines_on_immediate_sell(self):
        """T-PROD-RAWUSE-08: 바로판매 → prefill_lines에 N건 포함."""
        res = self.svc.confirm("U1", self._payload(30))
        self.assertEqual(len(res["prefill_lines"]), 2)

    def test_rawuse_09_no_product_out_after_confirm(self):
        """T-PROD-RAWUSE-09: 생산확정 후 상품 OUT 없음."""
        self.svc.confirm("U1", self._payload(30))
        cnt = self.conn.execute(
            "SELECT COUNT(*) FROM t_stock_log WHERE item_cd=? AND io_type='OUT'",
            (ITEM_PRODUCT,),
        ).fetchone()[0]
        self.assertEqual(cnt, 0)

    def test_rawuse_10_harvest_has_no_raw_consumption(self):
        """T-PROD-RAWUSE-10: HARVEST 생산에는 raw_consumptions 없음 → 원물 out_qty 불변."""
        raw_out_before = self.conn.execute(
            "SELECT COALESCE(SUM(out_qty),0) FROM t_stock_master WHERE farm_cd=? AND item_cd=?",
            (FARM, ITEM_RAW),
        ).fetchone()[0]

        payload = ProductionConfirmIn(
            farm_cd=FARM,
            prod_type=PROD_TYPE_PACK,
            input_source=INPUT_SOURCE_HARVEST,
            variety_cd=VARIETY,
            wh_cd=WH,
            pack_weight=15.0,
            harvest_work_id=WORK_HARVEST,
            lines=[ProductionLineIn(grade_cd=GRADE, size_cd=SIZE_DAI, qty=5, weight=15.0)],
            raw_consumptions=[],
        )
        res = self.svc.confirm("U1", payload)
        self.assertTrue(res["ok"])

        raw_out_after = self.conn.execute(
            "SELECT COALESCE(SUM(out_qty),0) FROM t_stock_master WHERE farm_cd=? AND item_cd=?",
            (FARM, ITEM_RAW),
        ).fetchone()[0]
        self.assertEqual(raw_out_before, raw_out_after)  # 원물 out 변화 없음


def _product_harvest_year(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT harvest_year FROM t_stock_master WHERE farm_cd=? AND item_cd=?",
        (FARM, ITEM_PRODUCT),
    ).fetchone()
    return int(row[0])


class TestHarvestYear(unittest.TestCase):
    """T-HYEAR-01~07: 상품 harvest_year = 원료 수확연도."""

    def setUp(self) -> None:
        self.conn, self.path = _build_db()
        self.svc = ProductionService(self.conn)

    def tearDown(self) -> None:
        self.conn.close()
        self.path.unlink(missing_ok=True)

    def _raw(self, year: int, qty: int = 1, storage: str | None = None, variety: str = VARIETY):
        return RawStockConsumptionIn(
            wh_cd=WH, variety_cd=variety, size_cd=RAW_SIZE,
            weight=20.0, harvest_year=year,
            storage_dt=storage or f"{year}-08-10", qty=qty,
        )

    def test_hyear_01_raw_stock_inherits_year(self) -> None:
        """T-HYEAR-01: 2026년산 원물 → 상품 2026."""
        self.svc.confirm("U1", ProductionConfirmIn(
            farm_cd=FARM, prod_type=PROD_TYPE_PACK,
            input_source=INPUT_SOURCE_RAW_STOCK, variety_cd=VARIETY, wh_cd=WH,
            pack_weight=15.0,
            lines=[ProductionLineIn(grade_cd=GRADE, size_cd=SIZE_DAI, qty=1)],
            raw_consumptions=[self._raw(2026)],
        ))
        self.assertEqual(_product_harvest_year(self.conn), 2026)

    def test_hyear_02_pack_date_does_not_change_year(self) -> None:
        """T-HYEAR-02: 생산일이 2027이어도 원물 2026 → 상품 2026."""
        from datetime import datetime
        from unittest.mock import patch

        fake = datetime(2027, 1, 10, 9, 0, 0)
        with patch("core.production_service.now_ops", return_value=fake), patch(
            "core.production_service.now_ops_str",
            lambda fmt="%Y-%m-%d %H:%M:%S": fake.strftime(fmt),
        ):
            self.svc.confirm("U1", ProductionConfirmIn(
                farm_cd=FARM, prod_type=PROD_TYPE_PACK,
                input_source=INPUT_SOURCE_RAW_STOCK, variety_cd=VARIETY, wh_cd=WH,
                pack_weight=15.0,
                lines=[ProductionLineIn(grade_cd=GRADE, size_cd=SIZE_DAI, qty=1)],
                raw_consumptions=[self._raw(2026)],
            ))
        self.assertEqual(_product_harvest_year(self.conn), 2026)
        storage = self.conn.execute(
            "SELECT storage_dt FROM t_stock_master WHERE item_cd=?",
            (ITEM_PRODUCT,),
        ).fetchone()[0]
        self.assertEqual(str(storage)[:10], "2027-01-10")

    def test_hyear_03_same_year_multi_raw_ok(self) -> None:
        """T-HYEAR-03: 복수 원물 2026+2026 허용."""
        self.conn.execute(
            f"""INSERT INTO t_stock_master VALUES
            ('{FARM}','{WH}','{ITEM_RAW}','{VARIETY}','NONE','{RAW_SIZE}',20.0,2026,
             '2026-09-01',5,0,0,'U1',NULL,NULL)"""
        )
        self.conn.commit()
        self.svc.confirm("U1", ProductionConfirmIn(
            farm_cd=FARM, prod_type=PROD_TYPE_PACK,
            input_source=INPUT_SOURCE_RAW_STOCK, variety_cd=VARIETY, wh_cd=WH,
            pack_weight=15.0,
            lines=[ProductionLineIn(grade_cd=GRADE, size_cd=SIZE_DAI, qty=1)],
            raw_consumptions=[
                self._raw(2026, qty=1, storage="2026-08-10"),
                self._raw(2026, qty=1, storage="2026-09-01"),
            ],
        ))
        self.assertEqual(_product_harvest_year(self.conn), 2026)

    def test_hyear_04_mixed_year_blocked(self) -> None:
        """T-HYEAR-04: 2025+2026 혼합 차단, 재고 불변."""
        self.conn.execute(
            f"""INSERT INTO t_stock_master VALUES
            ('{FARM}','{WH}','{ITEM_RAW}','{VARIETY}','NONE','{RAW_SIZE}',20.0,2025,
             '2025-10-01',5,0,0,'U1',NULL,NULL)"""
        )
        self.conn.commit()
        with self.assertRaises(ProductionError) as ctx:
            self.svc.confirm("U1", ProductionConfirmIn(
                farm_cd=FARM, prod_type=PROD_TYPE_PACK,
                input_source=INPUT_SOURCE_RAW_STOCK, variety_cd=VARIETY, wh_cd=WH,
                pack_weight=15.0,
                lines=[ProductionLineIn(grade_cd=GRADE, size_cd=SIZE_DAI, qty=1)],
                raw_consumptions=[
                    self._raw(2026, qty=1, storage="2026-08-10"),
                    self._raw(2025, qty=1, storage="2025-10-01"),
                ],
            ))
        self.assertEqual(ctx.exception.code, "MIXED_YEAR")
        self.assertEqual(_product_in_qty(self.conn), 0.0)
        self.assertEqual(_raw_out_qty(self.conn), 0.0)

    def test_hyear_05_harvest_uses_work_dt_year(self) -> None:
        """T-HYEAR-05: HARVEST work_dt=2026-08-19 → 상품 2026 (생산일 2027이어도)."""
        from datetime import datetime
        from unittest.mock import patch

        fake = datetime(2027, 1, 10, 9, 0, 0)
        with patch("core.production_service.now_ops", return_value=fake), patch(
            "core.production_service.now_ops_str",
            lambda fmt="%Y-%m-%d %H:%M:%S": fake.strftime(fmt),
        ):
            self.svc.confirm("U1", ProductionConfirmIn(
                farm_cd=FARM, prod_type=PROD_TYPE_PACK,
                input_source=INPUT_SOURCE_HARVEST, variety_cd=VARIETY, wh_cd=WH,
                pack_weight=15.0, harvest_work_id=WORK_HARVEST,
                lines=[ProductionLineIn(grade_cd=GRADE, size_cd=SIZE_DAI, qty=1)],
            ))
        self.assertEqual(_product_harvest_year(self.conn), 2026)

    def test_hyear_06_alloc_matches_same_year_row(self) -> None:
        """T-HYEAR-06: 주문 harvest_year=2026이면 생산재고 row 매칭."""
        from core.order_allocation_service import OrderAllocationService

        self.svc.confirm("U1", ProductionConfirmIn(
            farm_cd=FARM, prod_type=PROD_TYPE_PACK,
            input_source=INPUT_SOURCE_RAW_STOCK, variety_cd=VARIETY, wh_cd=WH,
            pack_weight=15.0,
            lines=[ProductionLineIn(grade_cd=GRADE, size_cd=SIZE_DAI, qty=3)],
            raw_consumptions=[self._raw(2026)],
        ))
        alloc = OrderAllocationService(self.conn)
        cur = self.conn.cursor()
        try:
            rows = alloc._fifo_stock_rows(cur, FARM, {
                "wh_cd": WH, "item_cd": ITEM_PRODUCT, "variety_cd": VARIETY,
                "grade_cd": GRADE, "size_cd": SIZE_DAI, "weight": 15.0,
                "harvest_year": 2026,
            })
        finally:
            cur.close()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["key"].harvest_year, 2026)

    def test_hyear_07_alloc_skips_other_year(self) -> None:
        """T-HYEAR-07: harvest_year 불일치 주문은 다른 재고로 처리."""
        from core.order_allocation_service import OrderAllocationService

        self.svc.confirm("U1", ProductionConfirmIn(
            farm_cd=FARM, prod_type=PROD_TYPE_PACK,
            input_source=INPUT_SOURCE_RAW_STOCK, variety_cd=VARIETY, wh_cd=WH,
            pack_weight=15.0,
            lines=[ProductionLineIn(grade_cd=GRADE, size_cd=SIZE_DAI, qty=3)],
            raw_consumptions=[self._raw(2026)],
        ))
        alloc = OrderAllocationService(self.conn)
        cur = self.conn.cursor()
        try:
            rows = alloc._fifo_stock_rows(cur, FARM, {
                "wh_cd": WH, "item_cd": ITEM_PRODUCT, "variety_cd": VARIETY,
                "grade_cd": GRADE, "size_cd": SIZE_DAI, "weight": 15.0,
                "harvest_year": 2025,
            })
        finally:
            cur.close()
        self.assertEqual(len(rows), 0)


if __name__ == "__main__":
    unittest.main()
