# -*- coding: utf-8 -*-
"""재고 조정 사유 — m_common_code AD01/AD010100. 판매 OUT과 분리. 전표 없음."""

from __future__ import annotations

IO_TYPE_IN = "IN"
IO_TYPE_OUT = "OUT"
ADJUST_IO_TYPES = frozenset({IO_TYPE_IN, IO_TYPE_OUT})

REF_TYPE_ADJUST = "ADJUST"

PARENT_ADJUST_MAJOR = "AD01"
PARENT_ADJUST_REASON = "AD010100"
LABEL_ADJUST_GROUP = "재고조정사유"

REASON_DISPOSE = "AD010101"
REASON_DAMAGE = "AD010102"
REASON_GIFT = "AD010103"
REASON_RETURN = "AD010104"
REASON_COUNT_DIFF = "AD010105"
REASON_OTHER = "AD010106"

LABEL_REASON_DISPOSE = "폐기"
LABEL_REASON_DAMAGE = "파손"
LABEL_REASON_GIFT = "증정"
LABEL_REASON_RETURN = "반품"
LABEL_REASON_COUNT_DIFF = "실사차이"
LABEL_REASON_OTHER = "기타"

ADJUST_REASON_ROWS = (
    (REASON_DISPOSE, LABEL_REASON_DISPOSE),
    (REASON_DAMAGE, LABEL_REASON_DAMAGE),
    (REASON_GIFT, LABEL_REASON_GIFT),
    (REASON_RETURN, LABEL_REASON_RETURN),
    (REASON_COUNT_DIFF, LABEL_REASON_COUNT_DIFF),
    (REASON_OTHER, LABEL_REASON_OTHER),
)

REASON_IO_ALLOWED = {
    REASON_DISPOSE: frozenset({IO_TYPE_OUT}),
    REASON_DAMAGE: frozenset({IO_TYPE_OUT}),
    REASON_GIFT: frozenset({IO_TYPE_OUT}),
    REASON_RETURN: frozenset({IO_TYPE_IN}),
    REASON_COUNT_DIFF: frozenset({IO_TYPE_IN, IO_TYPE_OUT}),
    REASON_OTHER: frozenset({IO_TYPE_IN, IO_TYPE_OUT}),
}

MSG_ADJUST_QTY = "조정 수량은 0보다 커야 합니다."
MSG_ADJUST_IO = "조정 구분이 올바르지 않습니다."
MSG_ADJUST_REASON = "조정 사유를 선택해 주세요."
MSG_ADJUST_DIR = "이 사유로는 선택한 조정을 할 수 없습니다."
MSG_ADJUST_NOT_FOUND = "재고를 찾을 수 없습니다."
MSG_ADJUST_NO_AVAIL = "가용재고보다 많이 줄일 수 없습니다."
MSG_REMARK_PREFIX = "재고조정"


def reason_allows_io(reason_cd: str, io_type: str) -> bool:
    allowed = REASON_IO_ALLOWED.get(str(reason_cd or "").strip())
    if not allowed:
        return False
    return str(io_type or "").strip().upper() in allowed
