# -*- coding: utf-8 -*-
"""관찰 AI 분석 Application Service — UI(PyQt)·REST 공통 유스케이스.

ObservationAiWorker / FastAPI 가 동일하게 호출한다.
OpenAI Provider·ObservationAiService·Stage3 저장 방식은 변경하지 않는다.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from core.ai.observation_ai_schema import PROMPT_VERSION
from core.ai.observation_ai_service import ObservationAiService
from core.db_manager import DBManager
from core.observation_safe_errors import (
    classify_ai_exception,
    safe_log,
    safe_user_message,
    sanitize_stored_error,
)
from core.observation_stage3 import (
    ANALYSIS_STATUS_FAILED,
    ANALYSIS_STATUS_OK,
    restore_ai_status_after_failure,
    save_ai_analysis_result,
    try_begin_observation_ai_analyzing,
    update_observation_ai_status,
)

ProgressCb = Callable[[str], None]


class ObservationAiApplicationService:
    """AI 분석 유스케이스 (검증·상태·분석·Stage3 저장·실패 복구)."""

    def __init__(self, provider=None):
        self._provider = provider

    def run_analysis(
        self,
        db: DBManager,
        *,
        farm_cd: str,
        obs_id: str,
        user_id: str,
        photo_ids: list[str],
        photo_paths: list[str],
        crop_hint: str = "",
        request_id: int = 0,
        on_progress: ProgressCb | None = None,
    ) -> dict[str, Any]:
        """분석 실행. 성공·실패 모두 동일 형식의 result dict 를 반환한다.

        동일 farm_cd+obs_id 가 이미 ANALYZING 이면 Provider 호출·이력 저장 없이 AI_BUSY.
        PSIS Snapshot 은 후보 확정 이후 UI/별도 워커 경로이며 본 유스케이스에 포함하지 않는다.
        """
        farm = str(farm_cd or "").strip()
        oid = str(obs_id or "").strip()
        uid = str(user_id or "").strip()
        req_id = int(request_id)

        def _progress(msg: str) -> None:
            if on_progress is not None:
                on_progress(msg)

        payload: dict[str, Any] = {
            "request_id": req_id,
            "ok": False,
            "error_code": "INTERNAL",
            "error_message": safe_user_message("INTERNAL"),
        }
        prev_status = DBManager.OBS_AI_STATUS_NONE
        analyzing_set = False

        try:
            _progress("분석 준비 중…")
            begun, begin_msg, prev = try_begin_observation_ai_analyzing(
                db, farm, oid, uid
            )
            if not begun:
                if begin_msg == "AI_BUSY":
                    return {
                        "request_id": req_id,
                        "ok": False,
                        "error_code": "AI_BUSY",
                        "error_message": safe_user_message("AI_BUSY"),
                    }
                if begin_msg == "DB_ERROR":
                    return {
                        "request_id": req_id,
                        "ok": False,
                        "error_code": "DB_ERROR",
                        "error_message": safe_user_message("DB_ERROR"),
                    }
                return {
                    "request_id": req_id,
                    "ok": False,
                    "error_code": "INTERNAL",
                    "error_message": str(begin_msg or safe_user_message("INTERNAL")),
                }
            prev_status = str(prev or DBManager.OBS_AI_STATUS_NONE)
            analyzing_set = True

            _progress("사진 안전 처리·AI 분석 중…")
            svc = ObservationAiService(provider=self._provider)
            resp = svc.analyze_photo_paths(
                list(photo_paths or []),
                crop_hint=str(crop_hint or ""),
            )
            if not resp.ok:
                err_code, err_msg = sanitize_stored_error(
                    resp.error_code, resp.error_message, domain="AI"
                )
                save_ai_analysis_result(
                    db,
                    farm,
                    oid,
                    user_id=uid,
                    photo_ids=list(photo_ids or []),
                    provider=resp.provider or "openai",
                    model_nm=resp.model_nm or "",
                    prompt_version=PROMPT_VERSION,
                    status=ANALYSIS_STATUS_FAILED,
                    result=None,
                    error_code=err_code,
                    error_message=err_msg,
                    provider_request_id=resp.provider_request_id,
                )
                restore_ai_status_after_failure(
                    db,
                    farm,
                    oid,
                    uid,
                    prev_status=prev_status,
                )
                payload = {
                    "request_id": req_id,
                    "ok": False,
                    "error_code": err_code,
                    "error_message": err_msg,
                    "prev_status": prev_status,
                }
            else:
                ok, msg, aid = save_ai_analysis_result(
                    db,
                    farm,
                    oid,
                    user_id=uid,
                    photo_ids=list(photo_ids or []),
                    provider=resp.provider or "openai",
                    model_nm=resp.model_nm or "",
                    prompt_version=PROMPT_VERSION,
                    status=ANALYSIS_STATUS_OK,
                    result=resp.result,
                    provider_request_id=resp.provider_request_id,
                )
                if not ok:
                    err_code, err_msg = sanitize_stored_error(
                        "DB_ERROR", msg, domain="AI"
                    )
                    restore_ai_status_after_failure(
                        db,
                        farm,
                        oid,
                        uid,
                        prev_status=prev_status,
                    )
                    payload = {
                        "request_id": req_id,
                        "ok": False,
                        "error_code": err_code,
                        "error_message": err_msg,
                        "prev_status": prev_status,
                    }
                else:
                    possible = bool((resp.result or {}).get("analysis_possible"))
                    new_status = (
                        DBManager.OBS_AI_STATUS_ANALYZED
                        if possible
                        else DBManager.OBS_AI_STATUS_REVIEW_REQUIRED
                    )
                    update_observation_ai_status(
                        db,
                        farm,
                        oid,
                        new_status,
                        uid,
                    )
                    payload = {
                        "request_id": req_id,
                        "ok": True,
                        "analysis_id": aid,
                        "result": resp.result,
                        "ai_status": new_status,
                    }
        except Exception as e:
            code, msg = classify_ai_exception(e)
            safe_log(code, type(e).__name__, where="ai_app_service", request_id=req_id)
            if analyzing_set:
                try:
                    restore_ai_status_after_failure(
                        db,
                        farm,
                        oid,
                        uid,
                        prev_status=prev_status,
                    )
                except Exception as e2:
                    safe_log(
                        "DB_ERROR",
                        type(e2).__name__,
                        where="ai_status_restore",
                        request_id=req_id,
                    )
            payload = {
                "request_id": req_id,
                "ok": False,
                "error_code": code,
                "error_message": msg,
                "prev_status": prev_status,
            }

        return payload
