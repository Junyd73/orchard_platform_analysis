# -*- coding: utf-8 -*-
"""경매 출하 lookup API 스키마 — DEC-036-C1."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AuctionMarketOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    market_cd: str
    market_name: str


class AuctionMarketListOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AuctionMarketOut]


class AuctionCorporationOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    corporation_name: str
    custm_id: str | None = None


class AuctionCorporationListOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AuctionCorporationOut]
