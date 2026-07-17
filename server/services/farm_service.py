# -*- coding: utf-8 -*-
"""농장·필지 서비스."""

from __future__ import annotations

from app.repository.interfaces.farm_repository import FarmRepository
from app.schemas.farm import FarmDetail, FarmSiteDetail, FarmSiteSummary


class FarmService:
    def __init__(self, repo: FarmRepository):
        self._repo = repo

    def get_farm(self, farm_cd: str) -> FarmDetail:
        return self._repo.get_farm(farm_cd)

    def list_sites(
        self, farm_cd: str, *, active_only: bool = True
    ) -> list[FarmSiteSummary]:
        return self._repo.list_sites(farm_cd, active_only=active_only)

    def get_site(self, farm_cd: str, site_id: str) -> FarmSiteDetail:
        return self._repo.get_site(farm_cd, site_id)
