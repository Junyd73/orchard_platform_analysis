# -*- coding: utf-8 -*-
"""DEC-036-A — auction ship schema + Core create TX."""

from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import threading
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve()
_SERVER = _HERE.parents[1]
_ROOT = _HERE.parents[2]
for p in (_HERE.parent, _SERVER, _ROOT):
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)

from core.auction_ship_constants import (  # noqa: E402
    AUCTION_SHIP_STATUS_IN_TRANSIT,
    CODE_AUCTION_SHIP_SCHEMA,
    CODE_AUCTION_SHIP_QTY_UNAVAILABLE,
    CODE_AUCTION_SHIP_STOCK_SCHEMA,
    TABLE_AUCTION_SHIP_DETAIL,
    TABLE_AUCTION_SHIP_MASTER,
)
from core.auction_ship_schema import (  # noqa: E402
    auction_ship_schema_ready,
    ensure_auction_ship_schema,
)
from core.auction_ship_service import (  # noqa: E402
    AuctionShipCreateIn,
    AuctionShipError,
    AuctionShipService,
    AuctionShipSpecLineIn,
)
from core.order_allocation_service import OrderAllocationService  # noqa: E402
from core.order_constants import WAREHOUSE_CD_DEFAULT  # noqa: E402
from core.stock_availability import get_active_auction_transit_qty  # noqa: E402
from test_order_service import FARM, _open_tmp, _schema_sql  # noqa: E402

ITEM = "FR010100"
VARIETY = "FR010101"
GRADE = "GR010100"
SIZE = "FR020101"
WEIGHT = 7.5
YEAR = 2025
MARKET_CD = "110001"
MARKET_NM = "서울가락"
CORP = "한국청과㈜"


def _ops_stock_ddl() -> str:
    """운영형 t_stock_master — stock_seq PK."""
    return """
        CREATE TABLE IF NOT EXISTS t_stock_master (
            stock_seq INTEGER PRIMARY KEY AUTOINCREMENT,
            farm_cd TEXT NOT NULL, wh_cd TEXT NOT NULL, item_cd TEXT NOT NULL,
            variety_cd TEXT NOT NULL, grade_cd TEXT, size_cd TEXT,
            weight REAL, harvest_year INTEGER, storage_dt TEXT,
            in_qty REAL DEFAULT 0, out_qty REAL DEFAULT 0, reserved_qty REAL DEFAULT 0,
            reg_id TEXT, mod_id TEXT, mod_dt TEXT
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_stock_master_unique ON t_stock_master(
            farm_cd, wh_cd, item_cd, variety_cd, grade_cd,
            size_cd, weight, harvest_year, storage_dt
        );
    """


def _open_ops() -> tuple[Path, sqlite3.Connection]:
    """경매출하 정상 fixture — stock_seq PK + auction schema."""
    fd, name = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    path = Path(name)
    conn = sqlite3.connect(str(path), timeout=15)
    conn.row_factory = sqlite3.Row
    conn.executescript(_schema_sql())
    conn.execute("DROP TABLE IF EXISTS t_stock_master")
    conn.executescript(_ops_stock_ddl())
    ensure_auction_ship_schema(conn)
    conn.commit()
    return path, conn


def _open_legacy_auction() -> tuple[Path, sqlite3.Connection]:
    """legacy stock( stock_seq 없음 ) + auction schema."""
    path, conn = _open_tmp()
    ensure_auction_ship_schema(conn)
    conn.commit()
    return path, conn


def _insert_stock(
    conn: sqlite3.Connection,
    *,
    storage_dt: str,
    in_qty: float,
    out_qty: float = 0,
    reserved: float = 0,
    stock_seq: int | None = None,
) -> int:
    if stock_seq is None:
        cur = conn.execute(
            """
            INSERT INTO t_stock_master (
                farm_cd, wh_cd, item_cd, variety_cd, grade_cd, size_cd,
                weight, harvest_year, storage_dt, in_qty, out_qty, reserved_qty, reg_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'TEST')
            """,
            (
                FARM,
                WAREHOUSE_CD_DEFAULT,
                ITEM,
                VARIETY,
                GRADE,
                SIZE,
                WEIGHT,
                YEAR,
                storage_dt,
                in_qty,
                out_qty,
                reserved,
            ),
        )
        conn.commit()
        return int(cur.lastrowid)
    conn.execute(
        """
        INSERT INTO t_stock_master (
            stock_seq, farm_cd, wh_cd, item_cd, variety_cd, grade_cd, size_cd,
            weight, harvest_year, storage_dt, in_qty, out_qty, reserved_qty, reg_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'TEST')
        """,
        (
            int(stock_seq),
            FARM,
            WAREHOUSE_CD_DEFAULT,
            ITEM,
            VARIETY,
            GRADE,
            SIZE,
            WEIGHT,
            YEAR,
            storage_dt,
            in_qty,
            out_qty,
            reserved,
        ),
    )
    conn.commit()
    return int(stock_seq)


