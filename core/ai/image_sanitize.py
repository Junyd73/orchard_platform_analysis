# -*- coding: utf-8 -*-
"""관찰 사진 AI 전송 전 안전 처리: EXIF 제거·축소·JPEG 변환(메모리)."""

from __future__ import annotations

import base64
from pathlib import Path

MAX_PHOTOS_PER_ANALYSIS = 3
MAX_LONG_EDGE_PX = 1600
JPEG_QUALITY = 85


def sanitize_image_to_jpeg_bytes(
    src_path: str | Path,
    *,
    max_long_edge: int = MAX_LONG_EDGE_PX,
    quality: int = JPEG_QUALITY,
) -> tuple[bool, str, bytes | None]:
    """EXIF/GPS 제거 후 긴 변 축소 JPEG 바이트 반환."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QImage, QImageReader

    path = Path(src_path)
    if not path.is_file():
        return False, "파일이 없습니다.", None

    reader = QImageReader(str(path))
    reader.setAutoTransform(True)
    img = reader.read()
    if img.isNull():
        return False, "이미지를 읽을 수 없습니다.", None

    # 메타 없는 새 이미지로 복사(EXIF 제거)
    clean = QImage(img.size(), QImage.Format.Format_RGB32)
    clean.fill(0)
    from PyQt6.QtGui import QPainter

    painter = QPainter(clean)
    painter.drawImage(0, 0, img)
    painter.end()

    w, h = clean.width(), clean.height()
    long_edge = max(w, h)
    if long_edge > max_long_edge and long_edge > 0:
        scale = max_long_edge / float(long_edge)
        nw = max(1, int(w * scale))
        nh = max(1, int(h * scale))
        clean = clean.scaled(
            nw,
            nh,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

    from PyQt6.QtCore import QBuffer, QIODevice

    qbuf = QBuffer()
    qbuf.open(QIODevice.OpenModeFlag.WriteOnly)
    ok = clean.save(qbuf, "JPG", quality)
    qbuf.close()
    if not ok:
        return False, "JPEG 변환에 실패했습니다.", None
    data = bytes(qbuf.data())
    if not data:
        return False, "변환 결과가 비어 있습니다.", None
    return True, "", data


def to_data_url_jpeg(jpeg_bytes: bytes) -> str:
    b64 = base64.b64encode(jpeg_bytes).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"


def prepare_images_for_ai(
    paths: list[str],
) -> tuple[bool, str, list[dict]]:
    """경로 목록 → [{path_label, data_url}] (최대 3장). 개인정보·절대경로 미포함."""
    selected = [p for p in (paths or []) if str(p or "").strip()][:MAX_PHOTOS_PER_ANALYSIS]
    if not selected:
        return False, "분석할 사진을 선택해 주세요.", []
    out: list[dict] = []
    for i, src in enumerate(selected, start=1):
        ok, msg, data = sanitize_image_to_jpeg_bytes(src)
        if not ok or not data:
            return False, f"{Path(src).name}: {msg}", []
        out.append(
            {
                "label": f"photo_{i}",
                "filename": Path(src).name,
                "data_url": to_data_url_jpeg(data),
                "byte_size": len(data),
            }
        )
    return True, "", out
