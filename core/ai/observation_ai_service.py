# -*- coding: utf-8 -*-
"""관찰 AI 서비스 — provider 선택·사진 준비·분석 오케스트레이션."""

from __future__ import annotations

import os

from core.ai.image_sanitize import prepare_images_for_ai
from core.ai.observation_ai_provider import (
    ObservationAiProvider,
    ObservationAiRequest,
    ObservationAiResponse,
)
from core.ai.observation_ai_schema import PROMPT_VERSION
from core.ai.openai_observation_provider import (
    ENV_API_KEY,
    OpenAIObservationProvider,
)


def get_default_observation_ai_provider() -> ObservationAiProvider:
    return OpenAIObservationProvider()


def is_observation_ai_available() -> bool:
    return bool((os.environ.get(ENV_API_KEY) or "").strip())


class ObservationAiService:
    def __init__(self, provider: ObservationAiProvider | None = None):
        self.provider = provider or get_default_observation_ai_provider()

    @property
    def prompt_version(self) -> str:
        return PROMPT_VERSION

    def is_available(self) -> bool:
        return self.provider.is_configured()

    def config_hint(self) -> str:
        return self.provider.config_hint()

    def analyze_photo_paths(
        self,
        paths: list[str],
        *,
        crop_hint: str = "",
        extra_note: str = "",
    ) -> ObservationAiResponse:
        ok, msg, images = prepare_images_for_ai(paths)
        if not ok:
            return ObservationAiResponse(
                ok=False,
                error_code="AI_IMAGE",
                error_message=msg,
                provider=getattr(self.provider, "_model", "") and "openai" or "unknown",
            )
        # data_url 만 전달 — 경로·농장코드 미포함
        payload = [{"data_url": x["data_url"]} for x in images]
        req = ObservationAiRequest(
            images=payload,
            crop_hint=crop_hint or "",
            extra_note=extra_note or "",
        )
        return self.provider.analyze(req)
