# -*- coding: utf-8 -*-
"""관찰 AI Provider 인터페이스."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ObservationAiRequest:
    images: list[dict] = field(default_factory=list)  # data_url 만 (경로·농장정보 금지)
    crop_hint: str = ""
    extra_note: str = ""


@dataclass
class ObservationAiResponse:
    ok: bool
    result: dict | None = None
    error_code: str = ""
    error_message: str = ""
    provider: str = ""
    model_nm: str = ""
    provider_request_id: str | None = None
    raw_rejected: bool = False


class ObservationAiProvider(ABC):
    @abstractmethod
    def is_configured(self) -> bool:
        ...

    @abstractmethod
    def analyze(self, request: ObservationAiRequest) -> ObservationAiResponse:
        ...

    def config_hint(self) -> str:
        return "AI 분석 API 키를 설정해 주세요."
