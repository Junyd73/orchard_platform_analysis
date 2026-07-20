# -*- coding: utf-8 -*-
"""알림 API 스키마 — NTF-001 Phase1."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class NotificationItem(BaseModel):
    noti_id: str
    farm_cd: str
    noti_type_cd: str
    noti_type_nm: str = ""
    priority_cd: str
    priority_nm: str = ""
    title: str
    body: str | None = None
    payload: dict[str, Any] | None = None
    source_cd: str
    ref_type: str | None = None
    ref_id: str | None = None
    event_at: str
    read_yn: str = "N"
    read_dt: str | None = None


class NotificationSummary(BaseModel):
    unread_count: int = 0
    urgent_count: int = 0


class NotificationReadResponse(BaseModel):
    noti_id: str
    read_yn: str = "Y"
    read_dt: str | None = None


class NotificationReadAllResponse(BaseModel):
    updated_count: int = Field(0, ge=0)
