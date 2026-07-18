# -*- coding: utf-8 -*-
"""스마트 방제 가이드(1단계) Application Service — 읽기 전용 데이터 통합.

확정 AI 후보 + PSIS 스냅샷 + 보유 재고 + 최근 사용이력을 한 payload 로 모은다.
추천 점수·사용가능/불가 판정은 하지 않는다.
"""

from __future__ import annotations

from typing import Any

from core.observation_stage3 import (
    get_confirmed_candidate,
    get_latest_ai_analysis,
    list_pesticide_snapshots,
)

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


def _row_dict(row: Any) -> dict[str, Any]:
    if row is None:
        return {}
    if isinstance(row, dict):
        return dict(row)
    try:
        return dict(row)
    except Exception:
        return {}


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _stock_qty(row: dict[str, Any]) -> int:
    """UI는 낱개(qty_piece) 기준."""
    return max(0, _safe_int(row.get("qty_piece"), 0))


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

    pesti_code = str(psis_case.get("pesti_code") or "").strip()
    ingredient = normalize_match_text(str(psis_case.get("active_ingredient") or ""))
    brand = normalize_match_text(str(psis_case.get("brand_name") or ""))
    pest_nm = normalize_match_text(str(psis_case.get("pesticide_name") or ""))
    # 품목코드: 스냅샷에 별도 필드가 없으면 pesti_code 외 후보 없음.
    # info 쪽 식별용으로 disease_use_seq 는 사용하지 않음(등록 조합키).

    best: dict[str, Any] | None = None
    best_level = MATCH_LEVEL_NOT_FOUND
    best_key = ""
    best_pri = 999

    for stock in stock_rows:
        level = MATCH_LEVEL_NOT_FOUND
        key = ""

        stock_code = str(stock.get("psis_pesti_code") or "").strip()
        stock_ingredient = normalize_match_text(str(stock.get("ingredient_nm") or ""))
        stock_brand = normalize_match_text(
            str(stock.get("brand_nm") or stock.get("item_nm") or "")
        )
        stock_pesticide = normalize_match_text(
            str(stock.get("pesticide_nm") or stock.get("item_nm") or "")
        )
        stock_item_code = str(stock.get("item_id") or "").strip()

        if pesti_code and stock_code and pesti_code == stock_code:
            level, key = MATCH_LEVEL_MATCH, "psis_pesti_code"
        elif (
            pesti_code
            and stock_item_code
            and pesti_code == stock_item_code
        ):
            # 품목코드 보조: pesti_code 가 item_id 문자열과 동일한 경우만
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


def _information_available(case: dict[str, Any], stock: dict[str, Any] | None) -> bool:
    fields = [
        case.get("dilution"),
        case.get("preharvest_interval"),
        case.get("max_use_count"),
        case.get("usage_method"),
        case.get("toxicity"),
    ]
    if any(str(f or "").strip() for f in fields):
        return True
    if stock:
        return any(
            str(stock.get(k) or "").strip()
            for k in ("dilution_guide", "usage_note", "caution_note")
        )
    return False


