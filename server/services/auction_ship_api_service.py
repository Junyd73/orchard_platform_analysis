# -*- coding: utf-8 -*-
"""경매 출하 REST — core.AuctionShipService 어댑터."""

from __future__ import annotations

from pathlib import Path

from app.core.exceptions import BusinessRuleError, DataIntegrityError, EntityNotFoundError
from app.db.sqlite import get_sqlite_connection, get_sqlite_write_connection
from app.schemas.auction_ship import (
    AuctionShipmentCreateIn,
    AuctionShipmentListItemOut,
    AuctionShipmentListPage,
    AuctionShipmentOut,
)
from app.services._core_path import ensure_repo_root_on_path

ensure_repo_root_on_path()

from core.auction_ship_constants import (  # noqa: E402
    AUCTION_SHIP_STATUS_IN_TRANSIT,
    CODE_AUCTION_SHIP_QTY_UNAVAILABLE,
    CODE_AUCTION_SHIP_SCHEMA,
    CODE_AUCTION_SHIP_STOCK_SCHEMA,
)
from core.auction_ship_service import (  # noqa: E402
    AuctionShipCreateIn,
    AuctionShipError,
    AuctionShipService,
    AuctionShipSpecLineIn,
)


def _map_core_error(exc: AuctionShipError) -> Exception:
    code = str(getattr(exc, "code", "") or "")
    message = str(getattr(exc, "message", None) or exc)
    if code in {
        CODE_AUCTION_SHIP_SCHEMA,
        CODE_AUCTION_SHIP_STOCK_SCHEMA,
        CODE_AUCTION_SHIP_QTY_UNAVAILABLE,
        "AUCTION_SHIP_INTEGRITY",
    }:
        return DataIntegrityError(message, error_code=code or "AUCTION_SHIP_CONFLICT")
    if code == "AUCTION_SHIP_CUSTM":
        return EntityNotFoundError(message, error_code=code)
    return BusinessRuleError(message, error_code=code or "AUCTION_SHIP_ERROR")


def _to_core(
    farm_cd: str,
    body: AuctionShipmentCreateIn,
    user_id: str,
) -> AuctionShipCreateIn:
    lines = [
        AuctionShipSpecLineIn(
            wh_cd=ln.wh_cd,
            item_cd=ln.item_cd,
            variety_cd=ln.variety_cd,
            grade_cd=ln.grade_cd,
            size_cd=ln.size_cd,
            weight=float(ln.weight),
            harvest_year=int(ln.harvest_year),
            qty=float(ln.qty),
        )
        for ln in body.lines
    ]
    return AuctionShipCreateIn(
        farm_cd=farm_cd,
        ship_dt=body.ship_dt,
        market_cd=body.market_cd,
        market_name=body.market_name,
        corporation_name=body.corporation_name,
        custm_id=body.custm_id,
        lines=lines,
        user_id=user_id,
    )


def _to_create_response(result: dict) -> AuctionShipmentOut:
    custm_id = result.get("custm_id")
    return AuctionShipmentOut(
        shipment_id=str(result.get("shipment_id") or ""),
        ship_dt=str(result.get("ship_dt") or ""),
        market_cd=str(result.get("market_cd") or ""),
        market_name=str(result.get("market_name") or ""),
        corporation_name=str(result.get("corporation_name") or ""),
        custm_id=str(custm_id).strip() if custm_id else None,
        status=str(result.get("status") or ""),
        total_shipped_qty=float(result.get("total_farm_shipped_qty") or 0),
        spec_count=int(result.get("spec_count") or 0),
        total_line_count=int(result.get("line_count") or 0),
    )


def _to_list_item(row: dict) -> AuctionShipmentListItemOut:
    custm_id = row.get("custm_id")
    return AuctionShipmentListItemOut(
        shipment_id=str(row.get("shipment_id") or ""),
        ship_dt=str(row.get("ship_dt") or ""),
        market_cd=str(row.get("market_cd") or ""),
        market_name=str(row.get("market_name") or ""),
        corporation_name=str(row.get("corporation_name") or ""),
        custm_id=str(custm_id).strip() if custm_id else None,
        status=str(row.get("status") or ""),
        total_shipped_qty=float(row.get("total_shipped_qty") or 0),
        spec_count=int(row.get("spec_count") or 0),
        total_line_count=int(row.get("total_line_count") or 0),
        reg_dt=str(row.get("reg_dt") or ""),
    )


class AuctionShipApiService:
    def __init__(self, db_path: str | Path):
        self._db_path = db_path

    def create_shipment(
        self,
        farm_cd: str,
        body: AuctionShipmentCreateIn,
        *,
        user_id: str | None,
    ) -> AuctionShipmentOut:
        payload = _to_core(
            farm_cd,
            body,
            (user_id or "").strip() or "MOBILE",
        )
        with get_sqlite_write_connection(self._db_path) as conn:
            try:
                result = AuctionShipService(conn).create_shipment(payload)
            except AuctionShipError as exc:
                raise _map_core_error(exc) from exc
        return _to_create_response(result)

    def list_shipments(
        self,
        farm_cd: str,
        *,
        status: str = AUCTION_SHIP_STATUS_IN_TRANSIT,
    ) -> AuctionShipmentListPage:
        with get_sqlite_connection(self._db_path) as conn:
            rows = AuctionShipService(conn).list_shipments(
                farm_cd,
                status=status,
            )
        items = [_to_list_item(row) for row in rows]
        return AuctionShipmentListPage(items=items, total=len(items))
