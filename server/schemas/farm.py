# -*- coding: utf-8 -*-
"""농장·필지 API 응답 계약 (실제 SQLite 컬럼 기준).

감사 식별자(reg_id/mod_id)·비밀번호는 포함하지 않는다.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class FarmSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    farm_cd: str = Field(..., min_length=1, description="농장코드 PK")
    farm_nm: str | None = None


class FarmDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    farm_cd: str = Field(..., min_length=1)
    farm_nm: str | None = None
    owner_nm: str | None = None
    address: str | None = None
    lat: float | None = None
    lon: float | None = None
    nx: int | None = None
    ny: int | None = None
    reg_dt: str | None = None


class FarmSiteSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    site_id: str = Field(..., min_length=1, description="필지ID TEXT PK (예: SITE01)")
    site_nm: str | None = None
    use_yn: str | None = Field(default=None, description="Y/N")


class FarmSiteDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    site_id: str = Field(..., min_length=1)
    farm_cd: str = Field(..., min_length=1)
    site_nm: str | None = None
    use_yn: str | None = None
    reg_dt: str | None = None
    mod_dt: str | None = None
