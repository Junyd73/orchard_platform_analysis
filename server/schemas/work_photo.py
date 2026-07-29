# -*- coding: utf-8 -*-
"""작업 결과 사진 API 스키마."""

from __future__ import annotations

from pydantic import BaseModel, Field


class WorkPhotoItem(BaseModel):
    photo_id: str
    work_id: str
    farm_cd: str
    sort_no: int
    display_nm: str
    original_nm: str | None = None
    stored_nm: str | None = None
    file_ext: str | None = None
    file_size: int | None = None
    width_px: int | None = None
    height_px: int | None = None
    thumb_url: str
    original_url: str


class WorkPhotoListResponse(BaseModel):
    work_id: str
    count: int = Field(ge=0)
    max_count: int = Field(ge=1)
    remaining: int = Field(ge=0)
    photos: list[WorkPhotoItem]


class WorkPhotoUploadResponse(BaseModel):
    uploaded: list[WorkPhotoItem]
    skipped: list[str] = Field(default_factory=list)
    count: int = Field(ge=0)
    max_count: int = Field(ge=1)
    remaining: int = Field(ge=0)
    message: str
    success: bool = True
    photo_id: str | None = None
    farm_cd: str | None = None
    work_id: str | None = None
    file_name: str | None = None
    file_path: str | None = None
    thumbnail_path: str | None = None
    file_size: int | None = None
    width: int | None = None
    height: int | None = None
    created_by: str | None = None
    error: str | None = None
    error_code: str | None = None
