# -*- coding: utf-8 -*-
"""DEC-035-B HARVEST N:M production consumption tests."""

from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

_REPO = Path(__file__).resolve().parents[2]
for p in (_REPO, _REPO / "server"):
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)

from core.harvest_consumption_guard import harvest_consumption_table_exists  # noqa: E402
from core.harvest_consumption_schema import (  # noqa: E402
    TABLE_HARVEST_CONSUMPTION,
    ensure_harvest_consumption_schema,
)
from core.production_service import (  # noqa: E402
    HarvestConsumptionIn,
    ProductionConfirmIn,
    ProductionError,
    ProductionLineIn,
    ProductionService,
)
from core.sales_stock_trace_schema import (  # noqa: E402
    REF_TYPE_SALE,
    ensure_sales_stock_trace_schema,
    stock_log_production_trace_ready,
)
from core.stock_constants import (  # noqa: E402
    INPUT_SOURCE_HARVEST,
    ITEM_PRODUCT,
    PROD_TYPE_PACK,
    REF_TYPE_PRODUCTION,
    REMARK_PACK_IN,
    WORK_MID_CD_HARVEST,
)
from core.work_log_constants import WORK_STATUS_DONE  # noqa: E402

FARM = "OR001"
VARIETY = "FR010101"
VARIETY2 = "FR010102"
WH = "WH01"
GRADE = "GR010100"
SIZE_DAI = "FR020101"
HARVEST_MID = WORK_MID_CD_HARVEST
WORK_A = "W-H-A"
WORK_B = "W-H-B"
WORK_OTHER = "W-OTHER"
WORK_NON_HARVEST = "W-NON-H"


def _line(qty: int = 1) -> ProductionLineIn:
    return ProductionLineIn(grade_cd=GRADE, size_cd=SIZE_DAI, qty=qty, weight=15.0)


def _pack_payload(
    *,
    consumptions: list[HarvestConsumptionIn],
    lines: list[ProductionLineIn] | None = None,
    variety: str = VARIETY,
) -> ProductionConfirmIn:
    return ProductionConfirmIn(
        farm_cd=FARM,
        prod_type=PROD_TYPE_PACK,
        input_source=INPUT_SOURCE_HARVEST,
        variety_cd=variety,
        wh_cd=WH,
        pack_weight=15.0,
        harvest_consumptions=consumptions,
        lines=lines or [_line(sum(c.qty for c in consumptions))],
    )


def _build_db(*, with_consumption: bool = True, with_trace: bool = True) -> tuple[sqlite3.Connection, Path]:
    fd, path_s = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    path = Path(path_s)
    conn = sqlite3.connect(str(path), timeout=15, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        f"""
        CREATE TABLE m_common_code (
            farm_cd TEXT, code_cd TEXT, code_nm TEXT, parent_cd TEXT
        );
        INSERT INTO m_common_code VALUES
          ('{FARM}','{VARIETY}','신고','FR010100'),
          ('{FARM}','{VARIETY2}','배','FR010100'),
          ('{FARM}','{GRADE}','특','GR01'),
          ('{FARM}','{SIZE_DAI}','18과','FR020100'),
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
          ('{WORK_A}','2026-08-19','{FARM}','{HARVEST_MID}','{VARIETY}',30,'WO010100','U1',NULL,NULL),
          ('{WORK_B}','2026-08-19','{FARM}','{HARVEST_MID}','{VARIETY}',40,'WO010100','U1',NULL,NULL),
          ('{WORK_OTHER}','2026-08-19','OTHER','{HARVEST_MID}','{VARIETY}',10,'WO010100','U1',NULL,NULL),
          ('{WORK_NON_HARVEST}','2026-08-19','{FARM}','WK010100','{VARIETY}',10,'WO010100','U1',NULL,NULL);

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
        """
    )
    if with_consumption:
        ensure_harvest_consumption_schema(conn)
    if with_trace:
        ensure_sales_stock_trace_schema(conn)
    conn.commit()
    return conn, path


