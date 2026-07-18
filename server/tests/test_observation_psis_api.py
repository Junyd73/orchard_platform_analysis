# -*- coding: utf-8 -*-
"""관찰 PSIS REST API 테스트."""

from __future__ import annotations

import sys
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.append(str(_REPO_ROOT))

from app.api import dependencies as deps
from app.core.config import get_settings
from app.db.sqlite import get_sqlite_connection, get_sqlite_write_connection
from app.main import app
from app.services.observation_psis_api_service import ObservationPsisApiService

client = TestClient(app)


def _has_farm(farm_cd: str) -> bool:
    settings = get_settings()
    with get_sqlite_connection(settings.sqlite_path) as conn:
        row = conn.execute(
            "SELECT 1 FROM m_farm_info WHERE farm_cd = ? LIMIT 1",
            (farm_cd,),
        ).fetchone()
    return row is not None


def _has_psis_table() -> bool:
    settings = get_settings()
    with get_sqlite_connection(settings.sqlite_path) as conn:
        row = conn.execute(
            """
            SELECT 1 FROM sqlite_master
            WHERE type='table' AND name='t_observation_pesticide_snapshot'
            LIMIT 1
            """
        ).fetchone()
    return row is not None


def _create_obs(farm_cd: str = "OR001") -> str:
    oid = f"TPSIS-{uuid.uuid4().hex[:10].upper()}"
    settings = get_settings()
    with get_sqlite_write_connection(settings.sqlite_path) as conn:
        sample = conn.execute(
            """
            SELECT target_type_cd, obs_type_cd, severity_cd, progress_status_cd
            FROM t_observation_master
            WHERE farm_cd = ? AND COALESCE(use_yn, 'Y') = 'Y'
            LIMIT 1
            """,
            (farm_cd,),
        ).fetchone()
        if not sample:
            raise RuntimeError("샘플 관찰 없음")
        conn.execute(
            """
            INSERT INTO t_observation_master (
                farm_cd, obs_id, obs_dt, obs_title,
                target_type_cd, obs_type_cd, severity_cd, progress_status_cd,
                ai_status, use_yn, reg_id, reg_dt, mod_id, mod_dt
            ) VALUES (
                ?, ?, date('now'), 'PSIS API테스트',
                ?, ?, ?, ?,
                'CONFIRMED', 'Y', 'TEST', datetime('now'), 'TEST', datetime('now')
            )
            """,
            (
                farm_cd,
                oid,
                sample["target_type_cd"],
                sample["obs_type_cd"],
                sample["severity_cd"],
                sample["progress_status_cd"],
            ),
        )
        conn.commit()
    return oid


def _cleanup(farm_cd: str, obs_id: str) -> None:
    settings = get_settings()
    with get_sqlite_write_connection(settings.sqlite_path) as conn:
        conn.execute(
            "DELETE FROM t_observation_pesticide_snapshot WHERE farm_cd=? AND obs_id=?",
            (farm_cd, obs_id),
        )
        conn.execute(
            "DELETE FROM t_observation_master WHERE farm_cd=? AND obs_id=?",
            (farm_cd, obs_id),
        )
        conn.commit()


@pytest.fixture
def psis_env():
    if not (_has_farm("OR001") and _has_psis_table()):
        pytest.skip("OR001 또는 PSIS 테이블 없음")
    try:
        import PyQt6  # noqa: F401
    except ImportError:
        pytest.skip("PyQt6 필요")
    oid = _create_obs()
    yield {"farm_cd": "OR001", "obs_id": oid}
    _cleanup("OR001", oid)
    app.dependency_overrides.clear()


def test_psis_get_empty(psis_env) -> None:
    farm = psis_env["farm_cd"]
    oid = psis_env["obs_id"]
    r = client.get(f"/api/v1/farms/{farm}/observations/{oid}/psis")
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["psis_status"] == "EMPTY"


def test_psis_post_requires_crop(psis_env) -> None:
    farm = psis_env["farm_cd"]
    oid = psis_env["obs_id"]
    r = client.post(
        f"/api/v1/farms/{farm}/observations/{oid}/psis",
        json={"disease_name": "검은별무늬병"},
    )
    assert r.status_code == 400


def test_psis_post_via_application_service(psis_env) -> None:
    from core.pesticide.psis_provider import FakePesticideProvider

    farm = psis_env["farm_cd"]
    oid = psis_env["obs_id"]
    settings = get_settings()
    svc = ObservationPsisApiService(
        db_path=settings.sqlite_path,
        photo_repo=deps.get_observation_photo_repository(),
        default_user_id="TEST",
        provider=FakePesticideProvider(),
    )
    app.dependency_overrides[deps.get_observation_psis_api_service] = lambda: svc

    r = client.post(
        f"/api/v1/farms/{farm}/observations/{oid}/psis",
        json={
            "crop_name": "배",
            "disease_name": "검은별무늬병",
            "force_refresh": True,
        },
        headers={"X-User-Id": "TEST"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["success"] is True
    assert body["similar_cases"]
    assert body["query_candidate"] == "검은별무늬병"
    assert "farm_cd" not in body["similar_cases"][0]
    assert body.get("error") in (None, "")

    g = client.get(
        f"/api/v1/farms/{farm}/observations/{oid}/psis",
        params={"crop_name": "배", "disease_name": "검은별무늬병"},
    )
    assert g.status_code == 200
    got = g.json()
    assert got["success"] is True
    assert got["similar_cases"]

    h = client.get(f"/api/v1/farms/{farm}/observations/{oid}/psis/history")
    assert h.status_code == 200
    assert h.json()["items"]


def test_psis_blocks_missing_confirmed_candidate(psis_env) -> None:
    from core.pesticide.psis_provider import FakePesticideProvider

    farm = psis_env["farm_cd"]
    oid = psis_env["obs_id"]
    settings = get_settings()
    svc = ObservationPsisApiService(
        db_path=settings.sqlite_path,
        photo_repo=deps.get_observation_photo_repository(),
        default_user_id="TEST",
        provider=FakePesticideProvider(),
    )
    app.dependency_overrides[deps.get_observation_psis_api_service] = lambda: svc

    r = client.post(
        f"/api/v1/farms/{farm}/observations/{oid}/psis",
        json={
            "crop_name": "배",
            "analysis_id": "NO_SUCH_ANALYSIS",
            "candidate_seq": 1,
        },
        headers={"X-User-Id": "TEST"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is False
    assert body.get("error_code") == "PSIS_PARAM"
