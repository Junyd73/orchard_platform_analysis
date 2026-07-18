# -*- coding: utf-8 -*-
"""관찰 사진 공통 정책 — PyQt/FastAPI/Pillow/DBManager 비의존."""

from __future__ import annotations

import re
from pathlib import PurePosixPath

OBS_PHOTO_MAX_BYTES = 20 * 1024 * 1024
OBS_THUMB_MAX_PX = 400
OBS_PHOTO_MAX_COUNT = 5
OBS_ALLOWED_EXTS = frozenset({".jpg", ".jpeg", ".png", ".webp"})

_SAFE_SEG = re.compile(r"^[A-Za-z0-9._\-]+$")


def safe_path_segment(value: str, fallback: str = "X") -> str:
    s = str(value or "").strip()
    if not s or not _SAFE_SEG.match(s) or ".." in s:
        return fallback
    return s


def build_obs_photo_rel_dir(farm_cd: str, obs_id: str, year: str) -> str:
    """DB 저장용 relative POSIX 경로(디렉터리)."""
    return str(
        PurePosixPath(safe_path_segment(farm_cd, "FARM"))
        / safe_path_segment(year, "0000")
        / safe_path_segment(obs_id, "OBS")
    )
