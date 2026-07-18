# -*- coding: utf-8 -*-
"""관찰용 공식 농약 조회 Provider 인터페이스."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PesticideSearchRequest:
    crop_name: str
    disease_name: str
    similar: bool = False
    page: int = 1
    page_size: int = 20


@dataclass
class PesticideSearchResponse:
    ok: bool
    items: list[dict[str, Any]] = field(default_factory=list)
    total_count: int = 0
    match_type: str = "EXACT"  # EXACT | SIMILAR
    error_code: str = ""
    error_message: str = ""
    source_nm: str = "농촌진흥청 농약안전정보시스템"
    source_url: str = "https://psis.rda.go.kr/"


class PesticideProvider(ABC):
    @abstractmethod
    def is_configured(self) -> bool:
        ...

    @abstractmethod
    def search(self, request: PesticideSearchRequest) -> PesticideSearchResponse:
        ...

    def config_hint(self) -> str:
        return "ORCHARD_PSIS_API_KEY를 설정해 주세요."
