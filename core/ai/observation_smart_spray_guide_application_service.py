# -*- coding: utf-8 -*-
"""스마트 방제 가이드 Application Service — 읽기 전용 데이터 통합.

확정 AI 후보 + 농약사전(m_pesticide_info / m_pesticide_pest_map) + 보유 재고
+ 최근 사용이력을 한 payload 로 모은다.
추천 점수·사용가능/불가 판정·실시간 PSIS 호출은 하지 않는다.

SQL 은 모두 `?` 파라미터 바인딩만 사용한다 (f-string / % / .format 금지).
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any

from core.observation_stage3 import (
    get_confirmed_candidate,
    get_latest_ai_analysis,
)
from core.pesticide_manager import (
    _catalog_usage_timing_and_limit_from_caution,
    _normalize_farm_crop_nm_for_psis,
)

_logger = logging.getLogger(__name__)

# 매칭 우선순위 (낮을수록 우선)
_MATCH_PRIORITY = {
    "info_id": 0,
    "psis_pesti_code": 1,
    "item_code": 2,
    "active_ingredient": 3,
    "brand_name": 4,
    "pesticide_name": 5,
    "pesticide_name_partial": 6,
}

GUIDE_STATUS_READY = "READY"
GUIDE_STATUS_PARTIAL = "PARTIAL"
GUIDE_STATUS_EMPTY = "EMPTY"
GUIDE_STATUS_NO_CANDIDATE = "NO_CANDIDATE"
GUIDE_STATUS_ERROR = "ERROR"

MATCH_LEVEL_MATCH = "MATCH"
MATCH_LEVEL_PARTIAL = "PARTIAL"
MATCH_LEVEL_NOT_FOUND = "NOT_FOUND"

STOCK_UNIT_PIECE = "낱개"
# 보유 재고는 전부 유지, 추천(비보유)만 상한
_GUIDE_RECOMMEND_LIMIT = 10

# 재고 보유(has_stock)로 인정하는 강한 매칭만 — 유효성분·부분일치는 제외
_STRONG_STOCK_KEYS = frozenset(
    {"info_id", "psis_pesti_code", "pesticide_name", "brand_name"}
)

_AI_NAME_SUFFIXES = ("가능성", "추정", "의심", "후보")


def normalize_match_text(value: str | None) -> str:
    """공백·전각공백 제거 후 소문자 정규화."""
    return (value or "").replace(" ", "").replace("\u3000", "").strip().lower()


def normalize_pest_lookup_keys(raw: str | None) -> list[str]:
    """AI 확정명 → 사전 pest_nm 조회용 후보 키 (우선순위 순, 중복 제거)."""
    s = (raw or "").strip()
    if not s:
        return []

    keys: list[str] = []
    seen: set[str] = set()

    def _add(v: str) -> None:
        t = (v or "").strip()
        if not t or t in seen:
            return
        seen.add(t)
        keys.append(t)

    _add(s)

    no_paren = re.sub(r"[（(][^）)]*[）)]", "", s).strip()
    _add(no_paren)
    if no_paren.endswith("류") and len(no_paren) > 1:
        _add(no_paren[:-1])

    for m in re.finditer(r"[（(]([^）)]+)[）)]", s):
        inner = (m.group(1) or "").strip()
        for suf in _AI_NAME_SUFFIXES:
            if inner.endswith(suf):
                inner = inner[: -len(suf)].strip()
                break
        _add(inner)
        if inner.endswith("류") and len(inner) > 1:
            _add(inner[:-1])

    return keys


def _as_str(value: Any) -> str:
    """API 문자 규칙: None/공백 → \"\"."""
    if value is None:
        return ""
    return str(value).strip()


