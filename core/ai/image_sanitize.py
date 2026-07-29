# -*- coding: utf-8 -*-
"""관찰 사진 AI 전송 전 안전 처리: EXIF 제거·축소·JPEG 변환(메모리).

PC·FastAPI 공통. Pillow 사용( headless 서버에서 PyQt6 불필요 ).
"""

from __future__ import annotations

import base64
import io
from pathlib import Path

MAX_PHOTOS_PER_ANALYSIS = 5
MAX_LONG_EDGE_PX = 1600
JPEG_QUALITY = 85

MSG_FILE_MISSING = "파일이 없습니다."
MSG_IMAGE_UNREADABLE = "이미지를 읽을 수 없습니다."
MSG_JPEG_FAIL = "JPEG 변환에 실패했습니다."
MSG_JPEG_EMPTY = "변환 결과가 비어 있습니다."
MSG_DEPENDENCY = "pillow 패키지가 설치되지 않았습니다."
MSG_SELECT_PHOTOS = "분석할 사진을 선택해 주세요."


def sanitize_image_to_jpeg_bytes(
    src_path: str | Path,
    *,
    max_long_edge: int = MAX_LONG_EDGE_PX,
    quality: int = JPEG_QUALITY,
) -> tuple[bool, str, bytes | None]:
    """EXIF/GPS 제거 후 긴 변 축소 JPEG 바이트 반환."""
    path = Path(src_path)
    if not path.is_file():
        return False, MSG_FILE_MISSING, None

    try:
        from PIL import Image, ImageOps
    except ImportError:
        return False, MSG_DEPENDENCY, None

    try:
        with Image.open(path) as opened:
            img = ImageOps.exif_transpose(opened)
            # EXIF 없는 새 버퍼용 복사
            img = img.copy()
        if img.mode != "RGB":
            img = img.convert("RGB")

        w, h = img.size
        if w <= 0 or h <= 0:
            return False, MSG_IMAGE_UNREADABLE, None

        long_edge = max(w, h)
        if long_edge > max_long_edge > 0:
            scale = max_long_edge / float(long_edge)
            nw = max(1, int(w * scale))
            nh = max(1, int(h * scale))
            img = img.resize((nw, nh), Image.Resampling.LANCZOS)

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=int(quality), optimize=True)
        data = buf.getvalue()
    except OSError:
        return False, MSG_IMAGE_UNREADABLE, None
    except Exception:
        return False, MSG_JPEG_FAIL, None

    if not data:
        return False, MSG_JPEG_EMPTY, None
    return True, "", data


def to_data_url_jpeg(jpeg_bytes: bytes) -> str:
    b64 = base64.b64encode(jpeg_bytes).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"


def prepare_images_for_ai(
    paths: list[str],
) -> tuple[bool, str, list[dict]]:
    """경로 목록 → [{label, data_url, …}] (최대 MAX_PHOTOS_PER_ANALYSIS장). 절대경로 미포함."""
    selected = [p for p in (paths or []) if str(p or "").strip()][:MAX_PHOTOS_PER_ANALYSIS]
    if not selected:
        return False, MSG_SELECT_PHOTOS, []
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
