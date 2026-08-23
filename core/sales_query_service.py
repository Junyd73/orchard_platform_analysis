# -*- coding: utf-8 -*-
"""판매 목록 read-only Application Service (Stage 5)."""

from __future__ import annotations

import datetime
import sqlite3
from typing import Any

from core.order_service import (
    OrderValidationError,
    _as_float,
    _row_val,
    to_compact_ymd,
    to_iso_date,
    year_start_iso,
)
from core.ops_biz_date import today_ops_iso
from core.order_ship_constants import SALES_STATUS_CONFIRMED
from core.sales_payment_constants import SALES_STATUS_DRAFT
from core.sales_query_constants import (
    MSG_PAYMENT_STATUS_INVALID,
    MSG_SALES_DATE_INVALID,
    MSG_SALES_STATUS_INVALID,
    PAYMENT_STATUS_FILTER_VALUES,
    PAYMENT_STATUS_PAID,
    PAYMENT_STATUS_PARTIAL,
    PAYMENT_STATUS_UNPAID,
    SALES_LIST_PAGE_DEFAULT,
    SALES_LIST_PAGE_SIZE_DEFAULT,
    SALES_LIST_PAGE_SIZE_MAX,
    SALES_STATUS_FILTER_VALUES,
)


class SalesQueryValidationError(Exception):
    """판매 목록 조회 업무 규칙 위반."""

    def __init__(self, message: str, *, code: str = "SALES_QUERY_VALIDATION"):
        super().__init__(message)
        self.message = message
        self.code = code


def _sales_dt_compact_sql(alias: str = "m") -> str:
    return f"REPLACE({alias}.sales_dt, '-', '')"


def compute_payment_status(
    sales_status: str | None,
    tot_sales_amt: float,
    paid_amt: float,
) -> str | None:
    """수금상태 — DRAFT는 None, CONFIRMED만 UNPAID/PARTIAL/PAID."""
    st = str(sales_status or "").strip()
    if st == SALES_STATUS_DRAFT:
        return None
    if st != SALES_STATUS_CONFIRMED:
        return None
    total = _as_float(tot_sales_amt)
    paid = _as_float(paid_amt)
    unpaid = max(0.0, total - paid)
    if paid <= 0:
        return PAYMENT_STATUS_UNPAID
    if unpaid <= 0:
        return PAYMENT_STATUS_PAID
    if 0 < paid < total:
        return PAYMENT_STATUS_PARTIAL
    return PAYMENT_STATUS_PAID


def compute_unpaid_amt(tot_sales_amt: float, paid_amt: float) -> float:
    return max(0.0, _as_float(tot_sales_amt) - _as_float(paid_amt))


def payment_status_filter_sql(
    pay_filter: str,
    *,
    paid_expr: str = "COALESCE(cash.paid_amt, 0)",
    total_expr: str = "COALESCE(m.tot_sales_amt, 0)",
) -> str:
    """compute_payment_status와 동일 의미의 SQL filter (상호배타)."""
    if pay_filter == PAYMENT_STATUS_UNPAID:
        return f"{paid_expr} <= 0"
    if pay_filter == PAYMENT_STATUS_PARTIAL:
        return f"{paid_expr} > 0 AND {paid_expr} < {total_expr}"
    if pay_filter == PAYMENT_STATUS_PAID:
        return f"{paid_expr} > 0 AND ({total_expr} - {paid_expr}) <= 0"
    raise SalesQueryValidationError(MSG_PAYMENT_STATUS_INVALID)


def _compact_ymd_or_raise(raw: str | None, *, default: str) -> str:
    src = str(raw or "").strip() or default
    try:
        compact = to_compact_ymd(src)
        datetime.date(
            int(compact[:4]),
            int(compact[4:6]),
            int(compact[6:8]),
        )
    except (OrderValidationError, ValueError, TypeError) as exc:
        raise SalesQueryValidationError(MSG_SALES_DATE_INVALID) from exc
    return compact


