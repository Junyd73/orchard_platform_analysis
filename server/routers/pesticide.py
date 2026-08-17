# -*- coding: utf-8 -*-
"""농약 재고 라우터 — SCR-020 + 확장(통계·사전·입고·CRUD)."""

from __future__ import annotations

from datetime import date

from app.core.ops_biz_date import today_ops

from fastapi import APIRouter, Depends, Header, Query

from app.api.dependencies import get_pesticide_service
from app.schemas.pesticide import (
    PesticideRecentUsageResponse,
    PesticideStockDetailResponse,
    PesticideStockListResponse,
    PesticideUsageListResponse,
)
from app.schemas.pesticide_ext import (
    PesticideInfoDetailDto,
    PesticideInfoListResponse,
    PesticideItemUpdateRequest,
    PesticideMessageResponse,
    PesticideReceiptApplyResponse,
    PesticideReceiptDetailDto,
    PesticideReceiptListResponse,
    PesticideReceiptSaveRequest,
    PesticideReceiptSaveResponse,
    PesticideStockHistListResponse,
    PesticideStockOutRequest,
    PesticideStockOutResponse,
    PesticideSupplierListResponse,
    PesticideYearlyStatsResponse,
)
from app.services.pesticide_service import PesticideService

router = APIRouter(
    prefix="/farms/{farm_cd}/pesticide",
    tags=["pesticide"],
)


