# -*- coding: utf-8 -*-
"""관찰 AI REST 어댑터 — ApplicationService 만 호출 (AI 로직 중복 금지)."""

from __future__ import annotations

import sys
from pathlib import Path

from app.core.exceptions import BusinessRuleError, EntityNotFoundError
from app.db.sqlite import get_sqlite_write_connection
from app.repository.interfaces.observation_photo_repository import (
    ObservationPhotoRepository,
)
from app.schemas.observation_ai import (
    ObservationAiAnalysisResponse,
    ObservationAiCandidateDto,
    ObservationAiHistoryItem,
    ObservationAiHistoryResponse,
    ObservationAiPhotoDto,
)
from app.services.observation_ai_db_bridge import ServerDbBridge
from app.services.observation_media import resolve_media_path

_AI_STATUS_NONE = "NONE"
_AI_STATUS_REVIEW_REQUIRED = "REVIEW_REQUIRED"


def _ensure_repo_root_on_path() -> Path:
    """server/ 실행 시 core.* import 를 위해 저장소 루트를 PYTHONPATH 에 추가."""
    root = Path(__file__).resolve().parents[3]
    root_s = str(root)
    # insert(0) 금지: server 의 app 패키지를 가릴 수 있음
    if root_s not in sys.path:
        sys.path.append(root_s)
    return root


def _max_photos_per_analysis() -> int:
    """core.ai.image_sanitize.MAX_PHOTOS_PER_ANALYSIS 와 동일 값."""
    _ensure_repo_root_on_path()
    from core.ai.image_sanitize import MAX_PHOTOS_PER_ANALYSIS  # noqa: WPS433

    return int(MAX_PHOTOS_PER_ANALYSIS)


def _import_application_service():
    _ensure_repo_root_on_path()
    from core.ai.observation_ai_application_service import (  # noqa: WPS433
        ObservationAiApplicationService,
    )

    return ObservationAiApplicationService


def _import_stage3():
    _ensure_repo_root_on_path()
    from core import observation_stage3 as stage3  # noqa: WPS433

    return stage3


