# -*- coding: utf-8 -*-
"""주문 Application Service — PyQt / FastAPI 공통 (Stage 2).

주문 3테이블만 저장한다. 판매·재고 HOLD·회계 전표를 만들지 않는다.
재고 0이어도 저장 가능하다 (DEC-002).
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
from typing import Any, Sequence

from core.ops_biz_date import now_ops_str, today_ops, today_ops_iso
from core.order_ship_qty import (
    confirmed_shipped_by_order_dlvry,
    confirmed_shipped_qty,
    order_line_ship_remainder,
)
from core.order_ship_constants import SALES_STATUS_CONFIRMED
from core.order_constants import (
    DELIVERY_TP_ADDR_OPTIONAL,
    DELIVERY_TP_PARENT_CD,
    DELIVERY_TP_PARCEL_CD,
    DELIVERY_TP_VISIT_CD,
    ITEM_MID_SUFFIX,
    MSG_ORDER_CANCEL_FORBIDDEN,
    MSG_ORDER_CONFIRM_FORBIDDEN,
    MSG_ORDER_ALLOC_QTY_BELOW,
    MSG_ORDER_ALLOC_SPEC_LOCKED,
    MSG_ORDER_CONFIRMED_LIMITED,
    MSG_ORDER_LOCKED_CANCEL,
    MSG_ORDER_LOCKED_DELIVERED,
    MSG_ORDER_PREPAY_AMT_NEGATIVE,
    MSG_ORDER_PREPAY_METHOD_FORBIDDEN_WHEN_ZERO,
    MSG_ORDER_PREPAY_METHOD_INVALID,
    MSG_ORDER_PREPAY_METHOD_REQUIRED,
    MSG_ORDER_PREPAY_METHOD_SCHEMA,
    MSG_ORDER_QTY_LOCKED,
    MSG_ORDER_SHIP_ONLY,
    MSG_PARCEL_DEST_INCOMPLETE,
    MSG_PARCEL_DEST_QTY,
    MSG_PARCEL_QTY_OVER,
    ORDER_LIST_PAGE_DEFAULT,
    ORDER_LIST_PAGE_SIZE_DEFAULT,
    ORDER_LIST_PAGE_SIZE_MAX,
    ORDER_NO_PREFIX,
    ORDER_NO_SEQ_LEN,
    ORDER_STATUS_CANCEL_CD,
    ORDER_STATUS_CANCELABLE,
    ORDER_STATUS_CONFIRMED_CD,
    ORDER_STATUS_DELIVERED_CD,
    ORDER_STATUS_LOCKED,
    ORDER_STATUS_PARENT_CD,
    ORDER_STATUS_PREP_CD,
    ORDER_STATUS_QTY_LOCKED,
    ORDER_STATUS_RESERVED_CD,
    PREPAY_METHOD_ACCT_LEVEL,
    PREPAY_METHOD_PARENT_CD,
    PREPAY_METHOD_USE_YN_Y,
    SALES_NO_EMPTY,
    STOCK_STATUS_OPEN,
    VARIETY_CD_LEN,
    WAREHOUSE_CD_DEFAULT,
)

_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_YMD_RE = re.compile(r"^\d{8}$")
_QTY_EPS = 1e-9


class OrderSaveError(Exception):
    """주문 저장/조회 업무 규칙 위반."""

    def __init__(self, message: str, *, code: str = "ORDER_SAVE_ERROR"):
        super().__init__(message)
        self.message = message
        self.code = code


class OrderValidationError(OrderSaveError):
    def __init__(self, message: str, *, code: str = "ORDER_VALIDATION"):
        super().__init__(message, code=code)


class OrderNotFoundError(OrderSaveError):
    def __init__(self, message: str = "주문을 찾을 수 없습니다."):
        super().__init__(message, code="ORDER_NOT_FOUND")


class OrderHasSalesError(OrderSaveError):
    def __init__(self, message: str = "판매가 연결된 주문은 Stage 2에서 수정할 수 없습니다."):
        super().__init__(message, code="ORDER_HAS_SALES")


@dataclass
class OrderDeliveryInput:
    delivery_tp_cd: str
    qty: float
    planned_dt: str | None = None
    snd_name: str = ""
    snd_tel: str = ""
    snd_addr: str = ""
    rcv_name: str = ""
    rcv_tel: str = ""
    rcv_addr: str = ""
    dlvry_msg: str = ""


@dataclass
class OrderLineInput:
    variety_cd: str
    weight: float
    grade_cd: str
    size_cd: str
    qty: float
    unit_price: float
    harvest_year: int | None = None
    warehouse_cd: str = WAREHOUSE_CD_DEFAULT
    item_cd: str | None = None
    dlvry_tp: str | None = None
    deliveries: list[OrderDeliveryInput] = field(default_factory=list)


@dataclass
class OrderSaveInput:
    custm_id: str
    order_dt: str | None = None
    season_type_cd: str = ""
    pre_pay_amt: float = 0.0
    pre_pay_method_cd: str | None = None
    tot_ship_fee: float = 0.0
    rmk: str = ""
    lines: list[OrderLineInput] = field(default_factory=list)


def item_cd_from_variety(variety_cd: str) -> str:
    """소분류(8) → 중분류(앞 6자리 + 00)."""
    raw = str(variety_cd or "").strip()
    if len(raw) >= 6:
        return f"{raw[:6]}{ITEM_MID_SUFFIX}"
    return raw


def to_iso_date(raw: str | None) -> str:
    """조회 호환: YYYY-MM-DD 우선, YYYYMMDD는 ISO로 변환."""
    s = str(raw or "").strip()
    if not s:
        return today_ops_iso()
    if _ISO_DATE_RE.match(s):
        return s
    compact = s.replace("-", "")
    if _YMD_RE.match(compact):
        return f"{compact[:4]}-{compact[4:6]}-{compact[6:8]}"
    raise OrderValidationError("주문일은 YYYY-MM-DD 형식이어야 합니다.")


def to_compact_ymd(raw: str | None) -> str:
    """기간 비교용 YYYYMMDD. ISO·레거시 모두 동일 키로 맞춤."""
    return to_iso_date(raw).replace("-", "")


def year_start_iso() -> str:
    return f"{today_ops().year:04d}-01-01"


def _order_dt_compact_sql(alias: str = "m") -> str:
    return f"REPLACE({alias}.order_dt, '-', '')"


def _table_exists(cur: sqlite3.Cursor, table: str) -> bool:
    row = cur.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (table,),
    ).fetchone()
    return row is not None


def _column_exists(cur: sqlite3.Cursor, table: str, column: str) -> bool:
    return column in {str(r[1]) for r in cur.execute(f"PRAGMA table_info({table})")}


def generate_order_no(cursor: sqlite3.Cursor, farm_cd: str, order_dt: str) -> str:
    """ORD + YYYYMMDD + - + SEQ(3). farm_cd 스코프. UUID 금지."""
    iso = to_iso_date(order_dt)
    date_part = iso.replace("-", "")
    prefix = f"{ORDER_NO_PREFIX}{date_part}"
    like = f"{prefix}-%"
    cursor.execute(
        """
        SELECT MAX(order_no) AS max_no
        FROM t_order_master
        WHERE farm_cd = ? AND order_no LIKE ?
        """,
        (str(farm_cd or "").strip(), like),
    )
    row = cursor.fetchone()
    max_no = None
    if row is not None:
        max_no = row["max_no"] if isinstance(row, sqlite3.Row) else row[0]
    new_seq = 1
    if max_no:
        try:
            new_seq = int(str(max_no).rsplit("-", 1)[-1]) + 1
        except (TypeError, ValueError):
            new_seq = 1
    return f"{prefix}-{new_seq:0{ORDER_NO_SEQ_LEN}d}"


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _row_val(row: Any, key: str, idx: int = 0) -> Any:
    if row is None:
        return None
    if isinstance(row, sqlite3.Row):
        try:
            return row[key]
        except (IndexError, KeyError):
            return row[idx]
    if isinstance(row, dict):
        return row.get(key)
    return row[idx]


def _line_fingerprint(
    variety_cd: Any,
    weight: Any,
    grade_cd: Any,
    size_cd: Any,
    qty: Any,
    unit_price: Any,
) -> tuple[str, float, str, str, float, float]:
    return (
        str(variety_cd or "").strip(),
        round(_as_float(weight), 6),
        str(grade_cd or "").strip(),
        str(size_cd or "").strip(),
        round(_as_float(qty), 6),
        round(_as_float(unit_price), 6),
    )


def _locked_edit_message(status_cd: str) -> str:
    if status_cd == ORDER_STATUS_DELIVERED_CD:
        return MSG_ORDER_LOCKED_DELIVERED
    if status_cd == ORDER_STATUS_CANCEL_CD:
        return MSG_ORDER_LOCKED_CANCEL
    return MSG_ORDER_LOCKED_DELIVERED


class OrderService:
    """주문 master/detail/delivery 조회·저장. 판매/재고/전표 금지."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def list_customers(
        self,
        farm_cd: str,
        q: str | None = None,
        *,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        farm = str(farm_cd or "").strip()
        keyword = str(q or "").strip()
        sql = """
            SELECT custm_id, custm_nm, mobile
            FROM m_customer
            WHERE farm_cd = ?
              AND COALESCE(use_yn, 'Y') = 'Y'
        """
        params: list[Any] = [farm]
        if keyword:
            like = f"%{keyword}%"
            sql += " AND (custm_nm LIKE ? OR IFNULL(mobile, '') LIKE ? OR custm_id LIKE ?)"
            params.extend([like, like, like])
        sql += " ORDER BY custm_nm COLLATE NOCASE, custm_id LIMIT ?"
        params.append(max(1, min(int(limit), 500)))
        cur = self.conn.cursor()
        try:
            cur.execute(sql, tuple(params))
            rows = cur.fetchall()
        finally:
            cur.close()
        out: list[dict[str, Any]] = []
        for row in rows:
            out.append(
                {
                    "custm_id": str(_row_val(row, "custm_id", 0) or ""),
                    "custm_nm": str(_row_val(row, "custm_nm", 1) or ""),
                    "mobile": str(_row_val(row, "mobile", 2) or ""),
                }
            )
        return out

    def _list_orders_filters(
        self,
        farm: str,
        *,
        from_date: str | None,
        to_date: str | None,
        status_cd: str | None,
        keyword: str | None,
    ) -> tuple[str, list[Any]]:
        from_raw = str(from_date or "").strip()
        to_raw = str(to_date or "").strip()
        from_key = to_compact_ymd(from_raw or year_start_iso())
        to_key = to_compact_ymd(to_raw or today_ops_iso())
        if from_key > to_key:
            from_key, to_key = to_key, from_key
        dt_sql = _order_dt_compact_sql("m")
        clauses = [
            "m.farm_cd = ?",
            f"{dt_sql} >= ?",
            f"{dt_sql} <= ?",
        ]
        params: list[Any] = [farm, from_key, to_key]
        st = str(status_cd or "").strip()
        if st:
            clauses.append("m.status_cd = ?")
            params.append(st)
        kw = str(keyword or "").strip()
        if kw:
            like = f"%{kw}%"
            clauses.append(
                "(m.order_no LIKE ? OR COALESCE(c.custm_nm, '') LIKE ?)"
            )
            params.extend([like, like])
        return " AND ".join(clauses), params

    def list_orders(
        self,
        farm_cd: str,
        *,
        from_date: str | None = None,
        to_date: str | None = None,
        status_cd: str | None = None,
        keyword: str | None = None,
        page: int = ORDER_LIST_PAGE_DEFAULT,
        page_size: int = ORDER_LIST_PAGE_SIZE_DEFAULT,
    ) -> dict[str, Any]:
        farm = str(farm_cd or "").strip()
        try:
            page_n = int(page)
        except (TypeError, ValueError):
            page_n = ORDER_LIST_PAGE_DEFAULT
        try:
            size_n = int(page_size)
        except (TypeError, ValueError):
            size_n = ORDER_LIST_PAGE_SIZE_DEFAULT
        page_n = max(1, page_n)
        size_n = min(max(1, size_n), ORDER_LIST_PAGE_SIZE_MAX)
        where_sql, where_params = self._list_orders_filters(
            farm,
            from_date=from_date,
            to_date=to_date,
            status_cd=status_cd,
            keyword=keyword,
        )
        count_sql = f"""
            SELECT COUNT(*) AS cnt
            FROM t_order_master m
            LEFT JOIN m_customer c
              ON c.custm_id = m.custm_id AND c.farm_cd = m.farm_cd
            WHERE {where_sql}
        """
        list_sql = f"""
            SELECT
                m.order_no,
                m.order_dt,
                m.custm_id,
                COALESCE(c.custm_nm, '') AS customer,
                m.status_cd,
                COALESCE(st.code_nm, m.status_cd) AS status_nm,
                COALESCE((
                    SELECT SUM(d.qty) FROM t_order_detail d
                    WHERE d.order_no = m.order_no AND d.farm_cd = m.farm_cd
                ), 0) AS total_qty,
                COALESCE(m.tot_order_amt, 0) AS total_amt,
                COALESCE(m.pre_pay_amt, 0) AS pre_pay_amt
            FROM t_order_master m
            LEFT JOIN m_customer c
              ON c.custm_id = m.custm_id AND c.farm_cd = m.farm_cd
            LEFT JOIN m_common_code st
              ON st.code_cd = m.status_cd
             AND st.farm_cd = m.farm_cd
             AND st.parent_cd = ?
            WHERE {where_sql}
            ORDER BY {_order_dt_compact_sql("m")} DESC, m.order_no DESC
            LIMIT ? OFFSET ?
        """
        offset = (page_n - 1) * size_n
        cur = self.conn.cursor()
        try:
            cur.execute(count_sql, tuple(where_params))
            count_row = cur.fetchone()
            total = int(_row_val(count_row, "cnt", 0) or 0)
            cur.execute(
                list_sql,
                (ORDER_STATUS_PARENT_CD, *where_params, size_n, offset),
            )
            rows = cur.fetchall()
        finally:
            cur.close()
        items: list[dict[str, Any]] = []
        for row in rows:
            raw_dt = str(_row_val(row, "order_dt", 1) or "")
            try:
                order_dt = to_iso_date(raw_dt)
            except OrderValidationError:
                order_dt = raw_dt
            items.append(
                {
                    "order_no": str(_row_val(row, "order_no", 0) or ""),
                    "order_dt": order_dt,
                    "custm_id": str(_row_val(row, "custm_id", 2) or ""),
                    "customer": str(_row_val(row, "customer", 3) or ""),
                    "status_cd": str(_row_val(row, "status_cd", 4) or ""),
                    "status_nm": str(_row_val(row, "status_nm", 5) or ""),
                    "total_qty": _as_float(_row_val(row, "total_qty", 6)),
                    "total_amt": _as_float(_row_val(row, "total_amt", 7)),
                    "pre_pay_amt": _as_float(_row_val(row, "pre_pay_amt", 8)),
                }
            )
        if items:
            cur = self.conn.cursor()
            try:
                self._enrich_order_list_items(cur, farm, items)
            finally:
                cur.close()
        return {
            "items": items,
            "total": total,
            "page": page_n,
            "page_size": size_n,
        }

    def _enrich_order_list_items(
        self, cur: sqlite3.Cursor, farm: str, items: list[dict[str, Any]]
    ) -> None:
        """페이지 주문건에 대해 대표상품·배송·출고잔여를 bulk 집계한다 (N+1 금지)."""
        order_nos = [str(it.get("order_no") or "").strip() for it in items]
        order_nos = [o for o in order_nos if o]
        empty = {
            "line_count": 0,
            "rep_item_cd": "",
            "rep_variety_cd": "",
            "rep_variety_nm": "",
            "rep_grade_cd": "",
            "rep_grade_nm": "",
            "rep_size_cd": "",
            "rep_size_nm": "",
            "rep_weight": 0.0,
            "delivery_tp_cd": "",
            "delivery_tp_nm": "",
            "delivery_tp_count": 0,
            "confirmed_shipped_qty": 0.0,
            "remaining_order_qty": 0.0,
        }
        if not order_nos:
            for it in items:
                total_qty = _as_float(it.get("total_qty"))
                it.update(empty)
                it["remaining_order_qty"] = max(0.0, total_qty)
            return

        placeholders = ",".join("?" * len(order_nos))
        cur.execute(
            f"""
            SELECT
                d.order_no, d.order_detail_id, d.item_cd, d.variety_cd, d.grade_cd, d.size_cd,
                d.weight, d.dlvry_tp,
                COALESCE(v.code_nm, '') AS variety_nm,
                COALESCE(g.code_nm, '') AS grade_nm,
                COALESCE(sz.code_nm, '') AS size_nm,
                COALESCE(tp.code_nm, d.dlvry_tp, '') AS delivery_tp_nm
            FROM t_order_detail d
            LEFT JOIN m_common_code v
              ON v.farm_cd = d.farm_cd AND v.code_cd = d.variety_cd
            LEFT JOIN m_common_code g
              ON g.farm_cd = d.farm_cd AND g.code_cd = d.grade_cd
            LEFT JOIN m_common_code sz
              ON sz.farm_cd = d.farm_cd AND sz.code_cd = d.size_cd
            LEFT JOIN m_common_code tp
              ON tp.farm_cd = d.farm_cd
             AND tp.code_cd = d.dlvry_tp
             AND tp.parent_cd = ?
            WHERE d.farm_cd = ?
              AND d.order_no IN ({placeholders})
            ORDER BY d.order_no, d.order_detail_id
            """,
            (DELIVERY_TP_PARENT_CD, farm, *order_nos),
        )
        details_by_order: dict[str, list[dict[str, Any]]] = {}
        for row in cur.fetchall() or []:
            ono = str(_row_val(row, "order_no", 0) or "")
            details_by_order.setdefault(ono, []).append(
                {
                    "order_detail_id": str(_row_val(row, "order_detail_id", 1) or ""),
                    "item_cd": str(_row_val(row, "item_cd", 2) or ""),
                    "variety_cd": str(_row_val(row, "variety_cd", 3) or ""),
                    "grade_cd": str(_row_val(row, "grade_cd", 4) or ""),
                    "size_cd": str(_row_val(row, "size_cd", 5) or ""),
                    "weight": _as_float(_row_val(row, "weight", 6)),
                    "dlvry_tp": str(_row_val(row, "dlvry_tp", 7) or ""),
                    "variety_nm": str(_row_val(row, "variety_nm", 8) or ""),
                    "grade_nm": str(_row_val(row, "grade_nm", 9) or ""),
                    "size_nm": str(_row_val(row, "size_nm", 10) or ""),
                    "delivery_tp_nm": str(_row_val(row, "delivery_tp_nm", 11) or ""),
                }
            )

        shipped_by_order: dict[str, float] = {}
        try:
            cur.execute(
                f"""
                SELECT sm.order_no, COALESCE(SUM(sd.qty), 0) AS shipped
                FROM t_sales_detail sd
                INNER JOIN t_sales_master sm
                  ON sm.farm_cd = sd.farm_cd AND sm.sales_no = sd.sales_no
                WHERE sd.farm_cd = ?
                  AND sm.order_no IN ({placeholders})
                  AND COALESCE(sm.sales_status, '') = ?
                GROUP BY sm.order_no
                """,
                (farm, *order_nos, SALES_STATUS_CONFIRMED),
            )
            for row in cur.fetchall() or []:
                ono = str(_row_val(row, "order_no", 0) or "")
                if ono:
                    shipped_by_order[ono] = _as_float(_row_val(row, "shipped", 1))
        except sqlite3.OperationalError:
            shipped_by_order = {}

        for it in items:
            ono = str(it.get("order_no") or "")
            total_qty = _as_float(it.get("total_qty"))
            lines = details_by_order.get(ono) or []
            shipped = float(shipped_by_order.get(ono, 0.0))
            _, remaining = order_line_ship_remainder(total_qty, shipped)
            patch = dict(empty)
            patch["confirmed_shipped_qty"] = shipped
            patch["remaining_order_qty"] = remaining
            patch["line_count"] = len(lines)
            if lines:
                rep = lines[0]
                patch["rep_item_cd"] = rep["item_cd"]
                patch["rep_variety_cd"] = rep["variety_cd"]
                patch["rep_variety_nm"] = rep["variety_nm"]
                patch["rep_grade_cd"] = rep["grade_cd"]
                patch["rep_grade_nm"] = rep["grade_nm"]
                patch["rep_size_cd"] = rep["size_cd"]
                patch["rep_size_nm"] = rep["size_nm"]
                patch["rep_weight"] = rep["weight"]
                tps: dict[str, str] = {}
                for ln in lines:
                    cd = str(ln.get("dlvry_tp") or "").strip()
                    if not cd:
                        continue
                    if cd not in tps:
                        tps[cd] = str(ln.get("delivery_tp_nm") or cd)
                patch["delivery_tp_count"] = len(tps)
                if len(tps) == 1:
                    only_cd = next(iter(tps))
                    patch["delivery_tp_cd"] = only_cd
                    patch["delivery_tp_nm"] = tps[only_cd]
            it.update(patch)

    def get_order(self, farm_cd: str, order_no: str) -> dict[str, Any]:
        farm = str(farm_cd or "").strip()
        no = str(order_no or "").strip()
        if not no:
            raise OrderNotFoundError()
        cur = self.conn.cursor()
        try:
            cur.execute(
                """
                SELECT
                    m.order_no, m.order_dt, m.custm_id,
                    COALESCE(c.custm_nm, '') AS customer,
                    COALESCE(c.mobile, '') AS mobile,
                    m.status_cd,
                    COALESCE(st.code_nm, m.status_cd) AS status_nm,
                    m.stock_status, m.season_type_cd,
                    COALESCE(m.tot_order_amt, 0) AS tot_order_amt,
                    COALESCE(m.tot_ship_fee, 0) AS tot_ship_fee,
                    COALESCE(m.pre_pay_amt, 0) AS pre_pay_amt,
                    COALESCE(m.tot_pay_amt, 0) AS tot_pay_amt,
                    COALESCE(m.rmk, '') AS rmk,
                    COALESCE(m.sales_no, '') AS sales_no
                FROM t_order_master m
                LEFT JOIN m_customer c
                  ON c.custm_id = m.custm_id AND c.farm_cd = m.farm_cd
                LEFT JOIN m_common_code st
                  ON st.code_cd = m.status_cd
                 AND st.farm_cd = m.farm_cd
                 AND st.parent_cd = ?
                WHERE m.farm_cd = ? AND m.order_no = ?
                """,
                (ORDER_STATUS_PARENT_CD, farm, no),
            )
            master = cur.fetchone()
            if master is None:
                raise OrderNotFoundError()
            pre_pay_method_cd: str | None = None
            if _column_exists(cur, "t_order_master", "pre_pay_method_cd"):
                cur.execute(
                    """
                    SELECT pre_pay_method_cd
                    FROM t_order_master
                    WHERE farm_cd = ? AND order_no = ?
                    """,
                    (farm, no),
                )
                method_row = cur.fetchone()
                raw_method = _row_val(method_row, "pre_pay_method_cd", 0) if method_row else None
                method_s = str(raw_method or "").strip()
                pre_pay_method_cd = method_s or None
            alloc_expr = (
                "COALESCE(d.allocated_qty, 0) AS allocated_qty"
                if _column_exists(cur, "t_order_detail", "allocated_qty")
                else "0 AS allocated_qty"
            )
            cur.execute(
                f"""
                SELECT
                    d.order_detail_id, d.item_cd, d.variety_cd, d.grade_cd, d.size_cd,
                    d.weight, d.qty, d.unit_price, d.item_amt, d.harvest_year, d.wh_cd, d.dlvry_tp,
                    COALESCE(v.code_nm, d.variety_cd) AS variety_nm,
                    COALESCE(g.code_nm, d.grade_cd) AS grade_nm,
                    COALESCE(s.code_nm, d.size_cd) AS size_nm,
                    COALESCE(t.code_nm, d.dlvry_tp) AS dlvry_tp_nm,
                    {alloc_expr}
                FROM t_order_detail d
                LEFT JOIN m_common_code v
                  ON v.farm_cd = d.farm_cd AND v.code_cd = d.variety_cd
                LEFT JOIN m_common_code g
                  ON g.farm_cd = d.farm_cd AND g.code_cd = d.grade_cd
                LEFT JOIN m_common_code s
                  ON s.farm_cd = d.farm_cd AND s.code_cd = d.size_cd
                LEFT JOIN m_common_code t
                  ON t.farm_cd = d.farm_cd AND t.code_cd = d.dlvry_tp
                WHERE d.farm_cd = ? AND d.order_no = ?
                ORDER BY d.order_detail_id
                """,
                (farm, no),
            )
            detail_rows = cur.fetchall()
            shipped_by_detail: dict[str, float] = {}
            for row in detail_rows:
                det_id = str(_row_val(row, "order_detail_id", 0) or "")
                shipped_by_detail[det_id] = confirmed_shipped_qty(cur, farm, det_id)
            shipped_by_order_dlvry = confirmed_shipped_by_order_dlvry(cur, farm, no)
            cur.execute(
                """
                SELECT
                    d.order_dlvry_id, d.order_detail_id, d.delivery_tp_cd, d.dlvry_qty,
                    d.planned_dt, d.snd_name, d.snd_tel, d.snd_addr,
                    d.rcv_name, d.rcv_tel, d.rcv_addr, d.dlvry_msg,
                    COALESCE(t.code_nm, d.delivery_tp_cd) AS delivery_tp_nm
                FROM t_order_delivery d
                LEFT JOIN m_common_code t
                  ON t.farm_cd = d.farm_cd AND t.code_cd = d.delivery_tp_cd
                WHERE d.farm_cd = ? AND d.order_no = ?
                ORDER BY d.order_dlvry_id
                """,
                (farm, no),
            )
            delivery_rows = cur.fetchall()
        finally:
            cur.close()

        deliveries_by_line: dict[str, list[dict[str, Any]]] = {}
        linked_shipped_by_line: dict[str, float] = {}
        for row in delivery_rows:
            det_id = str(_row_val(row, "order_detail_id", 1) or "")
            oid = str(_row_val(row, "order_dlvry_id", 0) or "")
            planned = _as_float(_row_val(row, "dlvry_qty", 3))
            dest_shipped = float(shipped_by_order_dlvry.get(oid, 0.0))
            _, dest_remain = order_line_ship_remainder(planned, dest_shipped)
            linked_shipped_by_line[det_id] = linked_shipped_by_line.get(det_id, 0.0) + dest_shipped
            deliveries_by_line.setdefault(det_id, []).append(
                {
                    "order_dlvry_id": oid,
                    "order_detail_id": det_id,
                    "delivery_tp_cd": str(_row_val(row, "delivery_tp_cd", 2) or ""),
                    "qty": planned,
                    "planned_dt": str(_row_val(row, "planned_dt", 4) or ""),
                    "snd_name": str(_row_val(row, "snd_name", 5) or ""),
                    "snd_tel": str(_row_val(row, "snd_tel", 6) or ""),
                    "snd_addr": str(_row_val(row, "snd_addr", 7) or ""),
                    "rcv_name": str(_row_val(row, "rcv_name", 8) or ""),
                    "rcv_tel": str(_row_val(row, "rcv_tel", 9) or ""),
                    "rcv_addr": str(_row_val(row, "rcv_addr", 10) or ""),
                    "dlvry_msg": str(_row_val(row, "dlvry_msg", 11) or ""),
                    "delivery_tp_nm": str(_row_val(row, "delivery_tp_nm", 12) or ""),
                    "confirmed_shipped_qty": dest_shipped,
                    "remaining_qty": dest_remain,
                }
            )

        lines: list[dict[str, Any]] = []
        total_qty = 0.0
        for row in detail_rows:
            det_id = str(_row_val(row, "order_detail_id", 0) or "")
            qty = _as_float(_row_val(row, "qty", 6))
            allocated = _as_float(_row_val(row, "allocated_qty", 16))
            confirmed, remaining = order_line_ship_remainder(qty, shipped_by_detail.get(det_id, 0.0))
            linked = float(linked_shipped_by_line.get(det_id, 0.0))
            untracked = max(0.0, confirmed - linked)
            if untracked <= _QTY_EPS:
                untracked = 0.0
            total_qty += qty
            lines.append(
                {
                    "order_detail_id": det_id,
                    "item_cd": str(_row_val(row, "item_cd", 1) or ""),
                    "variety_cd": str(_row_val(row, "variety_cd", 2) or ""),
                    "grade_cd": str(_row_val(row, "grade_cd", 3) or ""),
                    "size_cd": str(_row_val(row, "size_cd", 4) or ""),
                    "weight": _as_float(_row_val(row, "weight", 5)),
                    "qty": qty,
                    "unit_price": _as_float(_row_val(row, "unit_price", 7)),
                    "item_amt": _as_float(_row_val(row, "item_amt", 8)),
                    "harvest_year": int(
                        _as_float(_row_val(row, "harvest_year", 9), today_ops().year)
                    ),
                    "wh_cd": str(_row_val(row, "wh_cd", 10) or WAREHOUSE_CD_DEFAULT),
                    "dlvry_tp": str(_row_val(row, "dlvry_tp", 11) or ""),
                    "variety_nm": str(_row_val(row, "variety_nm", 12) or ""),
                    "grade_nm": str(_row_val(row, "grade_nm", 13) or ""),
                    "size_nm": str(_row_val(row, "size_nm", 14) or ""),
                    "dlvry_tp_nm": str(_row_val(row, "dlvry_tp_nm", 15) or ""),
                    "allocated_qty": allocated,
                    "unallocated_qty": qty - allocated,
                    "reserved_unshipped_qty": allocated,
                    "confirmed_shipped_qty": confirmed,
                    "remaining_order_qty": remaining,
                    "untracked_delivery_shipped_qty": untracked,
                    "deliveries": deliveries_by_line.get(det_id, []),
                }
            )

        raw_dt = str(_row_val(master, "order_dt", 1) or "")
        try:
            order_dt = to_iso_date(raw_dt)
        except OrderValidationError:
            order_dt = raw_dt
        return {
            "order_no": str(_row_val(master, "order_no", 0) or ""),
            "order_dt": order_dt,
            "custm_id": str(_row_val(master, "custm_id", 2) or ""),
            "customer": str(_row_val(master, "customer", 3) or ""),
            "mobile": str(_row_val(master, "mobile", 4) or ""),
            "status_cd": str(_row_val(master, "status_cd", 5) or ""),
            "status_nm": str(_row_val(master, "status_nm", 6) or ""),
            "stock_status": str(_row_val(master, "stock_status", 7) or STOCK_STATUS_OPEN),
            "season_type_cd": str(_row_val(master, "season_type_cd", 8) or ""),
            "tot_order_amt": _as_float(_row_val(master, "tot_order_amt", 9)),
            "total_amt": _as_float(_row_val(master, "tot_order_amt", 9)),
            "tot_ship_fee": _as_float(_row_val(master, "tot_ship_fee", 10)),
            "pre_pay_amt": _as_float(_row_val(master, "pre_pay_amt", 11)),
            "pre_pay_method_cd": pre_pay_method_cd,
            "tot_pay_amt": _as_float(_row_val(master, "tot_pay_amt", 12)),
            "rmk": str(_row_val(master, "rmk", 13) or ""),
            "sales_no": str(_row_val(master, "sales_no", 14) or ""),
            "total_qty": total_qty,
            "lines": lines,
        }

    def create_order(
        self,
        farm_cd: str,
        payload: OrderSaveInput,
        *,
        user_id: str,
    ) -> str:
        farm = str(farm_cd or "").strip()
        if not farm:
            raise OrderValidationError("농장 코드가 없습니다.")
        self._validate_payload(farm, payload)
        order_dt = to_iso_date(payload.order_dt)
        now_dt = now_ops_str()
        reg_id = str(user_id or "").strip() or "SYSTEM"
        tot_amt = self._total_item_amt(payload.lines)
        cur = self.conn.cursor()
        try:
            cur.execute("BEGIN IMMEDIATE")
            order_no = generate_order_no(cur, farm, order_dt)
            self._insert_master(
                cur,
                farm=farm,
                order_no=order_no,
                order_dt=order_dt,
                payload=payload,
                tot_amt=tot_amt,
                user_id=reg_id,
                now_dt=now_dt,
            )
            self._insert_lines_and_deliveries(
                cur,
                farm=farm,
                order_no=order_no,
                payload=payload,
                order_dt=order_dt,
                user_id=reg_id,
                now_dt=now_dt,
            )
            self.conn.commit()
            return order_no
        except Exception:
            self.conn.rollback()
            raise
        finally:
            cur.close()

    def replace_order(
        self,
        farm_cd: str,
        order_no: str,
        payload: OrderSaveInput,
        *,
        user_id: str,
    ) -> str:
        """출고 전·판매 미연결 주문의 상세/배송만 교체. HOLD/판매 금지."""
        farm = str(farm_cd or "").strip()
        no = str(order_no or "").strip()
        if not farm or not no:
            raise OrderValidationError("주문번호가 없습니다.")
        self._validate_payload(farm, payload)
        now_dt = now_ops_str()
        reg_id = str(user_id or "").strip() or "SYSTEM"
        tot_amt = self._total_item_amt(payload.lines)
        cur = self.conn.cursor()
        try:
            cur.execute("BEGIN IMMEDIATE")
            cur.execute(
                """
                SELECT stock_status, sales_no, order_dt, status_cd, custm_id, pre_pay_amt, rmk
                FROM t_order_master
                WHERE farm_cd = ? AND order_no = ?
                """,
                (farm, no),
            )
            row = cur.fetchone()
            if row is None:
                raise OrderNotFoundError()
            stock_status = str(_row_val(row, "stock_status", 0) or "")
            sales_no = str(_row_val(row, "sales_no", 1) or "").strip()
            existing_dt = str(_row_val(row, "order_dt", 2) or "")
            status_cd = str(_row_val(row, "status_cd", 3) or "")
            existing_cust = str(_row_val(row, "custm_id", 4) or "").strip()
            existing_pre_pay = _as_float(_row_val(row, "pre_pay_amt", 5))
            existing_rmk = str(_row_val(row, "rmk", 6) or "")
            if stock_status == "Y":
                raise OrderValidationError("이미 출고 처리된 주문은 수정할 수 없습니다.")
            if sales_no:
                raise OrderHasSalesError()
            if status_cd in ORDER_STATUS_LOCKED:
                raise OrderValidationError(_locked_edit_message(status_cd))
            alloc_snapshot = self._load_alloc_snapshot(cur, farm, no)
            self._validate_alloc_edit(payload, alloc_snapshot)
            if status_cd in ORDER_STATUS_QTY_LOCKED:
                cur.execute(
                    """
                    SELECT variety_cd, weight, grade_cd, size_cd, qty, unit_price
                    FROM t_order_detail
                    WHERE farm_cd = ? AND order_no = ?
                    ORDER BY order_detail_id
                    """,
                    (farm, no),
                )
                existing_keys = [
                    _line_fingerprint(
                        _row_val(r, "variety_cd", 0),
                        _row_val(r, "weight", 1),
                        _row_val(r, "grade_cd", 2),
                        _row_val(r, "size_cd", 3),
                        _row_val(r, "qty", 4),
                        _row_val(r, "unit_price", 5),
                    )
                    for r in cur.fetchall()
                ]
                payload_keys = [
                    _line_fingerprint(
                        ln.variety_cd,
                        ln.weight,
                        ln.grade_cd,
                        ln.size_cd,
                        ln.qty,
                        ln.unit_price,
                    )
                    for ln in payload.lines
                ]
                if existing_keys != payload_keys:
                    raise OrderValidationError(MSG_ORDER_QTY_LOCKED)
            if status_cd == ORDER_STATUS_CONFIRMED_CD:
                if abs(float(payload.pre_pay_amt or 0) - existing_pre_pay) > _QTY_EPS:
                    raise OrderValidationError(MSG_ORDER_CONFIRMED_LIMITED)
            if status_cd == ORDER_STATUS_PREP_CD:
                if (
                    payload.custm_id.strip() != existing_cust
                    or abs(float(payload.pre_pay_amt or 0) - existing_pre_pay) > _QTY_EPS
                    or str(payload.rmk or "") != existing_rmk
                ):
                    raise OrderValidationError(MSG_ORDER_SHIP_ONLY)
            cur.execute(
                "DELETE FROM t_order_delivery WHERE farm_cd = ? AND order_no = ?",
                (farm, no),
            )
            cur.execute(
                "DELETE FROM t_order_detail WHERE farm_cd = ? AND order_no = ?",
                (farm, no),
            )
            order_dt = to_iso_date(existing_dt) if existing_dt else to_iso_date(payload.order_dt)
            if status_cd == ORDER_STATUS_RESERVED_CD:
                order_dt = to_iso_date(payload.order_dt) if payload.order_dt else order_dt
            cur.execute(
                """
                UPDATE t_order_master SET
                    order_dt = ?, custm_id = ?, tot_order_amt = ?, tot_ship_fee = ?,
                    tot_pay_amt = ?, rmk = ?, mod_id = ?, mod_dt = ?,
                    season_type_cd = ?, pre_pay_amt = ?
                WHERE farm_cd = ? AND order_no = ?
                """,
                (
                    order_dt,
                    payload.custm_id.strip(),
                    tot_amt,
                    float(payload.tot_ship_fee or 0),
                    float(payload.pre_pay_amt or 0),
                    str(payload.rmk or ""),
                    reg_id,
                    now_dt,
                    str(payload.season_type_cd or ""),
                    float(payload.pre_pay_amt or 0),
                    farm,
                    no,
                ),
            )
            if _column_exists(cur, "t_order_master", "pre_pay_method_cd"):
                cur.execute(
                    """
                    UPDATE t_order_master
                    SET pre_pay_method_cd = ?
                    WHERE farm_cd = ? AND order_no = ?
                    """,
                    (
                        self._normalize_pre_pay_method(payload.pre_pay_method_cd),
                        farm,
                        no,
                    ),
                )
            self._insert_lines_and_deliveries(
                cur,
                farm=farm,
                order_no=no,
                payload=payload,
                order_dt=order_dt,
                user_id=reg_id,
                now_dt=now_dt,
                allocated_by_id={
                    row["order_detail_id"]: row["allocated_qty"] for row in alloc_snapshot
                },
            )
            self.conn.commit()
            return no
        except Exception:
            self.conn.rollback()
            raise
        finally:
            cur.close()

    def cancel_order(
        self,
        farm_cd: str,
        order_no: str,
        *,
        user_id: str,
    ) -> str:
        """예약접수·주문확정만 ST010500.

        미출고 allocation이 있으면 동일 TX에서 해제한다.
        allocation이 없는 주문(즉시출고형, allocated_qty=0)도 정상 취소한다.
        """
        farm = str(farm_cd or "").strip()
        no = str(order_no or "").strip()
        if not farm or not no:
            raise OrderValidationError("주문번호가 없습니다.")
        now_dt = now_ops_str()
        mod_id = str(user_id or "").strip() or "SYSTEM"
        cur = self.conn.cursor()
        try:
            cur.execute("BEGIN IMMEDIATE")
            cur.execute(
                """
                SELECT status_cd, stock_status, sales_no
                FROM t_order_master
                WHERE farm_cd = ? AND order_no = ?
                """,
                (farm, no),
            )
            row = cur.fetchone()
            if row is None:
                raise OrderNotFoundError()
            status_cd = str(_row_val(row, "status_cd", 0) or "")
            stock_status = str(_row_val(row, "stock_status", 1) or "")
            sales_no = str(_row_val(row, "sales_no", 2) or "").strip()
            if stock_status == "Y" or sales_no or status_cd not in ORDER_STATUS_CANCELABLE:
                raise OrderValidationError(MSG_ORDER_CANCEL_FORBIDDEN)
            if _table_exists(cur, "t_order_alloc"):
                from core.order_allocation_service import OrderAllocationService

                OrderAllocationService(self.conn).release_all_unshipped_in_tx(
                    cur, farm, no, user_id=mod_id, now_dt=now_dt
                )
            cur.execute(
                """
                UPDATE t_order_master
                SET status_cd = ?, mod_id = ?, mod_dt = ?
                WHERE farm_cd = ? AND order_no = ?
                """,
                (ORDER_STATUS_CANCEL_CD, mod_id, now_dt, farm, no),
            )
            self.conn.commit()
            return no
        except Exception:
            self.conn.rollback()
            raise
        finally:
            cur.close()

    def confirm_order(
        self,
        farm_cd: str,
        order_no: str,
        *,
        user_id: str,
    ) -> str:
        """예약접수(ST010100) → 주문확정(ST010200). 판매·재고·allocation 없음."""
        farm = str(farm_cd or "").strip()
        no = str(order_no or "").strip()
        if not farm or not no:
            raise OrderValidationError("주문번호가 없습니다.")
        now_dt = now_ops_str()
        mod_id = str(user_id or "").strip() or "SYSTEM"
        cur = self.conn.cursor()
        try:
            cur.execute("BEGIN IMMEDIATE")
            cur.execute(
                """
                SELECT status_cd
                FROM t_order_master
                WHERE farm_cd = ? AND order_no = ?
                """,
                (farm, no),
            )
            row = cur.fetchone()
            if row is None:
                raise OrderNotFoundError()
            status_cd = str(_row_val(row, "status_cd", 0) or "")
            if status_cd != ORDER_STATUS_RESERVED_CD:
                raise OrderValidationError(
                    MSG_ORDER_CONFIRM_FORBIDDEN,
                    code="ORDER_CONFIRM_FORBIDDEN",
                )
            cur.execute(
                """
                UPDATE t_order_master
                SET status_cd = ?, mod_id = ?, mod_dt = ?
                WHERE farm_cd = ? AND order_no = ?
                """,
                (ORDER_STATUS_CONFIRMED_CD, mod_id, now_dt, farm, no),
            )
            self.conn.commit()
            return no
        except Exception:
            self.conn.rollback()
            raise
        finally:
            cur.close()

    def _load_alloc_snapshot(
        self, cur: sqlite3.Cursor, farm: str, order_no: str
    ) -> list[dict[str, Any]]:
        if not _column_exists(cur, "t_order_detail", "allocated_qty"):
            return []
        cur.execute(
            """
            SELECT order_detail_id, variety_cd, weight, grade_cd, size_cd,
                   wh_cd, harvest_year, qty, COALESCE(allocated_qty, 0) AS allocated_qty
            FROM t_order_detail
            WHERE farm_cd = ? AND order_no = ?
            ORDER BY order_detail_id
            """,
            (farm, order_no),
        )
        rows = []
        for r in cur.fetchall():
            rows.append(
                {
                    "order_detail_id": str(_row_val(r, "order_detail_id", 0) or ""),
                    "variety_cd": str(_row_val(r, "variety_cd", 1) or ""),
                    "weight": _as_float(_row_val(r, "weight", 2)),
                    "grade_cd": str(_row_val(r, "grade_cd", 3) or ""),
                    "size_cd": str(_row_val(r, "size_cd", 4) or ""),
                    "wh_cd": str(_row_val(r, "wh_cd", 5) or WAREHOUSE_CD_DEFAULT),
                    "harvest_year": int(_as_float(_row_val(r, "harvest_year", 6), today_ops().year)),
                    "qty": _as_float(_row_val(r, "qty", 7)),
                    "allocated_qty": _as_float(_row_val(r, "allocated_qty", 8)),
                }
            )
        return rows

    def _validate_alloc_edit(
        self, payload: OrderSaveInput, snapshot: list[dict[str, Any]]
    ) -> None:
        harvest_default = today_ops().year
        for idx, snap in enumerate(snapshot):
            allocated = _as_float(snap["allocated_qty"])
            if allocated <= _QTY_EPS:
                continue
            if idx >= len(payload.lines):
                raise OrderValidationError(MSG_ORDER_ALLOC_SPEC_LOCKED)
            ln = payload.lines[idx]
            ln_wh = str(ln.warehouse_cd or "").strip() or WAREHOUSE_CD_DEFAULT
            ln_year = int(ln.harvest_year or harvest_default)
            if (
                str(ln.variety_cd).strip() != snap["variety_cd"]
                or abs(_as_float(ln.weight) - snap["weight"]) > _QTY_EPS
                or str(ln.grade_cd).strip() != snap["grade_cd"]
                or str(ln.size_cd).strip() != snap["size_cd"]
                or ln_wh != snap["wh_cd"]
                or ln_year != snap["harvest_year"]
            ):
                raise OrderValidationError(MSG_ORDER_ALLOC_SPEC_LOCKED)
            if _as_float(ln.qty) + _QTY_EPS < allocated:
                raise OrderValidationError(MSG_ORDER_ALLOC_QTY_BELOW)

    def _validate_payload(self, farm_cd: str, payload: OrderSaveInput) -> None:
        cust_id = str(payload.custm_id or "").strip()
        if not cust_id or cust_id == "GUEST":
            raise OrderValidationError("고객을 선택해 주십시오.")
        cur = self.conn.cursor()
        try:
            cur.execute(
                """
                SELECT 1 FROM m_customer
                WHERE farm_cd = ? AND custm_id = ? AND COALESCE(use_yn, 'Y') = 'Y'
                LIMIT 1
                """,
                (farm_cd, cust_id),
            )
            if cur.fetchone() is None:
                raise OrderValidationError("등록된 고객이 아닙니다.")
            self._validate_prepay_method(cur, payload)
        finally:
            cur.close()
        if not payload.lines:
            raise OrderValidationError("상세 품목이 없는 주문은 기록할 수 없습니다.")
        for idx, line in enumerate(payload.lines, start=1):
            variety = str(line.variety_cd or "").strip()
            if len(variety) != VARIETY_CD_LEN:
                raise OrderValidationError(f"{idx}행 품종 코드가 올바르지 않습니다.")
            if _as_float(line.qty) <= 0:
                raise OrderValidationError(f"{idx}행 수량은 0보다 커야 합니다.")
            if _as_float(line.unit_price) < 0:
                raise OrderValidationError(f"{idx}행 단가가 올바르지 않습니다.")
            if _as_float(line.weight) < 0:
                raise OrderValidationError(f"{idx}행 중량이 올바르지 않습니다.")
            if not str(line.grade_cd or "").strip() or not str(line.size_cd or "").strip():
                raise OrderValidationError(f"{idx}행 등급/크기를 선택해 주십시오.")
            deliveries = list(line.deliveries or [])
            line_tp = (
                str(line.dlvry_tp or "").strip()
                or (
                    str(deliveries[0].delivery_tp_cd or "").strip()
                    if deliveries
                    else ""
                )
                or DELIVERY_TP_VISIT_CD
            )
            if line_tp == DELIVERY_TP_PARCEL_CD:
                dlv_sum = sum(_as_float(d.qty) for d in deliveries)
                if dlv_sum - _as_float(line.qty) > _QTY_EPS:
                    raise OrderValidationError(
                        f"{idx}행 {MSG_PARCEL_QTY_OVER}",
                        code="PARCEL_QTY_OVER",
                    )
                for d in deliveries:
                    if _as_float(d.qty) <= 0:
                        raise OrderValidationError(
                            f"{idx}행 {MSG_PARCEL_DEST_QTY}",
                            code="PARCEL_DEST_QTY",
                        )
                    if (
                        not str(d.rcv_name or "").strip()
                        or not str(d.rcv_tel or "").strip()
                        or not str(d.rcv_addr or "").strip()
                    ):
                        raise OrderValidationError(
                            f"{idx}행 {MSG_PARCEL_DEST_INCOMPLETE}",
                            code="PARCEL_DEST_INCOMPLETE",
                        )
                continue
            if not deliveries:
                raise OrderValidationError(f"{idx}행 배송 정보가 없습니다.")
            dlv_sum = sum(_as_float(d.qty) for d in deliveries)
            if abs(dlv_sum - _as_float(line.qty)) > _QTY_EPS:
                raise OrderValidationError(
                    f"{idx}행 주문량과 배송 합계가 일치하지 않습니다."
                )
            for d in deliveries:
                if _as_float(d.qty) <= 0:
                    raise OrderValidationError(f"{idx}행 배송 수량이 올바르지 않습니다.")
                tp = str(d.delivery_tp_cd or "").strip() or DELIVERY_TP_VISIT_CD
                if tp not in DELIVERY_TP_ADDR_OPTIONAL:
                    if not str(d.rcv_addr or "").strip():
                        raise OrderValidationError(
                            f"{idx}행 택배/화물 배송은 수령 주소가 필요합니다."
                        )
                if tp == DELIVERY_TP_PARCEL_CD:
                    if not str(d.rcv_name or "").strip():
                        raise OrderValidationError(
                            f"{idx}행 택배 배송은 수령인이 필요합니다."
                        )
                    if not str(d.rcv_tel or "").strip():
                        raise OrderValidationError(
                            f"{idx}행 택배 배송은 수령 연락처가 필요합니다."
                        )

    def _normalize_pre_pay_method(self, raw: str | None) -> str | None:
        s = str(raw or "").strip()
        return s or None

    def _validate_prepay_method(self, cur: sqlite3.Cursor, payload: OrderSaveInput) -> None:
        """선입금 결제수단 검증. 회계 전표는 만들지 않는다 (DEC-028)."""
        pre_pay = _as_float(payload.pre_pay_amt)
        if pre_pay < 0:
            raise OrderValidationError(MSG_ORDER_PREPAY_AMT_NEGATIVE)
        method = self._normalize_pre_pay_method(payload.pre_pay_method_cd)
        payload.pre_pay_method_cd = method
        if pre_pay == 0:
            if method is not None:
                raise OrderValidationError(MSG_ORDER_PREPAY_METHOD_FORBIDDEN_WHEN_ZERO)
            return
        if method is None:
            raise OrderValidationError(MSG_ORDER_PREPAY_METHOD_REQUIRED)
        if not _column_exists(cur, "t_order_master", "pre_pay_method_cd"):
            raise OrderValidationError(MSG_ORDER_PREPAY_METHOD_SCHEMA)
        if not _table_exists(cur, "m_account_code"):
            raise OrderValidationError(MSG_ORDER_PREPAY_METHOD_INVALID)
        cur.execute(
            """
            SELECT 1
            FROM m_account_code
            WHERE acct_cd = ?
              AND parent_cd = ?
              AND CAST(acct_level AS TEXT) = ?
              AND COALESCE(use_yn, 'N') = ?
            LIMIT 1
            """,
            (
                method,
                PREPAY_METHOD_PARENT_CD,
                str(PREPAY_METHOD_ACCT_LEVEL),
                PREPAY_METHOD_USE_YN_Y,
            ),
        )
        if cur.fetchone() is None:
            raise OrderValidationError(MSG_ORDER_PREPAY_METHOD_INVALID)

    def _total_item_amt(self, lines: Sequence[OrderLineInput]) -> float:
        total = 0.0
        for line in lines:
            total += _as_float(line.qty) * _as_float(line.unit_price)
        return total

    def _insert_master(
        self,
        cur: sqlite3.Cursor,
        *,
        farm: str,
        order_no: str,
        order_dt: str,
        payload: OrderSaveInput,
        tot_amt: float,
        user_id: str,
        now_dt: str,
    ) -> None:
        ship = float(payload.tot_ship_fee or 0)
        pre_pay = float(payload.pre_pay_amt or 0)
        method = self._normalize_pre_pay_method(payload.pre_pay_method_cd)
        has_method_col = _column_exists(cur, "t_order_master", "pre_pay_method_cd")
        if has_method_col:
            cur.execute(
                """
                INSERT INTO t_order_master (
                    order_no, farm_cd, order_dt, custm_id, status_cd, stock_status,
                    tot_order_amt, tot_ship_fee, tot_pay_amt, rmk, reg_id, reg_dt,
                    season_type_cd, pre_pay_amt, pre_pay_method_cd, sales_no
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    order_no,
                    farm,
                    order_dt,
                    payload.custm_id.strip(),
                    ORDER_STATUS_RESERVED_CD,
                    STOCK_STATUS_OPEN,
                    tot_amt,
                    ship,
                    pre_pay,
                    str(payload.rmk or ""),
                    user_id,
                    now_dt,
                    str(payload.season_type_cd or ""),
                    pre_pay,
                    method,
                    SALES_NO_EMPTY,
                ),
            )
            return
        cur.execute(
            """
            INSERT INTO t_order_master (
                order_no, farm_cd, order_dt, custm_id, status_cd, stock_status,
                tot_order_amt, tot_ship_fee, tot_pay_amt, rmk, reg_id, reg_dt,
                season_type_cd, pre_pay_amt, sales_no
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                order_no,
                farm,
                order_dt,
                payload.custm_id.strip(),
                ORDER_STATUS_RESERVED_CD,
                STOCK_STATUS_OPEN,
                tot_amt,
                ship,
                pre_pay,
                str(payload.rmk or ""),
                user_id,
                now_dt,
                str(payload.season_type_cd or ""),
                pre_pay,
                SALES_NO_EMPTY,
            ),
        )

    def _insert_lines_and_deliveries(
        self,
        cur: sqlite3.Cursor,
        *,
        farm: str,
        order_no: str,
        payload: OrderSaveInput,
        order_dt: str,
        user_id: str,
        now_dt: str,
        allocated_by_id: dict[str, float] | None = None,
    ) -> None:
        harvest_default = today_ops().year
        alloc_map = allocated_by_id or {}
        has_alloc_col = _column_exists(cur, "t_order_detail", "allocated_qty")
        for idx, line in enumerate(payload.lines, start=1):
            det_id = f"{order_no}-{idx:02d}"
            variety = str(line.variety_cd).strip()
            item_cd = str(line.item_cd or "").strip() or item_cd_from_variety(variety)
            qty = _as_float(line.qty)
            price = _as_float(line.unit_price)
            wh_cd = str(line.warehouse_cd or "").strip() or WAREHOUSE_CD_DEFAULT
            harvest_year = int(line.harvest_year or harvest_default)
            dlvry_tp = (
                str(line.dlvry_tp or "").strip()
                or str(line.deliveries[0].delivery_tp_cd or "").strip()
                or DELIVERY_TP_VISIT_CD
            )
            if has_alloc_col:
                cur.execute(
                    """
                    INSERT INTO t_order_detail (
                        order_detail_id, order_no, farm_cd, item_cd, variety_cd,
                        grade_cd, size_cd, weight, qty, unit_price, item_amt,
                        wh_cd, reg_id, reg_dt, dlvry_tp, harvest_year, allocated_qty
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        det_id,
                        order_no,
                        farm,
                        item_cd,
                        variety,
                        str(line.grade_cd).strip(),
                        str(line.size_cd).strip(),
                        _as_float(line.weight),
                        qty,
                        price,
                        qty * price,
                        wh_cd,
                        user_id,
                        now_dt,
                        dlvry_tp,
                        harvest_year,
                        _as_float(alloc_map.get(det_id, 0)),
                    ),
                )
            else:
                cur.execute(
                    """
                    INSERT INTO t_order_detail (
                        order_detail_id, order_no, farm_cd, item_cd, variety_cd,
                        grade_cd, size_cd, weight, qty, unit_price, item_amt,
                        wh_cd, reg_id, reg_dt, dlvry_tp, harvest_year
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        det_id,
                        order_no,
                        farm,
                        item_cd,
                        variety,
                        str(line.grade_cd).strip(),
                        str(line.size_cd).strip(),
                        _as_float(line.weight),
                        qty,
                        price,
                        qty * price,
                        wh_cd,
                        user_id,
                        now_dt,
                        dlvry_tp,
                        harvest_year,
                    ),
                )
            for d_idx, d in enumerate(line.deliveries, start=1):
                dlvry_id = f"{det_id}-P{d_idx:02d}"
                planned = str(d.planned_dt or "").strip() or order_dt
                try:
                    planned = to_iso_date(planned)
                except OrderValidationError:
                    planned = order_dt
                tp = str(d.delivery_tp_cd or "").strip() or dlvry_tp
                cur.execute(
                    """
                    INSERT INTO t_order_delivery (
                        order_dlvry_id, order_no, farm_cd, order_detail_id,
                        snd_name, snd_tel, snd_addr,
                        rcv_name, rcv_tel, rcv_addr,
                        dlvry_qty, dlvry_msg, delivery_tp_cd, planned_dt, reg_dt
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        dlvry_id,
                        order_no,
                        farm,
                        det_id,
                        str(d.snd_name or ""),
                        str(d.snd_tel or ""),
                        str(d.snd_addr or ""),
                        str(d.rcv_name or ""),
                        str(d.rcv_tel or ""),
                        str(d.rcv_addr or ""),
                        _as_float(d.qty),
                        str(d.dlvry_msg or ""),
                        tp,
                        planned,
                        now_dt,
                    ),
                )
