# -*- coding: utf-8 -*-
"""관찰 PSIS REST — ApplicationService 공통 엔진 연동."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query

from app.api.dependencies import get_observation_psis_api_service
from app.schemas.observation_psis import (
    ObservationPsisHistoryResponse,
    ObservationPsisResponse,
    ObservationPsisSearchRequest,
)
from app.services.observation_psis_api_service import ObservationPsisApiService

router = APIRouter(
    prefix="/farms/{farm_cd}/observations/{obs_id}/psis",
    tags=["observation-psis"],
)


def _user_header(
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> str | None:
    return x_user_id


@router.post("", response_model=ObservationPsisResponse)
def run_observation_psis_search(
    farm_cd: str,
    obs_id: str,
    body: ObservationPsisSearchRequest,
    user_id: str | None = Depends(_user_header),
    service: ObservationPsisApiService = Depends(get_observation_psis_api_service),
) -> ObservationPsisResponse:
    return service.search(
        farm_cd,
        obs_id,
        user_id=user_id,
        analysis_id=body.analysis_id,
        candidate_seq=body.candidate_seq,
        crop_name=body.crop_name,
        disease_name=body.disease_name,
        force_refresh=body.force_refresh,
        allow_similar=body.allow_similar,
    )


@router.get("", response_model=ObservationPsisResponse)
def get_observation_psis(
    farm_cd: str,
    obs_id: str,
    crop_name: str | None = Query(None),
    disease_name: str | None = Query(None),
    service: ObservationPsisApiService = Depends(get_observation_psis_api_service),
) -> ObservationPsisResponse:
    return service.get_latest(
        farm_cd, obs_id, crop_name=crop_name, disease_name=disease_name
    )


@router.get("/history", response_model=ObservationPsisHistoryResponse)
def get_observation_psis_history(
    farm_cd: str,
    obs_id: str,
    limit: int = Query(50, ge=1, le=200),
    service: ObservationPsisApiService = Depends(get_observation_psis_api_service),
) -> ObservationPsisHistoryResponse:
    return service.get_history(farm_cd, obs_id, limit=limit)
