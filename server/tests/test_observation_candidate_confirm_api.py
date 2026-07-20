# -*- coding: utf-8 -*-
"""관찰 AI 후보 확정 REST API 테스트."""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.append(str(_REPO_ROOT))

from app.api import dependencies as deps
from app.core.config import get_settings
from app.db.sqlite import get_sqlite_connection, get_sqlite_write_connection
from app.main import app
from app.services.observation_ai_db_bridge import ServerDbBridge
from app.services.observation_candidate_confirm_api_service import (
    ObservationCandidateConfirmApiService,
)

client = TestClient(app)


def _has_farm(farm_cd: str) -> bool:
    settings = get_settings()
    with get_sqlite_connection(settings.sqlite_path) as conn:
        row = conn.execute(
            "SELECT 1 FROM m_farm_info WHERE farm_cd = ? LIMIT 1",
            (farm_cd,),
        ).fetchone()
    return row is not None


def _has_ai_table() -> bool:
    settings = get_settings()
    with get_sqlite_connection(settings.sqlite_path) as conn:
        row = conn.execute(
            """
            SELECT 1 FROM sqlite_master
            WHERE type='table' AND name='t_observation_ai_analysis'
            LIMIT 1
            """
        ).fetchone()
    return row is not None


def _create_obs_with_analysis(farm_cd: str = "OR001") -> tuple[str, str]:
    from core.ai.observation_ai_schema import normalize_analysis_result
    from core.observation_stage3 import ANALYSIS_STATUS_OK, save_ai_analysis_result

    oid = f"TCAND-{uuid.uuid4().hex[:10].upper()}"
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
                ?, ?, date('now'), '후보확정API테스트',
                ?, ?, ?, ?,
                'ANALYZED', 'Y', 'TEST', datetime('now'), 'TEST', datetime('now')
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
        db = ServerDbBridge(conn)
        raw = {
            "analysis_possible": True,
            "image_quality": "GOOD",
            "overall_summary": "요약",
            "target_part": "잎",
            "candidates": [
                {
                    "category": "DISEASE",
                    "name_ko": "검은별무늬병",
                    "scientific_name": None,
                    "confidence": 0.8,
                    "visual_evidence": ["반점"],
                    "differential_reason": "형태",
                    "urgency": "MEDIUM",
                },
                {
                    "category": "DISEASE",
                    "name_ko": "붉은별무늬병",
                    "scientific_name": None,
                    "confidence": 0.4,
                    "visual_evidence": ["반점"],
                    "differential_reason": "색",
                    "urgency": "LOW",
                },
            ],
            "additional_photos": [],
            "safe_immediate_actions": [],
            "warning": "",
        }
        ok_n, _, norm = normalize_analysis_result(raw)
        assert ok_n
        ok, msg, aid = save_ai_analysis_result(
            db,
            farm_cd,
            oid,
            user_id="TEST",
            photo_ids=[],
            provider="fake",
            model_nm="fake",
            prompt_version="v1",
            status=ANALYSIS_STATUS_OK,
            result=norm,
        )
        assert ok, msg
    return oid, aid


def _cleanup(farm_cd: str, obs_id: str) -> None:
    settings = get_settings()
    with get_sqlite_write_connection(settings.sqlite_path) as conn:
        conn.execute(
            "DELETE FROM t_observation_ai_candidate WHERE farm_cd=? AND analysis_id IN "
            "(SELECT analysis_id FROM t_observation_ai_analysis WHERE farm_cd=? AND obs_id=?)",
            (farm_cd, farm_cd, obs_id),
        )
        conn.execute(
            "DELETE FROM t_observation_ai_photo WHERE farm_cd=? AND analysis_id IN "
            "(SELECT analysis_id FROM t_observation_ai_analysis WHERE farm_cd=? AND obs_id=?)",
            (farm_cd, farm_cd, obs_id),
        )
        conn.execute(
            "DELETE FROM t_observation_ai_analysis WHERE farm_cd=? AND obs_id=?",
            (farm_cd, obs_id),
        )
        conn.execute(
            "DELETE FROM t_observation_master WHERE farm_cd=? AND obs_id=?",
            (farm_cd, obs_id),
        )
        conn.commit()


@pytest.fixture
def cand_env():
    if not (_has_farm("OR001") and _has_ai_table()):
        pytest.skip("OR001 또는 AI 테이블 없음")
    try:
        import PyQt6  # noqa: F401
    except ImportError:
        pytest.skip("PyQt6 필요")
    oid, aid = _create_obs_with_analysis()
    yield {"farm_cd": "OR001", "obs_id": oid, "analysis_id": aid}
    _cleanup("OR001", oid)
    app.dependency_overrides.clear()


