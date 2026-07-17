# -*- coding: utf-8 -*-
"""관찰 서비스 — 조회 + DRAFT/COMPLETED 생명주기."""

from __future__ import annotations

import logging
import re
import sqlite3
from datetime import date
from pathlib import Path

from app.core.exceptions import BusinessRuleError, EntityNotFoundError
from app.core.observation_constants import (
    MOBILE_BASIC_TARGET_CDS,
    OBS_AI_STATUS_NONE,
    OBS_PROGRESS_WATCHING_CD,
    OBS_SEVERITY_NORMAL_CD,
    TARGET_DEFAULT_OBS_TYPE,
)
from app.core.observation_delete_policy import can_delete_observation
from app.core.observation_lifecycle import (
    OBS_RECORD_ACTIVE,
    OBS_STATUS_COMPLETED,
    OBS_STATUS_DRAFT,
)
from app.db.sqlite import get_sqlite_connection, get_sqlite_write_connection
from app.repository.interfaces.observation_photo_repository import (
    ObservationPhotoRepository,
)
from app.repository.interfaces.observation_repository import ObservationRepository
from app.schemas.observation import (
    ObservationBasicCreateRequest,
    ObservationBasicUpdateRequest,
    ObservationDetail,
    ObservationDraftItem,
    ObservationListItem,
    ObservationSaveResponse,
    ObservationSummary,
)
from app.services.observation_media import compensate_photo_files

logger = logging.getLogger(__name__)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# 관찰 관련 부속 테이블 (존재 시 물리 DELETE)
_RELATED_TABLES_BY_OBS = (
    "t_observation_fruit_measurement",
    "t_observation_pesticide_snapshot",
)
_AI_ANALYSIS_TABLE = "t_observation_ai_analysis"
_AI_CANDIDATE_TABLE = "t_observation_ai_candidate"
_AI_PHOTO_TABLE = "t_observation_ai_photo"


