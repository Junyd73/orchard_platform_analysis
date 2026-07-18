# -*- coding: utf-8 -*-
"""스마트 방제 가이드 REST 어댑터 — ApplicationService 만 호출."""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

from app.core.exceptions import EntityNotFoundError
from app.db.sqlite import get_sqlite_write_connection
from app.repository.interfaces.observation_photo_repository import (
    ObservationPhotoRepository,
)
from app.schemas.observation_smart_spray_guide import (
    ObservationSmartSprayGuideResponse,
    SmartSprayGuideCandidateDto,
    SmartSprayGuideItemDto,
    SmartSprayGuideObservationDto,
)
from app.services.observation_ai_db_bridge import ServerDbBridge

_logger = logging.getLogger(__name__)


def _ensure_repo_root_on_path() -> Path:
    root = Path(__file__).resolve().parents[3]
    root_s = str(root)
    if root_s not in sys.path:
        sys.path.append(root_s)
    return root


def _import_guide_app():
    _ensure_repo_root_on_path()
    from core.ai.observation_smart_spray_guide_application_service import (  # noqa: WPS433
        ObservationSmartSprayGuideApplicationService,
    )

    return ObservationSmartSprayGuideApplicationService


def _s(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _i(value, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _f(value, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


class ObservationSmartSprayGuideApiService:
    def __init__(
        self,
        *,
        db_path: Path | str,
        photo_repo: ObservationPhotoRepository,
    ):
        self._db_path = Path(db_path)
        self._photo_repo = photo_repo

    def _ensure_farm_and_obs(self, farm_cd: str, obs_id: str) -> dict:
        farm = _s(farm_cd)
        oid = _s(obs_id)
        if not farm or not self._photo_repo.farm_exists(farm):
            raise EntityNotFoundError("Farm not found")
        if not oid:
            raise EntityNotFoundError("Observation not found")
        obs = self._photo_repo.get_observation(farm, oid)
        if not obs:
            raise EntityNotFoundError("Observation not found")
        return obs

    def _map_item(self, it: dict) -> SmartSprayGuideItemDto:
        return SmartSprayGuideItemDto(
            rank=_i(it.get("rank"), 0),
            snapshot_id=_s(it.get("snapshot_id")),
            pesticide_name=_s(it.get("pesticide_name")),
            brand_name=_s(it.get("brand_name")),
            active_ingredient=_s(it.get("active_ingredient")),
            crop_name=_s(it.get("crop_name")),
            disease_name=_s(it.get("disease_name")),
            purpose=_s(it.get("purpose")),
            pesti_code=_s(it.get("pesti_code")),
            item_id=_i(it.get("item_id"), 0),
            info_id=_i(it.get("info_id"), 0),
            stock_qty=_i(it.get("stock_qty"), 0),
            stock_unit=_s(it.get("stock_unit")) or "낱개",
            has_stock=bool(it.get("has_stock")),
            last_used_date=(
                _s(it.get("last_used_date"))[:10]
                if _s(it.get("last_used_date"))
                else None
            ),
            dilution=_s(it.get("dilution")),
            phi=_s(it.get("phi")),
            max_use_count=_s(it.get("max_use_count")),
            usage_method=_s(it.get("usage_method")),
            toxicity=_s(it.get("toxicity")),
            from_psis=bool(it.get("from_psis")),
            from_stock=bool(it.get("from_stock")),
            psis_registered=bool(it.get("psis_registered")),
            information_available=bool(it.get("information_available")),
            match_level=_s(it.get("match_level")) or "NOT_FOUND",
            match_key=_s(it.get("match_key")),
        )

    def _to_response(self, payload: dict) -> ObservationSmartSprayGuideResponse:
        ok = bool(payload.get("ok"))
        obs_raw = payload.get("observation")
        cand_raw = payload.get("confirmed_candidate")
        observation = None
        if isinstance(obs_raw, dict) and _s(obs_raw.get("obs_id")):
            observation = SmartSprayGuideObservationDto(
                obs_id=_s(obs_raw.get("obs_id")),
                farm_cd=_s(obs_raw.get("farm_cd") or payload.get("farm_cd")),
                obs_title=_s(obs_raw.get("obs_title")),
                obs_dt=(
                    _s(obs_raw.get("obs_dt"))[:10]
                    if _s(obs_raw.get("obs_dt"))
                    else None
                ),
                ai_status=_s(obs_raw.get("ai_status")),
                site_id=_s(obs_raw.get("site_id")),
                site_nm=_s(obs_raw.get("site_nm")),
            )
        confirmed = None
        if isinstance(cand_raw, dict) and (
            _s(cand_raw.get("analysis_id")) or _s(cand_raw.get("confirmed_name"))
        ):
            confirmed = SmartSprayGuideCandidateDto(
                analysis_id=_s(cand_raw.get("analysis_id")),
                candidate_seq=_i(cand_raw.get("candidate_seq"), 0),
                name_ko=_s(cand_raw.get("name_ko")),
                confirmed_name=_s(cand_raw.get("confirmed_name")),
                category=_s(cand_raw.get("category")),
                confidence=_f(cand_raw.get("confidence"), 0.0),
            )
        return ObservationSmartSprayGuideResponse(
            success=ok,
            guide_status=_s(payload.get("guide_status")) or "ERROR",
            farm_cd=_s(payload.get("farm_cd")),
            obs_id=_s(payload.get("obs_id")),
            observation=observation,
            confirmed_candidate=confirmed,
            psis_status=_s(payload.get("psis_status")) or "NONE",
            crop_name=_s(payload.get("crop_name")),
            disease_name=_s(payload.get("disease_name")),
            items=[self._map_item(x) for x in (payload.get("items") or [])],
            error="" if ok else (_s(payload.get("error_message")) or "조회에 실패했습니다."),
            error_code="" if ok else _s(payload.get("error_code")),
        )

    def get_guide(
        self, farm_cd: str, obs_id: str
    ) -> ObservationSmartSprayGuideResponse:
        t0 = time.perf_counter()
        _logger.debug(
            "[SMART_GUIDE] API START farm=%s obs=%s",
            _s(farm_cd) or "-",
            _s(obs_id) or "-",
        )
        obs = self._ensure_farm_and_obs(farm_cd, obs_id)
        farm = _s(obs.get("farm_cd") or farm_cd)
        oid = _s(obs.get("obs_id") or obs_id)
        AppSvc = _import_guide_app()
        with get_sqlite_write_connection(self._db_path) as conn:
            db = ServerDbBridge(conn)
            payload = AppSvc().build_guide(db, farm_cd=farm, obs_id=oid)
            resp = self._to_response(payload)
        total_ms = int((time.perf_counter() - t0) * 1000)
        _logger.info(
            "[SMART_GUIDE] API TOTAL %d ms farm=%s obs=%s status=%s",
            total_ms,
            farm or "-",
            oid or "-",
            resp.guide_status,
        )
        return resp
