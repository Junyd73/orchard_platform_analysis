# -*- coding: utf-8 -*-
"""경매 출하 REST — DEC-036-B / DEC-037 Stage D·F-2."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query

from app.api.dependencies import (
    get_auction_candidate_api_service,
    get_auction_correction_api_service,
    get_auction_finalize_api_service,
    get_auction_ship_api_service,
)
from app.schemas.auction_candidate import AuctionCandidateListOut
from app.schemas.auction_ship import (
    AuctionCancelIn,
    AuctionCancelOut,
    AuctionFinalizeOut,
    AuctionFinalizeRequest,
    AuctionReopenRequest,
    AuctionReopenResponse,
    AuctionShipmentCreateIn,
    AuctionShipmentDetailOut,
    AuctionShipmentListPage,
    AuctionShipmentOut,
)
from app.services.auction_candidate_api_service import AuctionCandidateApiService
from app.services.auction_correction_api_service import AuctionCorrectionApiService
from app.services.auction_finalize_api_service import AuctionFinalizeApiService
from app.services.auction_ship_api_service import AuctionShipApiService

from core.auction_ship_constants import AUCTION_SHIP_STATUS_IN_TRANSIT

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
    status: str = Query(default=AUCTION_SHIP_STATUS_IN_TRANSIT),
    service: AuctionShipApiService = Depends(get_auction_ship_api_service),
) -> AuctionShipmentListPage:
    return service.list_shipments(farm_cd, status=status)


@router.get("/{shipment_id}", response_model=AuctionShipmentDetailOut)
def get_auction_shipment(
    farm_cd: str,
    shipment_id: str,
    service: AuctionShipApiService = Depends(get_auction_ship_api_service),
) -> AuctionShipmentDetailOut:
    return service.get_shipment(farm_cd, shipment_id)


@router.get("/{shipment_id}/auction-candidates", response_model=AuctionCandidateListOut)
def list_auction_candidates(
    farm_cd: str,
    shipment_id: str,
    trade_dt: str = Query(..., min_length=10, max_length=10, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    service: AuctionCandidateApiService = Depends(get_auction_candidate_api_service),
) -> AuctionCandidateListOut:
    return service.list_candidates(farm_cd, shipment_id, trade_dt)


@router.post("/{shipment_id}/cancel", response_model=AuctionCancelOut)
def cancel_auction_shipment(
    farm_cd: str,
    shipment_id: str,
    body: AuctionCancelIn | None = None,
    user_id: str | None = Depends(_user_header),
    service: AuctionShipApiService = Depends(get_auction_ship_api_service),
) -> AuctionCancelOut:
    return service.cancel_shipment(farm_cd, shipment_id, body, user_id=user_id)


@router.post("/{shipment_id}/finalize", response_model=AuctionFinalizeOut)
def finalize_auction_shipment(
    farm_cd: str,
    shipment_id: str,
    body: AuctionFinalizeRequest,
    user_id: str | None = Depends(_user_header),
    service: AuctionFinalizeApiService = Depends(get_auction_finalize_api_service),
) -> AuctionFinalizeOut:
    return service.finalize(farm_cd, shipment_id, body, user_id=user_id)


@router.post("/{shipment_id}/reopen", response_model=AuctionReopenResponse)
def reopen_auction_shipment(
    farm_cd: str,
    shipment_id: str,
    body: AuctionReopenRequest | None = None,
    user_id: str | None = Depends(_user_header),
    service: AuctionCorrectionApiService = Depends(get_auction_correction_api_service),
) -> AuctionReopenResponse:
    return service.reopen(farm_cd, shipment_id, body, user_id=user_id)
