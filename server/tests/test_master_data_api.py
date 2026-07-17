# -*- coding: utf-8 -*-
"""기준정보 API 통합 테스트 (운영 SQLite 읽기 전용)."""

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


@pytest.mark.skipif(not _has_farm("OR001"), reason="OR001 농장 없음")
def test_get_farm_or001() -> None:
    response = client.get("/api/v1/farms/OR001")
    assert response.status_code == 200
    body = response.json()
    assert body["farm_cd"] == "OR001"
    assert "farm_nm" in body
    assert "user_pw" not in body


@pytest.mark.skipif(not _has_farm("OR001"), reason="OR001 농장 없음")
def test_list_sites_or001() -> None:
    response = client.get("/api/v1/farms/OR001/sites")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert all(item.get("use_yn") != "N" for item in body)


@pytest.mark.skipif(not _has_farm("OR001"), reason="OR001 농장 없음")
def test_list_sites_active_only_param() -> None:
    active = client.get("/api/v1/farms/OR001/sites", params={"active_only": True})
    all_rows = client.get("/api/v1/farms/OR001/sites", params={"active_only": False})
    assert active.status_code == 200
    assert all_rows.status_code == 200
    assert len(all_rows.json()) >= len(active.json())


def test_get_farm_not_found() -> None:
    response = client.get("/api/v1/farms/NO_SUCH_FARM_XYZ")
    assert response.status_code == 404
    body = response.json()
    assert body.get("error_code") == "ENTITY_NOT_FOUND"
    assert "detail" in body


@pytest.mark.skipif(not _has_farm("OR001"), reason="OR001 농장 없음")
def test_get_site_not_found() -> None:
    response = client.get("/api/v1/farms/OR001/sites/NO_SUCH_SITE_XYZ")
    assert response.status_code == 404
    assert response.json().get("error_code") == "ENTITY_NOT_FOUND"


@pytest.mark.skipif(not _has_farm("OR001"), reason="OR001 농장 없음")
def test_common_codes_wt01() -> None:
    response = client.get(
        "/api/v1/common-codes",
        params={"farm_cd": "OR001", "parent_cd": "WT01", "active_only": True},
    )
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert all(item.get("farm_cd") == "OR001" for item in body)
    assert all(item.get("parent_cd") == "WT01" for item in body)
    assert all(item.get("use_yn") != "N" for item in body)


def test_common_codes_requires_farm_cd() -> None:
    response = client.get(
        "/api/v1/common-codes",
        params={"parent_cd": "WT01"},
    )
    assert response.status_code == 422


def test_common_codes_requires_parent_cd() -> None:
    response = client.get(
        "/api/v1/common-codes",
        params={"farm_cd": "OR001"},
    )
    assert response.status_code == 422
