# -*- coding: utf-8 -*-
"""관찰 사진 사용자 표시명 — 저장명(stored)과 분리, 조회 시 계산."""

from __future__ import annotations

import re

_UNSAFE = re.compile(r'[/\\:*?"<>|]+')
_SPACES = re.compile(r"\s+")
_MULTI_US = re.compile(r"_+")

DISPLAY_NM_MAX_LEN = 80

# 관찰대상 코드 → 표시용 짧은 이름 (PC 공통코드 명칭과 맞춤)
_TARGET_SHORT = {
    "OB010200": "열매",
    "OB010400": "병해충",
    "OB010100": "나무",
    "OB010300": "잎가지",
    "OB010500": "토양시설",
    "OB010600": "기타",
}


def _sanitize_token(value: str, *, fallback: str = "") -> str:
    s = str(value or "").strip()
    if not s:
        return fallback
    s = _SPACES.sub("_", s)
    s = _UNSAFE.sub("", s)
    s = _MULTI_US.sub("_", s).strip("._")
    return s or fallback


def _obs_date_digits(obs_dt: str) -> str:
    digits = "".join(ch for ch in (obs_dt or "") if ch.isdigit())
    if len(digits) >= 8:
        return digits[:8]
    return digits or "00000000"


def _ext(file_ext: str | None, fallback: str = "jpg") -> str:
    ext = str(file_ext or "").strip().lstrip(".").lower()
    if ext in {"jpeg"}:
        return "jpg"
    if ext in {"jpg", "png", "webp"}:
        return ext
    return fallback


def target_short_label(target_type_cd: str | None, target_type_nm: str | None) -> str:
    cd = str(target_type_cd or "").strip()
    if cd in _TARGET_SHORT:
        return _TARGET_SHORT[cd]
    nm = _sanitize_token(str(target_type_nm or ""), fallback="")
    return nm or "관찰사진"


def build_photo_display_nm(
    *,
    target_type_cd: str | None,
    target_type_nm: str | None,
    site_nm: str | None,
    obs_dt: str,
    seq: int,
    file_ext: str | None,
) -> str:
    """사용자 표시명: {대상}_{필지}_{YYYYMMDD}_{순번}.{ext}

    저장 파일명(stored_nm)과 무관. 순서 변경 시 seq만 바뀌면 됨.
    """
    target = target_short_label(target_type_cd, target_type_nm)
    site = _sanitize_token(str(site_nm or ""), fallback="")
    day = _obs_date_digits(obs_dt)
    order = max(1, int(seq or 1))
    ext = _ext(file_ext)

    if target == "관찰사진" and not site:
        stem = f"관찰사진_{day}_{order:02d}"
    elif site:
        stem = f"{target}_{site}_{day}_{order:02d}"
    else:
        stem = f"{target}_{day}_{order:02d}"

    stem = _sanitize_token(stem, fallback=f"관찰사진_{day}_{order:02d}")
    name = f"{stem}.{ext}"
    if len(name) <= DISPLAY_NM_MAX_LEN:
        return name
    # 확장자 보존하며 stem 축소
    keep = DISPLAY_NM_MAX_LEN - len(ext) - 1
    return f"{stem[: max(8, keep)]}.{ext}"
