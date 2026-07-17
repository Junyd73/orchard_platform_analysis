# -*- coding: utf-8 -*-
"""관찰 사진 파일 저장 (PC core/observation_media 규칙, Pillow 기반)."""

from __future__ import annotations

import hashlib
import re
import shutil
import uuid
from pathlib import Path, PurePosixPath

from PIL import Image, ImageOps

from app.core.exceptions import BusinessRuleError

OBS_PHOTO_MAX_BYTES = 20 * 1024 * 1024
OBS_THUMB_MAX_PX = 400
OBS_PHOTO_MAX_COUNT = 5
OBS_ALLOWED_EXTS = frozenset({".jpg", ".jpeg", ".png", ".webp"})
_SAFE_SEG = re.compile(r"^[A-Za-z0-9._\-]+$")


def _safe_seg(value: str, fallback: str = "X") -> str:
    s = str(value or "").strip()
    if not s or not _SAFE_SEG.match(s) or ".." in s:
        return fallback
    return s


def build_obs_photo_rel_dir(farm_cd: str, obs_id: str, year: str) -> str:
    return str(
        PurePosixPath(_safe_seg(farm_cd, "FARM"))
        / _safe_seg(year, "0000")
        / _safe_seg(obs_id, "OBS")
    )


def resolve_media_path(media_root: Path, rel_path: str) -> Path | None:
    rel = str(rel_path or "").replace("\\", "/").strip().lstrip("/")
    if not rel or ".." in PurePosixPath(rel).parts:
        return None
    root = media_root.resolve()
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


def compensate_photo_files(media_root: Path, rel_paths: list[str]) -> None:
    for rel in rel_paths or []:
        abs_path = resolve_media_path(media_root, rel)
        if abs_path is None or not abs_path.is_file():
            continue
        try:
            abs_path.unlink()
        except OSError:
            pass


def process_observation_photo_bytes(
    media_root: Path,
    farm_cd: str,
    obs_id: str,
    obs_dt: str,
    *,
    data: bytes,
    original_nm: str,
    photo_id: str | None = None,
) -> dict:
    """원본 저장 + 썸네일 생성. 성공 시 meta dict."""
    if not data:
        raise BusinessRuleError("빈 파일입니다.")
    if len(data) > OBS_PHOTO_MAX_BYTES:
        raise BusinessRuleError(
            f"파일 용량은 최대 {OBS_PHOTO_MAX_BYTES // (1024 * 1024)}MB 입니다."
        )

    name = str(original_nm or "photo.jpg").strip() or "photo.jpg"
    ext = Path(name).suffix.lower()
    if ext not in OBS_ALLOWED_EXTS:
        # content-type 없는 갤러리 대비: 바이트로 재확인 전 확장자 보정
        if not ext:
            ext = ".jpg"
            name = f"{name}.jpg"
        else:
            raise BusinessRuleError("지원 확장자는 jpg, jpeg, png, webp 입니다.")

    tmp = media_root / "_tmp" / f"{uuid.uuid4().hex}{ext}"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    created_rel: list[str] = []
    try:
        tmp.write_bytes(data)
        try:
            with Image.open(tmp) as img:
                img = ImageOps.exif_transpose(img)
                width, height = img.size
                if width <= 0 or height <= 0:
                    raise BusinessRuleError("이미지를 읽을 수 없습니다.")
                digest = file_sha256(tmp)
                if not digest:
                    raise BusinessRuleError("파일 해시 계산에 실패했습니다.")

                year = "".join(ch for ch in (obs_dt or "") if ch.isdigit())[:4] or "0000"
                pid = (photo_id or "").strip() or f"PHO{uuid.uuid4().hex[:12].upper()}"
                rel_dir = build_obs_photo_rel_dir(farm_cd, obs_id, year)
                stored_nm = f"{pid}{ext}"
                rel_original = f"{rel_dir}/original/{stored_nm}"
                rel_thumb = f"{rel_dir}/thumbnail/{stored_nm}"

                abs_original = resolve_media_path(media_root, rel_original)
                abs_thumb = resolve_media_path(media_root, rel_thumb)
                if abs_original is None or abs_thumb is None:
                    raise BusinessRuleError("저장 경로가 올바르지 않습니다.")

                abs_original.parent.mkdir(parents=True, exist_ok=True)
                abs_thumb.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(tmp), str(abs_original))
                created_rel.append(rel_original)

                thumb = img.copy()
                thumb.thumbnail((OBS_THUMB_MAX_PX, OBS_THUMB_MAX_PX))
                save_kwargs: dict = {}
                fmt = (img.format or "").upper()
                if ext in {".jpg", ".jpeg"}:
                    if thumb.mode not in ("RGB", "L"):
                        thumb = thumb.convert("RGB")
                    save_kwargs["quality"] = 85
                    thumb.save(str(abs_thumb), format="JPEG", **save_kwargs)
                elif ext == ".png":
                    thumb.save(str(abs_thumb), format="PNG")
                else:
                    thumb.save(str(abs_thumb), format=fmt or "WEBP")
                created_rel.append(rel_thumb)

                return {
                    "photo_id": pid,
                    "file_path": rel_original,
                    "thumb_path": rel_thumb,
                    "original_nm": name,
                    "stored_nm": stored_nm,
                    "file_ext": ext.lstrip("."),
                    "file_size": len(data),
                    "width_px": int(width),
                    "height_px": int(height),
                    "file_hash": digest,
                }
        except BusinessRuleError:
            raise
        except OSError as exc:
            raise BusinessRuleError(f"사진 저장 실패: {exc}") from exc
        except Exception as exc:
            raise BusinessRuleError("이미지 파일이 아니거나 손상되었습니다.") from exc
    except Exception:
        compensate_photo_files(media_root, created_rel)
        raise
    finally:
        try:
            if tmp.is_file():
                tmp.unlink()
        except OSError:
            pass
