# -*- coding: utf-8 -*-
"""경매 출하 lookup REST — core.auction_lookup_service 어댑터."""

from __future__ import annotations

from pathlib import Path

from app.core.exceptions import BusinessRuleError
from app.db.sqlite import get_sqlite_connection
from app.schemas.auction_lookup import (
    AuctionCorporationListOut,
    AuctionCorporationOut,
    AuctionMarketListOut,
    AuctionMarketOut,
)
from app.services._core_path import ensure_repo_root_on_path

ensure_repo_root_on_path()

from core.auction_lookup_service import (  # noqa: E402
    AuctionLookupError,
    CODE_AUCTION_LOOKUP_INVALID_MARKET,
    list_auction_corporations,
    list_auction_markets,
)


def _map_lookup_error(exc: AuctionLookupError) -> Exception:
    code = str(getattr(exc, "code", "") or "")
    message = str(getattr(exc, "message", None) or exc)
    if code == CODE_AUCTION_LOOKUP_INVALID_MARKET:
        return BusinessRuleError(message, error_code=code)
    return BusinessRuleError(message, error_code=code or "AUCTION_LOOKUP_ERROR")


class AuctionLookupApiService:
    def __init__(self, db_path: str | Path):
        self._db_path = db_path

    def list_markets(self) -> AuctionMarketListOut:
        items = [
            AuctionMarketOut(**row)
            for row in list_auction_markets()
        ]
        return AuctionMarketListOut(items=items)

    def list_corporations(self, *, market_cd: str) -> AuctionCorporationListOut:
        with get_sqlite_connection(self._db_path) as conn:
            try:
                rows = list_auction_corporations(conn, market_cd=market_cd)
            except AuctionLookupError as exc:
                raise _map_lookup_error(exc) from exc
        items = [AuctionCorporationOut(**row) for row in rows]
        return AuctionCorporationListOut(items=items)