def _as_int(value: Any, default: int = 0) -> int:
    """API 숫자 규칙: 실패·None → 0."""
    try:
        if value is None or value == "":
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def resolve_dilution_unit(*hints: Any) -> str:
    """규격·품목명 힌트로 희석 단위 판별. 액체→ml, 고체→g, 불명→\"\".

    예: \"250ml\"/\"1L\"/유제 → ml, \"250g\"/\"1kg\"/수화제 → g
    """
    blob = " ".join(_as_str(h) for h in hints if h is not None).lower()
    if not blob:
        return ""
    # 액체 표기 (ml·L) — 고체의 g보다 우선해 오판 방지
    if re.search(r"\d\s*(?:ml|㎖)\b", blob, flags=re.IGNORECASE):
        return "ml"
    if re.search(r"\d\s*l\b", blob, flags=re.IGNORECASE):
        return "ml"
    if any(k in blob for k in ("유제", "액제", "수현탁", "액상수화", "미탁제")):
        return "ml"
    if re.search(r"\d\s*(?:g|kg)\b", blob, flags=re.IGNORECASE):
        return "g"
    if any(k in blob for k in ("수화제", "입제", "분제", "수용제", "입상수화")):
        return "g"
    return ""


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_date_or_null(value: Any) -> str | None:
    """날짜 규칙: 없으면 null."""
    s = _as_str(value)
    return s[:10] if s else None


def _row_dict(row: Any) -> dict[str, Any]:
    if row is None:
        return {}
    if isinstance(row, dict):
        return dict(row)
    try:
        return dict(row)
    except Exception:
        return {}


def _stock_qty(row: dict[str, Any]) -> int:
    """UI는 낱개(qty_piece) 기준."""
    return max(0, _as_int(row.get("qty_piece"), 0))


def _ms_since(t0: float) -> int:
    return int((time.perf_counter() - t0) * 1000)


def _toxicity_from_caution(caution_note: str) -> str:
    """caution_note 첫 줄(독성 등)을 표시용으로 사용."""
    for ln in (caution_note or "").splitlines():
        t = (ln or "").strip()
        if t:
            return t
    return ""


def match_psis_to_stock(
    psis_case: dict[str, Any],
    stock_rows: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, str, str]:
    """사전/PSIS 1건 ↔ 재고 목록 매칭.

    Returns:
        (matched_stock_or_None, match_level, match_key)
    """
    if not stock_rows:
        return None, MATCH_LEVEL_NOT_FOUND, ""

    case_info_id = _as_int(psis_case.get("info_id"), 0)
    pesti_code = _as_str(psis_case.get("pesti_code"))
    ingredient = normalize_match_text(_as_str(psis_case.get("active_ingredient")))
    brand = normalize_match_text(_as_str(psis_case.get("brand_name")))
    pest_nm = normalize_match_text(_as_str(psis_case.get("pesticide_name")))

    best: dict[str, Any] | None = None
    best_level = MATCH_LEVEL_NOT_FOUND
    best_key = ""
    best_pri = 999

    for stock in stock_rows:
        level = MATCH_LEVEL_NOT_FOUND
        key = ""

        stock_info_id = _as_int(stock.get("info_id"), 0)
        stock_code = _as_str(stock.get("psis_pesti_code"))
        stock_ingredient = normalize_match_text(_as_str(stock.get("ingredient_nm")))
        stock_brand = normalize_match_text(
            _as_str(stock.get("brand_nm") or stock.get("item_nm"))
        )
        stock_pesticide = normalize_match_text(
            _as_str(stock.get("pesticide_nm") or stock.get("item_nm"))
        )
        stock_item_code = _as_str(stock.get("item_id"))

        if case_info_id > 0 and stock_info_id > 0 and case_info_id == stock_info_id:
            level, key = MATCH_LEVEL_MATCH, "info_id"
        elif pesti_code and stock_code and pesti_code == stock_code:
            level, key = MATCH_LEVEL_MATCH, "psis_pesti_code"
        elif pesti_code and stock_item_code and pesti_code == stock_item_code:
            level, key = MATCH_LEVEL_MATCH, "item_code"
        elif ingredient and stock_ingredient and ingredient == stock_ingredient:
            level, key = MATCH_LEVEL_MATCH, "active_ingredient"
        elif brand and stock_brand and brand == stock_brand:
            level, key = MATCH_LEVEL_MATCH, "brand_name"
        elif pest_nm and stock_pesticide and pest_nm == stock_pesticide:
            level, key = MATCH_LEVEL_MATCH, "pesticide_name"
        elif pest_nm and stock_pesticide and (
            pest_nm in stock_pesticide or stock_pesticide in pest_nm
        ):
            level, key = MATCH_LEVEL_PARTIAL, "pesticide_name_partial"
        elif brand and stock_brand and (brand in stock_brand or stock_brand in brand):
            level, key = MATCH_LEVEL_PARTIAL, "brand_name"
        elif ingredient and stock_ingredient and (
            ingredient in stock_ingredient or stock_ingredient in ingredient
        ):
            level, key = MATCH_LEVEL_PARTIAL, "active_ingredient"
        else:
            continue

        pri = _MATCH_PRIORITY.get(key, 99)
        qty = _stock_qty(stock)
        if best is None or pri < best_pri or (pri == best_pri and qty > _stock_qty(best)):
            best = stock
            best_level = level
            best_key = key
            best_pri = pri

    return best, best_level, best_key


