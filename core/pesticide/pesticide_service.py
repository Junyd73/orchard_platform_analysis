# -*- coding: utf-8 -*-
"""관찰일지 공식 등록 농약정보 조회 서비스(캐시·스냅샷)."""

from __future__ import annotations

import datetime
import os
from typing import Any

from core.pesticide.pesticide_provider import (
    PesticideProvider,
    PesticideSearchRequest,
    PesticideSearchResponse,
)
from core.pesticide.psis_provider import ENV_API_KEY, PsisProvider

CACHE_HOURS = 24


def is_psis_available() -> bool:
    return bool((os.environ.get(ENV_API_KEY) or "").strip())


def _parse_dt(raw: str | None) -> datetime.datetime | None:
    s = str(raw or "").strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(s[:19], fmt)
        except ValueError:
            continue
    return None


def is_cache_fresh(fetched_at: str | None, hours: int = CACHE_HOURS) -> bool:
    dt = _parse_dt(fetched_at)
    if not dt:
        return False
    return datetime.datetime.now() - dt <= datetime.timedelta(hours=hours)


class ObservationPesticideService:
    def __init__(self, provider: PesticideProvider | None = None):
        self.provider = provider or PsisProvider()

    def is_available(self) -> bool:
        return self.provider.is_configured()

    def config_hint(self) -> str:
        return self.provider.config_hint()

    def search_official(
        self,
        crop_name: str,
        disease_name: str,
        *,
        similar: bool = False,
    ) -> PesticideSearchResponse:
        return self.provider.search(
            PesticideSearchRequest(
                crop_name=crop_name,
                disease_name=disease_name,
                similar=similar,
            )
        )

    def search_with_cache_policy(
        self,
        db,
        farm_cd: str,
        obs_id: str,
        crop_name: str,
        disease_name: str,
        *,
        force_refresh: bool = False,
        allow_similar: bool = False,
        user_id: str = "",
        analysis_id: str | None = None,
    ) -> dict[str, Any]:
        """캐시(스냅샷) → 정확검색 → (동의 시)유사검색. DB 저장은 호출자가 수행해도 됨.

        반환 키: ok, items, match_type, from_cache, fetched_at, error_code, error_message, saved
        """
        from core.observation_stage3 import (
            latest_pesticide_snapshot_group,
            replace_pesticide_snapshots,
        )

        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cached, fetched_at = latest_pesticide_snapshot_group(
            db, farm_cd, obs_id, crop_name, disease_name
        )
        if cached and not force_refresh and is_cache_fresh(fetched_at):
            return {
                "ok": True,
                "items": cached,
                "match_type": cached[0].get("match_type") or "EXACT",
                "from_cache": True,
                "fetched_at": fetched_at,
                "error_code": "",
                "error_message": "",
                "saved": False,
                "label": "과거 조회자료(캐시)",
            }

        if not self.is_available():
            if cached:
                return {
                    "ok": True,
                    "items": cached,
                    "match_type": cached[0].get("match_type") or "EXACT",
                    "from_cache": True,
                    "fetched_at": fetched_at,
                    "error_code": "",
                    "error_message": "",
                    "saved": False,
                    "label": "과거 조회자료(오프라인)",
                }
            return {
                "ok": False,
                "items": [],
                "match_type": "EXACT",
                "from_cache": False,
                "fetched_at": None,
                "error_code": "NO_KEY",
                "error_message": self.config_hint(),
                "saved": False,
                "label": "",
            }

        resp = self.search_official(crop_name, disease_name, similar=False)
        match_type = "EXACT"
        if resp.ok and not resp.items and allow_similar:
            resp = self.search_official(crop_name, disease_name, similar=True)
            match_type = "SIMILAR"

        if not resp.ok:
            if cached:
                return {
                    "ok": True,
                    "items": cached,
                    "match_type": cached[0].get("match_type") or "EXACT",
                    "from_cache": True,
                    "fetched_at": fetched_at,
                    "error_code": resp.error_code,
                    "error_message": resp.error_message,
                    "saved": False,
                    "label": "과거 조회자료(오프라인)",
                }
            return {
                "ok": False,
                "items": [],
                "match_type": match_type,
                "from_cache": False,
                "fetched_at": None,
                "error_code": resp.error_code,
                "error_message": resp.error_message,
                "saved": False,
                "label": "",
            }

        items = list(resp.items or [])
        for it in items:
            it["fetched_at"] = now
            it["match_type"] = match_type

        saved = False
        if user_id and items:
            sok, _smsg, _ids = replace_pesticide_snapshots(
                db,
                farm_cd,
                obs_id,
                analysis_id,
                crop_name,
                disease_name,
                match_type,
                items,
                user_id,
            )
            saved = bool(sok)

        return {
            "ok": True,
            "items": items,
            "match_type": match_type,
            "from_cache": False,
            "fetched_at": now,
            "error_code": "",
            "error_message": "",
            "saved": saved,
            "label": "공식 등록정보 조회 결과"
            + (" (유사명 검색)" if match_type == "SIMILAR" else ""),
        }
