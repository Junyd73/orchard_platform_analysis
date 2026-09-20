# -*- coding: utf-8 -*-
"""경매조회 REST — core.market_auction_query 어댑터."""

from __future__ import annotations

from app.core.exceptions import BusinessRuleError, ExternalDependencyError
from app.schemas.market_auction import (
    MarketAuctionItemOut,
    MarketAuctionListOut,
    MarketAuctionSummaryOut,
)
from app.services._core_path import ensure_repo_root_on_path

ensure_repo_root_on_path()

from core.market_auction_query import (  # noqa: E402
    CODE_MARKET_AUCTION_SOURCE,
    MarketAuctionQueryError,
    MarketAuctionQueryService,
)


def _map_query_error(exc: MarketAuctionQueryError) -> Exception:
    if exc.code == CODE_MARKET_AUCTION_SOURCE:
        return ExternalDependencyError(exc.message, error_code=exc.code)
    return BusinessRuleError(exc.message, error_code=exc.code)


class MarketAuctionApiService:
    def __init__(self, query_service: MarketAuctionQueryService):
        self._query = query_service

    def list_auctions(
        self,
        *,
        trade_date: str,
        market_cd: str,
        corporation_cd: str | None = None,
        origin_cd: str | None = None,
        variety: str | None = None,
        refresh: bool = False,
        page: int = 1,
        page_size: int = 50,
    ) -> MarketAuctionListOut:
        try:
            payload = self._query.query(
                trade_date=trade_date,
                market_cd=market_cd,
                corporation_cd=corporation_cd,
                origin_cd=origin_cd,
                variety=variety,
                refresh=refresh,
                page=page,
                page_size=page_size,
            )
        except MarketAuctionQueryError as exc:
            raise _map_query_error(exc) from exc
        return MarketAuctionListOut(
            trade_date=payload["trade_date"],
            fetched_at=payload["fetched_at"],
            cache_hit=bool(payload["cache_hit"]),
            stale=bool(payload["stale"]),
            market_cd=payload["market_cd"],
            market_name=payload.get("market_name"),
            total_count=int(payload["total_count"]),
            page=int(payload["page"]),
            page_size=int(payload["page_size"]),
            has_more=bool(payload["has_more"]),
            summary=MarketAuctionSummaryOut(**payload["summary"]),
            items=[MarketAuctionItemOut(**row) for row in payload["items"]],
        )
