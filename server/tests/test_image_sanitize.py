# -*- coding: utf-8 -*-
"""AI 사진 sanitize — Pillow 경로 (headless 서버 호환)."""

from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest
from PIL import Image

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.append(str(_REPO_ROOT))

from core.ai.image_sanitize import (  # noqa: E402
    MAX_LONG_EDGE_PX,
    prepare_images_for_ai,
    sanitize_image_to_jpeg_bytes,
    to_data_url_jpeg,
)


def _write_png(path: Path, size: tuple[int, int] = (200, 120)) -> None:
    Image.new("RGB", size, (40, 120, 60)).save(path, format="PNG")


def test_sanitize_jpeg_bytes_and_strip_to_jpeg(tmp_path: Path) -> None:
    src = tmp_path / "leaf.png"
    _write_png(src, (2000, 1000))
    ok, msg, data = sanitize_image_to_jpeg_bytes(src)
    assert ok is True
    assert msg == ""
    assert data
    assert data[:2] == b"\xff\xd8"  # JPEG SOI
    with Image.open(io.BytesIO(data)) as img:
        assert max(img.size) <= MAX_LONG_EDGE_PX
        assert img.format == "JPEG"


def test_sanitize_missing_file(tmp_path: Path) -> None:
    ok, msg, data = sanitize_image_to_jpeg_bytes(tmp_path / "nope.jpg")
    assert ok is False
    assert data is None
    assert "없" in msg


def test_prepare_images_for_ai_data_url(tmp_path: Path) -> None:
    p1 = tmp_path / "a.jpg"
    p2 = tmp_path / "b.jpg"
    Image.new("RGB", (80, 60), (1, 2, 3)).save(p1, format="JPEG")
    Image.new("RGB", (90, 70), (4, 5, 6)).save(p2, format="JPEG")
    ok, msg, images = prepare_images_for_ai([str(p1), str(p2)])
    assert ok is True
    assert msg == ""
    assert len(images) == 2
    assert images[0]["data_url"].startswith("data:image/jpeg;base64,")
    assert "orchard" not in images[0]["data_url"].lower()
    assert str(tmp_path) not in images[0]["data_url"]
    assert to_data_url_jpeg(b"abc").startswith("data:image/jpeg;base64,")


def test_prepare_images_empty() -> None:
    ok, msg, images = prepare_images_for_ai([])
    assert ok is False
    assert images == []
    assert msg
