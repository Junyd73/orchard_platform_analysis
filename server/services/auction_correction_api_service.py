# -*- coding: utf-8 -*-
"""경락매칭 정정 REST — core.AuctionCorrectionService 어댑터."""

from __future__ import annotations

from pathlib import Path

from app.db.sqlite import get_sqlite_write_connection
from app.schemas.auction_ship import AuctionReopenRequest, AuctionReopenResponse
from app.services._core_path import ensure_repo_root_on_path
from app.services.auction_api_errors import map_auction_error

ensure_repo_root_on_path()

from core.auction_correction_service import (  # noqa: E402
    AuctionCorrectionError,
    AuctionCorrectionIn,
    AuctionCorrectionService,
)
from core.auction_ship_constants import AUCTION_SHIP_STATUS_IN_TRANSIT  # noqa: E402


class AuctionCorrectionApiService:
    def __init__(self, db_path: str | Path):
        self._db_path = db_path

    def reopen(
        self,
        farm_cd: str,
        shipment_id: str,
        body: AuctionReopenRequest | None = None,
        *,
        user_id: str | None,
    ) -> AuctionReopenResponse:
        payload = AuctionCorrectionIn(
            farm_cd=farm_cd,
            shipment_id=shipment_id,
            user_id=(user_id or "").strip() or "MOBILE",
            remark=None if body is None else body.remark,
        )
        with get_sqlite_write_connection(self._db_path) as conn:
            try:
                result = AuctionCorrectionService(conn).reopen(payload)
            except AuctionCorrectionError as exc:
                raise map_auction_error(
                    exc, default_code="AUCTION_CORRECTION_ERROR"
                ) from exc
        sales_no = result.get("sales_no")
        match_dt = result.get("match_trade_dt")
        return AuctionReopenResponse(
            shipment_id=str(result.get("shipment_id") or shipment_id),
            status=str(result.get("status") or AUCTION_SHIP_STATUS_IN_TRANSIT),
            sales_no=str(sales_no).strip() if sales_no else None,
            match_trade_dt=str(match_dt).strip() if match_dt else None,
            cancelled_sales_no=str(result.get("cancelled_sales_no") or ""),
        )
