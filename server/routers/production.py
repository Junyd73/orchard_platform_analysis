# -*- coding: utf-8 -*-
"""생산확정 REST — Stage P."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query

from app.api.dependencies import get_production_api_service
from app.schemas.production import (
    HarvestRecordOut,
    ProductionConfirmRequest,
    ProductionConfirmResponse,
    RawStockItemOut,
)
from app.services.production_api_service import ProductionApiService

router = APIRouter(
    prefix="/farms/{farm_cd}/production",
    tags=["production"],
)


def _user_header(
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> str:
    return (x_user_id or "").strip() or "MOBILE"


@router.get("/harvest-records", response_model=list[HarvestRecordOut])
def list_harvest_records(
    farm_cd: str,
    from_date: str | None = Query(None, alias="from_date"),
    to_date: str | None = Query(None, alias="to_date"),
    variety_cd: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    service: ProductionApiService = Depends(get_production_api_service),
) -> list[HarvestRecordOut]:
    return service.list_harvest_records(
        farm_cd,
        from_dt=from_date,
        to_dt=to_date,
        variety_cd=variety_cd,
        limit=limit,
    )


@router.get("/raw-stock", response_model=list[RawStockItemOut])
def list_raw_stock(
    farm_cd: str,
    variety_cd: str | None = Query(None),
    service: ProductionApiService = Depends(get_production_api_service),
) -> list[RawStockItemOut]:
    return service.list_raw_stock(farm_cd, variety_cd=variety_cd)


@router.post("/confirm", response_model=ProductionConfirmResponse)
def confirm_production(
    farm_cd: str,
    body: ProductionConfirmRequest,
    user_id: str = Depends(_user_header),
    service: ProductionApiService = Depends(get_production_api_service),
) -> ProductionConfirmResponse:
    return service.confirm(farm_cd, user_id, body)
