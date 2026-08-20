# -*- coding: utf-8 -*-
"""재고 증감 REST 스키마. 전표 없음."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class StockAdjustRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    wh_cd: str = Field(..., min_length=1)
    item_cd: str = Field(..., min_length=1)
    variety_cd: str = Field(..., min_length=1)
    grade_cd: str = Field(..., min_length=1)
    size_cd: str = Field(..., min_length=1)
    weight: float
    harvest_year: int
    storage_dt: str = Field(..., min_length=8)
    io_type: str = Field(..., min_length=2)
    qty: float = Field(..., gt=0)
    reason_cd: str = Field(..., min_length=1)


class StockAdjustResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    stock_seq: int
    io_type: str
    qty: float
    reason_cd: str
