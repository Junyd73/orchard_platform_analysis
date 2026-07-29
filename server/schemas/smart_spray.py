# -*- coding: utf-8 -*-
"""SPR-001 스마트방제·발병여건 API 스키마."""

from __future__ import annotations

from pydantic import BaseModel, Field


class OutbreakParamItem(BaseModel):
    farm_cd: str | None = None
    user_id: str | None = None
    pest_nm: str
    param_key: str
    param_value: str
    source: str = "system"
    param_op: str | None = None
    display_value: str | None = None
    example: str | None = None
    compare_enabled: bool = False


class OutbreakParamListResponse(BaseModel):
    success: bool = True
    scope: str
    items: list[OutbreakParamItem] = Field(default_factory=list)


class OutbreakParamUpsertRequest(BaseModel):
    pest_nm: str
    param_key: str
    param_value: str
    as_farm_default: bool = False


class OutbreakParamDeleteRequest(BaseModel):
    pest_nm: str
    param_key: str
    as_farm_default: bool = False


class OutbreakParamMutationResponse(BaseModel):
    success: bool = True
    item: OutbreakParamItem | None = None
    message: str = ""


class SmartSprayCta(BaseModel):
    kind: str
    label: str
    route: str


class SmartSprayBriefingCard(BaseModel):
    pest_nm: str
    score: int = 0
    risk_level: str = ""
    reasons: list[str] = Field(default_factory=list)
    photo_url: str | None = None
    photo_id: str | None = None
    obs_id: str | None = None
    stock_count: int = 0
    last_spray_dt: str | None = None
    last_spray_item_nm: str | None = None
    last_spray_qty: int | None = None
    efficacy_days: int | None = None
    efficacy_days_left: int | None = None
    efficacy_active: bool = False
    ctas: list[SmartSprayCta] = Field(default_factory=list)


class SmartSprayBriefingPatched(BaseModel):
    observation: bool = False
    stock: bool = False
    personal: bool = False


class SmartSprayBriefingResponse(BaseModel):
    success: bool = True
    farm_cd: str
    work_dt: str
    computed_at: str | None = None
    source: str = "snapshot"  # snapshot | fallback_build | dirty_rebuild
    patched: SmartSprayBriefingPatched = Field(
        default_factory=SmartSprayBriefingPatched
    )
    param_source_note: str = "effective (user > farm > system)"
    cards: list[SmartSprayBriefingCard] = Field(default_factory=list)
