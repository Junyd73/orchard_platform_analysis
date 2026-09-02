# -*- coding: utf-8 -*-
"""경매 출하 REST — DEC-036-B."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header

from app.api.dependencies import get_auction_ship_api_service
from app.schemas.auction_ship import (
    AuctionShipmentCreateIn,
    AuctionShipmentListPage,
    AuctionShipmentOut,
)
from app.services.auction_ship_api_service import AuctionShipApiService

router = APIRouter(
    prefix="/farms/{farm_cd}/auction-shipments",
    tags=["auction-shipments"],
)


def _user_header(
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> str | None:
    return x_user_id


@router.post("", response_model=AuctionShipmentOut)
def create_auction_shipment(
    farm_cd: str,
    body: AuctionShipmentCreateIn,
    user_id: str | None = Depends(_user_header),
    service: AuctionShipApiService = Depends(get_auction_ship_api_service),
) -> AuctionShipmentOut:
    return service.create_shipment(farm_cd, body, user_id=user_id)


@router.get("", response_model=AuctionShipmentListPage)
def list_auction_shipments(
    farm_cd: str,
    service: AuctionShipApiService = Depends(get_auction_ship_api_service),
) -> AuctionShipmentListPage:
    return service.list_shipments(farm_cd)
