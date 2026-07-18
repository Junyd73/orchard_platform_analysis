# -*- coding: utf-8 -*-
"""관찰일지 Stage3 — AI 분석·공식 농약 스냅샷 스키마/CRUD (멱등)."""

from __future__ import annotations

import datetime
import json
import sqlite3
from typing import Any

from core.db_manager import DBManager

_YN_Y = "Y"
_YN_N = "N"
_DEL_N = "N"

ANALYSIS_STATUS_PENDING = "PENDING"
ANALYSIS_STATUS_OK = "OK"
ANALYSIS_STATUS_FAILED = "FAILED"
PROMPT_VERSION = "obs_ai_v1"


def _now_str() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _row_dict(row) -> dict:
    if row is None:
        return {}
    if hasattr(row, "keys"):
        return {k: row[k] for k in row.keys()}
    return {}


def _json_dumps(value) -> str | None:
    if value is None:
        return None
    try:
        return json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError):
        return None


def _json_loads(raw, default=None):
    if raw is None or raw == "":
        return default
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(str(raw))
    except (TypeError, ValueError, json.JSONDecodeError):
        return default


def ensure_observation_stage3_schema(db: DBManager) -> None:
    """Stage3 테이블·인덱스·AI 상태 공통코드 멱등 보장."""
    _ensure_ai_analysis_table(db)
    _ensure_ai_candidate_table(db)
    _ensure_ai_photo_table(db)
    _ensure_pesticide_snapshot_table(db)
    _ensure_stage3_ai_status_codes(db)


def _ensure_ai_analysis_table(db: DBManager) -> None:
    try:
        db.execute_query(
            """
            CREATE TABLE IF NOT EXISTS t_observation_ai_analysis (
                farm_cd TEXT NOT NULL,
                analysis_id TEXT NOT NULL,
                obs_id TEXT NOT NULL,
                root_obs_id TEXT,
                provider TEXT,
                model_nm TEXT,
                prompt_version TEXT,
                status TEXT,
                image_quality TEXT,
                analysis_possible INTEGER,
                overall_summary TEXT,
                target_part TEXT,
                additional_photos_json TEXT,
                immediate_actions_json TEXT,
                normalized_result_json TEXT,
                provider_request_id TEXT,
                input_photo_count INTEGER,
                error_code TEXT,
                error_message TEXT,
                analyzed_at TEXT,
                created_by TEXT,
                created_at TEXT,
                updated_by TEXT,
                updated_at TEXT,
                del_yn TEXT DEFAULT 'N',
                PRIMARY KEY (farm_cd, analysis_id)
            )
            """
        )
        db.execute_query(
            "CREATE INDEX IF NOT EXISTS idx_obs_ai_analysis_obs "
            "ON t_observation_ai_analysis(farm_cd, obs_id)"
        )
        db.execute_query(
            "CREATE INDEX IF NOT EXISTS idx_obs_ai_analysis_root "
            "ON t_observation_ai_analysis(farm_cd, root_obs_id)"
        )
        db.execute_query(
            "CREATE INDEX IF NOT EXISTS idx_obs_ai_analysis_status "
            "ON t_observation_ai_analysis(farm_cd, status)"
        )
        db.execute_query(
            "CREATE INDEX IF NOT EXISTS idx_obs_ai_analysis_at "
            "ON t_observation_ai_analysis(farm_cd, analyzed_at)"
        )
    except Exception as e:
        print(f"[DB] ensure t_observation_ai_analysis: {e}")


