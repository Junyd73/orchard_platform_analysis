# -*- coding: utf-8 -*-
"""판매 추가수금 Core — cash SSOT + AccountManager SALE 재사용 (개발순서 3).

TX:
  add_payment() — BEGIN IMMEDIATE 소유
  add_payment_in_tx() — caller-owned (4단계 OrderShip 재사용용, BEGIN/COMMIT 없음)

회계: AccountManager.sync_ledger_by_basket('SALE', ...) 그대로.
발생주의 매출+미수 전표 금지. 신규 회계 엔진 금지.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from typing import Any

from core.account_manager import AccountManager
from core.ops_biz_date import now_ops_str, today_ops_iso
from core.order_ship_constants import SALES_STATUS_CONFIRMED
from core.order_service import OrderValidationError, to_iso_date
from core.sales_payment_constants import (
    compute_payment_status,
    compute_unpaid_amt,
    ERR_PAY_DT_BEFORE_SALES,
    ERR_PAY_DT_FUTURE,
    ERR_PAY_DT_INVALID,
    MSG_PAID_EXCEEDS_SALES,
    payment_status_ui_label,
    MSG_PAY_AMT_INVALID,
    MSG_PAY_AMT_OVER_UNPAID,
    MSG_PAY_DT_BEFORE_SALES,
    MSG_PAY_DT_FUTURE,
    MSG_PAY_DT_INVALID,
    MSG_PAY_METHOD_INVALID,
    MSG_PAY_METHOD_REQUIRED,
    MSG_SALES_DRAFT_PAYMENT_FORBIDDEN,
    MSG_SALES_NOT_FOUND,
    MSG_SALES_STATUS_PAYMENT_FORBIDDEN,
    MSG_SOURCE_ORDER_MISMATCH,
    PAID_DETAIL_SEQ_LEN,
    PAID_DETAIL_SUFFIX,
    PAYMENT_SOURCE_GENERAL,
    PAYMENT_SOURCE_ORDER_PREPAY,
    PAY_METHOD_ACCT_LEVEL,
    PAY_METHOD_PARENT_CD,
    PAY_METHOD_USE_YN_Y,
    SALES_STATUS_DRAFT,
)

_REF_TYPE_SALE = "SALE"
_PAID_DETAIL_RE = re.compile(
    rf"^.+-{re.escape(PAID_DETAIL_SUFFIX)}(\d+)$"
)


class PaymentError(Exception):
    def __init__(self, message: str, *, code: str = "PAYMENT_ERROR"):
        super().__init__(message)
        self.code = code


class PaymentValidationError(PaymentError):
    def __init__(self, message: str, *, code: str = "PAYMENT_VALIDATION"):
        super().__init__(message, code=code)


class PaymentNotFoundError(PaymentError):
    def __init__(self, message: str = MSG_SALES_NOT_FOUND, *, code: str = "PAYMENT_NOT_FOUND"):
        super().__init__(message, code=code)


@dataclass
class PaymentAddIn:
    farm_cd: str
    sales_no: str
    pay_amt: float
    pay_method_cd: str
    pay_dt: str = ""
    rmk: str = ""
    user_id: str = "SYSTEM"
    # Stage4: 출고 시 선입금 자동적용 provenance. None = 일반 추가수금(order_no NULL)
    source_order_no: str | None = None


class ConnectionDbAdapter:
    """AccountManager용 동일 sqlite3.Connection fetch_all 어댑터."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def fetch_all(self, query, params=()):
        cur = self.conn.cursor()
        cur.execute(query, params)
        return cur.fetchall()


def _as_float(raw: Any) -> float:
    try:
        return float(raw if raw is not None else 0)
    except (TypeError, ValueError):
        return 0.0


def _norm_text(raw: Any) -> str:
    return str(raw or "").strip()


def _basket_group_key(pay_method_cd: str) -> str:
    method = _norm_text(pay_method_cd)
    return f"{method}_{method}"


def _normalize_pay_dt(raw: Any) -> str:
    """조회용 pay_dt — ISO 우선, 파싱 불가 legacy는 raw 유지."""
    s = _norm_text(raw)
    if not s:
        return ""
    try:
        return to_iso_date(s)
    except OrderValidationError:
        return s


