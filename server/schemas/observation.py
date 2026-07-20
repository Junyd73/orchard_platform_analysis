# -*- coding: utf-8 -*-
"""관찰(생육관찰) 스키마 — 조회 + 생명주기."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ObservationSummary(BaseModel):
    """SCR-001 요약 카드 (COMPLETED+ACTIVE만)."""

    today_count: int = Field(ge=0, description="오늘 관찰 건수")
    pest_count: int = Field(
        ge=0,
        description="병해충(OB010400) 건수",
    )
    danger_count: int = Field(
        ge=0,
        description="주의·위험(OS010300/OS010400) ∧ 미완료 — PC caution_danger",
    )
    fruit_count: int = Field(ge=0, description="과실/열매(OB010200) 건수")
    ai_pending_count: int = Field(ge=0, description="AI 대기·분석 건수")
    as_of_date: str = Field(description="집계 기준일 YYYY-MM-DD")


class ObservationListItem(BaseModel):
    """SCR-001 관찰 카드용 목록 항목."""

    obs_id: str
    farm_cd: str
    obs_dt: str
    obs_title: str | None = None
    target_type_cd: str
    target_type_nm: str
    obs_type_cd: str
    obs_type_nm: str
    site_id: str | None = None
    site_nm: str | None = None
    location_text: str
    severity_cd: str
    severity_nm: str
    progress_status_cd: str
    progress_status_nm: str
    ai_status: str
    followup_dt: str | None = None
    has_photo: bool = False
    thumb_path: str | None = None
    thumb_url: str | None = None
    thumb_photo_id: str | None = None
    observation_status: str = "COMPLETED"
    record_status: str = "ACTIVE"
    # AI 확정/후보 병해충명 (없으면 null)
    ai_pest_nm: str | None = None


class ObservationDraftItem(BaseModel):
    """작성 중(DRAFT) 관찰."""

    obs_id: str
    farm_cd: str
    obs_dt: str
    obs_title: str | None = None
    target_type_cd: str
    target_type_nm: str
    site_id: str | None = None
    site_nm: str | None = None
    location_text: str
    photo_count: int = 0
    mod_dt: str | None = None
    observation_status: str = "DRAFT"
    record_status: str = "ACTIVE"


class ObservationBasicCreateRequest(BaseModel):
    """SCR-002 기본정보 임시 저장(신규) → DRAFT."""

    obs_dt: str = Field(..., description="관찰일 YYYY-MM-DD")
    target_type_cd: str = Field(..., description="OB010400|OB010200")
    site_id: str = Field(..., min_length=1)
    obs_title: str | None = None
    obs_content: str | None = None
    parent_obs_id: str | None = Field(
        default=None, description="후속 관찰 시 직전 obs_id"
    )
    followup_dt: str | None = Field(
        default=None, description="재관찰 예정일 YYYY-MM-DD"
    )
    zone_nm: str | None = None
    row_no: str | None = None
    tree_no: str | None = None
    branch_no: str | None = None
    sample_no: str | None = None
    severity_cd: str | None = Field(
        default=None,
        description="위험도 OS010100~OS010400 (미지정 시 정상)",
    )


class ObservationBasicUpdateRequest(BaseModel):
    """기본정보 수정 (DRAFT/COMPLETED, ACTIVE)."""

    obs_dt: str = Field(..., description="관찰일 YYYY-MM-DD")
    target_type_cd: str = Field(..., description="OB010400|OB010200")
    site_id: str = Field(..., min_length=1)
    obs_title: str | None = None
    obs_content: str | None = None
    severity_cd: str | None = Field(
        default=None,
        description="위험도 OS010100~OS010400 (미지정 시 기존값 유지)",
    )

class ObservationSoftDeleteRequest(BaseModel):
    delete_reason: str | None = None


class ObservationDetail(BaseModel):
    """관찰 단건 (초안 복원·상세·사진 진입)."""

    obs_id: str
    farm_cd: str
    obs_dt: str
    target_type_cd: str
    target_type_nm: str
    obs_type_cd: str
    obs_type_nm: str
    site_id: str | None = None
    site_nm: str | None = None
    severity_cd: str
    severity_nm: str
    progress_status_cd: str
    progress_status_nm: str
    obs_title: str | None = None
    obs_content: str | None = None
    ai_status: str
    use_yn: str = "Y"
    observation_status: str = "DRAFT"
    record_status: str = "ACTIVE"
    reg_id: str | None = None
    reg_dt: str | None = None
    mod_id: str | None = None
    mod_dt: str | None = None
    completed_at: str | None = None
    completed_by: str | None = None
    photo_count: int = 0
    can_delete: bool = False
    zone_nm: str | None = None
    row_no: str | None = None
    tree_no: str | None = None
    branch_no: str | None = None
    sample_no: str | None = None
    root_obs_id: str | None = None
    parent_obs_id: str | None = None
    followup_dt: str | None = None


class ObservationSaveResponse(BaseModel):
    obs_id: str
    farm_cd: str
    created: bool
    message: str
    observation_status: str | None = None
