# -*- coding: utf-8 -*-
"""경락 확정 REST — core.AuctionFinalizeService 어댑터."""

from __future__ import annotations

from pathlib import Path

from app.db.sqlite import get_sqlite_write_connection
from app.schemas.auction_ship import AuctionFinalizeOut, AuctionFinalizeRequest
from app.services._core_path import ensure_repo_root_on_path
from app.services.auction_api_errors import map_auction_error

ensure_repo_root_on_path()

from core.auction_candidate_service import SourceFetch  # noqa: E402
from core.auction_finalize_service import (  # noqa: E402
    AuctionDiscrepancyIn,
    AuctionFinalizeError,
    AuctionFinalizeIn,
    AuctionFinalizeService,
    AuctionSelectedIn,
)


class AuctionFinalizeApiService:
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

    def finalize(
        self,
        farm_cd: str,
        shipment_id: str,
        body: AuctionFinalizeRequest,
        *,
        user_id: str | None,
    ) -> AuctionFinalizeOut:
        payload = AuctionFinalizeIn(
            farm_cd=farm_cd,
            shipment_id=shipment_id,
            trade_dt=body.trade_dt,
            selected=[
                AuctionSelectedIn(
                    source_key=item.source_key,
                    user_grade_cd=item.user_grade_cd,
                )
                for item in body.selected_candidates
            ],
            discrepancies=[
                AuctionDiscrepancyIn(
                    spec_variety_cd=item.variety_cd,
                    spec_grade_cd=item.grade_cd,
                    spec_size_cd=item.size_cd,
                    spec_weight=float(item.weight),
                    reason_cd=item.reason_cd,
                    remark=item.remark,
                    return_confirmed=bool(item.return_confirmed),
                )
                for item in body.discrepancies
            ],
            user_id=(user_id or "").strip() or "MOBILE",
        )
        with get_sqlite_write_connection(self._db_path) as conn:
            try:
                result = AuctionFinalizeService(
                    conn,
                    settlement_fetch=self._settlement_fetch,
                    realtime_fetch=self._realtime_fetch,
                ).finalize(payload)
            except AuctionFinalizeError as exc:
                raise map_auction_error(exc, default_code="AUCTION_MATCH_ERROR") from exc
        return AuctionFinalizeOut(
            shipment_id=str(result.get("shipment_id") or shipment_id),
            status=str(result.get("status") or ""),
            sales_no=str(result.get("sales_no") or ""),
            match_trade_dt=str(result.get("match_trade_dt") or ""),
            total_sales_qty=float(result.get("total_sales_qty") or 0),
            gross_sales_amount=float(result.get("tot_sales_amt") or 0),
            matched_count=int(result.get("match_count") or 0),
            discrepancy_count=int(result.get("discrepancy_count") or 0),
        )
