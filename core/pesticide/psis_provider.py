# -*- coding: utf-8 -*-
"""농촌진흥청 PSIS OpenAPI provider (관찰일지용)."""

from __future__ import annotations

import os
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any
from xml.etree.ElementTree import ParseError

from core.pesticide.pesticide_provider import (
    PesticideProvider,
    PesticideSearchRequest,
    PesticideSearchResponse,
)

ENV_API_KEY = "ORCHARD_PSIS_API_KEY"
ENV_API_URL = "ORCHARD_PSIS_API_URL"
ENV_TIMEOUT = "ORCHARD_PSIS_TIMEOUT_SEC"
DEFAULT_URL = "http://psis.rda.go.kr/openApi/service.do"
DEFAULT_TIMEOUT = 15

PSIS_ERR_MSG = {
    "ERR_101": "API 인증에 실패했습니다. API 키·도메인 승인을 확인해 주세요.",
    "ERR_103": "요청 파라미터가 올바르지 않습니다.",
    "ERR_201": "필수 파라미터가 누락되었거나 잘못되었습니다.",
    "ERR_901": "서비스 연결에 실패했습니다. 잠시 후 다시 시도해 주세요.",
}


def _timeout() -> float:
    try:
        return max(3.0, float(os.environ.get(ENV_TIMEOUT) or DEFAULT_TIMEOUT))
    except (TypeError, ValueError):
        return float(DEFAULT_TIMEOUT)


def _api_url() -> str:
    return (os.environ.get(ENV_API_URL) or DEFAULT_URL).strip() or DEFAULT_URL