def _ensure_ai_candidate_table(db: DBManager) -> None:
    try:
        db.execute_query(
            """
            CREATE TABLE IF NOT EXISTS t_observation_ai_candidate (
                farm_cd TEXT NOT NULL,
                analysis_id TEXT NOT NULL,
                candidate_seq INTEGER NOT NULL,
                category TEXT,
                name_ko TEXT,
                scientific_name TEXT,
                confidence REAL,
                visual_evidence_json TEXT,
                differential_reason TEXT,
                urgency TEXT,
                selected_yn TEXT DEFAULT 'N',
                confirmed_name TEXT,
                confirmed_by TEXT,
                confirmed_at TEXT,
                created_at TEXT,
                PRIMARY KEY (farm_cd, analysis_id, candidate_seq)
            )
            """
        )
    except Exception as e:
        print(f"[DB] ensure t_observation_ai_candidate: {e}")


def _ensure_ai_photo_table(db: DBManager) -> None:
    try:
        db.execute_query(
            """
            CREATE TABLE IF NOT EXISTS t_observation_ai_photo (
                farm_cd TEXT NOT NULL,
                analysis_id TEXT NOT NULL,
                photo_id TEXT NOT NULL,
                created_at TEXT,
                PRIMARY KEY (farm_cd, analysis_id, photo_id)
            )
            """
        )
    except Exception as e:
        print(f"[DB] ensure t_observation_ai_photo: {e}")


def _ensure_pesticide_snapshot_table(db: DBManager) -> None:
    try:
        db.execute_query(
            """
            CREATE TABLE IF NOT EXISTS t_observation_pesticide_snapshot (
                farm_cd TEXT NOT NULL,
                snapshot_id TEXT NOT NULL,
                analysis_id TEXT,
                obs_id TEXT NOT NULL,
                crop_name TEXT,
                disease_name TEXT,
                match_type TEXT,
                pesti_code TEXT,
                disease_use_seq TEXT,
                pesticide_name TEXT,
                brand_name TEXT,
                company_name TEXT,
                active_ingredient TEXT,
                purpose_name TEXT,
                action_mechanism TEXT,
                usage_method TEXT,
                dilution TEXT,
                preharvest_interval TEXT,
                max_use_count TEXT,
                toxicity TEXT,
                fish_toxicity TEXT,
                source_nm TEXT,
                source_url TEXT,
                fetched_at TEXT,
                created_by TEXT,
                created_at TEXT,
                del_yn TEXT DEFAULT 'N',
                PRIMARY KEY (farm_cd, snapshot_id)
            )
            """
        )
        db.execute_query(
            "CREATE INDEX IF NOT EXISTS idx_obs_pesti_snap_analysis "
            "ON t_observation_pesticide_snapshot(farm_cd, analysis_id)"
        )
        db.execute_query(
            "CREATE INDEX IF NOT EXISTS idx_obs_pesti_snap_obs "
            "ON t_observation_pesticide_snapshot(farm_cd, obs_id)"
        )
        db.execute_query(
            "CREATE INDEX IF NOT EXISTS idx_obs_pesti_snap_crop_dis "
            "ON t_observation_pesticide_snapshot(farm_cd, crop_name, disease_name)"
        )
    except Exception as e:
        print(f"[DB] ensure t_observation_pesticide_snapshot: {e}")


def _ensure_stage3_ai_status_codes(db: DBManager) -> None:
    """신규 AI 상태 공통코드 멱등 추가(기존 OA01 보존)."""
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
    farm_cds = [str(r[0]).strip() for r in farms if r and r[0]] or ["OR001"]
    parent = DBManager.OBS_AI_STATUS_PARENT_CD
    children = (
        ("OA010700", DBManager.OBS_AI_STATUS_ANALYZING),
        ("OA010800", DBManager.OBS_AI_STATUS_ANALYZED),
        ("OA010900", DBManager.OBS_AI_STATUS_REVIEW_REQUIRED),
    )
    now_sql = "datetime('now','localtime')"
    for farm_cd in farm_cds:
        for code_cd, code_nm in children:
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
                (farm_cd, code_cd, code_nm, parent, farm_cd, code_cd),
            )


