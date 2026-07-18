# -*- coding: utf-8 -*-
"""관찰 AI 분석 백그라운드 워커 — Thread·Signal·Application Service 호출만 담당."""

from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

from core.ai.observation_ai_application_service import ObservationAiApplicationService
from core.db_manager import DBManager
from core.observation_safe_errors import safe_user_message


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
        try:
            db_local = DBManager(self._db_path) if self._db_path else DBManager()
            app_svc = ObservationAiApplicationService(provider=self._provider)
            payload = app_svc.run_analysis(
                db_local,
                farm_cd=self._farm_cd,
                obs_id=self._obs_id,
                user_id=self._user_id,
                photo_ids=self._photo_ids,
                photo_paths=self._photo_paths,
                crop_hint=self._crop_hint,
                request_id=self._request_id,
                on_progress=lambda msg: self.progress.emit(msg),
            )
        finally:
            if db_local is not None:
                try:
                    db_local.close()
                except Exception:
                    pass
            self.completed.emit(payload)
