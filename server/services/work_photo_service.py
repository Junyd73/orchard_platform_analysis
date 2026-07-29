# -*- coding: utf-8 -*-
"""작업 결과 사진 서비스 — 목록/업로드/삭제/파일조회."""

from __future__ import annotations

from pathlib import Path

from app.core.exceptions import BusinessRuleError, EntityNotFoundError
from app.db.sqlite import get_sqlite_connection, get_sqlite_write_connection
from app.schemas.work_photo import (
    WorkPhotoItem,
    WorkPhotoListResponse,
    WorkPhotoUploadResponse,
)
from app.services._core_path import ensure_repo_root_on_path
from app.services.observation_ai_db_bridge import ServerDbBridge
from app.services.observation_media import resolve_media_path


class WorkPhotoService:
    def __init__(
        self,
        *,
        db_path: Path | str,
        media_root: Path,
        default_user_id: str = "MOBILE",
    ):
        self._db_path = Path(db_path)
        self._media_root = Path(media_root)
        self._default_user_id = str(default_user_id or "MOBILE").strip() or "MOBILE"
        ensure_repo_root_on_path()
        from core.work_photo_schema import ensure_work_photo_schema

        ensure_work_photo_schema(self._db_path)

    def _require_user_id(self, user_id: str | None) -> str:
        uid = str(user_id or "").strip()
        if uid:
            return uid
        fallback = self._default_user_id
        if fallback:
            return fallback
        raise BusinessRuleError("사용자 세션 정보가 없습니다.")

    def _user_id(self, user_id: str | None) -> str:
        uid = str(user_id or "").strip()
        return uid or self._default_user_id

    def _ensure_farm(self, farm_cd: str) -> str:
        farm = str(farm_cd or "").strip()
        if not farm:
            raise EntityNotFoundError("Farm not found")
        with get_sqlite_connection(self._db_path) as conn:
            row = conn.execute(
                "SELECT 1 FROM m_farm_info WHERE farm_cd = ? LIMIT 1",
                (farm,),
            ).fetchone()
        if not row:
            raise EntityNotFoundError("Farm not found")
        return farm

    def _ensure_work(self, farm_cd: str, work_id: str) -> dict:
        wid = str(work_id or "").strip()
        if not wid:
            raise EntityNotFoundError("Work not found")
        with get_sqlite_connection(self._db_path) as conn:
            row = conn.execute(
                """
                SELECT work_id, work_dt
                FROM t_work_detail
                WHERE farm_cd = ? AND work_id = ?
                LIMIT 1
                """,
                (farm_cd, wid),
            ).fetchone()
        if not row:
            raise EntityNotFoundError("Work not found")
        return {"work_id": str(row["work_id"]), "work_dt": str(row["work_dt"] or "")}

    def _urls(self, farm_cd: str, work_id: str, photo_id: str) -> tuple[str, str]:
        base = f"/farms/{farm_cd}/work-logs/works/{work_id}/photos/{photo_id}"
        return f"{base}/thumbnail", f"{base}/original"

    def _to_item(self, row: dict, *, index: int) -> WorkPhotoItem:
        farm = str(row.get("farm_cd") or "")
        wid = str(row.get("work_id") or "")
        pid = str(row.get("photo_id") or "")
        thumb_url, original_url = self._urls(farm, wid, pid)
        sort_no = row.get("sort_no")
        try:
            sn = int(sort_no) if sort_no is not None else index + 1
        except (TypeError, ValueError):
            sn = index + 1
        ext = str(row.get("file_ext") or "").strip()
        display_nm = str(row.get("original_nm") or "").strip() or f"작업사진_{sn}"
        if ext and not display_nm.lower().endswith(f".{ext.lower()}"):
            display_nm = f"{display_nm}.{ext}" if "." not in display_nm else display_nm
        return WorkPhotoItem(
            photo_id=pid,
            work_id=wid,
            farm_cd=farm,
            sort_no=sn,
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

    def list_photos(self, farm_cd: str, work_id: str) -> WorkPhotoListResponse:
        ensure_repo_root_on_path()
        from core.work_photo_db import list_work_photos
        from core.work_photo_policy import WORK_PHOTO_MAX_COUNT

        farm = self._ensure_farm(farm_cd)
        work = self._ensure_work(farm, work_id)
        wid = work["work_id"]
        with get_sqlite_connection(self._db_path) as conn:
            db = ServerDbBridge(conn)
            rows = list_work_photos(db, farm, wid)
        photos = [self._to_item(r, index=i) for i, r in enumerate(rows)]
        count = len(photos)
        return WorkPhotoListResponse(
            work_id=wid,
            count=count,
            max_count=WORK_PHOTO_MAX_COUNT,
            remaining=max(0, WORK_PHOTO_MAX_COUNT - count),
            photos=photos,
        )

    async def upload_photos(
        self,
        farm_cd: str,
        work_id: str,
        files: list,
        *,
        user_id: str | None = None,
    ) -> WorkPhotoUploadResponse:
        ensure_repo_root_on_path()
        from core.work_photo_policy import WORK_PHOTO_MAX_COUNT
        from core.work_photo_upload_application_service import (
            WorkPhotoUploadApplicationService,
        )

        farm = self._ensure_farm(farm_cd)
        work = self._ensure_work(farm, work_id)
        wid = work["work_id"]
        work_dt = work["work_dt"]
        uid = self._require_user_id(user_id)

        upload_files = list(files or [])
        if not upload_files:
            raise BusinessRuleError("업로드할 파일이 없습니다.")

        app_svc = WorkPhotoUploadApplicationService()
        new_photo_ids: list[str] = []
        skipped: list[str] = []
        last_ok: dict | None = None

        with get_sqlite_write_connection(self._db_path) as conn:
            db = ServerDbBridge(conn)
            for f in upload_files:
                filename = str(getattr(f, "filename", None) or "photo.jpg")
                data = await f.read()
                payload = app_svc.upload(
                    db,
                    farm_cd=farm,
                    work_id=wid,
                    work_dt=work_dt,
                    user_id=uid,
                    media_root=self._media_root,
                    data=data,
                    original_nm=filename,
                    max_count=WORK_PHOTO_MAX_COUNT,
                )
                if payload.get("ok"):
                    new_photo_ids.append(str(payload.get("photo_id") or ""))
                    last_ok = payload
                else:
                    code = str(payload.get("error_code") or "")
                    if code == "PHOTO_DUP":
                        skipped.append(filename)
                        continue
                    raise BusinessRuleError(
                        str(
                            payload.get("error_message")
                            or payload.get("error")
                            or "사진 업로드에 실패했습니다."
                        )
                    )

        listing = self.list_photos(farm, wid)
        id_set = set(new_photo_ids)
        uploaded = [p for p in listing.photos if p.photo_id in id_set]
        msg = f"{len(uploaded)}장이 등록되었습니다."
        if skipped:
            msg += f" (중복 {len(skipped)}장 제외)"
        first = last_ok or {}
        return WorkPhotoUploadResponse(
            uploaded=uploaded,
            skipped=skipped,
            count=listing.count,
            max_count=listing.max_count,
            remaining=listing.remaining,
            message=msg,
            success=bool(uploaded),
            photo_id=first.get("photo_id") if uploaded else None,
            farm_cd=farm if uploaded else None,
            work_id=wid if uploaded else None,
            file_name=first.get("file_name") if uploaded else None,
            file_path=first.get("file_path") if uploaded else None,
            thumbnail_path=first.get("thumbnail_path") if uploaded else None,
            file_size=first.get("file_size") if uploaded else None,
            width=first.get("width") if uploaded else None,
            height=first.get("height") if uploaded else None,
            created_by=first.get("created_by") if uploaded else None,
            error=None,
            error_code=None,
        )

    def delete_photo(
        self,
        farm_cd: str,
        work_id: str,
        photo_id: str,
        *,
        user_id: str | None = None,
    ) -> None:
        ensure_repo_root_on_path()
        from core.work_photo_db import get_work_photo, soft_delete_work_photo

        farm = self._ensure_farm(farm_cd)
        work = self._ensure_work(farm, work_id)
        wid = work["work_id"]
        uid = self._user_id(user_id)
        pid = str(photo_id or "").strip()
        with get_sqlite_write_connection(self._db_path) as conn:
            db = ServerDbBridge(conn)
            row = get_work_photo(db, farm, wid, pid)
            if not row:
                raise EntityNotFoundError("Photo not found")
            ok, _msg = soft_delete_work_photo(
                db, farm_cd=farm, work_id=wid, photo_id=pid, user_id=uid
            )
            if not ok:
                raise EntityNotFoundError("Photo not found")

    def resolve_photo_file(
        self,
        farm_cd: str,
        work_id: str,
        photo_id: str,
        *,
        kind: str,
    ) -> Path:
        ensure_repo_root_on_path()
        from core.work_photo_db import get_work_photo

        farm = self._ensure_farm(farm_cd)
        work = self._ensure_work(farm, work_id)
        wid = work["work_id"]
        pid = str(photo_id or "").strip()
        with get_sqlite_connection(self._db_path) as conn:
            db = ServerDbBridge(conn)
            row = get_work_photo(db, farm, wid, pid)
        if not row:
            raise EntityNotFoundError("Photo not found")
        key = "thumb_path" if kind == "thumbnail" else "file_path"
        rel = str(row.get(key) or "").strip()
        if not rel and kind == "thumbnail":
            rel = str(row.get("file_path") or "").strip()
        path = resolve_media_path(self._media_root, rel)
        if path is None or not path.is_file():
            raise EntityNotFoundError("Photo file not found")
        return path