def _consumed_qty(conn: sqlite3.Connection, work_id: str = WORK_A) -> int:
    row = conn.execute(
        f"""
        SELECT COALESCE(SUM(consumed_container_qty), 0)
        FROM {TABLE_HARVEST_CONSUMPTION}
        WHERE farm_cd=? AND harvest_work_id=? AND is_valid=1
        """,
        (FARM, work_id),
    ).fetchone()
    return int(row[0])


def _product_in_qty(conn: sqlite3.Connection) -> float:
    row = conn.execute(
        "SELECT COALESCE(SUM(in_qty), 0) FROM t_stock_master WHERE farm_cd=? AND item_cd=?",
        (FARM, ITEM_PRODUCT),
    ).fetchone()
    return float(row[0])


def _product_in_log_qty(conn: sqlite3.Connection) -> float:
    row = conn.execute(
        """
        SELECT COALESCE(SUM(qty), 0)
        FROM t_stock_log
        WHERE farm_cd=? AND item_cd=? AND io_type='IN'
        """,
        (FARM, ITEM_PRODUCT),
    ).fetchone()
    return float(row[0])


def _run_concurrent_confirm(
    path: Path,
    *,
    work_id: str = WORK_A,
    use_qty: int = 8,
) -> list[str | int]:
    results: list[str | int] = []
    lock = threading.Lock()

    def worker() -> None:
        c = sqlite3.connect(str(path), timeout=15)
        c.row_factory = sqlite3.Row
        svc = ProductionService(c)
        try:
            svc.confirm(
                "U1",
                _pack_payload(
                    consumptions=[HarvestConsumptionIn(work_id=work_id, qty=use_qty)],
                    lines=[_line(use_qty)],
                ),
            )
            with lock:
                results.append(use_qty)
        except ProductionError as exc:
            with lock:
                results.append(exc.code)
        finally:
            c.close()

    t1 = threading.Thread(target=worker)
    t2 = threading.Thread(target=worker)
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    return results


def _assert_harvest_confirm_rolled_back(
    testcase: unittest.TestCase,
    conn: sqlite3.Connection,
    *,
    work_id: str = WORK_A,
) -> None:
    status = conn.execute(
        "SELECT status_cd FROM t_work_detail WHERE work_id=?", (work_id,)
    ).fetchone()[0]
    testcase.assertEqual(_product_in_qty(conn), 0.0)
    if harvest_consumption_table_exists(conn):
        testcase.assertEqual(
            conn.execute(f"SELECT COUNT(*) FROM {TABLE_HARVEST_CONSUMPTION}").fetchone()[0],
            0,
        )
    testcase.assertEqual(
        conn.execute(
            "SELECT COUNT(*) FROM t_stock_log WHERE item_cd=? AND io_type='IN'",
            (ITEM_PRODUCT,),
        ).fetchone()[0],
        0,
    )
    testcase.assertNotEqual(status, WORK_STATUS_DONE)


class HarvestNmCoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self.conn, self.path = _build_db()
        self.svc = ProductionService(self.conn)

    def tearDown(self) -> None:
        self.conn.close()
        self.path.unlink(missing_ok=True)

    def test_nm_01_two_harvests_one_event(self) -> None:
        payload = _pack_payload(
            consumptions=[
                HarvestConsumptionIn(work_id=WORK_A, qty=20),
                HarvestConsumptionIn(work_id=WORK_B, qty=15),
            ],
            lines=[_line(35)],
        )
        self.svc.confirm("U1", payload)
        rows = self.conn.execute(
            f"""
            SELECT prod_confirm_id, harvest_work_id, consumed_container_qty
            FROM {TABLE_HARVEST_CONSUMPTION}
            ORDER BY harvest_work_id
            """
        ).fetchall()
        self.assertEqual(len(rows), 2)
        pid = str(rows[0]["prod_confirm_id"])
        self.assertEqual(pid, str(rows[1]["prod_confirm_id"]))
        self.assertTrue(pid.startswith("PRD"))
        self.assertEqual(
            {str(r["harvest_work_id"]): int(r["consumed_container_qty"]) for r in rows},
            {WORK_A: 20, WORK_B: 15},
        )
        rec_a = next(r for r in self.svc.list_harvest_records(FARM) if r["work_id"] == WORK_A)
        rec_b = next(r for r in self.svc.list_harvest_records(FARM) if r["work_id"] == WORK_B)
        self.assertEqual(rec_a["remaining_container_qty"], 10)
        self.assertEqual(rec_b["remaining_container_qty"], 25)
        prod_in = self.conn.execute(
            "SELECT COALESCE(SUM(in_qty),0) FROM t_stock_master WHERE item_cd=?",
            (ITEM_PRODUCT,),
        ).fetchone()[0]
        self.assertEqual(float(prod_in), 35.0)

    def test_nm_02_reuse_remaining(self) -> None:
        self.svc.confirm(
            "U1",
            _pack_payload(
                consumptions=[HarvestConsumptionIn(work_id=WORK_A, qty=20)],
                lines=[_line(5)],
            ),
        )
        self.svc.confirm(
            "U1",
            _pack_payload(
                consumptions=[HarvestConsumptionIn(work_id=WORK_A, qty=5)],
                lines=[_line(3)],
            ),
        )
        rec = next(r for r in self.svc.list_harvest_records(FARM) if r["work_id"] == WORK_A)
        self.assertEqual(rec["remaining_container_qty"], 5)
        with self.assertRaises(ProductionError) as ctx:
            self.svc.confirm(
                "U1",
                _pack_payload(
                    consumptions=[HarvestConsumptionIn(work_id=WORK_A, qty=6)],
                    lines=[_line(1)],
                ),
            )
        self.assertEqual(ctx.exception.code, "HARVEST_EXCEED")

    def test_nm_03_legacy_only_rejected(self) -> None:
        payload = ProductionConfirmIn(
            farm_cd=FARM,
            prod_type=PROD_TYPE_PACK,
            input_source=INPUT_SOURCE_HARVEST,
            variety_cd=VARIETY,
            pack_weight=15.0,
            harvest_work_id=WORK_A,
            lines=[_line(1)],
        )
        with self.assertRaises(ProductionError) as ctx:
            self.svc.confirm("U1", payload)
        self.assertEqual(ctx.exception.code, "HARVEST_CONSUMPTIONS")
        self.assertEqual(
            self.conn.execute(f"SELECT COUNT(*) FROM {TABLE_HARVEST_CONSUMPTION}").fetchone()[0],
            0,
        )
        self.assertEqual(
            self.conn.execute(
                "SELECT COALESCE(SUM(in_qty),0) FROM t_stock_master WHERE item_cd=?",
                (ITEM_PRODUCT,),
            ).fetchone()[0],
            0,
        )

    def test_nm_04_validation_matrix(self) -> None:
        cases: list[tuple[ProductionConfirmIn, str]] = [
            (
                _pack_payload(consumptions=[HarvestConsumptionIn(work_id=WORK_A, qty=0)]),
                "HARVEST_CONSUMPTIONS",
            ),
            (
                _pack_payload(consumptions=[HarvestConsumptionIn(work_id=WORK_A, qty=31)]),
                "HARVEST_EXCEED",
            ),
            (
                _pack_payload(consumptions=[HarvestConsumptionIn(work_id="NO-SUCH", qty=1)]),
                "HARVEST_NOT_FOUND",
            ),
            (
                _pack_payload(consumptions=[HarvestConsumptionIn(work_id=WORK_OTHER, qty=1)]),
                "HARVEST_NOT_FOUND",
            ),
            (
                _pack_payload(consumptions=[HarvestConsumptionIn(work_id=WORK_NON_HARVEST, qty=1)]),
                "HARVEST_NOT_HARVEST",
            ),
            (
                _pack_payload(
                    consumptions=[
                        HarvestConsumptionIn(work_id=WORK_A, qty=1),
                        HarvestConsumptionIn(work_id=WORK_A, qty=1),
                    ]
                ),
                "HARVEST_DUPLICATE",
            ),
            (
                ProductionConfirmIn(
                    farm_cd=FARM,
                    prod_type=PROD_TYPE_PACK,
                    input_source=INPUT_SOURCE_HARVEST,
                    variety_cd=VARIETY,
                    harvest_consumptions=[],
                    lines=[_line(1)],
                ),
                "HARVEST_CONSUMPTIONS",
            ),
        ]
        for payload, code in cases:
            with self.subTest(code=code):
                with self.assertRaises(ProductionError) as ctx:
                    self.svc.confirm("U1", payload)
                self.assertEqual(ctx.exception.code, code)

        self.conn.execute(
            f"INSERT INTO t_work_detail VALUES ('W-Y2','2025-08-19','{FARM}','{HARVEST_MID}','{VARIETY}',10,'WO010100','U1',NULL,NULL)"
        )
        self.conn.commit()
        with self.assertRaises(ProductionError) as ctx:
            self.svc.confirm(
                "U1",
                _pack_payload(
                    consumptions=[
                        HarvestConsumptionIn(work_id=WORK_A, qty=1),
                        HarvestConsumptionIn(work_id="W-Y2", qty=1),
                    ]
                ),
            )
        self.assertEqual(ctx.exception.code, "MIXED_YEAR")

        self.conn.execute(
            f"INSERT INTO t_work_detail VALUES ('W-V2','2026-08-19','{FARM}','{HARVEST_MID}','{VARIETY2}',10,'WO010100','U1',NULL,NULL)"
        )
        self.conn.commit()
        with self.assertRaises(ProductionError) as ctx:
            self.svc.confirm(
                "U1",
                _pack_payload(
                    consumptions=[
                        HarvestConsumptionIn(work_id=WORK_A, qty=1),
                        HarvestConsumptionIn(work_id="W-V2", qty=1),
                    ]
                ),
            )
        self.assertEqual(ctx.exception.code, "MIXED_VARIETY")

    def test_nm_05_schema_precondition_consumption_table(self) -> None:
        conn, path = _build_db(with_consumption=False, with_trace=True)
        try:
            svc = ProductionService(conn)
            with self.assertRaises(ProductionError) as ctx:
                svc.confirm(
                    "U1",
                    _pack_payload(consumptions=[HarvestConsumptionIn(work_id=WORK_A, qty=1)]),
                )
            self.assertEqual(ctx.exception.code, "HARVEST_SCHEMA")
            _assert_harvest_confirm_rolled_back(self, conn)
        finally:
            conn.close()
            path.unlink(missing_ok=True)

    def test_nm_05b_schema_precondition_trace_columns(self) -> None:
        conn, path = _build_db(with_consumption=True, with_trace=False)
        try:
            self.assertFalse(stock_log_production_trace_ready(conn))
            svc = ProductionService(conn)
            with self.assertRaises(ProductionError) as ctx:
                svc.confirm(
                    "U1",
                    _pack_payload(consumptions=[HarvestConsumptionIn(work_id=WORK_A, qty=1)]),
                )
            self.assertEqual(ctx.exception.code, "HARVEST_TRACE_SCHEMA")
            _assert_harvest_confirm_rolled_back(self, conn)
        finally:
            conn.close()
            path.unlink(missing_ok=True)

    def test_nm_06_tx_rollback_after_consumption(self) -> None:
        payload = _pack_payload(
            consumptions=[HarvestConsumptionIn(work_id=WORK_A, qty=5)],
            lines=[
                ProductionLineIn(grade_cd=GRADE, size_cd=SIZE_DAI, qty=3, weight=15.0),
                ProductionLineIn(grade_cd=GRADE, size_cd=SIZE_DAI, qty=2, weight=0.0),
            ],
        )
        with self.assertRaises(ProductionError):
            self.svc.confirm("U1", payload)
        self.assertEqual(
            self.conn.execute(f"SELECT COUNT(*) FROM {TABLE_HARVEST_CONSUMPTION}").fetchone()[0],
            0,
        )
        self.assertEqual(
            self.conn.execute(
                "SELECT COUNT(*) FROM t_stock_log WHERE item_cd=? AND io_type='IN'",
                (ITEM_PRODUCT,),
            ).fetchone()[0],
            0,
        )
        status = self.conn.execute(
            "SELECT status_cd FROM t_work_detail WHERE work_id=?", (WORK_A,)
        ).fetchone()[0]
        self.assertNotEqual(status, WORK_STATUS_DONE)

    def test_nm_07_trace_same_prod_confirm_id(self) -> None:
        payload = _pack_payload(
            consumptions=[
                HarvestConsumptionIn(work_id=WORK_A, qty=2),
                HarvestConsumptionIn(work_id=WORK_B, qty=3),
            ],
            lines=[
                ProductionLineIn(grade_cd=GRADE, size_cd=SIZE_DAI, qty=4, weight=15.0),
                ProductionLineIn(grade_cd=GRADE, size_cd=SIZE_DAI, qty=1, weight=7.5),
            ],
        )
        self.svc.confirm("U1", payload)
        pid = self.conn.execute(
            f"SELECT prod_confirm_id FROM {TABLE_HARVEST_CONSUMPTION} LIMIT 1"
        ).fetchone()[0]
        logs = self.conn.execute(
            """
            SELECT ref_type, ref_id, qty FROM t_stock_log
            WHERE item_cd=? AND io_type='IN' AND remark=?
            ORDER BY log_id
            """,
            (ITEM_PRODUCT, REMARK_PACK_IN),
        ).fetchall()
        self.assertEqual(len(logs), 2)
        for row in logs:
            self.assertEqual(row["ref_type"], REF_TYPE_PRODUCTION)
            self.assertEqual(row["ref_id"], pid)

    def test_nm_08_harvest_records_without_table(self) -> None:
        conn, path = _build_db(with_consumption=False)
        try:
            svc = ProductionService(conn)
            rows = svc.list_harvest_records(FARM)
            self.assertEqual(rows[0]["consumed_container_qty"], 0)
            self.assertEqual(
                rows[0]["remaining_container_qty"],
                rows[0]["harvest_container_qty"],
            )
            self.assertEqual(rows[0]["harvest_year"], 2026)
        finally:
            conn.close()
            path.unlink(missing_ok=True)

    def test_nm_09_done_marks_all_used_works(self) -> None:
        payload = _pack_payload(
            consumptions=[
                HarvestConsumptionIn(work_id=WORK_A, qty=1),
                HarvestConsumptionIn(work_id=WORK_B, qty=1),
            ],
            lines=[_line(2)],
        )
        self.svc.confirm("U1", payload)
        for wid in (WORK_A, WORK_B):
            status = self.conn.execute(
                "SELECT status_cd FROM t_work_detail WHERE work_id=?", (wid,)
            ).fetchone()[0]
            self.assertEqual(status, WORK_STATUS_DONE)

    def test_nm_10_negative_remaining_blocks_confirm(self) -> None:
        self.conn.execute(
            f"""
            INSERT INTO {TABLE_HARVEST_CONSUMPTION} (
                farm_cd, prod_confirm_id, harvest_work_id,
                consumed_container_qty, is_valid, reg_id, reg_dt
            ) VALUES (?, 'PRD20260819-001', ?, 35, 1, 'U1', '2026-08-19 10:00:00')
            """,
            (FARM, WORK_A),
        )
        self.conn.commit()
        with self.assertRaises(ProductionError) as ctx:
            self.svc.confirm(
                "U1",
                _pack_payload(consumptions=[HarvestConsumptionIn(work_id=WORK_A, qty=1)]),
            )
        self.assertEqual(ctx.exception.code, "HARVEST_REMAINING_NEGATIVE")

    def test_nm_11_prod_confirm_id_seq(self) -> None:
        from datetime import datetime

        fake = datetime(2026, 8, 19, 10, 0, 0)
        with patch("core.production_service.now_ops", return_value=fake), patch(
            "core.production_service.now_ops_str",
            lambda fmt="%Y-%m-%d %H:%M:%S": fake.strftime(fmt),
        ):
            self.svc.confirm(
                "U1",
                _pack_payload(consumptions=[HarvestConsumptionIn(work_id=WORK_A, qty=1)]),
            )
            self.svc.confirm(
                "U1",
                _pack_payload(consumptions=[HarvestConsumptionIn(work_id=WORK_B, qty=1)]),
            )
        ids = [
            str(r[0])
            for r in self.conn.execute(
                f"SELECT prod_confirm_id FROM {TABLE_HARVEST_CONSUMPTION} ORDER BY consumption_seq"
            ).fetchall()
        ]
        self.assertEqual(ids, ["PRD20260819-001", "PRD20260819-002"])

    def test_nm_12_sale_trace_regression(self) -> None:
        self.conn.execute(
            """
            INSERT INTO t_stock_log
            (farm_cd, item_cd, variety_cd, harvest_year, grade_cd, size_cd,
             weight, io_type, qty, remark, reg_id, ref_type, ref_id)
            VALUES (?, ?, ?, 2026, ?, ?, 15.0, 'OUT', 1, '판매', 'U1', ?, 'SALE-001')
            """,
            (FARM, ITEM_PRODUCT, VARIETY, GRADE, SIZE_DAI, REF_TYPE_SALE),
        )
        self.conn.commit()
        self.svc.confirm(
            "U1",
            _pack_payload(consumptions=[HarvestConsumptionIn(work_id=WORK_A, qty=1)]),
        )
        sale = self.conn.execute(
            "SELECT ref_type, ref_id FROM t_stock_log WHERE ref_id='SALE-001'"
        ).fetchone()
        self.assertEqual(sale["ref_type"], REF_TYPE_SALE)