def _local(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def _text(el) -> str:
    return (el.text or "").strip() if el is not None else ""


def _child_map(el) -> dict[str, str]:
    out: dict[str, str] = {}
    for c in list(el):
        out[_local(c.tag).lower()] = _text(c)
    return out


def _map_item(raw: dict[str, str]) -> dict[str, Any]:
    g = lambda *keys: next((raw[k] for k in keys if raw.get(k)), "")
    return {
        "pesti_code": g("pesticode", "pesti_code"),
        "disease_use_seq": g("diseaseuseseq", "disease_use_seq"),
        "crop_name": g("cropname", "crop_name"),
        "disease_name": g("diseaseweedname", "disease_name"),
        "pesticide_name": g("pestiname", "pesticide_name", "itemname"),
        "brand_name": g("brandname", "brand_name"),
        "company_name": g("compname", "company_name"),
        "active_ingredient": g("indict", "engcorname", "active_ingredient"),
        "purpose_name": g("usepurpose", "purpose_name"),
        "action_mechanism": g("wsmarks", "action_mechanism"),
        "usage_method": g("usepart", "usage_method", "useguide"),
        "dilution": g("dilution", "dilutionrate", "useamount"),
        "preharvest_interval": g("phi", "preharvest_interval", "safeuse"),
        "max_use_count": g("usecount", "max_use_count"),
        "toxicity": g("toxic", "toxicity"),
        "fish_toxicity": g("fishtoxic", "fish_toxicity"),
        "source_nm": "농촌진흥청 농약안전정보시스템",
        "source_url": "https://psis.rda.go.kr/",
    }


class PsisProvider(PesticideProvider):
    def __init__(self, api_key: str | None = None):
        self._api_key = (
            api_key if api_key is not None else os.environ.get(ENV_API_KEY) or ""
        ).strip()

    def is_configured(self) -> bool:
        return bool(self._api_key)

    def config_hint(self) -> str:
        return (
            "ORCHARD_PSIS_API_KEY(.orchard.env)와 농약안전정보시스템 "
            "도메인 승인이 필요합니다."
        )

    def search(self, request: PesticideSearchRequest) -> PesticideSearchResponse:
        if not self.is_configured():
            return PesticideSearchResponse(
                ok=False,
                error_code="NO_KEY",
                error_message=self.config_hint(),
                match_type="SIMILAR" if request.similar else "EXACT",
            )
        crop = (request.crop_name or "").strip()
        disease = (request.disease_name or "").strip()
        if not crop:
            return PesticideSearchResponse(
                ok=False,
                error_code="PARAM",
                error_message="작물명을 입력해 주세요.",
            )
        if not disease:
            return PesticideSearchResponse(
                ok=False,
                error_code="PARAM",
                error_message="확정 병해충명을 입력해 주세요.",
            )

        page = max(1, int(request.page or 1))
        page_size = max(1, min(int(request.page_size or 20), 20))
        start = (page - 1) * page_size + 1
        params = {
            "apiKey": self._api_key,
            "serviceCode": "SVC01",
            "serviceType": "AA001",
            "cropName": crop,
            "cropCheck": "Y",
            "diseaseWeedName": disease,
            "similarFlag": "Y" if request.similar else "N",
            "displayCount": str(page_size),
            "startPoint": str(start),
        }
        raw, err = self._http_get(params)
        if err:
            return PesticideSearchResponse(
                ok=False,
                error_code="NETWORK",
                error_message=err,
                match_type="SIMILAR" if request.similar else "EXACT",
            )
        try:
            root = ET.fromstring(raw or b"")
        except ParseError:
            return PesticideSearchResponse(
                ok=False,
                error_code="XML",
                error_message="PSIS 응답 XML을 해석하지 못했습니다.",
                match_type="SIMILAR" if request.similar else "EXACT",
            )

        code, msg = self._parse_result(root)
        if code and code.startswith("ERR_"):
            return PesticideSearchResponse(
                ok=False,
                error_code=code,
                error_message=PSIS_ERR_MSG.get(code, msg or "공식 조회 오류"),
                match_type="SIMILAR" if request.similar else "EXACT",
            )

        items = []
        total = 0
        for el in root.iter():
            tag = _local(el.tag).lower()
            if tag == "totalcount":
                try:
                    total = int(_text(el) or 0)
                except ValueError:
                    total = 0
            if tag in ("item", "list", "row"):
                # only leafish item nodes with pesticode-like children
                cmap = _child_map(el)
                if any(k in cmap for k in ("pesticode", "brandname", "pestiname")):
                    items.append(_map_item(cmap))

        # dedupe
        seen = set()
        unique = []
        for it in items:
            key = (it.get("pesti_code"), it.get("disease_use_seq"), it.get("brand_name"))
            if key in seen:
                continue
            seen.add(key)
            unique.append(it)

        if total <= 0:
            total = len(unique)
        return PesticideSearchResponse(
            ok=True,
            items=unique,
            total_count=total,
            match_type="SIMILAR" if request.similar else "EXACT",
        )

    def _http_get(self, params: dict[str, str]) -> tuple[bytes | None, str]:
        # apiKey는 URL 로그에 출력하지 않음
        q = urllib.parse.urlencode(params)
        url = f"{_api_url()}?{q}"
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=_timeout()) as resp:
                return resp.read(), ""
        except urllib.error.HTTPError as e:
            return None, "공식 농약정보 서버 응답 오류가 발생했습니다."
        except urllib.error.URLError:
            return None, "네트워크 오류로 공식 농약정보를 조회하지 못했습니다."
        except TimeoutError:
            return None, "공식 농약정보 조회 시간이 초과되었습니다."
        except Exception:
            return None, "공식 농약정보 조회 중 오류가 발생했습니다."

    def _parse_result(self, root) -> tuple[str, str]:
        code, msg = "", ""
        for el in root.iter():
            tag = _local(el.tag).lower()
            if tag in ("resultcode", "code", "err_code", "errorcode"):
                code = _text(el)
            if tag in ("resultmsg", "message", "err_msg", "errormsg"):
                msg = _text(el)
        return code, msg


class FakePesticideProvider(PesticideProvider):
    def __init__(self, items: list[dict] | None = None, fail_code: str = ""):
        self._items = items
        self._fail_code = fail_code

    def is_configured(self) -> bool:
        return True

    def search(self, request: PesticideSearchRequest) -> PesticideSearchResponse:
        if self._fail_code:
            return PesticideSearchResponse(
                ok=False,
                error_code=self._fail_code,
                error_message=f"fake fail {self._fail_code}",
                match_type="SIMILAR" if request.similar else "EXACT",
            )
        items = self._items or [
            {
                "pesti_code": "P001",
                "disease_use_seq": "1",
                "crop_name": request.crop_name,
                "disease_name": request.disease_name,
                "pesticide_name": "테스트살균제",
                "brand_name": "테스트상표",
                "company_name": "테스트회사",
                "active_ingredient": "시험성분 10%",
                "purpose_name": "살균제",
                "action_mechanism": "-",
                "usage_method": "경엽처리",
                "dilution": "1000배",
                "preharvest_interval": "7일",
                "max_use_count": "3회",
                "toxicity": "저독성",
                "fish_toxicity": "III급",
                "source_nm": "농촌진흥청 농약안전정보시스템",
                "source_url": "https://psis.rda.go.kr/",
            }
        ]
        return PesticideSearchResponse(
            ok=True,
            items=items,
            total_count=len(items),
            match_type="SIMILAR" if request.similar else "EXACT",
        )
