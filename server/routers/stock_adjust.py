# -*- coding: utf-8 -*-
"""재고 증감 REST."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header

from app.api.dependencies import get_stock_adjust_api_service
from app.schemas.stock_adjust import (
    StockAdjustBySpecRequest,
    StockAdjustRequest,
    StockAdjustResponse,
)
from app.services.stock_adjust_api_service import StockAdjustApiService

router = APIRouter(
    prefix="/farms/{farm_cd}/fruit-stock",
    tags=["fruit-stock"],
)


def _user_header(
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> str | None:
    return x_user_id


@router.post("/adjust", response_model=StockAdjustResponse)
def adjust_stock(
    farm_cd: str,
    body: StockAdjustRequest,
    user_id: str | None = Depends(_user_header),
    service: StockAdjustApiService = Depends(get_stock_adjust_api_service),
) -> StockAdjustResponse:
    return service.adjust(farm_cd, body, user_id=user_id)


@router.post("/adjust-by-spec", response_model=StockAdjustResponse)
def adjust_stock_by_spec(
    farm_cd: str,
    body: StockAdjustBySpecRequest,
    user_id: str | None = Depends(_user_header),
    service: StockAdjustApiService = Depends(get_stock_adjust_api_service),
) -> StockAdjustResponse:
    """판매규격 집계 조정 — storage_dt 사용자 선택 없음."""
    return service.adjust_by_sale_spec(farm_cd, body, user_id=user_id)
