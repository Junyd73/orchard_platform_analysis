# -*- coding: utf-8 -*-
"""스마트 방제 가이드 REST — 읽기 전용 통합 API."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import get_observation_smart_spray_guide_api_service
from app.schemas.observation_smart_spray_guide import (
    ObservationSmartSprayGuideResponse,
)
from app.services.observation_smart_spray_guide_api_service import (
    ObservationSmartSprayGuideApiService,
)

router = APIRouter(
    prefix="/farms/{farm_cd}/observations/{obs_id}/smart-spray-guide",
    tags=["observation-smart-spray-guide"],
)


@router.get("", response_model=ObservationSmartSprayGuideResponse)
def get_observation_smart_spray_guide(
    farm_cd: str,
    obs_id: str,
    service: ObservationSmartSprayGuideApiService = Depends(
        get_observation_smart_spray_guide_api_service
    ),
) -> ObservationSmartSprayGuideResponse:
    return service.get_guide(farm_cd, obs_id)