def _log_match(
    *,
    psis_code: str,
    item_code: str,
    active_ingredient: str,
    match_level: str,
    match_method: str,
) -> None:
    _logger.debug(
        "[SMART_GUIDE_MATCH] PSIS_CODE=%s ITEM_CODE=%s ACTIVE_INGREDIENT=%s "
        "MATCH_LEVEL=%s MATCH_METHOD=%s",
        psis_code or "-",
        item_code or "-",
        active_ingredient or "-",
        match_level or MATCH_LEVEL_NOT_FOUND,
        match_method or "-",
    )


def _information_available(case: dict[str, Any], stock: dict[str, Any] | None) -> bool:
    fields = [
        case.get("dilution"),
        case.get("preharvest_interval"),
        case.get("max_use_count"),
        case.get("usage_method"),
        case.get("toxicity"),
    ]
    if any(_as_str(f) for f in fields):
        return True
    if stock:
        return any(
            _as_str(stock.get(k))
            for k in ("dilution_guide", "usage_note", "caution_note")
        )
    return False


def _resolve_guide_status(items: list[dict[str, Any]]) -> str:
    """READY: 재고 매칭 1건 이상 / PARTIAL: 사전만 / EMPTY: 사전 없음."""
    if not items:
        return GUIDE_STATUS_EMPTY
    if any(bool(it.get("has_stock")) for it in items):
        return GUIDE_STATUS_READY
    return GUIDE_STATUS_PARTIAL


