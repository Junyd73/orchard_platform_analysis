# -*- coding: utf-8 -*-
"""SPR-001 스마트방제 발병여건·브리핑 서비스 (스냅샷 SSOT)."""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

from app.core.exceptions import BusinessRuleError, EntityNotFoundError
from app.db.sqlite import get_sqlite_connection, get_sqlite_write_connection
from app.schemas.smart_spray import (
    OutbreakParamDeleteRequest,
    OutbreakParamItem,
    OutbreakParamListResponse,
    OutbreakParamMutationResponse,
    OutbreakParamUpsertRequest,
    SmartSprayBriefingCard,
    SmartSprayBriefingPatched,
    SmartSprayBriefingResponse,
    SmartSprayCta,
)
from app.services._core_path import ensure_repo_root_on_path
from app.services.observation_ai_db_bridge import ServerDbBridge

ensure_repo_root_on_path()

from core.pest_efficacy import build_efficacy_status  # noqa: E402
from core.pest_outbreak_param_service import (  # noqa: E402
    SCOPE_EFFECTIVE,
    SCOPE_FARM,
    SCOPE_MINE,
    PestOutbreakParamService,
)
from core.pesticide_ai_recommend_manager import PesticideAIRecommendManager  # noqa: E402
from core.smart_spray_briefing_schema import (  # noqa: E402
    TABLE_SMART_SPRAY_BRIEFING,
    ensure_smart_spray_briefing_schema,
)

ADMIN_ROLES = frozenset({"SYS_ADMIN", "ADMIN", "SYSEM"})
PARAM_SCOPE_FARM = "farm"


def _s(value: Any) -> str:
    return str(value or "").strip()


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _card_to_dict(card: SmartSprayBriefingCard) -> dict[str, Any]:
    return card.model_dump()


def _card_from_dict(raw: dict[str, Any]) -> SmartSprayBriefingCard:
    return SmartSprayBriefingCard.model_validate(raw)


