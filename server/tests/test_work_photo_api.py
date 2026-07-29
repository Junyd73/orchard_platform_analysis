# -*- coding: utf-8 -*-
"""작업 결과 사진 API 테스트 (Phase1 CRUD)."""

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
from core.work_photo_policy import WORK_PHOTO_MAX_COUNT
from core.work_photo_schema import ensure_work_photo_schema

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


def _create_temp_work(farm_cd: str = "OR001") -> str:
    wid = f"TWPH-{uuid.uuid4().hex[:10].upper()}"
    settings = get_settings()
    ensure_work_photo_schema(settings.sqlite_path)
    with get_sqlite_write_connection(settings.sqlite_path) as conn:
        cols = {
            str(r[1]).lower()
            for r in conn.execute("PRAGMA table_info(t_work_detail)").fetchall()
        }
        sample = conn.execute(
            """
            SELECT work_mid_cd, status_cd
            FROM t_work_detail
            WHERE farm_cd = ?
            LIMIT 1
            """,
            (farm_cd,),
        ).fetchone()
        mid = sample["work_mid_cd"] if sample else "WK010100"
        status = sample["status_cd"] if sample else "10"
        fields = ["farm_cd", "work_id", "work_dt", "work_mid_cd", "status_cd"]
        vals: list = [farm_cd, wid, "20260722", mid, status]
        if "use_yn" in cols:
            fields.append("use_yn")
            vals.append("Y")
        if "reg_id" in cols:
            fields.append("reg_id")
            vals.append("TEST")
        placeholders = ",".join("?" for _ in fields)
        conn.execute(
            f"INSERT INTO t_work_detail ({','.join(fields)}) VALUES ({placeholders})",
            tuple(vals),
        )
        conn.commit()
    return wid


def _cleanup_temp_work(farm_cd: str, work_id: str) -> None:
    settings = get_settings()
    with get_sqlite_write_connection(settings.sqlite_path) as conn:
        conn.execute(
            "DELETE FROM t_work_photo WHERE farm_cd = ? AND work_id = ?",
            (farm_cd, work_id),
        )
        conn.execute(
            "DELETE FROM t_work_detail WHERE farm_cd = ? AND work_id = ?",
            (farm_cd, work_id),
        )
        conn.commit()


@pytest.fixture
def work_photo_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    if not _has_farm("OR001"):
        pytest.skip("OR001 없음")
    media = tmp_path / "work_photos"
    media.mkdir()
    monkeypatch.setenv("WORK_MEDIA_ROOT", str(media))
    get_settings.cache_clear()
    wid = _create_temp_work("OR001")
    yield "OR001", wid, media
    _cleanup_temp_work("OR001", wid)
    get_settings.cache_clear()


def test_list_work_photos_empty(work_photo_env) -> None:
    farm, wid, _media = work_photo_env
    res = client.get(f"/api/v1/farms/{farm}/work-logs/works/{wid}/photos")
    assert res.status_code == 200
    body = res.json()
    assert body["work_id"] == wid
    assert body["count"] == 0
    assert body["max_count"] == WORK_PHOTO_MAX_COUNT
    assert body["remaining"] == WORK_PHOTO_MAX_COUNT


def test_upload_and_delete_work_photo(work_photo_env) -> None:
    farm, wid, media = work_photo_env
    res = client.post(
        f"/api/v1/farms/{farm}/work-logs/works/{wid}/photos",
        files=[("files", ("a.png", _png_bytes(), "image/png"))],
        headers={"X-User-Id": "TEST"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["success"] is True
    assert body["count"] == 1
    assert len(body["uploaded"]) == 1
    pid = body["uploaded"][0]["photo_id"]
    assert (media / farm).exists() or any(media.rglob("*.png"))

    thumb = client.get(
        f"/api/v1/farms/{farm}/work-logs/works/{wid}/photos/{pid}/thumbnail"
    )
    assert thumb.status_code == 200

    deleted = client.delete(
        f"/api/v1/farms/{farm}/work-logs/works/{wid}/photos/{pid}",
        headers={"X-User-Id": "TEST"},
    )
    assert deleted.status_code == 200
    listed = client.get(f"/api/v1/farms/{farm}/work-logs/works/{wid}/photos")
    assert listed.status_code == 200
    assert listed.json()["count"] == 0


def test_upload_requires_saved_work(work_photo_env) -> None:
    farm, _wid, _media = work_photo_env
    missing = f"MISSING-{uuid.uuid4().hex[:8].upper()}"
    res = client.post(
        f"/api/v1/farms/{farm}/work-logs/works/{missing}/photos",
        files=[("files", ("a.png", _png_bytes(), "image/png"))],
        headers={"X-User-Id": "TEST"},
    )
    assert res.status_code in (404, 400, 422)
