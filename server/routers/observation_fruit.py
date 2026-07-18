# -*- coding: utf-8 -*-
"""과실 측정·추적 REST."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header

from app.api.dependencies import get_observation_fruit_api_service
from app.schemas.observation_fruit import (
    FollowupUpdateRequest,
    FollowupUpdateResponse,
    FruitMeasurementResponse,
    FruitMeasurementUpsertRequest,
    ObservationTrackResponse,
)
from app.services.observation_fruit_api_service import ObservationFruitApiService

router = APIRouter(
    prefix="/farms/{farm_cd}/observations/{obs_id}",
    tags=["observation-fruit"],
)


def _user_header(
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> str | None:
    return x_user_id


@router.get("/fruit", response_model=FruitMeasurementResponse)
def get_fruit_measurement(
    farm_cd: str,
    obs_id: str,
    service: ObservationFruitApiService = Depends(get_observation_fruit_api_service),
) -> FruitMeasurementResponse:
    return service.get_measurement(farm_cd, obs_id)


@router.put("/fruit", response_model=FruitMeasurementResponse)
def upsert_fruit_measurement(
    farm_cd: str,
    obs_id: str,
    body: FruitMeasurementUpsertRequest,
    user_id: str | None = Depends(_user_header),
    service: ObservationFruitApiService = Depends(get_observation_fruit_api_service),
) -> FruitMeasurementResponse:
    return service.upsert_measurement(farm_cd, obs_id, body, user_id=user_id)


@router.get("/track", response_model=ObservationTrackResponse)
def get_observation_track(
    farm_cd: str,
    obs_id: str,
    service: ObservationFruitApiService = Depends(get_observation_fruit_api_service),
) -> ObservationTrackResponse:
    return service.list_track(farm_cd, obs_id)


@router.put("/followup", response_model=FollowupUpdateResponse)
def update_followup(
    farm_cd: str,
    obs_id: str,
    body: FollowupUpdateRequest,
    user_id: str | None = Depends(_user_header),
    service: ObservationFruitApiService = Depends(get_observation_fruit_api_service),
) -> FollowupUpdateResponse:
    return service.update_followup(
        farm_cd, obs_id, body.followup_dt, user_id=user_id
    )
