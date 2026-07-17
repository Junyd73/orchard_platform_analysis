# -*- coding: utf-8 -*-
"""관찰 사진 가져오기 백그라운드 워커 — 파일 처리만 담당(DB 없음)."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

from core.observation_media import process_observation_photo_file


class PhotoImportWorker(QObject):
    """이미지 검증·복사·썸네일 생성을 워커 스레드에서 수행."""

    progress = pyqtSignal(int, int, str)
    file_completed = pyqtSignal(dict)
    file_failed = pyqtSignal(str, str)
    finished = pyqtSignal(list, list)
    fatal_error = pyqtSignal(str)

    def __init__(
        self,
        farm_cd: str,
        obs_id: str,
        obs_dt: str,
        items: list[tuple[str, str]],
        request_id: int,
    ):
        super().__init__()
        self._farm_cd = str(farm_cd or "").strip()
        self._obs_id = str(obs_id or "").strip()
        self._obs_dt = str(obs_dt or "").strip()
        self._items = list(items or [])
        self._request_id = int(request_id)

    @pyqtSlot()
    def run(self):
        success: list[dict] = []
        failed: list[tuple[str, str]] = []
        total = len(self._items)
        if not self._farm_cd or not self._obs_id:
            self.fatal_error.emit("관찰 정보가 없어 사진을 처리할 수 없습니다.")
            self.finished.emit([], [])
            return
        if total == 0:
            self.finished.emit([], [])
            return

        try:
            for i, (src_path, photo_id) in enumerate(self._items, start=1):
                name = Path(src_path).name
                self.progress.emit(i, total, name)
                ok, msg, meta = process_observation_photo_file(
                    self._farm_cd,
                    self._obs_id,
                    self._obs_dt,
                    src_path,
                    photo_id=photo_id,
                )
                if ok and meta:
                    meta["request_id"] = self._request_id
                    self.file_completed.emit(meta)
                    success.append(meta)
                else:
                    err = msg or "저장 실패"
                    self.file_failed.emit(src_path, err)
                    failed.append((src_path, err))
            self.finished.emit(success, failed)
        except Exception as e:
            print(f"PhotoImportWorker error: {e}")
            self.fatal_error.emit(str(e) or "사진 처리 중 오류가 발생했습니다.")
            self.finished.emit(success, failed)