def generate_analysis_id(db: DBManager, farm_cd: str) -> str:
    farm = (farm_cd or "").strip()
    digits = datetime.date.today().strftime("%Y%m%d")
    prefix = f"AIA{digits}-"
    rows = db.execute_query(
        """
        SELECT analysis_id FROM t_observation_ai_analysis
        WHERE farm_cd = ? AND analysis_id LIKE ?
        ORDER BY analysis_id DESC LIMIT 1
        """,
        (farm, prefix + "%"),
    )
    seq = 1
    if rows and rows[0] and rows[0][0]:
        try:
            seq = int(str(rows[0][0]).rsplit("-", 1)[-1]) + 1
        except (TypeError, ValueError):
            seq = 1
    return f"{prefix}{seq:03d}"


def generate_snapshot_id(db: DBManager, farm_cd: str) -> str:
    farm = (farm_cd or "").strip()
    digits = datetime.date.today().strftime("%Y%m%d")
    prefix = f"PSS{digits}-"
    rows = db.execute_query(
        """
        SELECT snapshot_id FROM t_observation_pesticide_snapshot
        WHERE farm_cd = ? AND snapshot_id LIKE ?
        ORDER BY snapshot_id DESC LIMIT 1
        """,
        (farm, prefix + "%"),
    )
    seq = 1
    if rows and rows[0] and rows[0][0]:
        try:
            seq = int(str(rows[0][0]).rsplit("-", 1)[-1]) + 1
        except (TypeError, ValueError):
            seq = 1
    return f"{prefix}{seq:03d}"


def update_observation_ai_status(
    db: DBManager, farm_cd: str, obs_id: str, ai_status: str, user_id: str
) -> tuple[bool, str]:
    farm = (farm_cd or "").strip()
    oid = (obs_id or "").strip()
    uid = (user_id or "").strip()
    status = db.normalize_obs_ai_status(ai_status, db.OBS_AI_STATUS_NONE)
    if not farm or not oid:
        return False, "관찰번호가 없습니다."
    if not uid:
        return False, "사용자 세션 정보가 없습니다."
    obs = db.get_observation(farm, oid)
    if not obs or (obs.get("use_yn") or _YN_Y) != _YN_Y:
        return False, "대상 관찰을 찾을 수 없습니다."
    now = _now_str()
    try:
        db.execute_query(
            """
            UPDATE t_observation_master
            SET ai_status = ?, mod_id = ?, mod_dt = ?
            WHERE farm_cd = ? AND obs_id = ? AND COALESCE(use_yn, 'Y') = 'Y'
            """,
            (status, uid, now, farm, oid),
        )
        return True, "AI 상태가 갱신되었습니다."
    except Exception as e:
        print(f"[DB] update_observation_ai_status: code=DB_ERROR")
        return False, "데이터 저장 중 오류가 발생했습니다."


