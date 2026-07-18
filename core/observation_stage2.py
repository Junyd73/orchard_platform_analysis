# -*- coding: utf-8 -*-
"""관찰일지 Stage2 — 사진·열매측정·추적·대시보드 DB/스키마/CRUD."""

from __future__ import annotations

import datetime
import sqlite3
from typing import Any

from core.db_manager import DBManager

# 로컬 참조용 별칭 (DBManager 상수와 동기)
OBS_SHOT_PARENT_CD = DBManager.OBS_SHOT_PARENT_CD
OBS_FRUIT_SHAPE_PARENT_CD = DBManager.OBS_FRUIT_SHAPE_PARENT_CD
OBS_FRUIT_COLOR_PARENT_CD = DBManager.OBS_FRUIT_COLOR_PARENT_CD
OBS_STALK_PARENT_CD = DBManager.OBS_STALK_PARENT_CD
OBS_CALYX_PARENT_CD = DBManager.OBS_CALYX_PARENT_CD
OBS_TARGET_FRUIT_CD = DBManager.OBS_TARGET_FRUIT_CD
OBS_PROGRESS_DONE_CDS = DBManager.OBS_PROGRESS_DONE_CDS
OBS_SEVERITY_RANK = DBManager.OBS_SEVERITY_RANK

_YN_Y = "Y"
_YN_N = "N"

_NULLABLE_NUM_KEYS = (
    "width_mm",
    "height_mm",
    "circumference_mm",
    "estimated_weight_g",
)
_FLAG_YN_KEYS = (
    "spot_yn",
    "wound_yn",
    "crack_yn",
    "russet_yn",
    "sunburn_yn",
    "deformity_yn",
)


def _now_str() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _today_ymd() -> str:
    return datetime.date.today().strftime("%Y-%m-%d")


def _row_dict(row) -> dict:
    if row is None:
        return {}
    if hasattr(row, "keys"):
        return {k: row[k] for k in row.keys()}
    return {}


def _norm_ymd(raw) -> str:
    s = str(raw or "").strip()
    if len(s) >= 10 and s[4] == "-":
        return s[:10]
    digits = "".join(ch for ch in s if ch.isdigit())
    if len(digits) >= 8:
        return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"
    return s


def _parse_nonneg_or_null(value) -> tuple[bool, float | None, str]:
    """빈값→None, 숫자>=0 허용. 실패 시 (False, None, msg)."""
    if value is None:
        return True, None, ""
    if isinstance(value, str) and not value.strip():
        return True, None, ""
    try:
        num = float(value)
    except (TypeError, ValueError):
        return False, None, "숫자는 0 이상이어야 합니다."
    if num < 0:
        return False, None, "숫자는 0 이상이어야 합니다."
    return True, num, ""


def _norm_yn(value, default: str = _YN_N) -> str:
    raw = str(value or "").strip().upper()
    if raw in (_YN_Y, _YN_N):
        return raw
    return default


def ensure_observation_stage2_schema(db: DBManager) -> None:
    """사진·열매측정 테이블·인덱스·공통코드·root_obs_id 백필(멱등)."""
    _ensure_observation_photo_table(db)
    _ensure_observation_fruit_table(db)
    _backfill_root_obs_id(db)
    _ensure_observation_stage2_common_codes(db)


def _ensure_observation_photo_table(db: DBManager) -> None:
    try:
        db.execute_query(
            """
            CREATE TABLE IF NOT EXISTS t_observation_photo (
                farm_cd TEXT NOT NULL,
                photo_id TEXT NOT NULL,
                obs_id TEXT NOT NULL,
                file_path TEXT,
                thumb_path TEXT,
                original_nm TEXT,
                stored_nm TEXT,
                file_ext TEXT,
                file_size INTEGER,
                width_px INTEGER,
                height_px INTEGER,
                shot_type_cd TEXT,
                captured_dt TEXT,
                photo_rmk TEXT,
                sort_no INTEGER,
                file_hash TEXT,
                use_yn TEXT DEFAULT 'Y',
                reg_id TEXT,
                reg_dt TEXT,
                mod_id TEXT,
                mod_dt TEXT,
                PRIMARY KEY (farm_cd, photo_id)
            )
            """
        )
        db.execute_query(
            "CREATE INDEX IF NOT EXISTS idx_obs_photo_obs "
            "ON t_observation_photo(farm_cd, obs_id, use_yn)"
        )
    except Exception as e:
        print(f"[DB] ensure t_observation_photo: {e}")


def _ensure_observation_fruit_table(db: DBManager) -> None:
    try:
        db.execute_query(
            """
            CREATE TABLE IF NOT EXISTS t_observation_fruit_measurement (
                farm_cd TEXT NOT NULL,
                obs_id TEXT NOT NULL,
                width_mm REAL,
                height_mm REAL,
                circumference_mm REAL,
                estimated_weight_g REAL,
                shape_cd TEXT,
                skin_color_cd TEXT,
                asymmetry_level INTEGER,
                spot_yn TEXT,
                wound_yn TEXT,
                crack_yn TEXT,
                russet_yn TEXT,
                sunburn_yn TEXT,
                deformity_yn TEXT,
                stalk_status_cd TEXT,
                calyx_status_cd TEXT,
                fruit_rmk TEXT,
                reg_id TEXT,
                reg_dt TEXT,
                mod_id TEXT,
                mod_dt TEXT,
                PRIMARY KEY (farm_cd, obs_id)
            )
            """
        )
    except Exception as e:
        print(f"[DB] ensure t_observation_fruit_measurement: {e}")


