# -*- coding: utf-8 -*-
"""관찰 AI 분석 응답 DTO — 모바일·PC 공용 REST 계약."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ObservationAiAnalyzeRequest(BaseModel):
    """POST 분석 요청. 사진은 서버에 이미 업로드된 건만 사용한다."""

    photo_ids: list[str] | None = Field(
        default=None,
        description="분석 대상 photo_id (미지정 시 정렬순 최대 3장)",
    )
    crop_hint: str = Field(default="", description="작물 힌트(선택)")
    consent: bool = Field(
        ...,
        description="외부 AI 전송 동의(클라이언트에서 고지 후 true)",
    )


class ObservationAiCandidateDto(BaseModel):
    candidate_seq: int
    category: str | None = None
    name_ko: str | None = None
    scientific_name: str | None = None
    confidence: float | None = None
    visual_evidence: list[str] = Field(default_factory=list)
    differential_reason: str | None = None
    urgency: str | None = None
    selected_yn: str | None = None
    confirmed_name: str | None = None


class ObservationAiPhotoDto(BaseModel):
    photo_id: str


class ObservationAiAnalysisResponse(BaseModel):
    """최신 분석·POST 결과 공용 응답."""

    success: bool
    ai_status: str
    analysis_id: str | None = None
    summary: str | None = None
    candidates: list[ObservationAiCandidateDto] = Field(default_factory=list)
    photos: list[ObservationAiPhotoDto] = Field(default_factory=list)
    confidence: float | None = None
    analyzed_at: str | None = None
    error: str | None = None
    error_code: str | None = None
    # 부가 메타(모바일 UX·디버그, 스키마 비침해)
    analysis_status: str | None = None
    review_required: bool = False
    image_quality: str | None = None
    analysis_possible: bool | None = None


class ObservationAiHistoryItem(BaseModel):
    analysis_id: str
    status: str | None = None
    image_quality: str | None = None
    analysis_possible: bool | None = None
    overall_summary: str | None = None
    model_nm: str | None = None
    analyzed_at: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    input_photo_count: int | None = None


class ObservationAiHistoryResponse(BaseModel):
    success: bool
    ai_status: str
    items: list[ObservationAiHistoryItem] = Field(default_factory=list)
    error: str | None = None