def save_ai_analysis_result(
    db: DBManager,
    farm_cd: str,
    obs_id: str,
    *,
    user_id: str,
    photo_ids: list[str],
    provider: str,
    model_nm: str,
    prompt_version: str,
    status: str,
    result: dict | None,
    error_code: str | None = None,
    error_message: str | None = None,
    provider_request_id: str | None = None,
    analysis_id: str | None = None,
) -> tuple[bool, str, str | None]:
    """분석 결과 저장. 실패해도 기존 CONFIRMED 후보를 삭제하지 않음(신규 analysis 행만 추가)."""
    farm = (farm_cd or "").strip()
    oid = (obs_id or "").strip()
    uid = (user_id or "").strip()
    if not farm or not oid:
        return False, "관찰번호가 없습니다.", None
    if not uid:
        return False, "사용자 세션 정보가 없습니다.", None
    obs = db.get_observation(farm, oid)
    if not obs or (obs.get("use_yn") or _YN_Y) != _YN_Y:
        return False, "대상 관찰을 찾을 수 없습니다.", None

    aid = (analysis_id or "").strip() or generate_analysis_id(db, farm)
    now = _now_str()
    result = dict(result or {})
    possible = 1 if result.get("analysis_possible") else 0
    candidates = list(result.get("candidates") or [])[:3]

    try:
        db.conn.isolation_level = None
        cur = db.conn.cursor()
        cur.execute("BEGIN TRANSACTION")
        cur.execute(
            """
            INSERT INTO t_observation_ai_analysis (
                farm_cd, analysis_id, obs_id, root_obs_id, provider, model_nm,
                prompt_version, status, image_quality, analysis_possible,
                overall_summary, target_part, additional_photos_json,
                immediate_actions_json, normalized_result_json,
                provider_request_id, input_photo_count, error_code, error_message,
                analyzed_at, created_by, created_at, updated_by, updated_at, del_yn
            ) VALUES (
                ?,?,?,?,?,?,
                ?,?,?,?,
                ?,?,?,
                ?,?,
                ?,?,?,?,
                ?,?,?,?,?, 'N'
            )
            """,
            (
                farm,
                aid,
                oid,
                (obs.get("root_obs_id") or oid),
                (provider or "").strip() or None,
                (model_nm or "").strip() or None,
                (prompt_version or PROMPT_VERSION),
                (status or ANALYSIS_STATUS_OK),
                result.get("image_quality"),
                possible,
                result.get("overall_summary"),
                result.get("target_part"),
                _json_dumps(result.get("additional_photos")),
                _json_dumps(result.get("safe_immediate_actions")),
                _json_dumps(result),
                (provider_request_id or "").strip() or None,
                len(photo_ids or []),
                (error_code or "").strip() or None,
                (error_message or "").strip() or None,
                now,
                uid,
                now,
                uid,
                now,
            ),
        )
        for i, c in enumerate(candidates, start=1):
            cur.execute(
                """
                INSERT INTO t_observation_ai_candidate (
                    farm_cd, analysis_id, candidate_seq, category, name_ko,
                    scientific_name, confidence, visual_evidence_json,
                    differential_reason, urgency, selected_yn,
                    confirmed_name, confirmed_by, confirmed_at, created_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?, 'N', NULL, NULL, NULL, ?)
                """,
                (
                    farm,
                    aid,
                    i,
                    c.get("category"),
                    c.get("name_ko"),
                    c.get("scientific_name"),
                    c.get("confidence"),
                    _json_dumps(c.get("visual_evidence")),
                    c.get("differential_reason"),
                    c.get("urgency"),
                    now,
                ),
            )
        for pid in photo_ids or []:
            pid = str(pid or "").strip()
            if not pid:
                continue
            cur.execute(
                """
                INSERT OR IGNORE INTO t_observation_ai_photo (
                    farm_cd, analysis_id, photo_id, created_at
                ) VALUES (?, ?, ?, ?)
                """,
                (farm, aid, pid, now),
            )
        db.conn.commit()
        return True, "AI 분석 결과가 저장되었습니다.", aid
    except Exception as e:
        if db.conn:
            try:
                db.conn.rollback()
            except sqlite3.Error:
                pass
        print("[OBS] save_ai_analysis_result rollback: code=DB_ERROR")
        return False, "데이터 저장 중 오류가 발생했습니다.", None
    finally:
        db.conn.isolation_level = ""


def restore_ai_status_after_failure(
    db: DBManager,
    farm_cd: str,
    obs_id: str,
    user_id: str,
    *,
    prev_status: str,
) -> tuple[bool, str]:
    """실패 후 상태 복구: CONFIRMED면 유지, 그 외 FAILED. ANALYZING 잔류 금지."""
    target = (
        DBManager.OBS_AI_STATUS_CONFIRMED
        if str(prev_status or "").strip().upper() == DBManager.OBS_AI_STATUS_CONFIRMED
        else DBManager.OBS_AI_STATUS_FAILED
    )
    return update_observation_ai_status(db, farm_cd, obs_id, target, user_id)


