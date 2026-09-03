# -*- coding: utf-8 -*-
"""DEC-037 Stage C — auction match finalize Core (mock candidates, temp DB)."""

from __future__ import annotations

import sqlite3
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_HERE = Path(__file__).resolve()
_SERVER = _HERE.parents[1]
_ROOT = _HERE.parents[2]
for p in (_HERE.parent, _SERVER, _ROOT):
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)

from core.auction_candidate_constants import (  # noqa: E402
    SOURCE_REALTIME,
    SOURCE_SETTLEMENT,
)
from core.auction_candidate_service import AuctionCandidateService  # noqa: E402
from core.auction_finalize_service import (  # noqa: E402
    AuctionDiscrepancyIn,
    AuctionFinalizeError,
    AuctionFinalizeIn,
    AuctionFinalizeService,
    AuctionSelectedIn,
    _allocate_reverse_fifo,
)
from core.auction_match_constants import (  # noqa: E402
    CODE_AUCTION_MATCH_AMBIGUOUS_SPEC,
    CODE_AUCTION_MATCH_DISCREPANCY,
    CODE_AUCTION_MATCH_DUPLICATE_SOURCE,
    CODE_AUCTION_MATCH_GRADE,
    CODE_AUCTION_MATCH_RETURN,
    CODE_AUCTION_MATCH_SPEC_UNMATCHED,
    CODE_AUCTION_MATCH_STALE,
    CODE_AUCTION_MATCH_STATUS,
    CODE_AUCTION_MATCH_UNRESOLVED,
    INDEX_AUCTION_MATCH_SOURCE_ACTIVE_LEGACY,
    INDEX_AUCTION_MATCH_SOURCE_KEY_ACTIVE,
    MSG_REMARK_AUCTION_RETURN,
    REASON_DAMAGE,
    REASON_OTHER,
    REASON_QTY_ERROR,
    REASON_RETURN,
    SALES_SOURCE_AUCTION,
    TABLE_AUCTION_MATCH_DETAIL,
    TABLE_AUCTION_QTY_DISCREPANCY,
    TABLE_AUCTION_RETURN_LINE,
)
from core.auction_match_schema import (  # noqa: E402
    active_source_key_duplicates,
    auction_match_schema_ready,
    ensure_auction_match_schema,
)
from core.auction_ship_constants import (  # noqa: E402
    AUCTION_SHIP_STATUS_COMPLETED,
    AUCTION_SHIP_STATUS_IN_TRANSIT,
    CODE_AUCTION_SHIP_CANCEL_STATUS,
    IO_TYPE_IN,
    IO_TYPE_OUT,
    REF_TYPE_AUCTION_SHIP,
)
from core.auction_ship_service import (  # noqa: E402
    AuctionShipCreateIn,
    AuctionShipError,
    AuctionShipService,
    AuctionShipSpecLineIn,
)
from core.order_constants import WAREHOUSE_CD_DEFAULT  # noqa: E402
from core.order_ship_constants import SALES_STATUS_CONFIRMED  # noqa: E402
from core.sales_class_constants import (  # noqa: E402
    SALES_CATEGORY_AUCTION,
    SALES_ROUTE_AUCTION,
    SALES_TYPE_WHOLESALE,
)
from test_auction_candidate_service import (  # noqa: E402
    CORP,
    FARM,
    MARKET_CD,
    TRADE_DT,
    _ensure_farm,
    _row,
)
from test_auction_ship_service import (  # noqa: E402
    GRADE,
    ITEM,
    SIZE,
    VARIETY,
    WEIGHT,
    YEAR,
    _insert_stock,
    _open_ops,
    _payload,
    _spec_line,
)

GRADE2 = "GR010200"
SIZE2 = "FR020102"
SIZE_NM = "15과"
FARM2 = "OR002"


def _index_sql(conn: sqlite3.Connection, name: str) -> str:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='index' AND name=? LIMIT 1",
        (name,),
    ).fetchone()
    return str(row[0] or "") if row and row[0] else ""


def _insert_match_row(
    conn: sqlite3.Connection,
    *,
    farm: str,
    shipment_id: str,
    source_key: str,
    is_valid: int = 1,
) -> None:
    conn.execute(
        f"""
        INSERT INTO {TABLE_AUCTION_MATCH_DETAIL} (
            farm_cd, shipment_id,
            spec_variety_cd, spec_grade_cd, spec_size_cd, spec_weight,
            source_type, source_key, trade_dt, qty, unit_price, amount,
            is_valid, reg_dt
        ) VALUES (?, ?, ?, ?, ?, ?, 'SETTLEMENT', ?, '2026-09-01', 1, 1, 1, ?, '2026-09-02')
        """,
        (farm, shipment_id, VARIETY, GRADE, SIZE, WEIGHT, source_key, int(is_valid)),
    )


_SALES_DDL = """
DROP TABLE IF EXISTS t_sales_detail;
DROP TABLE IF EXISTS t_sales_master;
CREATE TABLE t_sales_master (
    sales_no TEXT, farm_cd TEXT, sales_dt TEXT, sales_tp TEXT, custm_id TEXT,
    tot_sales_amt REAL, tot_ship_fee REAL DEFAULT 0, tot_item_amt REAL,
    tot_paid_amt REAL DEFAULT 0, tot_unpaid_amt REAL, status_cd TEXT, rmk TEXT,
    reg_id TEXT, reg_dt TEXT, order_no TEXT,
    sales_status TEXT, sales_source TEXT,
    auction_fee REAL DEFAULT 0, extra_cost REAL DEFAULT 0,
    sales_type_cd TEXT, sales_category_cd TEXT, sales_route_cd TEXT,
    mod_id TEXT, mod_dt TEXT,
    PRIMARY KEY (sales_no, farm_cd)
);
CREATE TABLE t_sales_detail (
    sale_detail_no TEXT, sales_no TEXT, farm_cd TEXT,
    item_cd TEXT, variety_cd TEXT, grade_cd TEXT, size_cd TEXT,
    qty REAL, unit_price REAL, tot_item_amt REAL, ship_fee REAL DEFAULT 0,
    tot_sale_amt REAL, tot_paid_amt REAL DEFAULT 0, tot_unpaid_amt REAL,
    dlvry_tp TEXT, order_detail_id TEXT, wh_cd TEXT, stock_seq INTEGER,
    reg_id TEXT, reg_dt TEXT,
    PRIMARY KEY (sale_detail_no, farm_cd)
);
"""


