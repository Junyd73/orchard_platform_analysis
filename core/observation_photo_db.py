# -*- coding: utf-8 -*-
"""관찰 사진 DB CRUD — DBManager/PyQt 비의존 (duck-typed db).

스키마·SQL은 Stage2 와 동일. ApplicationService·서버가 이 모듈만 import 한다.
"""

from __future__ import annotations

import datetime
from typing import Any


_YN_Y = "Y"


def _now_str() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _row_dict(row) -> dict:
    if row is None:
        return {}
    if hasattr(row, "keys"):
        return {k: row[k] for k in row.keys()}
    return {}


def generate_photo_id(db, farm_cd: str) -> str:
    """PHO{YYYYMMDD}-{seq:03d}"""
    farm = (farm_cd or "").strip()
    digits = datetime.date.today().strftime("%Y%m%d")
    prefix = f"PHO{digits}-"
    rows = db.execute_query(
        """
        SELECT photo_id FROM t_observation_photo
        WHERE farm_cd = ? AND photo_id LIKE ?
        ORDER BY photo_id DESC LIMIT 1
        """,
        (farm, prefix + "%"),
    )
    seq = 1
    if rows and rows[0] and rows[0][0]:
        tail = str(rows[0][0]).rsplit("-", 1)[-1]
        try:
            seq = int(tail) + 1
        except (TypeError, ValueError):
            seq = 1
    return f"{prefix}{seq:03d}"


def _generate_photo_id_with_cur(cur, farm_cd: str) -> str:
    farm = (farm_cd or "").strip()
    digits = datetime.date.today().strftime("%Y%m%d")
    prefix = f"PHO{digits}-"
    cur.execute(
        """
        SELECT photo_id FROM t_observation_photo
        WHERE farm_cd = ? AND photo_id LIKE ?
        ORDER BY photo_id DESC LIMIT 1
        """,
        (farm, prefix + "%"),
    )
    row = cur.fetchone()
    seq = 1
    if row and row[0]:
        tail = str(row[0]).rsplit("-", 1)[-1]
        try:
            seq = int(tail) + 1
        except (TypeError, ValueError):
            seq = 1
    return f"{prefix}{seq:03d}"


def list_observation_photos(db, farm_cd: str, obs_id: str) -> list[dict]:
    farm = (farm_cd or "").strip()
    oid = (obs_id or "").strip()
    if not farm or not oid:
        return []
    rows = db.execute_query(
        """
        SELECT *
        FROM t_observation_photo
        WHERE farm_cd = ? AND obs_id = ? AND COALESCE(use_yn, 'Y') = 'Y'
        ORDER BY COALESCE(sort_no, 999999), photo_id
        """,
        (farm, oid),
    ) or []
    return [_row_dict(r) for r in rows]


def get_observation_photo(db, farm_cd: str, photo_id: str) -> dict | None:
    farm = (farm_cd or "").strip()
    pid = (photo_id or "").strip()
    if not farm or not pid:
        return None
    rows = db.execute_query(
        """
        SELECT * FROM t_observation_photo
        WHERE farm_cd = ? AND photo_id = ?
        LIMIT 1
        """,
        (farm, pid),
    )
    if not rows:
        return None
    return _row_dict(rows[0])


def photo_hash_exists(db, farm_cd: str, obs_id: str, file_hash: str) -> bool:
    fh = (file_hash or "").strip()
    if not fh:
        return False
    dup = db.execute_query(
        """
        SELECT 1 FROM t_observation_photo
        WHERE farm_cd = ? AND obs_id = ?
          AND file_hash = ? AND COALESCE(use_yn, 'Y') = 'Y'
        LIMIT 1
        """,
        (farm_cd, obs_id, fh),
    )
    return bool(dup)


def _next_photo_sort_no(cur, farm_cd: str, obs_id: str) -> int:
    cur.execute(
        """
        SELECT COALESCE(MAX(sort_no), 0) FROM t_observation_photo
        WHERE farm_cd = ? AND obs_id = ? AND COALESCE(use_yn, 'Y') = 'Y'
        """,
        (farm_cd, obs_id),
    )
    row = cur.fetchone()
    return int((row[0] if row else 0) or 0) + 1