def test_confirm_candidate_rest(cand_env) -> None:
    farm = cand_env["farm_cd"]
    oid = cand_env["obs_id"]
    aid = cand_env["analysis_id"]
    settings = get_settings()
    svc = ObservationCandidateConfirmApiService(
        db_path=settings.sqlite_path,
        photo_repo=deps.get_observation_photo_repository(),
    )
    app.dependency_overrides[deps.get_observation_candidate_confirm_api_service] = (
        lambda: svc
    )

    r = client.post(
        f"/api/v1/farms/{farm}/observations/{oid}/candidates/confirm",
        json={"analysis_id": aid, "candidate_seq": 1, "severity_cd": "OS010400"},
        headers={"X-User-Id": "TEST"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["success"] is True
    assert body["confirmed_name"] == "검은별무늬병"
    assert body["ai_status"] == "CONFIRMED"
    assert body["confirmed_by"] == "TEST"
    assert body["confirmed_at"]

    settings = get_settings()
    with get_sqlite_connection(settings.sqlite_path) as conn:
        sev = conn.execute(
            """
            SELECT severity_cd FROM t_observation_master
            WHERE farm_cd = ? AND obs_id = ?
            """,
            (farm, oid),
        ).fetchone()
    assert sev is not None
    assert sev["severity_cd"] == "OS010400"

    r2 = client.post(
        f"/api/v1/farms/{farm}/observations/{oid}/candidates/confirm",
        json={
            "analysis_id": aid,
            "candidate_seq": 2,
            "confirmed_name": "붉은별무늬병",
            "severity_cd": "OS010300",
        },
        headers={"X-User-Id": "TEST"},
    )
    assert r2.status_code == 200
    b2 = r2.json()
    assert b2["success"] is True
    assert b2["candidate_seq"] == 2
    assert b2["confirmed_name"] == "붉은별무늬병"


def test_confirm_rejects_bad_analysis(cand_env) -> None:
    farm = cand_env["farm_cd"]
    oid = cand_env["obs_id"]
    settings = get_settings()
    svc = ObservationCandidateConfirmApiService(
        db_path=settings.sqlite_path,
        photo_repo=deps.get_observation_photo_repository(),
    )
    app.dependency_overrides[deps.get_observation_candidate_confirm_api_service] = (
        lambda: svc
    )
    r = client.post(
        f"/api/v1/farms/{farm}/observations/{oid}/candidates/confirm",
        json={"analysis_id": "NO_SUCH", "candidate_seq": 1, "severity_cd": "OS010400"},
        headers={"X-User-Id": "TEST"},
    )
    assert r.status_code == 200
    assert r.json()["success"] is False


def test_confirm_requires_user_header(cand_env) -> None:
    farm = cand_env["farm_cd"]
    oid = cand_env["obs_id"]
    aid = cand_env["analysis_id"]
    settings = get_settings()
    svc = ObservationCandidateConfirmApiService(
        db_path=settings.sqlite_path,
        photo_repo=deps.get_observation_photo_repository(),
    )
    app.dependency_overrides[deps.get_observation_candidate_confirm_api_service] = (
        lambda: svc
    )

    with get_sqlite_write_connection(settings.sqlite_path) as conn:
        ai_before = conn.execute(
            "SELECT ai_status FROM t_observation_master WHERE farm_cd=? AND obs_id=?",
            (farm, oid),
        ).fetchone()["ai_status"]

    r = client.post(
        f"/api/v1/farms/{farm}/observations/{oid}/candidates/confirm",
        json={"analysis_id": aid, "candidate_seq": 1, "severity_cd": "OS010400"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is False
    assert body["error_code"] == "AI_CONFIRM_PARAM"

    r2 = client.post(
        f"/api/v1/farms/{farm}/observations/{oid}/candidates/confirm",
        json={"analysis_id": aid, "candidate_seq": 1, "severity_cd": "OS010400"},
        headers={"X-User-Id": "   "},
    )
    assert r2.status_code == 200
    assert r2.json()["success"] is False

    with get_sqlite_write_connection(settings.sqlite_path) as conn:
        row = conn.execute(
            """
            SELECT selected_yn, confirmed_by FROM t_observation_ai_candidate
            WHERE farm_cd = ? AND analysis_id = ? AND candidate_seq = 1
            """,
            (farm, aid),
        ).fetchone()
        ai_after = conn.execute(
            "SELECT ai_status FROM t_observation_master WHERE farm_cd=? AND obs_id=?",
            (farm, oid),
        ).fetchone()["ai_status"]
    assert str(row["selected_yn"] or "N") != "Y"
    assert not row["confirmed_by"]
    assert ai_after == ai_before


def test_confirm_wrong_obs_blocks(cand_env) -> None:
    farm = cand_env["farm_cd"]
    aid = cand_env["analysis_id"]
    settings = get_settings()
    svc = ObservationCandidateConfirmApiService(
        db_path=settings.sqlite_path,
        photo_repo=deps.get_observation_photo_repository(),
    )
    app.dependency_overrides[deps.get_observation_candidate_confirm_api_service] = (
        lambda: svc
    )
    # 다른 관찰 생성
    other = _create_obs_with_analysis()[0]
    try:
        r = client.post(
            f"/api/v1/farms/{farm}/observations/{other}/candidates/confirm",
            json={"analysis_id": aid, "candidate_seq": 1, "severity_cd": "OS010400"},
            headers={"X-User-Id": "TEST"},
        )
        assert r.status_code == 200
        assert r.json()["success"] is False
    finally:
        _cleanup(farm, other)