def _payment_source_of(order_no: Any) -> tuple[str, str | None]:
    """cash.order_no 실값만으로 GENERAL / ORDER_PREPAY 판정."""
    source = _norm_text(order_no) or None
    if source:
        return PAYMENT_SOURCE_ORDER_PREPAY, source
    return PAYMENT_SOURCE_GENERAL, None


class SalesPaymentService:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    # ------------------------------------------------------------------ public
    def get_payment_summary(self, farm_cd: str, sales_no: str) -> dict[str, Any]:
        cur = self.conn.cursor()
        try:
            return self._build_summary(cur, farm_cd, sales_no)
        finally:
            cur.close()

    def list_payments(self, farm_cd: str, sales_no: str) -> list[dict[str, Any]]:
        cur = self.conn.cursor()
        try:
            self._require_sales_row(cur, farm_cd, sales_no)
            return self._list_cash_rows(cur, farm_cd, sales_no)
        finally:
            cur.close()

    def add_payment(self, payload: PaymentAddIn) -> dict[str, Any]:
        cur = self.conn.cursor()
        try:
            cur.execute("BEGIN IMMEDIATE")
            result = self.add_payment_in_tx(cur, payload)
            self.conn.commit()
            return result
        except Exception:
            self.conn.rollback()
            raise
        finally:
            cur.close()

    def add_payment_in_tx(self, cur: sqlite3.Cursor, payload: PaymentAddIn) -> dict[str, Any]:
        """caller-owned TX. BEGIN/COMMIT 하지 않음 (4단계 OrderShip 재사용)."""
        farm = _norm_text(payload.farm_cd)
        sales_no = _norm_text(payload.sales_no)
        if not farm or not sales_no:
            raise PaymentValidationError(MSG_SALES_NOT_FOUND)

        sales = self._require_sales_row(cur, farm, sales_no)
        status = _norm_text(sales.get("sales_status"))
        if status == SALES_STATUS_DRAFT:
            raise PaymentValidationError(MSG_SALES_DRAFT_PAYMENT_FORBIDDEN)
        if status != SALES_STATUS_CONFIRMED:
            raise PaymentValidationError(MSG_SALES_STATUS_PAYMENT_FORBIDDEN)

        pay_amt = _as_float(payload.pay_amt)
        if pay_amt <= 0:
            raise PaymentValidationError(MSG_PAY_AMT_INVALID)

        method = _norm_text(payload.pay_method_cd)
        if not method:
            raise PaymentValidationError(MSG_PAY_METHOD_REQUIRED)
        self._require_cash_method(cur, method)

        tot_sales = _as_float(sales.get("tot_sales_amt"))
        paid_before = self._cash_paid_sum(cur, farm, sales_no)
        unpaid = tot_sales - paid_before
        if pay_amt - unpaid > 1e-9:
            raise PaymentValidationError(MSG_PAY_AMT_OVER_UNPAID)

        pay_dt_input = _norm_text(payload.pay_dt)
        user_id = _norm_text(payload.user_id) or "SYSTEM"
        rmk = _norm_text(payload.rmk) or f"판매입금({sales_no})"
        now_dt = now_ops_str()
        cash_order_no = self._resolve_cash_order_no(payload, sales)
        if _norm_text(payload.source_order_no):
            pay_dt_raw = pay_dt_input or today_ops_iso()
            try:
                pay_dt = to_iso_date(pay_dt_raw)
            except OrderValidationError:
                pay_dt = pay_dt_raw
        else:
            if not pay_dt_input:
                raise PaymentValidationError(
                    MSG_PAY_DT_INVALID, code=ERR_PAY_DT_INVALID
                )
            pay_dt = self._validate_general_pay_dt(
                pay_dt_input, _norm_text(sales.get("sales_dt"))
            )

        existing = self._load_cash_raw(cur, farm, sales_no)
        new_paid_detail_no = self._next_paid_detail_no(cur, sales_no)
        basket = self._build_basket(existing, new_item={
            "paid_detail_no": new_paid_detail_no,
            "pay_method_cd": method,
            "pay_amt": pay_amt,
            "rmk": rmk,
            "slip_no": None,
        })

        sales_dt = _norm_text(sales.get("sales_dt")) or pay_dt
        adapter = ConnectionDbAdapter(self.conn)
        acct = AccountManager(adapter, farm)
        ledger_queries, slip_map = acct.sync_ledger_by_basket(
            _REF_TYPE_SALE, sales_no, sales_dt, basket, user_id
        )
        for sql, params in ledger_queries:
            cur.execute(sql, params)

        self._apply_slip_map_to_cash(cur, farm, sales_no, existing, slip_map)
        new_slip = slip_map.get(_basket_group_key(method))
        cur.execute(
            """
            INSERT INTO t_cash_ledger (
                paid_detail_no, sales_no, farm_cd, pay_dt, pay_method_cd,
                pay_amt, rmk, reg_id, reg_dt, slip_no, order_no
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_paid_detail_no,
                sales_no,
                farm,
                pay_dt,
                method,
                pay_amt,
                rmk,
                user_id,
                now_dt,
                new_slip,
                cash_order_no,
            ),
        )

        paid_after = self._cash_paid_sum(cur, farm, sales_no)
        if paid_after - tot_sales > 1e-9:
            raise PaymentValidationError(MSG_PAID_EXCEEDS_SALES)
        unpaid_after = tot_sales - paid_after
        cur.execute(
            """
            UPDATE t_sales_master
               SET tot_paid_amt = ?,
                   tot_unpaid_amt = ?,
                   mod_id = ?,
                   mod_dt = ?
             WHERE farm_cd = ? AND sales_no = ?
            """,
            (paid_after, unpaid_after, user_id, now_dt, farm, sales_no),
        )

        return self._build_summary(cur, farm, sales_no)

    # ----------------------------------------------------------------- helpers
    def _require_sales_row(
        self, cur: sqlite3.Cursor, farm_cd: str, sales_no: str
    ) -> dict[str, Any]:
        cur.execute(
            """
            SELECT sales_no, farm_cd, sales_dt, sales_status,
                   tot_sales_amt, tot_paid_amt, tot_unpaid_amt, order_no
              FROM t_sales_master
             WHERE farm_cd = ? AND sales_no = ?
            """,
            (farm_cd, sales_no),
        )
        row = cur.fetchone()
        if not row:
            raise PaymentNotFoundError()
        keys = [
            "sales_no",
            "farm_cd",
            "sales_dt",
            "sales_status",
            "tot_sales_amt",
            "tot_paid_amt",
            "tot_unpaid_amt",
            "order_no",
        ]
        if isinstance(row, sqlite3.Row):
            return {k: row[k] for k in keys}
        return dict(zip(keys, row))

    @staticmethod
    def _validate_general_pay_dt(pay_dt_raw: str, sales_dt_raw: str) -> str:
        """DEC-030 — 일반수금 pay_dt: sales_dt <= pay_dt <= today (OPS KST)."""
        try:
            pay_dt = to_iso_date(pay_dt_raw)
        except OrderValidationError as exc:
            raise PaymentValidationError(
                MSG_PAY_DT_INVALID, code=ERR_PAY_DT_INVALID
            ) from exc
        try:
            sales_dt = to_iso_date(sales_dt_raw)
        except OrderValidationError as exc:
            raise PaymentValidationError(
                MSG_PAY_DT_INVALID, code=ERR_PAY_DT_INVALID
            ) from exc
        today = today_ops_iso()
        if pay_dt < sales_dt:
            raise PaymentValidationError(
                MSG_PAY_DT_BEFORE_SALES, code=ERR_PAY_DT_BEFORE_SALES
            )
        if pay_dt > today:
            raise PaymentValidationError(
                MSG_PAY_DT_FUTURE, code=ERR_PAY_DT_FUTURE
            )
        return pay_dt

    @staticmethod
    def _resolve_cash_order_no(
        payload: PaymentAddIn, sales: dict[str, Any]
    ) -> str | None:
        """선입금 provenance: source_order_no 있으면 판매.order_no와 일치해야 함."""
        source = _norm_text(payload.source_order_no)
        if not source:
            return None
        sales_order = _norm_text(sales.get("order_no"))
        if sales_order != source:
            raise PaymentValidationError(MSG_SOURCE_ORDER_MISMATCH)
        return source

    def _require_cash_method(self, cur: sqlite3.Cursor, acct_cd: str) -> None:
        cur.execute(
            """
            SELECT 1
              FROM m_account_code
             WHERE acct_cd = ?
               AND parent_cd = ?
               AND CAST(acct_level AS TEXT) = ?
               AND use_yn = ?
            """,
            (
                acct_cd,
                PAY_METHOD_PARENT_CD,
                str(PAY_METHOD_ACCT_LEVEL),
                PAY_METHOD_USE_YN_Y,
            ),
        )
        if not cur.fetchone():
            raise PaymentValidationError(MSG_PAY_METHOD_INVALID)

    def _cash_paid_sum(self, cur: sqlite3.Cursor, farm_cd: str, sales_no: str) -> float:
        cur.execute(
            """
            SELECT COALESCE(SUM(pay_amt), 0)
              FROM t_cash_ledger
             WHERE farm_cd = ? AND sales_no = ?
            """,
            (farm_cd, sales_no),
        )
        return _as_float(cur.fetchone()[0])

    def _load_cash_raw(
        self, cur: sqlite3.Cursor, farm_cd: str, sales_no: str
    ) -> list[dict[str, Any]]:
        cur.execute(
            """
            SELECT paid_detail_no, pay_dt, pay_method_cd, pay_amt, rmk, slip_no, order_no
              FROM t_cash_ledger
             WHERE farm_cd = ? AND sales_no = ?
             ORDER BY paid_detail_no
            """,
            (farm_cd, sales_no),
        )
        rows = cur.fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            if isinstance(r, sqlite3.Row):
                out.append(dict(r))
            else:
                out.append(
                    {
                        "paid_detail_no": r[0],
                        "pay_dt": r[1],
                        "pay_method_cd": r[2],
                        "pay_amt": r[3],
                        "rmk": r[4],
                        "slip_no": r[5],
                        "order_no": r[6],
                    }
                )
        return out

    def _list_cash_rows(
        self, cur: sqlite3.Cursor, farm_cd: str, sales_no: str
    ) -> list[dict[str, Any]]:
        has_rmk = self._cash_column_exists(cur, "rmk")
        has_order_no = self._cash_column_exists(cur, "order_no")
        rmk_expr = "c.rmk" if has_rmk else "NULL AS rmk"
        order_expr = "c.order_no" if has_order_no else "NULL AS order_no"
        cur.execute(
            f"""
            SELECT c.paid_detail_no, c.pay_dt, c.pay_method_cd, c.pay_amt,
                   {rmk_expr}, c.slip_no, {order_expr},
                   a.acct_nm AS pay_method_nm
              FROM t_cash_ledger c
              LEFT JOIN m_account_code a ON a.acct_cd = c.pay_method_cd
             WHERE c.farm_cd = ? AND c.sales_no = ?
             ORDER BY c.paid_detail_no
            """,
            (farm_cd, sales_no),
        )
        rows = cur.fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            if isinstance(r, sqlite3.Row):
                method_cd = _norm_text(r["pay_method_cd"])
                method_nm = _norm_text(r["pay_method_nm"]) or method_cd
                payment_source, source_order_no = _payment_source_of(r["order_no"])
                out.append(
                    {
                        "paid_detail_no": r["paid_detail_no"],
                        "pay_dt": _normalize_pay_dt(r["pay_dt"]),
                        "pay_method_cd": method_cd,
                        "pay_method_nm": method_nm,
                        "pay_amt": _as_float(r["pay_amt"]),
                        "rmk": r["rmk"],
                        "slip_no": r["slip_no"],
                        "order_no": source_order_no,
                        "payment_source": payment_source,
                        "source_order_no": source_order_no,
                    }
                )
            else:
                method_cd = _norm_text(r[2])
                method_nm = _norm_text(r[7]) or method_cd
                payment_source, source_order_no = _payment_source_of(r[6])
                out.append(
                    {
                        "paid_detail_no": r[0],
                        "pay_dt": _normalize_pay_dt(r[1]),
                        "pay_method_cd": method_cd,
                        "pay_amt": _as_float(r[3]),
                        "rmk": r[4],
                        "slip_no": r[5],
                        "order_no": source_order_no,
                        "pay_method_nm": method_nm,
                        "payment_source": payment_source,
                        "source_order_no": source_order_no,
                    }
                )
        return out

    @staticmethod
    def _cash_column_exists(cur: sqlite3.Cursor, column: str) -> bool:
        cur.execute("PRAGMA table_info(t_cash_ledger)")
        cols = {
            str(row[1] if not isinstance(row, sqlite3.Row) else row["name"])
            for row in cur.fetchall()
        }
        return column in cols

    def _build_summary(
        self, cur: sqlite3.Cursor, farm_cd: str, sales_no: str
    ) -> dict[str, Any]:
        sales = self._require_sales_row(cur, farm_cd, sales_no)
        sales_status = _norm_text(sales.get("sales_status"))
        tot_sales = _as_float(sales.get("tot_sales_amt"))
        paid = self._cash_paid_sum(cur, farm_cd, sales_no)
        unpaid = compute_unpaid_amt(tot_sales, paid)
        payment_status = compute_payment_status(sales_status, tot_sales, paid)
        payments = self._list_cash_rows(cur, farm_cd, sales_no)
        return {
            "sales_no": sales_no,
            "farm_cd": farm_cd,
            "sales_status": sales_status,
            "tot_sales_amt": tot_sales,
            "tot_paid_amt": paid,
            "tot_unpaid_amt": unpaid,
            "payment_status": payment_status,
            "collection_status": payment_status_ui_label(payment_status),
            "payments": payments,
        }

    @staticmethod
    def _next_paid_detail_no(cur: sqlite3.Cursor, sales_no: str) -> str:
        """형식은 {sales_no}-PNN 유지. seq는 동일 sales_no 전역 PK 충돌 방지."""
        cur.execute(
            "SELECT paid_detail_no FROM t_cash_ledger WHERE sales_no = ?",
            (sales_no,),
        )
        max_seq = 0
        for row in cur.fetchall():
            pd = _norm_text(row[0] if not isinstance(row, sqlite3.Row) else row[0])
            m = _PAID_DETAIL_RE.match(pd)
            if m:
                max_seq = max(max_seq, int(m.group(1)))
        return (
            f"{sales_no}-{PAID_DETAIL_SUFFIX}"
            f"{max_seq + 1:0{PAID_DETAIL_SEQ_LEN}d}"
        )

    @staticmethod
    def _build_basket(
        existing: list[dict[str, Any]], *, new_item: dict[str, Any]
    ) -> list[dict[str, Any]]:
        basket: list[dict[str, Any]] = []
        for row in existing:
            method = _norm_text(row.get("pay_method_cd"))
            amt = _as_float(row.get("pay_amt"))
            if amt <= 0 or not method:
                continue
            basket.append(
                {
                    "status": "ORG",
                    "orig_data": {
                        "paid_detail_no": row.get("paid_detail_no"),
                        "slip_no": row.get("slip_no"),
                    },
                    "acct_cd": method,
                    "method": method,
                    "amt": amt,
                    "pay_status": "Y",
                    "rmk": _norm_text(row.get("rmk")) or "",
                }
            )
        method = _norm_text(new_item.get("pay_method_cd"))
        basket.append(
            {
                "status": "INS",
                "orig_data": {
                    "paid_detail_no": new_item.get("paid_detail_no"),
                    "slip_no": new_item.get("slip_no"),
                },
                "acct_cd": method,
                "method": method,
                "amt": _as_float(new_item.get("pay_amt")),
                "pay_status": "Y",
                "rmk": _norm_text(new_item.get("rmk")) or "",
            }
        )
        return basket

    def _apply_slip_map_to_cash(
        self,
        cur: sqlite3.Cursor,
        farm_cd: str,
        sales_no: str,
        existing: list[dict[str, Any]],
        slip_map: dict[str, Any],
    ) -> None:
        for row in existing:
            method = _norm_text(row.get("pay_method_cd"))
            if not method:
                continue
            key = _basket_group_key(method)
            new_slip = slip_map.get(key)
            if not new_slip:
                continue
            pd_no = _norm_text(row.get("paid_detail_no"))
            cur.execute(
                """
                UPDATE t_cash_ledger
                   SET slip_no = ?
                 WHERE farm_cd = ? AND sales_no = ? AND paid_detail_no = ?
                """,
                (new_slip, farm_cd, sales_no, pd_no),
            )
