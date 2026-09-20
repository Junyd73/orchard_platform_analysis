# -*- coding: utf-8 -*-
"""확정 경락 매칭 READ REST — core.auction_match_query 어댑터."""

from __future__ import annotations

from pathlib import Path

from app.db.sqlite import get_sqlite_connection
from app.schemas.auction_match import (
    AuctionConfirmedMatchItemOut,
    AuctionConfirmedMatchListOut,
)
from app.services._core_path import ensure_repo_root_on_path

ensure_repo_root_on_path()

from core.auction_match_query import list_confirmed_auction_matches  # noqa: E402


class AuctionMatchApiService:
    def __init__(self, *, db_path: str | Path):
        self._db_path = str(db_path)

    def list_confirmed(
        self,
        farm_cd: str,
        *,
        trade_dt: str,
    ) -> AuctionConfirmedMatchListOut:
        farm = str(farm_cd or "").strip()
        trade = str(trade_dt or "").strip()
        with get_sqlite_connection(self._db_path) as conn:
            conn.row_factory = __import__("sqlite3").Row
            rows = list_confirmed_auction_matches(
                conn,
                farm_cd=farm,
                trade_dt=trade,
            )
        items = [AuctionConfirmedMatchItemOut.model_validate(row) for row in rows]
        return AuctionConfirmedMatchListOut(
            farm_cd=farm,
            trade_dt=trade,
            total_count=len(items),
            items=items,
        )
