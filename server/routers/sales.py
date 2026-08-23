# -*- coding: utf-8 -*-
"""판매 목록/상세/수금내역 라우터."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query

from app.api.dependencies import get_sales_api_service
from app.schemas.sales import (
    SalesDetail,
    SalesListPage,
    SalesPaymentCreateRequest,
    SalesPaymentHistory,
)
from app.services.sales_api_service import SalesApiService

from core.sales_query_constants import (  # noqa: E402
    SALES_LIST_PAGE_DEFAULT,
    SALES_LIST_PAGE_SIZE_DEFAULT,
    SALES_LIST_PAGE_SIZE_MAX,
)

router = APIRouter(
    prefix="/farms/{farm_cd}/sales",
    tags=["sales"],
)


def _user_header(
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> str | None:
    return x_user_id


@router.get("", response_model=SalesListPage)
def list_sales(
    farm_cd: str,
    from_date: str | None = Query(None),
    to_date: str | None = Query(None),
    sales_status: str | None = Query(None),
    payment_status: str | None = Query(None),
    keyword: str | None = Query(None),
    page: int = Query(SALES_LIST_PAGE_DEFAULT, ge=1),
    page_size: int = Query(
        SALES_LIST_PAGE_SIZE_DEFAULT, ge=1, le=SALES_LIST_PAGE_SIZE_MAX
    ),
    service: SalesApiService = Depends(get_sales_api_service),
) -> SalesListPage:
    return service.list_sales(
        farm_cd,
        from_date=from_date,
        to_date=to_date,
        sales_status=sales_status,
        payment_status=payment_status,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )


@router.get("/{sales_no}/payments", response_model=SalesPaymentHistory)
def get_sale_payments(
    farm_cd: str,
    sales_no: str,
    service: SalesApiService = Depends(get_sales_api_service),
) -> SalesPaymentHistory:
    return service.get_sale_payments(farm_cd, sales_no)


@router.post("/{sales_no}/payments", response_model=SalesPaymentHistory)
def create_sale_payment(
    farm_cd: str,
    sales_no: str,
    body: SalesPaymentCreateRequest,
    user_id: str | None = Depends(_user_header),
    service: SalesApiService = Depends(get_sales_api_service),
) -> SalesPaymentHistory:
    return service.add_sale_payment(farm_cd, sales_no, body, user_id=user_id)


@router.get("/{sales_no}", response_model=SalesDetail)
def get_sale_detail(
    farm_cd: str,
    sales_no: str,
    service: SalesApiService = Depends(get_sales_api_service),
) -> SalesDetail:
    return service.get_sale_detail(farm_cd, sales_no)
