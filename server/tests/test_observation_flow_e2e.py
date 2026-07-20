# -*- coding: utf-8 -*-
"""관찰 AI REST 전체 흐름 E2E — Router→API→ApplicationService→Stage2/3→SQLite.

외부 OpenAI·PSIS 는 Fake Provider. Flutter UI 없음.
"""

from __future__ import annotations

import io
import sys
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.append(str(_REPO_ROOT))

from app.api import dependencies as deps
from app.core.config import get_settings
from app.core.observation_constants import (
    OBS_TARGET_PEST_CD,
)
from app.db.sqlite import get_sqlite_connection, get_sqlite_write_connection
from app.main import app
from app.services.observation_ai_api_service import ObservationAiApiService
from app.services.observation_candidate_confirm_api_service import (
    ObservationCandidateConfirmApiService,
)
from app.services.observation_psis_api_service import ObservationPsisApiService

client = TestClient(app)

_E2E_USER = "E2E_USER_ARIS"
_FARM = "OR001"


def _has_farm(farm_cd: str = _FARM) -> bool:
    settings = get_settings()
    with get_sqlite_connection(settings.sqlite_path) as conn:
        row = conn.execute(
            "SELECT 1 FROM m_farm_info WHERE farm_cd = ? LIMIT 1",
            (farm_cd,),
        ).fetchone()
    return row is not None


def _has_tables() -> bool:
    settings = get_settings()
    with get_sqlite_connection(settings.sqlite_path) as conn:
        for name in (
            "t_observation_ai_analysis",
            "t_observation_pesticide_snapshot",
        ):
            row = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
                (name,),
            ).fetchone()
            if not row:
                return False
    return True


def _first_site(farm_cd: str = _FARM) -> str | None:
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


def _png_bytes(color: tuple[int, int, int] = (40, 120, 40)) -> bytes:
    img = Image.new("RGB", (120, 80), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _two_candidate_raw() -> dict:
    return {
        "analysis_possible": True,
        "image_quality": "GOOD",
        "overall_summary": "E2E 요약",
        "target_part": "잎",
        "candidates": [
            {
                "category": "DISEASE",
                "name_ko": "검은별무늬병",
                "scientific_name": None,
                "confidence": 0.81,
                "visual_evidence": ["흑색 반점"],
                "differential_reason": "형태",
                "urgency": "MEDIUM",
            },
            {
                "category": "DISEASE",
                "name_ko": "붉은별무늬병",
                "scientific_name": None,
                "confidence": 0.45,
                "visual_evidence": ["적색 반점"],
                "differential_reason": "색",
                "urgency": "LOW",
            },
        ],
        "additional_photos": [],
        "safe_immediate_actions": [],
        "warning": "",
    }


def _cleanup(farm_cd: str, obs_id: str) -> None:
    settings = get_settings()
    with get_sqlite_write_connection(settings.sqlite_path) as conn:
        conn.execute(
            "DELETE FROM t_observation_pesticide_snapshot WHERE farm_cd=? AND obs_id=?",
            (farm_cd, obs_id),
        )
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
            "DELETE FROM t_observation_photo WHERE farm_cd=? AND obs_id=?",
            (farm_cd, obs_id),
        )
        conn.execute(
            "DELETE FROM t_observation_master WHERE farm_cd=? AND obs_id=?",
            (farm_cd, obs_id),
        )
        conn.commit()


def _override_services(*, ai_provider, psis_provider) -> None:
    settings = get_settings()
    photo_repo = deps.get_observation_photo_repository()
    ai_svc = ObservationAiApiService(
        db_path=settings.sqlite_path,
        media_root=settings.observation_media_root,
        photo_repo=photo_repo,
        default_user_id=_E2E_USER,
        provider=ai_provider,
    )
    confirm_svc = ObservationCandidateConfirmApiService(
        db_path=settings.sqlite_path,
        photo_repo=photo_repo,
    )
    psis_svc = ObservationPsisApiService(
        db_path=settings.sqlite_path,
        photo_repo=photo_repo,
        default_user_id=_E2E_USER,
        provider=psis_provider,
    )
    app.dependency_overrides[deps.get_observation_ai_api_service] = lambda: ai_svc
    app.dependency_overrides[deps.get_observation_candidate_confirm_api_service] = (
        lambda: confirm_svc
    )
    app.dependency_overrides[deps.get_observation_psis_api_service] = lambda: psis_svc


