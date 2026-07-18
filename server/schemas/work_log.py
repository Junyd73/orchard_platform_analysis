# -*- coding: utf-8 -*-
"""영농일지 MVP 스키마 — 월간·일간(기상·이슈·작업)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class WorkLogMonthSummary(BaseModel):
    work_day_count: int = 0
    work_count: int = 0
    resource_count: int = 0
    labor_sum: float = 0.0
    expense_sum: float = 0.0


class WorkLogDayCell(BaseModel):
    work_dt: str
    weather_cd: str = ""
    weather_nm: str = ""
    work_rmk: str = ""
    has_issue: bool = False
    work_names: list[str] = Field(default_factory=list)
    work_count: int = 0
    extra_work_count: int = 0
    resource_count: int = 0
    labor_sum: float = 0.0
    expense_sum: float = 0.0
    total_cost: float = 0.0
    has_work: bool = False
    has_in_progress: bool = False


class WorkLogMonthlyResponse(BaseModel):
    success: bool = True
    year: int
    month: int
    summary: WorkLogMonthSummary
    days: dict[str, WorkLogDayCell] = Field(default_factory=dict)


class WorkLogMasterDto(BaseModel):
    work_dt: str
    farm_cd: str
    day_of_week: str | None = None
    weather_cd: str | None = None
    weather_nm: str | None = None
    temp_min: float | None = None
    temp_max: float | None = None
    precip: float | None = None
    humidity: float | None = None
    sun_rise: str | None = None
    sun_set: str | None = None
    sunshine_hr: float | None = None
    wind_max: float | None = None
    wind_min: float | None = None
    work_rmk: str | None = None


class WorkLogWorkItem(BaseModel):
    work_id: str
    work_dt: str
    farm_cd: str
    work_main_cd: str = "WK01"
    work_mid_cd: str | None = None
    work_mid_nm: str | None = None
    work_loc_id: str | None = None
    work_loc_nm: str | None = None
    rmk: str | None = None
    start_tm: str | None = None
    end_tm: str | None = None
    status_cd: str | None = None
    status_nm: str | None = None


class WorkLogDailyResponse(BaseModel):
    success: bool = True
    work_dt: str
    farm_cd: str
    master: WorkLogMasterDto | None = None
    works: list[WorkLogWorkItem] = Field(default_factory=list)


class WorkLogMasterUpsertRequest(BaseModel):
    day_of_week: str | None = None
    weather_cd: str | None = None
    temp_min: float | None = None
    temp_max: float | None = None
    precip: float | None = None
    humidity: float | None = None
    sun_rise: str | None = None
    sun_set: str | None = None
    sunshine_hr: float | None = None
    wind_max: float | None = None
    wind_min: float | None = None
    work_rmk: str | None = None


class WorkLogWorkUpsertItem(BaseModel):
    work_id: str | None = None
    work_mid_cd: str
    work_loc_id: str | None = None
    rmk: str | None = None
    start_tm: str | None = None
    end_tm: str | None = None
    status_cd: str | None = None


class WorkLogWorksUpsertRequest(BaseModel):
    works: list[WorkLogWorkUpsertItem] = Field(default_factory=list)


class WorkLogSaveResponse(BaseModel):
    success: bool = True
    work_dt: str
    farm_cd: str
    message: str = "저장되었습니다."
    work_ids: list[str] = Field(default_factory=list)
