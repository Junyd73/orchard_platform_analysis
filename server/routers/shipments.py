# -*- coding: utf-8 -*-
"""판매출고 confirm REST — Stage 5C."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header

from app.api.dependencies import get_order_ship_api_service
from app.schemas.shipment import ShipConfirmRequest, ShipConfirmResponse
from app.services.order_ship_api_service import OrderShipApiService

router = APIRouter(
    prefix="/farms/{farm_cd}/shipments",
    tags=["shipments"],
)


def _user_header(
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> str | None:
    return x_user_id


@router.post("/confirm", response_model=ShipConfirmResponse)
def confirm_shipment(
    farm_cd: str,
    body: ShipConfirmRequest,
    user_id: str | None = Depends(_user_header),
    service: OrderShipApiService = Depends(get_order_ship_api_service),
) -> ShipConfirmResponse:
    return service.confirm(farm_cd, body, user_id=user_id)
