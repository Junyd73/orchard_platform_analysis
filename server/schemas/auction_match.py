# -*- coding: utf-8 -*-
"""확정 경락 매칭 READ 스키마 — R26-F."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AuctionConfirmedMatchItemOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    match_seq: int
    shipment_id: str
    source_key: str
    trade_dt: str
    market_cd: str | None = None
    market_name: str | None = None
    corporation_name: str | None = None
    origin_name: str | None = None
    variety_name: str | None = None
    spec_text: str | None = None
    auction_box_qty: int = 0
    auction_weight_kg: float | None = None
    auction_price: float | None = None
    auction_amount: float = 0
    auction_time: str | None = None
    match_status: str = Field(default="confirmed")


class AuctionConfirmedMatchListOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    farm_cd: str
    trade_dt: str
    total_count: int
    items: list[AuctionConfirmedMatchItemOut]