def _backfill_root_obs_id(db: DBManager) -> None:
    try:
        db.execute_query(
            """
            UPDATE t_observation_master
            SET root_obs_id = obs_id
            WHERE root_obs_id IS NULL OR TRIM(root_obs_id) = ''
            """
        )
    except Exception as e:
        print(f"[DB] backfill root_obs_id: {e}")


def _ensure_observation_stage2_common_codes(db: DBManager) -> None:
    """촬영유형·열매형태·과피색·과경·꽃받침 공통코드 멱등 등록(농장별)."""
    try:
        cur = db.conn.cursor()
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='m_common_code'"
        )
        if not cur.fetchone():
            return
    except sqlite3.Error:
        return

    farms = db.execute_query("SELECT farm_cd FROM m_farm_info") or []
    farm_cds = [str(r[0]).strip() for r in farms if r and r[0]]
    if not farm_cds:
        farm_cds = ["OR001"]

    parents = (
        (OBS_SHOT_PARENT_CD, "촬영유형"),
        (OBS_FRUIT_SHAPE_PARENT_CD, "열매형태"),
        (OBS_FRUIT_COLOR_PARENT_CD, "과피색"),
        (OBS_STALK_PARENT_CD, "과경상태"),
        (OBS_CALYX_PARENT_CD, "꽃받침상태"),
    )
    children = (
        (OBS_SHOT_PARENT_CD, "OH010100", "전체"),
        (OBS_SHOT_PARENT_CD, "OH010200", "정면"),
        (OBS_SHOT_PARENT_CD, "OH010300", "측면"),
        (OBS_SHOT_PARENT_CD, "OH010400", "상단"),
        (OBS_SHOT_PARENT_CD, "OH010500", "근접"),
        (OBS_SHOT_PARENT_CD, "OH010600", "잎 앞면"),
        (OBS_SHOT_PARENT_CD, "OH010700", "잎 뒷면"),
        (OBS_SHOT_PARENT_CD, "OH010800", "병반"),
        (OBS_SHOT_PARENT_CD, "OH010900", "해충"),
        (OBS_SHOT_PARENT_CD, "OH011000", "기타"),
        (OBS_FRUIT_SHAPE_PARENT_CD, "FS010100", "원형"),
        (OBS_FRUIT_SHAPE_PARENT_CD, "FS010200", "편원형"),
        (OBS_FRUIT_SHAPE_PARENT_CD, "FS010300", "장원형"),
        (OBS_FRUIT_SHAPE_PARENT_CD, "FS010400", "비대칭"),
        (OBS_FRUIT_SHAPE_PARENT_CD, "FS010500", "기형"),
        (OBS_FRUIT_SHAPE_PARENT_CD, "FS010600", "판정보류"),
        (OBS_FRUIT_COLOR_PARENT_CD, "FC010100", "녹색"),
        (OBS_FRUIT_COLOR_PARENT_CD, "FC010200", "황록색"),
        (OBS_FRUIT_COLOR_PARENT_CD, "FC010300", "황갈색"),
        (OBS_FRUIT_COLOR_PARENT_CD, "FC010400", "갈색"),
        (OBS_FRUIT_COLOR_PARENT_CD, "FC010500", "착색불균일"),
        (OBS_FRUIT_COLOR_PARENT_CD, "FC010600", "기타"),
        (OBS_STALK_PARENT_CD, "FK010100", "정상"),
        (OBS_STALK_PARENT_CD, "FK010200", "약함"),
        (OBS_STALK_PARENT_CD, "FK010300", "탈락위험"),
        (OBS_STALK_PARENT_CD, "FK010400", "기타"),
        (OBS_CALYX_PARENT_CD, "FY010100", "정상"),
        (OBS_CALYX_PARENT_CD, "FY010200", "갈변"),
        (OBS_CALYX_PARENT_CD, "FY010300", "부패"),
        (OBS_CALYX_PARENT_CD, "FY010400", "기타"),
    )
    now_sql = "datetime('now','localtime')"
    for farm_cd in farm_cds:
        for code_cd, code_nm in parents:
            db.execute_query(
                f"""
                INSERT INTO m_common_code (
                    farm_cd, code_cd, code_nm, parent_cd, use_yn,
                    reg_id, reg_dt, mod_id, mod_dt
                )
                SELECT ?, ?, ?, NULL, 'Y', 'SYSTEM', {now_sql}, 'SYSTEM', {now_sql}
                WHERE NOT EXISTS (
                    SELECT 1 FROM m_common_code
                    WHERE farm_cd = ? AND code_cd = ?
                )
                """,
                (farm_cd, code_cd, code_nm, farm_cd, code_cd),
            )
        for parent_cd, code_cd, code_nm in children:
            db.execute_query(
                f"""
                INSERT INTO m_common_code (
                    farm_cd, code_cd, code_nm, parent_cd, use_yn,
                    reg_id, reg_dt, mod_id, mod_dt
                )
                SELECT ?, ?, ?, ?, 'Y', 'SYSTEM', {now_sql}, 'SYSTEM', {now_sql}
                WHERE NOT EXISTS (
                    SELECT 1 FROM m_common_code
                    WHERE farm_cd = ? AND code_cd = ?
                )
                """,
                (farm_cd, code_cd, code_nm, parent_cd, farm_cd, code_cd),
            )


