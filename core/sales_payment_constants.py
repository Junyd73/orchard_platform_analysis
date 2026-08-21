# -*- coding: utf-8 -*-
"""판매 수금 Core 상수 (개발순서 3 · DEC-029)."""

from __future__ import annotations

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

COLLECTION_STATUS_UNPAID = "미수"
COLLECTION_STATUS_PARTIAL = "부분수금"
COLLECTION_STATUS_PAID = "수금완료"

MSG_SALES_NOT_FOUND = "판매 내역을 찾을 수 없습니다."
MSG_SALES_DRAFT_PAYMENT_FORBIDDEN = "임시저장(DRAFT) 판매에는 수금할 수 없습니다."
MSG_SALES_STATUS_PAYMENT_FORBIDDEN = "확정(CONFIRMED) 판매만 수금할 수 있습니다."
MSG_PAY_AMT_INVALID = "수금액은 0보다 커야 합니다."
MSG_PAY_AMT_OVER_UNPAID = "수금액이 미수금을 초과할 수 없습니다."
MSG_PAY_METHOD_REQUIRED = "결제수단을 선택해 주세요."
MSG_PAY_METHOD_INVALID = "결제수단이 올바르지 않습니다."
MSG_PAID_EXCEEDS_SALES = "수금 합계가 판매금액을 초과합니다."
MSG_SOURCE_ORDER_MISMATCH = "선입금 적용 주문번호가 판매와 일치하지 않습니다."
