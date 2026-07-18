# -*- coding: utf-8 -*-
"""관찰 사진 업로드 Application Service — UI·REST 공통 (PyQt/FastAPI 비의존).

파일: observation_photo_files / 정책: observation_photo_policy / DB: observation_photo_db
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from core.observation_photo_db import (
    add_observation_photo,
    generate_photo_id,
    get_observation_photo,
    list_observation_photos,
)
from core.observation_photo_files import (
    compensate_photo_files,
    process_observation_photo_bytes,
)
from core.observation_photo_policy import OBS_PHOTO_MAX_COUNT
from core.observation_safe_errors import safe_log, safe_user_message


def _split_err(raw: str) -> tuple[str, str]:
    s = str(raw or "")
    if "|" in s:
        code, msg = s.split("|", 1)
        return code.strip() or "PHOTO_PARAM", msg.strip()
    return "PHOTO_PARAM", s or safe_user_message("PHOTO_PARAM")


class ObservationPhotoUploadApplicationService:
    """사진 1장 업로드 유스케이스."""

    def upload(
        self,
        db,
        *,
        farm_cd: str,
        obs_id: str,
        user_id: str,
        media_root: str | Path,
        data: bytes,
        original_nm: str,
        max_count: int = OBS_PHOTO_MAX_COUNT,
        request_id: int = 0,
        photo_id: str | None = None,
        shot_type_cd: str | None = None,
        photo_rmk: str | None = None,
    ) -> dict[str, Any]:
        farm = str(farm_cd or "").strip()
        oid = str(obs_id or "").strip()
        uid = str(user_id or "").strip()
        root = Path(media_root)
        req_id = int(request_id)

        fail: dict[str, Any] = {
            "request_id": req_id,
            "ok": False,
            "success": False,
            "photo_id": None,
            "farm_cd": farm or None,
            "obs_id": oid or None,
            "file_name": None,
            "file_path": None,
            "thumbnail_path": None,
            "file_size": None,
            "width": None,
            "height": None,
            "created_by": None,
            "created_at": None,
            "error_code": "PHOTO_PARAM",
            "error_message": safe_user_message("PHOTO_PARAM"),
            "error": safe_user_message("PHOTO_PARAM"),
            "original_name": str(original_nm or ""),
        }

        created_rel: list[str] = []
        try:
            if not farm or not oid:
                return fail
            if not uid:
                return {
                    **fail,
                    "error_message": "사용자 세션 정보가 없습니다.",
                    "error": "사용자 세션 정보가 없습니다.",
                }

            obs = db.get_observation(farm, oid) or {}
            if not obs or str(obs.get("use_yn") or "Y") != "Y":
                return {
                    **fail,
                    "error_message": "대상 관찰을 찾을 수 없습니다.",
                    "error": "대상 관찰을 찾을 수 없습니다.",
                }

            existing = list_observation_photos(db, farm, oid)
            lim = max(1, int(max_count or OBS_PHOTO_MAX_COUNT))
            if len(existing) >= lim:
                msg = f"사진은 최대 {lim}장까지 등록할 수 있습니다."
                return {
                    **fail,
                    "error_code": "PHOTO_LIMIT",
                    "error_message": msg,
                    "error": msg,
                }

            pid = (photo_id or "").strip() or generate_photo_id(db, farm)
            obs_dt = str(obs.get("obs_dt") or "")
            meta = process_observation_photo_bytes(
                root,
                farm,
                oid,
                obs_dt,
                data=data or b"",
                original_nm=original_nm,
                photo_id=pid,
            )
            if shot_type_cd is not None:
                meta["shot_type_cd"] = shot_type_cd
            if photo_rmk is not None:
                meta["photo_rmk"] = photo_rmk
            created_rel = [
                str(meta.get("file_path") or ""),
                str(meta.get("thumb_path") or ""),
            ]

            ok, msg, saved_id, is_dup = add_observation_photo(
                db, farm, oid, meta, uid
            )
            if not ok:
                compensate_photo_files(root, created_rel)
                if is_dup:
                    return {
                        **fail,
                        "error_code": "PHOTO_DUP",
                        "error_message": str(msg or safe_user_message("PHOTO_DUP")),
                        "error": str(msg or safe_user_message("PHOTO_DUP")),
                    }
                code = "DB_ERROR" if "저장" in str(msg) or "오류" in str(msg) else "PHOTO_PARAM"
                return {
                    **fail,
                    "error_code": code,
                    "error_message": str(msg or safe_user_message(code)),
                    "error": str(msg or safe_user_message(code)),
                }

            row = get_observation_photo(db, farm, str(saved_id or pid)) or meta
            return {
                "request_id": req_id,
                "ok": True,
                "success": True,
                "photo_id": str(row.get("photo_id") or saved_id or pid),
                "farm_cd": farm,
                "obs_id": oid,
                "file_name": row.get("original_nm") or meta.get("original_nm"),
                "file_path": row.get("file_path") or meta.get("file_path"),
                "thumbnail_path": row.get("thumb_path") or meta.get("thumb_path"),
                "file_size": row.get("file_size") or meta.get("file_size"),
                "width": row.get("width_px") or meta.get("width_px"),
                "height": row.get("height_px") or meta.get("height_px"),
                "created_by": row.get("reg_id") or uid,
                "created_at": row.get("reg_dt"),
                "error_code": "",
                "error_message": "",
                "error": None,
                "original_name": str(original_nm or meta.get("original_nm") or ""),
                "meta": meta,
            }
        except ValueError as e:
            compensate_photo_files(root, created_rel)
            code, msg = _split_err(str(e))
            if code not in (
                "PHOTO_PARAM",
                "PHOTO_TYPE",
                "PHOTO_EMPTY",
                "PHOTO_TOO_LARGE",
                "PHOTO_LIMIT",
                "PHOTO_DUP",
                "PHOTO_SAVE",
                "DB_ERROR",
            ):
                code = "PHOTO_PARAM"
            return {
                **fail,
                "error_code": code,
                "error_message": msg or safe_user_message(code),
                "error": msg or safe_user_message(code),
            }
        except Exception as e:
            compensate_photo_files(root, created_rel)
            safe_log(
                "DB_ERROR",
                type(e).__name__,
                where="photo_upload_app",
                request_id=req_id,
            )
            return {
                **fail,
                "error_code": "DB_ERROR",
                "error_message": safe_user_message("DB_ERROR"),
                "error": safe_user_message("DB_ERROR"),
            }
