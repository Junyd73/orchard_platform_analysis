# -*- coding: utf-8 -*-
"""중기예보 프리페치 — t_weather_cache sentinel (SCH-001 P2)."""

from __future__ import annotations

import json
import logging
from datetime import datetime

from app.core.ops_biz_date import now_ops
from pathlib import Path
from typing import Any, Callable

from app.db.sqlite import get_sqlite_write_connection
from app.jobs._common import empty_job_result, resolve_db_path
from app.services._core_path import ensure_repo_root_on_path
from app.services.observation_ai_db_bridge import ServerDbBridge

ensure_repo_root_on_path()

logger = logging.getLogger(__name__)

# ISO 일자와 충돌하지 않는 sentinel (월캘린더 셀로 쓰이지 않음)
MID_FORECAST_CACHE_DT = "__mid__"

MidFetcher = Callable[[float, float], dict[str, Any] | None]


def _s(value: Any) -> str:
    return str(value or "").strip()


def _f(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _load_farms(conn) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT farm_cd, lat, lon
        FROM m_farm_info
        WHERE TRIM(COALESCE(farm_cd, '')) <> ''
        ORDER BY farm_cd
        """
    ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        lat = r["lat"] if hasattr(r, "keys") else r[1]
        lon = r["lon"] if hasattr(r, "keys") else r[2]
        if lat is None or lon is None:
            continue
        out.append(
            {
                "farm_cd": _s(r["farm_cd"] if hasattr(r, "keys") else r[0]),
                "lat": _f(lat),
                "lon": _f(lon),
            }
        )
    return out


def run_mid_forecast_prefetch(
    db_path: Path | str,
    *,
    fetch_mid: MidFetcher | None = None,
) -> dict[str, Any]:
    """농장별 중기예보를 t_weather_cache(weather_dt=__mid__)에 저장."""
    path = resolve_db_path(db_path)
    result = empty_job_result(job="mid_forecast")

    with get_sqlite_write_connection(path) as conn:
        farms = _load_farms(conn)
        result["farms"] = len(farms)
        if not farms:
            return result

        bridge = ServerDbBridge(conn)
        from core.weather_manager import WeatherManager

        wm = WeatherManager(db_manager=bridge)
        wm._ensure_weather_cache_table()

        if fetch_mid is None:

            def _fetch(lat: float, lon: float) -> dict[str, Any] | None:
                data = wm.get_mid_forecast(lat, lon)
                return data if isinstance(data, dict) and data else None

            fetch_mid = _fetch

        for farm in farms:
            try:
                mid = fetch_mid(float(farm["lat"]), float(farm["lon"]))
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "mid_forecast farm=%s: %s", farm.get("farm_cd"), exc
                )
                result["failed"] += 1
                continue
            if not mid:
                result["failed"] += 1
                continue
            payload = {
                "kind": "mid",
                "fetched_at": now_ops().strftime("%Y-%m-%d %H:%M:%S"),
                "mid": mid,
            }
            try:
                bridge.execute_query(
                    """
                    INSERT OR REPLACE INTO t_weather_cache
                    (farm_cd, weather_dt, weather_json, reg_dt)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        farm["farm_cd"],
                        MID_FORECAST_CACHE_DT,
                        json.dumps(payload, ensure_ascii=False),
                        now_ops().strftime("%Y-%m-%d %H:%M:%S"),
                    ),
                )
                result["fetched"] += 1
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "mid_forecast save farm=%s: %s", farm.get("farm_cd"), exc
                )
                result["failed"] += 1

    return result