class ObservationAiApiService:
    """사진 확인 → ApplicationService.run_analysis → Stage3 조회 → DTO."""

    def __init__(
        self,
        *,
        db_path: Path | str,
        media_root: Path,
        photo_repo: ObservationPhotoRepository,
        default_user_id: str = "MOBILE",
        provider=None,
    ):
        self._db_path = Path(db_path)
        self._media_root = Path(media_root)
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

    def _resolve_photo_inputs(
        self,
        farm_cd: str,
        obs_id: str,
        photo_ids: list[str] | None,
    ) -> tuple[list[str], list[str]]:
        rows = self._photo_repo.list_photos(farm_cd, obs_id)
        if not rows:
            raise BusinessRuleError("분석할 사진이 없습니다. 사진을 먼저 업로드해 주세요.")

        by_id = {str(r.get("photo_id") or ""): r for r in rows}
        max_n = _max_photos_per_analysis()
        if photo_ids:
            wanted = [str(p or "").strip() for p in photo_ids if str(p or "").strip()]
            if len(wanted) > max_n:
                raise BusinessRuleError(
                    f"사진은 최대 {max_n}장까지 분석할 수 있습니다."
                )
            selected_rows = []
            for pid in wanted:
                row = by_id.get(pid)
                if not row:
                    raise BusinessRuleError(f"사진을 찾을 수 없습니다: {pid}")
                selected_rows.append(row)
        else:
            selected_rows = list(rows)[:max_n]

        ids: list[str] = []
        paths: list[str] = []
        for row in selected_rows:
            pid = str(row.get("photo_id") or "").strip()
            rel = str(row.get("file_path") or "").strip()
            abs_p = resolve_media_path(self._media_root, rel)
            if abs_p is None or not abs_p.is_file():
                raise BusinessRuleError(
                    "사진 파일이 없습니다. 업로드 후 다시 분석해 주세요."
                )
            ids.append(pid)
            paths.append(str(abs_p))

        if not paths:
            raise BusinessRuleError(
                f"분석할 사진을 1~{max_n}장 선택해 주세요."
            )
        return ids, paths

    @staticmethod
    def _top_confidence(candidates: list[dict]) -> float | None:
        vals: list[float] = []
        for c in candidates or []:
            raw = c.get("confidence")
            if raw is None:
                continue
            try:
                vals.append(float(raw))
            except (TypeError, ValueError):
                continue
        return max(vals) if vals else None

    def _map_candidates(
        self, candidates: list[dict]
    ) -> list[ObservationAiCandidateDto]:
        out: list[ObservationAiCandidateDto] = []
        for c in candidates or []:
            evidence = c.get("visual_evidence")
            if not isinstance(evidence, list):
                evidence = []
            conf = c.get("confidence")
            try:
                conf_f = float(conf) if conf is not None else None
            except (TypeError, ValueError):
                conf_f = None
            try:
                seq = int(c.get("candidate_seq") or 0)
            except (TypeError, ValueError):
                seq = 0
            out.append(
                ObservationAiCandidateDto(
                    candidate_seq=seq,
                    category=c.get("category"),
                    name_ko=c.get("name_ko"),
                    scientific_name=c.get("scientific_name"),
                    confidence=conf_f,
                    visual_evidence=[str(x) for x in evidence],
                    differential_reason=c.get("differential_reason"),
                    urgency=c.get("urgency"),
                    selected_yn=c.get("selected_yn"),
                    confirmed_name=c.get("confirmed_name"),
                )
            )
        return out

    def _to_analysis_response(
        self,
        *,
        success: bool,
        ai_status: str,
        analysis: dict | None = None,
        error: str | None = None,
        error_code: str | None = None,
    ) -> ObservationAiAnalysisResponse:
        analysis = dict(analysis or {}) if analysis else {}
        candidates = list(analysis.get("candidates") or [])
        photo_ids = [str(p) for p in (analysis.get("photo_ids") or []) if p]
        possible = analysis.get("analysis_possible")
        if possible is not None and not isinstance(possible, bool):
            try:
                possible = bool(int(possible))
            except (TypeError, ValueError):
                possible = bool(possible)
        status = str(ai_status or _AI_STATUS_NONE).strip().upper() or _AI_STATUS_NONE
        return ObservationAiAnalysisResponse(
            success=success,
            ai_status=status,
            analysis_id=(str(analysis.get("analysis_id") or "").strip() or None),
            summary=analysis.get("overall_summary"),
            candidates=self._map_candidates(candidates),
            photos=[ObservationAiPhotoDto(photo_id=p) for p in photo_ids],
            confidence=self._top_confidence(candidates),
            analyzed_at=analysis.get("analyzed_at"),
            error=error,
            error_code=error_code,
            analysis_status=analysis.get("status"),
            review_required=(status == _AI_STATUS_REVIEW_REQUIRED),
            image_quality=analysis.get("image_quality"),
            analysis_possible=possible,
        )

    def analyze(
        self,
        farm_cd: str,
        obs_id: str,
        *,
        user_id: str | None,
        consent: bool,
        photo_ids: list[str] | None = None,
        crop_hint: str = "",
    ) -> ObservationAiAnalysisResponse:
        if not consent:
            raise BusinessRuleError(
                "외부 AI 전송에 동의한 후 분석을 요청해 주세요."
            )
        obs = self._ensure_farm_and_obs(farm_cd, obs_id)
        farm = str(obs.get("farm_cd") or farm_cd).strip()
        oid = str(obs.get("obs_id") or obs_id).strip()
        ids, paths = self._resolve_photo_inputs(farm, oid, photo_ids)
        uid = self._user_id(user_id)

        AppSvc = _import_application_service()
        stage3 = _import_stage3()

        with get_sqlite_write_connection(self._db_path) as conn:
            db = ServerDbBridge(conn)
            payload = AppSvc(provider=self._provider).run_analysis(
                db,
                farm_cd=farm,
                obs_id=oid,
                user_id=uid,
                photo_ids=ids,
                photo_paths=paths,
                crop_hint=str(crop_hint or ""),
            )
            after = db.get_observation(farm, oid) or {}
            ai_status = str(after.get("ai_status") or _AI_STATUS_NONE)
            err_code = str(payload.get("error_code") or "").strip() or None

            if payload.get("ok"):
                aid = str(payload.get("analysis_id") or "").strip()
                analysis = (
                    stage3.get_ai_analysis(db, farm, aid)
                    if aid
                    else stage3.get_latest_ai_analysis(db, farm, oid)
                )
                return self._to_analysis_response(
                    success=True,
                    ai_status=str(payload.get("ai_status") or ai_status),
                    analysis=analysis,
                )

            # BUSY: Provider·이력 없음 — 기존 최신 성공 분석만 참고용으로 두지 않고 빈 본문
            if err_code == "AI_BUSY":
                return self._to_analysis_response(
                    success=False,
                    ai_status=ai_status,
                    analysis=None,
                    error=str(
                        payload.get("error_message")
                        or "이미 AI 분석이 진행 중입니다."
                    ),
                    error_code="AI_BUSY",
                )

            attempt = stage3.get_latest_ai_attempt(db, farm, oid)
            err = str(
                payload.get("error_message")
                or err_code
                or "분석에 실패했습니다."
            )
            return self._to_analysis_response(
                success=False,
                ai_status=ai_status,
                analysis=attempt,
                error=err,
                error_code=err_code,
            )

    def get_latest(
        self, farm_cd: str, obs_id: str
    ) -> ObservationAiAnalysisResponse:
        obs = self._ensure_farm_and_obs(farm_cd, obs_id)
        farm = str(obs.get("farm_cd") or farm_cd).strip()
        oid = str(obs.get("obs_id") or obs_id).strip()
        ai_status = str(obs.get("ai_status") or _AI_STATUS_NONE)
        stage3 = _import_stage3()

        with get_sqlite_write_connection(self._db_path) as conn:
            db = ServerDbBridge(conn)
            # 마스터 ai_status 는 repo 조회 시점 값일 수 있어 재조회
            fresh = db.get_observation(farm, oid) or obs
            ai_status = str(fresh.get("ai_status") or ai_status)
            analysis = stage3.get_latest_ai_analysis(db, farm, oid)
            if not analysis:
                return self._to_analysis_response(
                    success=True,
                    ai_status=ai_status,
                    analysis=None,
                )
            return self._to_analysis_response(
                success=True,
                ai_status=ai_status,
                analysis=analysis,
            )

    def get_history(
        self, farm_cd: str, obs_id: str, *, limit: int = 20
    ) -> ObservationAiHistoryResponse:
        obs = self._ensure_farm_and_obs(farm_cd, obs_id)
        farm = str(obs.get("farm_cd") or farm_cd).strip()
        oid = str(obs.get("obs_id") or obs_id).strip()
        stage3 = _import_stage3()

        with get_sqlite_write_connection(self._db_path) as conn:
            db = ServerDbBridge(conn)
            fresh = db.get_observation(farm, oid) or obs
            ai_status = str(fresh.get("ai_status") or _AI_STATUS_NONE)
            rows = stage3.list_ai_analysis_history(db, farm, oid, limit=limit)

        items: list[ObservationAiHistoryItem] = []
        for r in rows:
            possible = r.get("analysis_possible")
            if possible is not None and not isinstance(possible, bool):
                try:
                    possible = bool(int(possible))
                except (TypeError, ValueError):
                    possible = bool(possible)
            items.append(
                ObservationAiHistoryItem(
                    analysis_id=str(r.get("analysis_id") or ""),
                    status=r.get("status"),
                    image_quality=r.get("image_quality"),
                    analysis_possible=possible,
                    overall_summary=r.get("overall_summary"),
                    model_nm=r.get("model_nm"),
                    analyzed_at=r.get("analyzed_at"),
                    error_code=r.get("error_code"),
                    error_message=r.get("error_message"),
                    input_photo_count=(
                        int(r["input_photo_count"])
                        if r.get("input_photo_count") is not None
                        else None
                    ),
                )
            )
        return ObservationAiHistoryResponse(
            success=True,
            ai_status=ai_status,
            items=items,
        )
