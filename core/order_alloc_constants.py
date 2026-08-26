# -*- coding: utf-8 -*-
"""주문 재고배정 Stage 3A 상수 — DEC-008 / DEC-018."""

from __future__ import annotations

TABLE_ORDER_ALLOC = "t_order_alloc"
COL_ALLOCATED_QTY = "allocated_qty"

IO_TYPE_HOLD = "HOLD"
IO_TYPE_CANCEL_HOLD = "CANCEL_HOLD"

ALLOC_ID_SUFFIX = "A"
ALLOC_ID_SEQ_LEN = 3

MSG_ALLOC_ORDER_NOT_FOUND = "주문을 찾을 수 없습니다."
MSG_ALLOC_DETAIL_NOT_FOUND = "주문 상세를 찾을 수 없습니다."
MSG_ALLOC_CANCELLED = "취소된 주문은 배정할 수 없습니다."
MSG_ALLOC_LOCKED = "현재 상태에서는 배정할 수 없습니다."
MSG_ALLOC_QTY_INVALID = "배정 수량이 올바르지 않습니다."
MSG_ALLOC_QTY_UNAVAILABLE = "가용 재고가 부족합니다."
MSG_ALLOC_OVER_ORDER = "주문 수량을 초과해 배정할 수 없습니다."
MSG_ALLOC_NO_STOCK = "배정 가능한 재고가 없습니다."
MSG_RELEASE_QTY_INVALID = "해제 수량이 올바르지 않습니다."
MSG_RELEASE_OVER = "미출고 배정량을 초과해 해제할 수 없습니다."
MSG_ALLOC_SHIPPED_CANCEL = "출고된 배정이 있어 주문을 취소할 수 없습니다."
MSG_ALLOC_SPEC_LOCKED = "배정된 상품의 규격은 변경할 수 없습니다."
MSG_ALLOC_QTY_BELOW = "배정수량보다 적게 주문수량을 줄일 수 없습니다."
MSG_ALLOC_MIGRATE_BLOCKED = (
    "현재 reserved_qty가 있어 allocation migration을 자동 진행하지 않습니다."
)
MSG_ALLOC_INVARIANT = "배정 정합성이 깨졌습니다."

REMARK_HOLD_PREFIX = "ALLOC HOLD"
REMARK_CANCEL_PREFIX = "ALLOC CANCEL_HOLD"

IO_TYPE_AUDIT = "AUDIT"
REF_TYPE_ALLOC_MIGRATE = "ALLOC_MIGRATE"

LEGACY_HOLD_CLEANUP_STOCK_SEQ = 156
LEGACY_HOLD_CLEANUP_QTY = 103.0
LEGACY_HOLD_CLEANUP_ORDERS = (
    ("ORD20260228-001", 55.0),
    ("ORD20260301-001", 17.0),
    ("ORD20260301-002", 31.0),
)


def alloc_remark(*, hold: bool, order_no: str, order_detail_id: str, storage_dt: str) -> str:
    prefix = REMARK_HOLD_PREFIX if hold else REMARK_CANCEL_PREFIX
    return f"{prefix}:{order_no}:{order_detail_id}:{storage_dt}"
