"""
영농일지 ‘날씨 가져오기’ 백그라운드 워커.
메인 UI 스레드에서 WeatherManager/API를 직접 호출하지 않는다.
SQLite는 워커 전용 DBManager 연결을 사용한다.
"""
from __future__ import annotations

import os
import time

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot


class WeatherFetchWorker(QObject):
    """영농일지 날씨 조회 워커 (캐시→API 전부 워커에서 처리)."""

    finished = pyqtSignal(dict)
    failed = pyqtSignal(str)
    elapsed = pyqtSignal(float)

    def __init__(
        self,
        db_file: str,
        farm_cd: str,
        work_dt: str,
        lat: float,
        lon: float,
        nx: int,
        ny: int,
        request_id: int,
        force_refresh: bool = False,
    ):
        super().__init__()
        self._db_file = str(db_file or "").strip()
        self._farm_cd = str(farm_cd or "").strip()
        self._work_dt = str(work_dt or "").strip()[:10]
        self._lat = float(lat)
        self._lon = float(lon)
        self._nx = int(nx)
        self._ny = int(ny)
        self._request_id = int(request_id)
        self._force_refresh = bool(force_refresh)

    @pyqtSlot()
    def run(self):
        db_local = None
        t0 = time.perf_counter()
        try:
            db_path = os.path.realpath(os.path.abspath(self._db_file))
            if not db_path or not os.path.isfile(db_path):
                self.elapsed.emit(0.0)
                self.failed.emit("데이터베이스 파일을 찾을 수 없습니다.")
                return

            # 검증 로그: 전체 절대경로 출력 금지
            print(f"WeatherFetchWorker db={os.path.basename(db_path)}")

            from core.db_manager import DBManager
            from core.weather_manager import WeatherManager

            db_local = DBManager(db_path)
            # 동일 파일 사용 여부(파일명 기준 안전 로그)
            print(
                f"WeatherFetchWorker connected={os.path.basename(db_local.db_name)}"
            )
            wm = WeatherManager(db_manager=db_local)
            # 캐시 peek → 미스 시 API → 캐시 저장 (메인 UI 스레드 금지)
            result = wm.fetch_work_log_weather(
                self._farm_cd,
                self._work_dt,
                self._nx,
                self._ny,
                self._lat,
                self._lon,
                force_refresh=self._force_refresh,
            )
            sec = float(result.get("elapsed") or (time.perf_counter() - t0))
            self.elapsed.emit(sec)
            payload = dict(result or {})
            payload["request_id"] = self._request_id
            payload["work_dt"] = self._work_dt
            payload["farm_cd"] = self._farm_cd
            payload["nx"] = self._nx
            payload["ny"] = self._ny
            payload["elapsed"] = sec
            if payload.get("ok") and payload.get("data"):
                self.finished.emit(payload)
            else:
                self.failed.emit(
                    str(payload.get("error") or "날씨 데이터를 가져오지 못했습니다.")
                )
        except Exception as e:
            sec = time.perf_counter() - t0
            self.elapsed.emit(sec)
            print(f"WeatherFetchWorker error: {e}")
            self.failed.emit(str(e) or "날씨 조회 중 오류가 발생했습니다.")
        finally:
            if db_local is not None:
                try:
                    db_local.close()
                except Exception:
                    pass
