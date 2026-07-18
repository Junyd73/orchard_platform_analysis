# -*- coding: utf-8 -*-
"""관찰 PSIS(공식 농약정보) 응답 DTO — 모바일·PC 공용 REST 계약."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ObservationPsisSearchRequest(BaseModel):
    """POST PSIS 조회. analysis/후보 또는 작물·병명."""

    analysis_id: str | None = None
    candidate_seq: int | None = None
    crop_name: str | None = Field(
        default=None, description="작물명(미지정 시 요청 필수 아님, 후보 경로면 필수)"
    )
    disease_name: str | None = None
    force_refresh: bool = False
    allow_similar: bool = False


class ObservationPsisCaseDto(BaseModel):
    """PSIS 공식 등록정보 1건 — 절대경로·타농장 개인정보 없음."""

    rank: int
    snapshot_id: str | None = None
    similarity: str | None = Field(
        default=None, description="match_type: EXACT | SIMILAR"
    )
    pesticide_name: str | None = None
    brand_name: str | None = None
    company_name: str | None = None
    active_ingredient: str | None = None
    crop_name: str | None = None
    disease_name: str | None = None
    purpose_name: str | None = None
    usage_method: str | None = None
    dilution: str | None = None
    preharvest_interval: str | None = None
    max_use_count: str | None = None
    toxicity: str | None = None
    fish_toxicity: str | None = None
    source_nm: str | None = None
    # 민감정보 없음 — farm_cd 는 요청 컨텍스트에만 존재


class ObservationPsisResponse(BaseModel):
    success: bool
    psis_status: str = Field(
        description="OK | CACHED | EMPTY | FAILED"
    )
    snapshot_id: str | None = None
    snapshot_ids: list[str] = Field(default_factory=list)
    analysis_id: str | None = None
    candidate_seq: int | None = None
    query_candidate: str | None = Field(
        default=None, description="조회에 사용한 확정 병해충명"
    )
    crop_name: str | None = None
    match_type: str | None = None
    from_cache: bool = False
    similar_cases: list[ObservationPsisCaseDto] = Field(default_factory=list)
    searched_at: str | None = None
    label: str | None = None
    error: str | None = None
    error_code: str | None = None


class ObservationPsisHistoryItem(BaseModel):
    snapshot_id: str
    analysis_id: str | None = None
    crop_name: str | None = None
    disease_name: str | None = None
    match_type: str | None = None
    pesticide_name: str | None = None
    brand_name: str | None = None
    fetched_at: str | None = None


class ObservationPsisHistoryResponse(BaseModel):
    success: bool
    items: list[ObservationPsisHistoryItem] = Field(default_factory=list)
    error: str | None = None
