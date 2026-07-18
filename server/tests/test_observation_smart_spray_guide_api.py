# -*- coding: utf-8 -*-
"""스마트 방제 가이드 REST API 테스트."""

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
from app.services.observation_smart_spray_guide_api_service import (
    ObservationSmartSprayGuideApiService,
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


def _create_obs(farm_cd: str = "OR001") -> str:
    oid = f"TSG-{uuid.uuid4().hex[:10].upper()}"
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
                ?, ?, date('now'), '스마트방제가이드API테스트',
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
    return oid


def _cleanup(farm_cd: str, obs_id: str) -> None:
    settings = get_settings()
    with get_sqlite_write_connection(settings.sqlite_path) as conn:
        conn.execute(
            "DELETE FROM t_observation_pesticide_snapshot WHERE farm_cd=? AND obs_id=?",
            (farm_cd, obs_id),
        )
        conn.execute(
            "DELETE FROM t_observation_ai_candidate WHERE farm_cd=? AND analysis_id LIKE ?",
            (farm_cd, f"%{obs_id}%"),
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


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


@pytest.mark.skipif(not _has_farm("OR001"), reason="OR001 농장 없음")
def test_smart_spray_guide_no_candidate():
    farm = "OR001"
    oid = _create_obs(farm)
    try:
        settings = get_settings()
        svc = ObservationSmartSprayGuideApiService(
            db_path=settings.sqlite_path,
            photo_repo=deps.get_observation_photo_repository(),
        )
        app.dependency_overrides[deps.get_observation_smart_spray_guide_api_service] = (
            lambda: svc
        )
        r = client.get(f"/api/v1/farms/{farm}/observations/{oid}/smart-spray-guide")
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert body["guide_status"] == "NO_CANDIDATE"
        assert body["items"] == []
        assert body["observation"]["obs_id"] == oid
    finally:
        _cleanup(farm, oid)


@pytest.mark.skipif(not _has_farm("OR001"), reason="OR001 농장 없음")
def test_smart_spray_guide_with_mocked_payload():
    farm = "OR001"
    oid = _create_obs(farm)
    try:
        settings = get_settings()
        svc = ObservationSmartSprayGuideApiService(
            db_path=settings.sqlite_path,
            photo_repo=deps.get_observation_photo_repository(),
        )
        app.dependency_overrides[deps.get_observation_smart_spray_guide_api_service] = (
            lambda: svc
        )
        fake = {
            "ok": True,
            "guide_status": "READY",
            "farm_cd": farm,
            "obs_id": oid,
            "observation": {
                "obs_id": oid,
                "farm_cd": farm,
                "obs_title": "t",
                "ai_status": "CONFIRMED",
            },
            "confirmed_candidate": {
                "analysis_id": "A1",
                "candidate_seq": 1,
                "confirmed_name": "검은별무늬병",
                "name_ko": "검은별무늬병",
            },
            "psis_status": "CACHED",
            "crop_name": "배",
            "disease_name": "검은별무늬병",
            "items": [
                {
                    "rank": 1,
                    "snapshot_id": "S1",
                    "pesticide_name": "테스트농약",
                    "brand_name": "브랜드",
                    "active_ingredient": "성분",
                    "crop_name": "배",
                    "disease_name": "검은별무늬병",
                    "purpose": "살균",
                    "stock_qty": 3,
                    "stock_unit": "낱개",
                    "has_stock": True,
                    "last_used_date": "2026-07-01",
                    "dilution": "1000배",
                    "phi": "7일",
                    "max_use_count": "3",
                    "usage_method": "경엽살포",
                    "toxicity": "보통",
                    "from_psis": True,
                    "from_stock": True,
                    "psis_registered": True,
                    "information_available": True,
                    "match_level": "MATCH",
                    "match_key": "psis_pesti_code",
                }
            ],
            "error_code": None,
            "error_message": None,
        }
        with patch.object(
            ObservationSmartSprayGuideApiService,
            "get_guide",
            return_value=svc._to_response(fake),
        ):
            # call mapping path via _to_response directly
            mapped = svc._to_response(fake)
            assert mapped.success is True
            assert mapped.guide_status == "READY"
            assert mapped.items[0].has_stock is True
            assert mapped.items[0].phi == "7일"
            assert mapped.confirmed_candidate.confirmed_name == "검은별무늬병"

        r = client.get(f"/api/v1/farms/{farm}/observations/{oid}/smart-spray-guide")
        assert r.status_code == 200
    finally:
        _cleanup(farm, oid)


@pytest.mark.skipif(not _has_farm("OR001"), reason="OR001 농장 없음")
def test_smart_spray_guide_not_found():
    settings = get_settings()
    svc = ObservationSmartSprayGuideApiService(
        db_path=settings.sqlite_path,
        photo_repo=deps.get_observation_photo_repository(),
    )
    app.dependency_overrides[deps.get_observation_smart_spray_guide_api_service] = (
        lambda: svc
    )
    r = client.get("/api/v1/farms/OR001/observations/NO-SUCH-OBS/smart-spray-guide")
    assert r.status_code == 404
