# -*- coding: utf-8 -*-
"""확정 경락 매칭 READ REST — R26-F. farm 스코프."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_auction_match_api_service
from app.schemas.auction_match import AuctionConfirmedMatchListOut
from app.services.auction_match_api_service import AuctionMatchApiService

router = APIRouter(
    prefix="/farms/{farm_cd}/auction-matches",
    tags=["auction-matches"],
)


@router.get("", response_model=AuctionConfirmedMatchListOut)
def list_confirmed_auction_matches(
    farm_cd: str,
    trade_dt: str = Query(..., min_length=10, max_length=10, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    service: AuctionMatchApiService = Depends(get_auction_match_api_service),
) -> AuctionConfirmedMatchListOut:
    return service.list_confirmed(farm_cd, trade_dt=trade_dt)