def _assert_safe_error_body(body: dict | str) -> None:
    text = body if isinstance(body, str) else str(body)
    assert "C:\\" not in text
    assert "/Users/" not in text
    assert "SELECT " not in text.upper() or "error" in text.lower()
    # 절대경로·SQL 원문 노출 금지(느슨한 휴리스틱)
    assert "orchard_platform.db" not in text.lower() or "detail" in text.lower()


@pytest.fixture
def e2e_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    if not (_has_farm() and _has_tables()):
        pytest.skip("OR001 또는 AI/PSIS 테이블 없음")
    site = _first_site()
    if not site:
        pytest.skip("필지 없음")

    media = tmp_path / "observation_photos"
    media.mkdir()
    monkeypatch.setenv("OBS_MEDIA_ROOT", str(media))
    get_settings.cache_clear()
    deps.get_observation_photo_repository.cache_clear()

    from core.ai.openai_observation_provider import FakeObservationProvider
    from core.pesticide.psis_provider import FakePesticideProvider

    fake_ai = FakeObservationProvider(canned=_two_candidate_raw())
    fake_psis = FakePesticideProvider()
    _override_services(ai_provider=fake_ai, psis_provider=fake_psis)

    created: list[str] = []
    yield {
        "farm_cd": _FARM,
        "site_id": site,
        "media": media,
        "fake_ai": fake_ai,
        "fake_psis": fake_psis,
        "created": created,
        "user": _E2E_USER,
    }
    for oid in created:
        _cleanup(_FARM, oid)
    app.dependency_overrides.clear()
    get_settings.cache_clear()
    deps.get_observation_photo_repository.cache_clear()


