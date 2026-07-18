# -*- coding: utf-8 -*-
"""OpenAI Responses API 기반 관찰 이미지 분석 provider."""

from __future__ import annotations

import json
import os
from typing import Any

from core.ai.observation_ai_provider import (
    ObservationAiProvider,
    ObservationAiRequest,
    ObservationAiResponse,
)
from core.ai.observation_ai_schema import (
    OBSERVATION_AI_JSON_SCHEMA,
    SYSTEM_PROMPT,
    normalize_analysis_result,
)

ENV_API_KEY = "OPENAI_API_KEY"
ENV_MODEL = "ORCHARD_OPENAI_MODEL"
ENV_TIMEOUT = "ORCHARD_AI_TIMEOUT_SEC"
DEFAULT_MODEL = "gpt-5.6"
DEFAULT_TIMEOUT_SEC = 60


def _timeout_sec() -> float:
    try:
        return max(5.0, float(os.environ.get(ENV_TIMEOUT) or DEFAULT_TIMEOUT_SEC))
    except (TypeError, ValueError):
        return float(DEFAULT_TIMEOUT_SEC)


def _model_name() -> str:
    return (os.environ.get(ENV_MODEL) or DEFAULT_MODEL).strip() or DEFAULT_MODEL


def _classify_openai_error(exc: Exception) -> tuple[str, str]:
    from core.observation_safe_errors import classify_ai_exception
    return classify_ai_exception(exc)


class OpenAIObservationProvider(ObservationAiProvider):
    def __init__(self, api_key: str | None = None, model: str | None = None):
        self._api_key = (api_key if api_key is not None else os.environ.get(ENV_API_KEY) or "").strip()
        self._model = (model or _model_name()).strip()

    def is_configured(self) -> bool:
        return bool(self._api_key)

    def config_hint(self) -> str:
        return (
            "OPENAI_API_KEY 환경변수(.orchard.env)를 설정하면 "
            "관찰 사진 AI 분석을 사용할 수 있습니다."
        )

    def analyze(self, request: ObservationAiRequest) -> ObservationAiResponse:
        if not self.is_configured():
            return ObservationAiResponse(
                ok=False,
                error_code="AI_NO_KEY",
                error_message=self.config_hint(),
                provider="openai",
                model_nm=self._model,
            )
        last_err: ObservationAiResponse | None = None
        for attempt in range(2):  # 최대 1회 재시도
            resp = self._call_once(request)
            if resp.ok:
                return resp
            last_err = resp
            if resp.error_code in {
                "AI_AUTH",
                "AI_RATE_LIMIT",
                "AI_NO_KEY",
                "AI_SCHEMA",
                "AUTH",
                "BILLING",
                "NO_KEY",
                "SCHEMA",
            }:
                break
            if attempt == 0:
                continue
        return last_err or ObservationAiResponse(
            ok=False,
            error_code="AI_PROVIDER",
            error_message="AI 분석에 실패했습니다.",
            provider="openai",
            model_nm=self._model,
        )

    def _call_once(self, request: ObservationAiRequest) -> ObservationAiResponse:
        try:
            from openai import OpenAI
        except ImportError:
            return ObservationAiResponse(
                ok=False,
                error_code="AI_DEPENDENCY",
                error_message="openai 패키지가 설치되지 않았습니다. pip install openai",
                provider="openai",
                model_nm=self._model,
            )

        images = list(request.images or [])
        if not images:
            return ObservationAiResponse(
                ok=False,
                error_code="AI_NO_IMAGE",
                error_message="분석할 이미지가 없습니다.",
                provider="openai",
                model_nm=self._model,
            )

        user_parts: list[dict[str, Any]] = [
            {
                "type": "input_text",
                "text": (
                    "과수 관찰 사진을 분석해 병·해충·생리장해 후보를 JSON으로 제공하세요. "
                    "약제명·희석배수·살포방법은 절대 포함하지 마세요."
                    + (
                        f" 작물 힌트: {request.crop_hint}."
                        if (request.crop_hint or "").strip()
                        else ""
                    )
                ),
            }
        ]
        for img in images:
            url = str(img.get("data_url") or "").strip()
            if not url:
                continue
            user_parts.append({"type": "input_image", "image_url": url})

        client = OpenAI(api_key=self._api_key, timeout=_timeout_sec())
        try:
            # Responses API + Structured Outputs
            response = client.responses.create(
                model=self._model,
                store=False,
                input=[
                    {
                        "role": "system",
                        "content": [{"type": "input_text", "text": SYSTEM_PROMPT}],
                    },
                    {"role": "user", "content": user_parts},
                ],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "observation_ai_result",
                        "strict": True,
                        "schema": OBSERVATION_AI_JSON_SCHEMA,
                    }
                },
            )
        except Exception as e:
            code, msg = _classify_openai_error(e)
            from core.observation_safe_errors import safe_log
            safe_log(code, type(e).__name__, where="openai_call")
            return ObservationAiResponse(
                ok=False,
                error_code=code,
                error_message=msg,
                provider="openai",
                model_nm=self._model,
            )

        req_id = getattr(response, "id", None)
        text = ""
        try:
            text = getattr(response, "output_text", None) or ""
            if not text:
                # fallback parse
                for item in getattr(response, "output", None) or []:
                    for c in getattr(item, "content", None) or []:
                        t = getattr(c, "text", None)
                        if t:
                            text = str(t)
                            break
        except Exception:
            text = ""

        if not text:
            return ObservationAiResponse(
                ok=False,
                error_code="AI_EMPTY",
                error_message="AI가 빈 응답을 반환했습니다.",
                provider="openai",
                model_nm=self._model,
                provider_request_id=str(req_id) if req_id else None,
            )

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            from core.observation_safe_errors import safe_log
            safe_log("AI_SCHEMA", "JSONDecodeError", where="openai_parse")
            return ObservationAiResponse(
                ok=False,
                error_code="AI_SCHEMA",
                error_message="AI 응답 파싱에 실패했습니다.",
                provider="openai",
                model_nm=self._model,
                provider_request_id=str(req_id) if req_id else None,
                raw_rejected=True,
            )

        ok, msg, normalized = normalize_analysis_result(parsed)
        if not ok:
            return ObservationAiResponse(
                ok=False,
                error_code="AI_SCHEMA",
                error_message=msg or "AI 응답 정규화에 실패했습니다.",
                provider="openai",
                model_nm=self._model,
                provider_request_id=str(req_id) if req_id else None,
                raw_rejected=True,
            )
        return ObservationAiResponse(
            ok=True,
            result=normalized,
            provider="openai",
            model_nm=self._model,
            provider_request_id=str(req_id) if req_id else None,
        )


