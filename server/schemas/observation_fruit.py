# -*- coding: utf-8 -*-
"""과실 측정·추적 REST DTO — Stage2 어댑터."""

from __future__ import annotations

from pydantic import BaseModel, Field


class FruitMeasurementDto(BaseModel):
    """t_observation_fruit_measurement 1행."""

    farm_cd: str = ""
    obs_id: str = ""
    width_mm: float | None = None
    height_mm: float | None = None
    circumference_mm: float | None = None
    estimated_weight_g: float | None = None
    shape_cd: str | None = None
    skin_color_cd: str | None = None
    asymmetry_level: int | None = None
    spot_yn: str = "N"
    wound_yn: str = "N"
    crack_yn: str = "N"
    russet_yn: str = "N"
    sunburn_yn: str = "N"
    deformity_yn: str = "N"
    stalk_status_cd: str | None = None
    calyx_status_cd: str | None = None
    fruit_rmk: str | None = None


class FruitMeasurementUpsertRequest(BaseModel):
    width_mm: float | None = None
    height_mm: float | None = None
    circumference_mm: float | None = None
    estimated_weight_g: float | None = None
    shape_cd: str | None = None
    skin_color_cd: str | None = None
    asymmetry_level: int | None = None
    spot_yn: str | None = "N"
    wound_yn: str | None = "N"
    crack_yn: str | None = "N"
    russet_yn: str | None = "N"
    sunburn_yn: str | None = "N"
    deformity_yn: str | None = "N"
    stalk_status_cd: str | None = None
    calyx_status_cd: str | None = None
    fruit_rmk: str | None = None


class FruitMeasurementResponse(BaseModel):
    success: bool
    measurement: FruitMeasurementDto | None = None
    error: str = ""
    error_code: str = ""


class ObservationTrackItemDto(BaseModel):
    """list_observation_track 1건 + 이전 대비 Δ."""

    obs_id: str
    farm_cd: str
    obs_dt: str
    root_obs_id: str | None = None
    parent_obs_id: str | None = None
    followup_dt: str | None = None
    obs_title: str | None = None
    obs_content: str | None = None
    site_id: str | None = None
    zone_nm: str | None = None
    row_no: str | None = None
    tree_no: str | None = None
    branch_no: str | None = None
    sample_no: str | None = None
    thumb_photo_id: str | None = None
    thumb_path: str | None = None
    width_mm: float | None = None
    height_mm: float | None = None
    circumference_mm: float | None = None
    estimated_weight_g: float | None = None
    shape_cd: str | None = None
    skin_color_cd: str | None = None
    fruit_rmk: str | None = None
    delta_width_mm: float | None = None
    delta_height_mm: float | None = None
    delta_circumference_mm: float | None = None
    delta_estimated_weight_g: float | None = None
    is_current: bool = False


class ObservationTrackResponse(BaseModel):
    success: bool
    root_obs_id: str = ""
    current_obs_id: str = ""
    track_count: int = 0
    followup_dt: str | None = None
    items: list[ObservationTrackItemDto] = Field(default_factory=list)
    error: str = ""
    error_code: str = ""


class FollowupUpdateRequest(BaseModel):
    followup_dt: str | None = Field(
        default=None, description="재관찰 예정일 YYYY-MM-DD (null/빈값=해제)"
    )


class FollowupUpdateResponse(BaseModel):
    success: bool
    obs_id: str = ""
    followup_dt: str | None = None
    message: str = ""
    error: str = ""
    error_code: str = ""