class SalesQueryService:
    """판매 목록 read-only 조회. cash SUM이 수금 SSOT."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def _cash_subquery_sql(self) -> str:
        return """
            SELECT farm_cd, sales_no, SUM(COALESCE(pay_amt, 0)) AS paid_amt
            FROM t_cash_ledger
            GROUP BY farm_cd, sales_no
        """

    def _list_filters(
        self,
        farm: str,
        *,
        from_date: str | None,
        to_date: str | None,
        sales_status: str | None,
        payment_status: str | None,
        keyword: str | None,
    ) -> tuple[str, list[Any]]:
        from_key = _compact_ymd_or_raise(from_date, default=year_start_iso())
        to_key = _compact_ymd_or_raise(to_date, default=today_ops_iso())
        if from_key > to_key:
            from_key, to_key = to_key, from_key
        dt_sql = _sales_dt_compact_sql("m")
        clauses = [
            "m.farm_cd = ?",
            f"{dt_sql} >= ?",
            f"{dt_sql} <= ?",
        ]
        params: list[Any] = [farm, from_key, to_key]

        st = str(sales_status or "").strip()
        if st:
            if st not in SALES_STATUS_FILTER_VALUES:
                raise SalesQueryValidationError(MSG_SALES_STATUS_INVALID)
            clauses.append("COALESCE(m.sales_status, '') = ?")
            params.append(st)

        pay_filter = str(payment_status or "").strip().upper()
        if pay_filter:
            if pay_filter not in PAYMENT_STATUS_FILTER_VALUES:
                raise SalesQueryValidationError(MSG_PAYMENT_STATUS_INVALID)
            clauses.append("COALESCE(m.sales_status, '') = ?")
            params.append(SALES_STATUS_CONFIRMED)
            paid_expr = "COALESCE(cash.paid_amt, 0)"
            total_expr = "COALESCE(m.tot_sales_amt, 0)"
            clauses.append(
                payment_status_filter_sql(
                    pay_filter,
                    paid_expr=paid_expr,
                    total_expr=total_expr,
                )
            )

        kw = str(keyword or "").strip()
        if kw:
            like = f"%{kw}%"
            clauses.append(
                "(m.sales_no LIKE ? OR COALESCE(m.order_no, '') LIKE ?"
                " OR COALESCE(c.custm_nm, '') LIKE ?)"
            )
            params.extend([like, like, like])

        return " AND ".join(clauses), params

    def list_sales(
        self,
        farm_cd: str,
        *,
        from_date: str | None = None,
        to_date: str | None = None,
        sales_status: str | None = None,
        payment_status: str | None = None,
        keyword: str | None = None,
        page: int = SALES_LIST_PAGE_DEFAULT,
        page_size: int = SALES_LIST_PAGE_SIZE_DEFAULT,
    ) -> dict[str, Any]:
        farm = str(farm_cd or "").strip()
        try:
            page_n = int(page)
        except (TypeError, ValueError):
            page_n = SALES_LIST_PAGE_DEFAULT
        try:
            size_n = int(page_size)
        except (TypeError, ValueError):
            size_n = SALES_LIST_PAGE_SIZE_DEFAULT
        page_n = max(1, page_n)
        size_n = min(max(1, size_n), SALES_LIST_PAGE_SIZE_MAX)

        where_sql, where_params = self._list_filters(
            farm,
            from_date=from_date,
            to_date=to_date,
            sales_status=sales_status,
            payment_status=payment_status,
            keyword=keyword,
        )
        cash_sql = self._cash_subquery_sql()
        count_sql = f"""
            SELECT COUNT(*) AS cnt
            FROM t_sales_master m
            LEFT JOIN m_customer c
              ON c.custm_id = m.custm_id AND c.farm_cd = m.farm_cd
            LEFT JOIN ({cash_sql}) cash
              ON cash.farm_cd = m.farm_cd AND cash.sales_no = m.sales_no
            WHERE {where_sql}
        """
        list_sql = f"""
            SELECT
                m.sales_no,
                m.sales_dt,
                m.custm_id,
                COALESCE(c.custm_nm, '') AS customer,
                m.order_no,
                COALESCE(m.sales_status, '') AS sales_status,
                COALESCE(m.sales_source, '') AS sales_source,
                COALESCE(m.tot_sales_amt, 0) AS tot_sales_amt,
                COALESCE(cash.paid_amt, 0) AS paid_amt
            FROM t_sales_master m
            LEFT JOIN m_customer c
              ON c.custm_id = m.custm_id AND c.farm_cd = m.farm_cd
            LEFT JOIN ({cash_sql}) cash
              ON cash.farm_cd = m.farm_cd AND cash.sales_no = m.sales_no
            WHERE {where_sql}
            ORDER BY {_sales_dt_compact_sql('m')} DESC, m.sales_no DESC
            LIMIT ? OFFSET ?
        """
        offset = (page_n - 1) * size_n
        cur = self.conn.cursor()
        try:
            cur.execute(count_sql, tuple(where_params))
            total = int(_row_val(cur.fetchone(), "cnt", 0) or 0)
            cur.execute(list_sql, (*where_params, size_n, offset))
            rows = cur.fetchall()
        finally:
            cur.close()

        items: list[dict[str, Any]] = []
        for row in rows:
            raw_dt = str(_row_val(row, "sales_dt", 1) or "")
            try:
                sales_dt = to_iso_date(raw_dt)
            except OrderValidationError:
                sales_dt = raw_dt
            tot = _as_float(_row_val(row, "tot_sales_amt", 7))
            paid = _as_float(_row_val(row, "paid_amt", 8))
            cust_id = str(_row_val(row, "custm_id", 2) or "")
            customer = str(_row_val(row, "customer", 3) or "").strip()
            if not customer and cust_id:
                customer = cust_id
            if not customer:
                customer = "-"
            sales_st = str(_row_val(row, "sales_status", 5) or "")
            items.append(
                {
                    "sales_no": str(_row_val(row, "sales_no", 0) or ""),
                    "sales_dt": sales_dt,
                    "custm_id": cust_id,
                    "customer": customer,
                    "order_no": str(_row_val(row, "order_no", 4) or "") or None,
                    "sales_status": sales_st,
                    "sales_source": str(_row_val(row, "sales_source", 6) or ""),
                    "tot_sales_amt": tot,
                    "paid_amt": paid,
                    "unpaid_amt": compute_unpaid_amt(tot, paid),
                    "payment_status": compute_payment_status(sales_st, tot, paid),
                    "rep_item_cd": "",
                    "rep_variety_cd": "",
                    "rep_variety_nm": "",
                    "rep_weight": 0.0,
                    "rep_grade_cd": "",
                    "rep_grade_nm": "",
                    "rep_size_cd": "",
                    "rep_size_nm": "",
                }
            )

        if items:
            cur = self.conn.cursor()
            try:
                self._enrich_rep_details(cur, farm, items)
            finally:
                cur.close()

        return {
            "items": items,
            "total": total,
            "page": page_n,
            "page_size": size_n,
        }

    def _enrich_rep_details(
        self, cur: sqlite3.Cursor, farm: str, items: list[dict[str, Any]]
    ) -> None:
        sales_nos = [
            str(it.get("sales_no") or "").strip()
            for it in items
            if str(it.get("sales_no") or "").strip()
        ]
        if not sales_nos:
            return
        placeholders = ",".join("?" * len(sales_nos))
        cur.execute(
            f"""
            SELECT
                d.sales_no,
                d.sale_detail_no,
                d.item_cd,
                d.variety_cd,
                d.grade_cd,
                d.size_cd,
                d.weight,
                COALESCE(v.code_nm, '') AS variety_nm,
                COALESCE(g.code_nm, '') AS grade_nm,
                COALESCE(sz.code_nm, '') AS size_nm
            FROM t_sales_detail d
            LEFT JOIN m_common_code v
              ON v.farm_cd = d.farm_cd AND v.code_cd = d.variety_cd
            LEFT JOIN m_common_code g
              ON g.farm_cd = d.farm_cd AND g.code_cd = d.grade_cd
            LEFT JOIN m_common_code sz
              ON sz.farm_cd = d.farm_cd AND sz.code_cd = d.size_cd
            WHERE d.farm_cd = ?
              AND d.sales_no IN ({placeholders})
            ORDER BY d.sales_no, d.sale_detail_no ASC
            """,
            (farm, *sales_nos),
        )
        rep_by_sales: dict[str, dict[str, Any]] = {}
        for row in cur.fetchall() or []:
            sno = str(_row_val(row, "sales_no", 0) or "")
            if sno and sno not in rep_by_sales:
                rep_by_sales[sno] = {
                    "rep_item_cd": str(_row_val(row, "item_cd", 2) or ""),
                    "rep_variety_cd": str(_row_val(row, "variety_cd", 3) or ""),
                    "rep_variety_nm": str(_row_val(row, "variety_nm", 7) or ""),
                    "rep_weight": _as_float(_row_val(row, "weight", 6)),
                    "rep_grade_cd": str(_row_val(row, "grade_cd", 4) or ""),
                    "rep_grade_nm": str(_row_val(row, "grade_nm", 8) or ""),
                    "rep_size_cd": str(_row_val(row, "size_cd", 5) or ""),
                    "rep_size_nm": str(_row_val(row, "size_nm", 9) or ""),
                }
        for it in items:
            patch = rep_by_sales.get(str(it.get("sales_no") or ""))
            if patch:
                it.update(patch)
