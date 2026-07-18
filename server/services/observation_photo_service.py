# -*- coding: utf-8 -*-
"""관찰 사진 서비스 — 업로드/삭제/목록/대표사진 (등록 저장과 분리)."""

from __future__ import annotations

from pathlib import Path

from app.core.exceptions import BusinessRuleError, EntityNotFoundError
from app.db.sqlite import get_sqlite_write_connection
from app.repository.interfaces.observation_photo_repository import (
    ObservationPhotoRepository,
)
from app.schemas.observation_photo import (
    ObservationPhotoItem,
    ObservationPhotoListResponse,
    ObservationPhotoUploadResponse,
)
from app.services._core_path import ensure_repo_root_on_path
from app.services.observation_ai_db_bridge import ServerDbBridge
from app.services.observation_media import (
    OBS_PHOTO_MAX_COUNT,
    resolve_media_path,
)
from app.services.photo_display_name import build_photo_display_nm

_YN_Y = "Y"


class ObservationPhotoService:
    def __init__(
        self,
        repo: ObservationPhotoRepository,
        *,
        media_root: Path,
        db_path: Path | str | None = None,
        default_user_id: str = "MOBILE",
    ):
        self._repo = repo
        self._media_root = Path(media_root)
        self._db_path = Path(db_path) if db_path else None
        self._default_user_id = str(default_user_id or "MOBILE").strip() or "MOBILE"

    def _ensure_farm(self, farm_cd: str) -> str:
        farm = str(farm_cd or "").strip()
        if not farm or not self._repo.farm_exists(farm):
            raise EntityNotFoundError("Farm not found")
        return farm

    def _ensure_observation(self, farm_cd: str, obs_id: str) -> dict:
        oid = str(obs_id or "").strip()
        if not oid:
            raise EntityNotFoundError("Observation not found")
        obs = self._repo.get_observation(farm_cd, oid)
        if not obs:
            raise EntityNotFoundError("Observation not found")
        return obs

    def _user_id(self, user_id: str | None) -> str:
        """목록·삭제 등 기존 동작용. 업로드는 require_user_id 사용."""
        uid = str(user_id or "").strip()
        return uid or self._default_user_id

    def _require_user_id(self, user_id: str | None) -> str:
        uid = str(user_id or "").strip()
        if not uid:
            raise BusinessRuleError("사용자 세션 정보가 없습니다.")
        return uid

    def _urls(self, farm_cd: str, obs_id: str, photo_id: str) -> tuple[str, str]:
        """VITE_API_BASE_URL(/api/v1)에 붙일 상대경로. /api/v1 중복 금지."""
        base = f"/farms/{farm_cd}/observations/{obs_id}/photos/{photo_id}"
        return f"{base}/thumbnail", f"{base}/original"

    def _to_item(
        self,
        row: dict,
        *,
        obs: dict,
        index: int,
        is_representative: bool,
    ) -> ObservationPhotoItem:
        farm = str(row.get("farm_cd") or "")
        oid = str(row.get("obs_id") or "")
        pid = str(row.get("photo_id") or "")
        thumb_url, original_url = self._urls(farm, oid, pid)
        sort_no = row.get("sort_no")
        try:
            sn = int(sort_no) if sort_no is not None else index + 1
        except (TypeError, ValueError):
            sn = index + 1
        seq = index + 1
        display_nm = build_photo_display_nm(
            target_type_cd=str(obs.get("target_type_cd") or ""),
            target_type_nm=str(obs.get("target_type_nm") or ""),
            site_nm=str(obs.get("site_nm") or ""),
            obs_dt=str(obs.get("obs_dt") or ""),
            seq=seq,
            file_ext=str(row.get("file_ext") or "") or None,
        )
        return ObservationPhotoItem(
            photo_id=pid,
            obs_id=oid,
            farm_cd=farm,
            sort_no=sn,
            is_representative=is_representative,
            display_nm=display_nm,
            original_nm=row.get("original_nm"),
            stored_nm=row.get("stored_nm"),
            file_ext=row.get("file_ext"),
            file_size=int(row["file_size"]) if row.get("file_size") is not None else None,
            width_px=int(row["width_px"]) if row.get("width_px") is not None else None,
            height_px=int(row["height_px"]) if row.get("height_px") is not None else None,
            thumb_url=thumb_url,
            original_url=original_url,
        )

    def list_photos(self, farm_cd: str, obs_id: str) -> ObservationPhotoListResponse:
        farm = self._ensure_farm(farm_cd)
        obs = self._ensure_observation(farm, obs_id)
        rows = self._repo.list_photos(farm, obs_id)
        photos = [
            self._to_item(r, obs=obs, index=i, is_representative=(i == 0))
            for i, r in enumerate(rows)
        ]
        count = len(photos)
        return ObservationPhotoListResponse(
            obs_id=str(obs_id).strip(),
            count=count,
            max_count=OBS_PHOTO_MAX_COUNT,
            remaining=max(0, OBS_PHOTO_MAX_COUNT - count),
            photos=photos,
        )

    def get_representative(
        self, farm_cd: str, obs_id: str
    ) -> ObservationPhotoItem | None:
        farm = self._ensure_farm(farm_cd)
        obs = self._ensure_observation(farm, obs_id)
        rows = self._repo.list_photos(farm, obs_id)
        if not rows:
            return None
        return self._to_item(rows[0], obs=obs, index=0, is_representative=True)

    async def upload_photos(
        self,
        farm_cd: str,
        obs_id: str,
        files: list,
        *,
        user_id: str | None = None,
    ) -> ObservationPhotoUploadResponse:
        farm = self._ensure_farm(farm_cd)
        obs = self._ensure_observation(farm, obs_id)
        uid = self._require_user_id(user_id)
        oid = str(obs_id).strip()

        if self._db_path is None:
            raise BusinessRuleError("사진 저장소 설정이 없습니다.")

        upload_files = list(files or [])
        if not upload_files:
            raise BusinessRuleError("업로드할 파일이 없습니다.")

        ensure_repo_root_on_path()
        from core.observation_photo_upload_application_service import (
            ObservationPhotoUploadApplicationService,
        )

        app_svc = ObservationPhotoUploadApplicationService()
        new_photo_ids: list[str] = []
        skipped: list[str] = []
        last_ok: dict | None = None
        last_fail: dict | None = None

        with get_sqlite_write_connection(self._db_path) as conn:
            db = ServerDbBridge(conn)
            for f in upload_files:
                filename = str(getattr(f, "filename", None) or "photo.jpg")
                data = await f.read()
                payload = app_svc.upload(
                    db,
                    farm_cd=farm,
                    obs_id=oid,
                    user_id=uid,
                    media_root=self._media_root,
                    data=data,
                    original_nm=filename,
                    max_count=OBS_PHOTO_MAX_COUNT,
                )
                if payload.get("ok"):
                    new_photo_ids.append(str(payload.get("photo_id") or ""))
                    last_ok = payload
                else:
                    last_fail = payload
                    code = str(payload.get("error_code") or "")
                    if code == "PHOTO_DUP":
                        skipped.append(filename)
                        continue
                    # 첫 실패(한도·형식 등)는 즉시 중단
                    raise BusinessRuleError(
                        str(
                            payload.get("error_message")
                            or payload.get("error")
                            or "사진 업로드에 실패했습니다."
                        )
                    )

        listing = self.list_photos(farm, oid)
        id_set = set(new_photo_ids)
        uploaded = [p for p in listing.photos if p.photo_id in id_set]
        msg = f"{len(uploaded)}장이 등록되었습니다."
        if skipped:
            msg += f" (중복 {len(skipped)}장 제외)"

        first = last_ok or {}
        return ObservationPhotoUploadResponse(
            uploaded=uploaded,
            skipped=skipped,
            count=listing.count,
            max_count=listing.max_count,
            remaining=listing.remaining,
            message=msg,
            success=bool(uploaded),
            photo_id=first.get("photo_id") if uploaded else None,
            farm_cd=farm if uploaded else None,
            obs_id=oid if uploaded else None,
            file_name=first.get("file_name") if uploaded else None,
            file_path=first.get("file_path") if uploaded else None,
            thumbnail_path=first.get("thumbnail_path") if uploaded else None,
            file_size=first.get("file_size") if uploaded else None,
            width=first.get("width") if uploaded else None,
            height=first.get("height") if uploaded else None,
            created_by=first.get("created_by") if uploaded else None,
            created_at=first.get("created_at") if uploaded else None,
            error=None,
            error_code=None,
        )

    def delete_photo(
        self,
        farm_cd: str,
        obs_id: str,
        photo_id: str,
        *,
        user_id: str | None = None,
    ) -> None:
        farm = self._ensure_farm(farm_cd)
        self._ensure_observation(farm, obs_id)
        uid = self._user_id(user_id)
        pid = str(photo_id or "").strip()
        row = self._repo.get_photo(farm, pid)
        if (
            not row
            or str(row.get("obs_id") or "") != str(obs_id).strip()
            or str(row.get("use_yn") or _YN_Y) != _YN_Y
        ):
            raise EntityNotFoundError("Photo not found")
        ok = self._repo.soft_delete_photo(farm, pid, uid)
        if not ok:
            raise EntityNotFoundError("Photo not found")
        # 삭제 후 sort_no 재정렬 → 대표사진 = 새 1번
        remaining = self._repo.list_photos(farm, obs_id)
        if remaining:
            self._repo.reorder_photos(
                farm,
                str(obs_id).strip(),
                [str(r["photo_id"]) for r in remaining],
                uid,
            )

    def reorder_photos(
        self,
        farm_cd: str,
        obs_id: str,
        photo_ids: list[str],
        *,
        user_id: str | None = None,
    ) -> ObservationPhotoListResponse:
        farm = self._ensure_farm(farm_cd)
        self._ensure_observation(farm, obs_id)
        uid = self._user_id(user_id)
        oid = str(obs_id).strip()
        existing = self._repo.list_photos(farm, oid)
        existing_ids = {str(r["photo_id"]) for r in existing}
        ids = [str(p).strip() for p in (photo_ids or []) if str(p or "").strip()]
        if set(ids) != existing_ids or len(ids) != len(existing_ids):
            raise BusinessRuleError("사진 순서 목록이 현재 등록 사진과 일치하지 않습니다.")
        self._repo.reorder_photos(farm, oid, ids, uid)
        return self.list_photos(farm, oid)

    def resolve_photo_file(
        self,
        farm_cd: str,
        obs_id: str,
        photo_id: str,
        *,
        kind: str,
    ) -> Path:
        farm = self._ensure_farm(farm_cd)
        self._ensure_observation(farm, obs_id)
        row = self._repo.get_photo(farm, str(photo_id).strip())
        if (
            not row
            or str(row.get("obs_id") or "") != str(obs_id).strip()
            or str(row.get("use_yn") or _YN_Y) != _YN_Y
        ):
            raise EntityNotFoundError("Photo not found")
        key = "thumb_path" if kind == "thumbnail" else "file_path"
        rel = str(row.get(key) or "").strip()
        if not rel and kind == "thumbnail":
            rel = str(row.get("file_path") or "").strip()
        path = resolve_media_path(self._media_root, rel)
        if path is None or not path.is_file():
            raise EntityNotFoundError("Photo file not found")
        return path


_YN_Y = "Y"
