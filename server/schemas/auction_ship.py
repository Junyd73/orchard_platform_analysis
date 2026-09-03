# -*- coding: utf-8 -*-
"""경매 출하 DEC-036-B API 스키마."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AuctionShipmentLineIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    wh_cd: str = Field(..., min_length=1)
    item_cd: str = Field(..., min_length=1)
    variety_cd: str = Field(..., min_length=1)
    grade_cd: str = Field(..., min_length=1)
    size_cd: str = Field(..., min_length=1)
    weight: float = Field(..., gt=0)
    harvest_year: int
    qty: float = Field(..., gt=0)


class AuctionShipmentCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ship_dt: str = Field(..., min_length=10, max_length=10)
    market_cd: str = Field(..., min_length=1)
    market_name: str = Field(..., min_length=1)
    corporation_name: str = Field(..., min_length=1)
    custm_id: str | None = None
    lines: list[AuctionShipmentLineIn] = Field(..., min_length=1)


class AuctionShipmentOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shipment_id: str
    ship_dt: str
    market_cd: str
    market_name: str
    corporation_name: str
    custm_id: str | None = None
    status: str
    total_shipped_qty: float
    spec_count: int
    total_line_count: int


class AuctionShipmentListItemOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shipment_id: str
    ship_dt: str
    market_cd: str
    market_name: str
    corporation_name: str
    custm_id: str | None = None
    status: str
    total_shipped_qty: float
    spec_count: int
    total_line_count: int
    reg_dt: str
    sales_no: str | None = None
    match_trade_dt: str | None = None
    gross_sales_amount: float | None = None
    cancel_allowed: bool
    reopen_allowed: bool


class AuctionShipmentSpecOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    variety_cd: str
    variety_name: str
    grade_cd: str
    grade_name: str
    size_cd: str
    size_name: str
    weight: float
    farm_shipped_qty: float
    matched_qty: float | None = None
    diff_qty: float | None = None
    discrepancy_reason: str | None = None


class AuctionShipmentDetailOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shipment_id: str
    ship_dt: str
    market_cd: str
    market_name: str
    corporation_name: str
    custm_id: str | None = None
    status: str
    sales_no: str | None = None
    match_trade_dt: str | None = None
    total_shipped_qty: float
    gross_sales_amount: float | None = None
    specs: list[AuctionShipmentSpecOut]
    cancel_allowed: bool
    reopen_allowed: bool


class AuctionReopenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    remark: str | None = None


class AuctionReopenResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shipment_id: str
    status: str
    sales_no: str | None = None
    match_trade_dt: str | None = None
    cancelled_sales_no: str


class AuctionCancelIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    remark: str | None = None


class AuctionCancelOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shipment_id: str
    status: str
    restored_qty: float


class AuctionFinalizeSelectedIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_key: str = Field(..., min_length=1)
    user_grade_cd: str | None = None


class AuctionFinalizeDiscrepancyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    variety_cd: str = Field(..., min_length=1)
    grade_cd: str = Field(..., min_length=1)
    size_cd: str = Field(..., min_length=1)
    weight: float = Field(..., gt=0)
    reason_cd: str = Field(..., min_length=1)
    remark: str | None = None
    return_confirmed: bool = False


class AuctionFinalizeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trade_dt: str = Field(..., min_length=10, max_length=10, pattern=r"^\d{4}-\d{2}-\d{2}$")
    selected_candidates: list[AuctionFinalizeSelectedIn] = Field(..., min_length=1)
    discrepancies: list[AuctionFinalizeDiscrepancyIn] = Field(default_factory=list)


class AuctionFinalizeOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shipment_id: str
    status: str
    sales_no: str
    match_trade_dt: str
    total_sales_qty: float
    gross_sales_amount: float
    matched_count: int
    discrepancy_count: int


class AuctionShipmentListPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AuctionShipmentListItemOut]
    total: int
