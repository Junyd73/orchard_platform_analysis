# -*- coding: utf-8 -*-
"""관찰 AI 후보 확정 Application Service — UI·REST 공통.

Stage3 confirm_ai_candidate 저장 규칙을 변경하지 않고 검증·payload 만 담당한다.
"""

from __future__ import annotations

from typing import Any

from core.observation_safe_errors import (
    classify_ai_exception,
    safe_log,
    safe_user_message,
)
from core.observation_stage3 import (
    confirm_ai_candidate,
    get_ai_analysis,
    get_confirmed_candidate,
    list_ai_candidates,
)


class ObservationCandidateConfirmApplicationService:
    """후보 확정 유스케이스 (검증 → Stage3 확정 → 공통 payload)."""

    def confirm_candidate(
        self,
        db,
        *,
        farm_cd: str,
        obs_id: str,
        user_id: str,
        analysis_id: str,
        candidate_seq: int,
        confirmed_name: str | None = None,
        request_id: int = 0,
    ) -> dict[str, Any]:
        farm = str(farm_cd or "").strip()
        oid = str(obs_id or "").strip()
        uid = str(user_id or "").strip()
        aid = str(analysis_id or "").strip()
        req_id = int(request_id)

        fail = {
            "request_id": req_id,
            "ok": False,
            "analysis_id": aid or None,
            "candidate_seq": None,
            "confirmed_name": None,
            "confirmed_by": None,
            "confirmed_at": None,
            "ai_status": None,
            "error_code": "AI_CONFIRM_PARAM",
            "error_message": safe_user_message("AI_CONFIRM_PARAM"),
        }

        try:
            if not farm or not oid or not aid:
                return fail
            if not uid:
                return {
                    **fail,
                    "error_message": "사용자 세션 정보가 없습니다.",
                }
            try:
                seq = int(candidate_seq)
            except (TypeError, ValueError):
                return {
                    **fail,
                    "error_message": "후보 번호가 올바르지 않습니다.",
                }
            fail["candidate_seq"] = seq

            obs = db.get_observation(farm, oid) or {}
            if not obs or str(obs.get("use_yn") or "Y") != "Y":
                return {
                    **fail,
                    "error_message": "대상 관찰을 찾을 수 없습니다.",
                }

            analysis = get_ai_analysis(db, farm, aid)
            if not analysis:
                return {
                    **fail,
                    "error_code": "AI_CONFIRM_NOT_FOUND",
                    "error_message": "분석 정보를 찾을 수 없습니다.",
                }
            if str(analysis.get("obs_id") or "") != oid:
                return {
                    **fail,
                    "error_code": "AI_CONFIRM_PARAM",
                    "error_message": "분석이 해당 관찰에 속하지 않습니다.",
                }

            chosen = None
            for c in list_ai_candidates(db, farm, aid):
                try:
                    if int(c.get("candidate_seq") or -1) == seq:
                        chosen = c
                        break
                except (TypeError, ValueError):
                    continue
            if not chosen:
                return {
                    **fail,
                    "error_code": "AI_CONFIRM_NOT_FOUND",
                    "error_message": safe_user_message("AI_CONFIRM_NOT_FOUND"),
                }

            name = str(confirmed_name or "").strip() or str(
                chosen.get("name_ko") or ""
            ).strip()
            if not name:
                return {
                    **fail,
                    "error_message": "확정 병해충명을 입력해 주세요.",
                }

            ok, msg = confirm_ai_candidate(
                db,
                farm,
                aid,
                seq,
                name,
                uid,
                obs_id=oid,
            )
            if not ok:
                code = "AI_CONFIRM_NOT_FOUND"
                low = str(msg or "")
                if "저장" in low:
                    code = "DB_ERROR"
                elif "세션" in low or "입력" in low or "분석 정보" in low:
                    code = "AI_CONFIRM_PARAM"
                return {
                    **fail,
                    "error_code": code,
                    "error_message": str(msg or safe_user_message(code)),
                }

            conf = get_confirmed_candidate(db, farm, aid) or {}
            after = db.get_observation(farm, oid) or {}
            return {
                "request_id": req_id,
                "ok": True,
                "analysis_id": aid,
                "candidate_seq": seq,
                "confirmed_name": str(
                    conf.get("confirmed_name") or name
                ).strip()
                or name,
                "confirmed_by": conf.get("confirmed_by") or uid,
                "confirmed_at": conf.get("confirmed_at"),
                "ai_status": str(after.get("ai_status") or "CONFIRMED"),
                "error_code": "",
                "error_message": str(msg or "병해충 후보가 확정되었습니다."),
            }
        except Exception as e:
            code, emsg = classify_ai_exception(e)
            if code == "AI_PROVIDER":
                code = "DB_ERROR"
                emsg = safe_user_message("DB_ERROR")
            safe_log(
                code,
                type(e).__name__,
                where="candidate_confirm_app",
                request_id=req_id,
            )
            return {
                **fail,
                "error_code": code,
                "error_message": emsg,
            }
