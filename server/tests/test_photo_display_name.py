# -*- coding: utf-8 -*-
"""사진 표시명·URL 계약 테스트."""

from __future__ import annotations

from app.services.photo_display_name import build_photo_display_nm


def test_display_nm_fruit_with_site() -> None:
    name = build_photo_display_nm(
        target_type_cd="OB010200",
        target_type_nm="열매",
        site_nm="뒷밭",
        obs_dt="2026-07-17",
        seq=1,
        file_ext="jpg",
    )
    assert name == "열매_뒷밭_20260717_01.jpg"


def test_display_nm_pest_seq2() -> None:
    name = build_photo_display_nm(
        target_type_cd="OB010400",
        target_type_nm="병해충",
        site_nm="앞밭",
        obs_dt="2026-07-17",
        seq=2,
        file_ext="png",
    )
    assert name == "병해충_앞밭_20260717_02.png"


def test_display_nm_fallback() -> None:
    name = build_photo_display_nm(
        target_type_cd="",
        target_type_nm="",
        site_nm="",
        obs_dt="2026-07-17",
        seq=1,
        file_ext="jpg",
    )
    assert name == "관찰사진_20260717_01.jpg"


def test_display_nm_sanitizes_unsafe() -> None:
    name = build_photo_display_nm(
        target_type_cd="OB010400",
        target_type_nm="병해충",
        site_nm='A/B:C*',
        obs_dt="2026-07-17",
        seq=1,
        file_ext="jpg",
    )
    assert "/" not in name
    assert ":" not in name
    assert "*" not in name
