# -*- coding: utf-8 -*-
"""경매 출하 lookup REST — DEC-036-C1."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_auction_lookup_api_service
from app.schemas.auction_lookup import (
    AuctionCorporationListOut,
    AuctionMarketListOut,
)
from app.services.auction_lookup_api_service import AuctionLookupApiService

router = APIRouter(tags=["auction-lookups"])


@router.get("/auction-markets", response_model=AuctionMarketListOut)
def list_auction_markets(
    service: AuctionLookupApiService = Depends(get_auction_lookup_api_service),
) -> AuctionMarketListOut:
    return service.list_markets()


@router.get("/auction-corporations", response_model=AuctionCorporationListOut)
def list_auction_corporations(
    market_cd: str = Query(..., min_length=1),
    service: AuctionLookupApiService = Depends(get_auction_lookup_api_service),
) -> AuctionCorporationListOut:
    return service.list_corporations(market_cd=market_cd)