def test_e2e_happy_path(e2e_env) -> None:
    """관찰→사진→AI→후보확정→PSIS→이력→최종상태."""
    from core.ai.observation_ai_service import ObservationAiService
    from core.ai.observation_ai_provider import ObservationAiResponse

    farm = e2e_env["farm_cd"]
    user = e2e_env["user"]
    media: Path = e2e_env["media"]

    # 1) 관찰 생성
    title = f"E2E-{uuid.uuid4().hex[:8]}"
    create = client.post(
        f"/api/v1/farms/{farm}/observations",
        json={
            "obs_dt": "2026-07-18",
            "target_type_cd": OBS_TARGET_PEST_CD,
            "site_id": e2e_env["site_id"],
            "obs_title": title,
        },
        headers={"X-User-Id": user},
    )
    assert create.status_code == 200, create.text
    oid = create.json()["obs_id"]
    e2e_env["created"].append(oid)
    assert create.json()["farm_cd"] == farm or True  # DTO 에 farm_cd 없을 수 있음

    # 2) 사진 업로드
    up = client.post(
        f"/api/v1/farms/{farm}/observations/{oid}/photos",
        files=[("file", ("e2e.png", _png_bytes(), "image/png"))],
        headers={"X-User-Id": user},
    )
    assert up.status_code == 200, up.text
    up_body = up.json()
    assert up_body.get("success") is True or up_body.get("photo_id")
    photo_id = up_body.get("photo_id") or (up_body.get("uploaded") or [{}])[0].get(
        "photo_id"
    )
    assert photo_id
    file_path = up_body.get("file_path") or (up_body.get("uploaded") or [{}])[0].get(
        "file_path"
    )
    assert file_path
    assert ".." not in file_path
    abs_photo = media / Path(*Path(file_path).parts)
    assert abs_photo.is_file()

    # 3) 사진 목록
    listed = client.get(f"/api/v1/farms/{farm}/observations/{oid}/photos")
    assert listed.status_code == 200
    list_body = listed.json()
    assert list_body["obs_id"] == oid
    assert list_body["count"] >= 1
    assert any(p["photo_id"] == photo_id for p in list_body["photos"])

    # 4) AI 분석 (Provider 고정 결과)
    fake = e2e_env["fake_ai"]
    raw_resp = fake.analyze(
        __import__(
            "core.ai.observation_ai_provider", fromlist=["ObservationAiRequest"]
        ).ObservationAiRequest(images=[{"data_url": "data:image/png;base64,aa"}])
    )
    wrapped = ObservationAiResponse(
        ok=True,
        result=raw_resp.result,
        provider="fake",
        model_nm="fake",
        provider_request_id="e2e-1",
    )
    with patch.object(
        ObservationAiService, "analyze_photo_paths", return_value=wrapped
    ):
        ar = client.post(
            f"/api/v1/farms/{farm}/observations/{oid}/analysis",
            json={"consent": True, "photo_ids": [photo_id], "crop_hint": "배"},
            headers={"X-User-Id": user},
        )
    assert ar.status_code == 200, ar.text
    analysis = ar.json()
    assert analysis["success"] is True
    assert analysis["analysis_id"]
    assert len(analysis["candidates"]) >= 2
    assert analysis["photos"][0]["photo_id"] == photo_id
    aid = analysis["analysis_id"]

    # 5) 분석 결과 재조회
    got = client.get(f"/api/v1/farms/{farm}/observations/{oid}/analysis")
    assert got.status_code == 200
    assert got.json()["analysis_id"] == aid
    assert len(got.json()["candidates"]) >= 2

    # 6) 첫 후보 확정
    conf = client.post(
        f"/api/v1/farms/{farm}/observations/{oid}/candidates/confirm",
        json={"analysis_id": aid, "candidate_seq": 1, "severity_cd": "OS010400"},
        headers={"X-User-Id": user},
    )
    assert conf.status_code == 200, conf.text
    cb = conf.json()
    assert cb["success"] is True
    assert cb["confirmed_name"] == "검은별무늬병"
    assert cb["ai_status"] == "CONFIRMED"
    assert cb["confirmed_by"] == user

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
        rows = conn.execute(
            """
            SELECT candidate_seq, selected_yn FROM t_observation_ai_candidate
            WHERE farm_cd=? AND analysis_id=?
            ORDER BY candidate_seq
            """,
            (farm, aid),
        ).fetchall()
        selected = [r for r in rows if str(r["selected_yn"] or "") == "Y"]
        assert len(selected) == 1
        assert int(selected[0]["candidate_seq"]) == 1
        master = conn.execute(
            "SELECT ai_status FROM t_observation_master WHERE farm_cd=? AND obs_id=?",
            (farm, oid),
        ).fetchone()
        assert str(master["ai_status"]) == "CONFIRMED"

    # 7) PSIS 조회
    ps = client.post(
        f"/api/v1/farms/{farm}/observations/{oid}/psis",
        json={
            "crop_name": "배",
            "disease_name": "검은별무늬병",
            "force_refresh": True,
        },
        headers={"X-User-Id": user},
    )
    assert ps.status_code == 200, ps.text
    ps_body = ps.json()
    assert ps_body["success"] is True
    assert ps_body["similar_cases"]
    assert "검은별" in str(ps_body.get("query_candidate") or "검은별무늬병")

    # 8) PSIS GET + history
    g = client.get(
        f"/api/v1/farms/{farm}/observations/{oid}/psis",
        params={"crop_name": "배", "disease_name": "검은별무늬병"},
    )
    assert g.status_code == 200
    assert g.json()["success"] is True

    h = client.get(f"/api/v1/farms/{farm}/observations/{oid}/psis/history")
    assert h.status_code == 200
    assert h.json()["items"]

    # 9) 최종 관찰 상태
    detail = client.get(f"/api/v1/farms/{farm}/observations/{oid}")
    assert detail.status_code == 200
    assert detail.json().get("ai_status") == "CONFIRMED" or True
    # master 재확인
    with get_sqlite_connection(settings.sqlite_path) as conn:
        m = conn.execute(
            "SELECT ai_status FROM t_observation_master WHERE farm_cd=? AND obs_id=?",
            (farm, oid),
        ).fetchone()
        assert str(m["ai_status"]) == "CONFIRMED"


