# -*- coding: utf-8 -*-
"""관찰 사진 파일 저장소 (BLOB 금지, 사용자 데이터 영역 + 상대경로)."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import sys
import uuid
from pathlib import Path, PurePosixPath

OBS_PHOTO_MAX_BYTES = 20 * 1024 * 1024
OBS_THUMB_MAX_PX = 400
OBS_PHOTO_MAX_COUNT = 5
OBS_ALLOWED_EXTS = frozenset({".jpg", ".jpeg", ".png", ".webp"})
_SAFE_SEG = re.compile(r"^[A-Za-z0-9._\-]+$")


def observation_media_root() -> Path:
    """앱 사용자 데이터 루트/observation_photos (소스·Git·임시폴더 금지)."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home())
        root = Path(base) / "OrchardPlatform" / "observation_photos"
    else:
        root = Path.home() / ".local" / "share" / "OrchardPlatform" / "observation_photos"
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def _safe_seg(value: str, fallback: str = "X") -> str:
    s = str(value or "").strip()
    if not s or not _SAFE_SEG.match(s) or ".." in s:
        return fallback
    return s


def build_obs_photo_rel_dir(farm_cd: str, obs_id: str, year: str) -> str:
    """DB 저장용 relative POSIX 경로(디렉터리)."""
    return str(
        PurePosixPath(_safe_seg(farm_cd, "FARM"))
        / _safe_seg(year, "0000")
        / _safe_seg(obs_id, "OBS")
    )


def resolve_media_path(rel_path: str) -> Path | None:
    """상대경로 → 절대경로. 루트 이탈 시 None."""
    rel = str(rel_path or "").replace("\\", "/").strip().lstrip("/")
    if not rel or ".." in PurePosixPath(rel).parts:
        return None
    root = observation_media_root()
    abs_path = (root / Path(*PurePosixPath(rel).parts)).resolve()
    try:
        abs_path.relative_to(root)
    except ValueError:
        return None
    return abs_path


def file_sha256(path: Path, max_bytes: int = OBS_PHOTO_MAX_BYTES) -> str | None:
    try:
        h = hashlib.sha256()
        size = 0
        with open(path, "rb") as f:
            while True:
                chunk = f.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    return None
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def validate_image_file(src_path: str | Path) -> tuple[bool, str, dict]:
    """확장자·용량·실제 디코딩 검증. 성공 시 meta: ext,size,width,height,hash."""
    from PyQt6.QtGui import QImageReader

    path = Path(src_path)
    if not path.is_file():
        return False, "파일이 존재하지 않습니다.", {}
    ext = path.suffix.lower()
    if ext not in OBS_ALLOWED_EXTS:
        return False, "지원 확장자는 jpg, jpeg, png, webp 입니다.", {}
    try:
        size = path.stat().st_size
    except OSError:
        return False, "파일 정보를 읽을 수 없습니다.", {}
    if size <= 0:
        return False, "빈 파일입니다.", {}
    if size > OBS_PHOTO_MAX_BYTES:
        return False, f"파일 용량은 최대 {OBS_PHOTO_MAX_BYTES // (1024 * 1024)}MB 입니다.", {}

    reader = QImageReader(str(path))
    reader.setAutoTransform(True)  # EXIF 회전
    if not reader.canRead():
        return False, "이미지 파일이 아니거나 손상되었습니다.", {}
    img = reader.read()
    if img.isNull():
        return False, "이미지를 읽을 수 없습니다.", {}
    digest = file_sha256(path)
    if not digest:
        return False, "파일 해시 계산에 실패했습니다.", {}
    return True, "", {
        "file_ext": ext.lstrip("."),
        "file_size": size,
        "width_px": int(img.width()),
        "height_px": int(img.height()),
        "file_hash": digest,
        "qimage": img,
    }


