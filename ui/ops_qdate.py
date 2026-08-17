# -*- coding: utf-8 -*-
"""PyQt QDate/QTime — OPS KST (today_ops / now_ops)."""

from __future__ import annotations

from PyQt6.QtCore import QDate, QTime

from core.ops_biz_date import now_ops, today_ops


def qdate_today_ops() -> QDate:
    """업무 '오늘'을 QDate로 (OS QDate.currentDate 대체)."""
    d = today_ops()
    return QDate(d.year, d.month, d.day)


def qtime_now_ops() -> QTime:
    """업무 현재 시각을 QTime로."""
    n = now_ops()
    return QTime(n.hour, n.minute, n.second)
