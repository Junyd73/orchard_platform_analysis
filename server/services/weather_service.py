# -*- coding: utf-8 -*-
"""모바일 날씨 상세 서비스 — WeatherManager.build_mobile_weather_detail 위임."""

from __future__ import annotations

from datetime import date

from app.core.ops_biz_date import today_ops
from pathlib import Path
from typing import Any

from app.core.exceptions import BusinessRuleError, EntityNotFoundError
from app.db.sqlite import get_sqlite_connection, get_sqlite_write_connection
from app.schemas.weather import (
    WeatherCurrentDto,
    WeatherDetailResponse,
    WeatherHourlyItemDto,
    WeatherPeriodHalfDto,
    WeatherSunEventDto,
    WeatherWeeklyItemDto,
)
from app.services._core_path import ensure_repo_root_on_path
from app.services.observation_ai_db_bridge import ServerDbBridge

MSG_FARM_LOCATION_MISSING = (
    "농장 위치(위도·경도·격자)가 없습니다. 농장 정보를 확인해 주세요."
)
MSG_WEATHER_DETAIL_FAILED = "날씨 상세 데이터를 가져오지 못했습니다."


def _s(v: Any) -> str:
    return str(v or "").strip()


def _half(raw: Any) -> WeatherPeriodHalfDto | None:
    if not isinstance(raw, dict):
        return None
    return WeatherPeriodHalfDto(
        precip_prob_pct=int(raw.get("precip_prob_pct") or 0),
        precip_mm=raw.get("precip_mm"),
        wind_ms=raw.get("wind_ms"),
    )


class WeatherService:
    def __init__(self, *, db_path: Path | str) -> None:
        self._db_path = Path(db_path)

    def _ensure_farm(self, farm_cd: str) -> str:
        farm = _s(farm_cd)
        if not farm:
            raise EntityNotFoundError("Farm not found")
        with get_sqlite_connection(self._db_path) as conn:
            row = conn.execute(
                "SELECT 1 AS ok FROM m_farm_info WHERE farm_cd = ? LIMIT 1",
                (farm,),
            ).fetchone()
        if not row:
            raise EntityNotFoundError("Farm not found")
        return farm

    def _load_farm_geo(
        self, farm_cd: str
    ) -> tuple[float, float, int, int, str]:
        """lat, lon, nx, ny, location_label."""
        with get_sqlite_connection(self._db_path) as conn:
            row = conn.execute(
                """
                SELECT lat, lon, nx, ny,
                       COALESCE(address, '') AS address,
                       COALESCE(farm_nm, '') AS farm_nm
                FROM m_farm_info
                WHERE farm_cd = ?
                LIMIT 1
                """,
                (farm_cd,),
            ).fetchone()
        if not row:
            raise EntityNotFoundError("Farm not found")
        lat, lon, nx, ny = row["lat"], row["lon"], row["nx"], row["ny"]
        if lat is None or lon is None or nx is None or ny is None:
            raise BusinessRuleError(MSG_FARM_LOCATION_MISSING)
        try:
            loc = _s(row["address"]) or _s(row["farm_nm"])
            return float(lat), float(lon), int(nx), int(ny), loc
        except (TypeError, ValueError) as exc:
            raise BusinessRuleError(MSG_FARM_LOCATION_MISSING) from exc

    def get_detail(
        self,
        farm_cd: str,
        *,
        target_date: str | None = None,
    ) -> WeatherDetailResponse:
        farm = self._ensure_farm(farm_cd)
        lat, lon, nx, ny, location = self._load_farm_geo(farm)
        dt = _s(target_date)[:10] or today_ops().isoformat()

        ensure_repo_root_on_path()
        from core.weather_manager import WeatherManager  # noqa: WPS433

        with get_sqlite_write_connection(self._db_path) as conn:
            bridge = ServerDbBridge(conn)
            wm = WeatherManager(db_manager=bridge)
            payload = wm.build_mobile_weather_detail(
                nx=nx,
                ny=ny,
                lat=lat,
                lon=lon,
                target_date=dt,
                location_label=location,
            )

        if not payload or not payload.get("ok"):
            raise BusinessRuleError(MSG_WEATHER_DETAIL_FAILED)

        current_raw = payload.get("current") or {}
        hourly = [
            WeatherHourlyItemDto.model_validate(item)
            for item in (payload.get("hourly") or [])
            if isinstance(item, dict)
        ]
        sun_events = [
            WeatherSunEventDto.model_validate(item)
            for item in (payload.get("sun_events") or [])
            if isinstance(item, dict)
        ]
        weekly = [
            WeatherWeeklyItemDto.model_validate(item)
            for item in (payload.get("weekly") or [])
            if isinstance(item, dict)
        ]

        return WeatherDetailResponse(
            success=True,
            farm_cd=farm,
            date=_s(payload.get("date")) or dt,
            location=location,
            current=WeatherCurrentDto.model_validate(current_raw),
            tomorrow_am=_half(payload.get("tomorrow_am")),
            hourly=hourly,
            sun_events=sun_events,
            weekly=weekly,
            updated_at=_s(payload.get("updated_at")) or None,
            elapsed=float(payload.get("elapsed") or 0.0),
            message="날씨 상세 조회 완료",
        )
