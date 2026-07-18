# -*- coding: utf-8 -*-
"""관찰 사진 파일 처리 (Pillow) — PyQt/FastAPI 비의존.

PC core/observation_media 와 동일 경로·용량·확장자·썸네일 규격.
원본은 EXIF/GPS 제거 후 저장한다 (모바일·REST 공통).
"""

from __future__ import annotations

import hashlib
import io
import uuid
from pathlib import Path, PurePosixPath

from core.observation_media import (
    OBS_ALLOWED_EXTS,
    OBS_PHOTO_MAX_BYTES,
    OBS_THUMB_MAX_PX,
    build_obs_photo_rel_dir,
)


def resolve_media_path(media_root: Path, rel_path: str) -> Path | None:
    rel = str(rel_path or "").replace("\\", "/").strip().lstrip("/")
    if not rel or ".." in PurePosixPath(rel).parts:
        return None
    root = Path(media_root).resolve()
    abs_path = (root / Path(*PurePosixPath(rel).parts)).resolve()
    try:
        abs_path.relative_to(root)
    except ValueError:
        return None
    return abs_path


def compensate_photo_files(media_root: Path, rel_paths: list[str]) -> None:
    for rel in rel_paths or []:
        abs_path = resolve_media_path(media_root, rel)
        if abs_path is None or not abs_path.is_file():
            continue
        try:
            abs_path.unlink()
        except OSError:
            pass


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


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
    """검증·EXIF 제거·원본/썸네일 저장. 성공 시 meta dict. 실패 시 ValueError(code|msg)."""
    from PIL import Image, ImageOps

    if not data:
        raise ValueError("PHOTO_EMPTY|빈 파일입니다.")
    if len(data) > OBS_PHOTO_MAX_BYTES:
        raise ValueError(
            f"PHOTO_TOO_LARGE|파일 용량은 최대 "
            f"{OBS_PHOTO_MAX_BYTES // (1024 * 1024)}MB 입니다."
        )

    name = str(original_nm or "photo.jpg").strip() or "photo.jpg"
    # 경로 순회 문자 차단
    if ".." in name.replace("\\", "/") or "/" in name.replace("\\", "/"):
        name = Path(name).name or "photo.jpg"
    ext = Path(name).suffix.lower()
    if ext not in OBS_ALLOWED_EXTS:
        if not ext:
            ext = ".jpg"
            name = f"{name}.jpg"
        else:
            raise ValueError("PHOTO_TYPE|지원 확장자는 jpg, jpeg, png, webp 입니다.")

    created_rel: list[str] = []
    root = Path(media_root)
    try:
        try:
            with Image.open(io.BytesIO(data)) as opened:
                img = ImageOps.exif_transpose(opened)
                # EXIF 제거: 새 이미지로 복사
                img = img.copy()
                width, height = img.size
                if width <= 0 or height <= 0:
                    raise ValueError("PHOTO_TYPE|이미지를 읽을 수 없습니다.")

                year = "".join(ch for ch in (obs_dt or "") if ch.isdigit())[:4] or "0000"
                pid = (photo_id or "").strip() or f"PHO{uuid.uuid4().hex[:12].upper()}"
                rel_dir = build_obs_photo_rel_dir(farm_cd, obs_id, year)
                stored_nm = f"{pid}{ext}"
                rel_original = f"{rel_dir}/original/{stored_nm}"
                rel_thumb = f"{rel_dir}/thumbnail/{stored_nm}"

                abs_original = resolve_media_path(root, rel_original)
                abs_thumb = resolve_media_path(root, rel_thumb)
                if abs_original is None or abs_thumb is None:
                    raise ValueError("PHOTO_SAVE|저장 경로가 올바르지 않습니다.")

                abs_original.parent.mkdir(parents=True, exist_ok=True)
                abs_thumb.parent.mkdir(parents=True, exist_ok=True)

                buf = io.BytesIO()
                save_kw: dict = {}
                if ext in {".jpg", ".jpeg"}:
                    out = img.convert("RGB") if img.mode not in ("RGB", "L") else img
                    save_kw["quality"] = 92
                    out.save(buf, format="JPEG", **save_kw)
                    abs_original.write_bytes(buf.getvalue())
                    thumb = out.copy()
                elif ext == ".png":
                    img.save(buf, format="PNG")
                    abs_original.write_bytes(buf.getvalue())
                    thumb = img.copy()
                else:
                    img.save(buf, format="WEBP")
                    abs_original.write_bytes(buf.getvalue())
                    thumb = img.copy()
                created_rel.append(rel_original)

                stored_bytes = abs_original.read_bytes()
                digest = _sha256_bytes(stored_bytes)

                thumb.thumbnail((OBS_THUMB_MAX_PX, OBS_THUMB_MAX_PX))
                if ext in {".jpg", ".jpeg"}:
                    if thumb.mode not in ("RGB", "L"):
                        thumb = thumb.convert("RGB")
                    thumb.save(str(abs_thumb), format="JPEG", quality=85)
                elif ext == ".png":
                    thumb.save(str(abs_thumb), format="PNG")
                else:
                    thumb.save(str(abs_thumb), format="WEBP")
                created_rel.append(rel_thumb)

                return {
                    "photo_id": pid,
                    "file_path": rel_original,
                    "thumb_path": rel_thumb,
                    "original_nm": name,
                    "stored_nm": stored_nm,
                    "file_ext": ext.lstrip("."),
                    "file_size": len(stored_bytes),
                    "width_px": int(width),
                    "height_px": int(height),
                    "file_hash": digest,
                }
        except ValueError:
            raise
        except OSError as exc:
            raise ValueError(f"PHOTO_SAVE|사진 저장 실패") from exc
        except Exception as exc:
            raise ValueError("PHOTO_TYPE|이미지 파일이 아니거나 손상되었습니다.") from exc
    except Exception:
        compensate_photo_files(root, created_rel)
        raise
