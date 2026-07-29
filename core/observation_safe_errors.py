# -*- coding: utf-8 -*-
"""관찰 AI/PSIS 외부 오류 정제 — 원본 예외·키·URL 미노출."""

from __future__ import annotations

import re

# 사용자 안내용 안전 메시지
SAFE_MESSAGES: dict[str, str] = {
    "AI_AUTH": "AI 인증에 실패했습니다. API 키를 확인해 주세요.",
    "AI_TIMEOUT": "AI 분석 시간이 초과되었습니다. 잠시 후 다시 시도해 주세요.",
    "AI_RATE_LIMIT": "AI 요청 한도 또는 요금 제한으로 분석을 완료하지 못했습니다.",
    "AI_NETWORK": "네트워크 오류로 AI 서버에 연결하지 못했습니다.",
    "AI_SCHEMA": "AI 응답을 해석하지 못했습니다. 다시 시도해 주세요.",
    "AI_PROVIDER": "AI 분석 중 오류가 발생했습니다.",
    "AI_NO_KEY": "OPENAI_API_KEY가 설정되지 않았습니다.",
    "AI_NO_IMAGE": "분석할 이미지가 없습니다.",
    "AI_IMAGE": "사진 전처리에 실패했습니다.",
    "AI_DEPENDENCY": "openai 패키지가 설치되지 않았습니다.",
    "AI_EMPTY": "AI가 빈 응답을 반환했습니다.",
    "AI_BUSY": "이미 AI 분석이 진행 중입니다. 완료 후 다시 확인해 주세요.",
    "AI_CONFIRM_PARAM": "확정에 필요한 정보를 확인해 주세요.",
    "AI_CONFIRM_NOT_FOUND": "확정할 후보를 찾을 수 없습니다.",
    "PHOTO_PARAM": "사진 업로드에 필요한 정보를 확인해 주세요.",
    "PHOTO_TYPE": "지원 확장자는 jpg, jpeg, png, webp 입니다.",
    "PHOTO_EMPTY": "빈 파일입니다.",
    "PHOTO_TOO_LARGE": "파일 용량이 허용 한도를 초과했습니다.",
    "PHOTO_LIMIT": "등록 가능한 사진 장수를 초과했습니다.",
    "PHOTO_DUP": "동일 사진이 이미 등록되어 있습니다.",
    "PHOTO_SAVE": "사진 저장에 실패했습니다.",
    "PSIS_AUTH": "공식 농약정보 인증에 실패했습니다. API 키·도메인 승인을 확인해 주세요.",
    "PSIS_DOMAIN": "공식 농약정보 도메인 승인이 필요합니다.",
    "PSIS_TIMEOUT": "공식 농약정보 조회 시간이 초과되었습니다.",
    "PSIS_NETWORK": "네트워크 오류로 공식 농약정보를 조회하지 못했습니다.",
    "PSIS_PARSE": "공식 농약정보 응답을 해석하지 못했습니다.",
    "PSIS_NO_KEY": "ORCHARD_PSIS_API_KEY가 설정되지 않았습니다.",
    "PSIS_PARAM": "작물명과 확정 병해충명을 확인해 주세요.",
    "DB_ERROR": "데이터 저장 중 오류가 발생했습니다.",
    "INTERNAL": "내부 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.",
}

# 레거시 코드 → 표준 코드
_LEGACY_AI = {
    "AUTH": "AI_AUTH",
    "TIMEOUT": "AI_TIMEOUT",
    "BILLING": "AI_RATE_LIMIT",
    "NETWORK": "AI_NETWORK",
    "SCHEMA": "AI_SCHEMA",
    "PROVIDER": "AI_PROVIDER",
    "NO_KEY": "AI_NO_KEY",
    "NO_IMAGE": "AI_NO_IMAGE",
    "IMAGE": "AI_IMAGE",
    "DEPENDENCY": "AI_DEPENDENCY",
    "EMPTY": "AI_EMPTY",
    "FATAL": "INTERNAL",
    "DB": "DB_ERROR",
    "FAIL": "INTERNAL",
}
_LEGACY_PSIS = {
    "NO_KEY": "PSIS_NO_KEY",
    "PARAM": "PSIS_PARAM",
    "NETWORK": "PSIS_NETWORK",
    "XML": "PSIS_PARSE",
    "ERR_101": "PSIS_AUTH",
    "ERR_103": "PSIS_PARAM",
    "ERR_201": "PSIS_PARAM",
    "ERR_901": "PSIS_NETWORK",
    "FATAL": "INTERNAL",
    "FAIL": "INTERNAL",
}

