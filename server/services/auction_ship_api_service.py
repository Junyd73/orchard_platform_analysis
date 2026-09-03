# -*- coding: utf-8 -*-
"""경매 출하 REST — core.AuctionShipService 어댑터."""

from __future__ import annotations

from pathlib import Path

from app.core.exceptions import BusinessRuleError
from app.db.sqlite import get_sqlite_connection, get_sqlite_write_connection
from app.schemas.auction_ship import (
    AuctionCancelIn,
    AuctionCancelOut,
    AuctionShipmentCreateIn,
    AuctionShipmentDetailOut,
    AuctionShipmentListItemOut,
    AuctionShipmentListPage,
    AuctionShipmentOut,
    AuctionShipmentSpecOut,
)
from app.services._core_path import ensure_repo_root_on_path
from app.services.auction_api_errors import map_auction_error

ensure_repo_root_on_path()

from core.auction_ship_constants import (  # noqa: E402
    AUCTION_SHIP_LIST_STATUSES,
    AUCTION_SHIP_STATUS_IN_TRANSIT,
    CODE_AUCTION_SHIP_LIST_STATUS,
    MSG_AUCTION_SHIP_LIST_STATUS,
)
from core.auction_correction_service import AuctionCorrectionService  # noqa: E402
from core.auction_ship_service import (  # noqa: E402
    AuctionShipCreateIn,
    AuctionShipError,
    AuctionShipService,
    AuctionShipSpecLineIn,
)


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
    gross = row.get("gross_sales_amount")
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
        sales_no=str(row.get("sales_no") or "").strip() or None,
        match_trade_dt=str(row.get("match_trade_dt") or "").strip() or None,
        gross_sales_amount=None if gross is None else float(gross),
        cancel_allowed=bool(row.get("cancel_allowed")),
        reopen_allowed=bool(row.get("reopen_allowed")),
    )


def _to_detail(result: dict) -> AuctionShipmentDetailOut:
    custm_id = result.get("custm_id")
    gross = result.get("gross_sales_amount")
    specs = [
        AuctionShipmentSpecOut(
            variety_cd=str(s.get("variety_cd") or ""),
            variety_name=str(s.get("variety_name") or ""),
            grade_cd=str(s.get("grade_cd") or ""),
            grade_name=str(s.get("grade_name") or ""),
            size_cd=str(s.get("size_cd") or ""),
            size_name=str(s.get("size_name") or ""),
            weight=float(s.get("weight") or 0),
            farm_shipped_qty=float(s.get("farm_shipped_qty") or 0),
            matched_qty=s.get("matched_qty"),
            diff_qty=s.get("diff_qty"),
            discrepancy_reason=s.get("discrepancy_reason"),
        )
        for s in (result.get("specs") or [])
    ]
    return AuctionShipmentDetailOut(
        shipment_id=str(result.get("shipment_id") or ""),
        ship_dt=str(result.get("ship_dt") or ""),
        market_cd=str(result.get("market_cd") or ""),
        market_name=str(result.get("market_name") or ""),
        corporation_name=str(result.get("corporation_name") or ""),
        custm_id=str(custm_id).strip() if custm_id else None,
        status=str(result.get("status") or ""),
        sales_no=str(result.get("sales_no") or "").strip() or None,
        match_trade_dt=str(result.get("match_trade_dt") or "").strip() or None,
        total_shipped_qty=float(result.get("total_shipped_qty") or 0),
        gross_sales_amount=None if gross is None else float(gross),
        specs=specs,
        cancel_allowed=bool(result.get("cancel_allowed")),
        reopen_allowed=bool(result.get("reopen_allowed")),
    )


def _with_permissions(conn, farm_cd: str, row: dict) -> dict:
    perms = AuctionCorrectionService(conn).get_action_permissions(
        farm_cd,
        str(row.get("shipment_id") or ""),
    )
    return {**row, **perms}


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
                raise map_auction_error(exc, default_code="AUCTION_SHIP_ERROR") from exc
        return _to_create_response(result)

    def list_shipments(
        self,
        farm_cd: str,
        *,
        status: str | None = None,
    ) -> AuctionShipmentListPage:
        st = str(status or AUCTION_SHIP_STATUS_IN_TRANSIT).strip() or AUCTION_SHIP_STATUS_IN_TRANSIT
        if st not in AUCTION_SHIP_LIST_STATUSES:
            raise BusinessRuleError(
                MSG_AUCTION_SHIP_LIST_STATUS,
                error_code=CODE_AUCTION_SHIP_LIST_STATUS,
            )
        with get_sqlite_connection(self._db_path) as conn:
            rows = AuctionShipService(conn).list_shipments(farm_cd, status=st)
            items = [_to_list_item(_with_permissions(conn, farm_cd, row)) for row in rows]
        return AuctionShipmentListPage(items=items, total=len(items))

    def get_shipment(self, farm_cd: str, shipment_id: str) -> AuctionShipmentDetailOut:
        with get_sqlite_connection(self._db_path) as conn:
            try:
                result = AuctionShipService(conn).get_shipment(farm_cd, shipment_id)
            except AuctionShipError as exc:
                raise map_auction_error(exc, default_code="AUCTION_SHIP_ERROR") from exc
            result = _with_permissions(conn, farm_cd, result)
        return _to_detail(result)

    def cancel_shipment(
        self,
        farm_cd: str,
        shipment_id: str,
        body: AuctionCancelIn | None = None,
        *,
        user_id: str | None,
    ) -> AuctionCancelOut:
        _ = body
        with get_sqlite_write_connection(self._db_path) as conn:
            try:
                result = AuctionShipService(conn).cancel_shipment(
                    farm_cd,
                    shipment_id,
                    user_id=(user_id or "").strip() or "MOBILE",
                )
            except AuctionShipError as exc:
                raise map_auction_error(exc, default_code="AUCTION_SHIP_ERROR") from exc
        return AuctionCancelOut(
            shipment_id=str(result.get("shipment_id") or shipment_id),
            status=str(result.get("status") or ""),
            restored_qty=float(result.get("restored_qty") or 0),
        )
