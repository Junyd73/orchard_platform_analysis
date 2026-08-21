# -*- coding: utf-8 -*-
"""PC 판매 재저장 — order_no 보존(P1) + 선입금 행 불변(P2) + 판매일 우회차단(P2b).

Service 계층이 아님. SalesPage.execute_full_save와 테스트가 동일 규칙을 쓴다.
"""

from __future__ import annotations

import sqlite3
from typing import Any, Mapping, Sequence

MSG_PREPAY_CASH_IMMUTABLE = (
    "출고 시 자동 적용된 선입금 내역은 판매관리에서 수정하거나 삭제할 수 없습니다.\n"
    "선입금 관련 변경이 필요한 경우 주문/출고 이력을 확인해 주세요."
)
MSG_PREPAY_SALES_DT_IMMUTABLE = (
    "출고 시 자동 적용된 선입금이 있는 판매는 판매일을 변경할 수 없습니다.\n"
    "선입금 관련 변경이 필요한 경우 주문/출고 이력을 확인해 주세요."
)


class PcPrepayImmutableError(Exception):
    """Stage4 자동 선입금 cash 행 수정·삭제 시도."""

    def __init__(self, message: str = MSG_PREPAY_CASH_IMMUTABLE):
        super().__init__(message)


def _norm_order_no(raw: Any) -> str | None:
    text = str(raw or "").strip()
    return text or None


def _norm_pay_dt(raw: Any) -> str:
    return str(raw or "").strip()[:10]


def _norm_method(raw: Any) -> str:
    return str(raw or "").strip()


def _norm_amt(raw: Any) -> float:
    try:
        return round(float(raw if raw is not None else 0), 0)
    except (TypeError, ValueError):
        return 0.0


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


def fetch_master_sales_dt(
    cur: sqlite3.Cursor, farm_cd: str, sales_no: str
) -> str | None:
    """DELETE 전 DB의 t_sales_master.sales_dt만 읽는다. UI/역산 금지."""
    cur.execute(
        """
        SELECT sales_dt
          FROM t_sales_master
         WHERE farm_cd = ? AND sales_no = ?
        """,
        (farm_cd, sales_no),
    )
    row = cur.fetchone()
    if row is None:
        return None
    if isinstance(row, sqlite3.Row):
        raw = row["sales_dt"]
    else:
        raw = row[0]
    text = _norm_pay_dt(raw)
    return text or None


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


def is_protected_prepay_orig(orig_data: Mapping[str, Any] | None) -> bool:
    """보호 대상 = orig_data.order_no IS NOT NULL (Stage4 자동 선입금)."""
    if not orig_data:
        return False
    return _norm_order_no(orig_data.get("order_no")) is not None


def validate_protected_prepay_row(
    *,
    status: str,
    orig_data: Mapping[str, Any] | None,
    pay_dt: Any = None,
    pay_method_cd: Any = None,
    pay_amt: Any = None,
) -> None:
    """보호 행이면 MOD/DEL 및 ORG 핵심값 변경을 거부한다."""
    if not is_protected_prepay_orig(orig_data):
        return

    st = str(status or "").strip().upper()
    if st in {"MOD", "DEL"}:
        raise PcPrepayImmutableError()

    # ORG(및 UI 상태 누락)라도 핵심값 변경이면 거부
    o = orig_data or {}
    if (
        _norm_pay_dt(o.get("pay_dt")) != _norm_pay_dt(pay_dt)
        or _norm_method(o.get("pay_method_cd")) != _norm_method(pay_method_cd)
        or _norm_amt(o.get("pay_amt")) != _norm_amt(pay_amt)
    ):
        raise PcPrepayImmutableError()


def validate_pc_prepay_basket(pay_basket: Sequence[Mapping[str, Any]]) -> None:
    """pay_basket(+deleted) 전체에 대해 Stage4 선입금 불변성 검증."""
    for item in pay_basket:
        orig = item.get("orig_data")
        method = item.get("pay_method_cd")
        if method is None:
            method = item.get("method")
        amt = item.get("pay_amt")
        if amt is None:
            amt = item.get("amt")
        pay_dt = item.get("pay_dt")
        if pay_dt is None and isinstance(orig, Mapping):
            pay_dt = orig.get("pay_dt")
        validate_protected_prepay_row(
            status=str(item.get("status") or ""),
            orig_data=orig if isinstance(orig, Mapping) else None,
            pay_dt=pay_dt,
            pay_method_cd=method,
            pay_amt=amt,
        )


def basket_has_protected_prepay(pay_basket: Sequence[Mapping[str, Any]]) -> bool:
    for item in pay_basket:
        orig = item.get("orig_data")
        if isinstance(orig, Mapping) and is_protected_prepay_orig(orig):
            return True
    return False


def validate_protected_prepay_sales_dt(
    pay_basket: Sequence[Mapping[str, Any]],
    original_sales_dt: Any,
    current_sales_dt: Any,
) -> None:
    """보호 선입금 cash가 있으면 master.sales_dt 변경 금지 (P2b)."""
    if not basket_has_protected_prepay(pay_basket):
        return
    orig = _norm_pay_dt(original_sales_dt)
    cur = _norm_pay_dt(current_sales_dt)
    if not orig:
        # 신규 판매(기존 row 없음) — 판매일 변경 이슈 없음
        return
    if orig != cur:
        raise PcPrepayImmutableError(MSG_PREPAY_SALES_DT_IMMUTABLE)


def validate_pc_prepay_save(
    pay_basket: Sequence[Mapping[str, Any]],
    *,
    original_sales_dt: Any,
    current_sales_dt: Any,
) -> None:
    """SalesPage 저장 직전 통합 검증 (행 불변 + 판매일 불변)."""
    validate_pc_prepay_basket(pay_basket)
    validate_protected_prepay_sales_dt(
        pay_basket, original_sales_dt, current_sales_dt
    )
