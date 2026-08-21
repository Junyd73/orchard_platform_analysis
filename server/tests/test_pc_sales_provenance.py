# -*- coding: utf-8 -*-
"""Stage4-P1 — PC 판매 재저장 시 order_no provenance 보존."""

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

from core.order_ship_constants import SALES_STATUS_CONFIRMED  # noqa: E402
from core.order_ship_service import OrderShipService  # noqa: E402
from core.pc_sales_provenance import (  # noqa: E402
    cash_order_no_on_resave,
    fetch_master_order_no,
)

FARM = "OR001"
SALES_NO = "20260821-01"
ORDER_NO = "ORD20260821-001"
SALES_DT = "2026-08-21"
METHOD = "AS010101"


def _schema() -> str:
    return """
        CREATE TABLE t_sales_master (
            sales_no TEXT, farm_cd TEXT, sales_dt TEXT,
            tot_sales_amt REAL, tot_paid_amt REAL, tot_unpaid_amt REAL,
            order_no TEXT, sales_status TEXT, sales_source TEXT,
            rmk TEXT, reg_id TEXT,
            PRIMARY KEY (sales_no, farm_cd)
        );
        CREATE TABLE t_cash_ledger (
            paid_detail_no TEXT PRIMARY KEY,
            sales_no TEXT NOT NULL, farm_cd TEXT NOT NULL,
            pay_dt TEXT NOT NULL, pay_method_cd TEXT NOT NULL,
            pay_amt REAL DEFAULT 0, rmk TEXT, reg_id TEXT, reg_dt TEXT,
            slip_no TEXT, order_no TEXT
        );
        CREATE TABLE t_order_master (
            order_no TEXT PRIMARY KEY, farm_cd TEXT, pre_pay_amt REAL,
            pre_pay_method_cd TEXT
        );
    """


def _pc_style_resave(
    conn: sqlite3.Connection,
    *,
    farm_cd: str,
    sales_no: str,
    pay_basket: list[dict],
) -> None:
    """execute_full_save의 order_no 보존 경로와 동일 helper 사용.

    master/cash DELETE→INSERT 시 order_no만 계약 검증 (detail/배송 제외).
    """
    cur = conn.cursor()
    existing_master_order_no = fetch_master_order_no(cur, farm_cd, sales_no)
    cur.execute(
        """
        SELECT sales_dt, tot_sales_amt, tot_paid_amt, tot_unpaid_amt,
               sales_status, sales_source, rmk, reg_id
          FROM t_sales_master
         WHERE farm_cd=? AND sales_no=?
        """,
        (farm_cd, sales_no),
    )
    master = cur.fetchone()
    if master is None:
        raise AssertionError("sales master missing for resave test")

    cur.execute(
        "DELETE FROM t_cash_ledger WHERE farm_cd=? AND sales_no=?",
        (farm_cd, sales_no),
    )
    cur.execute(
        "DELETE FROM t_sales_master WHERE farm_cd=? AND sales_no=?",
        (farm_cd, sales_no),
    )
    cur.execute(
        """
        INSERT INTO t_sales_master (
            sales_no, farm_cd, sales_dt, tot_sales_amt, tot_paid_amt, tot_unpaid_amt,
            order_no, sales_status, sales_source, rmk, reg_id
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            sales_no,
            farm_cd,
            master["sales_dt"],
            master["tot_sales_amt"],
            master["tot_paid_amt"],
            master["tot_unpaid_amt"],
            existing_master_order_no,
            master["sales_status"],
            master["sales_source"],
            master["rmk"],
            master["reg_id"],
        ),
    )
    for i, item in enumerate(pay_basket):
        if str(item.get("status") or "").upper() == "DEL":
            continue
        pd_no = f"{sales_no}-P{i + 1:02d}"
        preserved = cash_order_no_on_resave(
            status=str(item.get("status") or ""),
            orig_data=item.get("orig_data"),
        )
        cur.execute(
            """
            INSERT INTO t_cash_ledger (
                paid_detail_no, sales_no, farm_cd, pay_dt, pay_method_cd,
                pay_amt, slip_no, rmk, reg_id, order_no
            ) VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            (
                pd_no,
                sales_no,
                farm_cd,
                SALES_DT,
                item["method"],
                item["amt"],
                item.get("slip_no"),
                item.get("rmk", ""),
                "T",
                preserved,
            ),
        )
    conn.commit()


