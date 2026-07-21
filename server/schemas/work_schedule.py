# -*- coding: utf-8 -*-
"""영농 일정(Schedule) API 스키마 — WLS-001 Phase1."""

from __future__ import annotations

from pydantic import BaseModel, Field


class WorkScheduleItem(BaseModel):
    farm_cd: str
    sched_id: str
    work_dt: str
    work_main_cd: str = "WK01"
    work_mid_cd: str
    work_loc_id: str | None = None
    title: str | None = None
    contents: str | None = None
    sched_status_cd: str
    converted_work_id: str | None = None
    google_event_id: str | None = None
    sync_status: str = "PENDING"
    last_synced_at: str | None = None


class WorkScheduleListResponse(BaseModel):
    success: bool = True
    data: list[WorkScheduleItem] = Field(default_factory=list)


class WorkScheduleCreateRequest(BaseModel):
    work_dt: str
    work_mid_cd: str
    work_loc_id: str | None = None
    title: str | None = None
    contents: str | None = None


class WorkScheduleUpdateRequest(BaseModel):
    work_dt: str | None = None
    work_mid_cd: str | None = None
    work_loc_id: str | None = None
    title: str | None = None
    contents: str | None = None
    sched_status_cd: str | None = None


class WorkScheduleCreateResponse(BaseModel):
    success: bool = True
    data: dict = Field(default_factory=dict)


class WorkScheduleConvertPrefill(BaseModel):
    work_dt: str
    work_mid_cd: str
    work_loc_id: str | None = None
    memo: str = ""


class WorkScheduleConvertData(BaseModel):
    sched_id: str
    work_id: str
    prefilled_data: WorkScheduleConvertPrefill


class WorkScheduleConvertResponse(BaseModel):
    success: bool = True
    data: WorkScheduleConvertData


class WorkScheduleMessageResponse(BaseModel):
    success: bool = True
    message: str = ""