def _open_finalize() -> tuple[Path, sqlite3.Connection]:
    path, conn = _open_ops()
    conn.executescript(_SALES_DDL)
    ensure_auction_match_schema(conn)
    conn.execute(
        "INSERT INTO m_common_code (farm_cd, code_cd, code_nm, parent_cd) VALUES (?, ?, ?, ?)",
        (FARM, SIZE, SIZE_NM, "FR02"),
    )
    conn.execute(
        "INSERT INTO m_common_code (farm_cd, code_cd, code_nm, parent_cd) VALUES (?, ?, ?, ?)",
        (FARM, SIZE2, SIZE_NM, "FR02"),
    )
    _ensure_farm(conn)
    conn.commit()
    return path, conn


def _stock(
    conn: sqlite3.Connection,
    *,
    seq: int,
    storage_dt: str,
    in_qty: float,
    reserved: float = 0,
    grade: str = GRADE,
    size: str = SIZE,
) -> int:
    conn.execute(
        """
        INSERT INTO t_stock_master (
            stock_seq, farm_cd, wh_cd, item_cd, variety_cd, grade_cd, size_cd,
            weight, harvest_year, storage_dt, in_qty, out_qty, reserved_qty, reg_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, 'TEST')
        """,
        (
            int(seq),
            FARM,
            WAREHOUSE_CD_DEFAULT,
            ITEM,
            VARIETY,
            grade,
            size,
            WEIGHT,
            YEAR,
            storage_dt,
            in_qty,
            reserved,
        ),
    )
    conn.commit()
    return int(seq)


def _disc(
    *,
    reason: str,
    remark: str | None = None,
    return_confirmed: bool = False,
    grade: str = GRADE,
    size: str = SIZE,
) -> AuctionDiscrepancyIn:
    return AuctionDiscrepancyIn(
        spec_variety_cd=VARIETY,
        spec_grade_cd=grade,
        spec_size_cd=size,
        spec_weight=WEIGHT,
        reason_cd=reason,
        remark=remark,
        return_confirmed=return_confirmed,
    )


class AuctionMatchSchemaTest(unittest.TestCase):
    def test_ensure_idempotent(self) -> None:
        path, conn = _open_ops()
        try:
            first = ensure_auction_match_schema(conn)
            self.assertTrue(first["ok"])
            conn.commit()
            second = ensure_auction_match_schema(conn)
            self.assertTrue(second["ok"])
            self.assertTrue(auction_match_schema_ready(conn))
            names = {
                str(r[1])
                for r in conn.execute("PRAGMA table_info(t_auction_ship_master)")
            }
            self.assertIn("sales_no", names)
            self.assertIn("match_trade_dt", names)
            idx = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
                (INDEX_AUCTION_MATCH_SOURCE_KEY_ACTIVE,),
            ).fetchone()
            self.assertIsNotNone(idx)
            sql = _index_sql(conn, INDEX_AUCTION_MATCH_SOURCE_KEY_ACTIVE).lower()
            self.assertIn("source_key", sql)
            self.assertNotIn("farm_cd", sql)
            self.assertIsNone(
                conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
                    (INDEX_AUCTION_MATCH_SOURCE_ACTIVE_LEGACY,),
                ).fetchone()
            )
        finally:
            conn.close()
            path.unlink(missing_ok=True)

    def test_replaces_farm_scoped_unique(self) -> None:
        path, conn = _open_ops()
        try:
            ensure_auction_match_schema(conn)
            conn.execute(f"DROP INDEX IF EXISTS {INDEX_AUCTION_MATCH_SOURCE_KEY_ACTIVE}")
            conn.execute(
                f"""
                CREATE UNIQUE INDEX {INDEX_AUCTION_MATCH_SOURCE_ACTIVE_LEGACY}
                ON {TABLE_AUCTION_MATCH_DETAIL} (farm_cd, source_key)
                WHERE is_valid = 1
                """
            )
            conn.commit()
            stats = ensure_auction_match_schema(conn)
            self.assertTrue(stats["ok"])
            conn.commit()
            self.assertEqual(_index_sql(conn, INDEX_AUCTION_MATCH_SOURCE_ACTIVE_LEGACY), "")
            new_sql = _index_sql(conn, INDEX_AUCTION_MATCH_SOURCE_KEY_ACTIVE).lower()
            self.assertIn("source_key", new_sql)
            self.assertNotIn("farm_cd", new_sql)
        finally:
            conn.close()
            path.unlink(missing_ok=True)

    def test_duplicate_active_source_key_blocks_migration(self) -> None:
        path, conn = _open_ops()
        try:
            ensure_auction_match_schema(conn)
            conn.execute(f"DROP INDEX IF EXISTS {INDEX_AUCTION_MATCH_SOURCE_KEY_ACTIVE}")
            conn.execute(
                f"""
                CREATE UNIQUE INDEX {INDEX_AUCTION_MATCH_SOURCE_ACTIVE_LEGACY}
                ON {TABLE_AUCTION_MATCH_DETAIL} (farm_cd, source_key)
                WHERE is_valid = 1
                """
            )
            _insert_match_row(conn, farm=FARM, shipment_id="S1", source_key="DUPKEY")
            _insert_match_row(conn, farm=FARM2, shipment_id="S2", source_key="DUPKEY")
            conn.commit()
            self.assertEqual(active_source_key_duplicates(conn), [("DUPKEY", 2)])
            stats = ensure_auction_match_schema(conn)
            self.assertFalse(stats["ok"])
            self.assertEqual(stats["reason"], "active duplicate source_key")
            self.assertIn("farm_cd", _index_sql(conn, INDEX_AUCTION_MATCH_SOURCE_ACTIVE_LEGACY).lower())
            self.assertEqual(_index_sql(conn, INDEX_AUCTION_MATCH_SOURCE_KEY_ACTIVE), "")
        finally:
            conn.close()
            path.unlink(missing_ok=True)

    def test_direct_insert_other_farm_duplicate_rejected(self) -> None:
        path, conn = _open_finalize()
        try:
            _insert_match_row(conn, farm=FARM, shipment_id="S1", source_key="GLOBKEY")
            conn.commit()
            with self.assertRaises(sqlite3.IntegrityError):
                _insert_match_row(conn, farm=FARM2, shipment_id="S2", source_key="GLOBKEY")
        finally:
            conn.close()
            path.unlink(missing_ok=True)