class ObservationSmartSprayGuideApplicationService:
    """관찰별 스마트 방제 가이드 통합 조회 (읽기 전용)."""

    def build_guide(
        self,
        db,
        *,
        farm_cd: str,
        obs_id: str,
    ) -> dict[str, Any]:
        farm = str(farm_cd or "").strip()
        oid = str(obs_id or "").strip()
        base: dict[str, Any] = {
            "ok": False,
            "guide_status": GUIDE_STATUS_ERROR,
            "farm_cd": farm or None,
            "obs_id": oid or None,
            "observation": None,
            "confirmed_candidate": None,
            "psis_status": "NONE",
            "crop_name": None,
            "disease_name": None,
            "items": [],
            "error_code": None,
            "error_message": None,
        }

        try:
            if not farm or not oid:
                return {
                    **base,
                    "error_code": "GUIDE_PARAM",
                    "error_message": "농장코드와 관찰번호가 필요합니다.",
                }

            obs = db.get_observation(farm, oid) or {}
            if not obs or str(obs.get("use_yn") or "Y") != "Y":
                return {
                    **base,
                    "error_code": "GUIDE_NOT_FOUND",
                    "error_message": "대상 관찰을 찾을 수 없습니다.",
                }

            observation = {
                "obs_id": oid,
                "farm_cd": farm,
                "obs_title": str(obs.get("obs_title") or "").strip() or None,
                "obs_dt": str(obs.get("obs_dt") or "").strip() or None,
                "ai_status": str(obs.get("ai_status") or "").strip() or None,
                "site_id": str(obs.get("site_id") or "").strip() or None,
                "site_nm": str(obs.get("site_nm") or "").strip() or None,
            }
            base["observation"] = observation

            analysis = get_latest_ai_analysis(db, farm, oid)
            confirmed = None
            analysis_id = None
            if analysis:
                analysis_id = str(analysis.get("analysis_id") or "").strip() or None
                if analysis_id:
                    confirmed = get_confirmed_candidate(db, farm, analysis_id)

            if not confirmed:
                return {
                    **base,
                    "ok": True,
                    "guide_status": GUIDE_STATUS_NO_CANDIDATE,
                    "confirmed_candidate": None,
                    "psis_status": "NONE",
                    "items": [],
                }

            confirmed_payload = {
                "analysis_id": analysis_id,
                "candidate_seq": _safe_int(confirmed.get("candidate_seq"), 0) or None,
                "name_ko": str(confirmed.get("name_ko") or "").strip() or None,
                "confirmed_name": (
                    str(
                        confirmed.get("confirmed_name")
                        or confirmed.get("name_ko")
                        or ""
                    ).strip()
                    or None
                ),
                "category": str(confirmed.get("category") or "").strip() or None,
                "confidence": confirmed.get("confidence"),
            }
            disease_name = confirmed_payload["confirmed_name"]

            snapshots = list_pesticide_snapshots(db, farm, oid)
            if disease_name:
                by_disease = [
                    s
                    for s in snapshots
                    if str(s.get("disease_name") or "").strip() == disease_name
                ]
                if by_disease:
                    snapshots = by_disease

            latest_group: list[dict[str, Any]] = []
            crop_name = None
            if snapshots:
                fetched = snapshots[0].get("fetched_at")
                crop_name = str(snapshots[0].get("crop_name") or "").strip() or None
                latest_group = [
                    s for s in snapshots if s.get("fetched_at") == fetched
                ]

            psis_status = "CACHED" if latest_group else "EMPTY"

            stock_rows = self._load_stock_with_info(db, farm)
            last_used_by_item, last_used_by_name = self._load_last_used_maps(db, farm)

            items: list[dict[str, Any]] = []
            for i, snap in enumerate(latest_group, start=1):
                matched, match_level, match_key = match_psis_to_stock(snap, stock_rows)
                qty = _stock_qty(matched) if matched else 0
                has_stock = bool(matched) and qty > 0
                last_used = None
                if matched:
                    iid = _safe_int(matched.get("item_id"), 0)
                    last_used = last_used_by_item.get(iid)
                    if not last_used:
                        nm = normalize_match_text(
                            str(
                                matched.get("item_nm")
                                or matched.get("pesticide_nm")
                                or ""
                            )
                        )
                        last_used = last_used_by_name.get(nm)
                items.append(
                    {
                        "rank": i,
                        "snapshot_id": (
                            str(snap.get("snapshot_id") or "").strip() or None
                        ),
                        "pesticide_name": (
                            str(snap.get("pesticide_name") or "").strip() or None
                        ),
                        "brand_name": (
                            str(snap.get("brand_name") or "").strip() or None
                        ),
                        "active_ingredient": (
                            str(snap.get("active_ingredient") or "").strip() or None
                        ),
                        "crop_name": (
                            str(snap.get("crop_name") or "").strip() or crop_name
                        ),
                        "disease_name": (
                            str(snap.get("disease_name") or "").strip()
                            or disease_name
                        ),
                        "purpose": (
                            str(snap.get("purpose_name") or "").strip() or None
                        ),
                        "pesti_code": (
                            str(snap.get("pesti_code") or "").strip() or None
                        ),
                        "item_id": (
                            _safe_int(matched.get("item_id"), 0) or None
                            if matched
                            else None
                        ),
                        "info_id": (
                            _safe_int(matched.get("info_id"), 0) or None
                            if matched
                            else None
                        ),
                        "stock_qty": qty if matched else 0,
                        "stock_unit": STOCK_UNIT_PIECE,
                        "has_stock": has_stock,
                        "last_used_date": last_used,
                        "dilution": str(snap.get("dilution") or "").strip() or None,
                        "phi": (
                            str(snap.get("preharvest_interval") or "").strip() or None
                        ),
                        "max_use_count": (
                            str(snap.get("max_use_count"))
                            if snap.get("max_use_count") is not None
                            and str(snap.get("max_use_count")).strip() != ""
                            else None
                        ),
                        "usage_method": (
                            str(snap.get("usage_method") or "").strip() or None
                        ),
                        "toxicity": str(snap.get("toxicity") or "").strip() or None,
                        "from_psis": True,
                        "from_stock": bool(matched),
                        "psis_registered": True,
                        "information_available": _information_available(snap, matched),
                        "match_level": match_level,
                        "match_key": match_key or None,
                    }
                )

            guide_status = (
                GUIDE_STATUS_READY if items else GUIDE_STATUS_EMPTY
            )
            return {
                **base,
                "ok": True,
                "guide_status": guide_status,
                "confirmed_candidate": confirmed_payload,
                "psis_status": psis_status,
                "crop_name": crop_name,
                "disease_name": disease_name,
                "items": items,
            }
        except Exception as exc:  # noqa: BLE001 — 통합 API 경계
            return {
                **base,
                "ok": False,
                "guide_status": GUIDE_STATUS_ERROR,
                "error_code": "GUIDE_INTERNAL",
                "error_message": "스마트 방제 가이드를 구성하지 못했습니다.",
                "error_detail": type(exc).__name__,
            }

    def _load_stock_with_info(self, db, farm_cd: str) -> list[dict[str, Any]]:
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
            dt = str(r.get("last_dt") or "").strip()[:10]
            if not dt:
                continue
            iid = _safe_int(r.get("item_id"), 0)
            if iid > 0:
                prev = by_item.get(iid)
                if not prev or dt > prev:
                    by_item[iid] = dt
            nm = normalize_match_text(str(r.get("nm") or ""))
            if nm:
                prev = by_name.get(nm)
                if not prev or dt > prev:
                    by_name[nm] = dt
        return by_item, by_name
