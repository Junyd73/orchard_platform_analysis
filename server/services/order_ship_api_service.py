# -*- coding: utf-8 -*-
"""판매출고 REST — core.OrderShipService.confirm() 어댑터."""

from __future__ import annotations

from pathlib import Path

from app.core.exceptions import BusinessRuleError, DataIntegrityError, EntityNotFoundError
from app.db.sqlite import get_sqlite_write_connection
from app.schemas.shipment import (
    RemainingOrderOut,
    ShipConfirmRequest,
    ShipConfirmResponse,
    ShipDetailOut,
)
from app.services._core_path import ensure_repo_root_on_path

ensure_repo_root_on_path()

from core.order_service import OrderNotFoundError, OrderSaveError  # noqa: E402
from core.order_ship_constants import SALES_STATUS_CONFIRMED  # noqa: E402
from core.order_ship_service import (  # noqa: E402
    OrderShipService,
    ShipConfirmIn,
    ShipConflictError,
    ShipError,
    ShipLineIn,
    ShipValidationError,
)
from core.order_ship_delivery import ShipDeliveryAllocIn  # noqa: E402


def _to_core(farm_cd: str, body: ShipConfirmRequest, user_id: str) -> ShipConfirmIn:
    lines: list[ShipLineIn] = []
    for ln in body.lines:
        allocs = None
        if ln.delivery_allocations is not None:
            allocs = [
                ShipDeliveryAllocIn(
                    qty=float(a.qty),
                    rcv_name=a.rcv_name or "",
                    rcv_tel=a.rcv_tel or "",
                    rcv_addr=a.rcv_addr or "",
                    dlvry_msg=a.dlvry_msg or "",
                    ship_fee=float(a.ship_fee or 0),
                )
                for a in ln.delivery_allocations
            ]
        lines.append(
            ShipLineIn(
                qty=ln.qty,
                order_detail_id=ln.order_detail_id,
                item_cd=ln.item_cd,
                variety_cd=ln.variety_cd,
                grade_cd=ln.grade_cd,
                size_cd=ln.size_cd,
                weight=ln.weight,
                harvest_year=ln.harvest_year,
                wh_cd=ln.wh_cd,
                unit_price=ln.unit_price,
                delivery_allocations=allocs,
            )
        )
    return ShipConfirmIn(
        farm_cd=farm_cd,
        ship_mode=body.ship_mode,
        order_no=body.order_no,
        sales_dt=body.sales_dt,
        custm_id=body.custm_id,
        user_id=user_id,
        rmk=body.rmk,
        dlvry_tp=getattr(body, "dlvry_tp", "") or "",
        ship_fee=float(getattr(body, "ship_fee", 0) or 0),
        rcv_name=getattr(body, "rcv_name", "") or "",
        rcv_tel=getattr(body, "rcv_tel", "") or "",
        rcv_addr=getattr(body, "rcv_addr", "") or "",
        dlvry_msg=getattr(body, "dlvry_msg", "") or "",
        snd_name=getattr(body, "snd_name", "") or "",
        snd_tel=getattr(body, "snd_tel", "") or "",
        snd_addr=getattr(body, "snd_addr", "") or "",
        lines=lines,
    )


def _map_core_error(exc: OrderSaveError) -> Exception:
    code = str(getattr(exc, "code", "") or "")
    message = str(getattr(exc, "message", None) or exc)
    if isinstance(exc, OrderNotFoundError) or code == "ORDER_NOT_FOUND":
        return EntityNotFoundError(message)
    if isinstance(exc, ShipValidationError):
        return BusinessRuleError(message, error_code=code or "SHIP_VALIDATION")
    if isinstance(exc, ShipConflictError) or code in {
        "ORDER_OVER_SHIP",
        "ALLOC_OVER_SHIP",
        "STOCK_UNAVAILABLE",
        "DATA_INTEGRITY",
        "SCHEMA_PRECONDITION",
    }:
        return DataIntegrityError(message, error_code=code or "SHIP_CONFLICT")
    if isinstance(exc, ShipError) and code == "SCHEMA_PRECONDITION":
        return DataIntegrityError(message, error_code=code)
    if isinstance(exc, ShipError):
        return BusinessRuleError(message, error_code=code or "SHIP_ERROR")
    return BusinessRuleError(message, error_code=code or "ORDER_SAVE_ERROR")


def _to_response(result: dict) -> ShipConfirmResponse:
    remaining_rows = [
        RemainingOrderOut(
            order_detail_id=str(row.get("order_detail_id") or ""),
            order_qty=float(row.get("order_qty") or 0),
            confirmed_shipped_qty=float(row.get("confirmed_shipped_qty") or 0),
            remaining_order_qty=float(row.get("remaining_order_qty") or 0),
        )
        for row in result.get("remaining_order") or []
    ]
    remaining_total = None
    if remaining_rows:
        remaining_total = sum(r.remaining_order_qty for r in remaining_rows)
    order_status = result.get("order_status_cd") or None
    if order_status == "":
        order_status = None
    details = [
        ShipDetailOut(
            sale_detail_no=str(d["sale_detail_no"]),
            order_detail_id=d.get("order_detail_id"),
            stock_seq=int(d["stock_seq"]),
            qty=float(d["qty"]),
        )
        for d in result.get("sales_details") or []
    ]
    return ShipConfirmResponse(
        ok=bool(result.get("ok")),
        sales_no=str(result.get("sales_no") or ""),
        sales_status=SALES_STATUS_CONFIRMED,
        ship_mode=str(result.get("ship_mode") or ""),
        order_no=result.get("order_no"),
        details=details,
        order_status=order_status,
        remaining_order_qty=remaining_total,
        remaining_order=remaining_rows,
    )


class OrderShipApiService:
    def __init__(self, db_path: str | Path):
        self._db_path = db_path

    def confirm(
        self,
        farm_cd: str,
        body: ShipConfirmRequest,
        *,
        user_id: str | None,
    ) -> ShipConfirmResponse:
        payload = _to_core(farm_cd, body, (user_id or "").strip() or "MOBILE")
        with get_sqlite_write_connection(self._db_path) as conn:
            try:
                result = OrderShipService(conn).confirm(payload)
            except OrderSaveError as exc:
                raise _map_core_error(exc) from exc
        return _to_response(result)
