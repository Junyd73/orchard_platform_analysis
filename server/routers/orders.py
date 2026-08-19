# -*- coding: utf-8 -*-
"""주문 Stage 2 라우터 — 목록/상세/등록/수정/취소."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query

from app.api.dependencies import get_order_api_service
from app.schemas.order import (
    AllocationCreateRequest,
    AllocationReleaseRequest,
    AllocationSummaryOut,
    OrderCreateRequest,
    OrderDetail,
    OrderListPage,
)
from app.services._core_path import ensure_repo_root_on_path
from app.services.order_api_service import OrderApiService

ensure_repo_root_on_path()
from core.order_constants import (  # noqa: E402
    ORDER_LIST_PAGE_DEFAULT,
    ORDER_LIST_PAGE_SIZE_DEFAULT,
    ORDER_LIST_PAGE_SIZE_MAX,
)

router = APIRouter(
    prefix="/farms/{farm_cd}/orders",
    tags=["orders"],
)


def _user_header(
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> str | None:
    return x_user_id


@router.get("", response_model=OrderListPage)
def list_orders(
    farm_cd: str,
    from_date: str | None = Query(None),
    to_date: str | None = Query(None),
    status_cd: str | None = Query(None),
    keyword: str | None = Query(None),
    page: int = Query(ORDER_LIST_PAGE_DEFAULT, ge=1),
    page_size: int = Query(
        ORDER_LIST_PAGE_SIZE_DEFAULT, ge=1, le=ORDER_LIST_PAGE_SIZE_MAX
    ),
    service: OrderApiService = Depends(get_order_api_service),
) -> OrderListPage:
    return service.list_orders(
        farm_cd,
        from_date=from_date,
        to_date=to_date,
        status_cd=status_cd,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )


@router.get("/{order_no}", response_model=OrderDetail)
def get_order(
    farm_cd: str,
    order_no: str,
    service: OrderApiService = Depends(get_order_api_service),
) -> OrderDetail:
    return service.get_order(farm_cd, order_no)


@router.post("", response_model=OrderDetail)
def create_order(
    farm_cd: str,
    body: OrderCreateRequest,
    user_id: str | None = Depends(_user_header),
    service: OrderApiService = Depends(get_order_api_service),
) -> OrderDetail:
    return service.create_order(farm_cd, body, user_id=user_id)


@router.put("/{order_no}", response_model=OrderDetail)
def replace_order(
    farm_cd: str,
    order_no: str,
    body: OrderCreateRequest,
    user_id: str | None = Depends(_user_header),
    service: OrderApiService = Depends(get_order_api_service),
) -> OrderDetail:
    return service.replace_order(farm_cd, order_no, body, user_id=user_id)


@router.post("/{order_no}/cancel", response_model=OrderDetail)
def cancel_order(
    farm_cd: str,
    order_no: str,
    user_id: str | None = Depends(_user_header),
    service: OrderApiService = Depends(get_order_api_service),
) -> OrderDetail:
    return service.cancel_order(farm_cd, order_no, user_id=user_id)


@router.get("/{order_no}/allocations", response_model=AllocationSummaryOut)
def list_allocations(
    farm_cd: str,
    order_no: str,
    service: OrderApiService = Depends(get_order_api_service),
) -> AllocationSummaryOut:
    return service.list_allocations(farm_cd, order_no)


@router.post("/{order_no}/allocations", response_model=AllocationSummaryOut)
def create_allocation(
    farm_cd: str,
    order_no: str,
    body: AllocationCreateRequest,
    user_id: str | None = Depends(_user_header),
    service: OrderApiService = Depends(get_order_api_service),
) -> AllocationSummaryOut:
    return service.allocate(farm_cd, order_no, body, user_id=user_id)


@router.post("/{order_no}/allocations/release", response_model=AllocationSummaryOut)
def release_allocation(
    farm_cd: str,
    order_no: str,
    body: AllocationReleaseRequest,
    user_id: str | None = Depends(_user_header),
    service: OrderApiService = Depends(get_order_api_service),
) -> AllocationSummaryOut:
    return service.release_allocation(farm_cd, order_no, body, user_id=user_id)