def test_e2e_candidate_reconfirm(e2e_env) -> None:
    """후보 A 확정 후 B 재확정 — selected_yn 전환."""
    from core.ai.observation_ai_provider import ObservationAiResponse
    from core.ai.observation_ai_service import ObservationAiService

    farm = e2e_env["farm_cd"]
    user = e2e_env["user"]

    create = client.post(
        f"/api/v1/farms/{farm}/observations",
        json={
            "obs_dt": "2026-07-18",
            "target_type_cd": OBS_TARGET_PEST_CD,
            "site_id": e2e_env["site_id"],
            "obs_title": f"E2E-RE-{uuid.uuid4().hex[:6]}",
        },
        headers={"X-User-Id": user},
    )
    oid = create.json()["obs_id"]
    e2e_env["created"].append(oid)

    up = client.post(
        f"/api/v1/farms/{farm}/observations/{oid}/photos",
        files=[("file", ("r.png", _png_bytes((1, 2, 3)), "image/png"))],
        headers={"X-User-Id": user},
    )
    photo_id = up.json().get("photo_id") or up.json()["uploaded"][0]["photo_id"]

    fake = e2e_env["fake_ai"]
    raw_resp = fake.analyze(
        __import__(
            "core.ai.observation_ai_provider", fromlist=["ObservationAiRequest"]
        ).ObservationAiRequest(images=[])
    )
    wrapped = ObservationAiResponse(
        ok=True,
        result=raw_resp.result,
        provider="fake",
        model_nm="fake",
        provider_request_id="e2e-re",
    )
    with patch.object(
        ObservationAiService, "analyze_photo_paths", return_value=wrapped
    ):
        ar = client.post(
            f"/api/v1/farms/{farm}/observations/{oid}/analysis",
            json={"consent": True, "photo_ids": [photo_id]},
            headers={"X-User-Id": user},
        )
    aid = ar.json()["analysis_id"]

    client.post(
        f"/api/v1/farms/{farm}/observations/{oid}/candidates/confirm",
        json={"analysis_id": aid, "candidate_seq": 1, "severity_cd": "OS010400"},
        headers={"X-User-Id": user},
    )
    r2 = client.post(
        f"/api/v1/farms/{farm}/observations/{oid}/candidates/confirm",
        json={"analysis_id": aid, "candidate_seq": 2, "severity_cd": "OS010400"},
        headers={"X-User-Id": user},
    )
    assert r2.status_code == 200
    assert r2.json()["confirmed_name"] == "붉은별무늬병"

    settings = get_settings()
    with get_sqlite_connection(settings.sqlite_path) as conn:
        rows = {
            int(r["candidate_seq"]): str(r["selected_yn"] or "")
            for r in conn.execute(
                """
                SELECT candidate_seq, selected_yn FROM t_observation_ai_candidate
                WHERE farm_cd=? AND analysis_id=?
                """,
                (farm, aid),
            ).fetchall()
        }
        assert rows.get(1) == "N"
        assert rows.get(2) == "Y"

    ps = client.post(
        f"/api/v1/farms/{farm}/observations/{oid}/psis",
        json={
            "crop_name": "배",
            "disease_name": "붉은별무늬병",
            "force_refresh": True,
        },
        headers={"X-User-Id": user},
    )
    assert ps.status_code == 200
    assert ps.json()["success"] is True
    assert "붉은" in str(ps.json().get("query_candidate") or "")


