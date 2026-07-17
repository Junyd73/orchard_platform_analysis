# -*- coding: utf-8 -*-
"""AI 농약 추천 백그라운드 실행 — UI 프리즈 방지(QThread + QObject)."""

from __future__ import annotations

import time
from typing import Any, Callable, Optional

from PyQt6.QtCore import QObject, pyqtSignal

from core.db_manager import DBManager
from core.pesticide_ai_recommend_manager import PesticideAIRecommendManager


def _throttle_callback(
    inner: Optional[Callable[[str, Any], None]], min_log_interval_s: float = 0.08
) -> Optional[Callable[[str, Any], None]]:
    """log만 최소 간격 제한하고(step/percent/payload는 즉시 전달)."""
    if inner is None:
        return None
    last_log: list[float] = [0.0]

    def wrapped(kind: str, val: Any) -> None:
        if kind == "log":
            t = time.monotonic()
            if last_log[0] > 0 and t - last_log[0] < min_log_interval_s:
                time.sleep(min_log_interval_s - (t - last_log[0]))
            last_log[0] = time.monotonic()
        inner(kind, val)

    return wrapped


class AiRecommendWorker(QObject):
    """추천 분석을 메인 스레드 밖에서 실행하고 진행 신호만 보냄."""

    progress_step = pyqtSignal(str)
    progress_log = pyqtSignal(str)
    progress_percent = pyqtSignal(int)
    progress_payload = pyqtSignal(str, dict)
    finished = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, farm_cd: str):
        super().__init__()
        self._farm_cd = str(farm_cd or "").strip()

    def run(self) -> None:
        # 메인 스레드 DB 연결을 워커에서 쓰면 sqlite3 스레드 검사에 걸릴 수 있음 → 스레드 전용 연결 사용.
        db_local: DBManager | None = None
        try:
            if not self._farm_cd:
                self.failed.emit(
                    "농장 정보가 없어 분석을 시작할 수 없습니다. 농장을 선택한 뒤 다시 시도해 주세요."
                )
                return

            def _emit(kind: str, val: Any) -> None:
                if kind == "step":
                    self.progress_step.emit(str(val))
                elif kind == "log":
                    self.progress_log.emit(str(val))
                elif kind == "percent":
                    try:
                        self.progress_percent.emit(int(val))
                    except (TypeError, ValueError):
                        self.progress_percent.emit(0)
                elif kind == "payload":
                    payload = dict(val) if isinstance(val, dict) else {}
                    step_name = str(payload.get("step") or "")
                    self.progress_payload.emit(step_name, payload)

            cb = _throttle_callback(_emit, min_log_interval_s=0.08)
            db_local = DBManager()
            mgr = PesticideAIRecommendManager(db_local)
            result = mgr.get_recommendation(self._farm_cd, progress_callback=cb)
            self.finished.emit(result)
        except Exception:
            self.failed.emit(
                "분석 중 문제가 발생했습니다. 네트워크와 설정을 확인한 뒤 잠시 후 다시 시도해 주세요."
            )
        finally:
            if db_local is not None:
                db_local.close()