class HarvestNmConcurrencyTest(unittest.TestCase):
    def test_nm_concurrent_remaining_10_one_success(self) -> None:
        """original/remaining=10, 8+8 → 정확히 1건만 성공."""
        conn, path = _build_db()
        try:
            conn.execute(
                "UPDATE t_work_detail SET harvest_container_qty=? WHERE work_id=?",
                (10, WORK_A),
            )
            conn.commit()
            results = _run_concurrent_confirm(path, work_id=WORK_A, use_qty=8)
            success = [x for x in results if isinstance(x, int)]
            failures = [x for x in results if isinstance(x, str)]
            self.assertEqual(len(success), 1)
            self.assertEqual(success[0], 8)
            self.assertEqual(len(failures), 1)
            self.assertEqual(failures[0], "HARVEST_EXCEED")
            self.assertEqual(_consumed_qty(conn, WORK_A), 8)
            self.assertLessEqual(_consumed_qty(conn, WORK_A), 10)
            self.assertEqual(_product_in_log_qty(conn), 8.0)
        finally:
            conn.close()
            path.unlink(missing_ok=True)

    def test_nm_concurrent_remaining_30_both_success(self) -> None:
        """original/remaining=30, 8+8 → 둘 다 성공 가능."""
        conn, path = _build_db()
        try:
            results = _run_concurrent_confirm(path, work_id=WORK_A, use_qty=8)
            success = sorted(x for x in results if isinstance(x, int))
            self.assertEqual(success, [8, 8])
            self.assertEqual(_consumed_qty(conn, WORK_A), 16)
            self.assertLessEqual(_consumed_qty(conn, WORK_A), 30)
            self.assertEqual(_product_in_log_qty(conn), 16.0)
        finally:
            conn.close()
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
