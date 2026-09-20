# -*- coding: utf-8 -*-
"""경매조회 READ API 스키마 — R26-B."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class MarketAuctionSummaryOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    auction_box_qty: str
    auction_weight_kg: str
    auction_amount: int


class MarketAuctionItemOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trade_date: str
    auction_time: str | None = None
    market_cd: str
    market_name: str | None = None
    corporation_cd: str | None = None
    corporation_name: str | None = None
    origin_cd: str | None = None
    origin_name: str | None = None
    variety_cd: str | None = None
    variety_name: str | None = None
    unit_qty: str | None = None
    unit_nm: str | None = None
    spec_text: str | None = None
    auction_box_qty: str | None = None
    auction_weight_kg: str | None = None
    auction_price: int | None = None
    auction_amount: int = 0


class MarketAuctionListOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trade_date: str
    fetched_at: str
    cache_hit: bool = False
    stale: bool = False
    market_cd: str
    market_name: str | None = None
    total_count: int = 0
    page: int = 1
    page_size: int = 50
    has_more: bool = False
    summary: MarketAuctionSummaryOut
    items: list[MarketAuctionItemOut] = Field(default_factory=list)
