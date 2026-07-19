# -*- coding: utf-8 -*-
"""관찰 AI Structured Output 스키마·정규화."""

from __future__ import annotations

from typing import Any

PROMPT_VERSION = "obs_ai_v2"

IMAGE_QUALITY_VALUES = frozenset({"GOOD", "FAIR", "POOR"})
CATEGORY_VALUES = frozenset(
    {"DISEASE", "PEST", "PHYSIOLOGICAL", "DAMAGE", "UNKNOWN"}
)
URGENCY_VALUES = frozenset({"LOW", "MEDIUM", "HIGH"})
TARGET_PART_HINTS = ("잎", "열매", "가지", "줄기", "수피", "해충", "기타")

OBSERVATION_AI_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "analysis_possible": {"type": "boolean"},
        "image_quality": {"type": "string", "enum": ["GOOD", "FAIR", "POOR"]},
        "overall_summary": {"type": "string"},
        "target_part": {"type": "string"},
        "candidates": {
            "type": "array",
            "maxItems": 3,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": [
                            "DISEASE",
                            "PEST",
                            "PHYSIOLOGICAL",
                            "DAMAGE",
                            "UNKNOWN",
                        ],
                    },
                    "name_ko": {"type": "string"},
                    "scientific_name": {"type": ["string", "null"]},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "visual_evidence": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "differential_reason": {"type": "string"},
                    "urgency": {
                        "type": "string",
                        "enum": ["LOW", "MEDIUM", "HIGH"],
                    },
                },
                "required": [
                    "category",
                    "name_ko",
                    "scientific_name",
                    "confidence",
                    "visual_evidence",
                    "differential_reason",
                    "urgency",
                ],
            },
        },
        "additional_photos": {
            "type": "array",
            "items": {"type": "string"},
        },
        "safe_immediate_actions": {
            "type": "array",
            "items": {"type": "string"},
        },
        "warning": {"type": "string"},
    },
    "required": [
        "analysis_possible",
        "image_quality",
        "overall_summary",
        "target_part",
        "candidates",
        "additional_photos",
        "safe_immediate_actions",
        "warning",
    ],
}

SYSTEM_PROMPT = """당신은 과수원 병해충·생리장해 관찰 보조 분석가입니다.
사진만으로 확진하지 말고 '가능성'과 '후보'로만 표현하십시오.
사용자가 제공한 관찰일·작물·생육단계·절기·기상은 참고 맥락이며, 사진 소견과 모순되면 사진을 우선하십시오.
농약 상표명·제품명·희석배수·살포 횟수·약제명을 절대 추천하거나 언급하지 마십시오.
확진 표현을 사용하지 마십시오.
후보는 최대 3개까지, confidence는 0~1입니다.
사진이 부적합하거나 무관하면 analysis_possible=false로 두십시오.
확신이 없으면 category=UNKNOWN을 허용합니다.
출력은 지정된 JSON 스키마만 따르십시오."""


def empty_analysis_result(
    *,
    warning: str = "사진만으로 확진할 수 없음",
    summary: str = "",
    quality: str = "POOR",
    possible: bool = False,
) -> dict[str, Any]:
    return {
        "analysis_possible": bool(possible),
        "image_quality": quality if quality in IMAGE_QUALITY_VALUES else "POOR",
        "overall_summary": summary or "",
        "target_part": "기타",
        "candidates": [],
        "additional_photos": [],
        "safe_immediate_actions": [],
        "warning": warning,
    }


def normalize_analysis_result(raw: Any) -> tuple[bool, str, dict[str, Any]]:
    """파싱·정규화. 실패 시 (False, msg, safe_default)."""
    if not isinstance(raw, dict):
        return False, "AI 응답 형식이 올바르지 않습니다.", empty_analysis_result()

    quality = str(raw.get("image_quality") or "POOR").upper()
    if quality not in IMAGE_QUALITY_VALUES:
        quality = "POOR"
    possible = bool(raw.get("analysis_possible"))
    candidates_in = raw.get("candidates") or []
    if not isinstance(candidates_in, list):
        candidates_in = []

    candidates: list[dict] = []
    for c in candidates_in[:3]:
        if not isinstance(c, dict):
            continue
        cat = str(c.get("category") or "UNKNOWN").upper()
        if cat not in CATEGORY_VALUES:
            cat = "UNKNOWN"
        urg = str(c.get("urgency") or "LOW").upper()
        if urg not in URGENCY_VALUES:
            urg = "LOW"
        try:
            conf = float(c.get("confidence") or 0.0)
        except (TypeError, ValueError):
            conf = 0.0
        conf = max(0.0, min(1.0, conf))
        evidence = c.get("visual_evidence") or []
        if not isinstance(evidence, list):
            evidence = [str(evidence)]
        sci = c.get("scientific_name")
        if sci is not None:
            sci = str(sci).strip() or None
        candidates.append(
            {
                "category": cat,
                "name_ko": str(c.get("name_ko") or "").strip() or "미상",
                "scientific_name": sci,
                "confidence": conf,
                "visual_evidence": [str(x) for x in evidence if str(x).strip()],
                "differential_reason": str(c.get("differential_reason") or "").strip(),
                "urgency": urg,
            }
        )

    add_photos = raw.get("additional_photos") or []
    if not isinstance(add_photos, list):
        add_photos = []
    actions = raw.get("safe_immediate_actions") or []
    if not isinstance(actions, list):
        actions = []

    out = {
        "analysis_possible": possible,
        "image_quality": quality,
        "overall_summary": str(raw.get("overall_summary") or "").strip(),
        "target_part": str(raw.get("target_part") or "기타").strip() or "기타",
        "candidates": candidates,
        "additional_photos": [str(x) for x in add_photos if str(x).strip()],
        "safe_immediate_actions": [str(x) for x in actions if str(x).strip()],
        "warning": str(raw.get("warning") or "사진만으로 확진할 수 없음").strip(),
    }
    return True, "", out
