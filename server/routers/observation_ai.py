# -*- coding: utf-8 -*-
"""관찰 AI 분석 REST — ApplicationService 공통 엔진 연동."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query

from app.api.dependencies import get_observation_ai_api_service
from app.schemas.observation_ai import (
    ObservationAiAnalysisResponse,
    ObservationAiAnalyzeRequest,
    ObservationAiHistoryResponse,
)
from app.services.observation_ai_api_service import ObservationAiApiService

router = APIRouter(
    prefix="/farms/{farm_cd}/observations/{obs_id}/analysis",
    tags=["observation-ai"],
)


def _user_header(
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> str | None:
    return x_user_id


@router.post("", response_model=ObservationAiAnalysisResponse)
def run_observation_ai_analysis(
    farm_cd: str,
    obs_id: str,
    body: ObservationAiAnalyzeRequest,
    user_id: str | None = Depends(_user_header),
    service: ObservationAiApiService = Depends(get_observation_ai_api_service),
) -> ObservationAiAnalysisResponse:
    """사진 확인 → ObservationAiApplicationService.run_analysis → Stage3 → JSON."""
    return service.analyze(
        farm_cd,
        obs_id,
        user_id=user_id,
        consent=body.consent,
        photo_ids=body.photo_ids,
        crop_hint=body.crop_hint,
    )


@router.get("", response_model=ObservationAiAnalysisResponse)
def get_observation_ai_analysis(
    farm_cd: str,
    obs_id: str,
    service: ObservationAiApiService = Depends(get_observation_ai_api_service),
) -> ObservationAiAnalysisResponse:
    """최신 유효 Stage3 분석 조회."""
    return service.get_latest(farm_cd, obs_id)


@router.get("/history", response_model=ObservationAiHistoryResponse)
def get_observation_ai_analysis_history(
    farm_cd: str,
    obs_id: str,
    limit: int = Query(20, ge=1, le=100),
    service: ObservationAiApiService = Depends(get_observation_ai_api_service),
) -> ObservationAiHistoryResponse:
    """분석 이력 목록 (Stage3 list_ai_analysis_history)."""
    return service.get_history(farm_cd, obs_id, limit=limit)
