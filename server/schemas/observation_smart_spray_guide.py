# -*- coding: utf-8 -*-
"""스마트 방제 가이드 REST DTO — 읽기 전용 통합 응답."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SmartSprayGuideObservationDto(BaseModel):
    obs_id: str
    farm_cd: str
    obs_title: str | None = None
    obs_dt: str | None = None
    ai_status: str | None = None
    site_id: str | None = None
    site_nm: str | None = None


class SmartSprayGuideCandidateDto(BaseModel):
    analysis_id: str | None = None
    candidate_seq: int | None = None
    name_ko: str | None = None
    confirmed_name: str | None = None
    category: str | None = None
    confidence: float | None = None


class SmartSprayGuideItemDto(BaseModel):
    """①보유·②추천·③사용기준에 공통으로 쓰는 농약 1건."""

    rank: int
    snapshot_id: str | None = None
    pesticide_name: str | None = None
    brand_name: str | None = None
    active_ingredient: str | None = None
    crop_name: str | None = None
    disease_name: str | None = None
    purpose: str | None = None
    pesti_code: str | None = None
    item_id: int | None = None
    info_id: int | None = None
    stock_qty: int = 0
    stock_unit: str | None = Field(default="낱개")
    has_stock: bool = False
    last_used_date: str | None = None
    dilution: str | None = None
    phi: str | None = Field(default=None, description="수확 전 안전사용기간")
    max_use_count: str | None = None
    usage_method: str | None = None
    toxicity: str | None = None
    from_psis: bool = False
    from_stock: bool = False
    psis_registered: bool = False
    information_available: bool = False
    match_level: str | None = Field(
        default=None, description="MATCH | PARTIAL | NOT_FOUND"
    )
    match_key: str | None = None


class ObservationSmartSprayGuideResponse(BaseModel):
    success: bool
    guide_status: str = Field(
        description="READY | EMPTY | NO_CANDIDATE | ERROR"
    )
    farm_cd: str | None = None
    obs_id: str | None = None
    observation: SmartSprayGuideObservationDto | None = None
    confirmed_candidate: SmartSprayGuideCandidateDto | None = None
    psis_status: str = Field(
        default="NONE", description="CACHED | EMPTY | NONE"
    )
    crop_name: str | None = None
    disease_name: str | None = None
    items: list[SmartSprayGuideItemDto] = Field(default_factory=list)
    error: str | None = None
    error_code: str | None = None
