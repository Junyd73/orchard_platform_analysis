# -*- coding: utf-8 -*-
"""관찰 PSIS REST 어댑터 — ApplicationService 만 호출."""

from __future__ import annotations

import sys
from pathlib import Path

from app.core.exceptions import BusinessRuleError, EntityNotFoundError
from app.db.sqlite import get_sqlite_write_connection
from app.repository.interfaces.observation_photo_repository import (
    ObservationPhotoRepository,
)
from app.schemas.observation_psis import (
    ObservationPsisCaseDto,
    ObservationPsisHistoryItem,
    ObservationPsisHistoryResponse,
    ObservationPsisResponse,
)
from app.services.observation_ai_db_bridge import ServerDbBridge


def _ensure_repo_root_on_path() -> Path:
    root = Path(__file__).resolve().parents[3]
    root_s = str(root)
    if root_s not in sys.path:
        sys.path.append(root_s)
    return root


def _import_psis_app():
    _ensure_repo_root_on_path()
    from core.ai.observation_psis_application_service import (  # noqa: WPS433
        ObservationPsisApplicationService,
    )

    return ObservationPsisApplicationService


def _import_stage3():
    _ensure_repo_root_on_path()
    from core import observation_stage3 as stage3  # noqa: WPS433

    return stage3


class ObservationPsisApiService:
    def __init__(
        self,
        *,
        db_path: Path | str,
        photo_repo: ObservationPhotoRepository,
        default_user_id: str = "MOBILE",
        provider=None,
    ):
        self._db_path = Path(db_path)
        self._photo_repo = photo_repo
        self._default_user_id = str(default_user_id or "MOBILE").strip() or "MOBILE"
        self._provider = provider

    def _user_id(self, user_id: str | None) -> str:
        uid = str(user_id or "").strip()
        return uid or self._default_user_id

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

    def _map_cases(self, items: list[dict]) -> list[ObservationPsisCaseDto]:
        out: list[ObservationPsisCaseDto] = []
        for i, it in enumerate(items or [], start=1):
            out.append(
                ObservationPsisCaseDto(
                    rank=i,
                    snapshot_id=(
                        str(it.get("snapshot_id") or "").strip() or None
                    ),
                    similarity=it.get("match_type"),
                    pesticide_name=it.get("pesticide_name"),
                    brand_name=it.get("brand_name"),
                    company_name=it.get("company_name"),
                    active_ingredient=it.get("active_ingredient"),
                    crop_name=it.get("crop_name"),
                    disease_name=it.get("disease_name"),
                    purpose_name=it.get("purpose_name"),
                    usage_method=it.get("usage_method"),
                    dilution=it.get("dilution"),
                    preharvest_interval=it.get("preharvest_interval"),
                    max_use_count=(
                        str(it["max_use_count"])
                        if it.get("max_use_count") is not None
                        else None
                    ),
                    toxicity=it.get("toxicity"),
                    fish_toxicity=it.get("fish_toxicity"),
                    source_nm=it.get("source_nm"),
                )
            )
        return out

    def _to_response(self, payload: dict) -> ObservationPsisResponse:
        ok = bool(payload.get("ok"))
        items = list(payload.get("items") or [])
        from_cache = bool(payload.get("from_cache"))
        err_code = str(payload.get("error_code") or "").strip() or None
        if ok and items and from_cache:
            status = "CACHED"
        elif ok and items:
            status = "OK"
        elif ok:
            status = "EMPTY"
        else:
            status = "FAILED"
        snap_ids = [
            str(x) for x in (payload.get("snapshot_ids") or []) if str(x or "").strip()
        ]
        sid = str(payload.get("snapshot_id") or "").strip() or None
        if not sid and snap_ids:
            sid = snap_ids[0]
        seq = payload.get("candidate_seq")
        try:
            seq_i = int(seq) if seq is not None else None
        except (TypeError, ValueError):
            seq_i = None
        return ObservationPsisResponse(
            success=ok,
            psis_status=status,
            snapshot_id=sid,
            snapshot_ids=snap_ids,
            analysis_id=(str(payload.get("analysis_id") or "").strip() or None),
            candidate_seq=seq_i,
            query_candidate=(
                str(payload.get("disease_name") or "").strip() or None
            ),
            crop_name=(str(payload.get("crop_name") or "").strip() or None),
            match_type=payload.get("match_type"),
            from_cache=from_cache,
            similar_cases=self._map_cases(items),
            searched_at=payload.get("fetched_at"),
            label=payload.get("label"),
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

    def search(
        self,
        farm_cd: str,
        obs_id: str,
        *,
        user_id: str | None,
        analysis_id: str | None = None,
        candidate_seq: int | None = None,
        crop_name: str | None = None,
        disease_name: str | None = None,
        force_refresh: bool = False,
        allow_similar: bool = False,
    ) -> ObservationPsisResponse:
        obs = self._ensure_farm_and_obs(farm_cd, obs_id)
        farm = str(obs.get("farm_cd") or farm_cd).strip()
        oid = str(obs.get("obs_id") or obs_id).strip()
        crop = str(crop_name or "").strip()
        if not crop:
            raise BusinessRuleError("작물명(crop_name)을 입력해 주세요.")

        AppSvc = _import_psis_app()
        with get_sqlite_write_connection(self._db_path) as conn:
            db = ServerDbBridge(conn)
            payload = AppSvc(provider=self._provider).run_search(
                db,
                farm_cd=farm,
                obs_id=oid,
                user_id=self._user_id(user_id),
                crop_name=crop,
                disease_name=str(disease_name or ""),
                analysis_id=analysis_id,
                candidate_seq=candidate_seq,
                force_refresh=force_refresh,
                allow_similar=allow_similar,
            )
            return self._to_response(payload)

    def get_latest(
        self,
        farm_cd: str,
        obs_id: str,
        *,
        crop_name: str | None = None,
        disease_name: str | None = None,
    ) -> ObservationPsisResponse:
        obs = self._ensure_farm_and_obs(farm_cd, obs_id)
        farm = str(obs.get("farm_cd") or farm_cd).strip()
        oid = str(obs.get("obs_id") or obs_id).strip()
        stage3 = _import_stage3()

        with get_sqlite_write_connection(self._db_path) as conn:
            db = ServerDbBridge(conn)
            crop = str(crop_name or "").strip() or None
            disease = str(disease_name or "").strip() or None
            if crop and disease:
                rows, fetched = stage3.latest_pesticide_snapshot_group(
                    db, farm, oid, crop, disease
                )
            else:
                all_rows = stage3.list_pesticide_snapshots(db, farm, oid)
                if not all_rows:
                    return ObservationPsisResponse(
                        success=True,
                        psis_status="EMPTY",
                        similar_cases=[],
                    )
                # 최신 fetched_at 그룹
                fetched = all_rows[0].get("fetched_at")
                crop = str(all_rows[0].get("crop_name") or "") or None
                disease = str(all_rows[0].get("disease_name") or "") or None
                rows = [
                    r
                    for r in all_rows
                    if r.get("fetched_at") == fetched
                    and r.get("crop_name") == crop
                    and r.get("disease_name") == disease
                ]
            snap_ids = [
                str(r.get("snapshot_id") or "")
                for r in rows
                if r.get("snapshot_id")
            ]
            return ObservationPsisResponse(
                success=True,
                psis_status="CACHED" if rows else "EMPTY",
                snapshot_id=snap_ids[0] if snap_ids else None,
                snapshot_ids=snap_ids,
                analysis_id=(
                    str(rows[0].get("analysis_id") or "").strip() or None
                    if rows
                    else None
                ),
                query_candidate=disease,
                crop_name=crop,
                match_type=(rows[0].get("match_type") if rows else None),
                from_cache=True,
                similar_cases=self._map_cases(rows),
                searched_at=str(fetched) if fetched else None,
                label="과거 조회자료(캐시)",
            )

    def get_history(
        self, farm_cd: str, obs_id: str, *, limit: int = 50
    ) -> ObservationPsisHistoryResponse:
        obs = self._ensure_farm_and_obs(farm_cd, obs_id)
        farm = str(obs.get("farm_cd") or farm_cd).strip()
        oid = str(obs.get("obs_id") or obs_id).strip()
        stage3 = _import_stage3()
        lim = max(1, min(int(limit or 50), 200))

        with get_sqlite_write_connection(self._db_path) as conn:
            db = ServerDbBridge(conn)
            rows = stage3.list_pesticide_snapshots(db, farm, oid)[:lim]

        items = [
            ObservationPsisHistoryItem(
                snapshot_id=str(r.get("snapshot_id") or ""),
                analysis_id=(str(r.get("analysis_id") or "").strip() or None),
                crop_name=r.get("crop_name"),
                disease_name=r.get("disease_name"),
                match_type=r.get("match_type"),
                pesticide_name=r.get("pesticide_name"),
                brand_name=r.get("brand_name"),
                fetched_at=r.get("fetched_at"),
            )
            for r in rows
            if r.get("snapshot_id")
        ]
        return ObservationPsisHistoryResponse(success=True, items=items)
