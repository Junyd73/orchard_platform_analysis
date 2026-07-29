# -*- coding: utf-8 -*-
"""농약 재고 API 스키마 — SCR-020."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

WarnSource = Literal["item", "default"]


class PesticideStockSummaryDto(BaseModel):
    total_count: int = 0
    low_count: int = 0
    default_warn_piece_below: int = 1
    last_spray_dt: str | None = None


class PesticideStockItemDto(BaseModel):
    item_id: int
    item_nm: str
    spec_nm: str | None = None
    pest_category_nm: str | None = None
    qty_piece: int = 0
    warn_piece_below: int | None = None
    warn_threshold: int = 1
    warn_source: WarnSource = "default"
    is_low: bool = False
    info_id: int | None = None
    info_pesticide_nm: str | None = None
    ingredient_nm: str | None = None
    pest_target_nm: str | None = None


class PesticideStockListResponse(BaseModel):
    summary: PesticideStockSummaryDto
    items: list[PesticideStockItemDto] = Field(default_factory=list)


class PesticideStockItemDetailDto(PesticideStockItemDto):
    rmk: str | None = None


class PesticideUsageRowDto(BaseModel):
    use_id: int
    use_line_id: int
    use_dt: str
    use_qty: int = 0
    purpose_nm: str | None = None
    work_id: str | None = None
    worker_nm: str | None = None
    site_nm: str | None = None
    item_nm: str | None = None


class PesticideStockDetailResponse(BaseModel):
    item: PesticideStockItemDetailDto
    recent_usage: list[PesticideUsageRowDto] = Field(default_factory=list)


class PesticideUsageListResponse(BaseModel):
    item_id: int
    total: int = 0
    offset: int = 0
    limit: int = 20
    rows: list[PesticideUsageRowDto] = Field(default_factory=list)


class PesticideRecentUsageLineDto(BaseModel):
    item_nm: str
    use_qty: int = 0
    unit: str = "개"


class PesticideRecentUsageDayDto(BaseModel):
    use_dt: str
    lines: list[PesticideRecentUsageLineDto] = Field(default_factory=list)


class PesticideRecentUsageResponse(BaseModel):
    last_spray_dt: str | None = None
    days: list[PesticideRecentUsageDayDto] = Field(default_factory=list)
