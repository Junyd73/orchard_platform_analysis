# -*- coding: utf-8 -*-
"""관찰 기본정보 임시 저장 API 테스트 (SCR-002 진입)."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.observation_constants import (
    OBS_PROGRESS_WATCHING_CD,
    OBS_SEVERITY_NORMAL_CD,
    OBS_TARGET_PEST_CD,
    OBS_TYPE_DISEASE_CD,
)
from app.db.sqlite import get_sqlite_connection, get_sqlite_write_connection
from app.main import app

client = TestClient(app)


def _has_farm(farm_cd: str = "OR001") -> bool:
    settings = get_settings()
    with get_sqlite_connection(settings.sqlite_path) as conn:
        row = conn.execute(
            "SELECT 1 FROM m_farm_info WHERE farm_cd = ? LIMIT 1",
            (farm_cd,),
        ).fetchone()
    return row is not None


def _first_site(farm_cd: str = "OR001") -> str | None:
    settings = get_settings()
    with get_sqlite_connection(settings.sqlite_path) as conn:
        row = conn.execute(
            """
            SELECT site_id FROM m_farm_site
            WHERE farm_cd = ? AND COALESCE(use_yn, 'Y') = 'Y'
            LIMIT 1
            """,
            (farm_cd,),
        ).fetchone()
    return str(row["site_id"]) if row else None


def _delete_obs(farm_cd: str, obs_id: str) -> None:
    settings = get_settings()
    with get_sqlite_write_connection(settings.sqlite_path) as conn:
        conn.execute(
            "DELETE FROM t_observation_photo WHERE farm_cd = ? AND obs_id = ?",
            (farm_cd, obs_id),
        )
        conn.execute(
            "DELETE FROM t_observation_master WHERE farm_cd = ? AND obs_id = ?",
            (farm_cd, obs_id),
        )
        conn.commit()


@pytest.fixture
def site_id():
    if not _has_farm("OR001"):
        pytest.skip("OR001 없음")
    sid = _first_site("OR001")
    if not sid:
        pytest.skip("필지 없음")
    return sid


def test_create_and_update_basic_no_duplicate(site_id: str) -> None:
    farm = "OR001"
    title = f"진입테스트-{uuid.uuid4().hex[:8]}"
    body = {
        "obs_dt": "2026-07-17",
        "target_type_cd": OBS_TARGET_PEST_CD,
        "site_id": site_id,
        "obs_title": title,
        "obs_content": None,
    }
    created_ids: list[str] = []
    try:
        res = client.post(
            f"/api/v1/farms/{farm}/observations",
            json=body,
            headers={"X-User-Id": "TEST"},
        )
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["created"] is True
        oid = data["obs_id"]
        created_ids.append(oid)
        assert oid.startswith("OBS20260717-")

        detail = client.get(f"/api/v1/farms/{farm}/observations/{oid}")
        assert detail.status_code == 200
        d = detail.json()
        assert d["target_type_cd"] == OBS_TARGET_PEST_CD
        assert d["obs_type_cd"] == OBS_TYPE_DISEASE_CD
        assert d["severity_cd"] == OBS_SEVERITY_NORMAL_CD
        assert d["progress_status_cd"] == OBS_PROGRESS_WATCHING_CD
        assert d["obs_title"] == title
        assert d["obs_content"] == title  # title만 넣으면 content 보정

        upd = client.put(
            f"/api/v1/farms/{farm}/observations/{oid}/basic",
            json={
                **body,
                "obs_title": title + "-수정",
                "obs_content": "내용",
            },
            headers={"X-User-Id": "TEST"},
        )
        assert upd.status_code == 200
        assert upd.json()["created"] is False
        assert upd.json()["obs_id"] == oid

        detail2 = client.get(f"/api/v1/farms/{farm}/observations/{oid}").json()
        assert detail2["obs_title"] == title + "-수정"
        assert detail2["obs_content"] == "내용"
    finally:
        for oid in created_ids:
            _delete_obs(farm, oid)


def test_create_rejects_empty_text(site_id: str) -> None:
    res = client.post(
        "/api/v1/farms/OR001/observations",
        json={
            "obs_dt": "2026-07-17",
            "target_type_cd": OBS_TARGET_PEST_CD,
            "site_id": site_id,
            "obs_title": "",
            "obs_content": "",
        },
        headers={"X-User-Id": "TEST"},
    )
    assert res.status_code == 400


def test_create_rejects_invalid_target(site_id: str) -> None:
    res = client.post(
        "/api/v1/farms/OR001/observations",
        json={
            "obs_dt": "2026-07-17",
            "target_type_cd": "OB010100",
            "site_id": site_id,
            "obs_title": "x",
        },
        headers={"X-User-Id": "TEST"},
    )
    assert res.status_code == 400
