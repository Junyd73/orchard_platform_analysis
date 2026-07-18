# -*- coding: utf-8 -*-
"""관찰 AI 후보 확정 REST."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header

from app.api.dependencies import get_observation_candidate_confirm_api_service
from app.schemas.observation_candidate import (
    ObservationCandidateConfirmRequest,
    ObservationCandidateConfirmResponse,
)
from app.services.observation_candidate_confirm_api_service import (
    ObservationCandidateConfirmApiService,
)

router = APIRouter(
    prefix="/farms/{farm_cd}/observations/{obs_id}/candidates",
    tags=["observation-candidates"],
)


def _user_header(
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> str | None:
    return x_user_id


@router.post("/confirm", response_model=ObservationCandidateConfirmResponse)
def confirm_observation_candidate(
    farm_cd: str,
    obs_id: str,
    body: ObservationCandidateConfirmRequest,
    user_id: str | None = Depends(_user_header),
    service: ObservationCandidateConfirmApiService = Depends(
        get_observation_candidate_confirm_api_service
    ),
) -> ObservationCandidateConfirmResponse:
    return service.confirm(
        farm_cd,
        obs_id,
        user_id=user_id,
        analysis_id=body.analysis_id,
        candidate_seq=body.candidate_seq,
        confirmed_name=body.confirmed_name,
    )