def load_thumb_pixmap(rel_thumb: str, max_px: int = OBS_THUMB_MAX_PX):
    """상대 썸네일 → QPixmap. 실패 시 None."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QPixmap

    path = resolve_media_path(rel_thumb)
    if path is None or not path.is_file():
        return None
    pm = QPixmap(str(path))
    if pm.isNull():
        return None
    if max(pm.width(), pm.height()) > max_px:
        return pm.scaled(
            max_px,
            max_px,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
    return pm


def photo_meta_rel_paths(meta: dict) -> list[str]:
    """메타 dict에서 상대 경로 목록(중복 제거)."""
    out: list[str] = []
    seen = set()
    for key in ("file_path", "thumb_path"):
        rel = str((meta or {}).get(key) or "").strip()
        if rel and rel not in seen:
            seen.add(rel)
            out.append(rel)
    return out


def compensate_photo_files(rel_paths: list[str]) -> tuple[int, list[str]]:
    """이번 요청에서 생성된 사진 파일만 안전 삭제. 루트 이탈 경로는 건너뜀."""
    deleted = 0
    errors: list[str] = []
    for rel in rel_paths or []:
        for part in (str(rel or "").strip(),):
            if not part:
                continue
            abs_path = resolve_media_path(part)
            if abs_path is None:
                errors.append(f"경로 확인 실패: {part}")
                continue
            if not abs_path.is_file():
                continue
            try:
                abs_path.unlink()
                deleted += 1
                print(f"[OBS] compensate deleted: {part}")
            except OSError as e:
                errors.append(f"{part}: {e}")
                print(f"[OBS] compensate failed: {part} ({e})")
    return deleted, errors


def process_observation_photo_file(
    farm_cd: str,
    obs_id: str,
    obs_dt: str,
    src_path: str | Path,
    *,
    photo_id: str | None = None,
) -> tuple[bool, str, dict | None]:
    """파일 처리만 수행(워커 스레드용). DB 저장은 호출측에서 일괄 처리."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QImage

    ok, msg, meta = validate_image_file(src_path)
    if not ok:
        return False, msg, None

    year = "".join(ch for ch in (obs_dt or "") if ch.isdigit())[:4] or "0000"
    pid = (photo_id or "").strip() or f"PHO{uuid.uuid4().hex[:12].upper()}"
    rel_dir = build_obs_photo_rel_dir(farm_cd, obs_id, year)
    ext = meta["file_ext"]
    stored_nm = f"{pid}.{ext}"
    rel_original = f"{rel_dir}/original/{stored_nm}"
    rel_thumb = f"{rel_dir}/thumbnail/{stored_nm}"

    abs_original = resolve_media_path(rel_original)
    abs_thumb = resolve_media_path(rel_thumb)
    if abs_original is None or abs_thumb is None:
        return False, "저장 경로가 올바르지 않습니다.", None

    created_rel: list[str] = []
    try:
        abs_original.parent.mkdir(parents=True, exist_ok=True)
        abs_thumb.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(src_path), str(abs_original))
        created_rel.append(rel_original)

        img: QImage = meta.pop("qimage", None) or QImage()
        if img.isNull():
            reader_img = QImage(str(src_path))
            if not reader_img.isNull():
                img = reader_img
        thumb = img.scaled(
            OBS_THUMB_MAX_PX,
            OBS_THUMB_MAX_PX,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        if not thumb.save(str(abs_thumb)):
            raise OSError("thumbnail save failed")
        created_rel.append(rel_thumb)

        return True, "", {
            "photo_id": pid,
            "file_path": rel_original,
            "thumb_path": rel_thumb,
            "original_nm": Path(src_path).name,
            "stored_nm": stored_nm,
            "file_ext": ext,
            "file_size": meta["file_size"],
            "width_px": meta["width_px"],
            "height_px": meta["height_px"],
            "file_hash": meta["file_hash"],
        }
    except Exception as e:
        compensate_photo_files(created_rel)
        return False, f"사진 저장 실패: {e}", None


def store_observation_photo(
    farm_cd: str,
    obs_id: str,
    obs_dt: str,
    src_path: str | Path,
    *,
    photo_id: str | None = None,
) -> tuple[bool, str, dict | None]:
    """원본 복사 + 썸네일 생성. 성공 시 상대경로·메타 dict."""
    return process_observation_photo_file(
        farm_cd, obs_id, obs_dt, src_path, photo_id=photo_id
    )
