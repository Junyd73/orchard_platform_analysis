# -*- coding: utf-8 -*-
"""관찰 AI 후보 확정 REST DTO."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ObservationCandidateConfirmRequest(BaseModel):
    analysis_id: str = Field(..., min_length=1)
    candidate_seq: int = Field(..., ge=1)
    confirmed_name: str | None = Field(
        default=None,
        description="미지정 시 후보 name_ko 사용",
    )
    severity_cd: str = Field(
        ...,
        min_length=1,
        description="사용자가 확인한 위험도 OS010100~OS010400",
    )


class ObservationCandidateConfirmResponse(BaseModel):
    success: bool
    analysis_id: str | None = None
    candidate_seq: int | None = None
    confirmed_name: str | None = None
    confirmed_by: str | None = None
    confirmed_at: str | None = None
    ai_status: str | None = None
    error: str | None = None
    error_code: str | None = None