class SmartSprayService:
    def __init__(self, *, db_path: Path | str) -> None:
        self._db_path = Path(db_path)

    def _ensure_farm(self, farm_cd: str) -> str:
        farm = _s(farm_cd)
        if not farm:
            raise BusinessRuleError("농장 코드가 없습니다.")
        with get_sqlite_connection(self._db_path) as conn:
            row = conn.execute(
                "SELECT 1 FROM m_farm_info WHERE farm_cd = ? LIMIT 1",
                (farm,),
            ).fetchone()
        if not row:
            raise EntityNotFoundError("Farm not found")
        return farm

    def _role_of(self, user_id: str | None) -> str:
        uid = _s(user_id)
        if not uid:
            return ""
        with get_sqlite_connection(self._db_path) as conn:
            row = conn.execute(
                """
                SELECT role_cd FROM m_user
                WHERE user_id = ? AND IFNULL(use_yn, 'Y') = 'Y'
                LIMIT 1
                """,
                (uid,),
            ).fetchone()
        if not row:
            return ""
        return _s(row["role_cd"] if hasattr(row, "keys") else row[0])

    def list_outbreak_params(
        self,
        farm_cd: str,
        *,
        user_id: str | None,
        scope: str = SCOPE_EFFECTIVE,
    ) -> OutbreakParamListResponse:
        farm = self._ensure_farm(farm_cd)
        sc = _s(scope) or SCOPE_EFFECTIVE
        with get_sqlite_write_connection(self._db_path) as conn:
            bridge = ServerDbBridge(conn)
            svc = PestOutbreakParamService(bridge)
            rows = svc.list_rows(farm, user_id=user_id, scope=sc)
        return OutbreakParamListResponse(
            scope=sc,
            items=[OutbreakParamItem(**r) for r in rows],
        )

    def upsert_outbreak_param(
        self,
        farm_cd: str,
        body: OutbreakParamUpsertRequest,
        *,
        user_id: str | None,
    ) -> OutbreakParamMutationResponse:
        farm = self._ensure_farm(farm_cd)
        if body.as_farm_default:
            role = self._role_of(user_id)
            if role not in ADMIN_ROLES:
                raise BusinessRuleError("농장 기본 설정은 관리자만 변경할 수 있습니다.")
        with get_sqlite_write_connection(self._db_path) as conn:
            bridge = ServerDbBridge(conn)
            svc = PestOutbreakParamService(bridge)
            try:
                item = svc.upsert(
                    farm,
                    user_id=user_id,
                    pest_nm=body.pest_nm,
                    param_key=body.param_key,
                    param_value=body.param_value,
                    actor_id=user_id,
                    as_farm_default=body.as_farm_default,
                )
            except ValueError as exc:
                raise BusinessRuleError(str(exc)) from exc
            if body.as_farm_default:
                self._mark_snapshot_dirty(bridge, farm, date.today().isoformat())
        return OutbreakParamMutationResponse(
            item=OutbreakParamItem(**item),
            message="저장되었습니다.",
        )

    def delete_outbreak_param(
        self,
        farm_cd: str,
        body: OutbreakParamDeleteRequest,
        *,
        user_id: str | None,
    ) -> OutbreakParamMutationResponse:
        farm = self._ensure_farm(farm_cd)
        if body.as_farm_default:
            role = self._role_of(user_id)
            if role not in ADMIN_ROLES:
                raise BusinessRuleError("농장 기본 설정은 관리자만 변경할 수 있습니다.")
        with get_sqlite_write_connection(self._db_path) as conn:
            bridge = ServerDbBridge(conn)
            svc = PestOutbreakParamService(bridge)
            try:
                svc.delete(
                    farm,
                    user_id=user_id,
                    pest_nm=body.pest_nm,
                    param_key=body.param_key,
                    as_farm_default=body.as_farm_default,
                )
            except ValueError as exc:
                raise BusinessRuleError(str(exc)) from exc
            if body.as_farm_default:
                self._mark_snapshot_dirty(bridge, farm, date.today().isoformat())
        return OutbreakParamMutationResponse(message="삭제되었습니다.")

    def stock_count_for_pest(
        self, bridge: ServerDbBridge, farm: str, pest_nm: str
    ) -> int:
        """병해충 연관 보유 품목 수.

        PSIS는 병해충마다 info 행이 갈라지므로, 연결 info와 동일 품목명·제조사
        형제 행의 pest_map까지 포함해 집계한다(재고목록 pest_target과 동일).
        """
        pest = _s(pest_nm)
        if not pest:
            return 0
        try:
            rows = bridge.execute_query(
                """
                SELECT COUNT(DISTINCT it.item_id) AS cnt
                FROM m_pesticide_item it
                INNER JOIN m_pesticide_info linked
                  ON linked.info_id = it.info_id
                 AND IFNULL(linked.use_yn, 'Y') = 'Y'
                WHERE it.farm_cd = ?
                  AND IFNULL(it.use_yn, 'Y') = 'Y'
                  AND IFNULL(it.qty_piece, 0) > 0
                  AND EXISTS (
                    SELECT 1
                    FROM m_pesticide_pest_map mp
                    INNER JOIN m_pesticide_info sib
                      ON sib.info_id = mp.info_id
                     AND IFNULL(sib.use_yn, 'Y') = 'Y'
                    WHERE IFNULL(mp.use_yn, 'Y') = 'Y'
                      AND TRIM(IFNULL(sib.pesticide_nm, ''))
                          = TRIM(IFNULL(linked.pesticide_nm, ''))
                      AND TRIM(IFNULL(sib.maker_nm, ''))
                          = TRIM(IFNULL(linked.maker_nm, ''))
                      AND (
                        REPLACE(IFNULL(mp.pest_nm, ''), ' ', '')
                          LIKE '%' || REPLACE(?, ' ', '') || '%'
                        OR REPLACE(?, ' ', '')
                          LIKE '%' || REPLACE(IFNULL(mp.pest_nm, ''), ' ', '') || '%'
                      )
                  )
                """,
                (farm, pest, pest),
            ) or []
        except Exception:
            return 0
        if not rows:
            return 0
        r = rows[0]
        try:
            return int(r["cnt"] if hasattr(r, "keys") else r[0] or 0)
        except (TypeError, ValueError, KeyError, IndexError):
            return 0

    def latest_obs_photo(
        self, bridge: ServerDbBridge, farm: str, pest_nm: str
    ) -> tuple[str | None, str | None, str | None]:
        """확정 후보명 유사 매칭 → (obs_id, photo_id, photo_url API path)."""
        try:
            rows = bridge.execute_query(
                """
                SELECT o.obs_id, p.photo_id, p.thumb_path, p.file_path
                FROM t_observation_ai_candidate c
                INNER JOIN t_observation_ai_analysis a
                  ON a.farm_cd = c.farm_cd AND a.analysis_id = c.analysis_id
                INNER JOIN t_observation_master o
                  ON o.farm_cd = a.farm_cd AND o.obs_id = a.obs_id
                LEFT JOIN t_observation_photo p
                  ON p.farm_cd = o.farm_cd AND p.obs_id = o.obs_id
                 AND IFNULL(p.use_yn, 'Y') = 'Y'
                WHERE c.farm_cd = ?
                  AND IFNULL(c.selected_yn, 'N') = 'Y'
                  AND (
                    REPLACE(IFNULL(c.confirmed_name, c.name_ko), ' ', '')
                      LIKE '%' || REPLACE(?, ' ', '') || '%'
                    OR REPLACE(?, ' ', '')
                      LIKE '%' || REPLACE(IFNULL(c.confirmed_name, c.name_ko), ' ', '') || '%'
                  )
                ORDER BY IFNULL(o.obs_dt, '') DESC, IFNULL(p.photo_id, '') DESC
                LIMIT 1
                """,
                (farm, pest_nm, pest_nm),
            ) or []
        except Exception:
            return None, None, None
        if not rows:
            return None, None, None
        d = rows[0]
        try:
            obs_id = _s(d["obs_id"] if hasattr(d, "keys") else d[0]) or None
            photo_id = _s(d["photo_id"] if hasattr(d, "keys") else d[1]) or None
            thumb = _s(d["thumb_path"] if hasattr(d, "keys") else d[2])
            rel = _s(d["file_path"] if hasattr(d, "keys") else d[3])
            photo_url = None
            if obs_id and photo_id:
                photo_url = (
                    f"/farms/{farm}/observations/{obs_id}"
                    f"/photos/{photo_id}/thumbnail"
                )
            elif thumb or rel:
                photo_url = thumb or rel
            return obs_id, photo_id, photo_url
        except (KeyError, IndexError, TypeError):
            return None, None, None

    def build_ctas(
        self,
        *,
        pest_nm: str,
        obs_id: str | None,
        stock_n: int,
    ) -> list[SmartSprayCta]:
        pest_q = quote(_s(pest_nm), safe="")
        return [
            SmartSprayCta(
                kind="observation",
                label="관련 관찰",
                # 관찰 없으면 빈 route — 클라이언트가 안내 메시지만 표시
                route=f"/observation/{obs_id}" if obs_id else "",
            ),
            SmartSprayCta(
                kind="stock",
                label=f"농약재고 ({stock_n})",
                route=(
                    f"/pesticide/stock?pest_nm={pest_q}"
                    if pest_q
                    else "/pesticide/stock"
                ),
            ),
            SmartSprayCta(
                kind="pest-dict",
                label="병해충 사전",
                route=(
                    f"/pesticide/pest-dict?pest_nm={pest_q}"
                    if pest_q
                    else "/pesticide/pest-dict"
                ),
            ),
        ]

    def build_farm_briefing_cards(
        self,
        bridge: ServerDbBridge,
        farm: str,
        *,
        rules: dict[str, Any],
        weather_ctx: dict[str, Any],
        work_dt: str,
        allow_score_fallback: bool = True,
    ) -> list[SmartSprayBriefingCard]:
        """점수 → top → 관찰/재고 CTA 카드. Job·폴백 공용."""
        mgr = PesticideAIRecommendManager(bridge)
        scores = mgr.calculate_pest_scores(weather_ctx, rules=rules)
        top = mgr.get_top_pests(scores, rules=rules)
        if not top and allow_score_fallback:
            # min_score 미통과 시에도 안내용 폴백 — 상한 없이 점수순
            top = sorted(
                scores, key=lambda x: int(x.get("score") or 0), reverse=True
            )
            top = [r for r in top if int(r.get("score") or 0) > 0]
        cards: list[SmartSprayBriefingCard] = []
        as_of = date.fromisoformat(work_dt) if len(work_dt) >= 10 else date.today()
        for row in top:
            pest = _s(row.get("pest_nm"))
            if not pest:
                continue
            obs_id, photo_id, photo_url = self.latest_obs_photo(bridge, farm, pest)
            stock_n = self.stock_count_for_pest(bridge, farm, pest)
            eff = build_efficacy_status(
                bridge, farm, pest, rules=rules, as_of=as_of
            )
            score = int(row.get("score") or 0)
            risk = _s(row.get("risk_level")) or mgr.get_risk_level(score)
            spec = rules.get(pest) if isinstance(rules, dict) else {}
            min_need = int((spec or {}).get("min_score") or 0)
            reasons = self._build_selection_reasons(
                pest_nm=pest,
                score=score,
                risk_level=risk,
                min_score=min_need,
                rule_reasons=list(row.get("reasons") or []),
                weather_ctx=weather_ctx,
                efficacy=eff,
            )
            cards.append(
                SmartSprayBriefingCard(
                    pest_nm=pest,
                    score=score,
                    risk_level=risk,
                    reasons=reasons,
                    photo_url=photo_url,
                    photo_id=photo_id,
                    obs_id=obs_id,
                    stock_count=stock_n,
                    last_spray_dt=eff.get("last_spray_dt"),
                    last_spray_item_nm=eff.get("last_spray_item_nm"),
                    last_spray_qty=eff.get("last_spray_qty"),
                    efficacy_days=eff.get("efficacy_days"),
                    efficacy_days_left=eff.get("efficacy_days_left"),
                    efficacy_active=bool(eff.get("efficacy_active")),
                    ctas=self.build_ctas(
                        pest_nm=pest,
                        obs_id=obs_id,
                        stock_n=stock_n,
                    ),
                )
            )
        return cards

    def _build_selection_reasons(
        self,
        *,
        pest_nm: str,
        score: int,
        risk_level: str,
        min_score: int,
        rule_reasons: list[str],
        weather_ctx: dict[str, Any],
        efficacy: dict[str, Any],
    ) -> list[str]:
        """스마트방제 카드용 선정사유 — 표준 문구만(사다리 중복은 채점단에서 제거)."""
        _ = (pest_nm, score, risk_level, min_score, weather_ctx)
        out: list[str] = []
        seen: set[str] = set()
        for msg in rule_reasons:
            s = _s(msg)
            if not s or s in seen:
                continue
            # 구 스냅샷 호환: (+N) 접미 제거
            if s.endswith(")") and "(+" in s:
                s = s[: s.rfind("(+")].rstrip()
            if not s or s in seen:
                continue
            seen.add(s)
            out.append(s)
        if efficacy.get("efficacy_active"):
            left = efficacy.get("efficacy_days_left")
            last = efficacy.get("last_spray_dt")
            eff_msg = f"잔효 참고: {left}일 남음" + (
                f" · 최근 살포 {last}" if last else ""
            )
            if eff_msg not in seen:
                out.insert(0, eff_msg)
        return out

    def apply_work_status_flags(
        self, bridge: ServerDbBridge, farm: str, ctx: dict[str, Any]
    ) -> dict[str, Any]:
        """봉지·최근 방제 플래그를 ctx에 갱신(스냅샷 재사용 시에도 필수)."""
        out = ctx if isinstance(ctx, dict) else {}
        mgr = PesticideAIRecommendManager(bridge)
        try:
            ws = mgr.get_work_status(farm) or {}
            out["after_bag_yn"] = bool(
                mgr.get_after_bag_status_for_year(farm) or ws.get("after_bag_yn")
            )
            out["recent_spray_yn"] = bool(ws.get("recent_spray_yn"))
            last_sp = mgr.get_last_spray_date(farm)
            out["last_spray_date"] = last_sp.isoformat() if last_sp else None
        except Exception:
            out.setdefault("after_bag_yn", False)
            out.setdefault("recent_spray_yn", False)
            out.setdefault("last_spray_date", None)
        return out

    def fetch_weather_ctx(
        self, bridge: ServerDbBridge, farm: str, work_dt: str
    ) -> dict[str, Any]:
        mgr = PesticideAIRecommendManager(bridge)
        try:
            wth = mgr.get_weather_summary(farm) or {}
        except Exception:
            wth = {}
        month = int(work_dt[5:7]) if len(work_dt) >= 7 else int(date.today().month)
        ctx: dict[str, Any] = {
            **wth,
            "farm_cd": farm,
            "current_month": month,
            "work_dt": work_dt,
        }
        return self.apply_work_status_flags(bridge, farm, ctx)

    def _mark_snapshot_dirty(
        self, bridge: ServerDbBridge, farm: str, work_dt: str
    ) -> None:
        ensure_smart_spray_briefing_schema(bridge)
        bridge.execute_query(
            f"""
            UPDATE {TABLE_SMART_SPRAY_BRIEFING}
               SET dirty_yn = 'Y', mod_dt = ?
             WHERE farm_cd = ? AND work_dt = ?
            """,
            (_now(), farm, work_dt),
        )

    def upsert_farm_snapshot(
        self,
        bridge: ServerDbBridge,
        farm: str,
        work_dt: str,
        *,
        weather_ctx: dict[str, Any],
        cards: list[SmartSprayBriefingCard],
        computed_at: str | None = None,
    ) -> str:
        ensure_smart_spray_briefing_schema(bridge)
        ts = computed_at or _now()
        wj = json.dumps(weather_ctx, ensure_ascii=False)
        cj = json.dumps([_card_to_dict(c) for c in cards], ensure_ascii=False)
        existing = bridge.execute_query(
            f"""
            SELECT 1 FROM {TABLE_SMART_SPRAY_BRIEFING}
            WHERE farm_cd = ? AND work_dt = ? LIMIT 1
            """,
            (farm, work_dt),
        ) or []
        if existing:
            bridge.execute_query(
                f"""
                UPDATE {TABLE_SMART_SPRAY_BRIEFING}
                   SET computed_at = ?,
                       param_scope = ?,
                       weather_ctx_json = ?,
                       cards_json = ?,
                       dirty_yn = 'N',
                       mod_dt = ?
                 WHERE farm_cd = ? AND work_dt = ?
                """,
                (ts, PARAM_SCOPE_FARM, wj, cj, ts, farm, work_dt),
            )
        else:
            bridge.execute_query(
                f"""
                INSERT INTO {TABLE_SMART_SPRAY_BRIEFING} (
                    farm_cd, work_dt, computed_at, param_scope,
                    weather_ctx_json, cards_json, dirty_yn, reg_dt, mod_dt
                ) VALUES (?, ?, ?, ?, ?, ?, 'N', ?, ?)
                """,
                (farm, work_dt, ts, PARAM_SCOPE_FARM, wj, cj, ts, ts),
            )
        return ts

    def read_farm_snapshot(
        self, bridge: ServerDbBridge, farm: str, work_dt: str
    ) -> dict[str, Any] | None:
        ensure_smart_spray_briefing_schema(bridge)
        rows = bridge.execute_query(
            f"""
            SELECT farm_cd, work_dt, computed_at, param_scope,
                   weather_ctx_json, cards_json, dirty_yn
              FROM {TABLE_SMART_SPRAY_BRIEFING}
             WHERE farm_cd = ? AND work_dt = ?
             LIMIT 1
            """,
            (farm, work_dt),
        ) or []
        if not rows:
            return None
        r = rows[0]
        try:
            computed_at = _s(r["computed_at"])
            dirty = _s(r["dirty_yn"]).upper() == "Y"
            wraw = r["weather_ctx_json"]
            craw = r["cards_json"]
        except (KeyError, TypeError):
            return None
        try:
            weather_ctx = json.loads(wraw) if isinstance(wraw, str) else dict(wraw or {})
        except (TypeError, json.JSONDecodeError):
            weather_ctx = {}
        try:
            cards_raw = json.loads(craw) if isinstance(craw, str) else list(craw or [])
        except (TypeError, json.JSONDecodeError):
            cards_raw = []
        cards = [
            _card_from_dict(c) for c in cards_raw if isinstance(c, dict)
        ]
        return {
            "computed_at": computed_at,
            "weather_ctx": weather_ctx if isinstance(weather_ctx, dict) else {},
            "cards": cards,
            "dirty": dirty,
        }

    def build_and_persist_farm_snapshot(
        self,
        bridge: ServerDbBridge,
        farm: str,
        work_dt: str,
        *,
        weather_ctx: dict[str, Any] | None = None,
        allow_score_fallback: bool = True,
        fetch_weather: bool = True,
    ) -> tuple[list[SmartSprayBriefingCard], dict[str, Any], str]:
        param_svc = PestOutbreakParamService(bridge)
        rules = param_svc.resolve_pest_rules(farm, None)
        if weather_ctx is None:
            if fetch_weather:
                ctx = self.fetch_weather_ctx(bridge, farm, work_dt)
            else:
                ctx = {
                    "farm_cd": farm,
                    "current_month": int(work_dt[5:7]) if len(work_dt) >= 7 else 1,
                    "work_dt": work_dt,
                }
                self.apply_work_status_flags(bridge, farm, ctx)
        else:
            # dirty rebuild 등: 기상수치는 재사용하되 봉지 여부는 최신으로 갱신
            ctx = dict(weather_ctx)
            ctx.setdefault("farm_cd", farm)
            ctx.setdefault("work_dt", work_dt)
            self.apply_work_status_flags(bridge, farm, ctx)
        cards = self.build_farm_briefing_cards(
            bridge,
            farm,
            rules=rules,
            weather_ctx=ctx,
            work_dt=work_dt,
            allow_score_fallback=allow_score_fallback,
        )
        computed_at = self.upsert_farm_snapshot(
            bridge, farm, work_dt, weather_ctx=ctx, cards=cards
        )
        return cards, ctx, computed_at

    def _user_has_personal_params(
        self, bridge: ServerDbBridge, farm: str, user_id: str | None
    ) -> bool:
        uid = _s(user_id)
        if not uid:
            return False
        rows = PestOutbreakParamService(bridge).list_rows(
            farm, user_id=uid, scope=SCOPE_MINE
        )
        return bool(rows)

    def _patch_observation_stock(
        self,
        bridge: ServerDbBridge,
        farm: str,
        work_dt: str,
        cards: list[SmartSprayBriefingCard],
        *,
        computed_at: str | None,
        rules: dict[str, Any] | None = None,
    ) -> tuple[list[SmartSprayBriefingCard], bool, bool]:
        patched_obs = False
        patched_stock = False
        as_of = date.fromisoformat(work_dt) if len(work_dt) >= 10 else date.today()
        out: list[SmartSprayBriefingCard] = []
        for card in cards:
            pest = card.pest_nm
            obs_id, photo_id, photo_url = self.latest_obs_photo(bridge, farm, pest)
            stock_n = self.stock_count_for_pest(bridge, farm, pest)
            eff = build_efficacy_status(
                bridge, farm, pest, rules=rules, as_of=as_of
            )
            new_obs = obs_id != card.obs_id or photo_url != card.photo_url
            new_stock = stock_n != int(card.stock_count or 0)
            if new_obs:
                patched_obs = True
            if new_stock or eff.get("last_spray_dt") != card.last_spray_dt:
                patched_stock = True
            reasons = list(card.reasons or [])
            # 잔효 안내 문구 재동기화
            reasons = [r for r in reasons if not str(r).startswith("잔효 기간 중")]
            if eff.get("efficacy_active"):
                left = eff.get("efficacy_days_left")
                reasons = [
                    f"잔효 기간 중({left}일 남음, 최근 살포 {eff.get('last_spray_dt')})"
                ] + reasons
            out.append(
                SmartSprayBriefingCard(
                    pest_nm=pest,
                    score=card.score,
                    risk_level=card.risk_level,
                    reasons=reasons,
                    photo_url=photo_url if obs_id else card.photo_url,
                    photo_id=photo_id if obs_id else card.photo_id,
                    obs_id=obs_id or card.obs_id,
                    stock_count=stock_n,
                    last_spray_dt=eff.get("last_spray_dt"),
                    last_spray_item_nm=eff.get("last_spray_item_nm"),
                    last_spray_qty=eff.get("last_spray_qty"),
                    efficacy_days=eff.get("efficacy_days"),
                    efficacy_days_left=eff.get("efficacy_days_left"),
                    efficacy_active=bool(eff.get("efficacy_active")),
                    ctas=self.build_ctas(
                        pest_nm=pest,
                        obs_id=obs_id or card.obs_id,
                        stock_n=stock_n,
                    ),
                )
            )
        return out, patched_obs, patched_stock

    def get_briefing(
        self,
        farm_cd: str,
        *,
        user_id: str | None,
    ) -> SmartSprayBriefingResponse:
        farm = self._ensure_farm(farm_cd)
        today = date.today().isoformat()
        source = "snapshot"
        patched = SmartSprayBriefingPatched()

        with get_sqlite_write_connection(self._db_path) as conn:
            bridge = ServerDbBridge(conn)
            ensure_smart_spray_briefing_schema(bridge)
            snap = self.read_farm_snapshot(bridge, farm, today)

            if snap is None:
                cards, _ctx, computed_at = self.build_and_persist_farm_snapshot(
                    bridge, farm, today, allow_score_fallback=True, fetch_weather=True
                )
                source = "fallback_build"
            elif snap["dirty"]:
                # 농장 파라미터 변경: 가능하면 weather_ctx 재사용(+봉지 플래그 갱신)
                cards, _ctx, computed_at = self.build_and_persist_farm_snapshot(
                    bridge,
                    farm,
                    today,
                    weather_ctx=snap["weather_ctx"] or None,
                    allow_score_fallback=True,
                    fetch_weather=not bool(snap["weather_ctx"]),
                )
                source = "dirty_rebuild"
            else:
                cards = list(snap["cards"])
                computed_at = snap["computed_at"]
                _ctx = dict(snap["weather_ctx"] or {})
                old_bag = _ctx.get("after_bag_yn")
                self.apply_work_status_flags(bridge, farm, _ctx)
                # 스냅샷에 봉지 미반영·변경 시 재점수·재저장
                if old_bag is None or bool(old_bag) != bool(_ctx.get("after_bag_yn")):
                    cards, _ctx, computed_at = self.build_and_persist_farm_snapshot(
                        bridge,
                        farm,
                        today,
                        weather_ctx=_ctx,
                        allow_score_fallback=True,
                        fetch_weather=False,
                    )
                    source = "bag_flag_rebuild"

            # 개인 발병여건 → 스냅샷 weather_ctx로만 재점수 (외부 기상 API 금지)
            personal_rules = None
            if self._user_has_personal_params(bridge, farm, user_id):
                param_svc = PestOutbreakParamService(bridge)
                personal_rules = param_svc.resolve_pest_rules(farm, user_id)
                weather_ctx = dict(_ctx or {})
                weather_ctx.setdefault("farm_cd", farm)
                weather_ctx.setdefault("work_dt", today)
                self.apply_work_status_flags(bridge, farm, weather_ctx)
                cards = self.build_farm_briefing_cards(
                    bridge,
                    farm,
                    rules=personal_rules,
                    weather_ctx=weather_ctx,
                    work_dt=today,
                    allow_score_fallback=True,
                )
                patched.personal = True

            if personal_rules is None:
                personal_rules = PestOutbreakParamService(bridge).resolve_pest_rules(
                    farm, user_id
                )

            cards, p_obs, p_stock = self._patch_observation_stock(
                bridge,
                farm,
                today,
                cards,
                computed_at=computed_at,
                rules=personal_rules,
            )
            patched.observation = p_obs
            patched.stock = p_stock

        return SmartSprayBriefingResponse(
            farm_cd=farm,
            work_dt=today,
            computed_at=computed_at,
            source=source,
            patched=patched,
            cards=cards,
        )
