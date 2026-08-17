# -*- coding: utf-8 -*-
"""OPS 업무 시각 — Asia/Seoul(KST). OS timezone에 의존하지 않음.

PC(core) · FastAPI(server) 공통 SSOT.
server는 app.core.ops_biz_date 에서 re-export 한다.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

OPS_TZ_NAME = "Asia/Seoul"
OPS_TZ = ZoneInfo(OPS_TZ_NAME)
# 하위 호환
_OPS_TZ = OPS_TZ

_NOW_OPS_SQL_FMT = "%Y-%m-%d %H:%M:%S"


def now_ops() -> datetime:
    """운영 업무 기준 현재 시각 (KST, tz-aware)."""
    return datetime.now(OPS_TZ)


def today_ops() -> date:
    """운영·관찰 등 업무 '오늘' (KST 달력일)."""
    return now_ops().date()


def today_ops_iso() -> str:
    """업무일 YYYY-MM-DD."""
    return today_ops().isoformat()


def now_ops_str(fmt: str = _NOW_OPS_SQL_FMT) -> str:
    """감사·등록 시각용 KST 문자열 (기본: YYYY-MM-DD HH:MM:SS)."""
    return now_ops().strftime(fmt)


# DML 전용: datetime('now','localtime') — 공백·대소문자 허용. bare datetime('now')/date('now')는 대상 아님.
_NOW_LOCALTIME_RE = re.compile(
    r"datetime\s*\(\s*'now'\s*,\s*'localtime'\s*\)",
    re.IGNORECASE,
)
_DDL_LEAD_RE = re.compile(
    r"^\s*(?:/\*.*?\*/\s*|--[^\n]*\n\s*)*(CREATE|ALTER)\b",
    re.IGNORECASE | re.DOTALL,
)


def materialize_now_ops_sql(query: str) -> str:
    """SQL DML의 datetime('now','localtime')만 KST 리터럴로 치환.

    - CREATE/ALTER(DDL)는 DEFAULT 표현식 보존을 위해 통째로 스킵
    - 인용 문자열 리터럴 내부는 치환하지 않음 (오탐 방지)
    - datetime('now') / date('now') 단독은 변경하지 않음
    """
    if not query or "now" not in query.lower():
        return query
    if _DDL_LEAD_RE.match(query):
        return query

    lit = "'" + now_ops_str().replace("'", "''") + "'"
    out: list[str] = []
    i = 0
    n = len(query)
    in_single = False
    in_double = False

    while i < n:
        ch = query[i]
        if not in_single and not in_double:
            m = _NOW_LOCALTIME_RE.match(query, i)
            if m:
                out.append(lit)
                i = m.end()
                continue
            if ch == "'":
                in_single = True
                out.append(ch)
                i += 1
                continue
            if ch == '"':
                in_double = True
                out.append(ch)
                i += 1
                continue
            out.append(ch)
            i += 1
            continue

        out.append(ch)
        if in_single:
            if ch == "'":
                # SQL escape: ''
                if i + 1 < n and query[i + 1] == "'":
                    out.append("'")
                    i += 2
                    continue
                in_single = False
            i += 1
            continue

        # in_double
        if ch == '"':
            in_double = False
        i += 1

    return "".join(out)
