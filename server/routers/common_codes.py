# -*- coding: utf-8 -*-
"""공통코드 조회 라우터."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_common_code_service
from app.schemas.common_code import CommonCodeItem
from app.services.common_code_service import CommonCodeService

router = APIRouter(prefix="/common-codes", tags=["common-codes"])


@router.get("", response_model=list[CommonCodeItem])
def list_common_codes(
    farm_cd: str = Query(..., min_length=1),
    parent_cd: str = Query(..., min_length=1),
    active_only: bool = Query(True),
    service: CommonCodeService = Depends(get_common_code_service),
) -> list[CommonCodeItem]:
    return service.list_codes(
        farm_cd, parent_cd, active_only=active_only
    )
