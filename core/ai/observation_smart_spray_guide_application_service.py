# -*- coding: utf-8 -*-
"""스마트 방제 가이드(1단계) Application Service — 읽기 전용 데이터 통합.

확정 AI 후보 + PSIS 스냅샷 + 보유 재고 + 최근 사용이력을 한 payload 로 모은다.
추천 점수·사용가능/불가 판정은 하지 않는다.

SQL 은 모두 `?` 파라미터 바인딩만 사용한다 (f-string / % / .format 금지).
"""

from __future__ import annotations

import logging
import time
from typing import Any

from core.observation_stage3 import (
    get_confirmed_candidate,
    get_latest_ai_analysis,
    list_pesticide_snapshots,
)

_logger = logging.getLogger(__name__)

# 매칭 우선순위 (낮을수록 우선)
_MATCH_PRIORITY = {
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


def normalize_match_text(value: str | None) -> str:
    """공백·전각공백 제거 후 소문자 정규화."""
    return (value or "").replace(" ", "").replace("\u3000", "").strip().lower()


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


def match_psis_to_stock(
    psis_case: dict[str, Any],
    stock_rows: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, str, str]:
    """PSIS 1건 ↔ 재고 목록 매칭.

    Returns:
        (matched_stock_or_None, match_level, match_key)
    """
    if not stock_rows:
        return None, MATCH_LEVEL_NOT_FOUND, ""

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

        stock_code = _as_str(stock.get("psis_pesti_code"))
        stock_ingredient = normalize_match_text(_as_str(stock.get("ingredient_nm")))
        stock_brand = normalize_match_text(
            _as_str(stock.get("brand_nm") or stock.get("item_nm"))
        )
        stock_pesticide = normalize_match_text(
            _as_str(stock.get("pesticide_nm") or stock.get("item_nm"))
        )
        stock_item_code = _as_str(stock.get("item_id"))

        if pesti_code and stock_code and pesti_code == stock_code:
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
    """READY: 재고 매칭 1건 이상 / PARTIAL: PSIS만 / EMPTY: PSIS 없음."""
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

            t_psis = time.perf_counter()
            snapshots = list_pesticide_snapshots(db, farm, oid)
            if disease_name:
                by_disease = [
                    s
                    for s in snapshots
                    if _as_str(s.get("disease_name")) == disease_name
                ]
                if by_disease:
                    snapshots = by_disease

            latest_group: list[dict[str, Any]] = []
            crop_name = ""
            if snapshots:
                fetched = snapshots[0].get("fetched_at")
                crop_name = _as_str(snapshots[0].get("crop_name"))
                latest_group = [
                    s for s in snapshots if s.get("fetched_at") == fetched
                ]

            psis_status = "CACHED" if latest_group else "EMPTY"
            psis_ms = _ms_since(t_psis)
            _logger.debug("[SMART_GUIDE] PSIS %d ms count=%d", psis_ms, len(latest_group))
            base["timing_ms"]["psis"] = psis_ms

            t_match = time.perf_counter()
            stock_rows = self._load_stock_with_info(db, farm)
            last_used_by_item, last_used_by_name = self._load_last_used_maps(db, farm)

            items: list[dict[str, Any]] = []
            for i, snap in enumerate(latest_group, start=1):
                matched, match_level, match_key = match_psis_to_stock(snap, stock_rows)
                qty = _stock_qty(matched) if matched else 0
                has_stock = bool(matched) and qty > 0
                item_id = _as_int(matched.get("item_id"), 0) if matched else 0
                info_id = _as_int(matched.get("info_id"), 0) if matched else 0
                last_used = None
                if matched:
                    last_used = last_used_by_item.get(item_id)
                    if not last_used:
                        nm = normalize_match_text(
                            _as_str(
                                matched.get("item_nm") or matched.get("pesticide_nm")
                            )
                        )
                        last_used = last_used_by_name.get(nm)

                pesti_code = _as_str(snap.get("pesti_code"))
                active_ingredient = _as_str(snap.get("active_ingredient"))
                _log_match(
                    psis_code=pesti_code,
                    item_code=str(item_id) if item_id else "",
                    active_ingredient=active_ingredient,
                    match_level=match_level,
                    match_method=match_key,
                )

                items.append(
                    {
                        "rank": i,
                        "snapshot_id": _as_str(snap.get("snapshot_id")),
                        "pesticide_name": _as_str(snap.get("pesticide_name")),
                        "brand_name": _as_str(snap.get("brand_name")),
                        "active_ingredient": active_ingredient,
                        "crop_name": _as_str(snap.get("crop_name")) or crop_name,
                        "disease_name": (
                            _as_str(snap.get("disease_name")) or disease_name
                        ),
                        "purpose": _as_str(snap.get("purpose_name")),
                        "pesti_code": pesti_code,
                        "item_id": item_id,
                        "info_id": info_id,
                        "stock_qty": qty,
                        "stock_unit": STOCK_UNIT_PIECE,
                        "has_stock": has_stock,
                        "last_used_date": last_used,
                        "dilution": _as_str(snap.get("dilution")),
                        "phi": _as_str(snap.get("preharvest_interval")),
                        "max_use_count": _as_str(snap.get("max_use_count")),
                        "usage_method": _as_str(snap.get("usage_method")),
                        "toxicity": _as_str(snap.get("toxicity")),
                        "from_psis": True,
                        "from_stock": bool(matched),
                        "psis_registered": True,
                        "information_available": _information_available(snap, matched),
                        "match_level": match_level or MATCH_LEVEL_NOT_FOUND,
                        "match_key": match_key or "",
                    }
                )

            match_ms = _ms_since(t_match)
            _logger.debug("[SMART_GUIDE] MATCH %d ms items=%d", match_ms, len(items))
            base["timing_ms"]["match"] = match_ms

            guide_status = _resolve_guide_status(items)
            out = {
                **base,
                "ok": True,
                "guide_status": guide_status,
                "confirmed_candidate": confirmed_payload,
                "psis_status": psis_status,
                "crop_name": crop_name,
                "disease_name": disease_name,
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