def _hydrate_analysis(db: DBManager, farm: str, rec: dict) -> dict:
    rec = dict(rec or {})
    aid = rec.get("analysis_id") or ""
    rec["additional_photos"] = _json_loads(rec.get("additional_photos_json"), [])
    rec["immediate_actions"] = _json_loads(rec.get("immediate_actions_json"), [])
    rec["normalized_result"] = _json_loads(rec.get("normalized_result_json"), {})
    rec["candidates"] = list_ai_candidates(db, farm, aid)
    rec["photo_ids"] = list_ai_photo_ids(db, farm, aid)
    return rec


def get_ai_analysis(
    db: DBManager, farm_cd: str, analysis_id: str
) -> dict | None:
    """단건 상세(candidates·photo 포함). farm_cd 격리."""
    farm = (farm_cd or "").strip()
    aid = (analysis_id or "").strip()
    if not farm or not aid:
        return None
    rows = db.execute_query(
        """
        SELECT * FROM t_observation_ai_analysis
        WHERE farm_cd = ? AND analysis_id = ? AND COALESCE(del_yn, 'N') = 'N'
        LIMIT 1
        """,
        (farm, aid),
    )
    if not rows:
        return None
    return _hydrate_analysis(db, farm, _row_dict(rows[0]))


def get_latest_ai_attempt(
    db: DBManager, farm_cd: str, obs_id: str
) -> dict | None:
    """성공·실패 포함한 최신 실행(시도)."""
    farm = (farm_cd or "").strip()
    oid = (obs_id or "").strip()
    if not farm or not oid:
        return None
    rows = db.execute_query(
        """
        SELECT * FROM t_observation_ai_analysis
        WHERE farm_cd = ? AND obs_id = ? AND COALESCE(del_yn, 'N') = 'N'
        ORDER BY analyzed_at DESC, analysis_id DESC
        LIMIT 1
        """,
        (farm, oid),
    )
    if not rows:
        return None
    return _hydrate_analysis(db, farm, _row_dict(rows[0]))


def get_latest_ai_analysis(
    db: DBManager, farm_cd: str, obs_id: str
) -> dict | None:
    """현재 유효 분석: 확정 후보가 있는 최신 OK, 없으면 최신 OK. 실패만 있으면 None.

    실패 이력을 현재 확정 결과처럼 반환하지 않는다.
    """
    farm = (farm_cd or "").strip()
    oid = (obs_id or "").strip()
    if not farm or not oid:
        return None
    # 1) 확정 후보가 있는 성공 분석
    rows = db.execute_query(
        """
        SELECT a.*
        FROM t_observation_ai_analysis a
        WHERE a.farm_cd = ? AND a.obs_id = ?
          AND COALESCE(a.del_yn, 'N') = 'N'
          AND COALESCE(a.status, '') = ?
          AND EXISTS (
            SELECT 1 FROM t_observation_ai_candidate c
            WHERE c.farm_cd = a.farm_cd AND c.analysis_id = a.analysis_id
              AND COALESCE(c.selected_yn, 'N') = 'Y'
          )
        ORDER BY a.analyzed_at DESC, a.analysis_id DESC
        LIMIT 1
        """,
        (farm, oid, ANALYSIS_STATUS_OK),
    )
    if rows:
        return _hydrate_analysis(db, farm, _row_dict(rows[0]))
    # 2) 최신 성공 분석
    rows = db.execute_query(
        """
        SELECT * FROM t_observation_ai_analysis
        WHERE farm_cd = ? AND obs_id = ?
          AND COALESCE(del_yn, 'N') = 'N'
          AND COALESCE(status, '') = ?
        ORDER BY analyzed_at DESC, analysis_id DESC
        LIMIT 1
        """,
        (farm, oid, ANALYSIS_STATUS_OK),
    )
    if not rows:
        return None
    return _hydrate_analysis(db, farm, _row_dict(rows[0]))


