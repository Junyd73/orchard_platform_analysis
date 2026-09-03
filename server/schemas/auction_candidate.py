# -*- coding: utf-8 -*-
"""경락 후보 조회 DEC-037 Stage B API 스키마."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AuctionCandidateItemOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: str
    trade_dt: str
    market_cd: str
    market_name: str
    corporation_name: str
    origin_name: str | None = None
    variety_name: str | None = None
    grade_cd: str | None = None
    grade_name: str | None = None
    size_name: str | None = None
    spec_name: str | None = None
    spec_kg: float | None = None
    qty: int
    unit_price: int
    amount: int
    auction_time: str | None = None
    requires_grade_input: bool
    source_key: str = Field(..., min_length=1)


class AuctionCandidateListOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shipment_id: str
    trade_dt: str
    source_used: str
    items: list[AuctionCandidateItemOut]
