# -*- coding: utf-8 -*-
"""S2A 판매분류 schema / 공통코드 / SS01→SA02 매핑."""

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

from core.sales_class_constants import (  # noqa: E402
    SALES_CATEGORY_AUCTION,
    SALES_CATEGORY_CHUSEOK,
    SALES_CATEGORY_NORMAL,
    SALES_CATEGORY_PARENT_CD,
    SALES_CATEGORY_SEOLLAL,
    SALES_ROUTE_AUCTION,
    SALES_ROUTE_DIRECT,
    SALES_ROUTE_ORDER_SHIP,
    SALES_ROUTE_PARENT_CD,
    SALES_TYPE_EXPORT,
    SALES_TYPE_PARENT_CD,
    SALES_TYPE_RETAIL,
    SALES_TYPE_WHOLESALE,
    SEASON_TYPE_CHUSEOK,
    SEASON_TYPE_NORMAL,
    SEASON_TYPE_SEOLLAL,
    map_season_type_to_sales_category,
)
from core.sales_class_schema import ensure_sales_class_schema  # noqa: E402

FARM = "OR001"


class SalesClassSchemaTest(unittest.TestCase):
    def setUp(self) -> None:
        fd, name = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.path = Path(name)
        self.conn = sqlite3.connect(str(self.path))
        self.conn.row_factory = sqlite3.Row

    def tearDown(self) -> None:
        self.conn.close()
        self.path.unlink(missing_ok=True)

    def _bootstrap(self) -> None:
        self.conn.executescript(
            f"""
            CREATE TABLE m_farm_info (farm_cd TEXT PRIMARY KEY);
            INSERT INTO m_farm_info (farm_cd) VALUES ('{FARM}');

            CREATE TABLE m_common_code (
                farm_cd TEXT NOT NULL,
                code_cd TEXT NOT NULL,
                code_nm TEXT,
                parent_cd TEXT,
                use_yn TEXT DEFAULT 'Y',
                reg_id TEXT, reg_dt TEXT, mod_id TEXT, mod_dt TEXT,
                PRIMARY KEY (farm_cd, code_cd)
            );
            INSERT INTO m_common_code (farm_cd, code_cd, code_nm, parent_cd, use_yn)
            VALUES
              ('{FARM}', 'SS01', '시즌가격', NULL, 'Y'),
              ('{FARM}', 'SS010100', '설날', 'SS01', 'Y'),
              ('{FARM}', 'SS010200', '추석', 'SS01', 'Y'),
              ('{FARM}', 'SS010300', '일반', 'SS01', 'Y');

            CREATE TABLE t_order_master (
                order_no TEXT, farm_cd TEXT, order_dt TEXT,
                season_type_cd TEXT DEFAULT 'SS010300',
                sales_no TEXT,
                PRIMARY KEY (order_no, farm_cd)
            );
            INSERT INTO t_order_master (order_no, farm_cd, order_dt, season_type_cd, sales_no)
            VALUES ('ORD1', '{FARM}', '2026-08-01', 'SS010100', '');

            CREATE TABLE t_sales_master (
                sales_no TEXT, farm_cd TEXT, sales_dt TEXT,
                sales_tp TEXT, sales_source TEXT, sales_status TEXT,
                order_no TEXT, tot_sales_amt REAL,
                PRIMARY KEY (sales_no, farm_cd)
            );
            INSERT INTO t_sales_master (
                sales_no, farm_cd, sales_dt, sales_tp, sales_source, sales_status, order_no, tot_sales_amt
            ) VALUES
              ('S-ORD', '{FARM}', '2026-08-01', 'NORMAL', 'ORDER', 'CONFIRMED', 'ORD1', 1000),
              ('S-AUC', '{FARM}', '2026-08-01', NULL, 'AUCTION_RT', 'DRAFT', NULL, 2000),
              ('S-RV', '{FARM}', '2026-01-28', 'RV010102', 'ORDER', 'CONFIRMED', NULL, 3000);
            """
        )
        self.conn.commit()

    def _cols(self, table: str) -> set[str]:
        return {
            str(r[1]).strip().lower()
            for r in self.conn.execute(f"PRAGMA table_info({table})")
        }

    def test_t1_t2_columns_idempotent(self) -> None:
        self._bootstrap()
        first = ensure_sales_class_schema(self.conn)
        self.assertTrue(first["ok"], first)
        self.assertIn("t_order_master.sales_type_cd", first["columns"])
        self.assertIn("t_sales_master.sales_type_cd", first["columns"])
        self.assertIn("t_sales_master.sales_category_cd", first["columns"])
        self.assertIn("t_sales_master.sales_route_cd", first["columns"])
        self.assertEqual(len(first["columns"]), 4)

        order_cols = self._cols("t_order_master")
        sales_cols = self._cols("t_sales_master")
        self.assertIn("sales_type_cd", order_cols)
        self.assertTrue(
            {"sales_type_cd", "sales_category_cd", "sales_route_cd"} <= sales_cols
        )

        second = ensure_sales_class_schema(self.conn)
        self.assertTrue(second["ok"], second)
        self.assertEqual(second["columns"], [])
        self.assertEqual(second["codes_inserted"], [])

    def test_t3_t4_t5_existing_values_preserved(self) -> None:
        self._bootstrap()
        ensure_sales_class_schema(self.conn)
        rows = list(
            self.conn.execute(
                """
                SELECT sales_no, sales_tp, sales_source, sales_status,
                       sales_type_cd, sales_category_cd, sales_route_cd
                  FROM t_sales_master
                 ORDER BY sales_no
                """
            )
        )
        by_no = {r["sales_no"]: r for r in rows}
        self.assertEqual(by_no["S-ORD"]["sales_tp"], "NORMAL")
        self.assertEqual(by_no["S-ORD"]["sales_source"], "ORDER")
        self.assertIsNone(by_no["S-ORD"]["sales_type_cd"])
        self.assertIsNone(by_no["S-ORD"]["sales_category_cd"])
        self.assertIsNone(by_no["S-ORD"]["sales_route_cd"])

        self.assertIsNone(by_no["S-AUC"]["sales_tp"])
        self.assertEqual(by_no["S-AUC"]["sales_source"], "AUCTION_RT")

        self.assertEqual(by_no["S-RV"]["sales_tp"], "RV010102")
        self.assertEqual(by_no["S-RV"]["sales_source"], "ORDER")

        order = self.conn.execute(
            "SELECT season_type_cd, sales_type_cd FROM t_order_master WHERE order_no='ORD1'"
        ).fetchone()
        self.assertEqual(order["season_type_cd"], "SS010100")
        self.assertIsNone(order["sales_type_cd"])

    def test_t6_sa_codes_contract(self) -> None:
        self._bootstrap()
        stats = ensure_sales_class_schema(self.conn)
        self.assertTrue(stats["ok"], stats)
        parents = {
            r["code_cd"]: r
            for r in self.conn.execute(
                """
                SELECT code_cd, code_nm, parent_cd, use_yn
                  FROM m_common_code
                 WHERE farm_cd=? AND code_cd IN (?, ?, ?)
                """,
                (FARM, SALES_TYPE_PARENT_CD, SALES_CATEGORY_PARENT_CD, SALES_ROUTE_PARENT_CD),
            )
        }
        self.assertEqual(parents[SALES_TYPE_PARENT_CD]["code_nm"], "판매유형")
        self.assertIsNone(parents[SALES_TYPE_PARENT_CD]["parent_cd"])
        self.assertEqual(parents[SALES_CATEGORY_PARENT_CD]["code_nm"], "판매구분")
        self.assertEqual(parents[SALES_ROUTE_PARENT_CD]["code_nm"], "판매경로")

        children = {
            r["code_cd"]: r
            for r in self.conn.execute(
                """
                SELECT code_cd, code_nm, parent_cd
                  FROM m_common_code
                 WHERE farm_cd=? AND parent_cd IN (?, ?, ?)
                 ORDER BY code_cd
                """,
                (FARM, SALES_TYPE_PARENT_CD, SALES_CATEGORY_PARENT_CD, SALES_ROUTE_PARENT_CD),
            )
        }
        expected = {
            SALES_TYPE_RETAIL: (SALES_TYPE_PARENT_CD, "소매"),
            SALES_TYPE_WHOLESALE: (SALES_TYPE_PARENT_CD, "도매"),
            SALES_TYPE_EXPORT: (SALES_TYPE_PARENT_CD, "수출"),
            SALES_CATEGORY_NORMAL: (SALES_CATEGORY_PARENT_CD, "일반판매"),
            SALES_CATEGORY_CHUSEOK: (SALES_CATEGORY_PARENT_CD, "추석판매"),
            SALES_CATEGORY_SEOLLAL: (SALES_CATEGORY_PARENT_CD, "설판매"),
            SALES_CATEGORY_AUCTION: (SALES_CATEGORY_PARENT_CD, "경매판매"),
            SALES_ROUTE_DIRECT: (SALES_ROUTE_PARENT_CD, "직접판매"),
            SALES_ROUTE_ORDER_SHIP: (SALES_ROUTE_PARENT_CD, "주문출고"),
            SALES_ROUTE_AUCTION: (SALES_ROUTE_PARENT_CD, "경매연동"),
        }
        self.assertEqual(set(children), set(expected))
        for cd, (parent, nm) in expected.items():
            self.assertEqual(children[cd]["parent_cd"], parent)
            self.assertEqual(children[cd]["code_nm"], nm)

    def test_t7_ss01_untouched(self) -> None:
        self._bootstrap()
        ensure_sales_class_schema(self.conn)
        ss = list(
            self.conn.execute(
                """
                SELECT code_cd, code_nm, parent_cd
                  FROM m_common_code
                 WHERE farm_cd=? AND (code_cd='SS01' OR parent_cd='SS01')
                 ORDER BY code_cd
                """,
                (FARM,),
            )
        )
        self.assertEqual(
            [(r["code_cd"], r["code_nm"], r["parent_cd"]) for r in ss],
            [
                ("SS01", "시즌가격", None),
                ("SS010100", "설날", "SS01"),
                ("SS010200", "추석", "SS01"),
                ("SS010300", "일반", "SS01"),
            ],
        )

    def _sa_code_count(self) -> int:
        row = self.conn.execute(
            """
            SELECT COUNT(*) AS cnt
              FROM m_common_code
             WHERE farm_cd=? AND (code_cd LIKE 'SA01%' OR code_cd LIKE 'SA02%'
                    OR code_cd LIKE 'SA03%' OR code_cd IN ('SA01','SA02','SA03'))
            """,
            (FARM,),
        ).fetchone()
        return int(row["cnt"] if isinstance(row, sqlite3.Row) else row[0])

    def _assert_no_class_columns(self) -> None:
        order_cols = self._cols("t_order_master")
        sales_cols = self._cols("t_sales_master")
        self.assertNotIn("sales_type_cd", order_cols)
        self.assertNotIn("sales_type_cd", sales_cols)
        self.assertNotIn("sales_category_cd", sales_cols)
        self.assertNotIn("sales_route_cd", sales_cols)

    def _assert_bootstrap_data_unchanged(self) -> None:
        rows = list(
            self.conn.execute(
                """
                SELECT sales_no, sales_tp, sales_source, sales_status, tot_sales_amt
                  FROM t_sales_master
                 ORDER BY sales_no
                """
            )
        )
        by_no = {r["sales_no"]: r for r in rows}
        self.assertEqual(by_no["S-ORD"]["sales_tp"], "NORMAL")
        self.assertEqual(by_no["S-ORD"]["sales_source"], "ORDER")
        self.assertEqual(by_no["S-ORD"]["sales_status"], "CONFIRMED")
        self.assertEqual(by_no["S-ORD"]["tot_sales_amt"], 1000)
        self.assertIsNone(by_no["S-AUC"]["sales_tp"])
        self.assertEqual(by_no["S-AUC"]["sales_source"], "AUCTION_RT")
        self.assertEqual(by_no["S-RV"]["sales_tp"], "RV010102")
        order = self.conn.execute(
            "SELECT season_type_cd FROM t_order_master WHERE order_no='ORD1'"
        ).fetchone()
        self.assertEqual(order["season_type_cd"], "SS010100")

    def test_code_conflict_fails_atomic(self) -> None:
        """SA01 이름 충돌: ok=False, 컬럼/SA코드 미반영, 기존 데이터·외부 TX 유지."""
        self._bootstrap()
        self.conn.execute(
            """
            INSERT INTO m_common_code (farm_cd, code_cd, code_nm, parent_cd, use_yn)
            VALUES (?, 'SA01', '다른이름', NULL, 'Y')
            """,
            (FARM,),
        )
        self.conn.commit()
        sa_before = self._sa_code_count()
        self.assertEqual(sa_before, 1)

        # 외부 트랜잭션에 미커밋 마커 — helper 가 임의 commit/rollback 하면 안 됨.
        self.conn.execute("BEGIN")
        self.conn.execute(
            "INSERT INTO m_farm_info (farm_cd) VALUES ('TX_MARKER')"
        )
        self.assertTrue(self.conn.in_transaction)

        stats = ensure_sales_class_schema(self.conn)
        self.assertFalse(stats["ok"])
        self.assertIn("conflict", stats["reason"].lower())
        self.assertEqual(stats["columns"], [])
        self.assertEqual(stats["codes_inserted"], [])

        self._assert_no_class_columns()
        self.assertEqual(self._sa_code_count(), 1)
        self._assert_bootstrap_data_unchanged()

        # 외부 TX 미커밋: 마커가 아직 보이며, rollback 하면 사라짐.
        self.assertTrue(self.conn.in_transaction)
        marker = self.conn.execute(
            "SELECT 1 FROM m_farm_info WHERE farm_cd='TX_MARKER'"
        ).fetchone()
        self.assertIsNotNone(marker)
        self.conn.rollback()
        gone = self.conn.execute(
            "SELECT 1 FROM m_farm_info WHERE farm_cd='TX_MARKER'"
        ).fetchone()
        self.assertIsNone(gone)

    def test_use_yn_n_is_conflict_atomic(self) -> None:
        """동일 code_nm/parent 이라도 use_yn='N' 이면 자동 활성화 금지·원자 실패."""
        self._bootstrap()
        self.conn.execute(
            """
            INSERT INTO m_common_code (farm_cd, code_cd, code_nm, parent_cd, use_yn)
            VALUES (?, 'SA01', '판매유형', NULL, 'N')
            """,
            (FARM,),
        )
        self.conn.commit()

        stats = ensure_sales_class_schema(self.conn)
        self.assertFalse(stats["ok"])
        self.assertIn("conflict", stats["reason"].lower())
        self.assertEqual(stats["columns"], [])
        self.assertEqual(stats["codes_inserted"], [])
        self._assert_no_class_columns()
        row = self.conn.execute(
            """
            SELECT code_nm, parent_cd, use_yn
              FROM m_common_code
             WHERE farm_cd=? AND code_cd='SA01'
            """,
            (FARM,),
        ).fetchone()
        self.assertEqual(row["code_nm"], "판매유형")
        self.assertIsNone(row["parent_cd"])
        self.assertEqual(row["use_yn"], "N")
        self.assertEqual(self._sa_code_count(), 1)
        self._assert_bootstrap_data_unchanged()

    def test_external_tx_success_rolled_back_by_caller(self) -> None:
        """외부 TX 내 임의 INSERT + helper 성공 후 caller rollback 시 함께 원복."""
        self._bootstrap()
        self.conn.execute("BEGIN")
        self.conn.execute(
            "INSERT INTO m_farm_info (farm_cd) VALUES ('TX_MARKER')"
        )
        self.assertTrue(self.conn.in_transaction)

        stats = ensure_sales_class_schema(self.conn)
        self.assertTrue(stats["ok"], stats)
        self.assertEqual(len(stats["columns"]), 4)
        self.assertGreater(len(stats["codes_inserted"]), 0)
        self.assertIn("sales_type_cd", self._cols("t_order_master"))
        self.assertTrue(
            {"sales_type_cd", "sales_category_cd", "sales_route_cd"}
            <= self._cols("t_sales_master")
        )
        self.assertGreater(self._sa_code_count(), 0)
        marker = self.conn.execute(
            "SELECT 1 FROM m_farm_info WHERE farm_cd='TX_MARKER'"
        ).fetchone()
        self.assertIsNotNone(marker)
        self.assertTrue(self.conn.in_transaction)

        self.conn.rollback()
        self.assertIsNone(
            self.conn.execute(
                "SELECT 1 FROM m_farm_info WHERE farm_cd='TX_MARKER'"
            ).fetchone()
        )
        self._assert_no_class_columns()
        self.assertEqual(self._sa_code_count(), 0)
        self._assert_bootstrap_data_unchanged()

    def test_path_unavailable(self) -> None:
        stats = ensure_sales_class_schema(Path("C:/no/such/orchard_s2a.db"))
        self.assertFalse(stats["ok"])
        self.assertEqual(stats["reason"], "db_unavailable")


class SeasonCategoryMappingTest(unittest.TestCase):
    def test_t8_known_mapping(self) -> None:
        self.assertEqual(
            map_season_type_to_sales_category(SEASON_TYPE_NORMAL),
            SALES_CATEGORY_NORMAL,
        )
        self.assertEqual(
            map_season_type_to_sales_category(SEASON_TYPE_CHUSEOK),
            SALES_CATEGORY_CHUSEOK,
        )
        self.assertEqual(
            map_season_type_to_sales_category(SEASON_TYPE_SEOLLAL),
            SALES_CATEGORY_SEOLLAL,
        )

    def test_t9_blank_unknown_not_guessed(self) -> None:
        self.assertIsNone(map_season_type_to_sales_category(None))
        self.assertIsNone(map_season_type_to_sales_category(""))
        self.assertIsNone(map_season_type_to_sales_category("   "))
        self.assertIsNone(map_season_type_to_sales_category("SS019999"))
        self.assertIsNone(map_season_type_to_sales_category("SA020100"))


if __name__ == "__main__":
    unittest.main()
