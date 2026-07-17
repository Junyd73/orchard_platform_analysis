# -*- coding: utf-8 -*-
"""공통코드 API 응답 계약 (m_common_code 실제 컬럼 기준)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CommonCodeItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    farm_cd: str = Field(..., min_length=1)
    code_cd: str = Field(..., min_length=1)
    code_nm: str = Field(..., min_length=1)
    parent_cd: str | None = None
    use_yn: str | None = Field(default="Y", description="Y/N")
