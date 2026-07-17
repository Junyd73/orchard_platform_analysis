# -*- coding: utf-8 -*-
"""관찰 삭제 권한 — 작성자 동일 또는 과수원 ADMIN / SYS_ADMIN."""

from __future__ import annotations

ROLE_SYS_ADMIN = "SYS_ADMIN"
ROLE_ADMIN = "ADMIN"


def can_delete_observation(
    *,
    reg_id: str | None,
    user_id: str | None,
    role_cd: str | None,
    user_farm_cd: str | None = None,
    target_farm_cd: str | None = None,
) -> bool:
    """모바일/PC 채널과 무관하게 접속자 기준으로 판정한다.

    - 작성자(reg_id) == 접속자(user_id)
    - SYS_ADMIN: 전 농장
    - ADMIN: 본인 farm_cd 와 대상 farm_cd 가 같을 때
    """
    uid = str(user_id or "").strip()
    author = str(reg_id or "").strip()
    if uid and author and uid == author:
        return True

    role = str(role_cd or "").strip().upper()
    if role == ROLE_SYS_ADMIN:
        return True
    if role == ROLE_ADMIN:
        user_farm = str(user_farm_cd or "").strip().upper()
        target_farm = str(target_farm_cd or "").strip().upper()
        return bool(user_farm) and bool(target_farm) and user_farm == target_farm
    return False
