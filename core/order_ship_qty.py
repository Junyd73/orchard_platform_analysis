# -*- coding: utf-8 -*-
"""주문 line 출고누계·잔여 — OrderService / OrderShipService 공통 SSOT."""

from __future__ import annotations

import sqlite3

from core.order_ship_constants import SALES_STATUS_CONFIRMED

_QTY_EPS = 1e-9


def _as_float(val: object, default: float = 0.0) -> float:
    try:
        return float(val)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def confirmed_shipped_qty(cur: sqlite3.Cursor, farm: str, order_detail_id: str) -> float:
    """CONFIRMED t_sales_detail qty 합 — OrderShipService와 동일 기준."""
    try:
        cur.execute(
            """
            SELECT COALESCE(SUM(d.qty), 0)
            FROM t_sales_detail d
            INNER JOIN t_sales_master m
              ON m.farm_cd = d.farm_cd AND m.sales_no = d.sales_no
            WHERE d.farm_cd = ?
              AND d.order_detail_id = ?
              AND COALESCE(m.sales_status, '') = ?
            """,
            (farm, order_detail_id, SALES_STATUS_CONFIRMED),
        )
    except sqlite3.OperationalError:
        return 0.0
    row = cur.fetchone()
    if row is None:
        return 0.0
    return _as_float(row[0] if not isinstance(row, sqlite3.Row) else row[0])


def order_line_ship_remainder(order_qty: float, confirmed_shipped: float) -> tuple[float, float]:
    shipped = max(confirmed_shipped, 0.0)
    left = order_qty - shipped
    if left <= _QTY_EPS:
        left = 0.0
    return shipped, left