class ObservationService:
    def __init__(
        self,
        repo: ObservationRepository,
        *,
        photo_repo: ObservationPhotoRepository | None = None,
        media_root: Path | str | None = None,
    ):
        self._repo = repo
        self._photo_repo = photo_repo
        self._media_root = Path(media_root) if media_root else None

    def _ensure_farm(self, farm_cd: str) -> str:
        farm = str(farm_cd or "").strip()
        if not farm or not self._repo.farm_exists(farm):
            raise EntityNotFoundError("Farm not found")
        return farm

    def _user_id(self, user_id: str | None, default: str = "MOBILE") -> str:
        uid = str(user_id or "").strip()
        return uid or default

    def _resolve_user(
        self, user_id: str, role_hint: str | None = None
    ) -> tuple[str, str]:
        """m_user 기준 (role_cd, farm_cd). role_hint 가 있으면 role만 덮어쓴다."""
        uid = str(user_id or "").strip()
        if not uid:
            return "", ""
        role = ""
        farm = ""
        db_path = getattr(self._repo, "_db_path", None)
        if db_path is not None:
            try:
                with get_sqlite_connection(db_path) as conn:
                    row = conn.execute(
                        """
                        SELECT role_cd, farm_cd FROM m_user
                        WHERE user_id = ? AND COALESCE(use_yn, 'Y') = 'Y'
                        LIMIT 1
                        """,
                        (uid,),
                    ).fetchone()
                if row:
                    role = str(row["role_cd"] or "").strip().upper()
                    farm = str(row["farm_cd"] or "").strip().upper()
            except Exception:
                role, farm = "", ""
        hint = str(role_hint or "").strip().upper()
        if hint:
            role = hint
        return role, farm

    def _resolve_role(self, user_id: str, role_hint: str | None = None) -> str:
        role, _farm = self._resolve_user(user_id, role_hint)
        return role

    def _with_can_delete(
        self,
        detail: ObservationDetail,
        *,
        user_id: str | None,
        user_role: str | None = None,
        farm_cd: str | None = None,
    ) -> ObservationDetail:
        uid = self._user_id(user_id)
        role, user_farm = self._resolve_user(uid, user_role)
        target_farm = str(farm_cd or detail.farm_cd or "").strip()
        allowed = (
            detail.observation_status == OBS_STATUS_COMPLETED
            and detail.record_status == OBS_RECORD_ACTIVE
            and can_delete_observation(
                reg_id=detail.reg_id,
                user_id=uid,
                role_cd=role,
                user_farm_cd=user_farm,
                target_farm_cd=target_farm,
            )
        )
        return detail.model_copy(update={"can_delete": allowed})

    def _normalize_basic(
        self, body: ObservationBasicCreateRequest | ObservationBasicUpdateRequest
    ) -> dict:
        obs_dt = str(body.obs_dt or "").strip()
        if not _DATE_RE.match(obs_dt):
            raise BusinessRuleError("관찰일은 YYYY-MM-DD 형식이어야 합니다.")
        target = str(body.target_type_cd or "").strip()
        if target not in MOBILE_BASIC_TARGET_CDS:
            raise BusinessRuleError(
                "관찰 대상은 병해충(OB010400) 또는 과실(OB010200)만 선택할 수 있습니다."
            )
        site_id = str(body.site_id or "").strip()
        if not site_id:
            raise BusinessRuleError("필지를 선택해 주세요.")

        title = str(body.obs_title or "").strip()
        content = str(body.obs_content or "").strip()
        if not title and not content:
            raise BusinessRuleError("제목 또는 관찰 내용을 입력해 주세요.")
        if not title:
            title = content[:80]
        if not content:
            content = title

        obs_type = TARGET_DEFAULT_OBS_TYPE[target]
        return {
            "obs_dt": obs_dt,
            "target_type_cd": target,
            "obs_type_cd": obs_type,
            "site_id": site_id,
            "severity_cd": OBS_SEVERITY_NORMAL_CD,
            "progress_status_cd": OBS_PROGRESS_WATCHING_CD,
            "obs_title": title,
            "obs_content": content,
            "ai_status": OBS_AI_STATUS_NONE,
        }

    def get_summary(
        self, farm_cd: str, *, as_of_date: str | None = None
    ) -> ObservationSummary:
        farm = self._ensure_farm(farm_cd)
        day = str(as_of_date or "").strip() or date.today().isoformat()
        return self._repo.get_summary(farm, as_of_date=day)

    def list_observations(
        self,
        farm_cd: str,
        *,
        date_from: str | None = None,
        date_to: str | None = None,
        site_id: str | None = None,
        keyword: str | None = None,
        sort: str = "obs_dt_desc",
        limit: int = 50,
    ) -> list[ObservationListItem]:
        farm = self._ensure_farm(farm_cd)
        return self._repo.list_observations(
            farm,
            date_from=date_from,
            date_to=date_to,
            site_id=site_id,
            keyword=keyword,
            sort=sort,
            limit=limit,
        )

    def list_drafts(self, farm_cd: str, *, limit: int = 50) -> list[ObservationDraftItem]:
        farm = self._ensure_farm(farm_cd)
        return self._repo.list_drafts(farm, limit=limit)

    def get_observation(
        self,
        farm_cd: str,
        obs_id: str,
        *,
        user_id: str | None = None,
        user_role: str | None = None,
    ) -> ObservationDetail:
        farm = self._ensure_farm(farm_cd)
        detail = self._repo.get_observation(farm, str(obs_id or "").strip())
        if not detail:
            raise EntityNotFoundError("Observation not found")
        return self._with_can_delete(
            detail, user_id=user_id, user_role=user_role, farm_cd=farm
        )

    def create_basic(
        self,
        farm_cd: str,
        body: ObservationBasicCreateRequest,
        *,
        user_id: str | None = None,
    ) -> ObservationSaveResponse:
        farm = self._ensure_farm(farm_cd)
        uid = self._user_id(user_id)
        row = self._normalize_basic(body)
        if not self._repo.site_exists(farm, row["site_id"]):
            raise BusinessRuleError("선택한 필지를 찾을 수 없습니다.")
        obs_id = self._repo.generate_obs_id(farm, row["obs_dt"])
        row["farm_cd"] = farm
        row["obs_id"] = obs_id
        self._repo.insert_observation(row, uid)
        return ObservationSaveResponse(
            obs_id=obs_id,
            farm_cd=farm,
            created=True,
            message="기본정보가 저장되었습니다. (작성 중)",
            observation_status=OBS_STATUS_DRAFT,
        )

    def update_basic(
        self,
        farm_cd: str,
        obs_id: str,
        body: ObservationBasicUpdateRequest,
        *,
        user_id: str | None = None,
    ) -> ObservationSaveResponse:
        farm = self._ensure_farm(farm_cd)
        oid = str(obs_id or "").strip()
        if not oid:
            raise EntityNotFoundError("Observation not found")
        exist = self._repo.get_observation(farm, oid)
        if not exist:
            raise EntityNotFoundError("Observation not found")
        if exist.record_status != OBS_RECORD_ACTIVE:
            raise BusinessRuleError("삭제된 관찰은 수정할 수 없습니다.")
        if exist.observation_status not in (OBS_STATUS_DRAFT, OBS_STATUS_COMPLETED):
            raise BusinessRuleError("수정할 수 없는 상태입니다.")
        uid = self._user_id(user_id)
        row = self._normalize_basic(body)
        if not self._repo.site_exists(farm, row["site_id"]):
            raise BusinessRuleError("선택한 필지를 찾을 수 없습니다.")
        ok = self._repo.update_observation_basic(farm, oid, row, uid)
        if not ok:
            raise EntityNotFoundError("Observation not found")
        return ObservationSaveResponse(
            obs_id=oid,
            farm_cd=farm,
            created=False,
            message="기본정보가 수정되었습니다.",
            observation_status=exist.observation_status,
        )

    def complete(
        self,
        farm_cd: str,
        obs_id: str,
        *,
        user_id: str | None = None,
    ) -> ObservationSaveResponse:
        farm = self._ensure_farm(farm_cd)
        oid = str(obs_id or "").strip()
        exist = self._repo.get_observation(farm, oid)
        if not exist:
            raise EntityNotFoundError("Observation not found")
        if exist.observation_status != OBS_STATUS_DRAFT:
            raise BusinessRuleError("작성 중(DRAFT) 관찰만 완료할 수 있습니다.")
        uid = self._user_id(user_id)
        ok = self._repo.complete_observation(farm, oid, uid)
        if not ok:
            raise BusinessRuleError("관찰 완료 처리에 실패했습니다.")
        return ObservationSaveResponse(
            obs_id=oid,
            farm_cd=farm,
            created=False,
            message="관찰이 완료되었습니다.",
            observation_status=OBS_STATUS_COMPLETED,
        )

    def cancel_draft(
        self,
        farm_cd: str,
        obs_id: str,
        *,
        user_id: str | None = None,
    ) -> ObservationSaveResponse:
        farm = self._ensure_farm(farm_cd)
        oid = str(obs_id or "").strip()
        exist = self._repo.get_observation(farm, oid)
        if not exist:
            raise EntityNotFoundError("Observation not found")
        if exist.observation_status != OBS_STATUS_DRAFT:
            raise BusinessRuleError("작성 중(DRAFT) 관찰만 취소할 수 있습니다.")
        uid = self._user_id(user_id)

        # 사진 파일 + DB 물리 삭제 (사진 HTTP API 변경 없음)
        if self._photo_repo is not None and self._media_root is not None:
            photos = self._photo_repo.list_all_photos_for_obs(farm, oid)
            rels: list[str] = []
            for p in photos:
                for key in ("file_path", "thumb_path"):
                    rel = str(p.get(key) or "").strip()
                    if rel:
                        rels.append(rel)
            if rels:
                compensate_photo_files(self._media_root, rels)
            self._photo_repo.hard_delete_photos_for_obs(farm, oid)

        self._cleanup_ai_psis_temp(farm, oid)

        ok = self._repo.cancel_draft_observation(farm, oid, uid)
        if not ok:
            raise BusinessRuleError("작성 취소에 실패했습니다.")
        return ObservationSaveResponse(
            obs_id=oid,
            farm_cd=farm,
            created=False,
            message="작성 중인 관찰을 취소했습니다.",
            observation_status="CANCELLED",
        )

    def soft_delete(
        self,
        farm_cd: str,
        obs_id: str,
        *,
        user_id: str | None = None,
        user_role: str | None = None,
        delete_reason: str | None = None,
    ) -> ObservationSaveResponse:
        """완료 관찰 업무 삭제 — 관련 데이터·파일 물리 삭제 + 마스터 DELETED."""
        farm = self._ensure_farm(farm_cd)
        oid = str(obs_id or "").strip()
        exist = self._repo.get_observation(farm, oid)
        if not exist:
            raise EntityNotFoundError("Observation not found")
        if exist.observation_status != OBS_STATUS_COMPLETED:
            raise BusinessRuleError("완료된 관찰만 삭제할 수 있습니다.")
        uid = self._user_id(user_id)
        role, user_farm = self._resolve_user(uid, user_role)
        if not can_delete_observation(
            reg_id=exist.reg_id,
            user_id=uid,
            role_cd=role,
            user_farm_cd=user_farm,
            target_farm_cd=farm,
        ):
            raise BusinessRuleError("삭제 권한이 없습니다.")

        # 1) 삭제 대상 파일 경로 수집
        file_rels: list[str] = []
        if self._photo_repo is not None:
            for p in self._photo_repo.list_all_photos_for_obs(farm, oid):
                for key in ("file_path", "thumb_path"):
                    rel = str(p.get(key) or "").strip()
                    if rel:
                        file_rels.append(rel)

        # 2) DB 트랜잭션: 관련 행 삭제 + 마스터 DELETED
        self._purge_related_db_and_mark_deleted(
            farm, oid, uid, delete_reason=delete_reason
        )

        # 3) 파일 삭제 (DB 커밋 후 — 실패해도 목록에는 안 남음)
        if file_rels and self._media_root is not None:
            try:
                compensate_photo_files(self._media_root, file_rels)
            except Exception:
                logger.exception("observation file purge failed obs_id=%s", oid)

        return ObservationSaveResponse(
            obs_id=oid,
            farm_cd=farm,
            created=False,
            message="관찰 기록이 삭제되었습니다.",
            observation_status=exist.observation_status,
        )

    def _purge_related_db_and_mark_deleted(
        self,
        farm_cd: str,
        obs_id: str,
        user_id: str,
        *,
        delete_reason: str | None,
    ) -> None:
        db_path = getattr(self._repo, "_db_path", None)
        if db_path is None:
            raise BusinessRuleError("삭제에 실패했습니다.")
        reason = str(delete_reason or "").strip() or "사용자 삭제"
        try:
            with get_sqlite_write_connection(db_path) as conn:
                existing = {
                    str(r[0])
                    for r in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).fetchall()
                }
                # AI 자식 → 헤더
                if _AI_ANALYSIS_TABLE in existing:
                    aids = [
                        str(r[0])
                        for r in conn.execute(
                            f"""
                            SELECT analysis_id FROM {_AI_ANALYSIS_TABLE}
                            WHERE farm_cd = ? AND obs_id = ?
                            """,
                            (farm_cd, obs_id),
                        ).fetchall()
                        if r[0]
                    ]
                    for aid in aids:
                        if _AI_CANDIDATE_TABLE in existing:
                            conn.execute(
                                f"DELETE FROM {_AI_CANDIDATE_TABLE} WHERE analysis_id = ?",
                                (aid,),
                            )
                        if _AI_PHOTO_TABLE in existing:
                            conn.execute(
                                f"DELETE FROM {_AI_PHOTO_TABLE} WHERE analysis_id = ?",
                                (aid,),
                            )
                    conn.execute(
                        f"""
                        DELETE FROM {_AI_ANALYSIS_TABLE}
                        WHERE farm_cd = ? AND obs_id = ?
                        """,
                        (farm_cd, obs_id),
                    )
                for table in _RELATED_TABLES_BY_OBS:
                    if table not in existing:
                        continue
                    try:
                        conn.execute(
                            f"DELETE FROM {table} WHERE farm_cd = ? AND obs_id = ?",
                            (farm_cd, obs_id),
                        )
                    except sqlite3.Error:
                        logger.debug("purge skip %s", table, exc_info=True)

                # 사진 DB
                if "t_observation_photo" in existing:
                    conn.execute(
                        """
                        DELETE FROM t_observation_photo
                        WHERE farm_cd = ? AND obs_id = ?
                        """,
                        (farm_cd, obs_id),
                    )

                from datetime import datetime as _dt

                from app.core.observation_lifecycle import OBS_RECORD_DELETED

                now = _dt.now().strftime("%Y-%m-%d %H:%M:%S")
                cur = conn.execute(
                    """
                    UPDATE t_observation_master SET
                        record_status = ?,
                        use_yn = 'N',
                        deleted_at = ?,
                        deleted_by = ?,
                        delete_reason = ?,
                        mod_id = ?,
                        mod_dt = ?
                    WHERE farm_cd = ? AND obs_id = ?
                      AND COALESCE(observation_status, 'DRAFT') = ?
                      AND COALESCE(record_status, 'ACTIVE') = ?
                      AND COALESCE(use_yn, 'Y') = 'Y'
                    """,
                    (
                        OBS_RECORD_DELETED,
                        now,
                        user_id,
                        reason,
                        user_id,
                        now,
                        farm_cd,
                        obs_id,
                        OBS_STATUS_COMPLETED,
                        OBS_RECORD_ACTIVE,
                    ),
                )
                if cur.rowcount <= 0:
                    raise BusinessRuleError("삭제에 실패했습니다.")
                conn.commit()
        except BusinessRuleError:
            raise
        except Exception as exc:
            logger.exception("purge failed")
            raise BusinessRuleError("삭제에 실패했습니다.") from exc

    def _cleanup_ai_psis_temp(self, farm_cd: str, obs_id: str) -> None:
        """작성 취소 시 AI/PSIS 물리 삭제 (테이블 없으면 무시)."""
        db_path = getattr(self._repo, "_db_path", None)
        if db_path is None:
            return
        try:
            with get_sqlite_write_connection(db_path) as conn:
                existing = {
                    str(r[0])
                    for r in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).fetchall()
                }
                if _AI_ANALYSIS_TABLE in existing:
                    aids = [
                        str(r[0])
                        for r in conn.execute(
                            f"""
                            SELECT analysis_id FROM {_AI_ANALYSIS_TABLE}
                            WHERE farm_cd = ? AND obs_id = ?
                            """,
                            (farm_cd, obs_id),
                        ).fetchall()
                        if r[0]
                    ]
                    for aid in aids:
                        if _AI_CANDIDATE_TABLE in existing:
                            conn.execute(
                                f"DELETE FROM {_AI_CANDIDATE_TABLE} WHERE analysis_id = ?",
                                (aid,),
                            )
                        if _AI_PHOTO_TABLE in existing:
                            conn.execute(
                                f"DELETE FROM {_AI_PHOTO_TABLE} WHERE analysis_id = ?",
                                (aid,),
                            )
                    conn.execute(
                        f"""
                        DELETE FROM {_AI_ANALYSIS_TABLE}
                        WHERE farm_cd = ? AND obs_id = ?
                        """,
                        (farm_cd, obs_id),
                    )
                for table in _RELATED_TABLES_BY_OBS:
                    if table not in existing:
                        continue
                    try:
                        conn.execute(
                            f"DELETE FROM {table} WHERE farm_cd = ? AND obs_id = ?",
                            (farm_cd, obs_id),
                        )
                    except sqlite3.Error:
                        logger.debug("cleanup skip %s", table, exc_info=True)
                conn.commit()
        except Exception:
            logger.debug("AI/PSIS cleanup skipped", exc_info=True)
