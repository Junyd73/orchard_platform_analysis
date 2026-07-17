# -*- coding: utf-8 -*-
"""관찰 사진 API 스키마 (등록 저장과 분리)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ObservationPhotoItem(BaseModel):
    photo_id: str
    obs_id: str
    farm_cd: str
    sort_no: int
    is_representative: bool = False
    # 표시명(업무용) — 조회 시 계산. 저장 파일명과 분리
    display_nm: str
    # 원본 추적
    original_nm: str | None = None
    # 내부 저장 파일명
    stored_nm: str | None = None
    file_ext: str | None = None
    file_size: int | None = None
    width_px: int | None = None
    height_px: int | None = None
    # API 기준 상대경로 (/farms/.../thumbnail) — /api/v1 접두 없음
    thumb_url: str
    original_url: str


class ObservationPhotoListResponse(BaseModel):
    obs_id: str
    count: int = Field(ge=0)
    max_count: int = Field(ge=1)
    remaining: int = Field(ge=0)
    photos: list[ObservationPhotoItem]


class ObservationPhotoReorderRequest(BaseModel):
    photo_ids: list[str] = Field(min_length=1)


class ObservationPhotoUploadResponse(BaseModel):
    uploaded: list[ObservationPhotoItem]
    skipped: list[str] = Field(default_factory=list)
    count: int = Field(ge=0)
    max_count: int = Field(ge=1)
    remaining: int = Field(ge=0)
    message: str
