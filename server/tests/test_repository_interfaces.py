# -*- coding: utf-8 -*-
"""Repository 인터페이스 계약 테스트."""

from __future__ import annotations

import pytest

from app.repository.interfaces import CommonCodeRepository, FarmRepository
from app.repository.interfaces.common_code_repository import CommonCodeRepository as CCR
from app.repository.interfaces.farm_repository import FarmRepository as FR


def test_farm_repository_is_abc() -> None:
    assert issubclass(FarmRepository, FR)
    with pytest.raises(TypeError):
        FarmRepository()  # type: ignore[misc]


def test_common_code_repository_is_abc() -> None:
    assert issubclass(CommonCodeRepository, CCR)
    with pytest.raises(TypeError):
        CommonCodeRepository()  # type: ignore[misc]


def test_farm_repository_abstract_methods() -> None:
    names = {m for m in dir(FarmRepository) if not m.startswith("_")}
    for required in ("get_farm", "list_sites", "get_site"):
        assert required in names
        assert getattr(FarmRepository, required).__isabstractmethod__


def test_common_code_repository_abstract_methods() -> None:
    assert getattr(CommonCodeRepository, "list_codes").__isabstractmethod__
