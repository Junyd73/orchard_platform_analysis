# -*- coding: utf-8 -*-
"""관찰 PSIS(공식 농약정보) Application Service — UI·REST 공통 유스케이스.

PsisSearchWorker / FastAPI 가 동일하게 호출한다.
PSIS Provider·search_with_cache_policy·Snapshot 저장 방식은 변경하지 않는다.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from core.observation_safe_errors import (
    classify_psis_exception,
    safe_log,
    safe_user_message,
    sanitize_stored_error,
)
from core.observation_stage3 import (
    get_ai_analysis,
    get_confirmed_candidate,
    get_latest_ai_analysis,
    list_ai_candidates,
    list_pesticide_snapshots,
)
from core.pesticide.pesticide_service import ObservationPesticideService

ProgressCb = Callable[[str], None]


class ObservationPsisApplicationService:
    """PSIS 조회 유스케이스 (검증·후보 확인·검색·스냅샷·payload)."""

    def __init__(self, provider=None):
        self._provider = provider

    def run_search(
        self,
        db,
        *,
        farm_cd: str,
        obs_id: str,
        user_id: str,
        crop_name: str = "",
        disease_name: str = "",
        analysis_id: str | None = None,
        candidate_seq: int | None = None,
        force_refresh: bool = False,
        allow_similar: bool = False,
        request_id: int = 0,
        on_progress: ProgressCb | None = None,
    ) -> dict[str, Any]:
        """PSIS 검색 실행. 성공·실패 동일 형식 dict.

        crop/disease 가 비어 있으면 analysis_id·확정 후보에서 해석한다.
        """
        farm = str(farm_cd or "").strip()
        oid = str(obs_id or "").strip()
        uid = str(user_id or "").strip()
        req_id = int(request_id)

        def _progress(msg: str) -> None:
            if on_progress is not None:
                on_progress(msg)

        base_fail: dict[str, Any] = {
            "request_id": req_id,
            "ok": False,
            "items": [],
            "error_code": "INTERNAL",
            "error_message": safe_user_message("INTERNAL", domain="PSIS"),
            "from_cache": False,
            "analysis_id": None,
            "candidate_seq": None,
            "crop_name": "",
            "disease_name": "",
            "snapshot_ids": [],
        }

        try:
            _progress("조회 준비 중…")
            if not farm or not oid:
                return {
                    **base_fail,
                    "error_code": "PSIS_PARAM",
                    "error_message": safe_user_message("PSIS_PARAM", domain="PSIS"),
                }
            if not uid:
                return {
                    **base_fail,
                    "error_code": "PSIS_PARAM",
                    "error_message": "사용자 세션 정보가 없습니다.",
                }
            obs = db.get_observation(farm, oid) or {}
            if not obs or str(obs.get("use_yn") or "Y") != "Y":
                return {
                    **base_fail,
                    "error_code": "PSIS_PARAM",
                    "error_message": "대상 관찰을 찾을 수 없습니다.",
                }

            resolved = self._resolve_query(
                db,
                farm=farm,
                obs_id=oid,
                crop_name=crop_name,
                disease_name=disease_name,
                analysis_id=analysis_id,
                candidate_seq=candidate_seq,
            )
            if not resolved.get("ok"):
                return {
                    **base_fail,
                    "error_code": resolved.get("error_code") or "PSIS_PARAM",
                    "error_message": resolved.get("error_message")
                    or safe_user_message("PSIS_PARAM", domain="PSIS"),
                    "analysis_id": resolved.get("analysis_id"),
                    "candidate_seq": resolved.get("candidate_seq"),
                }

            crop = str(resolved["crop_name"])
            disease = str(resolved["disease_name"])
            aid = resolved.get("analysis_id")
            seq = resolved.get("candidate_seq")

            _progress("공식 등록정보 조회 중…")
            svc = ObservationPesticideService(provider=self._provider)
            result = svc.search_with_cache_policy(
                db,
                farm,
                oid,
                crop,
                disease,
                force_refresh=bool(force_refresh),
                allow_similar=bool(allow_similar),
                user_id=uid,
                analysis_id=aid,
            )
            result = dict(result or {})
            result["request_id"] = req_id
            result["analysis_id"] = aid
            result["candidate_seq"] = seq
            result["crop_name"] = crop
            result["disease_name"] = disease

            if result.get("error_code"):
                ec, em = sanitize_stored_error(
                    result.get("error_code"),
                    result.get("error_message"),
                    domain="PSIS",
                )
                result["error_code"] = ec
                result["error_message"] = em

            # 방금 저장된 스냅샷 ID (동일 crop+disease 활성 행)
            snap_ids: list[str] = []
            if result.get("ok") and result.get("saved"):
                rows = list_pesticide_snapshots(
                    db, farm, oid, crop_name=crop, disease_name=disease
                )
                snap_ids = [
                    str(r.get("snapshot_id") or "")
                    for r in rows
                    if r.get("snapshot_id")
                ]
            result["snapshot_ids"] = snap_ids
            if snap_ids:
                result["snapshot_id"] = snap_ids[0]
            elif result.get("ok") and result.get("from_cache"):
                rows = list_pesticide_snapshots(
                    db, farm, oid, crop_name=crop, disease_name=disease
                )
                if rows:
                    result["snapshot_id"] = str(rows[0].get("snapshot_id") or "") or None
                    result["snapshot_ids"] = [
                        str(r.get("snapshot_id") or "")
                        for r in rows
                        if r.get("snapshot_id")
                    ]
            return result
        except Exception as e:
            code, msg = classify_psis_exception(e)
            safe_log(code, type(e).__name__, where="psis_app_service", request_id=req_id)
            return {
                **base_fail,
                "error_code": code,
                "error_message": msg,
            }

    def _resolve_query(
        self,
        db,
        *,
        farm: str,
        obs_id: str,
        crop_name: str,
        disease_name: str,
        analysis_id: str | None,
        candidate_seq: int | None,
    ) -> dict[str, Any]:
        crop = str(crop_name or "").strip()
        disease = str(disease_name or "").strip()
        aid = str(analysis_id or "").strip() or None
        seq = candidate_seq

        if aid:
            analysis = get_ai_analysis(db, farm, aid)
            if not analysis or str(analysis.get("obs_id") or "") != obs_id:
                return {
                    "ok": False,
                    "error_code": "PSIS_PARAM",
                    "error_message": "분석 정보를 찾을 수 없거나 관찰과 일치하지 않습니다.",
                    "analysis_id": aid,
                    "candidate_seq": seq,
                }
        elif not disease:
            latest = get_latest_ai_analysis(db, farm, obs_id)
            if latest:
                aid = str(latest.get("analysis_id") or "").strip() or None

        if not disease:
            if not aid:
                return {
                    "ok": False,
                    "error_code": "PSIS_PARAM",
                    "error_message": safe_user_message("PSIS_PARAM", domain="PSIS"),
                }
            if seq is not None:
                try:
                    want = int(seq)
                except (TypeError, ValueError):
                    return {
                        "ok": False,
                        "error_code": "PSIS_PARAM",
                        "error_message": "후보 번호가 올바르지 않습니다.",
                        "analysis_id": aid,
                    }
                cands = list_ai_candidates(db, farm, aid)
                chosen = None
                for c in cands:
                    try:
                        if int(c.get("candidate_seq") or -1) == want:
                            chosen = c
                            break
                    except (TypeError, ValueError):
                        continue
                if not chosen:
                    return {
                        "ok": False,
                        "error_code": "PSIS_PARAM",
                        "error_message": "후보를 찾을 수 없습니다.",
                        "analysis_id": aid,
                        "candidate_seq": want,
                    }
                if str(chosen.get("selected_yn") or "N") != "Y":
                    return {
                        "ok": False,
                        "error_code": "PSIS_PARAM",
                        "error_message": "확정된 후보가 아닙니다. 후보 확정 후 조회해 주세요.",
                        "analysis_id": aid,
                        "candidate_seq": want,
                    }
                disease = str(
                    chosen.get("confirmed_name") or chosen.get("name_ko") or ""
                ).strip()
                seq = want
            else:
                conf = get_confirmed_candidate(db, farm, aid)
                if not conf:
                    return {
                        "ok": False,
                        "error_code": "PSIS_PARAM",
                        "error_message": "확정된 후보가 없습니다. 후보 확정 후 조회해 주세요.",
                        "analysis_id": aid,
                    }
                disease = str(
                    conf.get("confirmed_name") or conf.get("name_ko") or ""
                ).strip()
                try:
                    seq = int(conf.get("candidate_seq"))
                except (TypeError, ValueError):
                    seq = None

        if not crop or not disease:
            return {
                "ok": False,
                "error_code": "PSIS_PARAM",
                "error_message": safe_user_message("PSIS_PARAM", domain="PSIS"),
                "analysis_id": aid,
                "candidate_seq": seq,
            }
        return {
            "ok": True,
            "crop_name": crop,
            "disease_name": disease,
            "analysis_id": aid,
            "candidate_seq": seq,
        }
