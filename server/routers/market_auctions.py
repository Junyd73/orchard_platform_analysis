# -*- coding: utf-8 -*-
"""경매조회 REST — R26-B. farm 스코프 없음 (auction-lookups와 동일)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_market_auction_api_service
from app.schemas.market_auction import MarketAuctionListOut
from app.services.market_auction_api_service import MarketAuctionApiService
from app.services._core_path import ensure_repo_root_on_path

ensure_repo_root_on_path()

from core.market_price_manager import DEFAULT_MARKET_CODE  # noqa: E402

router = APIRouter(tags=["market-auctions"])

_PAGE_SIZE_MAX = 200


@router.get("/market-auctions", response_model=MarketAuctionListOut)
def list_market_auctions(
    trade_date: str = Query(..., min_length=10, max_length=10, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    market_cd: str = Query(DEFAULT_MARKET_CODE, min_length=1),
    corporation_cd: str | None = Query(None),
    origin_cd: str | None = Query(
        None,
        description="산지 코드/명칭. 콤마 구분 시 OR 다중 필터",
    ),
    variety: str | None = Query(None),
    refresh: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=_PAGE_SIZE_MAX),
    service: MarketAuctionApiService = Depends(get_market_auction_api_service),
) -> MarketAuctionListOut:
    return service.list_auctions(
        trade_date=trade_date,
        market_cd=market_cd,
        corporation_cd=corporation_cd,
        origin_cd=origin_cd,
        variety=variety,
        refresh=refresh,
        page=page,
        page_size=page_size,
    )
