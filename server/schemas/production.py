# -*- coding: utf-8 -*-
"""생산확정 REST 스키마."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ProductionLineIn(BaseModel):
    grade_cd: str
    size_cd: str
    qty: int = Field(ge=0)
    # line별 포장중량 (> 0이면 pack_weight 폴백보다 우선)
    weight: float = 0.0


class RawStockConsumptionIn(BaseModel):
    wh_cd: str
    variety_cd: str
    size_cd: str
    weight: float
    harvest_year: int
    storage_dt: str
    qty: int = Field(ge=1, description="사용 통수, 1 이상")


class HarvestConsumptionIn(BaseModel):
    work_id: str
    qty: int = Field(ge=1, description="사용 상자 수, 1 이상")


class ProductionConfirmRequest(BaseModel):
    prod_type: str = Field(description="PACK | PROCESS")
    input_source: str = Field(description="HARVEST | RAW_STOCK")
    variety_cd: str
    wh_cd: str = "WH01"
    pack_weight: float = 0
    lines: list[ProductionLineIn] = Field(default_factory=list)
    raw_consumptions: list[RawStockConsumptionIn] = Field(default_factory=list)
    harvest_consumptions: list[HarvestConsumptionIn] = Field(default_factory=list)
    work_ids: list[str] = Field(default_factory=list)
    harvest_work_id: str | None = None
    juice_qty: int = 0
    juice_grade_cd: str = "NONE"
    juice_item_cd: str = "FR010202"


class ProductionPrefillLineOut(BaseModel):
    item_cd: str
    variety_cd: str
    grade_cd: str
    size_cd: str
    weight: float
    qty: float
    work_id: str | None = None
    harvest_year: int = 0
    wh_cd: str = "WH01"
    item_nm: str = ""


class ProductionConfirmResponse(BaseModel):
    ok: bool = True
    prefill_lines: list[ProductionPrefillLineOut] = Field(default_factory=list)


class HarvestRecordOut(BaseModel):
    work_id: str
    work_dt: str
    variety_cd: str
    variety_nm: str = ""
    harvest_container_qty: int
    harvest_year: int = 0
    consumed_container_qty: int = 0
    remaining_container_qty: int = 0


class RawStockItemOut(BaseModel):
    wh_cd: str
    variety_cd: str
    variety_nm: str = ""
    size_cd: str
    size_nm: str = ""
    weight: float
    harvest_year: int
    storage_dt: str
    available_qty: int