class PcSalesProvenanceTests(unittest.TestCase):
    def setUp(self) -> None:
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(_schema())
        self.conn.commit()

    def tearDown(self) -> None:
        self.conn.close()
        try:
            os.unlink(self.path)
        except OSError:
            pass

    def test_helper_ins_always_null(self) -> None:
        self.assertIsNone(
            cash_order_no_on_resave(
                status="INS",
                orig_data={"order_no": ORDER_NO},
            )
        )

    def test_helper_org_mod_preserve_row(self) -> None:
        self.assertEqual(
            cash_order_no_on_resave(
                status="ORG",
                orig_data={"order_no": ORDER_NO},
            ),
            ORDER_NO,
        )
        self.assertIsNone(
            cash_order_no_on_resave(
                status="MOD",
                orig_data={"order_no": None},
            )
        )

    def test_a_master_order_no_preserved(self) -> None:
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO t_sales_master(
                sales_no, farm_cd, sales_dt, tot_sales_amt, tot_paid_amt, tot_unpaid_amt,
                order_no, sales_status, sales_source, reg_id
            ) VALUES (?,?,?,100000,100000,0,?,?,?,?)
            """,
            (SALES_NO, FARM, SALES_DT, ORDER_NO, SALES_STATUS_CONFIRMED, "ORDER", "T"),
        )
        self.conn.commit()
        _pc_style_resave(
            self.conn,
            farm_cd=FARM,
            sales_no=SALES_NO,
            pay_basket=[],
        )
        row = self.conn.execute(
            "SELECT order_no FROM t_sales_master WHERE farm_cd=? AND sales_no=?",
            (FARM, SALES_NO),
        ).fetchone()
        self.assertEqual(row["order_no"], ORDER_NO)

    def test_a_master_null_stays_null(self) -> None:
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO t_sales_master(
                sales_no, farm_cd, sales_dt, tot_sales_amt, tot_paid_amt, tot_unpaid_amt,
                order_no, sales_status, sales_source, reg_id
            ) VALUES (?,?,?,50000,0,50000,NULL,?,?,?)
            """,
            (SALES_NO, FARM, SALES_DT, SALES_STATUS_CONFIRMED, "ORDER", "T"),
        )
        self.conn.commit()
        self.assertIsNone(fetch_master_order_no(cur, FARM, SALES_NO))
        _pc_style_resave(
            self.conn,
            farm_cd=FARM,
            sales_no=SALES_NO,
            pay_basket=[],
        )
        row = self.conn.execute(
            "SELECT order_no FROM t_sales_master WHERE farm_cd=? AND sales_no=?",
            (FARM, SALES_NO),
        ).fetchone()
        self.assertIsNone(row["order_no"])

    def test_a_new_sales_no_row_is_null(self) -> None:
        cur = self.conn.cursor()
        self.assertIsNone(fetch_master_order_no(cur, FARM, "20260821-99"))

    def test_b_cash_row_level_provenance(self) -> None:
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO t_sales_master(
                sales_no, farm_cd, sales_dt, tot_sales_amt, tot_paid_amt, tot_unpaid_amt,
                order_no, sales_status, sales_source, reg_id
            ) VALUES (?,?,?,120000,120000,0,?,?,?,?)
            """,
            (SALES_NO, FARM, SALES_DT, ORDER_NO, SALES_STATUS_CONFIRMED, "ORDER", "T"),
        )
        cur.executemany(
            """
            INSERT INTO t_cash_ledger(
                paid_detail_no, sales_no, farm_cd, pay_dt, pay_method_cd,
                pay_amt, order_no, reg_id
            ) VALUES (?,?,?,?,?,?,?,?)
            """,
            [
                (f"{SALES_NO}-P01", SALES_NO, FARM, SALES_DT, METHOD, 100000, ORDER_NO, "T"),
                (f"{SALES_NO}-P02", SALES_NO, FARM, SALES_DT, METHOD, 20000, None, "T"),
            ],
        )
        self.conn.commit()

        # SELECT * 로드와 동일하게 orig_data에 order_no 포함
        loaded = [
            dict(r)
            for r in self.conn.execute(
                "SELECT * FROM t_cash_ledger WHERE farm_cd=? AND sales_no=? ORDER BY paid_detail_no",
                (FARM, SALES_NO),
            ).fetchall()
        ]
        basket = [
            {
                "status": "ORG",
                "orig_data": loaded[0],
                "method": loaded[0]["pay_method_cd"],
                "amt": loaded[0]["pay_amt"],
            },
            {
                "status": "ORG",
                "orig_data": loaded[1],
                "method": loaded[1]["pay_method_cd"],
                "amt": loaded[1]["pay_amt"],
            },
            {
                "status": "INS",
                "orig_data": {},
                "method": METHOD,
                "amt": 5000,
            },
        ]
        _pc_style_resave(
            self.conn, farm_cd=FARM, sales_no=SALES_NO, pay_basket=basket
        )
        rows = self.conn.execute(
            """
            SELECT paid_detail_no, pay_amt, order_no
              FROM t_cash_ledger
             WHERE farm_cd=? AND sales_no=?
             ORDER BY paid_detail_no
            """,
            (FARM, SALES_NO),
        ).fetchall()
        self.assertEqual(len(rows), 3)
        self.assertEqual(float(rows[0]["pay_amt"]), 100000)
        self.assertEqual(rows[0]["order_no"], ORDER_NO)
        self.assertEqual(float(rows[1]["pay_amt"]), 20000)
        self.assertIsNone(rows[1]["order_no"])
        self.assertEqual(float(rows[2]["pay_amt"]), 5000)
        self.assertIsNone(rows[2]["order_no"])

    def test_c_remaining_prepay_after_pc_resave(self) -> None:
        """150k 중 100k 적용 → PC 재저장 후에도 remaining=50k (Core 계산)."""
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO t_order_master(order_no, farm_cd, pre_pay_amt, pre_pay_method_cd)
            VALUES (?,?,150000,?)
            """,
            (ORDER_NO, FARM, METHOD),
        )
        cur.execute(
            """
            INSERT INTO t_sales_master(
                sales_no, farm_cd, sales_dt, tot_sales_amt, tot_paid_amt, tot_unpaid_amt,
                order_no, sales_status, sales_source, reg_id
            ) VALUES (?,?,?,100000,100000,0,?,?,?,?)
            """,
            (SALES_NO, FARM, SALES_DT, ORDER_NO, SALES_STATUS_CONFIRMED, "ORDER", "T"),
        )
        cur.execute(
            """
            INSERT INTO t_cash_ledger(
                paid_detail_no, sales_no, farm_cd, pay_dt, pay_method_cd,
                pay_amt, order_no, reg_id
            ) VALUES (?,?,?,?,?,?,?,?)
            """,
            (f"{SALES_NO}-P01", SALES_NO, FARM, SALES_DT, METHOD, 100000, ORDER_NO, "T"),
        )
        self.conn.commit()

        loaded = dict(
            self.conn.execute(
                "SELECT * FROM t_cash_ledger WHERE paid_detail_no=?",
                (f"{SALES_NO}-P01",),
            ).fetchone()
        )
        _pc_style_resave(
            self.conn,
            farm_cd=FARM,
            sales_no=SALES_NO,
            pay_basket=[
                {
                    "status": "ORG",
                    "orig_data": loaded,
                    "method": METHOD,
                    "amt": 100000,
                }
            ],
        )

        master = self.conn.execute(
            "SELECT order_no FROM t_sales_master WHERE sales_no=? AND farm_cd=?",
            (SALES_NO, FARM),
        ).fetchone()
        cash = self.conn.execute(
            "SELECT order_no, pay_amt FROM t_cash_ledger WHERE sales_no=? AND farm_cd=?",
            (SALES_NO, FARM),
        ).fetchone()
        self.assertEqual(master["order_no"], ORDER_NO)
        self.assertEqual(cash["order_no"], ORDER_NO)
        self.assertEqual(float(cash["pay_amt"]), 100000)

        svc = OrderShipService(self.conn)
        remaining = svc._get_remaining_order_prepay(
            self.conn.cursor(), FARM, ORDER_NO, 150000.0
        )
        self.assertEqual(remaining, 50000.0)


if __name__ == "__main__":
    unittest.main()