def generate_photo_id(db: DBManager, farm_cd: str) -> str:
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
    """트랜잭션 내부용 photo_id 채번."""
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


def list_observation_photos(db: DBManager, farm_cd: str, obs_id: str) -> list[dict]:
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


def get_observation_photo(
    db: DBManager, farm_cd: str, photo_id: str
) -> dict | None:
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


def add_observation_photo(
    db: DBManager,
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
    if file_hash and _photo_hash_exists(db, farm, oid, file_hash):
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
        msg = "사진이 등록되었습니다."
        return True, msg, photo_id, False
    except Exception as e:
        print(f"[DB] add_observation_photo: {e}")
        return False, f"사진 등록 중 오류가 발생했습니다: {e}", None, False


def _photo_hash_exists(
    db: DBManager, farm_cd: str, obs_id: str, file_hash: str
) -> bool:
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


def add_observation_photos_batch(
    db: DBManager,
    farm_cd: str,
    obs_id: str,
    metas: list[dict],
    user_id: str,
) -> tuple[bool, str, list[str], list[str], list[dict]]:
    """사진 메타 일괄 INSERT(단일 트랜잭션).

    반환: (성공여부, 메시지, 등록 photo_id 목록, 중복 파일명 목록, 파일정리 대상 meta)
    DB 실패 시 등록 시도분 전체 meta를 정리 대상으로 반환한다.
    """
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
        if fh and _photo_hash_exists(db, farm, oid, fh):
            dup_cleanup.append(meta)
            dup_names.append(str(meta.get("original_nm") or meta.get("photo_id") or "사진"))
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
        msg = f"{len(inserted)}장이 등록되었습니다."
        if dup_names:
            msg += f" (중복 {len(dup_names)}장 제외)"
        print(
            f"[OBS] photo batch commit: inserted={len(inserted)} "
            f"dup_excluded={len(dup_names)}"
        )
        return True, msg, inserted, dup_names, dup_cleanup
    except Exception as e:
        if db.conn:
            try:
                db.conn.rollback()
            except sqlite3.Error:
                pass
        print(f"[OBS] photo batch rollback: {e}")
        return (
            False,
            f"사진 DB 저장 실패: {e}",
            [],
            dup_names,
            list(to_insert),
        )
    finally:
        db.conn.isolation_level = ""

def update_observation_photo_meta(
    db: DBManager,
    farm_cd: str,
    photo_id: str,
    shot_type_cd: str | None,
    photo_rmk: str | None,
    sort_no: int | None,
    user_id: str,
) -> tuple[bool, str]:
    farm = (farm_cd or "").strip()
    pid = (photo_id or "").strip()
    uid = (user_id or "").strip()
    if not farm or not pid:
        return False, "수정할 사진이 없습니다."
    if not uid:
        return False, "사용자 세션 정보가 없습니다."
    exist = get_observation_photo(db, farm, pid)
    if not exist or (exist.get("use_yn") or _YN_Y) != _YN_Y:
        return False, "수정할 사진을 찾을 수 없습니다."
    now = _now_str()
    sn = sort_no
    if sn is not None:
        try:
            sn = int(sn)
        except (TypeError, ValueError):
            sn = exist.get("sort_no")
    else:
        sn = exist.get("sort_no")
    try:
        db.execute_query(
            """
            UPDATE t_observation_photo SET
                shot_type_cd = ?, photo_rmk = ?, sort_no = ?,
                mod_id = ?, mod_dt = ?
            WHERE farm_cd = ? AND photo_id = ? AND COALESCE(use_yn, 'Y') = 'Y'
            """,
            (
                (shot_type_cd or "").strip() or None,
                (photo_rmk or "").strip() or None,
                sn,
                uid,
                now,
                farm,
                pid,
            ),
        )
        return True, "사진 정보가 수정되었습니다."
    except Exception as e:
        print(f"[DB] update_observation_photo_meta: {e}")
        return False, f"사진 수정 중 오류가 발생했습니다: {e}"


def soft_delete_observation_photo(
    db: DBManager, farm_cd: str, photo_id: str, user_id: str
) -> tuple[bool, str]:
    farm = (farm_cd or "").strip()
    pid = (photo_id or "").strip()
    uid = (user_id or "").strip()
    if not farm or not pid:
        return False, "삭제할 사진이 없습니다."
    if not uid:
        return False, "사용자 세션 정보가 없습니다."
    exist = get_observation_photo(db, farm, pid)
    if not exist or (exist.get("use_yn") or _YN_Y) != _YN_Y:
        return False, "삭제할 사진을 찾을 수 없습니다."
    now = _now_str()
    try:
        db.execute_query(
            """
            UPDATE t_observation_photo
            SET use_yn = 'N', mod_id = ?, mod_dt = ?
            WHERE farm_cd = ? AND photo_id = ? AND COALESCE(use_yn, 'Y') = 'Y'
            """,
            (uid, now, farm, pid),
        )
        return True, "사진이 삭제되었습니다."
    except Exception as e:
        print(f"[DB] soft_delete_observation_photo: {e}")
        return False, f"사진 삭제 중 오류가 발생했습니다: {e}"


def reorder_observation_photos(
    db: DBManager,
    farm_cd: str,
    obs_id: str,
    photo_ids: list,
    user_id: str,
) -> tuple[bool, str]:
    farm = (farm_cd or "").strip()
    oid = (obs_id or "").strip()
    uid = (user_id or "").strip()
    if not farm or not oid:
        return False, "관찰번호가 없습니다."
    if not uid:
        return False, "사용자 세션 정보가 없습니다."
    ids = [str(p).strip() for p in (photo_ids or []) if str(p or "").strip()]
    if not ids:
        return False, "정렬할 사진이 없습니다."
    now = _now_str()
    queries = []
    for i, pid in enumerate(ids, start=1):
        queries.append(
            (
                """
                UPDATE t_observation_photo
                SET sort_no = ?, mod_id = ?, mod_dt = ?
                WHERE farm_cd = ? AND photo_id = ? AND obs_id = ?
                  AND COALESCE(use_yn, 'Y') = 'Y'
                """,
                (i, uid, now, farm, pid, oid),
            )
        )
    try:
        db.execute_transaction(queries)
        return True, "사진 순서가 변경되었습니다."
    except Exception as e:
        print(f"[DB] reorder_observation_photos: {e}")
        return False, f"사진 순서 변경 중 오류가 발생했습니다: {e}"


def get_fruit_measurement(
    db: DBManager, farm_cd: str, obs_id: str
) -> dict | None:
    farm = (farm_cd or "").strip()
    oid = (obs_id or "").strip()
    if not farm or not oid:
        return None
    rows = db.execute_query(
        """
        SELECT * FROM t_observation_fruit_measurement
        WHERE farm_cd = ? AND obs_id = ?
        LIMIT 1
        """,
        (farm, oid),
    )
    if not rows:
        return None
    return _row_dict(rows[0])


def _parse_fruit_payload(data: dict) -> tuple[bool, str, dict]:
    """열매 측정 입력 검증·파싱."""
    data = dict(data or {})
    parsed: dict[str, Any] = {}
    for key in _NULLABLE_NUM_KEYS:
        ok, num, msg = _parse_nonneg_or_null(data.get(key))
        if not ok:
            return False, msg, {}
        parsed[key] = num

    asym = data.get("asymmetry_level")
    if asym is None or (isinstance(asym, str) and not str(asym).strip()):
        parsed["asymmetry_level"] = None
    else:
        try:
            lv = int(asym)
        except (TypeError, ValueError):
            return False, "비대칭 등급은 정수여야 합니다.", {}
        if lv < 0:
            return False, "비대칭 등급은 0 이상이어야 합니다.", {}
        parsed["asymmetry_level"] = lv

    for key in _FLAG_YN_KEYS:
        parsed[key] = _norm_yn(data.get(key), _YN_N)

    parsed["shape_cd"] = (data.get("shape_cd") or "").strip() or None
    parsed["skin_color_cd"] = (data.get("skin_color_cd") or "").strip() or None
    parsed["stalk_status_cd"] = (data.get("stalk_status_cd") or "").strip() or None
    parsed["calyx_status_cd"] = (data.get("calyx_status_cd") or "").strip() or None
    parsed["fruit_rmk"] = (data.get("fruit_rmk") or "").strip() or None
    return True, "", parsed


def save_observation_bundle(
    db: DBManager,
    observation_data: dict,
    user_id: str,
    fruit_data: dict | None = None,
) -> tuple[bool, str, str | None]:
    """관찰 마스터와 열매 측정을 단일 트랜잭션으로 저장."""
    data = dict(observation_data or {})
    farm = (data.get("farm_cd") or "").strip()
    obs_dt = (data.get("obs_dt") or "").strip()
    target = (data.get("target_type_cd") or "").strip()
    obs_type = (data.get("obs_type_cd") or "").strip()
    severity = (data.get("severity_cd") or "").strip()
    progress = (data.get("progress_status_cd") or "").strip()
    title = (data.get("obs_title") or "").strip()
    content = (data.get("obs_content") or "").strip()
    uid = (user_id or "").strip()
    if not farm:
        return False, "농장코드가 없습니다.", None
    if not uid:
        return False, "사용자 세션 정보가 없습니다.", None
    if not obs_dt:
        return False, "관찰일자를 입력해 주세요.", None
    if not target:
        return False, "관찰 대상을 선택해 주세요.", None
    if not obs_type:
        return False, "관찰 유형을 선택해 주세요.", None
    if not severity:
        return False, "상태/심각도를 선택해 주세요.", None
    if not progress:
        return False, "처리상태를 선택해 주세요.", None
    if not title:
        return False, "제목을 입력해 주세요.", None
    if not content:
        return False, "관찰내용을 입력해 주세요.", None

    followup = (data.get("followup_dt") or "").strip() or None
    if followup and followup < obs_dt:
        return False, "재관찰 예정일은 관찰일자보다 이전일 수 없습니다.", None

    site_id = (data.get("site_id") or "").strip() or None
    if not site_id:
        return False, "작업장소를 선택해 주세요.", None

    obs_id = (data.get("obs_id") or "").strip()
    is_new = not obs_id
    now = _now_str()
    exist = None if is_new else db.get_observation(farm, obs_id)
    if not is_new:
        if not exist or (exist.get("use_yn") or _YN_Y) != _YN_Y:
            return False, "수정할 관찰을 찾을 수 없습니다.", None
        if str(exist.get("farm_cd") or "").strip() != farm:
            return False, "다른 농장의 관찰은 수정할 수 없습니다.", None

    is_fruit = target == OBS_TARGET_FRUIT_CD
    parsed_fruit: dict[str, Any] = {}
    if is_fruit:
        ok, fmsg, parsed_fruit = _parse_fruit_payload(fruit_data or {})
        if not ok:
            return False, fmsg, None

    if is_new:
        obs_id = db.generate_obs_id(farm, obs_dt)

    try:
        db.conn.isolation_level = None
        cur = db.conn.cursor()
        cur.execute("BEGIN TRANSACTION")

        if is_new:
            ai_status = db.normalize_obs_ai_status(
                data.get("ai_status"), db.OBS_AI_STATUS_NONE
            )
            root_id = (data.get("root_obs_id") or "").strip() or obs_id
            parent_id = (data.get("parent_obs_id") or "").strip() or None
            cur.execute(
                """
                INSERT INTO t_observation_master (
                    obs_id, farm_cd, obs_dt, target_type_cd, obs_type_cd,
                    site_id, zone_nm, row_no, tree_no, branch_no, sample_no,
                    severity_cd, progress_status_cd, obs_title, obs_content,
                    action_content, followup_dt, root_obs_id, parent_obs_id,
                    ai_status, use_yn, reg_id, reg_dt, mod_id, mod_dt
                ) VALUES (
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, 'Y', ?, ?, ?, ?
                )
                """,
                (
                    obs_id,
                    farm,
                    obs_dt,
                    target,
                    obs_type,
                    site_id,
                    (data.get("zone_nm") or "").strip() or None,
                    (data.get("row_no") or "").strip() or None,
                    (data.get("tree_no") or "").strip() or None,
                    (data.get("branch_no") or "").strip() or None,
                    (data.get("sample_no") or "").strip() or None,
                    severity,
                    progress,
                    title,
                    content,
                    (data.get("action_content") or "").strip() or None,
                    followup,
                    root_id,
                    parent_id,
                    ai_status,
                    uid,
                    now,
                    uid,
                    now,
                ),
            )
            msg = "관찰이 등록되었습니다."
        else:
            root_id = db._obs_preserve_field(
                data, "root_obs_id", exist.get("root_obs_id"), default=obs_id
            )
            parent_id = db._obs_preserve_field(
                data, "parent_obs_id", exist.get("parent_obs_id"), default=None
            )
            if "ai_status" in data and str(data.get("ai_status") or "").strip():
                ai_status = db.normalize_obs_ai_status(
                    data.get("ai_status"), exist.get("ai_status")
                )
            else:
                ai_status = db.normalize_obs_ai_status(
                    exist.get("ai_status"), db.OBS_AI_STATUS_NONE
                )
            cur.execute(
                """
                UPDATE t_observation_master SET
                    obs_dt = ?, target_type_cd = ?, obs_type_cd = ?,
                    site_id = ?, zone_nm = ?, row_no = ?, tree_no = ?,
                    branch_no = ?, sample_no = ?,
                    severity_cd = ?, progress_status_cd = ?,
                    obs_title = ?, obs_content = ?, action_content = ?,
                    followup_dt = ?,
                    root_obs_id = ?,
                    parent_obs_id = ?,
                    ai_status = ?,
                    mod_id = ?, mod_dt = ?
                WHERE farm_cd = ? AND obs_id = ? AND COALESCE(use_yn, 'Y') = 'Y'
                """,
                (
                    obs_dt,
                    target,
                    obs_type,
                    site_id,
                    (data.get("zone_nm") or "").strip() or None,
                    (data.get("row_no") or "").strip() or None,
                    (data.get("tree_no") or "").strip() or None,
                    (data.get("branch_no") or "").strip() or None,
                    (data.get("sample_no") or "").strip() or None,
                    severity,
                    progress,
                    title,
                    content,
                    (data.get("action_content") or "").strip() or None,
                    followup,
                    root_id,
                    parent_id,
                    ai_status,
                    uid,
                    now,
                    farm,
                    obs_id,
                ),
            )
            msg = "관찰이 수정되었습니다."

        if is_fruit:
            cur.execute(
                """
                SELECT 1 FROM t_observation_fruit_measurement
                WHERE farm_cd = ? AND obs_id = ?
                LIMIT 1
                """,
                (farm, obs_id),
            )
            fruit_exists = bool(cur.fetchone())
            if fruit_exists:
                cur.execute(
                    """
                    UPDATE t_observation_fruit_measurement SET
                        width_mm = ?, height_mm = ?, circumference_mm = ?,
                        estimated_weight_g = ?, shape_cd = ?, skin_color_cd = ?,
                        asymmetry_level = ?,
                        spot_yn = ?, wound_yn = ?, crack_yn = ?, russet_yn = ?,
                        sunburn_yn = ?, deformity_yn = ?,
                        stalk_status_cd = ?, calyx_status_cd = ?, fruit_rmk = ?,
                        mod_id = ?, mod_dt = ?
                    WHERE farm_cd = ? AND obs_id = ?
                    """,
                    (
                        parsed_fruit["width_mm"],
                        parsed_fruit["height_mm"],
                        parsed_fruit["circumference_mm"],
                        parsed_fruit["estimated_weight_g"],
                        parsed_fruit["shape_cd"],
                        parsed_fruit["skin_color_cd"],
                        parsed_fruit["asymmetry_level"],
                        parsed_fruit["spot_yn"],
                        parsed_fruit["wound_yn"],
                        parsed_fruit["crack_yn"],
                        parsed_fruit["russet_yn"],
                        parsed_fruit["sunburn_yn"],
                        parsed_fruit["deformity_yn"],
                        parsed_fruit["stalk_status_cd"],
                        parsed_fruit["calyx_status_cd"],
                        parsed_fruit["fruit_rmk"],
                        uid,
                        now,
                        farm,
                        obs_id,
                    ),
                )
            else:
                cur.execute(
                    """
                    INSERT INTO t_observation_fruit_measurement (
                        farm_cd, obs_id, width_mm, height_mm, circumference_mm,
                        estimated_weight_g, shape_cd, skin_color_cd, asymmetry_level,
                        spot_yn, wound_yn, crack_yn, russet_yn, sunburn_yn, deformity_yn,
                        stalk_status_cd, calyx_status_cd, fruit_rmk,
                        reg_id, reg_dt, mod_id, mod_dt
                    ) VALUES (
                        ?, ?, ?, ?, ?,
                        ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?,
                        ?, ?, ?,
                        ?, ?, ?, ?
                    )
                    """,
                    (
                        farm,
                        obs_id,
                        parsed_fruit["width_mm"],
                        parsed_fruit["height_mm"],
                        parsed_fruit["circumference_mm"],
                        parsed_fruit["estimated_weight_g"],
                        parsed_fruit["shape_cd"],
                        parsed_fruit["skin_color_cd"],
                        parsed_fruit["asymmetry_level"],
                        parsed_fruit["spot_yn"],
                        parsed_fruit["wound_yn"],
                        parsed_fruit["crack_yn"],
                        parsed_fruit["russet_yn"],
                        parsed_fruit["sunburn_yn"],
                        parsed_fruit["deformity_yn"],
                        parsed_fruit["stalk_status_cd"],
                        parsed_fruit["calyx_status_cd"],
                        parsed_fruit["fruit_rmk"],
                        uid,
                        now,
                        uid,
                        now,
                    ),
                )
        else:
            cur.execute(
                """
                DELETE FROM t_observation_fruit_measurement
                WHERE farm_cd = ? AND obs_id = ?
                """,
                (farm, obs_id),
            )

        db.conn.commit()
        print(f"[OBS] save_observation_bundle commit: obs_id={obs_id}")
        return True, msg, obs_id
    except Exception as e:
        if db.conn:
            try:
                db.conn.rollback()
            except sqlite3.Error:
                pass
        print(f"[OBS] save_observation_bundle rollback: {e}")
        return False, f"저장 중 오류가 발생했습니다: {e}", None
    finally:
        db.conn.isolation_level = ""


def save_fruit_measurement(
    db: DBManager,
    farm_cd: str,
    obs_id: str,
    data: dict,
    user_id: str,
) -> tuple[bool, str]:
    farm = (farm_cd or "").strip()
    oid = (obs_id or "").strip()
    uid = (user_id or "").strip()
    data = dict(data or {})
    if not farm:
        return False, "농장코드가 없습니다."
    if not uid:
        return False, "사용자 세션 정보가 없습니다."
    if not oid:
        return False, "관찰번호가 없습니다."

    obs = db.get_observation(farm, oid)
    if not obs or (obs.get("use_yn") or _YN_Y) != _YN_Y:
        return False, "대상 관찰을 찾을 수 없습니다."
    if str(obs.get("target_type_cd") or "").strip() != OBS_TARGET_FRUIT_CD:
        return False, "열매 관찰에서만 측정값을 저장할 수 있습니다."

    ok, msg, parsed = _parse_fruit_payload(data)
    if not ok:
        return False, msg

    now = _now_str()
    shape_cd = parsed["shape_cd"]
    skin_color_cd = parsed["skin_color_cd"]
    stalk_status_cd = parsed["stalk_status_cd"]
    calyx_status_cd = parsed["calyx_status_cd"]
    fruit_rmk = parsed["fruit_rmk"]

    exist = get_fruit_measurement(db, farm, oid)
    try:
        if exist:
            db.execute_query(
                """
                UPDATE t_observation_fruit_measurement SET
                    width_mm = ?, height_mm = ?, circumference_mm = ?,
                    estimated_weight_g = ?, shape_cd = ?, skin_color_cd = ?,
                    asymmetry_level = ?,
                    spot_yn = ?, wound_yn = ?, crack_yn = ?, russet_yn = ?,
                    sunburn_yn = ?, deformity_yn = ?,
                    stalk_status_cd = ?, calyx_status_cd = ?, fruit_rmk = ?,
                    mod_id = ?, mod_dt = ?
                WHERE farm_cd = ? AND obs_id = ?
                """,
                (
                    parsed["width_mm"],
                    parsed["height_mm"],
                    parsed["circumference_mm"],
                    parsed["estimated_weight_g"],
                    shape_cd,
                    skin_color_cd,
                    parsed["asymmetry_level"],
                    parsed["spot_yn"],
                    parsed["wound_yn"],
                    parsed["crack_yn"],
                    parsed["russet_yn"],
                    parsed["sunburn_yn"],
                    parsed["deformity_yn"],
                    stalk_status_cd,
                    calyx_status_cd,
                    fruit_rmk,
                    uid,
                    now,
                    farm,
                    oid,
                ),
            )
        else:
            db.execute_query(
                """
                INSERT INTO t_observation_fruit_measurement (
                    farm_cd, obs_id, width_mm, height_mm, circumference_mm,
                    estimated_weight_g, shape_cd, skin_color_cd, asymmetry_level,
                    spot_yn, wound_yn, crack_yn, russet_yn, sunburn_yn, deformity_yn,
                    stalk_status_cd, calyx_status_cd, fruit_rmk,
                    reg_id, reg_dt, mod_id, mod_dt
                ) VALUES (
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, ?,
                    ?, ?, ?, ?
                )
                """,
                (
                    farm,
                    oid,
                    parsed["width_mm"],
                    parsed["height_mm"],
                    parsed["circumference_mm"],
                    parsed["estimated_weight_g"],
                    shape_cd,
                    skin_color_cd,
                    parsed["asymmetry_level"],
                    parsed["spot_yn"],
                    parsed["wound_yn"],
                    parsed["crack_yn"],
                    parsed["russet_yn"],
                    parsed["sunburn_yn"],
                    parsed["deformity_yn"],
                    stalk_status_cd,
                    calyx_status_cd,
                    fruit_rmk,
                    uid,
                    now,
                    uid,
                    now,
                ),
            )
        return True, "열매 측정값이 저장되었습니다."
    except Exception as e:
        print(f"[DB] save_fruit_measurement: {e}")
        return False, f"열매 측정 저장 중 오류가 발생했습니다: {e}"


def list_observation_track(
    db: DBManager, farm_cd: str, root_obs_id: str
) -> list[dict]:
    """동일 root 계열 관찰을 시간순으로, 대표 썸네일·측정값 포함."""
    farm = (farm_cd or "").strip()
    root = (root_obs_id or "").strip()
    if not farm or not root:
        return []
    rows = db.execute_query(
        """
        SELECT
            o.obs_id, o.farm_cd, o.obs_dt, o.target_type_cd, o.obs_type_cd,
            o.site_id, o.zone_nm, o.row_no, o.tree_no, o.branch_no, o.sample_no,
            o.severity_cd, o.progress_status_cd, o.obs_title, o.obs_content,
            o.action_content, o.followup_dt, o.root_obs_id, o.parent_obs_id,
            o.ai_status, o.use_yn, o.reg_id, o.reg_dt, o.mod_id, o.mod_dt,
            COALESCE(cs.code_nm, o.severity_cd) AS severity_nm,
            COALESCE(cp.code_nm, o.progress_status_cd) AS progress_status_nm,
            th.thumb_path AS thumb_path,
            th.photo_id AS thumb_photo_id,
            fm.width_mm, fm.height_mm, fm.circumference_mm, fm.estimated_weight_g,
            fm.shape_cd, fm.skin_color_cd, fm.asymmetry_level,
            fm.spot_yn, fm.wound_yn, fm.crack_yn, fm.russet_yn,
            fm.sunburn_yn, fm.deformity_yn,
            fm.stalk_status_cd, fm.calyx_status_cd, fm.fruit_rmk
        FROM t_observation_master o
        LEFT JOIN m_common_code cs
            ON cs.farm_cd = o.farm_cd AND cs.code_cd = o.severity_cd
        LEFT JOIN m_common_code cp
            ON cp.farm_cd = o.farm_cd AND cp.code_cd = o.progress_status_cd
        LEFT JOIN (
            SELECT p.farm_cd, p.obs_id, p.photo_id, p.thumb_path
            FROM t_observation_photo p
            WHERE COALESCE(p.use_yn, 'Y') = 'Y'
              AND p.photo_id = (
                  SELECT p2.photo_id
                  FROM t_observation_photo p2
                  WHERE p2.farm_cd = p.farm_cd AND p2.obs_id = p.obs_id
                    AND COALESCE(p2.use_yn, 'Y') = 'Y'
                  ORDER BY COALESCE(p2.sort_no, 999999), p2.photo_id
                  LIMIT 1
              )
        ) th ON th.farm_cd = o.farm_cd AND th.obs_id = o.obs_id
        LEFT JOIN t_observation_fruit_measurement fm
            ON fm.farm_cd = o.farm_cd AND fm.obs_id = o.obs_id
        WHERE o.farm_cd = ?
          AND COALESCE(o.use_yn, 'Y') = 'Y'
          AND COALESCE(NULLIF(TRIM(o.root_obs_id), ''), o.obs_id) = ?
        ORDER BY o.obs_dt ASC, o.obs_id ASC
        """,
        (farm, root),
    ) or []
    return [_row_dict(r) for r in rows]


def count_observations_on_date(db: DBManager, farm_cd: str, obs_dt: str) -> int:
    farm = (farm_cd or "").strip()
    dt = _norm_ymd(obs_dt)
    if not farm or not dt:
        return 0
    rows = db.execute_query(
        """
        SELECT COUNT(*) FROM t_observation_master
        WHERE farm_cd = ?
          AND obs_dt = ?
          AND COALESCE(use_yn, 'Y') = 'Y'
        """,
        (farm, dt),
    )
    if not rows or rows[0][0] is None:
        return 0
    return int(rows[0][0])


def get_observation_dashboard_summary(
    db: DBManager, farm_cd: str, today_ymd: str
) -> dict:
    farm = (farm_cd or "").strip()
    today = _norm_ymd(today_ymd) or _today_ymd()
    empty = {
        "in_progress": 0,
        "followup_today": 0,
        "followup_overdue": 0,
        "caution_danger": 0,
        "month_done": 0,
    }
    if not farm:
        return empty

    month_prefix = today[:7]  # YYYY-MM
    done_list = sorted(OBS_PROGRESS_DONE_CDS)
    placeholders = ",".join("?" * len(done_list))
    try:
        rows = db.execute_query(
            f"""
            SELECT
                SUM(
                    CASE
                        WHEN progress_status_cd NOT IN ({placeholders})
                        THEN 1 ELSE 0
                    END
                ) AS in_progress,
                SUM(
                    CASE
                        WHEN progress_status_cd NOT IN ({placeholders})
                         AND followup_dt = ?
                        THEN 1 ELSE 0
                    END
                ) AS followup_today,
                SUM(
                    CASE
                        WHEN progress_status_cd NOT IN ({placeholders})
                         AND followup_dt IS NOT NULL
                         AND TRIM(followup_dt) <> ''
                         AND followup_dt < ?
                        THEN 1 ELSE 0
                    END
                ) AS followup_overdue,
                SUM(
                    CASE
                        WHEN severity_cd IN ('OS010300', 'OS010400')
                         AND progress_status_cd NOT IN ({placeholders})
                        THEN 1 ELSE 0
                    END
                ) AS caution_danger,
                SUM(
                    CASE
                        WHEN progress_status_cd IN ({placeholders})
                         AND obs_dt LIKE ?
                        THEN 1 ELSE 0
                    END
                ) AS month_done
            FROM t_observation_master
            WHERE farm_cd = ?
              AND COALESCE(use_yn, 'Y') = 'Y'
            """,
            (
                *done_list,
                *done_list,
                today,
                *done_list,
                today,
                *done_list,
                *done_list,
                f"{month_prefix}%",
                farm,
            ),
        )
    except Exception as e:
        print(f"[DB] get_observation_dashboard_summary: {e}")
        return empty

    if not rows:
        return empty
    r = rows[0]
    return {
        "in_progress": int(r[0] or 0),
        "followup_today": int(r[1] or 0),
        "followup_overdue": int(r[2] or 0),
        "caution_danger": int(r[3] or 0),
        "month_done": int(r[4] or 0),
    }


def _empty_obs_day_cell() -> dict:
    return {
        "observation_count": 0,
        "observation_max_severity": "",
        "has_observation": False,
        "has_observation_warning": False,
        "followup_due_count": 0,
        "followup_overdue_count": 0,
    }


def get_observation_monthly_day_map(
    db: DBManager, farm_cd: str, year: int, month: int
) -> dict:
    """일자별 관찰·재관찰 뱃지용 맵. key=YYYY-MM-DD."""
    farm = (farm_cd or "").strip()
    result: dict[str, dict] = {}
    try:
        y = int(year)
        m = int(month)
    except (TypeError, ValueError):
        return result
    if not farm or y < 1 or m < 1 or m > 12:
        return result

    start_dt = f"{y:04d}-{m:02d}-01"
    if m == 12:
        end_dt = f"{y + 1:04d}-01-01"
    else:
        end_dt = f"{y:04d}-{m + 1:02d}-01"
    today = _today_ymd()
    done_list = sorted(OBS_PROGRESS_DONE_CDS)
    ph = ",".join("?" * len(done_list))
    warn_rank = OBS_SEVERITY_RANK.get("OS010200", 2)

    try:
        obs_rows = db.execute_query(
            """
            SELECT obs_dt, severity_cd
            FROM t_observation_master
            WHERE farm_cd = ?
              AND COALESCE(use_yn, 'Y') = 'Y'
              AND obs_dt >= ? AND obs_dt < ?
            """,
            (farm, start_dt, end_dt),
        ) or []

        fu_rows = db.execute_query(
            f"""
            SELECT followup_dt
            FROM t_observation_master
            WHERE farm_cd = ?
              AND COALESCE(use_yn, 'Y') = 'Y'
              AND progress_status_cd NOT IN ({ph})
              AND followup_dt IS NOT NULL
              AND TRIM(followup_dt) <> ''
              AND followup_dt >= ? AND followup_dt < ?
            """,
            (farm, *done_list, start_dt, end_dt),
        ) or []
    except Exception as e:
        print(f"[DB] get_observation_monthly_day_map: {e}")
        return result

    for row in obs_rows:
        dt = _norm_ymd(row[0] if not hasattr(row, "keys") else row["obs_dt"])
        sev = str(
            (row[1] if not hasattr(row, "keys") else row["severity_cd"]) or ""
        ).strip()
        if not dt:
            continue
        cell = result.setdefault(dt, _empty_obs_day_cell())
        cell["observation_count"] = int(cell["observation_count"] or 0) + 1
        cell["has_observation"] = True
        cur = str(cell.get("observation_max_severity") or "")
        if OBS_SEVERITY_RANK.get(sev, 0) > OBS_SEVERITY_RANK.get(cur, 0):
            cell["observation_max_severity"] = sev
        if OBS_SEVERITY_RANK.get(sev, 0) >= warn_rank:
            cell["has_observation_warning"] = True

    for row in fu_rows:
        fu = _norm_ymd(row[0] if not hasattr(row, "keys") else row["followup_dt"])
        if not fu:
            continue
        cell = result.setdefault(fu, _empty_obs_day_cell())
        if fu < today:
            cell["followup_overdue_count"] = int(cell["followup_overdue_count"] or 0) + 1
        else:
            # today 및 미래: due (오늘이면 due, 미래도 예정 카운트)
            cell["followup_due_count"] = int(cell["followup_due_count"] or 0) + 1

    return result