def list_ai_analysis_history(
    db: DBManager, farm_cd: str, obs_id: str, limit: int = 20
) -> list[dict]:
    farm = (farm_cd or "").strip()
    oid = (obs_id or "").strip()
    if not farm or not oid:
        return []
    lim = max(1, min(int(limit or 20), 100))
    rows = db.execute_query(
        """
        SELECT analysis_id, status, image_quality, analysis_possible,
               overall_summary, model_nm, analyzed_at, error_code, error_message,
               input_photo_count
        FROM t_observation_ai_analysis
        WHERE farm_cd = ? AND obs_id = ? AND COALESCE(del_yn, 'N') = 'N'
        ORDER BY analyzed_at DESC, analysis_id DESC
        LIMIT ?
        """,
        (farm, oid, lim),
    ) or []
    return [_row_dict(r) for r in rows]


def list_ai_candidates(
    db: DBManager, farm_cd: str, analysis_id: str
) -> list[dict]:
    farm = (farm_cd or "").strip()
    aid = (analysis_id or "").strip()
    if not farm or not aid:
        return []
    rows = db.execute_query(
        """
        SELECT * FROM t_observation_ai_candidate
        WHERE farm_cd = ? AND analysis_id = ?
        ORDER BY candidate_seq
        """,
        (farm, aid),
    ) or []
    out = []
    for r in rows:
        d = _row_dict(r)
        d["visual_evidence"] = _json_loads(d.get("visual_evidence_json"), [])
        out.append(d)
    return out


def list_ai_photo_ids(
    db: DBManager, farm_cd: str, analysis_id: str
) -> list[str]:
    farm = (farm_cd or "").strip()
    aid = (analysis_id or "").strip()
    if not farm or not aid:
        return []
    rows = db.execute_query(
        """
        SELECT photo_id FROM t_observation_ai_photo
        WHERE farm_cd = ? AND analysis_id = ?
        ORDER BY photo_id
        """,
        (farm, aid),
    ) or []
    return [str(r[0]) for r in rows if r and r[0]]


def confirm_ai_candidate(
    db: DBManager,
    farm_cd: str,
    analysis_id: str,
    candidate_seq: int,
    confirmed_name: str,
    user_id: str,
    *,
    obs_id: str | None = None,
) -> tuple[bool, str]:
    farm = (farm_cd or "").strip()
    aid = (analysis_id or "").strip()
    uid = (user_id or "").strip()
    name = (confirmed_name or "").strip()
    if not farm or not aid:
        return False, "분석 정보가 없습니다."
    if not uid:
        return False, "사용자 세션 정보가 없습니다."
    if not name:
        return False, "확정 병해충명을 입력해 주세요."
    now = _now_str()
    try:
        db.conn.isolation_level = None
        cur = db.conn.cursor()
        cur.execute("BEGIN TRANSACTION")
        cur.execute(
            """
            UPDATE t_observation_ai_candidate
            SET selected_yn = 'N', confirmed_name = NULL,
                confirmed_by = NULL, confirmed_at = NULL
            WHERE farm_cd = ? AND analysis_id = ?
            """,
            (farm, aid),
        )
        cur.execute(
            """
            UPDATE t_observation_ai_candidate
            SET selected_yn = 'Y', confirmed_name = ?,
                confirmed_by = ?, confirmed_at = ?
            WHERE farm_cd = ? AND analysis_id = ? AND candidate_seq = ?
            """,
            (name, uid, now, farm, aid, int(candidate_seq)),
        )
        if cur.rowcount == 0:
            db.conn.rollback()
            return False, "확정할 후보를 찾을 수 없습니다."
        # 관찰 AI 상태 CONFIRMED
        oid = (obs_id or "").strip()
        if not oid:
            cur.execute(
                """
                SELECT obs_id FROM t_observation_ai_analysis
                WHERE farm_cd = ? AND analysis_id = ? AND COALESCE(del_yn,'N')='N'
                LIMIT 1
                """,
                (farm, aid),
            )
            row = cur.fetchone()
            oid = str(row[0]) if row and row[0] else ""
        if oid:
            cur.execute(
                """
                UPDATE t_observation_master
                SET ai_status = ?, mod_id = ?, mod_dt = ?
                WHERE farm_cd = ? AND obs_id = ? AND COALESCE(use_yn,'Y')='Y'
                """,
                (DBManager.OBS_AI_STATUS_CONFIRMED, uid, now, farm, oid),
            )
        db.conn.commit()
        return True, "병해충 후보가 확정되었습니다."
    except Exception as e:
        if db.conn:
            try:
                db.conn.rollback()
            except sqlite3.Error:
                pass
        print("[OBS] confirm_ai_candidate rollback: code=DB_ERROR")
        return False, "데이터 저장 중 오류가 발생했습니다."
    finally:
        db.conn.isolation_level = ""