class ObservationSmartSprayGuideApplicationService:
    """관찰별 스마트 방제 가이드 통합 조회 (읽기 전용)."""

    def build_guide(
        self,
        db,
        *,
        farm_cd: str,
        obs_id: str,
    ) -> dict[str, Any]:
        t_start = time.perf_counter()
        farm = _as_str(farm_cd)
        oid = _as_str(obs_id)
        _logger.debug("[SMART_GUIDE] START farm=%s obs=%s", farm or "-", oid or "-")

        base: dict[str, Any] = {
            "ok": False,
            "guide_status": GUIDE_STATUS_ERROR,
            "farm_cd": farm,
            "obs_id": oid,
            "observation": None,
            "confirmed_candidate": None,
            "psis_status": "NONE",
            "crop_name": "",
            "disease_name": "",
            "items": [],
            "error_code": "",
            "error_message": "",
            "timing_ms": {},
        }

        try:
            if not farm or not oid:
                out = {
                    **base,
                    "error_code": "GUIDE_PARAM",
                    "error_message": "농장코드와 관찰번호가 필요합니다.",
                }
                self._log_total(t_start, out)
                return out

            t_db = time.perf_counter()
            obs = db.get_observation(farm, oid) or {}
            if not obs or str(obs.get("use_yn") or "Y") != "Y":
                out = {
                    **base,
                    "error_code": "GUIDE_NOT_FOUND",
                    "error_message": "대상 관찰을 찾을 수 없습니다.",
                }
                self._log_total(t_start, out)
                return out

            observation = {
                "obs_id": oid,
                "farm_cd": farm,
                "obs_title": _as_str(obs.get("obs_title")),
                "obs_dt": _as_date_or_null(obs.get("obs_dt")),
                "ai_status": _as_str(obs.get("ai_status")),
                "site_id": _as_str(obs.get("site_id")),
                "site_nm": _as_str(obs.get("site_nm")),
            }
            base["observation"] = observation

            analysis = get_latest_ai_analysis(db, farm, oid)
            confirmed = None
            analysis_id = ""
            if analysis:
                analysis_id = _as_str(analysis.get("analysis_id"))
                if analysis_id:
                    confirmed = get_confirmed_candidate(db, farm, analysis_id)

            db_ms = _ms_since(t_db)
            _logger.debug("[SMART_GUIDE] DB %d ms", db_ms)
            base["timing_ms"]["db"] = db_ms

            if not confirmed:
                out = {
                    **base,
                    "ok": True,
                    "guide_status": GUIDE_STATUS_NO_CANDIDATE,
                    "confirmed_candidate": None,
                    "psis_status": "NONE",
                    "items": [],
                }
                self._log_total(t_start, out)
                return out

            confirmed_payload = {
                "analysis_id": analysis_id,
                "candidate_seq": _as_int(confirmed.get("candidate_seq"), 0),
                "name_ko": _as_str(confirmed.get("name_ko")),
                "confirmed_name": _as_str(
                    confirmed.get("confirmed_name") or confirmed.get("name_ko")
                ),
                "category": _as_str(confirmed.get("category")),
                "confidence": _as_float(confirmed.get("confidence"), 0.0),
            }
            disease_name = confirmed_payload["confirmed_name"]

            t_cat = time.perf_counter()
            crop_name = self._resolve_crop_name(db, farm)
            pest_key = self._resolve_pest_map_key(db, disease_name, crop_name)
            catalog_rows = (
                self._load_catalog_for_pest(db, pest_key, crop_name) if pest_key else []
            )
            # 응답 호환: 사전 조회 성공=CACHED, 없음=EMPTY (실시간 PSIS 아님)
            catalog_status = "CACHED" if catalog_rows else "EMPTY"
            cat_ms = _ms_since(t_cat)
            _logger.debug(
                "[SMART_GUIDE] CATALOG %d ms pest=%s crop=%s count=%d",
                cat_ms,
                pest_key or "-",
                crop_name or "-",
                len(catalog_rows),
            )
            base["timing_ms"]["catalog"] = cat_ms
            base["timing_ms"]["psis"] = cat_ms  # 기존 타이밍 키 호환

            t_match = time.perf_counter()
            stock_rows = self._load_stock_with_info(db, farm)
            last_used_by_item, last_used_by_name = self._load_last_used_maps(db, farm)

            items: list[dict[str, Any]] = []
            claimed_stock_ids: set[int] = set()
            display_disease = pest_key or disease_name
            for i, cat in enumerate(catalog_rows, start=1):
                case = self._catalog_as_case(cat, crop_name, display_disease)
                matched, match_level, match_key = match_psis_to_stock(case, stock_rows)
                item_id = _as_int(matched.get("item_id"), 0) if matched else 0
                qty = _stock_qty(matched) if matched else 0
                # 유효성분·부분일치는 ② 추천용만 — ① 보유재고로는 인정하지 않음
                strong = match_key in _STRONG_STOCK_KEYS
                has_stock = bool(matched) and qty > 0 and strong
                if has_stock and item_id > 0:
                    if item_id in claimed_stock_ids:
                        has_stock = False
                    else:
                        claimed_stock_ids.add(item_id)

                info_id = _as_int(cat.get("info_id"), 0)
                catalog_name = _as_str(case.get("pesticide_name"))
                catalog_brand = _as_str(case.get("brand_name"))
                # ① 보유재고 표시명은 실제 재고 품목명
                stock_item_nm = (
                    _as_str(matched.get("item_nm")) if matched and has_stock else ""
                )
                display_name = stock_item_nm or catalog_name
                display_brand = (
                    stock_item_nm or catalog_brand or catalog_name
                )

                last_used = None
                if has_stock and matched:
                    last_used = last_used_by_item.get(item_id)
                    if not last_used:
                        nm = normalize_match_text(
                            _as_str(
                                matched.get("item_nm") or matched.get("pesticide_nm")
                            )
                        )
                        last_used = last_used_by_name.get(nm)

                # 재고에 사전 사용기준이 더 있으면 보완
                dilution = _as_str(case.get("dilution"))
                usage_method = _as_str(case.get("usage_method"))
                phi = _as_str(case.get("preharvest_interval"))
                max_use = _as_str(case.get("max_use_count"))
                toxicity = _as_str(case.get("toxicity"))
                if matched and has_stock:
                    if not dilution:
                        dilution = _as_str(matched.get("dilution_guide"))
                    if not usage_method:
                        usage_method = _as_str(matched.get("usage_note"))
                    if (not phi or not max_use) and _as_str(matched.get("caution_note")):
                        t2, lim2 = _catalog_usage_timing_and_limit_from_caution(
                            _as_str(matched.get("caution_note"))
                        )
                        if not phi:
                            phi = t2
                        if not max_use:
                            max_use = lim2
                    if not toxicity:
                        toxicity = _toxicity_from_caution(
                            _as_str(matched.get("caution_note"))
                        )

                pesti_code = _as_str(case.get("pesti_code"))
                active_ingredient = _as_str(case.get("active_ingredient"))
                spec_nm = ""
                if matched and has_stock:
                    spec_nm = _as_str(matched.get("spec_nm"))
                if not spec_nm:
                    spec_nm = _as_str(cat.get("spec_nm"))
                dilution_unit = resolve_dilution_unit(
                    spec_nm,
                    display_name,
                    catalog_name,
                    catalog_brand,
                    _as_str(cat.get("pesticide_nm")),
                )
                # UI Match: 약한 성분매칭은 PARTIAL 유지
                ui_match_level = match_level or MATCH_LEVEL_NOT_FOUND
                if matched and not strong and match_level == MATCH_LEVEL_MATCH:
                    ui_match_level = MATCH_LEVEL_PARTIAL
                _log_match(
                    psis_code=pesti_code,
                    item_code=str(item_id) if item_id else "",
                    active_ingredient=active_ingredient,
                    match_level=ui_match_level,
                    match_method=match_key,
                )

                items.append(
                    {
                        "rank": i,
                        "snapshot_id": "",
                        "pesticide_name": display_name if has_stock else catalog_name,
                        "brand_name": display_brand if has_stock else catalog_brand,
                        "active_ingredient": active_ingredient,
                        "crop_name": _as_str(case.get("crop_name")) or crop_name,
                        "disease_name": display_disease,
                        "purpose": _as_str(case.get("purpose_name") or case.get("purpose")),
                        "pesti_code": pesti_code,
                        "item_id": item_id if has_stock else 0,
                        "info_id": info_id,
                        "stock_qty": qty if has_stock else 0,
                        "stock_unit": STOCK_UNIT_PIECE,
                        "has_stock": has_stock,
                        "last_used_date": last_used,
                        "spec_nm": spec_nm,
                        "dilution_unit": dilution_unit,
                        "dilution": dilution,
                        "phi": phi,
                        "max_use_count": max_use,
                        "usage_method": usage_method,
                        "toxicity": toxicity,
                        "from_psis": True,  # 사전(PSIS 동기화) 출처
                        "from_stock": has_stock,
                        "psis_registered": True,
                        "information_available": _information_available(
                            {
                                "dilution": dilution,
                                "preharvest_interval": phi,
                                "max_use_count": max_use,
                                "usage_method": usage_method,
                                "toxicity": toxicity,
                            },
                            matched if has_stock else None,
                        ),
                        "match_level": ui_match_level,
                        "match_key": match_key if has_stock else (match_key or ""),
                    }
                )

            # 보유 재고 우선 표시 (점수 산정 아님). 재고 매칭은 상한에 잘리지 않게 유지.
            items.sort(
                key=lambda it: (
                    0 if it.get("has_stock") else 1,
                    _as_str(it.get("pesticide_name")),
                )
            )
            stocked = [it for it in items if it.get("has_stock")]
            others = [it for it in items if not it.get("has_stock")]
            items = stocked + others[:_GUIDE_RECOMMEND_LIMIT]
            for idx, it in enumerate(items, start=1):
                it["rank"] = idx

            match_ms = _ms_since(t_match)
            _logger.debug("[SMART_GUIDE] MATCH %d ms items=%d", match_ms, len(items))
            base["timing_ms"]["match"] = match_ms

            guide_status = _resolve_guide_status(items)
            out = {
                **base,
                "ok": True,
                "guide_status": guide_status,
                "confirmed_candidate": confirmed_payload,
                "psis_status": catalog_status,
                "crop_name": crop_name,
                "disease_name": display_disease,
                "items": items,
            }
            self._log_total(t_start, out)
            return out
        except Exception as exc:  # noqa: BLE001 — 통합 API 경계
            out = {
                **base,
                "ok": False,
                "guide_status": GUIDE_STATUS_ERROR,
                "error_code": "GUIDE_INTERNAL",
                "error_message": "스마트 방제 가이드를 구성하지 못했습니다.",
                "error_detail": type(exc).__name__,
            }
            self._log_total(t_start, out)
            return out

    def _log_total(self, t_start: float, payload: dict[str, Any]) -> None:
        total = _ms_since(t_start)
        timing = dict(payload.get("timing_ms") or {})
        timing["total"] = total
        payload["timing_ms"] = timing
        _logger.debug("[SMART_GUIDE] END status=%s", payload.get("guide_status"))
        _logger.info(
            "[SMART_GUIDE] TOTAL %d ms farm=%s obs=%s status=%s",
            total,
            payload.get("farm_cd") or "-",
            payload.get("obs_id") or "-",
            payload.get("guide_status") or "-",
        )

    def _resolve_crop_name(self, db, farm_cd: str) -> str:
        """농장 활성 재배작물 1순위 → PSIS/사전용 정규화명."""
        sql = """
            SELECT crop_nm
            FROM m_farm_crop
            WHERE farm_cd = ?
              AND IFNULL(use_yn, 'Y') = 'Y'
            ORDER BY sort_ord, crop_nm
            LIMIT 1
        """
        try:
            rows = db.execute_query(sql, (farm_cd,)) or []
        except Exception:
            return ""
        if not rows:
            return ""
        raw = _as_str(_row_dict(rows[0]).get("crop_nm"))
        return _normalize_farm_crop_nm_for_psis(raw) if raw else ""

    def _resolve_pest_map_key(
        self, db, disease_name: str, crop_name: str
    ) -> str:
        """확정 병명 → m_pesticide_pest_map.pest_nm 실제 키."""
        keys = normalize_pest_lookup_keys(disease_name)
        if not keys:
            return ""

        for key in keys:
            if self._pest_map_exists(db, key, crop_name):
                return key

        # 포함 관계: 정규화 키 안에 사전 pest_nm 이 들어 있으면 최장 일치
        needle = keys[1] if len(keys) > 1 else keys[0]
        return self._find_pest_by_containment(db, needle, crop_name) or ""

    def _pest_map_exists(self, db, pest_nm: str, crop_name: str) -> bool:
        crop_hint = (crop_name or "").strip()
        sql = """
            SELECT 1
            FROM m_pesticide_info i
            INNER JOIN m_pesticide_pest_map m ON i.info_id = m.info_id
            WHERE IFNULL(i.use_yn, 'Y') = 'Y'
              AND IFNULL(m.use_yn, 'Y') = 'Y'
              AND TRIM(m.pest_nm) = ?
              AND (
                  i.crop_nm IS NULL
                  OR TRIM(IFNULL(i.crop_nm, '')) = ''
                  OR TRIM(IFNULL(i.crop_nm, '')) = ?
              )
            LIMIT 1
        """
        try:
            rows = db.execute_query(sql, (pest_nm, crop_hint)) or []
        except Exception:
            return False
        return bool(rows)

    def _find_pest_by_containment(
        self, db, needle: str, crop_name: str
    ) -> str:
        """needle 에 포함되거나 needle 을 포함하는 pest_nm 중 최장 일치."""
        n = (needle or "").strip()
        if len(n) < 2:
            return ""
        crop_hint = (crop_name or "").strip()
        sql = """
            SELECT DISTINCT TRIM(m.pest_nm) AS pest_nm
            FROM m_pesticide_info i
            INNER JOIN m_pesticide_pest_map m ON i.info_id = m.info_id
            WHERE IFNULL(i.use_yn, 'Y') = 'Y'
              AND IFNULL(m.use_yn, 'Y') = 'Y'
              AND length(TRIM(m.pest_nm)) >= 2
              AND (
                  i.crop_nm IS NULL
                  OR TRIM(IFNULL(i.crop_nm, '')) = ''
                  OR TRIM(IFNULL(i.crop_nm, '')) = ?
              )
        """
        try:
            rows = db.execute_query(sql, (crop_hint,)) or []
        except Exception:
            return ""
        best = ""
        for row in rows:
            pest = _as_str(_row_dict(row).get("pest_nm"))
            if not pest:
                continue
            if pest in n or n in pest:
                if len(pest) > len(best):
                    best = pest
        return best

    def _load_catalog_for_pest(
        self, db, pest_nm: str, crop_name: str
    ) -> list[dict[str, Any]]:
        """병해충·작물 기준 농약사전 행."""
        pest_key = (pest_nm or "").strip()
        if not pest_key:
            return []
        crop_hint = (crop_name or "").strip()
        sql = """
            SELECT
                i.info_id,
                i.pesticide_nm,
                i.brand_nm,
                i.ingredient_nm,
                i.category_nm,
                i.crop_nm,
                i.spec_nm,
                i.dilution_guide,
                i.usage_note,
                i.caution_note,
                i.psis_pesti_code,
                i.psis_disease_use_seq
            FROM m_pesticide_info i
            INNER JOIN m_pesticide_pest_map m ON i.info_id = m.info_id
            WHERE IFNULL(i.use_yn, 'Y') = 'Y'
              AND IFNULL(m.use_yn, 'Y') = 'Y'
              AND TRIM(m.pest_nm) = ?
              AND (
                  i.crop_nm IS NULL
                  OR TRIM(IFNULL(i.crop_nm, '')) = ''
                  OR TRIM(IFNULL(i.crop_nm, '')) = ?
              )
            ORDER BY i.pesticide_nm
        """
        try:
            rows = db.execute_query(sql, (pest_key, crop_hint)) or []
        except Exception:
            return []

        seen: set[int] = set()
        out: list[dict[str, Any]] = []
        for row in rows:
            r = _row_dict(row)
            iid = _as_int(r.get("info_id"), 0)
            if iid > 0 and iid in seen:
                continue
            if iid > 0:
                seen.add(iid)
            out.append(r)
        return out

    def _catalog_as_case(
        self, cat: dict[str, Any], crop_name: str, disease_name: str
    ) -> dict[str, Any]:
        caution = _as_str(cat.get("caution_note"))
        phi, max_use = _catalog_usage_timing_and_limit_from_caution(caution)
        brand = _as_str(cat.get("brand_nm"))
        pesticide_nm = _as_str(cat.get("pesticide_nm"))
        return {
            "info_id": _as_int(cat.get("info_id"), 0),
            "pesti_code": _as_str(cat.get("psis_pesti_code")),
            "pesticide_name": pesticide_nm or brand,
            "brand_name": brand or pesticide_nm,
            "active_ingredient": _as_str(cat.get("ingredient_nm")),
            "crop_name": _as_str(cat.get("crop_nm")) or crop_name,
            "disease_name": disease_name,
            "purpose_name": _as_str(cat.get("category_nm")),
            "dilution": _as_str(cat.get("dilution_guide")),
            "preharvest_interval": phi,
            "max_use_count": max_use,
            "usage_method": _as_str(cat.get("usage_note")),
            "toxicity": _toxicity_from_caution(caution),
        }

    def _load_stock_with_info(self, db, farm_cd: str) -> list[dict[str, Any]]:
        # farm_cd 는 반드시 ? 바인딩 — 문자열 보간 금지
        sql = """
            SELECT
                it.item_id,
                it.item_nm,
                it.spec_nm,
                it.qty_piece,
                it.qty_box,
                it.info_id,
                it.reg_dt,
                inf.pesticide_nm,
                inf.brand_nm,
                inf.ingredient_nm,
                inf.psis_pesti_code,
                inf.dilution_guide,
                inf.usage_note,
                inf.caution_note
            FROM m_pesticide_item it
            LEFT JOIN m_pesticide_info inf ON inf.info_id = it.info_id
            WHERE it.farm_cd = ?
              AND COALESCE(it.use_yn, 'Y') = 'Y'
            ORDER BY it.sort_ord, it.item_nm
        """
        try:
            rows = db.execute_query(sql, (farm_cd,)) or []
        except Exception:
            return []
        return [_row_dict(r) for r in rows]

    def _load_last_used_maps(
        self, db, farm_cd: str
    ) -> tuple[dict[int, str], dict[str, str]]:
        """item_id / 정규화 품목명 → 최근 사용일(YYYY-MM-DD)."""
        by_item: dict[int, str] = {}
        by_name: dict[str, str] = {}
        sql = """
            SELECT
                l.item_id AS item_id,
                TRIM(IFNULL(l.item_nm_snapshot, '')) AS nm,
                MAX(substr(u.use_dt, 1, 10)) AS last_dt
            FROM t_pesticide_use_line l
            INNER JOIN t_pesticide_use u ON u.use_id = l.use_id
            WHERE u.farm_cd = ?
              AND IFNULL(u.stock_applied_yn, 'N') = 'Y'
              AND length(IFNULL(u.use_dt, '')) >= 10
            GROUP BY l.item_id, TRIM(IFNULL(l.item_nm_snapshot, ''))
        """
        try:
            rows = db.execute_query(sql, (farm_cd,)) or []
        except Exception:
            return by_item, by_name
        for row in rows:
            r = _row_dict(row)
            dt = _as_date_or_null(r.get("last_dt"))
            if not dt:
                continue
            iid = _as_int(r.get("item_id"), 0)
            if iid > 0:
                prev = by_item.get(iid)
                if not prev or dt > prev:
                    by_item[iid] = dt
            nm = normalize_match_text(_as_str(r.get("nm")))
            if nm:
                prev = by_name.get(nm)
                if not prev or dt > prev:
                    by_name[nm] = dt
        return by_item, by_name
