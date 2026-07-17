# -*- coding: utf-8 -*-
"""Pydantic 스키마 계약 테스트."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.common_code import CommonCodeItem
from app.schemas.farm import FarmDetail, FarmSiteDetail, FarmSiteSummary, FarmSummary


def test_farm_summary_ok() -> None:
    obj = FarmSummary(farm_cd="OR001", farm_nm="테스트농장")
    assert obj.farm_cd == "OR001"
    assert obj.farm_nm == "테스트농장"


def test_farm_summary_requires_farm_cd() -> None:
    with pytest.raises(ValidationError):
        FarmSummary(farm_nm="x")  # type: ignore[call-arg]


def test_farm_detail_fields() -> None:
    obj = FarmDetail(
        farm_cd="OR001",
        farm_nm="A",
        owner_nm="B",
        address="addr",
        lat=36.1,
        lon=128.2,
        nx=1,
        ny=2,
        reg_dt="2026-01-01 00:00:00",
    )
    dumped = obj.model_dump()
    assert "user_pw" not in dumped
    assert dumped["farm_cd"] == "OR001"
    assert dumped["nx"] == 1


def test_farm_site_summary_site_id_text() -> None:
    obj = FarmSiteSummary(site_id="SITE01", site_nm="1구역", use_yn="Y")
    assert obj.site_id == "SITE01"


def test_farm_site_detail_requires_farm_and_site() -> None:
    with pytest.raises(ValidationError):
        FarmSiteDetail(site_id="SITE01")  # type: ignore[call-arg]
    obj = FarmSiteDetail(farm_cd="OR001", site_id="SITE01", site_nm="1구역")
    assert obj.farm_cd == "OR001"


def test_common_code_item_ok() -> None:
    obj = CommonCodeItem(
        farm_cd="OR001",
        code_cd="OB01",
        code_nm="관찰대상",
        parent_cd=None,
        use_yn="Y",
    )
    assert obj.code_cd == "OB01"


def test_common_code_requires_code_nm() -> None:
    with pytest.raises(ValidationError):
        CommonCodeItem(farm_cd="OR001", code_cd="OB01")  # type: ignore[call-arg]