def get_confirmed_candidate(
    db: DBManager, farm_cd: str, analysis_id: str
) -> dict | None:
    farm = (farm_cd or "").strip()
    aid = (analysis_id or "").strip()
    if not farm or not aid:
        return None
    rows = db.execute_query(
        """
        SELECT * FROM t_observation_ai_candidate
        WHERE farm_cd = ? AND analysis_id = ? AND COALESCE(selected_yn,'N') = 'Y'
        ORDER BY candidate_seq LIMIT 1
        """,
        (farm, aid),
    )
    if not rows:
        return None
    d = _row_dict(rows[0])
    d["visual_evidence"] = _json_loads(d.get("visual_evidence_json"), [])
    return d


def replace_pesticide_snapshots(
    db: DBManager,
    farm_cd: str,
    obs_id: str,
    analysis_id: str | None,
    crop_name: str,
    disease_name: str,
    match_type: str,
    items: list[dict],
    user_id: str,
) -> tuple[bool, str, list[str]]:
    """동일 crop+disease 기존 스냅샷 논리삭제 후 신규 저장."""
    farm = (farm_cd or "").strip()
    oid = (obs_id or "").strip()
    uid = (user_id or "").strip()
    crop = (crop_name or "").strip()
    disease = (disease_name or "").strip()
    if not farm or not oid:
        return False, "관찰번호가 없습니다.", []
    if not uid:
        return False, "사용자 세션 정보가 없습니다.", []
    now = _now_str()
    ids: list[str] = []
    try:
        db.conn.isolation_level = None
        cur = db.conn.cursor()
        cur.execute("BEGIN TRANSACTION")
        cur.execute(
            """
            UPDATE t_observation_pesticide_snapshot
            SET del_yn = 'Y'
            WHERE farm_cd = ? AND obs_id = ?
              AND crop_name = ? AND disease_name = ?
              AND COALESCE(del_yn,'N') = 'N'
            """,
            (farm, oid, crop, disease),
        )
        digits = datetime.date.today().strftime("%Y%m%d")
        prefix = f"PSS{digits}-"
        cur.execute(
            """
            SELECT snapshot_id FROM t_observation_pesticide_snapshot
            WHERE farm_cd = ? AND snapshot_id LIKE ?
            ORDER BY snapshot_id DESC LIMIT 1
            """,
            (farm, prefix + "%"),
        )
        row = cur.fetchone()
        seq = 1
        if row and row[0]:
            try:
                seq = int(str(row[0]).rsplit("-", 1)[-1]) + 1
            except (TypeError, ValueError):
                seq = 1
        for it in items or []:
            sid = f"{prefix}{seq:03d}"
            seq += 1
            ids.append(sid)
            cur.execute(
                """
                INSERT INTO t_observation_pesticide_snapshot (
                    farm_cd, snapshot_id, analysis_id, obs_id,
                    crop_name, disease_name, match_type,
                    pesti_code, disease_use_seq, pesticide_name, brand_name,
                    company_name, active_ingredient, purpose_name,
                    action_mechanism, usage_method, dilution,
                    preharvest_interval, max_use_count, toxicity, fish_toxicity,
                    source_nm, source_url, fetched_at, created_by, created_at, del_yn
                ) VALUES (
                    ?,?,?,?,
                    ?,?,?,
                    ?,?,?,?,
                    ?,?,?,
                    ?,?,?,
                    ?,?,?,?,
                    ?,?,?,?,?, 'N'
                )
                """,
                (
                    farm,
                    sid,
                    (analysis_id or "").strip() or None,
                    oid,
                    crop,
                    disease,
                    (match_type or "EXACT").strip() or "EXACT",
                    (it.get("pesti_code") or "").strip() or None,
                    (it.get("disease_use_seq") or "").strip() or None,
                    (it.get("pesticide_name") or "").strip() or None,
                    (it.get("brand_name") or "").strip() or None,
                    (it.get("company_name") or "").strip() or None,
                    (it.get("active_ingredient") or "").strip() or None,
                    (it.get("purpose_name") or "").strip() or None,
                    (it.get("action_mechanism") or "").strip() or None,
                    (it.get("usage_method") or "").strip() or None,
                    (it.get("dilution") or "").strip() or None,
                    (it.get("preharvest_interval") or "").strip() or None,
                    (it.get("max_use_count") or "").strip() or None,
                    (it.get("toxicity") or "").strip() or None,
                    (it.get("fish_toxicity") or "").strip() or None,
                    (it.get("source_nm") or "농촌진흥청 농약안전정보시스템").strip(),
                    (it.get("source_url") or "").strip() or None,
                    (it.get("fetched_at") or now),
                    uid,
                    now,
                ),
            )
        db.conn.commit()
        return True, f"{len(ids)}건의 공식 등록정보가 저장되었습니다.", ids
    except Exception as e:
        if db.conn:
            try:
                db.conn.rollback()
            except sqlite3.Error:
                pass
        print("[OBS] replace_pesticide_snapshots rollback: code=DB_ERROR")
        return False, "데이터 저장 중 오류가 발생했습니다.", []
    finally:
        db.conn.isolation_level = ""


