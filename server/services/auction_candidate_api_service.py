# -*- coding: utf-8 -*-
"""경락 후보 REST — core.AuctionCandidateService 어댑터. 읽기 전용."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.db.sqlite import get_sqlite_connection
from app.schemas.auction_candidate import AuctionCandidateItemOut, AuctionCandidateListOut
from app.services._core_path import ensure_repo_root_on_path
from app.services.auction_api_errors import map_auction_error

ensure_repo_root_on_path()

from core.auction_candidate_service import (  # noqa: E402
    AuctionCandidateError,
    AuctionCandidateService,
    SourceFetch,
)


def _to_response(result: dict[str, Any]) -> AuctionCandidateListOut:
    items = [
        AuctionCandidateItemOut(
            source_type=str(row.get("source_type") or ""),
            trade_dt=str(row.get("trade_dt") or ""),
            market_cd=str(row.get("market_cd") or ""),
            market_name=str(row.get("market_name") or ""),
            corporation_name=str(row.get("corporation_name") or ""),
            origin_name=row.get("origin_name"),
            variety_name=row.get("variety_name"),
            grade_cd=row.get("grade_cd"),
            grade_name=row.get("grade_name"),
            size_name=row.get("size_name"),
            spec_name=row.get("spec_name"),
            spec_kg=row.get("spec_kg"),
            qty=int(row.get("qty") or 0),
            unit_price=int(row.get("unit_price") or 0),
            amount=int(row.get("amount") or 0),
            auction_time=row.get("auction_time"),
            requires_grade_input=bool(row.get("requires_grade_input")),
            source_key=str(row.get("source_key") or ""),
        )
        for row in (result.get("items") or [])
    ]
    return AuctionCandidateListOut(
        shipment_id=str(result.get("shipment_id") or ""),
        trade_dt=str(result.get("trade_dt") or ""),
        source_used=str(result.get("source_used") or ""),
        items=items,
    )


class AuctionCandidateApiService:
    def __init__(
        self,
        db_path: str | Path,
        *,
        settlement_fetch: SourceFetch | None = None,
        realtime_fetch: SourceFetch | None = None,
    ):
        self._db_path = db_path
        self._settlement_fetch = settlement_fetch
        self._realtime_fetch = realtime_fetch

    def list_candidates(
        self,
        farm_cd: str,
        shipment_id: str,
        trade_dt: str,
    ) -> AuctionCandidateListOut:
        with get_sqlite_connection(self._db_path) as conn:
            try:
                result = AuctionCandidateService(
                    conn,
                    settlement_fetch=self._settlement_fetch,
                    realtime_fetch=self._realtime_fetch,
                ).list_candidates(farm_cd, shipment_id, trade_dt)
            except AuctionCandidateError as exc:
                raise map_auction_error(exc, default_code="AUCTION_CANDIDATE_ERROR") from exc
        return _to_response(result)