def add_observation_photo(
    db,
    farm_cd: str,
    obs_id: str,
    meta: dict,
    user_id: str,
) -> tuple[bool, str, str | None, bool]:
    """성공 시 (True, msg, photo_id, duplicate_hint)."""
    farm = (farm_cd or "").strip()
    oid = (obs_id or "").strip()
    uid = (user_id or "").strip()
    meta = dict(meta or {})
    if not farm:
        return False, "농장코드가 없습니다.", None, False
    if not uid:
        return False, "사용자 세션 정보가 없습니다.", None, False
    if not oid:
        return False, "관찰번호가 없습니다.", None, False

    obs = db.get_observation(farm, oid)
    if not obs or (obs.get("use_yn") or _YN_Y) != _YN_Y:
        return False, "대상 관찰을 찾을 수 없습니다.", None, False

    file_hash = (meta.get("file_hash") or "").strip() or None
    if file_hash and photo_hash_exists(db, farm, oid, file_hash):
        return False, "동일 해시 사진이 이미 등록되어 있습니다.", None, True

    photo_id = (meta.get("photo_id") or "").strip() or generate_photo_id(db, farm)
    now = _now_str()
    sort_no = meta.get("sort_no")
    try:
        sort_no = int(sort_no) if sort_no is not None and str(sort_no).strip() != "" else None
    except (TypeError, ValueError):
        sort_no = None
    if sort_no is None:
        mx = db.execute_query(
            """
            SELECT COALESCE(MAX(sort_no), 0) FROM t_observation_photo
            WHERE farm_cd = ? AND obs_id = ? AND COALESCE(use_yn, 'Y') = 'Y'
            """,
            (farm, oid),
        )
        sort_no = int(mx[0][0] or 0) + 1 if mx else 1

    try:
        db.execute_query(
            """
            INSERT INTO t_observation_photo (
                farm_cd, photo_id, obs_id, file_path, thumb_path,
                original_nm, stored_nm, file_ext, file_size,
                width_px, height_px, shot_type_cd, captured_dt, photo_rmk,
                sort_no, file_hash, use_yn, reg_id, reg_dt, mod_id, mod_dt
            ) VALUES (
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, 'Y', ?, ?, ?, ?
            )
            """,
            (
                farm,
                photo_id,
                oid,
                (meta.get("file_path") or "").strip() or None,
                (meta.get("thumb_path") or "").strip() or None,
                (meta.get("original_nm") or "").strip() or None,
                (meta.get("stored_nm") or "").strip() or None,
                (meta.get("file_ext") or "").strip() or None,
                meta.get("file_size"),
                meta.get("width_px"),
                meta.get("height_px"),
                (meta.get("shot_type_cd") or "").strip() or None,
                (meta.get("captured_dt") or "").strip() or None,
                (meta.get("photo_rmk") or "").strip() or None,
                sort_no,
                file_hash,
                uid,
                now,
                uid,
                now,
            ),
        )
        return True, "사진이 등록되었습니다.", photo_id, False
    except Exception:
        print("[DB] add_observation_photo: code=DB_ERROR")
        return False, "데이터 저장 중 오류가 발생했습니다.", None, False


def add_observation_photos_batch(
    db,
    farm_cd: str,
    obs_id: str,
    metas: list[dict],
    user_id: str,
) -> tuple[bool, str, list[str], list[str], list[dict]]:
    """사진 메타 일괄 INSERT(단일 트랜잭션). Stage2 호환."""
    farm = (farm_cd or "").strip()
    oid = (obs_id or "").strip()
    uid = (user_id or "").strip()
    items = [dict(m or {}) for m in (metas or [])]
    if not farm:
        return False, "농장코드가 없습니다.", [], [], items
    if not uid:
        return False, "사용자 세션 정보가 없습니다.", [], [], items
    if not oid:
        return False, "관찰번호가 없습니다.", [], [], items
    if not items:
        return True, "등록할 사진이 없습니다.", [], [], []

    obs = db.get_observation(farm, oid)
    if not obs or (obs.get("use_yn") or _YN_Y) != _YN_Y:
        return False, "대상 관찰을 찾을 수 없습니다.", [], [], items

    to_insert: list[dict] = []
    dup_cleanup: list[dict] = []
    dup_names: list[str] = []
    for meta in items:
        fh = (meta.get("file_hash") or "").strip() or None
        if fh and photo_hash_exists(db, farm, oid, fh):
            dup_cleanup.append(meta)
            dup_names.append(
                str(meta.get("original_nm") or meta.get("photo_id") or "사진")
            )
            continue
        to_insert.append(meta)

    if not to_insert:
        msg = "등록할 사진이 없습니다."
        if dup_names:
            msg = f"동일 해시 사진 {len(dup_names)}장은 제외되었습니다."
        print(f"[OBS] photo batch skip insert dup={len(dup_names)}")
        return True, msg, [], dup_names, dup_cleanup

    now = _now_str()
    inserted: list[str] = []
    try:
        db.conn.isolation_level = None
        cur = db.conn.cursor()
        cur.execute("BEGIN TRANSACTION")
        sort_no = _next_photo_sort_no(cur, farm, oid)
        for meta in to_insert:
            photo_id = (meta.get("photo_id") or "").strip()
            if not photo_id:
                photo_id = _generate_photo_id_with_cur(cur, farm)
            file_hash = (meta.get("file_hash") or "").strip() or None
            cur.execute(
                """
                INSERT INTO t_observation_photo (
                    farm_cd, photo_id, obs_id, file_path, thumb_path,
                    original_nm, stored_nm, file_ext, file_size,
                    width_px, height_px, shot_type_cd, captured_dt, photo_rmk,
                    sort_no, file_hash, use_yn, reg_id, reg_dt, mod_id, mod_dt
                ) VALUES (
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, 'Y', ?, ?, ?, ?
                )
                """,
                (
                    farm,
                    photo_id,
                    oid,
                    (meta.get("file_path") or "").strip() or None,
                    (meta.get("thumb_path") or "").strip() or None,
                    (meta.get("original_nm") or "").strip() or None,
                    (meta.get("stored_nm") or "").strip() or None,
                    (meta.get("file_ext") or "").strip() or None,
                    meta.get("file_size"),
                    meta.get("width_px"),
                    meta.get("height_px"),
                    (meta.get("shot_type_cd") or "").strip() or None,
                    (meta.get("captured_dt") or "").strip() or None,
                    (meta.get("photo_rmk") or "").strip() or None,
                    sort_no,
                    file_hash,
                    uid,
                    now,
                    uid,
                    now,
                ),
            )
            inserted.append(photo_id)
            sort_no += 1
        db.conn.commit()
        msg = f"{len(inserted)}장의 사진이 등록되었습니다."
        if dup_names:
            msg += f" (중복 {len(dup_names)}장 제외)"
        return True, msg, inserted, dup_names, dup_cleanup
    except Exception:
        try:
            db.conn.rollback()
        except Exception:
            pass
        print("[DB] add_observation_photos_batch: code=DB_ERROR")
        return False, "데이터 저장 중 오류가 발생했습니다.", [], [], items
    finally:
        try:
            db.conn.isolation_level = ""
        except Exception:
            pass
