# -*- coding: utf-8 -*-
"""모바일 날씨 상세 REST — 현재/시간별/주간 오전·오후."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_weather_service
from app.schemas.weather import WeatherDetailResponse
from app.services.weather_service import WeatherService

router = APIRouter(
    prefix="/farms/{farm_cd}/weather",
    tags=["weather"],
)


@router.get("/detail", response_model=WeatherDetailResponse)
def get_weather_detail(
    farm_cd: str,
    date: str | None = Query(
        default=None,
        description="기준일 YYYY-MM-DD (기본: 오늘)",
    ),
    service: WeatherService = Depends(get_weather_service),
) -> WeatherDetailResponse:
    """현재 상세 + 시간별(강수·습도·바람·일출/일몰) + 주간 오전/오후."""
    return service.get_detail(farm_cd, target_date=date)
