# -*- coding: utf-8 -*-
"""관찰 삭제 권한 단위 테스트."""

from __future__ import annotations

from app.core.observation_delete_policy import can_delete_observation


def test_author_can_delete_same_user() -> None:
    assert can_delete_observation(
        reg_id="junyd73",
        user_id="junyd73",
        role_cd="USER",
        user_farm_cd="OR001",
        target_farm_cd="OR001",
    )


def test_author_can_delete_regardless_of_channel_label() -> None:
    """모바일/PC 채널 라벨과 무관 — user_id 일치만 보면 된다."""
    assert can_delete_observation(
        reg_id="junyd73",
        user_id="junyd73",
        role_cd="USER",
    )


def test_farm_admin_can_delete_others_on_same_farm() -> None:
    assert can_delete_observation(
        reg_id="OTHER",
        user_id="junyd73",
        role_cd="ADMIN",
        user_farm_cd="OR001",
        target_farm_cd="OR001",
    )


def test_farm_admin_cannot_delete_other_farm() -> None:
    assert not can_delete_observation(
        reg_id="OTHER",
        user_id="junyd73",
        role_cd="ADMIN",
        user_farm_cd="OR001",
        target_farm_cd="OR002",
    )


def test_sys_admin_can_delete_any_farm() -> None:
    assert can_delete_observation(
        reg_id="OTHER",
        user_id="admin",
        role_cd="SYS_ADMIN",
        user_farm_cd="SYSTEM",
        target_farm_cd="OR001",
    )


def test_other_user_cannot_delete() -> None:
    assert not can_delete_observation(reg_id="A", user_id="B", role_cd="USER")
    assert not can_delete_observation(reg_id="A", user_id="", role_cd="")