# 화면 진단용 — 예외 클래스명만 허용 (메시지·키·URL 금지)
_SAFE_EXC_CLASS_RE = re.compile(r"\(([A-Za-z_][A-Za-z0-9_]{0,80})\)\s*$")
_BARE_EXC_CLASS_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,80}$")


def append_safe_exc_diag(base_msg: str, diag: str | None) -> str:
    """안전 문구 뒤에 (ExcClass) 만 유지·부착."""
    base = str(base_msg or "").strip()
    raw = str(diag or "").strip()
    if not raw:
        return base
    m = _SAFE_EXC_CLASS_RE.search(raw)
    if m:
        return f"{base} ({m.group(1)})"
    if _BARE_EXC_CLASS_RE.fullmatch(raw):
        return f"{base} ({raw})"
    return base


def normalize_error_code(code: str | None, *, domain: str = "AI") -> str:
    raw = str(code or "").strip().upper()
    if raw in SAFE_MESSAGES:
        return raw
    table = _LEGACY_AI if domain.upper() == "AI" else _LEGACY_PSIS
    mapped = table.get(raw)
    if mapped:
        return mapped
    if raw.startswith("AI_") or raw.startswith("PSIS_"):
        return raw if raw in SAFE_MESSAGES else "INTERNAL"
    return "INTERNAL"


def safe_user_message(code: str | None, *, domain: str = "AI") -> str:
    n = normalize_error_code(code, domain=domain)
    return SAFE_MESSAGES.get(n, SAFE_MESSAGES["INTERNAL"])


def classify_ai_exception(exc: BaseException) -> tuple[str, str]:
    import sqlite3

    name = type(exc).__name__
    low = (str(exc) or "").lower()
    lname = name.lower()
    if isinstance(exc, sqlite3.Error):
        code = "DB_ERROR"
    elif "timeout" in lname or "timeout" in low:
        code = "AI_TIMEOUT"
    elif "auth" in lname or "401" in low or "invalid_api_key" in low or "unauthorized" in low:
        code = "AI_AUTH"
    elif "429" in low or "quota" in low or "billing" in low or "rate" in low:
        code = "AI_RATE_LIMIT"
    elif "connect" in low or "network" in low or "dns" in low or "connection" in lname:
        code = "AI_NETWORK"
    else:
        code = "AI_PROVIDER"
    safe_log(code, name, where="openai")
    return code, append_safe_exc_diag(safe_user_message(code, domain="AI"), name)


def classify_psis_exception(exc: BaseException) -> tuple[str, str]:
    name = type(exc).__name__
    low = (str(exc) or "").lower()
    lname = name.lower()
    if "timeout" in lname or "timeout" in low:
        code = "PSIS_TIMEOUT"
    elif "auth" in low or "401" in low or "403" in low:
        code = "PSIS_AUTH"
    elif "parse" in lname or "xml" in low:
        code = "PSIS_PARSE"
    elif "url" in lname or "connect" in low or "network" in low:
        code = "PSIS_NETWORK"
    else:
        code = "PSIS_NETWORK"
    safe_log(code, name, where="psis")
    return code, append_safe_exc_diag(safe_user_message(code, domain="PSIS"), name)


def safe_log(code: str, exc_class: str, *, where: str = "", request_id: int | None = None) -> None:
    """내부 로그만 — 원본 예외 문구·키·URL·본문 금지."""
    bits = [f"[OBS_SAFE] code={code}", f"exc={exc_class}", f"where={where}"]
    if request_id is not None:
        bits.append(f"req={request_id}")
    print(" ".join(bits))


def sanitize_stored_error(code: str | None, message: str | None, *, domain: str = "AI") -> tuple[str, str]:
    n = normalize_error_code(code, domain=domain)
    # 본문은 안전 문구만. (ExcClass) 진단 접미사만 유지.
    return n, append_safe_exc_diag(safe_user_message(n, domain=domain), message)
