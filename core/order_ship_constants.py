# -*- coding: utf-8 -*-
"""Stage 5C 출고/판매 확정 상수 (DEC-027)."""

from __future__ import annotations

SHIP_MODE_STOCK = "STOCK"
SHIP_MODE_DIRECT = "DIRECT"
SHIP_MODES = frozenset({SHIP_MODE_STOCK, SHIP_MODE_DIRECT})

SALES_STATUS_CONFIRMED = "CONFIRMED"
SALES_SOURCE_ORDER = "ORDER"
IO_TYPE_OUT = "OUT"
STOCK_STATUS_DONE = "Y"
SALES_DETAIL_SEQ_LEN = 2

MSG_SCHEMA_PRECONDITION = "출고에 필요한 테이블/컬럼이 없습니다."
MSG_STOCK_REQUIRES_ORDER = "STOCK 출고는 주문이 필요합니다."
MSG_SHIP_QTY_INVALID = "출고 수량이 올바르지 않습니다."
MSG_SHIP_MODE_INVALID = "출고방식은 STOCK 또는 DIRECT 이어야 합니다."
MSG_SHIP_LINES_REQUIRED = "출고 라인이 없습니다."
MSG_ORDER_OVER_SHIP = "주문 잔여수량을 초과해 출고할 수 없습니다."
MSG_ALLOC_OVER_SHIP = "배정 잔여수량을 초과해 출고할 수 없습니다."
MSG_STOCK_UNAVAILABLE = "출고 가능한 재고가 부족합니다."
MSG_DATA_INTEGRITY = "재고/배정 정합성이 깨졌습니다."
MSG_ORDER_LOCKED = "현재 상태에서는 출고할 수 없습니다."
MSG_DETAIL_REQUIRED = "주문 상세번호가 필요합니다."
MSG_REMARK_SALE_OUT = "판매출고"

# Stage 6 보완 2C — 택배 상품별 다배송지 (주문 MSG_PARCEL_* 의미와 정합)
MSG_PARCEL_DEST_REQUIRED = "택배 배송지를 1건 이상 등록해 주십시오."
MSG_PARCEL_DEST_QTY = "배송수량은 0보다 커야 합니다."
MSG_PARCEL_DEST_INCOMPLETE = "택배 수령인·연락처·주소를 모두 입력해 주십시오."
MSG_PARCEL_QTY_MISMATCH = "택배 배송수량 합계가 판매수량과 같아야 합니다."
MSG_PARCEL_SHIP_FEE_NEG = "배송비는 0 이상이어야 합니다."
MSG_PARCEL_SHIP_FEE_MISMATCH = "배송비 합계가 일치하지 않습니다."
MSG_DELIVERY_SCHEMA = "배송 다건 저장에 필요한 컬럼이 없습니다."
