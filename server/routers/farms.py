# -*- coding: utf-8 -*-
"""농장·필지 조회 라우터."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_farm_service
from app.schemas.farm import FarmDetail, FarmSiteDetail, FarmSiteSummary
from app.services.farm_service import FarmService

router = APIRouter(prefix="/farms", tags=["farms"])


@router.get("/{farm_cd}", response_model=FarmDetail)
def get_farm(
    farm_cd: str,
    service: FarmService = Depends(get_farm_service),
) -> FarmDetail:
    return service.get_farm(farm_cd)


@router.get("/{farm_cd}/sites", response_model=list[FarmSiteSummary])
def list_farm_sites(
    farm_cd: str,
    active_only: bool = Query(True),
    service: FarmService = Depends(get_farm_service),
) -> list[FarmSiteSummary]:
    return service.list_sites(farm_cd, active_only=active_only)


@router.get("/{farm_cd}/sites/{site_id}", response_model=FarmSiteDetail)
def get_farm_site(
    farm_cd: str,
    site_id: str,
    service: FarmService = Depends(get_farm_service),
) -> FarmSiteDetail:
    return service.get_site(farm_cd, site_id)
