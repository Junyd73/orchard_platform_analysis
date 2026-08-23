# -*- coding: utf-8 -*-
"""판매 수금 Core 상수 (개발순서 3 · DEC-029)."""

from __future__ import annotations

from typing import Any

from core.order_constants import (
    PREPAY_METHOD_ACCT_LEVEL,
    PREPAY_METHOD_PARENT_CD,
    PREPAY_METHOD_USE_YN_Y,
)
from core.order_ship_constants import SALES_STATUS_CONFIRMED

SALES_STATUS_DRAFT = "DRAFT"
SALES_STATUS_PAYABLE = frozenset({SALES_STATUS_CONFIRMED})

# 현금성 결제수단 — DEC-028과 동일 (하드코딩 목록 금지)
PAY_METHOD_PARENT_CD = PREPAY_METHOD_PARENT_CD
PAY_METHOD_ACCT_LEVEL = PREPAY_METHOD_ACCT_LEVEL
PAY_METHOD_USE_YN_Y = PREPAY_METHOD_USE_YN_Y

PAID_DETAIL_SEQ_LEN = 2
PAID_DETAIL_SUFFIX = "P"

# API/Core 상태코드 (Stage5 · Stage6-0 SSOT)
PAYMENT_STATUS_UNPAID = "UNPAID"
PAYMENT_STATUS_PARTIAL = "PARTIAL"
PAYMENT_STATUS_PAID = "PAID"

# 수금 provenance — t_cash_ledger.order_no 만 기준 (Stage6B)
PAYMENT_SOURCE_GENERAL = "GENERAL"
PAYMENT_SOURCE_ORDER_PREPAY = "ORDER_PREPAY"

# UI label 전용 (DB/API 코드 아님)
COLLECTION_STATUS_UNPAID = "미수"
COLLECTION_STATUS_PARTIAL = "부분수금"
COLLECTION_STATUS_PAID = "수금완료"

PAYMENT_STATUS_UI_LABELS: dict[str, str] = {
    PAYMENT_STATUS_UNPAID: COLLECTION_STATUS_UNPAID,
    PAYMENT_STATUS_PARTIAL: COLLECTION_STATUS_PARTIAL,
    PAYMENT_STATUS_PAID: COLLECTION_STATUS_PAID,
}


def _payment_as_float(raw: Any) -> float:
    try:
        return float(raw if raw is not None else 0)
    except (TypeError, ValueError):
        return 0.0


def compute_unpaid_amt(tot_sales_amt: float, paid_amt: float) -> float:
    """조회용 미수금 — legacy 과수금 read 방어."""
    return max(0.0, _payment_as_float(tot_sales_amt) - _payment_as_float(paid_amt))


def compute_payment_status(
    sales_status: str | None,
    tot_sales_amt: float,
    paid_amt: float,
) -> str | None:
    """수금상태 — DRAFT/비CONFIRMED는 None, CONFIRMED만 UNPAID/PARTIAL/PAID."""
    st = str(sales_status or "").strip()
    if st == SALES_STATUS_DRAFT:
        return None
    if st != SALES_STATUS_CONFIRMED:
        return None
    total = _payment_as_float(tot_sales_amt)
    paid = _payment_as_float(paid_amt)
    unpaid = compute_unpaid_amt(total, paid)
    if paid <= 0:
        return PAYMENT_STATUS_UNPAID
    if unpaid <= 0:
        return PAYMENT_STATUS_PAID
    if 0 < paid < total:
        return PAYMENT_STATUS_PARTIAL
    return PAYMENT_STATUS_PAID


def payment_status_ui_label(payment_status: str | None) -> str | None:
    """영문 payment_status → UI 한글 label. null(DRAFT 등)은 None."""
    if payment_status is None:
        return None
    return PAYMENT_STATUS_UI_LABELS.get(payment_status)

MSG_SALES_NOT_FOUND = "판매 내역을 찾을 수 없습니다."
MSG_SALES_DRAFT_PAYMENT_FORBIDDEN = "임시저장(DRAFT) 판매에는 수금할 수 없습니다."
MSG_SALES_STATUS_PAYMENT_FORBIDDEN = "확정(CONFIRMED) 판매만 수금할 수 있습니다."
MSG_PAY_AMT_INVALID = "수금액은 0보다 커야 합니다."
MSG_PAY_AMT_OVER_UNPAID = "수금액이 미수금을 초과할 수 없습니다."
MSG_PAY_METHOD_REQUIRED = "결제수단을 선택해 주세요."
MSG_PAY_METHOD_INVALID = "결제수단이 올바르지 않습니다."
MSG_PAID_EXCEEDS_SALES = "수금 합계가 판매금액을 초과합니다."
MSG_SOURCE_ORDER_MISMATCH = "선입금 적용 주문번호가 판매와 일치하지 않습니다."
MSG_PAY_DT_INVALID = "수금일을 확인해 주세요."
MSG_PAY_DT_BEFORE_SALES = "수금일은 판매일보다 이전일 수 없습니다."
MSG_PAY_DT_FUTURE = "미래 날짜로 수금을 등록할 수 없습니다."

ERR_PAY_DT_INVALID = "PAY_DT_INVALID"
ERR_PAY_DT_BEFORE_SALES = "PAY_DT_BEFORE_SALES"
ERR_PAY_DT_FUTURE = "PAY_DT_FUTURE"
