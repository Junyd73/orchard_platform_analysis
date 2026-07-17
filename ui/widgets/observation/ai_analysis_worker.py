# -*- coding: utf-8 -*-
"""관찰 AI 분석 백그라운드 워커 — completed 단일 terminal 신호."""

from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

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
    update_observation_ai_status,
)


class ObservationAiWorker(QObject):
    progress = pyqtSignal(str)
    completed = pyqtSignal(dict)  # 성공·실패·예외 모두 1회만

    def __init__(
        self,
        db_path: str,
        farm_cd: str,
        obs_id: str,
        user_id: str,
        photo_ids: list[str],
        photo_paths: list[str],
        crop_hint: str,
        request_id: int,
        provider=None,
    ):
        super().__init__()
        self._db_path = str(db_path or "")
        self._farm_cd = str(farm_cd or "").strip()
        self._obs_id = str(obs_id or "").strip()
        self._user_id = str(user_id or "").strip()
        self._photo_ids = list(photo_ids or [])
        self._photo_paths = list(photo_paths or [])
        self._crop_hint = str(crop_hint or "")
        self._request_id = int(request_id)
        self._provider = provider

    @pyqtSlot()
    def run(self):
        db_local = None
        payload: dict = {
            "request_id": self._request_id,
            "ok": False,
            "error_code": "INTERNAL",
            "error_message": safe_user_message("INTERNAL"),
        }
        prev_status = DBManager.OBS_AI_STATUS_NONE
        analyzing_set = False
        try:
            self.progress.emit("분석 준비 중…")
            db_local = DBManager(self._db_path) if self._db_path else DBManager()
            before = db_local.get_observation(self._farm_cd, self._obs_id) or {}
            prev_status = str(before.get("ai_status") or DBManager.OBS_AI_STATUS_NONE)
            update_observation_ai_status(
                db_local,
                self._farm_cd,
                self._obs_id,
                DBManager.OBS_AI_STATUS_ANALYZING,
                self._user_id,
            )
            analyzing_set = True

            self.progress.emit("사진 안전 처리·AI 분석 중…")
            svc = ObservationAiService(provider=self._provider)
            resp = svc.analyze_photo_paths(
                self._photo_paths, crop_hint=self._crop_hint
            )
            if not resp.ok:
                err_code, err_msg = sanitize_stored_error(
                    resp.error_code, resp.error_message, domain="AI"
                )
                save_ai_analysis_result(
                    db_local,
                    self._farm_cd,
                    self._obs_id,
                    user_id=self._user_id,
                    photo_ids=self._photo_ids,
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
                    db_local,
                    self._farm_cd,
                    self._obs_id,
                    self._user_id,
                    prev_status=prev_status,
                )
                payload = {
                    "request_id": self._request_id,
                    "ok": False,
                    "error_code": err_code,
                    "error_message": err_msg,
                    "prev_status": prev_status,
                }
            else:
                ok, msg, aid = save_ai_analysis_result(
                    db_local,
                    self._farm_cd,
                    self._obs_id,
                    user_id=self._user_id,
                    photo_ids=self._photo_ids,
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
                        db_local,
                        self._farm_cd,
                        self._obs_id,
                        self._user_id,
                        prev_status=prev_status,
                    )
                    payload = {
                        "request_id": self._request_id,
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
                        db_local,
                        self._farm_cd,
                        self._obs_id,
                        new_status,
                        self._user_id,
                    )
                    payload = {
                        "request_id": self._request_id,
                        "ok": True,
                        "analysis_id": aid,
                        "result": resp.result,
                        "ai_status": new_status,
                    }
        except Exception as e:
            code, msg = classify_ai_exception(e)
            safe_log(code, type(e).__name__, where="ai_worker", request_id=self._request_id)
            if db_local is not None and analyzing_set:
                try:
                    restore_ai_status_after_failure(
                        db_local,
                        self._farm_cd,
                        self._obs_id,
                        self._user_id,
                        prev_status=prev_status,
                    )
                except Exception as e2:
                    safe_log(
                        "DB_ERROR",
                        type(e2).__name__,
                        where="ai_status_restore",
                        request_id=self._request_id,
                    )
            payload = {
                "request_id": self._request_id,
                "ok": False,
                "error_code": code,
                "error_message": msg,
                "prev_status": prev_status,
            }
        finally:
            if db_local is not None:
                try:
                    db_local.close()
                except Exception:
                    pass
            self.completed.emit(payload)