class FakeObservationProvider(ObservationAiProvider):
    """테스트용 provider — 실제 API 미호출."""

    def __init__(self, canned: dict | None = None, fail_code: str = ""):
        self._canned = canned
        self._fail_code = fail_code

    def is_configured(self) -> bool:
        return True

    def analyze(self, request: ObservationAiRequest) -> ObservationAiResponse:
        if self._fail_code:
            return ObservationAiResponse(
                ok=False,
                error_code=self._fail_code,
                error_message=f"fake fail: {self._fail_code}",
                provider="fake",
                model_nm="fake-model",
            )
        from core.ai.observation_ai_schema import empty_analysis_result, normalize_analysis_result

        raw = self._canned or {
            "analysis_possible": True,
            "image_quality": "GOOD",
            "overall_summary": "잎에 반점 가능 증상",
            "target_part": "잎",
            "candidates": [
                {
                    "category": "DISEASE",
                    "name_ko": "검은별무늬병",
                    "scientific_name": None,
                    "confidence": 0.72,
                    "visual_evidence": ["흑색 반점"],
                    "differential_reason": "반점 형태",
                    "urgency": "MEDIUM",
                }
            ],
            "additional_photos": ["잎 뒷면"],
            "safe_immediate_actions": ["추가 관찰"],
            "warning": "사진만으로 확진할 수 없음",
        }
        ok, msg, norm = normalize_analysis_result(raw)
        return ObservationAiResponse(
            ok=ok,
            result=norm if ok else empty_analysis_result(),
            error_code="" if ok else "SCHEMA",
            error_message=msg,
            provider="fake",
            model_nm="fake-model",
            provider_request_id="fake-req-1",
        )
