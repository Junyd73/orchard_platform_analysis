# -*- coding: utf-8 -*-
"""공식 농약정보(PSIS) 조회 워커 — completed 단일 terminal 신호."""

from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

from core.db_manager import DBManager
from core.observation_safe_errors import (
    classify_psis_exception,
    safe_log,
    safe_user_message,
    sanitize_stored_error,
)
from core.pesticide.pesticide_service import ObservationPesticideService


class PsisSearchWorker(QObject):
    progress = pyqtSignal(str)
    completed = pyqtSignal(dict)

    def __init__(
        self,
        db_path: str,
        farm_cd: str,
        obs_id: str,
        user_id: str,
        crop_name: str,
        disease_name: str,
        analysis_id: str | None,
        force_refresh: bool,
        allow_similar: bool,
        request_id: int,
        provider=None,
    ):
        super().__init__()
        self._db_path = str(db_path or "")
        self._farm_cd = str(farm_cd or "").strip()
        self._obs_id = str(obs_id or "").strip()
        self._user_id = str(user_id or "").strip()
        self._crop = str(crop_name or "").strip()
        self._disease = str(disease_name or "").strip()
        self._analysis_id = analysis_id
        self._force = bool(force_refresh)
        self._similar = bool(allow_similar)
        self._request_id = int(request_id)
        self._provider = provider

    @pyqtSlot()
    def run(self):
        db_local = None
        payload: dict = {
            "request_id": self._request_id,
            "ok": False,
            "items": [],
            "error_code": "INTERNAL",
            "error_message": safe_user_message("INTERNAL"),
        }
        try:
            self.progress.emit("공식 등록정보 조회 중…")
            db_local = DBManager(self._db_path) if self._db_path else DBManager()
            svc = ObservationPesticideService(provider=self._provider)
            result = svc.search_with_cache_policy(
                db_local,
                self._farm_cd,
                self._obs_id,
                self._crop,
                self._disease,
                force_refresh=self._force,
                allow_similar=self._similar,
                user_id=self._user_id,
                analysis_id=self._analysis_id,
            )
            result = dict(result or {})
            result["request_id"] = self._request_id
            if result.get("error_code"):
                ec, em = sanitize_stored_error(
                    result.get("error_code"),
                    result.get("error_message"),
                    domain="PSIS",
                )
                result["error_code"] = ec
                result["error_message"] = em
            payload = result
        except Exception as e:
            code, msg = classify_psis_exception(e)
            safe_log(code, type(e).__name__, where="psis_worker", request_id=self._request_id)
            payload = {
                "request_id": self._request_id,
                "ok": False,
                "items": [],
                "error_code": code,
                "error_message": msg,
                "from_cache": False,
            }
        finally:
            if db_local is not None:
                try:
                    db_local.close()
                except Exception:
                    pass
            self.completed.emit(payload)
