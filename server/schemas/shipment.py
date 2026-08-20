# -*- coding: utf-8 -*-
"""판매출고 confirm REST 스키마 (Stage 5C)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ShipLineRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    qty: float = Field(..., gt=0)
    order_detail_id: str | None = None
    item_cd: str = ""
    variety_cd: str = ""
    grade_cd: str = ""
    size_cd: str = ""
    weight: float = 0.0
    harvest_year: int = 0
    wh_cd: str = ""
    unit_price: float = Field(0.0, ge=0)


class ShipConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ship_mode: Literal["STOCK", "DIRECT"]
    sales_dt: str = ""
    order_no: str | None = None
    custm_id: str | None = None
    rmk: str = ""
    dlvry_tp: str = ""
    ship_fee: float = Field(0.0, ge=0)
    rcv_name: str = ""
    rcv_tel: str = ""
    rcv_addr: str = ""
    dlvry_msg: str = ""
    lines: list[ShipLineRequest] = Field(min_length=1)


class ShipDetailOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sale_detail_no: str
    order_detail_id: str | None = None
    stock_seq: int
    qty: float


class RemainingOrderOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_detail_id: str
    order_qty: float
    confirmed_shipped_qty: float
    remaining_order_qty: float


class ShipConfirmResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    sales_no: str
    sales_status: str
    ship_mode: str
    order_no: str | None = None
    details: list[ShipDetailOut]
    order_status: str | None = None
    remaining_order_qty: float | None = None
    remaining_order: list[RemainingOrderOut] = Field(default_factory=list)
