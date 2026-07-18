# -*- coding: utf-8 -*-
"""관찰 사진 API 테스트 (SCR-002 사진 단계)."""

from __future__ import annotations

import io
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.api import dependencies as deps
from app.core.config import get_settings
from app.db.sqlite import get_sqlite_connection, get_sqlite_write_connection
from app.main import app
from app.services.observation_media import OBS_PHOTO_MAX_COUNT

client = TestClient(app)


def _has_farm(farm_cd: str) -> bool:
    settings = get_settings()
    with get_sqlite_connection(settings.sqlite_path) as conn:
        row = conn.execute(
            "SELECT 1 FROM m_farm_info WHERE farm_cd = ? LIMIT 1",
            (farm_cd,),
        ).fetchone()
    return row is not None


def _png_bytes(color: tuple[int, int, int] = (40, 120, 40)) -> bytes:
    img = Image.new("RGB", (120, 80), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _create_temp_observation(farm_cd: str = "OR001") -> str:
    """테스트 전용 관찰 1건 생성. 스키마 최소 컬럼만 사용."""
    oid = f"TPHOTO-{uuid.uuid4().hex[:10].upper()}"
    settings = get_settings()
    with get_sqlite_write_connection(settings.sqlite_path) as conn:
        # 기존 행에서 NOT NULL 컬럼 패턴 참고
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
                use_yn, reg_id, reg_dt, mod_id, mod_dt
            ) VALUES (
                ?, ?, date('now'), '사진API테스트',
                ?, ?, ?, ?,
                'Y', 'TEST', datetime('now'), 'TEST', datetime('now')
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


def _cleanup_temp_observation(farm_cd: str, obs_id: str) -> None:
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
def photo_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    if not _has_farm("OR001"):
        pytest.skip("OR001 없음")
    media = tmp_path / "observation_photos"
    media.mkdir()
    monkeypatch.setenv("OBS_MEDIA_ROOT", str(media))
    get_settings.cache_clear()
    deps.get_observation_photo_repository.cache_clear()
    oid = _create_temp_observation("OR001")
    yield "OR001", oid, media
    _cleanup_temp_observation("OR001", oid)
    get_settings.cache_clear()
    deps.get_observation_photo_repository.cache_clear()


def test_list_photos_empty(photo_env) -> None:
    farm, oid, _media = photo_env
    res = client.get(f"/api/v1/farms/{farm}/observations/{oid}/photos")
    assert res.status_code == 200
    body = res.json()
    assert body["obs_id"] == oid
    assert body["count"] == 0
    assert body["max_count"] == OBS_PHOTO_MAX_COUNT
    assert body["remaining"] == OBS_PHOTO_MAX_COUNT


def test_upload_delete_reorder_max5(photo_env) -> None:
    farm, oid, _media = photo_env

    files = [
        ("files", (f"t{i}.png", _png_bytes((10 * (i + 1), 20, 30)), "image/png"))
        for i in range(5)
    ]
    up = client.post(
        f"/api/v1/farms/{farm}/observations/{oid}/photos",
        files=files,
        headers={"X-User-Id": "TEST"},
    )
    assert up.status_code == 200, up.text
    body = up.json()
    assert body["count"] == 5
    assert body["remaining"] == 0
    assert len(body["uploaded"]) == 5
    assert body["uploaded"][0]["is_representative"] is True

    sixth = client.post(
        f"/api/v1/farms/{farm}/observations/{oid}/photos",
        files=[("files", ("x6.png", _png_bytes((200, 0, 0)), "image/png"))],
        headers={"X-User-Id": "TEST"},
    )
    assert sixth.status_code == 400
    assert "최대" in sixth.json()["detail"] or "남은" in sixth.json()["detail"]

    rep = client.get(
        f"/api/v1/farms/{farm}/observations/{oid}/photos/representative"
    )
    assert rep.status_code == 200
    assert rep.json()["photo_id"] == body["uploaded"][0]["photo_id"]

    ids = [p["photo_id"] for p in body["uploaded"]]
    new_order = [ids[-1]] + ids[:-1]
    ord_res = client.put(
        f"/api/v1/farms/{farm}/observations/{oid}/photos/order",
        json={"photo_ids": new_order},
        headers={"X-User-Id": "TEST"},
    )
    assert ord_res.status_code == 200
    ordered = ord_res.json()["photos"]
    assert ordered[0]["photo_id"] == ids[-1]
    assert ordered[0]["is_representative"] is True

    thumb = client.get(
        f"/api/v1/farms/{farm}/observations/{oid}/photos/{ids[0]}/thumbnail"
    )
    assert thumb.status_code == 200
    assert "image" in thumb.headers.get("content-type", "")

    del_res = client.delete(
        f"/api/v1/farms/{farm}/observations/{oid}/photos/{ordered[0]['photo_id']}",
        headers={"X-User-Id": "TEST"},
    )
    assert del_res.status_code == 200

    again = client.post(
        f"/api/v1/farms/{farm}/observations/{oid}/photos",
        files=[("files", ("again.png", _png_bytes((1, 2, 3)), "image/png"))],
        headers={"X-User-Id": "TEST"},
    )
    assert again.status_code == 200
    assert again.json()["count"] == 5


def test_photos_obs_not_found() -> None:
    if not _has_farm("OR001"):
        pytest.skip("OR001 없음")
    res = client.get("/api/v1/farms/OR001/observations/NO_SUCH_OBS/photos")
    assert res.status_code == 404


def test_upload_requires_user_header(photo_env) -> None:
    farm, oid, _media = photo_env
    res = client.post(
        f"/api/v1/farms/{farm}/observations/{oid}/photos",
        files=[("file", ("a.png", _png_bytes(), "image/png"))],
    )
    assert res.status_code == 400


def test_upload_rejects_empty_and_bad_type(photo_env) -> None:
    farm, oid, _media = photo_env
    empty = client.post(
        f"/api/v1/farms/{farm}/observations/{oid}/photos",
        files=[("file", ("e.png", b"", "image/png"))],
        headers={"X-User-Id": "TEST"},
    )
    assert empty.status_code == 400

    bad = client.post(
        f"/api/v1/farms/{farm}/observations/{oid}/photos",
        files=[("file", ("x.txt", b"not-an-image", "text/plain"))],
        headers={"X-User-Id": "TEST"},
    )
    assert bad.status_code == 400


def test_upload_strips_exif_and_single_file_field(photo_env) -> None:
    farm, oid, media = photo_env
    img = Image.new("RGB", (80, 60), (10, 20, 30))
    exif = img.getexif()
    exif[274] = 6  # Orientation
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif)
    raw = buf.getvalue()
    assert b"Exif" in raw or len(raw) > 100

    up = client.post(
        f"/api/v1/farms/{farm}/observations/{oid}/photos",
        files=[("file", ("orient.jpg", raw, "image/jpeg"))],
        headers={"X-User-Id": "TEST"},
    )
    assert up.status_code == 200, up.text
    body = up.json()
    assert body["success"] is True
    assert body["photo_id"]
    assert body["file_path"]
    assert body["thumbnail_path"]
    assert body["created_by"] == "TEST"

    abs_path = media / Path(*Path(body["file_path"]).parts)
    assert abs_path.is_file()
    with Image.open(abs_path) as stored:
        stored_exif = stored.getexif()
        # Orientation 등 EXIF 제거됨
        assert not stored_exif or 274 not in stored_exif
