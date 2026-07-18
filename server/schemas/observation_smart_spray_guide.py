# -*- coding: utf-8 -*-
"""스마트 방제 가이드 REST DTO — 읽기 전용 통합 응답.

Null 규칙:
  문자 → \"\" / 숫자 → 0 / 날짜 → null / 리스트 → [] / 객체 → null
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class SmartSprayGuideObservationDto(BaseModel):
    obs_id: str = ""
    farm_cd: str = ""
    obs_title: str = ""
    obs_dt: str | None = None
    ai_status: str = ""
    site_id: str = ""
    site_nm: str = ""


class SmartSprayGuideCandidateDto(BaseModel):
    analysis_id: str = ""
    candidate_seq: int = 0
    name_ko: str = ""
    confirmed_name: str = ""
    category: str = ""
    confidence: float = 0.0


class SmartSprayGuideItemDto(BaseModel):
    """①보유·②추천·③사용기준에 공통으로 쓰는 농약 1건."""

    rank: int = 0
    snapshot_id: str = ""
    pesticide_name: str = ""
    brand_name: str = ""
    active_ingredient: str = ""
    crop_name: str = ""
    disease_name: str = ""
    purpose: str = ""
    pesti_code: str = ""
    item_id: int = 0
    info_id: int = 0
    stock_qty: int = 0
    stock_unit: str = "낱개"
    has_stock: bool = False
    last_used_date: str | None = None
    dilution: str = ""
    phi: str = Field(default="", description="수확 전 안전사용기간")
    max_use_count: str = ""
    usage_method: str = ""
    toxicity: str = ""
    from_psis: bool = False
    from_stock: bool = False
    psis_registered: bool = False
    information_available: bool = False
    match_level: str = Field(
        default="NOT_FOUND", description="MATCH | PARTIAL | NOT_FOUND"
    )
    match_key: str = ""


class ObservationSmartSprayGuideResponse(BaseModel):
    success: bool
    guide_status: str = Field(
        description="READY | PARTIAL | EMPTY | NO_CANDIDATE | ERROR"
    )
    farm_cd: str = ""
    obs_id: str = ""
    observation: SmartSprayGuideObservationDto | None = None
    confirmed_candidate: SmartSprayGuideCandidateDto | None = None
    psis_status: str = Field(
        default="NONE", description="CACHED | EMPTY | NONE"
    )
    crop_name: str = ""
    disease_name: str = ""
    items: list[SmartSprayGuideItemDto] = Field(default_factory=list)
    error: str = ""
    error_code: str = ""
