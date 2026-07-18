# -*- coding: utf-8 -*-
"""관찰 AI 분석 REST API 테스트 (ApplicationService 공통 엔진)."""

from __future__ import annotations

import io
import sys
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image

# core.* (ApplicationService) — 저장소 루트 (server/app 보다 앞에 두면 안 됨)
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.append(str(_REPO_ROOT))

from app.api import dependencies as deps
from app.core.config import get_settings
from app.db.sqlite import get_sqlite_connection, get_sqlite_write_connection
from app.main import app
from app.services.observation_ai_api_service import ObservationAiApiService
from app.services.observation_media import build_obs_photo_rel_dir

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
            WHERE type = 'table' AND name = 't_observation_ai_analysis'
            LIMIT 1
            """
        ).fetchone()
    return row is not None


def _png_bytes() -> bytes:
    img = Image.new("RGB", (80, 60), (30, 140, 40))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _create_obs_with_photo(farm_cd: str = "OR001") -> tuple[str, str]:
    """관찰 + 디스크 사진 1장. (obs_id, photo_id)."""
    oid = f"TAI-{uuid.uuid4().hex[:10].upper()}"
    pid = f"PHO-{uuid.uuid4().hex[:10].upper()}"
    settings = get_settings()
    media = settings.observation_media_root
    year = "2026"
    rel_dir = build_obs_photo_rel_dir(farm_cd, oid, year)
    abs_dir = media / Path(*Path(rel_dir).parts)
    abs_dir.mkdir(parents=True, exist_ok=True)
    stored = f"{pid}.jpg"
    rel_path = f"{rel_dir}/{stored}".replace("\\", "/")
    abs_file = abs_dir / stored
    Image.new("RGB", (100, 80), (20, 100, 20)).save(abs_file, format="JPEG")

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
                ?, ?, date('now'), 'AI API테스트',
                ?, ?, ?, ?,
                'NONE', 'Y', 'TEST', datetime('now'), 'TEST', datetime('now')
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
        conn.execute(
            """
            INSERT INTO t_observation_photo (
                farm_cd, photo_id, obs_id, file_path, thumb_path,
                original_nm, stored_nm, file_ext, file_size,
                sort_no, use_yn, reg_id, reg_dt, mod_id, mod_dt
            ) VALUES (
                ?, ?, ?, ?, NULL,
                'ai_test.jpg', ?, 'jpg', 1234,
                1, 'Y', 'TEST', datetime('now'), 'TEST', datetime('now')
            )
            """,
            (farm_cd, pid, oid, rel_path, stored),
        )
        conn.commit()
    return oid, pid


def _cleanup(farm_cd: str, obs_id: str) -> None:
    settings = get_settings()
    with get_sqlite_write_connection(settings.sqlite_path) as conn:
        conn.execute(
            "DELETE FROM t_observation_ai_photo WHERE farm_cd = ? AND analysis_id IN "
            "(SELECT analysis_id FROM t_observation_ai_analysis "
            " WHERE farm_cd = ? AND obs_id = ?)",
            (farm_cd, farm_cd, obs_id),
        )
        conn.execute(
            "DELETE FROM t_observation_ai_candidate WHERE farm_cd = ? AND analysis_id IN "
            "(SELECT analysis_id FROM t_observation_ai_analysis "
            " WHERE farm_cd = ? AND obs_id = ?)",
            (farm_cd, farm_cd, obs_id),
        )
        conn.execute(
            "DELETE FROM t_observation_ai_analysis WHERE farm_cd = ? AND obs_id = ?",
            (farm_cd, obs_id),
        )
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
def ai_env():
    if not (_has_farm("OR001") and _has_ai_table()):
        pytest.skip("OR001 또는 AI 테이블 없음")
    try:
        import PyQt6  # noqa: F401
    except ImportError:
        pytest.skip("서버 venv 에 PyQt6 필요 (공통 AI 엔진)")
    oid, pid = _create_obs_with_photo()
    yield {"farm_cd": "OR001", "obs_id": oid, "photo_id": pid}
    _cleanup("OR001", oid)
    deps.get_observation_ai_api_service.cache_clear() if hasattr(
        deps.get_observation_ai_api_service, "cache_clear"
    ) else None
    app.dependency_overrides.clear()


def test_get_analysis_empty(ai_env) -> None:
    farm = ai_env["farm_cd"]
    oid = ai_env["obs_id"]
    r = client.get(f"/api/v1/farms/{farm}/observations/{oid}/analysis")
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["analysis_id"] is None
    assert body["candidates"] == []
    assert body["ai_status"] in ("NONE", "PENDING", "")


def test_post_requires_consent(ai_env) -> None:
    farm = ai_env["farm_cd"]
    oid = ai_env["obs_id"]
    r = client.post(
        f"/api/v1/farms/{farm}/observations/{oid}/analysis",
        json={"consent": False},
    )
    assert r.status_code == 400
    assert r.json().get("error_code") == "BUSINESS_RULE_ERROR"


def test_post_analyze_via_application_service(ai_env) -> None:
    from core.ai.observation_ai_provider import ObservationAiResponse
    from core.ai.observation_ai_service import ObservationAiService
    from core.ai.openai_observation_provider import FakeObservationProvider

    farm = ai_env["farm_cd"]
    oid = ai_env["obs_id"]
    pid = ai_env["photo_id"]
    settings = get_settings()

    fake = FakeObservationProvider()
    raw = fake.analyze(
        __import__(
            "core.ai.observation_ai_provider", fromlist=["ObservationAiRequest"]
        ).ObservationAiRequest(images=[{"data_url": "data:image/jpeg;base64,aa"}])
    )
    wrapped = ObservationAiResponse(
        ok=True,
        result=raw.result,
        provider="fake",
        model_nm="fake",
        provider_request_id="api-test-1",
    )

    svc = ObservationAiApiService(
        db_path=settings.sqlite_path,
        media_root=settings.observation_media_root,
        photo_repo=deps.get_observation_photo_repository(),
        default_user_id="TEST",
        provider=fake,
    )
    app.dependency_overrides[deps.get_observation_ai_api_service] = lambda: svc

    with patch.object(
        ObservationAiService, "analyze_photo_paths", return_value=wrapped
    ) as mocked:
        r = client.post(
            f"/api/v1/farms/{farm}/observations/{oid}/analysis",
            json={
                "consent": True,
                "photo_ids": [pid],
                "crop_hint": "배",
            },
            headers={"X-User-Id": "TEST"},
        )
        assert mocked.called

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["success"] is True
    assert body["analysis_id"]
    assert body["summary"]
    assert body["candidates"]
    assert body["photos"]
    assert body["photos"][0]["photo_id"] == pid
    assert body["ai_status"] in ("ANALYZED", "REVIEW_REQUIRED")
    assert body["confidence"] is not None
    assert body["analyzed_at"]
    assert body.get("error") in (None, "")

    g = client.get(f"/api/v1/farms/{farm}/observations/{oid}/analysis")
    assert g.status_code == 200
    got = g.json()
    assert got["analysis_id"] == body["analysis_id"]
    assert got["candidates"][0]["name_ko"] == body["candidates"][0]["name_ko"]

    h = client.get(
        f"/api/v1/farms/{farm}/observations/{oid}/analysis/history",
        params={"limit": 10},
    )
    assert h.status_code == 200
    hist = h.json()
    assert hist["success"] is True
    assert any(i["analysis_id"] == body["analysis_id"] for i in hist["items"])


def test_post_analyze_busy(ai_env) -> None:
    """ANALYZING 중 두 번째 요청은 AI_BUSY, Provider 미호출."""
    from unittest.mock import patch

    from core.ai.observation_ai_service import ObservationAiService
    from core.db_manager import DBManager

    farm = ai_env["farm_cd"]
    oid = ai_env["obs_id"]
    pid = ai_env["photo_id"]
    settings = get_settings()

    with get_sqlite_write_connection(settings.sqlite_path) as conn:
        conn.execute(
            """
            UPDATE t_observation_master
            SET ai_status = ?
            WHERE farm_cd = ? AND obs_id = ?
            """,
            (DBManager.OBS_AI_STATUS_ANALYZING, farm, oid),
        )
        conn.commit()

    svc = ObservationAiApiService(
        db_path=settings.sqlite_path,
        media_root=settings.observation_media_root,
        photo_repo=deps.get_observation_photo_repository(),
        default_user_id="TEST",
    )
    app.dependency_overrides[deps.get_observation_ai_api_service] = lambda: svc

    with patch.object(ObservationAiService, "analyze_photo_paths") as mocked:
        r = client.post(
            f"/api/v1/farms/{farm}/observations/{oid}/analysis",
            json={"consent": True, "photo_ids": [pid]},
            headers={"X-User-Id": "TEST"},
        )
        mocked.assert_not_called()

    assert r.status_code == 200
    body = r.json()
    assert body["success"] is False
    assert body["error_code"] == "AI_BUSY"


def test_analysis_obs_not_found() -> None:
    if not _has_farm("OR001"):
        pytest.skip("OR001 없음")
    r = client.get("/api/v1/farms/OR001/observations/NO_SUCH_OBS_XYZ/analysis")
    assert r.status_code == 404
