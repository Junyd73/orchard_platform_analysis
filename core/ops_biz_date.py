# -*- coding: utf-8 -*-
"""OPS 업무 시각 — Asia/Seoul(KST). OS timezone에 의존하지 않음.

PC(core) · FastAPI(server) 공통 SSOT.
server는 app.core.ops_biz_date 에서 re-export 한다.
"""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

OPS_TZ_NAME = "Asia/Seoul"
OPS_TZ = ZoneInfo(OPS_TZ_NAME)
# 하위 호환
_OPS_TZ = OPS_TZ


def now_ops() -> datetime:
    """운영 업무 기준 현재 시각 (KST, tz-aware)."""
    return datetime.now(OPS_TZ)


def today_ops() -> date:
    """운영·관찰 등 업무 '오늘' (KST 달력일)."""
    return now_ops().date()