def _insert_stock_legacy(
    conn: sqlite3.Connection,
    *,
    storage_dt: str,
    in_qty: float,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO t_stock_master (
            farm_cd, wh_cd, item_cd, variety_cd, grade_cd, size_cd,
            weight, harvest_year, storage_dt, in_qty, out_qty, reserved_qty, reg_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 'TEST')
        """,
        (
            FARM,
            WAREHOUSE_CD_DEFAULT,
            ITEM,
            VARIETY,
            GRADE,
            SIZE,
            WEIGHT,
            YEAR,
            storage_dt,
            in_qty,
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def _spec_line(qty: float) -> AuctionShipSpecLineIn:
    return AuctionShipSpecLineIn(
        wh_cd=WAREHOUSE_CD_DEFAULT,
        item_cd=ITEM,
        variety_cd=VARIETY,
        grade_cd=GRADE,
        size_cd=SIZE,
        weight=WEIGHT,
        harvest_year=YEAR,
        qty=qty,
    )


def _payload(*qtys: float) -> AuctionShipCreateIn:
    return AuctionShipCreateIn(
        farm_cd=FARM,
        ship_dt="2026-08-31",
        market_cd=MARKET_CD,
        market_name=MARKET_NM,
        corporation_name=CORP,
        lines=[_spec_line(q) for q in qtys],
        user_id="TEST",
    )


def _counts(conn: sqlite3.Connection) -> dict[str, int]:
    def c(sql: str) -> int:
        row = conn.execute(sql).fetchone()
        return int(row[0]) if row else 0

    sale_logs = 0
    cols = {str(r[1]) for r in conn.execute("PRAGMA table_info(t_stock_log)")}
    if "ref_type" in cols:
        sale_logs = c("SELECT COUNT(*) FROM t_stock_log WHERE ref_type='SALE'")

    return {
        "master": c(f"SELECT COUNT(*) FROM {TABLE_AUCTION_SHIP_MASTER}"),
        "detail": c(f"SELECT COUNT(*) FROM {TABLE_AUCTION_SHIP_DETAIL}"),
        "sales": c("SELECT COUNT(*) FROM t_sales_master"),
        "out_sum": int(conn.execute("SELECT COALESCE(SUM(out_qty),0) FROM t_stock_master").fetchone()[0]),
        "reserved_sum": int(
            conn.execute("SELECT COALESCE(SUM(reserved_qty),0) FROM t_stock_master").fetchone()[0]
        ),
        "sale_logs": sale_logs,
    }


class AuctionShipSchemaTest(unittest.TestCase):
    def test_schema_create_idempotent(self) -> None:
        path, conn = _open_tmp()
        try:
            first = ensure_auction_ship_schema(conn)
            self.assertTrue(first["ok"])
            conn.commit()
            second = ensure_auction_ship_schema(conn)
            self.assertTrue(second["ok"])
            self.assertTrue(auction_ship_schema_ready(conn))
        finally:
            conn.close()
            path.unlink(missing_ok=True)

    def test_schema_on_existing_db_unchanged(self) -> None:
        path, conn = _open_tmp()
        try:
            before = conn.execute("SELECT COUNT(*) FROM t_stock_master").fetchone()[0]
            ensure_auction_ship_schema(conn)
            conn.commit()
            after = conn.execute("SELECT COUNT(*) FROM t_stock_master").fetchone()[0]
            self.assertEqual(before, after)
        finally:
            conn.close()
            path.unlink(missing_ok=True)

    def test_available_without_schema(self) -> None:
        path, conn = _open_tmp()
        try:
            _insert_stock_legacy(conn, storage_dt="2025-10-01", in_qty=20)
            rows = OrderAllocationService(conn).get_available_stock(FARM, item_cd=ITEM)
            self.assertEqual(len(rows), 1)
            self.assertAlmostEqual(rows[0]["available_qty"], 20.0)
        finally:
            conn.close()
            path.unlink(missing_ok=True)

    def test_create_rejects_without_schema(self) -> None:
        path, conn = _open_ops()
        try:
            conn.execute(f"DROP TABLE IF EXISTS {TABLE_AUCTION_SHIP_DETAIL}")
            conn.execute(f"DROP TABLE IF EXISTS {TABLE_AUCTION_SHIP_MASTER}")
            conn.commit()
            _insert_stock(conn, storage_dt="2025-10-01", in_qty=20)
            with self.assertRaises(AuctionShipError) as ctx:
                AuctionShipService(conn).create_shipment(_payload(10))
            self.assertEqual(ctx.exception.code, CODE_AUCTION_SHIP_SCHEMA)
        finally:
            conn.close()
            path.unlink(missing_ok=True)

    def test_create_rejects_without_stock_seq_schema(self) -> None:
        path, conn = _open_legacy_auction()
        try:
            before = _counts(conn)
            _insert_stock_legacy(conn, storage_dt="2025-10-01", in_qty=20)
            with self.assertRaises(AuctionShipError) as ctx:
                AuctionShipService(conn).create_shipment(_payload(10))
            self.assertEqual(ctx.exception.code, CODE_AUCTION_SHIP_STOCK_SCHEMA)
            after = _counts(conn)
            self.assertEqual(after["master"], before["master"])
            self.assertEqual(after["detail"], before["detail"])
            self.assertEqual(after["sales"], before["sales"])
        finally:
            conn.close()
            path.unlink(missing_ok=True)


class AuctionShipCoreTest(unittest.TestCase):
    def test_ship_01_basic_transit(self) -> None:
        path, conn = _open_ops()
        try:
            _insert_stock(conn, storage_dt="2025-10-01", in_qty=20)
            before = _counts(conn)
            out = AuctionShipService(conn).create_shipment(_payload(10))
            self.assertEqual(out["status"], AUCTION_SHIP_STATUS_IN_TRANSIT)
            after = _counts(conn)
            self.assertEqual(after["master"], before["master"] + 1)
            self.assertEqual(after["detail"], before["detail"] + 1)
            self.assertEqual(after["sales"], before["sales"])
            self.assertEqual(after["out_sum"], before["out_sum"])
            self.assertEqual(after["reserved_sum"], before["reserved_sum"])
            rows = OrderAllocationService(conn).get_available_stock(FARM, item_cd=ITEM)
            self.assertAlmostEqual(rows[0]["available_qty"], 10.0)
        finally:
            conn.close()
            path.unlink(missing_ok=True)

    def test_ship_02_reserved_and_transit(self) -> None:
        path, conn = _open_ops()
        try:
            _insert_stock(conn, storage_dt="2025-10-01", in_qty=20, reserved=5)
            AuctionShipService(conn).create_shipment(_payload(10))
            rows = OrderAllocationService(conn).get_available_stock(FARM, item_cd=ITEM)
            self.assertAlmostEqual(rows[0]["available_qty"], 5.0)
        finally:
            conn.close()
            path.unlink(missing_ok=True)

    def test_ship_03_over_available_reject(self) -> None:
        path, conn = _open_ops()
        try:
            _insert_stock(conn, storage_dt="2025-10-01", in_qty=10)
            with self.assertRaises(AuctionShipError) as ctx:
                AuctionShipService(conn).create_shipment(_payload(11))
            self.assertEqual(ctx.exception.code, CODE_AUCTION_SHIP_QTY_UNAVAILABLE)
            self.assertEqual(_counts(conn)["master"], 0)
        finally:
            conn.close()
            path.unlink(missing_ok=True)

    def test_physical_stock_seq_not_rowid(self) -> None:
        path, conn = _open_ops()
        try:
            stock_seq = _insert_stock(
                conn,
                storage_dt="2025-10-01",
                in_qty=20,
                stock_seq=101,
            )
            self.assertEqual(stock_seq, 101)
            rowid = conn.execute(
                "SELECT rowid FROM t_stock_master WHERE stock_seq = ?",
                (101,),
            ).fetchone()[0]
            AuctionShipService(conn).create_shipment(_payload(10))
            detail_seq = conn.execute(
                f"SELECT stock_seq FROM {TABLE_AUCTION_SHIP_DETAIL}"
            ).fetchone()[0]
            self.assertEqual(int(detail_seq), 101)
            self.assertNotEqual(int(detail_seq), 1)
            if int(rowid) == 1:
                self.assertNotEqual(int(detail_seq), int(rowid))
        finally:
            conn.close()
            path.unlink(missing_ok=True)

    def test_ship_05_fifo_split(self) -> None:
        path, conn = _open_ops()
        try:
            _insert_stock(conn, storage_dt="2025-10-01", in_qty=6, stock_seq=101)
            _insert_stock(conn, storage_dt="2025-10-02", in_qty=10, stock_seq=205)
            AuctionShipService(conn).create_shipment(_payload(8))
            rows = conn.execute(
                f"""
                SELECT d.stock_seq, d.farm_shipped_qty
                FROM {TABLE_AUCTION_SHIP_DETAIL} d
                ORDER BY d.line_seq
                """
            ).fetchall()
            self.assertEqual(len(rows), 2)
            by_seq = {int(r[0]): float(r[1]) for r in rows}
            self.assertAlmostEqual(by_seq[101], 6.0)
            self.assertAlmostEqual(by_seq[205], 2.0)
        finally:
            conn.close()
            path.unlink(missing_ok=True)

    def test_ship_06_multi_spec(self) -> None:
        path, conn = _open_ops()
        try:
            _insert_stock(conn, storage_dt="2025-10-01", in_qty=10)
            conn.execute(
                """
                INSERT INTO t_stock_master (
                    farm_cd, wh_cd, item_cd, variety_cd, grade_cd, size_cd,
                    weight, harvest_year, storage_dt, in_qty, out_qty, reserved_qty, reg_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 'TEST')
                """,
                (
                    FARM, WAREHOUSE_CD_DEFAULT, ITEM, VARIETY, GRADE, "FR020102",
                    WEIGHT, YEAR, "2025-10-01", 15,
                ),
            )
            conn.commit()
            payload = AuctionShipCreateIn(
                farm_cd=FARM,
                ship_dt="2026-08-31",
                market_cd=MARKET_CD,
                market_name=MARKET_NM,
                corporation_name=CORP,
                lines=[_spec_line(5), AuctionShipSpecLineIn(
                    wh_cd=WAREHOUSE_CD_DEFAULT,
                    item_cd=ITEM,
                    variety_cd=VARIETY,
                    grade_cd=GRADE,
                    size_cd="FR020102",
                    weight=WEIGHT,
                    harvest_year=YEAR,
                    qty=7,
                )],
            )
            out = AuctionShipService(conn).create_shipment(payload)
            self.assertEqual(out["line_count"], 2)
            self.assertAlmostEqual(out["total_farm_shipped_qty"], 12.0)
        finally:
            conn.close()
            path.unlink(missing_ok=True)

    def test_ship_08_non_positive_available_reject(self) -> None:
        path, conn = _open_ops()
        try:
            _insert_stock(conn, storage_dt="2025-10-01", in_qty=5, out_qty=10)
            with self.assertRaises(AuctionShipError):
                AuctionShipService(conn).create_shipment(_payload(1))
        finally:
            conn.close()
            path.unlink(missing_ok=True)

    def test_ship_07_sales_stock_invariants(self) -> None:
        path, conn = _open_ops()
        try:
            _insert_stock(conn, storage_dt="2025-10-01", in_qty=20)
            before = _counts(conn)
            AuctionShipService(conn).create_shipment(_payload(10))
            after = _counts(conn)
            self.assertEqual(after["sales"], before["sales"])
            self.assertEqual(after["out_sum"], before["out_sum"])
            self.assertEqual(after["reserved_sum"], before["reserved_sum"])
            self.assertEqual(after["sale_logs"], before["sale_logs"])
            self.assertEqual(after["master"], before["master"] + 1)
            self.assertEqual(after["detail"], before["detail"] + 1)
        finally:
            conn.close()
            path.unlink(missing_ok=True)

    def test_ship_04_concurrency(self) -> None:
        path, conn = _open_ops()
        try:
            stock_seq = _insert_stock(conn, storage_dt="2025-10-01", in_qty=10)
            results: list[str] = []
            lock = threading.Lock()

            def worker() -> None:
                c = sqlite3.connect(str(path), timeout=30)
                c.row_factory = sqlite3.Row
                try:
                    AuctionShipService(c).create_shipment(_payload(7))
                    with lock:
                        results.append("ok")
                except AuctionShipError as exc:
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
            self.assertEqual(results.count("ok"), 1)
            self.assertEqual(
                results.count(CODE_AUCTION_SHIP_QTY_UNAVAILABLE),
                1,
            )
            c2 = sqlite3.connect(str(path))
            transit = get_active_auction_transit_qty(
                c2, farm_cd=FARM, stock_seq=stock_seq,
            )
            c2.close()
            self.assertAlmostEqual(transit, 7.0)
        finally:
            conn.close()
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
