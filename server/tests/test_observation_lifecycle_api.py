# -*- coding: utf-8 -*-
"""관찰 DRAFT/COMPLETED 생명주기 API 테스트."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_observation_repository
from app.core.config import get_settings
from app.core.observation_constants import OBS_TARGET_PEST_CD
from app.db.observation_lifecycle_migrate import ensure_observation_lifecycle_schema
from app.db.sqlite import get_sqlite_connection, get_sqlite_write_connection
from app.main import app

client = TestClient(app)


def _setup():
    ensure_observation_lifecycle_schema(get_settings().sqlite_path)
    get_observation_repository.cache_clear()


def _has_farm(farm_cd: str = "OR001") -> bool:
    with get_sqlite_connection(get_settings().sqlite_path) as conn:
        row = conn.execute(
            "SELECT 1 FROM m_farm_info WHERE farm_cd = ? LIMIT 1",
            (farm_cd,),
        ).fetchone()
    return row is not None


def _first_site(farm_cd: str = "OR001") -> str | None:
    with get_sqlite_connection(get_settings().sqlite_path) as conn:
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
    with get_sqlite_write_connection(get_settings().sqlite_path) as conn:
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
    _setup()
    if not _has_farm("OR001"):
        pytest.skip("OR001 없음")
    sid = _first_site("OR001")
    if not sid:
        pytest.skip("필지 없음")
    return sid


def _create_draft(site_id: str, title: str | None = None) -> str:
    body = {
        "obs_dt": "2026-07-17",
        "target_type_cd": OBS_TARGET_PEST_CD,
        "site_id": site_id,
        "obs_title": title or f"LC-{uuid.uuid4().hex[:8]}",
        "obs_content": "생명주기 테스트",
    }
    res = client.post(
        "/api/v1/farms/OR001/observations",
        json=body,
        headers={"X-User-Id": "TEST"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["observation_status"] == "DRAFT"
    return res.json()["obs_id"]


def test_draft_not_in_list_or_summary(site_id: str) -> None:
    oid = _create_draft(site_id)
    try:
        listed = client.get("/api/v1/farms/OR001/observations?limit=200").json()
        assert all(x["obs_id"] != oid for x in listed)

        drafts = client.get("/api/v1/farms/OR001/observations/drafts").json()
        assert any(x["obs_id"] == oid for x in drafts)

        before = client.get("/api/v1/farms/OR001/observations/summary").json()
        # 완료 후 오늘 건수 증가 여부만 별도 테스트
        assert "today_count" in before
    finally:
        _delete_obs("OR001", oid)


def test_complete_then_list(site_id: str) -> None:
    oid = _create_draft(site_id)
    try:
        done = client.post(
            f"/api/v1/farms/OR001/observations/{oid}/complete",
            headers={"X-User-Id": "TEST"},
        )
        assert done.status_code == 200, done.text
        assert done.json()["observation_status"] == "COMPLETED"

        listed = client.get("/api/v1/farms/OR001/observations?limit=200").json()
        assert any(x["obs_id"] == oid for x in listed)

        drafts = client.get("/api/v1/farms/OR001/observations/drafts").json()
        assert all(x["obs_id"] != oid for x in drafts)

        detail = client.get(f"/api/v1/farms/OR001/observations/{oid}").json()
        assert detail["observation_status"] == "COMPLETED"
        assert detail["completed_at"]
    finally:
        _delete_obs("OR001", oid)


def test_cancel_removes_draft(site_id: str) -> None:
    oid = _create_draft(site_id)
    try:
        cancel = client.post(
            f"/api/v1/farms/OR001/observations/{oid}/cancel",
            headers={"X-User-Id": "TEST"},
        )
        assert cancel.status_code == 200, cancel.text

        drafts = client.get("/api/v1/farms/OR001/observations/drafts").json()
        assert all(x["obs_id"] != oid for x in drafts)

        detail = client.get(f"/api/v1/farms/OR001/observations/{oid}")
        assert detail.status_code == 404
    finally:
        _delete_obs("OR001", oid)


def test_soft_delete_completed(site_id: str) -> None:
    oid = _create_draft(site_id)
    try:
        client.post(
            f"/api/v1/farms/OR001/observations/{oid}/complete",
            headers={"X-User-Id": "TEST"},
        )
        deleted = client.delete(
            f"/api/v1/farms/OR001/observations/{oid}",
            headers={"X-User-Id": "TEST"},
            params={"delete_reason": "테스트 삭제"},
        )
        assert deleted.status_code == 200, deleted.text
        assert "삭제" in deleted.json()["message"]

        listed = client.get("/api/v1/farms/OR001/observations?limit=200").json()
        assert all(x["obs_id"] != oid for x in listed)

        detail = client.get(f"/api/v1/farms/OR001/observations/{oid}")
        assert detail.status_code == 404

        # 사진 DB 잔여 없음
        with get_sqlite_connection(get_settings().sqlite_path) as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS cnt FROM t_observation_photo
                WHERE farm_cd = ? AND obs_id = ?
                """,
                ("OR001", oid),
            ).fetchone()
            assert int(row["cnt"] or 0) == 0
    finally:
        _delete_obs("OR001", oid)


def test_delete_forbidden_for_other_user(site_id: str) -> None:
    oid = _create_draft(site_id)
    try:
        client.post(
            f"/api/v1/farms/OR001/observations/{oid}/complete",
            headers={"X-User-Id": "TEST"},
        )
        res = client.delete(
            f"/api/v1/farms/OR001/observations/{oid}",
            headers={"X-User-Id": "OTHER_USER"},
        )
        assert res.status_code == 400
        # 여전히 조회 가능
        assert client.get(f"/api/v1/farms/OR001/observations/{oid}").status_code == 200
    finally:
        _delete_obs("OR001", oid)


def test_other_farm_blocked(site_id: str) -> None:
    oid = _create_draft(site_id)
    try:
        res = client.get(f"/api/v1/farms/OR999/observations/{oid}")
        assert res.status_code in (404, 400)
    finally:
        _delete_obs("OR001", oid)


def test_summary_excludes_draft(site_id: str) -> None:
    """DRAFT는 오늘 관찰·AI 대기 등 통계에 포함되지 않는다."""
    before = client.get(
        "/api/v1/farms/OR001/observations/summary?as_of_date=2026-07-17"
    ).json()
    oid = _create_draft(site_id)
    try:
        after = client.get(
            "/api/v1/farms/OR001/observations/summary?as_of_date=2026-07-17"
        ).json()
        assert after["today_count"] == before["today_count"]
        assert after["danger_count"] == before["danger_count"]
        assert after["fruit_count"] == before["fruit_count"]
        assert after["ai_pending_count"] == before["ai_pending_count"]
    finally:
        _delete_obs("OR001", oid)
