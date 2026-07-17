# -*- coding: utf-8 -*-
"""관찰 조회 API 테스트 (읽기 전용)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.db.sqlite import get_sqlite_connection
from app.main import app

client = TestClient(app)


def _has_farm(farm_cd: str) -> bool:
    settings = get_settings()
    with get_sqlite_connection(settings.sqlite_path) as conn:
        row = conn.execute(
            "SELECT 1 FROM m_farm_info WHERE farm_cd = ? LIMIT 1",
            (farm_cd,),
        ).fetchone()
    return row is not None


def _has_observation_table() -> bool:
    settings = get_settings()
    with get_sqlite_connection(settings.sqlite_path) as conn:
        row = conn.execute(
            """
            SELECT 1 FROM sqlite_master
            WHERE type = 'table' AND name = 't_observation_master'
            LIMIT 1
            """
        ).fetchone()
    return row is not None


@pytest.mark.skipif(
    not (_has_farm("OR001") and _has_observation_table()),
    reason="OR001 또는 t_observation_master 없음",
)
def test_observation_summary_or001() -> None:
    response = client.get("/api/v1/farms/OR001/observations/summary")
    assert response.status_code == 200
    body = response.json()
    assert "today_count" in body
    assert "danger_count" in body
    assert "fruit_count" in body
    assert "ai_pending_count" in body
    assert "as_of_date" in body
    assert body["today_count"] >= 0


@pytest.mark.skipif(
    not (_has_farm("OR001") and _has_observation_table()),
    reason="OR001 또는 t_observation_master 없음",
)
def test_list_observations_or001() -> None:
    response = client.get(
        "/api/v1/farms/OR001/observations",
        params={"limit": 20, "sort": "obs_dt_desc"},
    )
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    if body:
        item = body[0]
        for key in (
            "obs_id",
            "obs_dt",
            "location_text",
            "severity_nm",
            "target_type_nm",
            "ai_status",
        ):
            assert key in item


def test_observation_summary_farm_not_found() -> None:
    response = client.get("/api/v1/farms/NO_SUCH_FARM_XYZ/observations/summary")
    assert response.status_code == 404
    assert response.json().get("error_code") == "ENTITY_NOT_FOUND"
