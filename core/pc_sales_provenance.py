# -*- coding: utf-8 -*-
"""PC 판매 재저장 시 order_no provenance 보존 (Stage4-P1).

Service 계층이 아님. SalesPage.execute_full_save와 테스트가 동일 규칙을 쓴다.
"""

from __future__ import annotations

import sqlite3
from typing import Any, Mapping


def _norm_order_no(raw: Any) -> str | None:
    text = str(raw or "").strip()
    return text or None


def fetch_master_order_no(
    cur: sqlite3.Cursor, farm_cd: str, sales_no: str
) -> str | None:
    """DELETE 전 DB의 t_sales_master.order_no만 읽는다. UI/역산 금지."""
    cur.execute(
        """
        SELECT order_no
          FROM t_sales_master
         WHERE farm_cd = ? AND sales_no = ?
        """,
        (farm_cd, sales_no),
    )
    row = cur.fetchone()
    if row is None:
        return None
    if isinstance(row, sqlite3.Row):
        return _norm_order_no(row["order_no"])
    return _norm_order_no(row[0])


def cash_order_no_on_resave(
    *, status: str, orig_data: Mapping[str, Any] | None
) -> str | None:
    """cash 행별 order_no.

    ORG/MOD → orig_data.order_no 보존
    INS     → 항상 NULL (PC 신규 일반수금)
    """
    st = str(status or "").strip().upper()
    if st == "INS":
        return None
    if st in {"ORG", "MOD"}:
        if not orig_data:
            return None
        return _norm_order_no(orig_data.get("order_no"))
    return None