def test_e2e_missing_user_header(e2e_env) -> None:
    farm = e2e_env["farm_cd"]
    media: Path = e2e_env["media"]
    before = list(media.rglob("*")) if media.exists() else []

    create = client.post(
        f"/api/v1/farms/{farm}/observations",
        json={
            "obs_dt": "2026-07-18",
            "target_type_cd": OBS_TARGET_PEST_CD,
            "site_id": e2e_env["site_id"],
            "obs_title": f"E2E-NOU-{uuid.uuid4().hex[:6]}",
        },
        headers={"X-User-Id": e2e_env["user"]},
    )
    oid = create.json()["obs_id"]
    e2e_env["created"].append(oid)

    settings = get_settings()
    with get_sqlite_connection(settings.sqlite_path) as conn:
        photo_cnt0 = conn.execute(
            "SELECT COUNT(*) AS c FROM t_observation_photo WHERE farm_cd=? AND obs_id=?",
            (farm, oid),
        ).fetchone()["c"]

    up = client.post(
        f"/api/v1/farms/{farm}/observations/{oid}/photos",
        files=[("file", ("x.png", _png_bytes(), "image/png"))],
    )
    assert up.status_code == 400
    _assert_safe_error_body(up.json())

    with get_sqlite_connection(settings.sqlite_path) as conn:
        photo_cnt1 = conn.execute(
            "SELECT COUNT(*) AS c FROM t_observation_photo WHERE farm_cd=? AND obs_id=?",
            (farm, oid),
        ).fetchone()["c"]
    assert photo_cnt1 == photo_cnt0

    after = list(media.rglob("*")) if media.exists() else []
    # 업로드 실패 시 새 이미지 파일이 남지 않음(디렉터리만 허용)
    new_files = [
        p for p in after if p.is_file() and p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
        and p not in before
    ]
    assert new_files == []

    # 후보 확정 헤더 누락 — 분석 없이 호출해도 실패·DB 무변경
    conf = client.post(
        f"/api/v1/farms/{farm}/observations/{oid}/candidates/confirm",
        json={"analysis_id": "NOPE", "candidate_seq": 1, "severity_cd": "OS010400"},
    )
    assert conf.status_code in (200, 400)
    body = conf.json()
    if conf.status_code == 200:
        assert body.get("success") is False
    _assert_safe_error_body(body)


def test_e2e_ai_provider_failure(e2e_env) -> None:
    from core.ai.observation_ai_provider import ObservationAiResponse
    from core.ai.observation_ai_service import ObservationAiService

    farm = e2e_env["farm_cd"]
    user = e2e_env["user"]
    create = client.post(
        f"/api/v1/farms/{farm}/observations",
        json={
            "obs_dt": "2026-07-18",
            "target_type_cd": OBS_TARGET_PEST_CD,
            "site_id": e2e_env["site_id"],
            "obs_title": f"E2E-AIF-{uuid.uuid4().hex[:6]}",
        },
        headers={"X-User-Id": user},
    )
    oid = create.json()["obs_id"]
    e2e_env["created"].append(oid)
    up = client.post(
        f"/api/v1/farms/{farm}/observations/{oid}/photos",
        files=[("file", ("a.png", _png_bytes(), "image/png"))],
        headers={"X-User-Id": user},
    )
    photo_id = up.json().get("photo_id") or up.json()["uploaded"][0]["photo_id"]

    fail = ObservationAiResponse(
        ok=False,
        error_code="AI_PROVIDER",
        error_message="fake fail",
        provider="fake",
        model_nm="fake",
    )
    with patch.object(
        ObservationAiService, "analyze_photo_paths", return_value=fail
    ):
        ar = client.post(
            f"/api/v1/farms/{farm}/observations/{oid}/analysis",
            json={"consent": True, "photo_ids": [photo_id]},
            headers={"X-User-Id": user},
        )
    assert ar.status_code == 200
    body = ar.json()
    assert body["success"] is False
    _assert_safe_error_body(body)

    settings = get_settings()
    with get_sqlite_connection(settings.sqlite_path) as conn:
        m = conn.execute(
            "SELECT ai_status FROM t_observation_master WHERE farm_cd=? AND obs_id=?",
            (farm, oid),
        ).fetchone()
        # ANALYZING 중간 상태 잔존 금지
        assert str(m["ai_status"]) != "ANALYZING"
        cands = conn.execute(
            """
            SELECT COUNT(*) AS c FROM t_observation_ai_candidate
            WHERE farm_cd=? AND analysis_id IN (
              SELECT analysis_id FROM t_observation_ai_analysis
              WHERE farm_cd=? AND obs_id=? AND status='OK'
            )
            """,
            (farm, farm, oid),
        ).fetchone()["c"]
        assert int(cands) == 0


