# -*- coding: utf-8 -*-
"""모바일 날씨 상세 스키마 — 현재/시간별/주간 오전·오후 (미세먼지 제외)."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


SunMarkerKind = Literal["sunrise", "sunset"]
HourlyKind = Literal["hour", "sun"]
WeeklySource = Literal["short", "mid"]


class WeatherPeriodHalfDto(BaseModel):
    precip_prob_pct: int = 0
    precip_mm: Optional[float] = None
    wind_ms: Optional[float] = None


class WeatherCurrentDto(BaseModel):
    temp_c: Optional[float] = None
    temp_min: Optional[float] = None
    temp_max: Optional[float] = None
    temp_diff_from_yesterday: Optional[float] = None
    weather_cd: str = "WT019900"
    weather_nm: str = "정보 없음"
    humidity_pct: Optional[float] = None
    wind_ms: Optional[float] = None
    precip_mm: Optional[float] = None
    precip_prob_pct: int = 0
    sun_rise: Optional[str] = None
    sun_set: Optional[str] = None


class WeatherHourlyItemDto(BaseModel):
    at: str
    kind: HourlyKind = "hour"
    temp_c: Optional[float] = None
    precip_prob_pct: Optional[int] = None
    precip_mm: Optional[float] = None
    humidity_pct: Optional[int] = None
    wind_ms: Optional[float] = None
    icon: Optional[str] = None
    weather_cd: Optional[str] = None
    marker: Optional[SunMarkerKind] = None


class WeatherSunEventDto(BaseModel):
    at: str
    kind: SunMarkerKind


class WeatherWeeklyItemDto(BaseModel):
    date: str
    weekday: str = ""
    temp_min: int = 0
    temp_max: int = 0
    icon: str = "cloud"
    am: WeatherPeriodHalfDto = Field(default_factory=WeatherPeriodHalfDto)
    pm: WeatherPeriodHalfDto = Field(default_factory=WeatherPeriodHalfDto)
    source: WeeklySource = "short"


class WeatherDetailResponse(BaseModel):
    success: bool = True
    farm_cd: str
    date: str
    location: str = ""
    current: WeatherCurrentDto
    tomorrow_am: Optional[WeatherPeriodHalfDto] = None
    hourly: list[WeatherHourlyItemDto] = Field(default_factory=list)
    sun_events: list[WeatherSunEventDto] = Field(default_factory=list)
    weekly: list[WeatherWeeklyItemDto] = Field(default_factory=list)
    updated_at: Optional[str] = None
    elapsed: float = 0.0
    message: str = "날씨 상세 조회 완료"