def list_pesticide_snapshots(
    db: DBManager,
    farm_cd: str,
    obs_id: str,
    *,
    crop_name: str | None = None,
    disease_name: str | None = None,
    include_deleted: bool = False,
) -> list[dict]:
    farm = (farm_cd or "").strip()
    oid = (obs_id or "").strip()
    if not farm or not oid:
        return []
    sql = """
        SELECT * FROM t_observation_pesticide_snapshot
        WHERE farm_cd = ? AND obs_id = ?
    """
    params: list[Any] = [farm, oid]
    if not include_deleted:
        sql += " AND COALESCE(del_yn,'N') = 'N'"
    if crop_name:
        sql += " AND crop_name = ?"
        params.append(crop_name.strip())
    if disease_name:
        sql += " AND disease_name = ?"
        params.append(disease_name.strip())
    sql += " ORDER BY fetched_at DESC, snapshot_id"
    rows = db.execute_query(sql, tuple(params)) or []
    return [_row_dict(r) for r in rows]


def latest_pesticide_snapshot_group(
    db: DBManager, farm_cd: str, obs_id: str, crop_name: str, disease_name: str
) -> tuple[list[dict], str | None]:
    """동일 작물·병명 스냅샷과 최신 fetched_at."""
    rows = list_pesticide_snapshots(
        db, farm_cd, obs_id, crop_name=crop_name, disease_name=disease_name
    )
    if not rows:
        return [], None
    fetched = rows[0].get("fetched_at")
    return rows, str(fetched) if fetched else None
