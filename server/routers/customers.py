# -*- coding: utf-8 -*-
"""고객 목록·신규등록 — m_customer SSOT (PC 주문 등록과 동일)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query

from app.api.dependencies import get_order_api_service
from app.schemas.order import CustomerCreateRequest, CustomerListItem
from app.services.order_api_service import OrderApiService

router = APIRouter(
    prefix="/farms/{farm_cd}/customers",
    tags=["customers"],
)


def _user_header(
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> str | None:
    return x_user_id


@router.get("", response_model=list[CustomerListItem])
def list_customers(
    farm_cd: str,
    q: str | None = Query(default=None),
    service: OrderApiService = Depends(get_order_api_service),
) -> list[CustomerListItem]:
    return service.list_customers(farm_cd, q=q)


@router.post("", response_model=CustomerListItem)
def create_customer(
    farm_cd: str,
    body: CustomerCreateRequest,
    user_id: str | None = Depends(_user_header),
    service: OrderApiService = Depends(get_order_api_service),
) -> CustomerListItem:
    return service.create_customer(farm_cd, body, user_id=user_id)
