# -*- coding: utf-8 -*-
"""관찰 AI 후보 확정 REST 어댑터 — ApplicationService 만 호출."""

from __future__ import annotations

import sys
from pathlib import Path

from app.core.exceptions import EntityNotFoundError
from app.db.sqlite import get_sqlite_write_connection
from app.repository.interfaces.observation_photo_repository import (
    ObservationPhotoRepository,
)
from app.schemas.observation_candidate import ObservationCandidateConfirmResponse
from app.services.observation_ai_db_bridge import ServerDbBridge


def _ensure_repo_root_on_path() -> Path:
    root = Path(__file__).resolve().parents[3]
    root_s = str(root)
    if root_s not in sys.path:
        sys.path.append(root_s)
    return root


def _import_confirm_app():
    _ensure_repo_root_on_path()
    from core.ai.observation_candidate_confirm_application_service import (  # noqa: WPS433
        ObservationCandidateConfirmApplicationService,
    )

    return ObservationCandidateConfirmApplicationService


class ObservationCandidateConfirmApiService:
    def __init__(
        self,
        *,
        db_path: Path | str,
        photo_repo: ObservationPhotoRepository,
        default_user_id: str = "MOBILE",
    ):
        self._db_path = Path(db_path)
        self._photo_repo = photo_repo
        self._default_user_id = str(default_user_id or "MOBILE").strip() or "MOBILE"

    def _user_id(self, user_id: str | None) -> str:
        return str(user_id or "").strip() or self._default_user_id

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

    def confirm(
        self,
        farm_cd: str,
        obs_id: str,
        *,
        user_id: str | None,
        analysis_id: str,
        candidate_seq: int,
        confirmed_name: str | None = None,
    ) -> ObservationCandidateConfirmResponse:
        obs = self._ensure_farm_and_obs(farm_cd, obs_id)
        farm = str(obs.get("farm_cd") or farm_cd).strip()
        oid = str(obs.get("obs_id") or obs_id).strip()
        AppSvc = _import_confirm_app()

        with get_sqlite_write_connection(self._db_path) as conn:
            db = ServerDbBridge(conn)
            payload = AppSvc().confirm_candidate(
                db,
                farm_cd=farm,
                obs_id=oid,
                user_id=self._user_id(user_id),
                analysis_id=analysis_id,
                candidate_seq=candidate_seq,
                confirmed_name=confirmed_name,
            )

        ok = bool(payload.get("ok"))
        seq = payload.get("candidate_seq")
        try:
            seq_i = int(seq) if seq is not None else None
        except (TypeError, ValueError):
            seq_i = None
        err_code = str(payload.get("error_code") or "").strip() or None
        return ObservationCandidateConfirmResponse(
            success=ok,
            analysis_id=(str(payload.get("analysis_id") or "").strip() or None),
            candidate_seq=seq_i,
            confirmed_name=payload.get("confirmed_name"),
            confirmed_by=payload.get("confirmed_by"),
            confirmed_at=payload.get("confirmed_at"),
            ai_status=payload.get("ai_status"),
            error=(
                None
                if ok
                else str(
                    payload.get("error_message")
                    or err_code
                    or "확정에 실패했습니다."
                )
            ),
            error_code=None if ok else err_code,
        )
