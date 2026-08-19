# -*- coding: utf-8 -*-
"""재고 조회 — 읽기 전용 (Stage 5B)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_order_api_service
from app.schemas.order import FruitStockItemOut, StockLogOut
from app.services.order_api_service import OrderApiService

router = APIRouter(
    prefix="/farms/{farm_cd}/fruit-stock",
    tags=["fruit-stock"],
)


@router.get("", response_model=list[FruitStockItemOut])
def list_fruit_stock(
    farm_cd: str,
    item_cd: str | None = Query(None),
    variety_cd: str | None = Query(None),
    wh_cd: str | None = Query(None),
    include_zero: bool = Query(False, description="소진(현재고=0) 포함 여부"),
    service: OrderApiService = Depends(get_order_api_service),
) -> list[FruitStockItemOut]:
    return service.list_fruit_stock(
        farm_cd, item_cd=item_cd, variety_cd=variety_cd,
        wh_cd=wh_cd, include_zero=include_zero,
    )


@router.get("/logs", response_model=list[StockLogOut])
def list_stock_logs(
    farm_cd: str,
    item_cd: str | None = Query(None),
    variety_cd: str | None = Query(None),
    grade_cd: str | None = Query(None),
    size_cd: str | None = Query(None),
    weight: float | None = Query(None),
    storage_dt: str | None = Query(None),
    harvest_year: int | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    service: OrderApiService = Depends(get_order_api_service),
) -> list[StockLogOut]:
    return service.list_stock_logs(
        farm_cd,
        item_cd=item_cd,
        variety_cd=variety_cd,
        grade_cd=grade_cd,
        size_cd=size_cd,
        weight=weight,
        storage_dt=storage_dt,
        harvest_year=harvest_year,
        limit=limit,
    )
