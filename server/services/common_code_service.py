# -*- coding: utf-8 -*-
"""공통코드 서비스."""

from __future__ import annotations

from app.repository.interfaces.common_code_repository import CommonCodeRepository
from app.schemas.common_code import CommonCodeItem


class CommonCodeService:
    def __init__(self, repo: CommonCodeRepository):
        self._repo = repo

    def list_codes(
        self,
        farm_cd: str,
        parent_cd: str,
        *,
        active_only: bool = True,
    ) -> list[CommonCodeItem]:
        return self._repo.list_codes(
            farm_cd, parent_cd, active_only=active_only
        )
