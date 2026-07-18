# -*- coding: utf-8 -*-
"""관찰 사진 파일 저장 — core.observation_photo_files 위임 (경로 규칙 동일)."""

from __future__ import annotations

from pathlib import Path

from app.core.exceptions import BusinessRuleError
from app.services._core_path import ensure_repo_root_on_path

ensure_repo_root_on_path()

from core.observation_photo_policy import (
    OBS_ALLOWED_EXTS,
    OBS_PHOTO_MAX_BYTES,
    OBS_PHOTO_MAX_COUNT,
    OBS_THUMB_MAX_PX,
    build_obs_photo_rel_dir,
)
from core.observation_photo_files import (  # noqa: E402
    compensate_photo_files as _core_compensate,
    process_observation_photo_bytes as _core_process,
    resolve_media_path as _core_resolve,
)


def resolve_media_path(media_root: Path, rel_path: str) -> Path | None:
    return _core_resolve(media_root, rel_path)


def compensate_photo_files(media_root: Path, rel_paths: list[str]) -> None:
    _core_compensate(media_root, rel_paths)


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
    try:
        return _core_process(
            media_root,
            farm_cd,
            obs_id,
            obs_dt,
            data=data,
            original_nm=original_nm,
            photo_id=photo_id,
        )
    except ValueError as exc:
        raw = str(exc)
        msg = raw.split("|", 1)[-1] if "|" in raw else raw
        raise BusinessRuleError(msg or "사진 처리에 실패했습니다.") from exc
