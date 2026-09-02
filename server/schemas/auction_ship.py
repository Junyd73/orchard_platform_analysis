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


class AuctionShipmentListPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AuctionShipmentListItemOut]
    total: int
