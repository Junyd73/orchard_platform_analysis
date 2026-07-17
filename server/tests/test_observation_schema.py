# -*- coding: utf-8 -*-
"""관찰 스키마 계약 테스트."""

from __future__ import annotations

from app.schemas.observation import ObservationListItem, ObservationSummary


def test_observation_summary_ok() -> None:
    obj = ObservationSummary(
        today_count=1,
        danger_count=0,
        fruit_count=2,
        ai_pending_count=3,
        as_of_date="2026-07-17",
    )
    assert obj.today_count == 1


def test_observation_list_item_ok() -> None:
    obj = ObservationListItem(
        obs_id="OBS20260717-001",
        farm_cd="OR001",
        obs_dt="2026-07-17",
        obs_title="테스트",
        target_type_cd="OB010200",
        target_type_nm="열매",
        obs_type_cd="OY010300",
        obs_type_nm="과실",
        site_id="SITE01",
        site_nm="1구역",
        location_text="1구역 · 나무 12",
        severity_cd="OS010100",
        severity_nm="정상",
        progress_status_cd="OP010100",
        progress_status_nm="관찰 중",
        ai_status="NONE",
        has_photo=False,
    )
    assert obj.obs_id.startswith("OBS")
