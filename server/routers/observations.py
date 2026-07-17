# -*- coding: utf-8 -*-
"""관찰(생육관찰) 라우터 — SCR-001/002/003 생명주기."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query

from app.api.dependencies import get_observation_service
from app.schemas.observation import (
    ObservationBasicCreateRequest,
    ObservationBasicUpdateRequest,
    ObservationDetail,
    ObservationDraftItem,
    ObservationListItem,
    ObservationSaveResponse,
    ObservationSummary,
)
from app.services.observation_service import ObservationService

router = APIRouter(
    prefix="/farms/{farm_cd}/observations",
    tags=["observations"],
)


def _user_header(
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> str | None:
    return x_user_id


def _role_header(
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
) -> str | None:
    return x_user_role


@router.get("/summary", response_model=ObservationSummary)
def get_observation_summary(
    farm_cd: str,
    as_of_date: str | None = Query(
        None, description="집계 기준일 YYYY-MM-DD (기본: 오늘)"
    ),
    service: ObservationService = Depends(get_observation_service),
) -> ObservationSummary:
    return service.get_summary(farm_cd, as_of_date=as_of_date)


@router.get("/drafts", response_model=list[ObservationDraftItem])
def list_observation_drafts(
    farm_cd: str,
    limit: int = Query(50, ge=1, le=200),
    service: ObservationService = Depends(get_observation_service),
) -> list[ObservationDraftItem]:
    return service.list_drafts(farm_cd, limit=limit)


@router.get("", response_model=list[ObservationListItem])
def list_observations(
    farm_cd: str,
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    site_id: str | None = Query(None),
    keyword: str | None = Query(None),
    sort: str = Query("obs_dt_desc", description="obs_dt_desc | obs_dt_asc"),
    limit: int = Query(50, ge=1, le=200),
    service: ObservationService = Depends(get_observation_service),
) -> list[ObservationListItem]:
    return service.list_observations(
        farm_cd,
        date_from=date_from,
        date_to=date_to,
        site_id=site_id,
        keyword=keyword,
        sort=sort,
        limit=limit,
    )


@router.post("", response_model=ObservationSaveResponse)
def create_observation_basic(
    farm_cd: str,
    body: ObservationBasicCreateRequest,
    x_user_id: str | None = Depends(_user_header),
    service: ObservationService = Depends(get_observation_service),
) -> ObservationSaveResponse:
    """기본정보 저장 → DRAFT (목록·통계 미포함)."""
    return service.create_basic(farm_cd, body, user_id=x_user_id)


@router.get("/{obs_id}", response_model=ObservationDetail)
def get_observation(
    farm_cd: str,
    obs_id: str,
    x_user_id: str | None = Depends(_user_header),
    x_user_role: str | None = Depends(_role_header),
    service: ObservationService = Depends(get_observation_service),
) -> ObservationDetail:
    return service.get_observation(
        farm_cd, obs_id, user_id=x_user_id, user_role=x_user_role
    )


@router.put("/{obs_id}/basic", response_model=ObservationSaveResponse)
def update_observation_basic(
    farm_cd: str,
    obs_id: str,
    body: ObservationBasicUpdateRequest,
    x_user_id: str | None = Depends(_user_header),
    service: ObservationService = Depends(get_observation_service),
) -> ObservationSaveResponse:
    return service.update_basic(farm_cd, obs_id, body, user_id=x_user_id)


@router.patch("/{obs_id}", response_model=ObservationSaveResponse)
def patch_observation(
    farm_cd: str,
    obs_id: str,
    body: ObservationBasicUpdateRequest,
    x_user_id: str | None = Depends(_user_header),
    service: ObservationService = Depends(get_observation_service),
) -> ObservationSaveResponse:
    """완료/초안 기본정보 수정 (obs_id·작성자·최초작성일 불변)."""
    return service.update_basic(farm_cd, obs_id, body, user_id=x_user_id)


@router.post("/{obs_id}/complete", response_model=ObservationSaveResponse)
def complete_observation(
    farm_cd: str,
    obs_id: str,
    x_user_id: str | None = Depends(_user_header),
    service: ObservationService = Depends(get_observation_service),
) -> ObservationSaveResponse:
    return service.complete(farm_cd, obs_id, user_id=x_user_id)


@router.post("/{obs_id}/cancel", response_model=ObservationSaveResponse)
def cancel_observation_draft(
    farm_cd: str,
    obs_id: str,
    x_user_id: str | None = Depends(_user_header),
    service: ObservationService = Depends(get_observation_service),
) -> ObservationSaveResponse:
    return service.cancel_draft(farm_cd, obs_id, user_id=x_user_id)


@router.delete("/{obs_id}", response_model=ObservationSaveResponse)
def soft_delete_observation(
    farm_cd: str,
    obs_id: str,
    delete_reason: str | None = Query(None),
    x_user_id: str | None = Depends(_user_header),
    x_user_role: str | None = Depends(_role_header),
    service: ObservationService = Depends(get_observation_service),
) -> ObservationSaveResponse:
    return service.soft_delete(
        farm_cd,
        obs_id,
        user_id=x_user_id,
        user_role=x_user_role,
        delete_reason=delete_reason,
    )