def _user_header(
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> str | None:
    return x_user_id


@router.get("/items", response_model=PesticideStockListResponse)
def list_pesticide_items(
    farm_cd: str,
    keyword: str = Query("", description="품목명·성분·분류 검색"),
    low_only: bool = Query(False, description="부족 품목만"),
    sort: str = Query("low_first", pattern="^(low_first|name)$"),
    service: PesticideService = Depends(get_pesticide_service),
) -> PesticideStockListResponse:
    return service.list_items(
        farm_cd,
        keyword=keyword,
        low_only=low_only,
        sort=sort,
    )


@router.get("/usage/recent", response_model=PesticideRecentUsageResponse)
def list_pesticide_recent_usage(
    farm_cd: str,
    days: int = Query(30, ge=1, le=90),
    max_days: int = Query(10, ge=1, le=30),
    service: PesticideService = Depends(get_pesticide_service),
) -> PesticideRecentUsageResponse:
    return service.list_recent_usage(farm_cd, days=days, max_days=max_days)


@router.get("/stats/yearly", response_model=PesticideYearlyStatsResponse)
def get_yearly_stats(
    farm_cd: str,
    year: int | None = Query(None),
    service: PesticideService = Depends(get_pesticide_service),
) -> PesticideYearlyStatsResponse:
    return service.get_yearly_stats(farm_cd, year or today_ops().year)


@router.get("/info", response_model=PesticideInfoListResponse)
def list_pesticide_info(
    farm_cd: str,
    keyword: str = Query(""),
    limit: int = Query(100, ge=1, le=300),
    service: PesticideService = Depends(get_pesticide_service),
) -> PesticideInfoListResponse:
    return service.list_info(farm_cd, keyword=keyword, limit=limit)


@router.get("/info/{info_id}", response_model=PesticideInfoDetailDto)
def get_pesticide_info(
    farm_cd: str,
    info_id: int,
    year: int | None = Query(None),
    service: PesticideService = Depends(get_pesticide_service),
) -> PesticideInfoDetailDto:
    return service.get_info_detail(
        farm_cd, info_id, year=year or today_ops().year
    )


@router.get("/suppliers", response_model=PesticideSupplierListResponse)
def list_suppliers(
    farm_cd: str,
    service: PesticideService = Depends(get_pesticide_service),
) -> PesticideSupplierListResponse:
    return service.list_suppliers(farm_cd)


@router.get("/receipts", response_model=PesticideReceiptListResponse)
def list_receipts(
    farm_cd: str,
    limit: int = Query(100, ge=1, le=300),
    service: PesticideService = Depends(get_pesticide_service),
) -> PesticideReceiptListResponse:
    return service.list_receipts(farm_cd, limit=limit)


@router.post("/receipts", response_model=PesticideReceiptSaveResponse)
def create_receipt(
    farm_cd: str,
    body: PesticideReceiptSaveRequest,
    user_id: str | None = Depends(_user_header),
    service: PesticideService = Depends(get_pesticide_service),
) -> PesticideReceiptSaveResponse:
    return service.save_receipt(farm_cd, body, user_id=user_id)


@router.get("/receipts/{receipt_id}", response_model=PesticideReceiptDetailDto)
def get_receipt(
    farm_cd: str,
    receipt_id: int,
    service: PesticideService = Depends(get_pesticide_service),
) -> PesticideReceiptDetailDto:
    return service.get_receipt_detail(farm_cd, receipt_id)


@router.put("/receipts/{receipt_id}", response_model=PesticideReceiptSaveResponse)
def update_receipt(
    farm_cd: str,
    receipt_id: int,
    body: PesticideReceiptSaveRequest,
    user_id: str | None = Depends(_user_header),
    service: PesticideService = Depends(get_pesticide_service),
) -> PesticideReceiptSaveResponse:
    return service.save_receipt(
        farm_cd, body, receipt_id=receipt_id, user_id=user_id
    )


@router.post(
    "/receipts/{receipt_id}/apply",
    response_model=PesticideReceiptApplyResponse,
)
def apply_receipt(
    farm_cd: str,
    receipt_id: int,
    user_id: str | None = Depends(_user_header),
    service: PesticideService = Depends(get_pesticide_service),
) -> PesticideReceiptApplyResponse:
    return service.apply_receipt(farm_cd, receipt_id, user_id=user_id)


@router.delete("/receipts/{receipt_id}", response_model=PesticideMessageResponse)
def delete_receipt(
    farm_cd: str,
    receipt_id: int,
    user_id: str | None = Depends(_user_header),
    service: PesticideService = Depends(get_pesticide_service),
) -> PesticideMessageResponse:
    return service.delete_receipt(farm_cd, receipt_id, user_id=user_id)


@router.post(
    "/items/{item_id}/stock-out",
    response_model=PesticideStockOutResponse,
)
def issue_pesticide_stock_out(
    farm_cd: str,
    item_id: int,
    body: PesticideStockOutRequest,
    user_id: str | None = Depends(_user_header),
    service: PesticideService = Depends(get_pesticide_service),
) -> PesticideStockOutResponse:
    return service.issue_stock_out(farm_cd, item_id, body, user_id=user_id)


@router.get(
    "/items/{item_id}/stock-hist",
    response_model=PesticideStockHistListResponse,
)
def list_item_stock_hist(
    farm_cd: str,
    item_id: int,
    limit: int = Query(100, ge=1, le=300),
    service: PesticideService = Depends(get_pesticide_service),
) -> PesticideStockHistListResponse:
    return service.list_stock_hist(farm_cd, item_id, limit=limit)


@router.get("/items/{item_id}/usage", response_model=PesticideUsageListResponse)
def list_pesticide_item_usage(
    farm_cd: str,
    item_id: int,
    date_from: str = Query(""),
    date_to: str = Query(""),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    service: PesticideService = Depends(get_pesticide_service),
) -> PesticideUsageListResponse:
    return service.list_item_usage(
        farm_cd,
        item_id,
        date_from=date_from,
        date_to=date_to,
        offset=offset,
        limit=limit,
    )


@router.get("/items/{item_id}", response_model=PesticideStockDetailResponse)
def get_pesticide_item(
    farm_cd: str,
    item_id: int,
    service: PesticideService = Depends(get_pesticide_service),
) -> PesticideStockDetailResponse:
    return service.get_item_detail(farm_cd, item_id)


@router.put("/items/{item_id}", response_model=PesticideMessageResponse)
def update_pesticide_item(
    farm_cd: str,
    item_id: int,
    body: PesticideItemUpdateRequest,
    user_id: str | None = Depends(_user_header),
    service: PesticideService = Depends(get_pesticide_service),
) -> PesticideMessageResponse:
    return service.update_item(farm_cd, item_id, body, user_id=user_id)


@router.delete("/items/{item_id}", response_model=PesticideMessageResponse)
def delete_pesticide_item(
    farm_cd: str,
    item_id: int,
    user_id: str | None = Depends(_user_header),
    service: PesticideService = Depends(get_pesticide_service),
) -> PesticideMessageResponse:
    return service.delete_item(farm_cd, item_id, user_id=user_id)