class ReverseFifoAllocTest(unittest.TestCase):
    def test_later_stock_first(self) -> None:
        details = [
            {"stock_seq": 202, "farm_shipped_qty": 3},
            {"stock_seq": 201, "farm_shipped_qty": 5},
        ]
        out = _allocate_reverse_fifo(details, 2)
        self.assertEqual([(a["stock_seq"], a["return_qty"]) for a in out], [(202, 2)])

    def test_span_two_stocks(self) -> None:
        details = [
            {"stock_seq": 202, "farm_shipped_qty": 3},
            {"stock_seq": 201, "farm_shipped_qty": 5},
        ]
        out = _allocate_reverse_fifo(details, 5)
        self.assertEqual(
            [(a["stock_seq"], a["return_qty"]) for a in out],
            [(202, 3), (201, 2)],
        )

    def test_excess_reject(self) -> None:
        with self.assertRaises(AuctionFinalizeError) as ctx:
            _allocate_reverse_fifo([{"stock_seq": 1, "farm_shipped_qty": 2}], 3)
        self.assertEqual(ctx.exception.code, CODE_AUCTION_MATCH_RETURN)


class AuctionFinalizeServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.path, self.conn = _open_finalize()
        self.settlement_rows: list[dict] = []
        self.realtime_rows: list[dict] = []

    def tearDown(self) -> None:
        self.conn.close()
        self.path.unlink(missing_ok=True)

    def _svc(self) -> AuctionFinalizeService:
        return AuctionFinalizeService(
            self.conn,
            settlement_fetch=lambda *_: list(self.settlement_rows),
            realtime_fetch=lambda *_: list(self.realtime_rows),
        )

    def _lookup(self, sid: str, farm: str = FARM) -> dict:
        return AuctionCandidateService(
            self.conn,
            settlement_fetch=lambda *_: list(self.settlement_rows),
            realtime_fetch=lambda *_: list(self.realtime_rows),
        ).list_candidates(farm, sid, TRADE_DT)

    def _ship(self, qty: float = 2, *, reserved: float = 0) -> str:
        _insert_stock(
            self.conn,
            storage_dt="2026-08-28",
            in_qty=20,
            reserved=reserved,
            stock_seq=202,
        )
        return str(AuctionShipService(self.conn).create_shipment(_payload(qty))["shipment_id"])

    def _run(
        self,
        sid: str,
        selected: list[AuctionSelectedIn],
        discrepancies: list[AuctionDiscrepancyIn] | None = None,
    ) -> dict:
        return self._svc().finalize(
            AuctionFinalizeIn(
                farm_cd=FARM,
                shipment_id=sid,
                trade_dt=TRADE_DT,
                selected=selected,
                discrepancies=discrepancies or (),
                user_id="TEST",
            )
        )

    def _stock_row(self, seq: int) -> sqlite3.Row:
        return self.conn.execute(
            "SELECT in_qty, out_qty, reserved_qty FROM t_stock_master WHERE stock_seq=?",
            (seq,),
        ).fetchone()

    def _available(self, seq: int) -> float:
        row = self._stock_row(seq)
        return float(row["in_qty"]) - float(row["out_qty"]) - float(row["reserved_qty"])

    def _ship_other_farm(self, qty: float = 2) -> str:
        _ensure_farm(self.conn, farm=FARM2)
        for row in self.conn.execute(
            "SELECT code_cd, code_nm, parent_cd FROM m_common_code WHERE farm_cd=?",
            (FARM,),
        ):
            self.conn.execute(
                """
                INSERT INTO m_common_code (farm_cd, code_cd, code_nm, parent_cd)
                VALUES (?, ?, ?, ?)
                """,
                (FARM2, row[0], row[1], row[2]),
            )
        self.conn.execute(
            """
            INSERT INTO t_stock_master (
                stock_seq, farm_cd, wh_cd, item_cd, variety_cd, grade_cd, size_cd,
                weight, harvest_year, storage_dt, in_qty, out_qty, reserved_qty, reg_id
            ) VALUES (302, ?, ?, ?, ?, ?, ?, ?, ?, '2026-08-28', 20, 0, 0, 'TEST')
            """,
            (FARM2, WAREHOUSE_CD_DEFAULT, ITEM, VARIETY, GRADE, SIZE, WEIGHT, YEAR),
        )
        self.conn.commit()
        payload = AuctionShipCreateIn(
            farm_cd=FARM2,
            ship_dt="2026-08-30",
            market_cd=MARKET_CD,
            market_name="서울가락",
            corporation_name=CORP,
            lines=[_spec_line(qty)],
            user_id="TEST",
        )
        return str(AuctionShipService(self.conn).create_shipment(payload)["shipment_id"])

    def _run_farm(
        self,
        farm: str,
        sid: str,
        selected: list[AuctionSelectedIn],
        discrepancies: list[AuctionDiscrepancyIn] | None = None,
    ) -> dict:
        return self._svc().finalize(
            AuctionFinalizeIn(
                farm_cd=farm,
                shipment_id=sid,
                trade_dt=TRADE_DT,
                selected=selected,
                discrepancies=discrepancies or (),
                user_id="TEST",
            )
        )

    def test_settlement_relookup_and_ignore_client_amount(self) -> None:
        sid = self._ship(2)
        self.settlement_rows = [_row(qty=2, price=90000, amount=180000)]
        item = self._lookup(sid)["items"][0]
        self.assertEqual(item["source_type"], SOURCE_SETTLEMENT)
        out = self._run(
            sid,
            [
                AuctionSelectedIn(
                    item["source_key"],
                    client_qty=99,
                    client_unit_price=1,
                    client_amount=1,
                )
            ],
        )
        match = self.conn.execute(
            f"SELECT qty, unit_price, amount, source_grade_cd, source_grade_name, spec_grade_cd FROM {TABLE_AUCTION_MATCH_DETAIL}"
        ).fetchone()
        self.assertEqual(int(match["qty"]), 2)
        self.assertEqual(float(match["unit_price"]), 90000)
        self.assertEqual(float(match["amount"]), 180000)
        self.assertEqual(match["source_grade_cd"], "G1")
        self.assertEqual(match["source_grade_name"], "특")
        self.assertEqual(match["spec_grade_cd"], GRADE)
        self.assertNotEqual(match["source_grade_cd"], match["spec_grade_cd"])
        self.assertEqual(out["status"], AUCTION_SHIP_STATUS_COMPLETED)

    def test_realtime_relookup_requires_user_grade(self) -> None:
        sid = self._ship(2)
        self.realtime_rows = [_row(qty=2, price=87000)]
        item = self._lookup(sid)["items"][0]
        self.assertEqual(item["source_type"], SOURCE_REALTIME)
        with self.assertRaises(AuctionFinalizeError) as ctx:
            self._run(sid, [AuctionSelectedIn(item["source_key"])])
        self.assertEqual(ctx.exception.code, CODE_AUCTION_MATCH_GRADE)
        out = self._run(sid, [AuctionSelectedIn(item["source_key"], user_grade_cd=GRADE)])
        match = self.conn.execute(
            f"SELECT source_grade_cd, source_grade_name, spec_grade_cd FROM {TABLE_AUCTION_MATCH_DETAIL}"
        ).fetchone()
        self.assertIsNone(match["source_grade_cd"])
        self.assertEqual(match["source_grade_name"], "특")
        self.assertEqual(match["spec_grade_cd"], GRADE)
        self.assertEqual(out["match_count"], 1)

    def test_realtime_grade_not_in_shipment(self) -> None:
        sid = self._ship(2)
        self.realtime_rows = [_row(qty=2, price=87000)]
        key = self._lookup(sid)["items"][0]["source_key"]
        with self.assertRaises(AuctionFinalizeError) as ctx:
            self._run(sid, [AuctionSelectedIn(key, user_grade_cd=GRADE2)])
        self.assertEqual(ctx.exception.code, CODE_AUCTION_MATCH_GRADE)

    def test_stale_source_key(self) -> None:
        sid = self._ship(2)
        self.settlement_rows = [_row(qty=2, price=90000)]
        with self.assertRaises(AuctionFinalizeError) as ctx:
            self._run(sid, [AuctionSelectedIn("dead" * 16)])
        self.assertEqual(ctx.exception.code, CODE_AUCTION_MATCH_STALE)

    def test_duplicate_source_in_payload(self) -> None:
        sid = self._ship(2)
        self.settlement_rows = [_row(qty=2, price=90000)]
        key = self._lookup(sid)["items"][0]["source_key"]
        with self.assertRaises(AuctionFinalizeError) as ctx:
            self._run(sid, [AuctionSelectedIn(key), AuctionSelectedIn(key)])
        self.assertEqual(ctx.exception.code, CODE_AUCTION_MATCH_DUPLICATE_SOURCE)

    def test_other_shipment_active_source_key(self) -> None:
        _insert_stock(self.conn, storage_dt="2026-08-28", in_qty=20, stock_seq=202)
        svc_ship = AuctionShipService(self.conn)
        sid1 = str(svc_ship.create_shipment(_payload(2))["shipment_id"])
        sid2 = str(svc_ship.create_shipment(_payload(2))["shipment_id"])
        self.settlement_rows = [_row(qty=2, price=90000)]
        key = self._lookup(sid1)["items"][0]["source_key"]
        self._run(sid1, [AuctionSelectedIn(key)])
        with self.assertRaises(AuctionFinalizeError) as ctx:
            self._run(sid2, [AuctionSelectedIn(key)])
        self.assertEqual(ctx.exception.code, CODE_AUCTION_MATCH_DUPLICATE_SOURCE)

    def test_different_farm_same_source_key_reject(self) -> None:
        sid1 = self._ship(2)
        self.settlement_rows = [_row(qty=2, price=90000)]
        key = self._lookup(sid1)["items"][0]["source_key"]
        self._run(sid1, [AuctionSelectedIn(key)])
        sid2 = self._ship_other_farm(2)
        key2 = self._lookup(sid2, farm=FARM2)["items"][0]["source_key"]
        self.assertEqual(key2, key)
        before = self.conn.execute(
            "SELECT in_qty, out_qty, reserved_qty FROM t_stock_master WHERE stock_seq=302"
        ).fetchone()
        sales_before = int(self.conn.execute("SELECT COUNT(*) FROM t_sales_master").fetchone()[0])
        match_before = int(
            self.conn.execute(f"SELECT COUNT(*) FROM {TABLE_AUCTION_MATCH_DETAIL}").fetchone()[0]
        )
        with self.assertRaises(AuctionFinalizeError) as ctx:
            self._run_farm(FARM2, sid2, [AuctionSelectedIn(key2)])
        self.assertEqual(ctx.exception.code, CODE_AUCTION_MATCH_DUPLICATE_SOURCE)
        ship2 = self.conn.execute(
            "SELECT status, sales_no FROM t_auction_ship_master WHERE shipment_id=?",
            (sid2,),
        ).fetchone()
        self.assertEqual(ship2["status"], AUCTION_SHIP_STATUS_IN_TRANSIT)
        self.assertIsNone(ship2["sales_no"])
        after = self.conn.execute(
            "SELECT in_qty, out_qty, reserved_qty FROM t_stock_master WHERE stock_seq=302"
        ).fetchone()
        self.assertEqual(tuple(after), tuple(before))
        self.assertEqual(
            int(self.conn.execute("SELECT COUNT(*) FROM t_sales_master").fetchone()[0]),
            sales_before,
        )
        self.assertEqual(
            int(self.conn.execute(f"SELECT COUNT(*) FROM {TABLE_AUCTION_MATCH_DETAIL}").fetchone()[0]),
            match_before,
        )

    def test_inactive_source_key_reusable(self) -> None:
        sid1 = self._ship(2)
        self.settlement_rows = [_row(qty=2, price=90000)]
        key = self._lookup(sid1)["items"][0]["source_key"]
        self._run(sid1, [AuctionSelectedIn(key)])
        self.conn.execute(
            f"UPDATE {TABLE_AUCTION_MATCH_DETAIL} SET is_valid=0 WHERE source_key=?",
            (key,),
        )
        self.conn.commit()
        sid2 = self._ship_other_farm(2)
        out = self._run_farm(FARM2, sid2, [AuctionSelectedIn(key)])
        self.assertEqual(out["status"], AUCTION_SHIP_STATUS_COMPLETED)
        active = self.conn.execute(
            f"""
            SELECT farm_cd FROM {TABLE_AUCTION_MATCH_DETAIL}
            WHERE source_key=? AND is_valid=1
            """,
            (key,),
        ).fetchall()
        self.assertEqual([str(r[0]) for r in active], [FARM2])

    def test_settlement_external_grade_maps_internal_spec(self) -> None:
        sid = self._ship(2)
        self.settlement_rows = [_row(qty=2, price=90000, grade="특", grade_cd="EXT99")]
        key = self._lookup(sid)["items"][0]["source_key"]
        self._run(sid, [AuctionSelectedIn(key)])
        row = self.conn.execute(
            f"SELECT spec_grade_cd, source_grade_cd FROM {TABLE_AUCTION_MATCH_DETAIL}"
        ).fetchone()
        self.assertEqual(row["spec_grade_cd"], GRADE)
        self.assertEqual(row["source_grade_cd"], "EXT99")

    def test_ambiguous_spec_mapping(self) -> None:
        _stock(self.conn, seq=201, storage_dt="2026-08-20", in_qty=5, size=SIZE)
        _stock(self.conn, seq=203, storage_dt="2026-08-21", in_qty=5, size=SIZE2)
        payload = AuctionShipCreateIn(
            farm_cd=FARM,
            ship_dt="2026-08-31",
            market_cd=MARKET_CD,
            market_name="서울가락",
            corporation_name=CORP,
            lines=[
                _spec_line(2),
                AuctionShipSpecLineIn(
                    wh_cd=WAREHOUSE_CD_DEFAULT,
                    item_cd=ITEM,
                    variety_cd=VARIETY,
                    grade_cd=GRADE,
                    size_cd=SIZE2,
                    weight=WEIGHT,
                    harvest_year=YEAR,
                    qty=2,
                ),
            ],
            user_id="TEST",
        )
        sid = str(AuctionShipService(self.conn).create_shipment(payload)["shipment_id"])
        self.settlement_rows = [_row(qty=2, price=90000)]
        key = self._lookup(sid)["items"][0]["source_key"]
        with self.assertRaises(AuctionFinalizeError) as ctx:
            self._run(
                sid,
                [AuctionSelectedIn(key)],
                [_disc(reason=REASON_QTY_ERROR, grade=GRADE, size=SIZE2)],
            )
        self.assertEqual(ctx.exception.code, CODE_AUCTION_MATCH_AMBIGUOUS_SPEC)

    def test_one_spec_n_match_and_three_sales_details(self) -> None:
        sid = self._ship(10)
        self.settlement_rows = [
            _row(qty=4, price=90000, auction_time="09:00:00"),
            _row(qty=3, price=87000, auction_time="09:01:00"),
            _row(qty=3, price=85000, auction_time="09:02:00"),
        ]
        items = self._lookup(sid)["items"]
        self.assertEqual(len(items), 3)
        out = self._run(sid, [AuctionSelectedIn(i["source_key"]) for i in items])
        n_match = self.conn.execute(
            f"SELECT COUNT(*) FROM {TABLE_AUCTION_MATCH_DETAIL}"
        ).fetchone()[0]
        n_det = self.conn.execute("SELECT COUNT(*) FROM t_sales_detail").fetchone()[0]
        self.assertEqual(int(n_match), 3)
        self.assertEqual(int(n_det), 3)
        master = self.conn.execute(
            "SELECT tot_sales_amt, tot_item_amt, sales_source, sales_dt, sales_status, "
            "sales_type_cd, sales_category_cd, sales_route_cd, auction_fee, tot_paid_amt "
            "FROM t_sales_master"
        ).fetchone()
        expected = 4 * 90000 + 3 * 87000 + 3 * 85000
        self.assertEqual(float(master["tot_sales_amt"]), expected)
        self.assertEqual(float(master["tot_item_amt"]), expected)
        self.assertEqual(master["sales_source"], SALES_SOURCE_AUCTION)
        self.assertEqual(master["sales_dt"], TRADE_DT)
        self.assertEqual(master["sales_status"], SALES_STATUS_CONFIRMED)
        self.assertEqual(master["sales_type_cd"], SALES_TYPE_WHOLESALE)
        self.assertEqual(master["sales_category_cd"], SALES_CATEGORY_AUCTION)
        self.assertEqual(master["sales_route_cd"], SALES_ROUTE_AUCTION)
        self.assertEqual(float(master["auction_fee"] or 0), 0)
        self.assertEqual(float(master["tot_paid_amt"] or 0), 0)
        self.assertEqual(out["tot_sales_amt"], expected)
        nulls = self.conn.execute(
            "SELECT COUNT(*) FROM t_sales_detail WHERE stock_seq IS NULL"
        ).fetchone()[0]
        self.assertEqual(int(nulls), 3)

    def test_no_extra_out_or_sale_log_and_completed(self) -> None:
        sid = self._ship(2, reserved=1)
        before = self._stock_row(202)
        self.settlement_rows = [_row(qty=2, price=90000)]
        key = self._lookup(sid)["items"][0]["source_key"]
        out = self._run(sid, [AuctionSelectedIn(key)])
        after = self._stock_row(202)
        self.assertEqual(float(after["out_qty"]), float(before["out_qty"]))
        self.assertEqual(float(after["in_qty"]), float(before["in_qty"]))
        self.assertEqual(float(after["reserved_qty"]), 1)
        sale_logs = self.conn.execute(
            "SELECT COUNT(*) FROM t_stock_log WHERE ref_type='SALE'"
        ).fetchone()[0]
        extra_out = self.conn.execute(
            "SELECT COUNT(*) FROM t_stock_log WHERE ref_type=? AND io_type=?",
            (REF_TYPE_AUCTION_SHIP, IO_TYPE_OUT),
        ).fetchone()[0]
        self.assertEqual(int(sale_logs), 0)
        self.assertEqual(int(extra_out), 1)
        ship = self.conn.execute(
            "SELECT status, sales_no, match_trade_dt, "
            "(SELECT company_confirmed_qty FROM t_auction_ship_detail WHERE shipment_id=? LIMIT 1) AS conf "
            "FROM t_auction_ship_master WHERE shipment_id=?",
            (sid, sid),
        ).fetchone()
        self.assertEqual(ship["status"], AUCTION_SHIP_STATUS_COMPLETED)
        self.assertEqual(ship["sales_no"], out["sales_no"])
        self.assertEqual(ship["match_trade_dt"], TRADE_DT)
        self.assertIsNone(ship["conf"])
        self.assertEqual(
            int(self.conn.execute(f"SELECT COUNT(*) FROM {TABLE_AUCTION_QTY_DISCREPANCY}").fetchone()[0]),
            0,
        )

    def test_diff_zero_discrepancy_reject(self) -> None:
        sid = self._ship(2)
        self.settlement_rows = [_row(qty=2, price=90000)]
        key = self._lookup(sid)["items"][0]["source_key"]
        with self.assertRaises(AuctionFinalizeError) as ctx:
            self._run(sid, [AuctionSelectedIn(key)], [_disc(reason=REASON_QTY_ERROR)])
        self.assertEqual(ctx.exception.code, CODE_AUCTION_MATCH_DISCREPANCY)

    def test_unresolved_diff_reject(self) -> None:
        sid = self._ship(2)
        self.settlement_rows = [_row(qty=3, price=90000)]
        key = self._lookup(sid)["items"][0]["source_key"]
        with self.assertRaises(AuctionFinalizeError) as ctx:
            self._run(sid, [AuctionSelectedIn(key)])
        self.assertEqual(ctx.exception.code, CODE_AUCTION_MATCH_UNRESOLVED)

    def test_qty_error_positive_and_negative(self) -> None:
        sid = self._ship(2)
        self.settlement_rows = [_row(qty=3, price=90000)]
        key = self._lookup(sid)["items"][0]["source_key"]
        self._run(sid, [AuctionSelectedIn(key)], [_disc(reason=REASON_QTY_ERROR)])
        row = self.conn.execute(
            f"SELECT matched_qty, farm_shipped_qty, diff_qty FROM {TABLE_AUCTION_QTY_DISCREPANCY}"
        ).fetchone()
        self.assertEqual(int(row["diff_qty"]), 1)
        self.assertEqual(int(row["matched_qty"]) - int(row["farm_shipped_qty"]), 1)

        path2, conn2 = _open_finalize()
        try:
            _insert_stock(conn2, storage_dt="2026-08-28", in_qty=20, stock_seq=202)
            sid2 = str(AuctionShipService(conn2).create_shipment(_payload(2))["shipment_id"])
            rows = [_row(qty=1, price=90000)]
            svc = AuctionFinalizeService(
                conn2,
                settlement_fetch=lambda *_: rows,
                realtime_fetch=lambda *_: [],
            )
            key2 = AuctionCandidateService(
                conn2, settlement_fetch=lambda *_: rows, realtime_fetch=lambda *_: []
            ).list_candidates(FARM, sid2, TRADE_DT)["items"][0]["source_key"]
            svc.finalize(
                AuctionFinalizeIn(
                    farm_cd=FARM,
                    shipment_id=sid2,
                    trade_dt=TRADE_DT,
                    selected=[AuctionSelectedIn(key2)],
                    discrepancies=[_disc(reason=REASON_QTY_ERROR)],
                    user_id="TEST",
                )
            )
            diff = conn2.execute(
                f"SELECT diff_qty FROM {TABLE_AUCTION_QTY_DISCREPANCY}"
            ).fetchone()[0]
            self.assertEqual(int(diff), -1)
        finally:
            conn2.close()
            path2.unlink(missing_ok=True)

    def test_other_requires_remark(self) -> None:
        sid = self._ship(2)
        self.settlement_rows = [_row(qty=3, price=90000)]
        key = self._lookup(sid)["items"][0]["source_key"]
        with self.assertRaises(AuctionFinalizeError) as ctx:
            self._run(sid, [AuctionSelectedIn(key)], [_disc(reason=REASON_OTHER)])
        self.assertEqual(ctx.exception.code, CODE_AUCTION_MATCH_DISCREPANCY)
        self._run(
            sid,
            [AuctionSelectedIn(key)],
            [_disc(reason=REASON_OTHER, remark="정산 오차")],
        )

    def test_damage_negative_ok_positive_reject(self) -> None:
        sid = self._ship(2)
        self.settlement_rows = [_row(qty=1, price=90000)]
        key = self._lookup(sid)["items"][0]["source_key"]
        before = self._stock_row(202)
        self._run(sid, [AuctionSelectedIn(key)], [_disc(reason=REASON_DAMAGE, remark="파손")])
        after = self._stock_row(202)
        self.assertEqual(float(after["in_qty"]), float(before["in_qty"]))
        self.assertEqual(float(after["out_qty"]), float(before["out_qty"]))

        path2, conn2 = _open_finalize()
        try:
            _insert_stock(conn2, storage_dt="2026-08-28", in_qty=20, stock_seq=202)
            sid2 = str(AuctionShipService(conn2).create_shipment(_payload(2))["shipment_id"])
            rows = [_row(qty=3, price=90000)]
            svc = AuctionFinalizeService(
                conn2, settlement_fetch=lambda *_: rows, realtime_fetch=lambda *_: []
            )
            key2 = AuctionCandidateService(
                conn2, settlement_fetch=lambda *_: rows, realtime_fetch=lambda *_: []
            ).list_candidates(FARM, sid2, TRADE_DT)["items"][0]["source_key"]
            with self.assertRaises(AuctionFinalizeError) as ctx:
                svc.finalize(
                    AuctionFinalizeIn(
                        farm_cd=FARM,
                        shipment_id=sid2,
                        trade_dt=TRADE_DT,
                        selected=[AuctionSelectedIn(key2)],
                        discrepancies=[_disc(reason=REASON_DAMAGE)],
                        user_id="TEST",
                    )
                )
            self.assertEqual(ctx.exception.code, CODE_AUCTION_MATCH_DISCREPANCY)
        finally:
            conn2.close()
            path2.unlink(missing_ok=True)

    def test_return_reverse_fifo_in_and_log(self) -> None:
        _stock(self.conn, seq=201, storage_dt="2026-08-20", in_qty=5)
        _stock(self.conn, seq=202, storage_dt="2026-08-21", in_qty=3)
        sid = str(AuctionShipService(self.conn).create_shipment(_payload(8))["shipment_id"])
        before_a = self._stock_row(201)
        before_b = self._stock_row(202)
        avail_a = self._available(201)
        avail_b = self._available(202)
        self.settlement_rows = [_row(qty=6, price=90000)]
        key = self._lookup(sid)["items"][0]["source_key"]
        self._run(
            sid,
            [AuctionSelectedIn(key)],
            [_disc(reason=REASON_RETURN, return_confirmed=True)],
        )
        after_a = self._stock_row(201)
        after_b = self._stock_row(202)
        self.assertEqual(float(after_a["out_qty"]), float(before_a["out_qty"]))
        self.assertEqual(float(after_b["out_qty"]), float(before_b["out_qty"]))
        self.assertEqual(float(after_b["in_qty"]), float(before_b["in_qty"]) + 2)
        self.assertEqual(float(after_a["in_qty"]), float(before_a["in_qty"]))
        self.assertEqual(self._available(202), avail_b + 2)
        self.assertEqual(self._available(201), avail_a)
        lines = self.conn.execute(
            f"SELECT stock_seq, qty FROM {TABLE_AUCTION_RETURN_LINE} ORDER BY return_seq"
        ).fetchall()
        self.assertEqual([(int(r["stock_seq"]), int(r["qty"])) for r in lines], [(202, 2)])
        logs = self.conn.execute(
            """
            SELECT stock_seq, qty, remark, io_type, ref_type FROM t_stock_log
            WHERE io_type=? AND remark LIKE ?
            """,
            (IO_TYPE_IN, f"{MSG_REMARK_AUCTION_RETURN}%"),
        ).fetchall()
        self.assertEqual(len(logs), 1)
        self.assertEqual(int(logs[0]["stock_seq"]), 202)
        self.assertEqual(int(logs[0]["qty"]), 2)
        self.assertEqual(logs[0]["ref_type"], REF_TYPE_AUCTION_SHIP)
        sale_logs = self.conn.execute(
            "SELECT COUNT(*) FROM t_stock_log WHERE ref_type='SALE'"
        ).fetchone()[0]
        self.assertEqual(int(sale_logs), 0)
        total = self.conn.execute(
            f"SELECT SUM(qty) FROM {TABLE_AUCTION_RETURN_LINE}"
        ).fetchone()[0]
        self.assertEqual(int(total), 2)

    def test_return_span_reverse_fifo(self) -> None:
        _stock(self.conn, seq=201, storage_dt="2026-08-20", in_qty=5)
        _stock(self.conn, seq=202, storage_dt="2026-08-21", in_qty=3)
        sid = str(AuctionShipService(self.conn).create_shipment(_payload(8))["shipment_id"])
        self.settlement_rows = [_row(qty=3, price=90000)]
        key = self._lookup(sid)["items"][0]["source_key"]
        self._run(
            sid,
            [AuctionSelectedIn(key)],
            [_disc(reason=REASON_RETURN, return_confirmed=True)],
        )
        lines = [
            (int(r["stock_seq"]), int(r["qty"]))
            for r in self.conn.execute(
                f"SELECT stock_seq, qty FROM {TABLE_AUCTION_RETURN_LINE} ORDER BY return_seq"
            )
        ]
        self.assertEqual(lines, [(202, 3), (201, 2)])
        self.assertEqual(float(self._stock_row(202)["in_qty"]), 6)
        self.assertEqual(float(self._stock_row(201)["in_qty"]), 7)

    def test_return_without_confirm_reject(self) -> None:
        sid = self._ship(2)
        self.settlement_rows = [_row(qty=1, price=90000)]
        key = self._lookup(sid)["items"][0]["source_key"]
        with self.assertRaises(AuctionFinalizeError) as ctx:
            self._run(sid, [AuctionSelectedIn(key)], [_disc(reason=REASON_RETURN)])
        self.assertEqual(ctx.exception.code, CODE_AUCTION_MATCH_RETURN)

    def test_return_positive_diff_reject(self) -> None:
        sid = self._ship(2)
        self.settlement_rows = [_row(qty=3, price=90000)]
        key = self._lookup(sid)["items"][0]["source_key"]
        with self.assertRaises(AuctionFinalizeError) as ctx:
            self._run(
                sid,
                [AuctionSelectedIn(key)],
                [_disc(reason=REASON_RETURN, return_confirmed=True)],
            )
        self.assertEqual(ctx.exception.code, CODE_AUCTION_MATCH_DISCREPANCY)

    def test_second_finalize_and_completed_cancel_reject(self) -> None:
        sid = self._ship(2)
        self.settlement_rows = [_row(qty=2, price=90000)]
        key = self._lookup(sid)["items"][0]["source_key"]
        self._run(sid, [AuctionSelectedIn(key)])
        with self.assertRaises(AuctionFinalizeError) as ctx:
            self._run(sid, [AuctionSelectedIn(key)])
        self.assertEqual(ctx.exception.code, CODE_AUCTION_MATCH_STATUS)
        n_sales = self.conn.execute("SELECT COUNT(*) FROM t_sales_master").fetchone()[0]
        self.assertEqual(int(n_sales), 1)
        with self.assertRaises(AuctionShipError) as cancel_ctx:
            AuctionShipService(self.conn).cancel_shipment(FARM, sid)
        self.assertEqual(cancel_ctx.exception.code, CODE_AUCTION_SHIP_CANCEL_STATUS)

    def test_exception_rolls_back(self) -> None:
        sid = self._ship(2)
        self.settlement_rows = [_row(qty=2, price=90000)]
        key = self._lookup(sid)["items"][0]["source_key"]
        before_out = float(self._stock_row(202)["out_qty"])
        with patch.object(AuctionFinalizeService, "_insert_sales_master", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                self._run(sid, [AuctionSelectedIn(key)])
        ship = self.conn.execute(
            "SELECT status, sales_no FROM t_auction_ship_master WHERE shipment_id=?",
            (sid,),
        ).fetchone()
        self.assertEqual(ship["status"], AUCTION_SHIP_STATUS_IN_TRANSIT)
        self.assertIsNone(ship["sales_no"])
        self.assertEqual(
            int(self.conn.execute(f"SELECT COUNT(*) FROM {TABLE_AUCTION_MATCH_DETAIL}").fetchone()[0]),
            0,
        )
        self.assertEqual(
            int(self.conn.execute("SELECT COUNT(*) FROM t_sales_master").fetchone()[0]),
            0,
        )
        self.assertEqual(float(self._stock_row(202)["out_qty"]), before_out)

    def test_unmatched_spec_needs_discrepancy(self) -> None:
        _stock(self.conn, seq=201, storage_dt="2026-08-20", in_qty=5, grade=GRADE)
        _stock(self.conn, seq=203, storage_dt="2026-08-21", in_qty=5, grade=GRADE2)
        payload = AuctionShipCreateIn(
            farm_cd=FARM,
            ship_dt="2026-08-31",
            market_cd=MARKET_CD,
            market_name="서울가락",
            corporation_name=CORP,
            lines=[
                _spec_line(2),
                AuctionShipSpecLineIn(
                    wh_cd=WAREHOUSE_CD_DEFAULT,
                    item_cd=ITEM,
                    variety_cd=VARIETY,
                    grade_cd=GRADE2,
                    size_cd=SIZE,
                    weight=WEIGHT,
                    harvest_year=YEAR,
                    qty=2,
                ),
            ],
            user_id="TEST",
        )
        sid = str(AuctionShipService(self.conn).create_shipment(payload)["shipment_id"])
        self.settlement_rows = [_row(qty=2, price=90000, grade="특")]
        key = self._lookup(sid)["items"][0]["source_key"]
        with self.assertRaises(AuctionFinalizeError) as ctx:
            self._run(sid, [AuctionSelectedIn(key)])
        self.assertEqual(ctx.exception.code, CODE_AUCTION_MATCH_UNRESOLVED)
        self._run(
            sid,
            [AuctionSelectedIn(key)],
            [_disc(reason=REASON_DAMAGE, grade=GRADE2, remark="미매칭 폐기")],
        )
        n = self.conn.execute(
            f"SELECT COUNT(*) FROM {TABLE_AUCTION_QTY_DISCREPANCY}"
        ).fetchone()[0]
        self.assertEqual(int(n), 1)

    def test_realtime_unmatched_size(self) -> None:
        sid = self._ship(2)
        self.realtime_rows = [_row(qty=2, price=87000, size="99과")]
        item = self._lookup(sid)["items"][0]
        with self.assertRaises(AuctionFinalizeError) as ctx:
            self._run(sid, [AuctionSelectedIn(item["source_key"], user_grade_cd=GRADE)])
        self.assertEqual(ctx.exception.code, CODE_AUCTION_MATCH_SPEC_UNMATCHED)


if __name__ == "__main__":
    unittest.main()
