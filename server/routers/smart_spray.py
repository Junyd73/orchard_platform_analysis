# -*- coding: utf-8 -*-
"""SPR-001 스마트방제·발병여건 라우터."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query

from app.api.dependencies import get_smart_spray_service
from app.schemas.smart_spray import (
    OutbreakParamDeleteRequest,
    OutbreakParamListResponse,
    OutbreakParamMutationResponse,
    OutbreakParamUpsertRequest,
    SmartSprayBriefingResponse,
)
from app.services.smart_spray_service import SmartSprayService

router = APIRouter(
    prefix="/farms/{farm_cd}/smart-spray",
    tags=["smart-spray"],
)


def _user_header(
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> str | None:
    return x_user_id


@router.get("/outbreak-params", response_model=OutbreakParamListResponse)
def list_outbreak_params(
    farm_cd: str,
    scope: str = Query("effective", pattern="^(mine|farm|effective)$"),
    user_id: str | None = Depends(_user_header),
    service: SmartSprayService = Depends(get_smart_spray_service),
) -> OutbreakParamListResponse:
    return service.list_outbreak_params(farm_cd, user_id=user_id, scope=scope)


@router.put("/outbreak-params", response_model=OutbreakParamMutationResponse)
def upsert_outbreak_param(
    farm_cd: str,
    body: OutbreakParamUpsertRequest,
    user_id: str | None = Depends(_user_header),
    service: SmartSprayService = Depends(get_smart_spray_service),
) -> OutbreakParamMutationResponse:
    return service.upsert_outbreak_param(farm_cd, body, user_id=user_id)


@router.delete("/outbreak-params", response_model=OutbreakParamMutationResponse)
def delete_outbreak_param(
    farm_cd: str,
    pest_nm: str = Query(...),
    param_key: str = Query(...),
    as_farm_default: bool = Query(False),
    user_id: str | None = Depends(_user_header),
    service: SmartSprayService = Depends(get_smart_spray_service),
) -> OutbreakParamMutationResponse:
    body = OutbreakParamDeleteRequest(
        pest_nm=pest_nm,
        param_key=param_key,
        as_farm_default=as_farm_default,
    )
    return service.delete_outbreak_param(farm_cd, body, user_id=user_id)


@router.get("/briefing", response_model=SmartSprayBriefingResponse)
def get_smart_spray_briefing(
    farm_cd: str,
    user_id: str | None = Depends(_user_header),
    service: SmartSprayService = Depends(get_smart_spray_service),
) -> SmartSprayBriefingResponse:
    return service.get_briefing(farm_cd, user_id=user_id)