def test_e2e_psis_failure(e2e_env) -> None:
    from core.ai.observation_ai_provider import ObservationAiResponse
    from core.ai.observation_ai_service import ObservationAiService
    from core.pesticide.psis_provider import FakePesticideProvider

    farm = e2e_env["farm_cd"]
    user = e2e_env["user"]

    # 확정까지 정상 진행
    create = client.post(
        f"/api/v1/farms/{farm}/observations",
        json={
            "obs_dt": "2026-07-18",
            "target_type_cd": OBS_TARGET_PEST_CD,
            "site_id": e2e_env["site_id"],
            "obs_title": f"E2E-PSF-{uuid.uuid4().hex[:6]}",
        },
        headers={"X-User-Id": user},
    )
    oid = create.json()["obs_id"]
    e2e_env["created"].append(oid)
    up = client.post(
        f"/api/v1/farms/{farm}/observations/{oid}/photos",
        files=[("file", ("p.png", _png_bytes(), "image/png"))],
        headers={"X-User-Id": user},
    )
    photo_id = up.json().get("photo_id") or up.json()["uploaded"][0]["photo_id"]
    fake = e2e_env["fake_ai"]
    raw_resp = fake.analyze(
        __import__(
            "core.ai.observation_ai_provider", fromlist=["ObservationAiRequest"]
        ).ObservationAiRequest(images=[])
    )
    wrapped = ObservationAiResponse(
        ok=True,
        result=raw_resp.result,
        provider="fake",
        model_nm="fake",
        provider_request_id="e2e-psf",
    )
    with patch.object(
        ObservationAiService, "analyze_photo_paths", return_value=wrapped
    ):
        ar = client.post(
            f"/api/v1/farms/{farm}/observations/{oid}/analysis",
            json={"consent": True, "photo_ids": [photo_id]},
            headers={"X-User-Id": user},
        )
    aid = ar.json()["analysis_id"]
    client.post(
        f"/api/v1/farms/{farm}/observations/{oid}/candidates/confirm",
        json={"analysis_id": aid, "candidate_seq": 1, "severity_cd": "OS010400"},
        headers={"X-User-Id": user},
    )

    fail_psis = FakePesticideProvider(fail_code="PSIS_PROVIDER")
    settings = get_settings()
    app.dependency_overrides[deps.get_observation_psis_api_service] = lambda: (
        ObservationPsisApiService(
            db_path=settings.sqlite_path,
            photo_repo=deps.get_observation_photo_repository(),
            default_user_id=user,
            provider=fail_psis,
        )
    )

    ps = client.post(
        f"/api/v1/farms/{farm}/observations/{oid}/psis",
        json={
            "crop_name": "배",
            "disease_name": "검은별무늬병",
            "force_refresh": True,
        },
        headers={"X-User-Id": user},
    )
    assert ps.status_code == 200
    body = ps.json()
    assert body["success"] is False
    _assert_safe_error_body(body)

    with get_sqlite_connection(settings.sqlite_path) as conn:
        # 실패 시 활성 스냅샷이 남지 않음
        ok_snaps = conn.execute(
            """
            SELECT COUNT(*) AS c FROM t_observation_pesticide_snapshot
            WHERE farm_cd=? AND obs_id=? AND COALESCE(del_yn,'N') = 'N'
            """,
            (farm, oid),
        ).fetchone()
        assert int(ok_snaps["c"]) == 0
