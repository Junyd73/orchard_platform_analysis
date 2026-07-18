# -*- coding: utf-8 -*-
"""스마트 방제 가이드 REST 어댑터 — ApplicationService 만 호출."""

from __future__ import annotations

import sys
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
        farm = str(farm_cd or "").strip()
        oid = str(obs_id or "").strip()
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
            rank=int(it.get("rank") or 0),
            snapshot_id=it.get("snapshot_id"),
            pesticide_name=it.get("pesticide_name"),
            brand_name=it.get("brand_name"),
            active_ingredient=it.get("active_ingredient"),
            crop_name=it.get("crop_name"),
            disease_name=it.get("disease_name"),
            purpose=it.get("purpose"),
            pesti_code=it.get("pesti_code"),
            item_id=it.get("item_id"),
            info_id=it.get("info_id"),
            stock_qty=int(it.get("stock_qty") or 0),
            stock_unit=it.get("stock_unit") or "낱개",
            has_stock=bool(it.get("has_stock")),
            last_used_date=it.get("last_used_date"),
            dilution=it.get("dilution"),
            phi=it.get("phi"),
            max_use_count=(
                str(it["max_use_count"])
                if it.get("max_use_count") is not None
                else None
            ),
            usage_method=it.get("usage_method"),
            toxicity=it.get("toxicity"),
            from_psis=bool(it.get("from_psis")),
            from_stock=bool(it.get("from_stock")),
            psis_registered=bool(it.get("psis_registered")),
            information_available=bool(it.get("information_available")),
            match_level=it.get("match_level"),
            match_key=it.get("match_key"),
        )

    def _to_response(self, payload: dict) -> ObservationSmartSprayGuideResponse:
        ok = bool(payload.get("ok"))
        obs_raw = payload.get("observation") or None
        cand_raw = payload.get("confirmed_candidate") or None
        observation = None
        if isinstance(obs_raw, dict) and obs_raw.get("obs_id"):
            observation = SmartSprayGuideObservationDto(
                obs_id=str(obs_raw["obs_id"]),
                farm_cd=str(obs_raw.get("farm_cd") or payload.get("farm_cd") or ""),
                obs_title=obs_raw.get("obs_title"),
                obs_dt=obs_raw.get("obs_dt"),
                ai_status=obs_raw.get("ai_status"),
                site_id=obs_raw.get("site_id"),
                site_nm=obs_raw.get("site_nm"),
            )
        confirmed = None
        if isinstance(cand_raw, dict) and (
            cand_raw.get("analysis_id") or cand_raw.get("confirmed_name")
        ):
            conf = cand_raw.get("confidence")
            try:
                conf_f = float(conf) if conf is not None else None
            except (TypeError, ValueError):
                conf_f = None
            confirmed = SmartSprayGuideCandidateDto(
                analysis_id=cand_raw.get("analysis_id"),
                candidate_seq=cand_raw.get("candidate_seq"),
                name_ko=cand_raw.get("name_ko"),
                confirmed_name=cand_raw.get("confirmed_name"),
                category=cand_raw.get("category"),
                confidence=conf_f,
            )
        err_code = str(payload.get("error_code") or "").strip() or None
        return ObservationSmartSprayGuideResponse(
            success=ok,
            guide_status=str(payload.get("guide_status") or "ERROR"),
            farm_cd=(str(payload.get("farm_cd") or "").strip() or None),
            obs_id=(str(payload.get("obs_id") or "").strip() or None),
            observation=observation,
            confirmed_candidate=confirmed,
            psis_status=str(payload.get("psis_status") or "NONE"),
            crop_name=payload.get("crop_name"),
            disease_name=payload.get("disease_name"),
            items=[self._map_item(x) for x in (payload.get("items") or [])],
            error=(
                None
                if ok
                else str(
                    payload.get("error_message")
                    or err_code
                    or "조회에 실패했습니다."
                )
            ),
            error_code=None if ok else err_code,
        )

    def get_guide(
        self, farm_cd: str, obs_id: str
    ) -> ObservationSmartSprayGuideResponse:
        obs = self._ensure_farm_and_obs(farm_cd, obs_id)
        farm = str(obs.get("farm_cd") or farm_cd).strip()
        oid = str(obs.get("obs_id") or obs_id).strip()
        AppSvc = _import_guide_app()
        with get_sqlite_write_connection(self._db_path) as conn:
            db = ServerDbBridge(conn)
            payload = AppSvc().build_guide(db, farm_cd=farm, obs_id=oid)
            return self._to_response(payload)
