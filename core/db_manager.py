import sqlite3
import os
import re
import hashlib
import hmac
import sys
import datetime
from PyQt6.QtCore import QDate, Qt, QTimer, QTime
from PyQt6.QtWidgets import *
from PyQt6.QtGui import *

from core.observation_ai_constants import (
    OBS_AI_STATUS_ANALYZED as _AI_ANALYZED,
    OBS_AI_STATUS_ANALYZING as _AI_ANALYZING,
    OBS_AI_STATUS_COMPLETED as _AI_COMPLETED,
    OBS_AI_STATUS_CONFIRMED as _AI_CONFIRMED,
    OBS_AI_STATUS_FAILED as _AI_FAILED,
    OBS_AI_STATUS_HOLD as _AI_HOLD,
    OBS_AI_STATUS_NONE as _AI_NONE,
    OBS_AI_STATUS_PARENT_CD as _AI_PARENT,
    OBS_AI_STATUS_PENDING as _AI_PENDING,
    OBS_AI_STATUS_REVIEW_REQUIRED as _AI_REVIEW,
    OBS_AI_STATUS_VALUES as _AI_VALUES,
)
from core import observation_stage2_constants as _OBS_S2_C
from core.ops_biz_date import materialize_now_ops_sql, now_ops, now_ops_str, today_ops

class DBManager:
    # ---------------------------------------------------------
    # [핵심] 모든 메서드는 클래스 안쪽으로 4칸 들여쓰기 되어야 합니다.
    # ---------------------------------------------------------

    # 사전(m_pesticide_info) 등록용 더미 행 — ensure 시 제거 대상 품목명
    PESTICIDE_INFO_PURGE_PLACEHOLDER_NM = "테스트농약"
    # 인건비 합계·미지급 집계에 포함: 고용·일용. 농장주·가족(자가노동) 제외.
    PARTNER_WORKER_TYPES_IN_LABOR_TOTAL = ("EMP", "TEMP")
    # 사이드바: 과수원관리(그룹) → 과수원현황(MN02)·인력관리(MN08) — MN12G(농약)와 동일 패턴
    ORCHARD_MENU_GROUP_CD = "MN02G"
    # 사이드바: 환경설정(그룹) → 코드관리(MN03)·메뉴관리(MN09)
    SETTINGS_MENU_GROUP_CD = "MN03G"
    MENU_MANAGEMENT_CD = "MN09"
    # parent_cd 변경 금지(항상 최상위 그룹/대시로 유지)
    # MN01G=영농관리 그룹 (구 MN01 단독 보호 → 그룹으로 이전)
    MENU_PROTECTED_ROOT_PARENT = frozenset({"MN01G", "MN02G", "MN03G"})
    # 영농관리 하위 메뉴
    FARM_WORK_MENU_GROUP_CD = "MN01G"
    WORK_LOG_MENU_DAILY_CD = "MN01"
    WORK_LOG_MENU_MONTHLY_CD = "MN17"
    OBSERVATION_LOG_MENU_CD = "MN16"
    # 관찰일지 공통코드 대분류
    OBS_TARGET_PARENT_CD = "OB01"
    OBS_TYPE_PARENT_CD = "OY01"
    OBS_SEVERITY_PARENT_CD = "OS01"
    OBS_PROGRESS_PARENT_CD = "OP01"
    OBS_AI_STATUS_PARENT_CD = _AI_PARENT
    # 관찰 Stage2 공통코드 (SSOT: observation_stage2_constants)
    OBS_SHOT_PARENT_CD = _OBS_S2_C.OBS_SHOT_PARENT_CD
    OBS_FRUIT_SHAPE_PARENT_CD = _OBS_S2_C.OBS_FRUIT_SHAPE_PARENT_CD
    OBS_FRUIT_COLOR_PARENT_CD = _OBS_S2_C.OBS_FRUIT_COLOR_PARENT_CD
    OBS_STALK_PARENT_CD = _OBS_S2_C.OBS_STALK_PARENT_CD
    OBS_CALYX_PARENT_CD = _OBS_S2_C.OBS_CALYX_PARENT_CD
    OBS_TARGET_FRUIT_CD = _OBS_S2_C.OBS_TARGET_FRUIT_CD
    OBS_PROGRESS_DONE_CDS = _OBS_S2_C.OBS_PROGRESS_DONE_CDS
    OBS_SEVERITY_RANK = _OBS_S2_C.OBS_SEVERITY_RANK
    OBS_AI_STATUS_NONE = _AI_NONE
    OBS_AI_STATUS_PENDING = _AI_PENDING
    OBS_AI_STATUS_COMPLETED = _AI_COMPLETED
    OBS_AI_STATUS_CONFIRMED = _AI_CONFIRMED
    OBS_AI_STATUS_HOLD = _AI_HOLD
    OBS_AI_STATUS_FAILED = _AI_FAILED
    # Stage3 확장 상태(기존 값 보존)
    OBS_AI_STATUS_ANALYZING = _AI_ANALYZING
    OBS_AI_STATUS_ANALYZED = _AI_ANALYZED
    OBS_AI_STATUS_REVIEW_REQUIRED = _AI_REVIEW
    OBS_AI_STATUS_VALUES = _AI_VALUES
    # 신규 메뉴 코드: MN + 영숫자(대문자 저장), 예: MN99, MN16G
    MENU_NEW_CD_PATTERN = re.compile(r"^MN[A-Z0-9]{1,10}$")

    ROLE_HIERARCHY = {
        'SYS_ADMIN': 30,
        'ADMIN': 20,
        'USER': 10
    }
    AUTH_LOCK_FAIL_THRESHOLD = 5
    AUTH_LOCK_SECONDS = 30

    def has_permission(self, current_role, limit_role):
        user_weight = self.ROLE_HIERARCHY.get(current_role, 0)
        limit_weight = self.ROLE_HIERARCHY.get(limit_role, 10)
        return user_weight >= limit_weight

    def hash_password(self, password):
        """
        신규 저장용 해시 포맷:
        pbkdf2_sha256$iterations$salt_hex$dk_hex
        """
        pwd = str(password or "")
        iterations = 260000
        salt = os.urandom(16)
        dk = hashlib.pbkdf2_hmac("sha256", pwd.encode("utf-8"), salt, iterations)
        return f"pbkdf2_sha256${iterations}${salt.hex()}${dk.hex()}"

    def _is_pbkdf2_hash(self, stored_hash: str) -> bool:
        s = str(stored_hash or "")
        return s.startswith("pbkdf2_sha256$")

    def _verify_password(self, input_password: str, stored_hash: str) -> bool:
        """
        기존 SHA256(레거시) + 신규 PBKDF2를 모두 검증.
        """
        raw = str(stored_hash or "").strip()
        if not raw:
            return False
        if self._is_pbkdf2_hash(raw):
            try:
                _, it_s, salt_hex, dk_hex = raw.split("$", 3)
                iterations = int(it_s)
                salt = bytes.fromhex(salt_hex)
                expected = bytes.fromhex(dk_hex)
            except Exception:
                return False
            actual = hashlib.pbkdf2_hmac(
                "sha256",
                str(input_password or "").encode("utf-8"),
                salt,
                iterations,
            )
            return hmac.compare_digest(actual, expected)
        # 레거시 SHA256
        legacy = hashlib.sha256(str(input_password or "").encode("utf-8")).hexdigest()
        return hmac.compare_digest(legacy, raw)

    def generate_sales_no(self, farm_cd: str, sales_date_str: str) -> str:
        """판매번호 생성 공통 규칙: YYYYMMDD-SEQ(2자리)."""
        date_part = str(sales_date_str or "").replace("-", "")
        if len(date_part) != 8 or not date_part.isdigit():
            date_part = today_ops().strftime("%Y%m%d")
        pattern = f"{date_part}-%"
        res = self.execute_query(
            """
            SELECT MAX(sales_no) AS max_no
            FROM t_sales_master
            WHERE sales_no LIKE ? AND farm_cd = ?
            """,
            (pattern, str(farm_cd or "").strip()),
        )
        new_seq = 1
        if res and res[0]["max_no"]:
            try:
                new_seq = int(str(res[0]["max_no"]).split("-")[1]) + 1
            except (TypeError, ValueError, IndexError):
                new_seq = 1
        return f"{date_part}-{new_seq:02d}"

    def login_check(self, user_id, user_pw):
        self.last_auth_error = None
        uid = str(user_id or "").strip()
        pwd = str(user_pw or "")
        if not uid or not pwd:
            return None
        sql = """
            SELECT u.user_id, u.user_nm, u.farm_cd, u.role_cd, u.user_pw, u.use_yn, f.farm_nm AS farm_nm
            FROM m_user u
            LEFT JOIN m_farm_info f ON u.farm_cd = f.farm_cd
            WHERE u.user_id = ? AND u.use_yn = 'Y'
            LIMIT 1
        """
        try:
            cur = self.conn.cursor()
            cur.execute(sql, (uid,))
            one = cur.fetchone()
        except sqlite3.Error as e:
            self.last_auth_error = f"AUTH_DB_ERROR:{e}"
            print(f"[DB] login_check error: {e}")
            return None
        if not one:
            return None
        row = dict(one)
        stored_hash = str(row.get("user_pw") or "")
        if not self._verify_password(pwd, stored_hash):
            return None
        # 레거시 SHA256 계정은 로그인 성공 시 신규 포맷으로 즉시 승격 저장
        if stored_hash and (not self._is_pbkdf2_hash(stored_hash)):
            try:
                upgraded = self.hash_password(pwd)
                self.execute_query(
                    "UPDATE m_user SET user_pw = ?, mod_dt = datetime('now','localtime') WHERE user_id = ?",
                    (upgraded, uid),
                )
            except Exception as e:
                print(f"[DB] legacy password upgrade failed for {uid}: {e}")
        fc = str(row.get("farm_cd") or "").strip()
        # farm_cd 자동 보정 제거: 비어 있으면 로그인 거부(테넌트 혼선 방지)
        if not fc:
            self.last_auth_error = "AUTH_NO_FARM_CD"
            return None
        fn = str(row.get("farm_nm") or "").strip()
        if not fn:
            try:
                alt_nm = self.execute_query(
                    "SELECT farm_nm FROM m_farm_info WHERE farm_cd = ? LIMIT 1",
                    (fc,),
                )
                if alt_nm and alt_nm[0][0] is not None:
                    nm_val = str(alt_nm[0][0]).strip()
                    if nm_val:
                        row["farm_nm"] = nm_val
            except Exception:
                pass
        row.pop("user_pw", None)
        row.pop("use_yn", None)
        return row

    def __init__(self, db_name="orchard_platform.db"):
        # core/ 내부에 있어도 프로젝트 루트 기준 DB 경로.
        # 절대경로가 전달되면(워커 등) join 하지 않고 그대로 정규화한다.
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        raw = str(db_name or "orchard_platform.db").strip() or "orchard_platform.db"
        if os.path.isabs(raw):
            self.db_name = os.path.realpath(os.path.abspath(raw))
        else:
            self.db_name = os.path.realpath(os.path.join(base_dir, raw))
        self.conn = None
        self.connect()

    def connect(self):
        try:
            self.conn = sqlite3.connect(self.db_name)
            self.conn.row_factory = sqlite3.Row
            self.conn.execute("PRAGMA foreign_keys = ON;")
            print(f"[DB] Connected: {self.db_name}")
            self.ensure_pesticide_schema()
            self.ensure_farm_crop_schema()
            self.ensure_work_detail_schema()
            self.ensure_work_photo_schema()
            self.ensure_sales_workflow_schema()
            self.ensure_partner_workforce_schema()
            self.ensure_observation_schema()
            self._ensure_menu_management_group()
            self._ensure_menu_management_page()
            self._apply_sidebar_menu_sort_default()
        except sqlite3.Error as e:
            print(f"[DB] Connect failed: {e}")

    def ensure_work_photo_schema(self):
        """작업 결과 사진 테이블 (t_work_photo)."""
        try:
            from core.work_photo_schema import ensure_work_photo_schema_on_db

            ensure_work_photo_schema_on_db(self)
        except Exception as e:
            print(f"[DB] ensure t_work_photo: {e}")

    def ensure_work_detail_schema(self):
        """영농일지 작업상세 스키마 보정(비고 컬럼 추가)."""
        try:
            cols = self.conn.execute("PRAGMA table_info(t_work_detail)").fetchall()
            col_names = {str(c[1]).strip().lower() for c in (cols or [])}
            if cols and "rmk" not in col_names:
                self.conn.execute("ALTER TABLE t_work_detail ADD COLUMN rmk TEXT")
                self.conn.commit()
                print("[DB] migrate t_work_detail.rmk added")
            for name, col_def in (
                ("google_event_id", "TEXT"),
                ("sync_status", "TEXT"),
                ("last_synced_at", "TEXT"),
            ):
                if cols and name not in col_names:
                    self.conn.execute(
                        f"ALTER TABLE t_work_detail ADD COLUMN {name} {col_def}"
                    )
                    print(f"[DB] migrate t_work_detail.{name} added")
                    col_names.add(name)
            if cols:
                self.conn.commit()
        except Exception as e:
            print(f"[DB] migrate t_work_detail.rmk: {e}")

    def ensure_sales_workflow_schema(self):
        """판매 업무상태/유입경로 컬럼 보정."""
        try:
            cur = self.conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='t_sales_master'")
            if not cur.fetchone():
                return
            cur.execute("PRAGMA table_info(t_sales_master)")
            col_names = {str(r[1]).strip().lower() for r in (cur.fetchall() or [])}
            if "sales_status" not in col_names:
                self.conn.execute(
                    "ALTER TABLE t_sales_master ADD COLUMN sales_status TEXT DEFAULT 'CONFIRMED'"
                )
                print("[DB] migrate t_sales_master.sales_status added")
            if "sales_source" not in col_names:
                self.conn.execute(
                    "ALTER TABLE t_sales_master ADD COLUMN sales_source TEXT DEFAULT 'ORDER'"
                )
                print("[DB] migrate t_sales_master.sales_source added")
            self.conn.commit()
        except Exception as e:
            print(f"[DB] migrate t_sales_master sales workflow columns: {e}")

    def ensure_partner_workforce_schema(self):
        """m_partner.worker_type_cd + 과수원관리(MN02G) 하위 인력관리(MN08) 메뉴 보장."""
        self._migrate_m_partner_worker_type()
        self._migrate_orchard_management_menu_group()

    def ensure_observation_schema(self):
        """관찰일지 테이블·인덱스·공통코드·영농관리 메뉴 보장(멱등)."""
        self._ensure_observation_table()
        self._ensure_observation_common_codes()
        self._migrate_farm_work_menu_group()
        from core.observation_stage2 import ensure_observation_stage2_schema
        ensure_observation_stage2_schema(self)
        from core.observation_stage3 import ensure_observation_stage3_schema
        ensure_observation_stage3_schema(self)

    def _ensure_observation_table(self):
        try:
            self.execute_query(
                """
                CREATE TABLE IF NOT EXISTS t_observation_master (
                    obs_id TEXT NOT NULL,
                    farm_cd TEXT NOT NULL,
                    obs_dt TEXT NOT NULL,
                    target_type_cd TEXT NOT NULL,
                    obs_type_cd TEXT NOT NULL,
                    site_id TEXT,
                    zone_nm TEXT,
                    row_no TEXT,
                    tree_no TEXT,
                    branch_no TEXT,
                    sample_no TEXT,
                    severity_cd TEXT NOT NULL,
                    progress_status_cd TEXT NOT NULL,
                    obs_title TEXT,
                    obs_content TEXT,
                    action_content TEXT,
                    followup_dt TEXT,
                    root_obs_id TEXT,
                    parent_obs_id TEXT,
                    ai_status TEXT DEFAULT 'NONE',
                    use_yn TEXT DEFAULT 'Y',
                    reg_id TEXT,
                    reg_dt TEXT,
                    mod_id TEXT,
                    mod_dt TEXT,
                    PRIMARY KEY (farm_cd, obs_id)
                )
                """
            )
            self.execute_query(
                "CREATE INDEX IF NOT EXISTS idx_obs_farm_dt "
                "ON t_observation_master(farm_cd, obs_dt)"
            )
            self.execute_query(
                "CREATE INDEX IF NOT EXISTS idx_obs_farm_target "
                "ON t_observation_master(farm_cd, target_type_cd)"
            )
            self.execute_query(
                "CREATE INDEX IF NOT EXISTS idx_obs_farm_progress "
                "ON t_observation_master(farm_cd, progress_status_cd)"
            )
            self.execute_query(
                "CREATE INDEX IF NOT EXISTS idx_obs_followup "
                "ON t_observation_master(followup_dt)"
            )
        except Exception as e:
            print(f"[DB] ensure t_observation_master: {e}")

    def _ensure_observation_common_codes(self):
        """관찰 공통코드 멱등 등록(농장별)."""
        try:
            cur = self.conn.cursor()
            cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='m_common_code'"
            )
            if not cur.fetchone():
                return
        except sqlite3.Error:
            return

        farms = self.execute_query("SELECT farm_cd FROM m_farm_info") or []
        farm_cds = [str(r[0]).strip() for r in farms if r and r[0]]
        if not farm_cds:
            farm_cds = ["OR001"]

        parents = (
            (self.OBS_TARGET_PARENT_CD, "관찰대상"),
            (self.OBS_TYPE_PARENT_CD, "관찰유형"),
            (self.OBS_SEVERITY_PARENT_CD, "관찰심각도"),
            (self.OBS_PROGRESS_PARENT_CD, "관찰처리상태"),
            (self.OBS_AI_STATUS_PARENT_CD, "관찰AI상태"),
        )
        children = (
            (self.OBS_TARGET_PARENT_CD, "OB010100", "나무"),
            (self.OBS_TARGET_PARENT_CD, "OB010200", "열매"),
            (self.OBS_TARGET_PARENT_CD, "OB010300", "잎·가지"),
            (self.OBS_TARGET_PARENT_CD, "OB010400", "병해충"),
            (self.OBS_TARGET_PARENT_CD, "OB010500", "토양·시설"),
            (self.OBS_TARGET_PARENT_CD, "OB010600", "기타"),
            (self.OBS_TYPE_PARENT_CD, "OY010100", "생육"),
            (self.OBS_TYPE_PARENT_CD, "OY010200", "착과"),
            (self.OBS_TYPE_PARENT_CD, "OY010300", "과실"),
            (self.OBS_TYPE_PARENT_CD, "OY010400", "병해"),
            (self.OBS_TYPE_PARENT_CD, "OY010500", "충해"),
            (self.OBS_TYPE_PARENT_CD, "OY010600", "생리장해"),
            (self.OBS_TYPE_PARENT_CD, "OY010700", "토양"),
            (self.OBS_TYPE_PARENT_CD, "OY010800", "시설"),
            (self.OBS_TYPE_PARENT_CD, "OY010900", "기타"),
            (self.OBS_SEVERITY_PARENT_CD, "OS010100", "정상"),
            (self.OBS_SEVERITY_PARENT_CD, "OS010200", "관심"),
            (self.OBS_SEVERITY_PARENT_CD, "OS010300", "주의"),
            (self.OBS_SEVERITY_PARENT_CD, "OS010400", "위험"),
            (self.OBS_PROGRESS_PARENT_CD, "OP010100", "관찰 중"),
            (self.OBS_PROGRESS_PARENT_CD, "OP010200", "조치 예정"),
            (self.OBS_PROGRESS_PARENT_CD, "OP010300", "조치 완료"),
            (self.OBS_PROGRESS_PARENT_CD, "OP010400", "정상 회복"),
            (self.OBS_PROGRESS_PARENT_CD, "OP010500", "종료"),
            (self.OBS_AI_STATUS_PARENT_CD, "OA010100", "NONE"),
            (self.OBS_AI_STATUS_PARENT_CD, "OA010200", "PENDING"),
            (self.OBS_AI_STATUS_PARENT_CD, "OA010300", "COMPLETED"),
            (self.OBS_AI_STATUS_PARENT_CD, "OA010400", "CONFIRMED"),
            (self.OBS_AI_STATUS_PARENT_CD, "OA010500", "HOLD"),
            (self.OBS_AI_STATUS_PARENT_CD, "OA010600", "FAILED"),
        )
        now_sql = "datetime('now','localtime')"
        for farm_cd in farm_cds:
            for code_cd, code_nm in parents:
                self.execute_query(
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
                self.execute_query(
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

    def _migrate_farm_work_menu_group(self):
        """영농관리(MN01G) + 영농일지(MN01)·관찰일지(MN16)·월간 영농현황(MN17)."""
        try:
            cur = self.conn.cursor()
            cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='m_menu_info'"
            )
            if not cur.fetchone():
                return
            cur.execute("PRAGMA table_info(m_menu_info)")
            col_names = {row[1] for row in cur.fetchall()}
        except (sqlite3.Error, Exception):
            return
        if not col_names or "parent_cd" not in col_names:
            return

        group_cd = self.FARM_WORK_MENU_GROUP_CD
        daily_cd = self.WORK_LOG_MENU_DAILY_CD
        obs_cd = self.OBSERVATION_LOG_MENU_CD
        monthly_cd = self.WORK_LOG_MENU_MONTHLY_CD
        has_mod = "module_nm" in col_names and "class_nm" in col_names

        top_sort = 20
        r = self.execute_query(
            "SELECT sort_ord FROM m_menu_info WHERE menu_cd = ? LIMIT 1",
            (group_cd,),
        )
        if r and r[0] is not None and r[0][0] is not None:
            try:
                top_sort = int(r[0][0])
            except (TypeError, ValueError):
                pass
        else:
            r1 = self.execute_query(
                "SELECT sort_ord FROM m_menu_info WHERE menu_cd = ? LIMIT 1",
                (daily_cd,),
            )
            if r1 and r1[0] is not None and r1[0][0] is not None:
                try:
                    top_sort = int(r1[0][0])
                except (TypeError, ValueError):
                    pass

        ex_g = self.execute_query(
            "SELECT 1 FROM m_menu_info WHERE menu_cd = ? LIMIT 1", (group_cd,)
        )
        if not ex_g:
            if has_mod:
                self.execute_query(
                    """
                    INSERT INTO m_menu_info (
                        menu_cd, menu_nm, parent_cd, icon_str, page_idx,
                        role_limit, sort_ord, use_yn, module_nm, class_nm
                    ) VALUES (?, ?, NULL, ?, 0, 'USER', ?, 'Y', NULL, NULL)
                    """,
                    (group_cd, "영농관리", "🌳", top_sort),
                )
            else:
                self.execute_query(
                    """
                    INSERT INTO m_menu_info (
                        menu_cd, menu_nm, parent_cd, icon_str, page_idx,
                        role_limit, sort_ord, use_yn
                    ) VALUES (?, ?, NULL, ?, 0, 'USER', ?, 'Y')
                    """,
                    (group_cd, "영농관리", "🌳", top_sort),
                )
        else:
            self.execute_query(
                """
                UPDATE m_menu_info
                SET menu_nm = '영농관리', parent_cd = NULL,
                    icon_str = COALESCE(NULLIF(TRIM(icon_str), ''), '🌳'),
                    role_limit = 'USER', use_yn = 'Y', sort_ord = ?
                WHERE menu_cd = ?
                """,
                (top_sort, group_cd),
            )
            if has_mod:
                self.execute_query(
                    "UPDATE m_menu_info SET module_nm = NULL, class_nm = NULL WHERE menu_cd = ?",
                    (group_cd,),
                )

        # MN01: 영농일지(일간 진입) — 코드 유지, 하위로 이동
        ex1 = self.execute_query(
            "SELECT 1 FROM m_menu_info WHERE menu_cd = ? LIMIT 1", (daily_cd,)
        )
        if ex1:
            if has_mod:
                self.execute_query(
                    """
                    UPDATE m_menu_info SET
                        menu_nm = '영농일지',
                        parent_cd = ?,
                        sort_ord = 10,
                        use_yn = 'Y',
                        role_limit = COALESCE(NULLIF(TRIM(role_limit), ''), 'USER'),
                        icon_str = COALESCE(NULLIF(TRIM(icon_str), ''), '📓'),
                        module_nm = 'ui.pages.work_log_page',
                        class_nm = 'WorkLogPage'
                    WHERE menu_cd = ?
                    """,
                    (group_cd, daily_cd),
                )
            else:
                self.execute_query(
                    """
                    UPDATE m_menu_info SET
                        menu_nm = '영농일지', parent_cd = ?, sort_ord = 10, use_yn = 'Y',
                        icon_str = COALESCE(NULLIF(TRIM(icon_str), ''), '📓')
                    WHERE menu_cd = ?
                    """,
                    (group_cd, daily_cd),
                )
        elif has_mod:
            self.execute_query(
                """
                INSERT INTO m_menu_info (
                    menu_cd, menu_nm, parent_cd, icon_str, page_idx,
                    role_limit, sort_ord, use_yn, module_nm, class_nm
                ) VALUES (?, '영농일지', ?, '📓', 0, 'USER', 10, 'Y',
                          'ui.pages.work_log_page', 'WorkLogPage')
                """,
                (daily_cd, group_cd),
            )

        def _upsert_child(menu_cd, menu_nm, icon, sort_ord, module_nm, class_nm):
            ex = self.execute_query(
                "SELECT 1 FROM m_menu_info WHERE menu_cd = ? LIMIT 1", (menu_cd,)
            )
            if ex:
                if has_mod:
                    self.execute_query(
                        """
                        UPDATE m_menu_info SET
                            menu_nm = ?, parent_cd = ?, sort_ord = ?, use_yn = 'Y',
                            role_limit = COALESCE(NULLIF(TRIM(role_limit), ''), 'USER'),
                            icon_str = COALESCE(NULLIF(TRIM(icon_str), ''), ?),
                            module_nm = COALESCE(NULLIF(TRIM(module_nm), ''), ?),
                            class_nm = COALESCE(NULLIF(TRIM(class_nm), ''), ?)
                        WHERE menu_cd = ?
                        """,
                        (
                            menu_nm,
                            group_cd,
                            sort_ord,
                            icon,
                            module_nm,
                            class_nm,
                            menu_cd,
                        ),
                    )
                else:
                    self.execute_query(
                        """
                        UPDATE m_menu_info SET
                            menu_nm = ?, parent_cd = ?, sort_ord = ?, use_yn = 'Y',
                            icon_str = COALESCE(NULLIF(TRIM(icon_str), ''), ?)
                        WHERE menu_cd = ?
                        """,
                        (menu_nm, group_cd, sort_ord, icon, menu_cd),
                    )
            elif has_mod:
                self.execute_query(
                    """
                    INSERT INTO m_menu_info (
                        menu_cd, menu_nm, parent_cd, icon_str, page_idx,
                        role_limit, sort_ord, use_yn, module_nm, class_nm
                    ) VALUES (?, ?, ?, ?, 0, 'USER', ?, 'Y', ?, ?)
                    """,
                    (
                        menu_cd,
                        menu_nm,
                        group_cd,
                        icon,
                        sort_ord,
                        module_nm,
                        class_nm,
                    ),
                )
            else:
                self.execute_query(
                    """
                    INSERT INTO m_menu_info (
                        menu_cd, menu_nm, parent_cd, icon_str, page_idx,
                        role_limit, sort_ord, use_yn
                    ) VALUES (?, ?, ?, ?, 0, 'USER', ?, 'Y')
                    """,
                    (menu_cd, menu_nm, group_cd, icon, sort_ord),
                )

        _upsert_child(
            obs_cd,
            "관찰일지",
            "🔎",
            20,
            "ui.pages.observation_log_page",
            "ObservationLogPage",
        )
        _upsert_child(
            monthly_cd,
            "월간 영농현황",
            "📅",
            30,
            "ui.pages.work_log_page",
            "WorkLogPage",
        )

    def generate_obs_id(self, farm_cd: str, obs_dt: str) -> str:
        """OBS + YYYYMMDD + - + SEQ(3). obs_dt는 YYYY-MM-DD."""
        farm = (farm_cd or "").strip()
        digits = "".join(ch for ch in (obs_dt or "") if ch.isdigit())[:8]
        if len(digits) != 8:
            digits = today_ops().strftime("%Y%m%d")
        prefix = f"OBS{digits}-"
        rows = self.execute_query(
            """
            SELECT obs_id FROM t_observation_master
            WHERE farm_cd = ? AND obs_id LIKE ?
            ORDER BY obs_id DESC LIMIT 1
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

    @classmethod
    def normalize_obs_ai_status(cls, value, fallback=None) -> str:
        """관찰 AI 상태 정규화. 허용값만 통과, 아니면 fallback→NONE."""
        raw = str(value or "").strip().upper()
        if raw in cls.OBS_AI_STATUS_VALUES:
            return raw
        fb = str(fallback or "").strip().upper()
        if fb in cls.OBS_AI_STATUS_VALUES:
            return fb
        return cls.OBS_AI_STATUS_NONE

    @staticmethod
    def _obs_preserve_field(data: dict, key: str, exist_val, *, default=None):
        """수정 시 요청에 필드가 없거나 빈값이면 기존값 유지."""
        if key not in data:
            cur = exist_val
        else:
            raw = data.get(key)
            if raw is None or str(raw).strip() == "":
                cur = exist_val
            else:
                cur = str(raw).strip()
        if cur is None or str(cur).strip() == "":
            return default
        return str(cur).strip()

    def list_observations(
        self,
        farm_cd: str,
        date_from: str | None = None,
        date_to: str | None = None,
        target_type_cd: str | None = None,
        obs_type_cd: str | None = None,
        severity_cd: str | None = None,
        progress_status_cd: str | None = None,
        site_id: str | None = None,
        keyword: str | None = None,
        limit: int = 500,
    ) -> list[dict]:
        farm = (farm_cd or "").strip()
        if not farm:
            return []
        where = ["o.farm_cd = ?", "COALESCE(o.use_yn, 'Y') = 'Y'"]
        params: list = [farm]
        if date_from:
            where.append("o.obs_dt >= ?")
            params.append(date_from)
        if date_to:
            where.append("o.obs_dt <= ?")
            params.append(date_to)
        if target_type_cd:
            where.append("o.target_type_cd = ?")
            params.append(target_type_cd)
        if obs_type_cd:
            where.append("o.obs_type_cd = ?")
            params.append(obs_type_cd)
        if severity_cd:
            where.append("o.severity_cd = ?")
            params.append(severity_cd)
        if progress_status_cd:
            where.append("o.progress_status_cd = ?")
            params.append(progress_status_cd)
        if site_id:
            where.append("o.site_id = ?")
            params.append(site_id)
        kw = (keyword or "").strip()
        if kw:
            like = f"%{kw}%"
            where.append(
                """(
                    IFNULL(o.obs_title, '') LIKE ?
                    OR IFNULL(o.obs_content, '') LIKE ?
                    OR IFNULL(o.tree_no, '') LIKE ?
                    OR IFNULL(o.sample_no, '') LIKE ?
                    OR IFNULL(o.zone_nm, '') LIKE ?
                )"""
            )
            params.extend([like, like, like, like, like])
        lim = max(1, min(int(limit or 500), 2000))
        sql = f"""
            SELECT
                o.obs_id, o.farm_cd, o.obs_dt, o.target_type_cd, o.obs_type_cd,
                o.site_id, o.zone_nm, o.row_no, o.tree_no, o.branch_no, o.sample_no,
                o.severity_cd, o.progress_status_cd, o.obs_title, o.obs_content,
                o.action_content, o.followup_dt, o.root_obs_id, o.parent_obs_id,
                o.ai_status, o.use_yn, o.reg_id, o.reg_dt, o.mod_id, o.mod_dt,
                COALESCE(fs.site_nm, '') AS site_nm,
                COALESCE(ct.code_nm, o.target_type_cd) AS target_type_nm,
                COALESCE(cy.code_nm, o.obs_type_cd) AS obs_type_nm,
                COALESCE(cs.code_nm, o.severity_cd) AS severity_nm,
                COALESCE(cp.code_nm, o.progress_status_cd) AS progress_status_nm
            FROM t_observation_master o
            LEFT JOIN m_farm_site fs
                ON fs.farm_cd = o.farm_cd AND fs.site_id = o.site_id
            LEFT JOIN m_common_code ct
                ON ct.farm_cd = o.farm_cd AND ct.code_cd = o.target_type_cd
            LEFT JOIN m_common_code cy
                ON cy.farm_cd = o.farm_cd AND cy.code_cd = o.obs_type_cd
            LEFT JOIN m_common_code cs
                ON cs.farm_cd = o.farm_cd AND cs.code_cd = o.severity_cd
            LEFT JOIN m_common_code cp
                ON cp.farm_cd = o.farm_cd AND cp.code_cd = o.progress_status_cd
            WHERE {" AND ".join(where)}
            ORDER BY o.obs_dt DESC, o.obs_id DESC
            LIMIT {lim}
        """
        rows = self.execute_query(sql, tuple(params)) or []
        return [dict(r) for r in rows]

    def get_observation(self, farm_cd: str, obs_id: str) -> dict | None:
        farm = (farm_cd or "").strip()
        oid = (obs_id or "").strip()
        if not farm or not oid:
            return None
        rows = self.execute_query(
            """
            SELECT
                o.*,
                COALESCE(fs.site_nm, '') AS site_nm,
                COALESCE(ct.code_nm, o.target_type_cd) AS target_type_nm,
                COALESCE(cy.code_nm, o.obs_type_cd) AS obs_type_nm,
                COALESCE(cs.code_nm, o.severity_cd) AS severity_nm,
                COALESCE(cp.code_nm, o.progress_status_cd) AS progress_status_nm
            FROM t_observation_master o
            LEFT JOIN m_farm_site fs
                ON fs.farm_cd = o.farm_cd AND fs.site_id = o.site_id
            LEFT JOIN m_common_code ct
                ON ct.farm_cd = o.farm_cd AND ct.code_cd = o.target_type_cd
            LEFT JOIN m_common_code cy
                ON cy.farm_cd = o.farm_cd AND cy.code_cd = o.obs_type_cd
            LEFT JOIN m_common_code cs
                ON cs.farm_cd = o.farm_cd AND cs.code_cd = o.severity_cd
            LEFT JOIN m_common_code cp
                ON cp.farm_cd = o.farm_cd AND cp.code_cd = o.progress_status_cd
            WHERE o.farm_cd = ? AND o.obs_id = ?
            LIMIT 1
            """,
            (farm, oid),
        )
        if not rows:
            return None
        return dict(rows[0])

    def save_observation(self, data: dict, user_id: str) -> tuple[bool, str, str | None]:
        """신규/수정 저장. 성공 시 (True, msg, obs_id)."""
        data = dict(data or {})
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
        now = now_ops().strftime("%Y-%m-%d %H:%M:%S")

        try:
            if is_new:
                ai_status = self.normalize_obs_ai_status(
                    data.get("ai_status"), self.OBS_AI_STATUS_NONE
                )
                obs_id = self.generate_obs_id(farm, obs_dt)
                root_id = (data.get("root_obs_id") or "").strip() or obs_id
                parent_id = (data.get("parent_obs_id") or "").strip() or None
                self.execute_query(
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
                return True, "관찰이 등록되었습니다.", obs_id

            exist = self.get_observation(farm, obs_id)
            if not exist or (exist.get("use_yn") or "Y") != "Y":
                return False, "수정할 관찰을 찾을 수 없습니다.", None

            root_id = self._obs_preserve_field(
                data, "root_obs_id", exist.get("root_obs_id"), default=obs_id
            )
            parent_id = self._obs_preserve_field(
                data, "parent_obs_id", exist.get("parent_obs_id"), default=None
            )
            if "ai_status" in data and str(data.get("ai_status") or "").strip():
                ai_status = self.normalize_obs_ai_status(
                    data.get("ai_status"), exist.get("ai_status")
                )
            else:
                ai_status = self.normalize_obs_ai_status(
                    exist.get("ai_status"), self.OBS_AI_STATUS_NONE
                )

            self.execute_query(
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
            return True, "관찰이 수정되었습니다.", obs_id
        except Exception as e:
            print(f"[DB] save_observation: {e}")
            return False, f"저장 중 오류가 발생했습니다: {e}", None

    def soft_delete_observation(
        self, farm_cd: str, obs_id: str, user_id: str
    ) -> tuple[bool, str]:
        """관찰 soft-delete.

        1차(root, parent 없음) 삭제 시 동일 root_obs_id 의 2차 이상도 함께 삭제한다.
        """
        farm = (farm_cd or "").strip()
        oid = (obs_id or "").strip()
        uid = (user_id or "").strip()
        if not farm or not oid:
            return False, "삭제할 관찰이 없습니다."
        if not uid:
            return False, "사용자 세션 정보가 없습니다."
        now = now_ops().strftime("%Y-%m-%d %H:%M:%S")
        try:
            before = self.get_observation(farm, oid)
            if not before or (before.get("use_yn") or "Y") != "Y":
                return False, "삭제할 관찰을 찾을 수 없습니다."

            parent_id = str(before.get("parent_obs_id") or "").strip()
            root_id = str(before.get("root_obs_id") or "").strip() or oid
            is_root = not parent_id or oid == root_id
            target_ids = [oid]
            if is_root:
                rows = self.execute_query(
                    """
                    SELECT obs_id
                    FROM t_observation_master
                    WHERE farm_cd = ?
                      AND COALESCE(use_yn, 'Y') = 'Y'
                      AND (
                        obs_id = ?
                        OR COALESCE(NULLIF(TRIM(root_obs_id), ''), obs_id) = ?
                      )
                    """,
                    (farm, root_id, root_id),
                ) or []
                ids = []
                for r in rows:
                    if hasattr(r, "keys"):
                        tid = str(r["obs_id"] if "obs_id" in r.keys() else "").strip()
                    else:
                        tid = str(r[0] if r else "").strip()
                    if tid:
                        ids.append(tid)
                target_ids = ids or [oid]

            placeholders = ",".join("?" for _ in target_ids)
            self.execute_query(
                f"""
                UPDATE t_observation_master
                SET use_yn = 'N', mod_id = ?, mod_dt = ?
                WHERE farm_cd = ?
                  AND obs_id IN ({placeholders})
                  AND COALESCE(use_yn, 'Y') = 'Y'
                """,
                (uid, now, farm, *target_ids),
            )
            related = max(0, len(target_ids) - 1)
            if is_root and related > 0:
                return (
                    True,
                    f"관찰 기록과 2차 이상 추적 {related}건이 함께 삭제되었습니다.",
                )
            return True, "관찰이 삭제되었습니다."
        except Exception as e:
            print(f"[DB] soft_delete_observation: {e}")
            return False, f"삭제 중 오류가 발생했습니다: {e}"

    # --- 관찰 Stage2 위임 ---
    def generate_photo_id(self, farm_cd: str) -> str:
        from core.observation_stage2 import generate_photo_id
        return generate_photo_id(self, farm_cd)

    def list_observation_photos(self, farm_cd: str, obs_id: str) -> list[dict]:
        from core.observation_stage2 import list_observation_photos
        return list_observation_photos(self, farm_cd, obs_id)

    def get_observation_photo(self, farm_cd: str, photo_id: str) -> dict | None:
        from core.observation_stage2 import get_observation_photo
        return get_observation_photo(self, farm_cd, photo_id)

    def add_observation_photo(
        self, farm_cd: str, obs_id: str, meta: dict, user_id: str
    ) -> tuple[bool, str, str | None, bool]:
        from core.observation_stage2 import add_observation_photo
        return add_observation_photo(self, farm_cd, obs_id, meta, user_id)

    def add_observation_photos_batch(
        self, farm_cd: str, obs_id: str, metas: list, user_id: str
    ) -> tuple[bool, str, list, list, list]:
        from core.observation_stage2 import add_observation_photos_batch
        return add_observation_photos_batch(
            self, farm_cd, obs_id, metas, user_id
        )

    def save_observation_bundle(
        self,
        observation_data: dict,
        user_id: str,
        fruit_data: dict | None = None,
    ) -> tuple[bool, str, str | None]:
        from core.observation_stage2 import save_observation_bundle
        return save_observation_bundle(
            self, observation_data, user_id, fruit_data=fruit_data
        )

    def update_observation_photo_meta(
        self,
        farm_cd: str,
        photo_id: str,
        shot_type_cd: str | None,
        photo_rmk: str | None,
        sort_no: int | None,
        user_id: str,
    ) -> tuple[bool, str]:
        from core.observation_stage2 import update_observation_photo_meta
        return update_observation_photo_meta(
            self, farm_cd, photo_id, shot_type_cd, photo_rmk, sort_no, user_id
        )

    def soft_delete_observation_photo(
        self, farm_cd: str, photo_id: str, user_id: str
    ) -> tuple[bool, str]:
        from core.observation_stage2 import soft_delete_observation_photo
        return soft_delete_observation_photo(self, farm_cd, photo_id, user_id)

    def reorder_observation_photos(
        self, farm_cd: str, obs_id: str, photo_ids: list, user_id: str
    ) -> tuple[bool, str]:
        from core.observation_stage2 import reorder_observation_photos
        return reorder_observation_photos(self, farm_cd, obs_id, photo_ids, user_id)

    def get_fruit_measurement(self, farm_cd: str, obs_id: str) -> dict | None:
        from core.observation_stage2 import get_fruit_measurement
        return get_fruit_measurement(self, farm_cd, obs_id)

    def save_fruit_measurement(
        self, farm_cd: str, obs_id: str, data: dict, user_id: str
    ) -> tuple[bool, str]:
        from core.observation_stage2 import save_fruit_measurement
        return save_fruit_measurement(self, farm_cd, obs_id, data, user_id)

    def list_observation_track(self, farm_cd: str, root_obs_id: str) -> list[dict]:
        from core.observation_stage2 import list_observation_track
        return list_observation_track(self, farm_cd, root_obs_id)

    def count_observations_on_date(self, farm_cd: str, obs_dt: str) -> int:
        from core.observation_stage2 import count_observations_on_date
        return count_observations_on_date(self, farm_cd, obs_dt)

    def get_observation_dashboard_summary(
        self, farm_cd: str, today_ymd: str
    ) -> dict:
        from core.observation_stage2 import get_observation_dashboard_summary
        return get_observation_dashboard_summary(self, farm_cd, today_ymd)

    def get_observation_monthly_day_map(
        self, farm_cd: str, year: int, month: int
    ) -> dict:
        from core.observation_stage2 import get_observation_monthly_day_map
        return get_observation_monthly_day_map(self, farm_cd, year, month)

    # --- 관찰 Stage3 위임 ---
    def generate_analysis_id(self, farm_cd: str) -> str:
        from core.observation_stage3 import generate_analysis_id
        return generate_analysis_id(self, farm_cd)

    def generate_snapshot_id(self, farm_cd: str) -> str:
        from core.observation_stage3 import generate_snapshot_id
        return generate_snapshot_id(self, farm_cd)

    def update_observation_ai_status(
        self, farm_cd: str, obs_id: str, ai_status: str, user_id: str
    ) -> tuple[bool, str]:
        from core.observation_stage3 import update_observation_ai_status
        return update_observation_ai_status(
            self, farm_cd, obs_id, ai_status, user_id
        )

    def save_ai_analysis_result(self, farm_cd: str, obs_id: str, **kwargs):
        from core.observation_stage3 import save_ai_analysis_result
        return save_ai_analysis_result(self, farm_cd, obs_id, **kwargs)

    def get_latest_ai_analysis(self, farm_cd: str, obs_id: str) -> dict | None:
        from core.observation_stage3 import get_latest_ai_analysis
        return get_latest_ai_analysis(self, farm_cd, obs_id)

    def get_latest_ai_attempt(self, farm_cd: str, obs_id: str) -> dict | None:
        from core.observation_stage3 import get_latest_ai_attempt
        return get_latest_ai_attempt(self, farm_cd, obs_id)

    def get_ai_analysis(self, farm_cd: str, analysis_id: str) -> dict | None:
        from core.observation_stage3 import get_ai_analysis
        return get_ai_analysis(self, farm_cd, analysis_id)

    def list_ai_analysis_history(
        self, farm_cd: str, obs_id: str, limit: int = 20
    ) -> list[dict]:
        from core.observation_stage3 import list_ai_analysis_history
        return list_ai_analysis_history(self, farm_cd, obs_id, limit)

    def confirm_ai_candidate(
        self,
        farm_cd: str,
        analysis_id: str,
        candidate_seq: int,
        confirmed_name: str,
        user_id: str,
        *,
        obs_id: str | None = None,
    ) -> tuple[bool, str]:
        from core.observation_stage3 import confirm_ai_candidate
        return confirm_ai_candidate(
            self,
            farm_cd,
            analysis_id,
            candidate_seq,
            confirmed_name,
            user_id,
            obs_id=obs_id,
        )

    def get_confirmed_candidate(
        self, farm_cd: str, analysis_id: str
    ) -> dict | None:
        from core.observation_stage3 import get_confirmed_candidate
        return get_confirmed_candidate(self, farm_cd, analysis_id)

    def replace_pesticide_snapshots(
        self, farm_cd: str, obs_id: str, analysis_id, crop_name, disease_name,
        match_type, items, user_id,
    ):
        from core.observation_stage3 import replace_pesticide_snapshots
        return replace_pesticide_snapshots(
            self, farm_cd, obs_id, analysis_id, crop_name, disease_name,
            match_type, items, user_id,
        )

    def list_pesticide_snapshots(
        self, farm_cd: str, obs_id: str, **kwargs
    ) -> list[dict]:
        from core.observation_stage3 import list_pesticide_snapshots
        return list_pesticide_snapshots(self, farm_cd, obs_id, **kwargs)

    def latest_pesticide_snapshot_group(
        self, farm_cd: str, obs_id: str, crop_name: str, disease_name: str
    ):
        from core.observation_stage3 import latest_pesticide_snapshot_group
        return latest_pesticide_snapshot_group(
            self, farm_cd, obs_id, crop_name, disease_name
        )

    def _migrate_m_partner_worker_type(self):
        try:
            cur = self.conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='m_partner'")
            if not cur.fetchone():
                return
            cur.execute("PRAGMA table_info(m_partner)")
            names = {str(r[1]).lower() for r in cur.fetchall()}
            if "worker_type_cd" not in names:
                self.conn.execute(
                    "ALTER TABLE m_partner ADD COLUMN worker_type_cd TEXT DEFAULT 'EMP'"
                )
                self.conn.execute(
                    """
                    UPDATE m_partner
                    SET worker_type_cd = 'EMP'
                    WHERE worker_type_cd IS NULL OR TRIM(worker_type_cd) = ''
                    """
                )
                self.conn.commit()
                print("[DB] migrate m_partner.worker_type_cd added")
        except Exception as e:
            print(f"[DB] migrate m_partner.worker_type_cd: {e}")

    def _migrate_orchard_management_menu_group(self):
        """과수원관리(MN02G) 그룹 + 하위 과수원현황(MN02)·인력관리(MN08). 기존 행도 parent/sort 보정."""
        try:
            cur = self.conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='m_menu_info'")
            if not cur.fetchone():
                return
            cur.execute("PRAGMA table_info(m_menu_info)")
            col_names = {row[1] for row in cur.fetchall()}
        except sqlite3.Error:
            return
        except Exception:
            return
        if not col_names or "parent_cd" not in col_names:
            return

        group_cd = DBManager.ORCHARD_MENU_GROUP_CD
        top_sort = 70
        r = self.execute_query(
            "SELECT sort_ord FROM m_menu_info WHERE menu_cd = ? LIMIT 1", (group_cd,)
        )
        if r and r[0] is not None and r[0][0] is not None:
            try:
                top_sort = int(r[0][0])
            except (TypeError, ValueError):
                pass

        ex_g = self.execute_query(
            "SELECT 1 FROM m_menu_info WHERE menu_cd = ? LIMIT 1", (group_cd,)
        )
        if not ex_g:
            if "module_nm" in col_names and "class_nm" in col_names:
                self.execute_query(
                    """
                    INSERT INTO m_menu_info (
                        menu_cd, menu_nm, parent_cd, icon_str, page_idx, role_limit, sort_ord, use_yn,
                        module_nm, class_nm
                    ) VALUES (?, ?, NULL, ?, 0, 'USER', ?, 'Y', NULL, NULL)
                    """,
                    (group_cd, "과수원관리", "🌳", top_sort),
                )
            else:
                self.execute_query(
                    """
                    INSERT INTO m_menu_info (
                        menu_cd, menu_nm, parent_cd, icon_str, page_idx, role_limit, sort_ord, use_yn
                    ) VALUES (?, ?, NULL, ?, 0, 'USER', ?, 'Y')
                    """,
                    (group_cd, "과수원관리", "🌳", top_sort),
                )
        else:
            self.execute_query(
                """
                UPDATE m_menu_info
                SET menu_nm = '과수원관리', parent_cd = NULL,
                    icon_str = COALESCE(NULLIF(TRIM(icon_str), ''), '🌳'),
                    role_limit = 'USER', use_yn = 'Y', sort_ord = ?
                WHERE menu_cd = ?
                """,
                (top_sort, group_cd),
            )
            if "module_nm" in col_names:
                self.execute_query(
                    "UPDATE m_menu_info SET module_nm = NULL, class_nm = NULL WHERE menu_cd = ?",
                    (group_cd,),
                )

        # 과수원 현황: FarmSitePage 매핑 행만(다른 DB에서 MN02가 다른 용도일 수 있음)
        self.execute_query(
            """
            UPDATE m_menu_info
            SET parent_cd = ?, sort_ord = 10, menu_nm = '과수원현황'
            WHERE menu_cd = 'MN02'
              AND (
                COALESCE(module_nm, '') LIKE '%farm_site%'
                OR COALESCE(class_nm, '') = 'FarmSitePage'
              )
            """,
            (group_cd,),
        )

        ex8 = self.execute_query("SELECT 1 FROM m_menu_info WHERE menu_cd = 'MN08' LIMIT 1")
        if ex8:
            if "module_nm" in col_names and "class_nm" in col_names:
                self.execute_query(
                    """
                    UPDATE m_menu_info SET
                        parent_cd = ?, sort_ord = 20,
                        module_nm = 'ui.pages.workforce_page', class_nm = 'WorkforcePage',
                        menu_nm = CASE
                            WHEN TRIM(COALESCE(menu_nm, '')) = '' THEN '인력관리'
                            ELSE menu_nm END
                    WHERE menu_cd = 'MN08'
                    """,
                    (group_cd,),
                )
            else:
                self.execute_query(
                    """
                    UPDATE m_menu_info SET parent_cd = ?, sort_ord = 20, menu_nm = '인력관리'
                    WHERE menu_cd = 'MN08'
                    """,
                    (group_cd,),
                )
        else:
            base_cols = (
                "menu_cd, menu_nm, parent_cd, icon_str, page_idx, role_limit, sort_ord, use_yn"
            )
            if "module_nm" in col_names and "class_nm" in col_names:
                self.execute_query(
                    f"""
                    INSERT INTO m_menu_info ({base_cols}, module_nm, class_nm)
                    VALUES ('MN08', '인력관리', ?, '👷', 0, 'USER', 20, 'Y',
                            'ui.pages.workforce_page', 'WorkforcePage')
                    """,
                    (group_cd,),
                )
            else:
                self.execute_query(
                    f"""
                    INSERT INTO m_menu_info ({base_cols})
                    VALUES ('MN08', '인력관리', ?, '👷', 0, 'USER', 20, 'Y')
                    """,
                    (group_cd,),
                )

    def _ensure_menu_management_group(self):
        """환경설정(MN03G) 그룹 + 코드관리(MN03) 하위 편입. 기존 MN03 단독 행도 보정."""
        try:
            cur = self.conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='m_menu_info'")
            if not cur.fetchone():
                return
            cur.execute("PRAGMA table_info(m_menu_info)")
            col_names = {row[1] for row in cur.fetchall()}
        except (sqlite3.Error, Exception):
            return
        if not col_names or "parent_cd" not in col_names:
            return

        group_cd = DBManager.SETTINGS_MENU_GROUP_CD
        top_sort = 80
        r = self.execute_query(
            "SELECT sort_ord FROM m_menu_info WHERE menu_cd = ? LIMIT 1", (group_cd,)
        )
        if r and r[0] is not None and r[0][0] is not None:
            try:
                top_sort = int(r[0][0])
            except (TypeError, ValueError):
                pass

        ex_g = self.execute_query(
            "SELECT 1 FROM m_menu_info WHERE menu_cd = ? LIMIT 1", (group_cd,)
        )
        if not ex_g:
            if "module_nm" in col_names and "class_nm" in col_names:
                self.execute_query(
                    """
                    INSERT INTO m_menu_info (
                        menu_cd, menu_nm, parent_cd, icon_str, page_idx, role_limit, sort_ord, use_yn,
                        module_nm, class_nm
                    ) VALUES (?, ?, NULL, ?, 0, 'USER', ?, 'Y', NULL, NULL)
                    """,
                    (group_cd, "환경설정", "⚙️", top_sort),
                )
            else:
                self.execute_query(
                    """
                    INSERT INTO m_menu_info (
                        menu_cd, menu_nm, parent_cd, icon_str, page_idx, role_limit, sort_ord, use_yn
                    ) VALUES (?, ?, NULL, ?, 0, 'USER', ?, 'Y')
                    """,
                    (group_cd, "환경설정", "⚙️", top_sort),
                )
        else:
            self.execute_query(
                """
                UPDATE m_menu_info
                SET menu_nm = '환경설정', parent_cd = NULL,
                    icon_str = COALESCE(NULLIF(TRIM(icon_str), ''), '⚙️'),
                    role_limit = 'USER', use_yn = 'Y', sort_ord = ?
                WHERE menu_cd = ?
                """,
                (top_sort, group_cd),
            )
            if "module_nm" in col_names:
                self.execute_query(
                    "UPDATE m_menu_info SET module_nm = NULL, class_nm = NULL WHERE menu_cd = ?",
                    (group_cd,),
                )

        ex3 = self.execute_query("SELECT 1 FROM m_menu_info WHERE menu_cd = 'MN03' LIMIT 1")
        if ex3:
            self.execute_query(
                """
                UPDATE m_menu_info
                SET parent_cd = ?,
                    sort_ord = 10,
                    menu_nm = CASE
                        WHEN TRIM(COALESCE(menu_nm, '')) IN ('', '환경설정') THEN '코드관리'
                        ELSE menu_nm
                    END
                WHERE menu_cd = 'MN03'
                """,
                (group_cd,),
            )
            if "module_nm" in col_names and "class_nm" in col_names:
                self.execute_query(
                    """
                    UPDATE m_menu_info
                    SET module_nm = COALESCE(NULLIF(TRIM(module_nm), ''), 'ui.pages.config_page'),
                        class_nm = COALESCE(NULLIF(TRIM(class_nm), ''), 'ConfigPage')
                    WHERE menu_cd = 'MN03'
                    """,
                    (),
                )

    def _ensure_menu_management_page(self):
        """메뉴관리(MN09) 행 보장·보정."""
        try:
            cur = self.conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='m_menu_info'")
            if not cur.fetchone():
                return
            cur.execute("PRAGMA table_info(m_menu_info)")
            col_names = {row[1] for row in cur.fetchall()}
        except (sqlite3.Error, Exception):
            return
        if not col_names:
            return

        group_cd = DBManager.SETTINGS_MENU_GROUP_CD
        menu_cd = DBManager.MENU_MANAGEMENT_CD
        ex = self.execute_query(
            "SELECT 1 FROM m_menu_info WHERE menu_cd = ? LIMIT 1", (menu_cd,)
        )
        base_cols = (
            "menu_cd, menu_nm, parent_cd, icon_str, page_idx, role_limit, sort_ord, use_yn"
        )
        if ex:
            if "module_nm" in col_names and "class_nm" in col_names:
                self.execute_query(
                    """
                    UPDATE m_menu_info SET
                        menu_nm = '메뉴관리',
                        parent_cd = ?,
                        sort_ord = 20,
                        use_yn = CASE WHEN TRIM(COALESCE(use_yn, '')) = '' THEN 'Y' ELSE use_yn END,
                        role_limit = 'ADMIN',
                        icon_str = COALESCE(NULLIF(TRIM(icon_str), ''), '🧩'),
                        module_nm = 'ui.pages.menu_manage_page',
                        class_nm = 'MenuManagePage'
                    WHERE menu_cd = ?
                    """,
                    (group_cd, menu_cd),
                )
            else:
                self.execute_query(
                    """
                    UPDATE m_menu_info SET
                        menu_nm = '메뉴관리',
                        parent_cd = ?,
                        sort_ord = 20,
                        use_yn = CASE WHEN TRIM(COALESCE(use_yn, '')) = '' THEN 'Y' ELSE use_yn END,
                        role_limit = 'ADMIN',
                        icon_str = COALESCE(NULLIF(TRIM(icon_str), ''), '🧩')
                    WHERE menu_cd = ?
                    """,
                    (group_cd, menu_cd),
                )
        else:
            if "module_nm" in col_names and "class_nm" in col_names:
                self.execute_query(
                    f"""
                    INSERT INTO m_menu_info ({base_cols}, module_nm, class_nm)
                    VALUES (?, '메뉴관리', ?, '🧩', 0, 'ADMIN', 20, 'Y',
                            'ui.pages.menu_manage_page', 'MenuManagePage')
                    """,
                    (menu_cd, group_cd),
                )
            else:
                self.execute_query(
                    f"""
                    INSERT INTO m_menu_info ({base_cols})
                    VALUES (?, '메뉴관리', ?, '🧩', 0, 'ADMIN', 20, 'Y')
                    """,
                    (menu_cd, group_cd),
                )

    def list_m_menu_info_all(self):
        """메뉴관리 화면용 m_menu_info 전체."""
        try:
            cur = self.conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='m_menu_info'")
            if not cur.fetchone():
                return []
        except sqlite3.Error:
            return []
        rows = self.execute_query("SELECT * FROM m_menu_info ORDER BY menu_cd")
        if not rows:
            return []
        return [dict(r) for r in rows]

    @staticmethod
    def _menu_descendant_codes(rows, root_cd: str) -> set:
        """root_cd 하위(직·간접 자식) menu_cd 집합. root_cd 자신은 제외."""
        by_parent = {}
        for r in rows:
            p = (r.get("parent_cd") or "").strip()
            by_parent.setdefault(p, []).append(r.get("menu_cd") or "")
        out = set()
        stack = [root_cd]
        while stack:
            cur = stack.pop()
            for ch in by_parent.get(cur, []):
                if not ch or ch in out:
                    continue
                out.add(ch)
                stack.append(ch)
        return out

    def update_m_menu_info_row(
        self,
        menu_cd: str,
        menu_nm: str,
        parent_cd: str | None,
        sort_ord: int,
        use_yn: str,
        role_limit: str,
        icon_str: str,
        module_nm: str | None,
        class_nm: str | None,
        editor_role_cd: str,
    ) -> tuple[bool, str | None]:
        """
        메뉴 1행 수정. 삭제 없음(use_yn='N'만).
        보호 MN01G/MN02G/MN03G: parent_cd는 항상 NULL.
        module_nm/class_nm: SYS_ADMIN만 변경, 그 외 기존값 유지.
        """
        menu_cd = (menu_cd or "").strip()
        if not menu_cd:
            return False, "메뉴 코드가 없습니다."

        rows = self.list_m_menu_info_all()
        codes = {r.get("menu_cd") for r in rows}
        if menu_cd not in codes:
            return False, "존재하지 않는 메뉴입니다."

        parent = (parent_cd or "").strip() or None
        if menu_cd in DBManager.MENU_PROTECTED_ROOT_PARENT:
            parent = None

        if parent:
            if parent not in codes:
                return False, "상위 메뉴 코드가 존재하지 않습니다."
            if parent == menu_cd:
                return False, "자기 자신을 상위로 지정할 수 없습니다."
            desc = DBManager._menu_descendant_codes(rows, menu_cd)
            if parent in desc:
                return False, "하위 메뉴를 상위로 지정할 수 없습니다."

        uy = (use_yn or "Y").strip().upper()[:1]
        if uy not in ("Y", "N"):
            uy = "Y"
        rl = (role_limit or "USER").strip().upper()
        if rl not in ("USER", "ADMIN", "SYS_ADMIN"):
            rl = "USER"

        allow_adv = self.has_permission(editor_role_cd, "SYS_ADMIN")
        mod_nm = (module_nm or "").strip() or None
        cls_nm = (class_nm or "").strip() or None
        if not allow_adv:
            for r in rows:
                if r.get("menu_cd") == menu_cd:
                    mod_nm = (r.get("module_nm") or "").strip() or None
                    cls_nm = (r.get("class_nm") or "").strip() or None
                    break

        try:
            so = int(sort_ord)
        except (TypeError, ValueError):
            so = 0

        try:
            cur = self.conn.cursor()
            cur.execute("PRAGMA table_info(m_menu_info)")
            col_names = {row[1] for row in cur.fetchall()}
        except sqlite3.Error:
            return False, "DB 오류"

        nm = (menu_nm or "").strip() or menu_cd
        ic = (icon_str or "").strip()

        if "module_nm" in col_names and "class_nm" in col_names:
            self.execute_query(
                """
                UPDATE m_menu_info SET
                    menu_nm = ?, parent_cd = ?, sort_ord = ?, use_yn = ?,
                    role_limit = ?, icon_str = ?, module_nm = ?, class_nm = ?
                WHERE menu_cd = ?
                """,
                (nm, parent, so, uy, rl, ic, mod_nm, cls_nm, menu_cd),
            )
        else:
            self.execute_query(
                """
                UPDATE m_menu_info SET
                    menu_nm = ?, parent_cd = ?, sort_ord = ?, use_yn = ?,
                    role_limit = ?, icon_str = ?
                WHERE menu_cd = ?
                """,
                (nm, parent, so, uy, rl, ic, menu_cd),
            )
        return True, None

    def insert_m_menu_info_row(
        self,
        menu_cd: str,
        menu_nm: str,
        parent_cd: str | None,
        sort_ord: int,
        use_yn: str,
        role_limit: str,
        icon_str: str,
        module_nm: str | None,
        class_nm: str | None,
        editor_role_cd: str,
    ) -> tuple[bool, str | None]:
        """m_menu_info 신규 1행. SYS_ADMIN만 허용."""
        if not self.has_permission((editor_role_cd or "").strip(), "SYS_ADMIN"):
            return False, "신규 등록은 SYS_ADMIN만 가능합니다."

        cd = (menu_cd or "").strip().upper()
        if not cd or not DBManager.MENU_NEW_CD_PATTERN.match(cd):
            return False, "메뉴코드는 MN으로 시작하는 영문·숫자 조합(예: MN99, MN16G)만 허용됩니다."
        if cd in DBManager.MENU_PROTECTED_ROOT_PARENT:
            return False, "예약된 메뉴 코드는 사용할 수 없습니다."

        rows = self.list_m_menu_info_all()
        codes = {r.get("menu_cd") for r in rows}
        if cd in codes:
            return False, "이미 사용 중인 메뉴 코드입니다."

        parent = (parent_cd or "").strip() or None
        if parent:
            if parent not in codes:
                return False, "상위 메뉴 코드가 존재하지 않습니다."
            if parent == cd:
                return False, "자기 자신을 상위로 지정할 수 없습니다."

        uy = (use_yn or "Y").strip().upper()[:1]
        if uy not in ("Y", "N"):
            uy = "Y"
        rl = (role_limit or "USER").strip().upper()
        if rl not in ("USER", "ADMIN", "SYS_ADMIN"):
            rl = "USER"

        try:
            so = int(sort_ord)
        except (TypeError, ValueError):
            so = 0

        nm = (menu_nm or "").strip() or cd
        ic = (icon_str or "").strip() or "📋"
        mod_nm = (module_nm or "").strip() or None
        cls_nm = (class_nm or "").strip() or None

        try:
            cur = self.conn.cursor()
            cur.execute("PRAGMA table_info(m_menu_info)")
            col_names = {row[1] for row in cur.fetchall()}
        except sqlite3.Error:
            return False, "DB 오류"

        base_cols = (
            "menu_cd, menu_nm, parent_cd, icon_str, page_idx, role_limit, sort_ord, use_yn"
        )
        if "module_nm" in col_names and "class_nm" in col_names:
            self.execute_query(
                f"""
                INSERT INTO m_menu_info ({base_cols}, module_nm, class_nm)
                VALUES (?, ?, ?, ?, 0, ?, ?, ?, ?, ?)
                """,
                (cd, nm, parent, ic, rl, so, uy, mod_nm, cls_nm),
            )
        else:
            self.execute_query(
                f"""
                INSERT INTO m_menu_info ({base_cols})
                VALUES (?, ?, ?, ?, 0, ?, ?, ?, ?)
                """,
                (cd, nm, parent, ic, rl, so, uy),
            )
        return True, None

    @staticmethod
    def _partner_in_labor_total_sql(partner_alias="p"):
        """m_partner JOIN 후 인건비 집계 포함 여부 (기본 EMP)."""
        return (
            f"(COALESCE({partner_alias}.worker_type_cd, 'EMP') IN "
            f"('{DBManager.PARTNER_WORKER_TYPES_IN_LABOR_TOTAL[0]}', "
            f"'{DBManager.PARTNER_WORKER_TYPES_IN_LABOR_TOTAL[1]}'))"
        )

    def ensure_pesticide_schema(self):
        """농약관리 테이블 및 사이드 메뉴 행 보장(기존 DB에도 안전하게 적용)."""
        self._drop_pesticide_purpose_tables_if_exist()
        ddls = [
            """
            CREATE TABLE IF NOT EXISTS m_pesticide_supplier (
                supplier_id INTEGER PRIMARY KEY AUTOINCREMENT,
                farm_cd TEXT NOT NULL,
                biz_reg_no TEXT,
                supplier_nm TEXT NOT NULL,
                ceo_nm TEXT,
                addr TEXT,
                biz_type TEXT,
                biz_item TEXT,
                use_yn TEXT NOT NULL DEFAULT 'Y',
                reg_id TEXT,
                reg_dt TEXT DEFAULT (datetime('now','localtime')),
                mod_id TEXT,
                mod_dt TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS m_pesticide_item (
                item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                farm_cd TEXT NOT NULL,
                item_nm TEXT NOT NULL,
                spec_nm TEXT,
                pest_category_nm TEXT DEFAULT '',
                qty_box INTEGER NOT NULL DEFAULT 0,
                qty_piece INTEGER NOT NULL DEFAULT 0,
                warn_box_below INTEGER,
                warn_piece_below INTEGER,
                sort_ord INTEGER NOT NULL DEFAULT 0,
                use_yn TEXT NOT NULL DEFAULT 'Y',
                rmk TEXT,
                reg_id TEXT,
                reg_dt TEXT DEFAULT (datetime('now','localtime')),
                mod_id TEXT,
                mod_dt TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS t_pesticide_receipt (
                receipt_id INTEGER PRIMARY KEY AUTOINCREMENT,
                farm_cd TEXT NOT NULL,
                receipt_dt TEXT NOT NULL,
                supplier_id INTEGER,
                supplier_nm_text TEXT,
                recipient_nm TEXT,
                rmk TEXT,
                reg_id TEXT,
                reg_dt TEXT DEFAULT (datetime('now','localtime')),
                mod_id TEXT,
                mod_dt TEXT,
                FOREIGN KEY (supplier_id) REFERENCES m_pesticide_supplier(supplier_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS t_pesticide_receipt_line (
                line_id INTEGER PRIMARY KEY AUTOINCREMENT,
                receipt_id INTEGER NOT NULL,
                line_no INTEGER NOT NULL DEFAULT 1,
                link_item_id INTEGER,
                info_id INTEGER,
                item_nm TEXT NOT NULL,
                spec_nm TEXT,
                qty INTEGER NOT NULL DEFAULT 0,
                unit_price REAL,
                supply_amt REAL,
                tax_amt REAL,
                line_rmk TEXT,
                checked_yn TEXT NOT NULL DEFAULT 'N',
                FOREIGN KEY (receipt_id) REFERENCES t_pesticide_receipt(receipt_id) ON DELETE CASCADE,
                FOREIGN KEY (link_item_id) REFERENCES m_pesticide_item(item_id) ON DELETE SET NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS t_pesticide_use (
                use_id INTEGER PRIMARY KEY AUTOINCREMENT,
                farm_cd TEXT NOT NULL,
                use_dt TEXT NOT NULL,
                site_id INTEGER,
                worker_nm TEXT,
                worker_id TEXT,
                work_type_nm TEXT,
                rmk TEXT,
                work_id TEXT,
                stock_applied_yn TEXT NOT NULL DEFAULT 'N',
                stock_applied_dt TEXT,
                stock_applied_by TEXT,
                cancel_yn TEXT NOT NULL DEFAULT 'N',
                use_yn TEXT NOT NULL DEFAULT 'Y',
                reg_id TEXT,
                reg_dt TEXT DEFAULT (datetime('now','localtime')),
                mod_id TEXT,
                mod_dt TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS t_pesticide_use_line (
                use_line_id INTEGER PRIMARY KEY AUTOINCREMENT,
                use_id INTEGER NOT NULL,
                line_no INTEGER NOT NULL DEFAULT 1,
                item_id INTEGER NOT NULL,
                item_nm_snapshot TEXT NOT NULL,
                spec_nm_snapshot TEXT,
                use_qty INTEGER NOT NULL DEFAULT 0,
                purpose_nm TEXT,
                line_rmk TEXT,
                reg_id TEXT,
                reg_dt TEXT DEFAULT (datetime('now','localtime')),
                mod_id TEXT,
                mod_dt TEXT,
                FOREIGN KEY (use_id) REFERENCES t_pesticide_use(use_id) ON DELETE CASCADE,
                FOREIGN KEY (item_id) REFERENCES m_pesticide_item(item_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS t_pesticide_stock_hist (
                hist_id INTEGER PRIMARY KEY AUTOINCREMENT,
                farm_cd TEXT NOT NULL,
                item_id INTEGER NOT NULL,
                trans_type TEXT NOT NULL,
                ref_table TEXT,
                ref_id INTEGER,
                ref_line_id INTEGER,
                qty_delta INTEGER NOT NULL,
                qty_after INTEGER,
                trans_dt TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                rmk TEXT,
                reg_id TEXT,
                reg_dt TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (item_id) REFERENCES m_pesticide_item(item_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS m_pesticide_info (
                info_id INTEGER PRIMARY KEY AUTOINCREMENT,
                pesticide_nm TEXT NOT NULL,
                maker_nm TEXT,
                ingredient_nm TEXT,
                category_nm TEXT,
                brand_nm TEXT,
                spec_nm TEXT,
                dilution_guide TEXT,
                usage_note TEXT,
                caution_note TEXT,
                use_yn TEXT DEFAULT 'Y',
                rmk TEXT,
                reg_id TEXT,
                reg_dt TEXT DEFAULT (datetime('now','localtime')),
                mod_id TEXT,
                mod_dt TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS m_pesticide_pest_map (
                map_id INTEGER PRIMARY KEY AUTOINCREMENT,
                info_id INTEGER NOT NULL,
                pest_nm TEXT NOT NULL,
                source_type TEXT NOT NULL DEFAULT 'manual',
                use_yn TEXT NOT NULL DEFAULT 'Y',
                rmk TEXT,
                reg_id TEXT,
                reg_dt TEXT DEFAULT (datetime('now','localtime')),
                mod_id TEXT,
                mod_dt TEXT,
                FOREIGN KEY (info_id) REFERENCES m_pesticide_info(info_id) ON DELETE CASCADE,
                UNIQUE (info_id, pest_nm)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS t_pest_ai_recommend_log (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                farm_cd TEXT,
                recommend_dt TEXT,
                avg_temp_3d REAL,
                rain_sum_7d REAL,
                rain_days_7d INTEGER,
                avg_humidity_7d REAL,
                recent_spray_yn TEXT,
                after_bag_yn TEXT,
                pests_json TEXT,
                pesticides_json TEXT,
                selected_pesticide_nm TEXT,
                reg_dt TEXT DEFAULT (datetime('now','localtime'))
            )
            """,
        ]
        for ddl in ddls:
            self.execute_query(ddl.strip())
        self._migrate_pesticide_receipt_columns()
        self._migrate_pesticide_item_columns()
        self._migrate_pesticide_item_info_id()
        self._migrate_pesticide_info_brand_nm()
        self._migrate_pesticide_info_psis_crop()
        self._migrate_pesticide_use_work_id()
        self._migrate_pesticide_use_cancel_yn()
        self._ensure_pesticide_pest_map_indexes()
        self._migrate_pest_nm_black_spot_to_official()
        self._ensure_pesticide_menu_row()
        self._ensure_pesticide_use_menu_row()
        self._ensure_pesticide_stats_menu_row()
        self._ensure_pesticide_info_menu_row()
        self._migrate_pesticide_menu_group()
        self._apply_sidebar_menu_sort_default()
        self._purge_placeholder_pesticide_info_catalog()

    def _apply_sidebar_menu_sort_default(self):
        """사이드바 1단 기본 순서 보정.

        사용자(메뉴관리)에서 저장한 sort_ord를 덮어쓰지 않도록
        정렬값이 비어있는 경우(NULL/0)만 기본값을 채운다.
        """
        try:
            cur = self.conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='m_menu_info'")
            if not cur.fetchone():
                return
        except sqlite3.Error:
            return
        # 간격 10. MN12G·MN02G는 하위 메뉴와 별도 트리(MN02·MN08은 _migrate_orchard_management_menu_group에서 sort).
        for menu_cd, sort_ord in (
            ("MN00", 10),
            ("MN01G", 20),
            ("MN05", 30),
            ("MN06", 40),
            ("MN07", 50),
            ("MN04", 55),
            ("MN12G", 60),
            ("MN02G", 70),
            ("MN03G", 80),
        ):
            try:
                self.execute_query(
                    """
                    UPDATE m_menu_info
                    SET sort_ord = ?
                    WHERE menu_cd = ?
                      AND (sort_ord IS NULL OR CAST(sort_ord AS INTEGER) <= 0)
                    """,
                    (sort_ord, menu_cd),
                )
            except sqlite3.Error:
                pass

    def _purge_placeholder_pesticide_info_catalog(self):
        """m_pesticide_info의 등록용 더미 행 제거. 재고 info_id는 선행 NULL."""
        nm = self.PESTICIDE_INFO_PURGE_PLACEHOLDER_NM
        try:
            self.execute_query(
                """
                UPDATE m_pesticide_item SET info_id = NULL
                WHERE info_id IN (
                    SELECT info_id FROM m_pesticide_info
                    WHERE COALESCE(TRIM(pesticide_nm), '') = ?
                )
                """,
                (nm,),
            )
            self.execute_query(
                """
                DELETE FROM m_pesticide_info
                WHERE COALESCE(TRIM(pesticide_nm), '') = ?
                """,
                (nm,),
            )
        except sqlite3.Error as e:
            print(f"[DB] purge placeholder m_pesticide_info: {e}")

    def ensure_farm_crop_schema(self):
        """농장별 재배작물 마스터(m_farm_crop). 기존 DB에도 안전하게 적용."""
        self.execute_query(
            """
            CREATE TABLE IF NOT EXISTS m_farm_crop (
                crop_id INTEGER PRIMARY KEY AUTOINCREMENT,
                farm_cd TEXT NOT NULL,
                crop_nm TEXT NOT NULL,
                sort_ord INTEGER NOT NULL DEFAULT 0,
                use_yn TEXT NOT NULL DEFAULT 'Y',
                rmk TEXT,
                reg_id TEXT,
                reg_dt TEXT DEFAULT (datetime('now','localtime')),
                mod_id TEXT,
                mod_dt TEXT
            )
            """
        )
        self.execute_query(
            """
            CREATE INDEX IF NOT EXISTS idx_m_farm_crop_farm_cd
            ON m_farm_crop(farm_cd)
            """
        )

    def _ensure_pesticide_info_menu_row(self):
        """m_menu_info에 농약정보 조회 메뉴(MN15) 보장."""
        try:
            cur = self.conn.cursor()
            cur.execute("PRAGMA table_info(m_menu_info)")
            col_names = {row[1] for row in cur.fetchall()}
        except sqlite3.Error:
            return
        except Exception:
            return
        if not col_names:
            return
        menu_cd = "MN15"
        exists = self.execute_query(
            "SELECT 1 FROM m_menu_info WHERE menu_cd = ? LIMIT 1",
            (menu_cd,),
        )
        if exists:
            if "module_nm" in col_names and "class_nm" in col_names:
                self.execute_query(
                    """
                    UPDATE m_menu_info SET module_nm = ?, class_nm = ?
                    WHERE menu_cd = ? AND (module_nm IS NULL OR module_nm = '' OR class_nm IS NULL OR class_nm = '')
                    """,
                    ("ui.pages.pesticide_info_page", "PesticideInfoPage", menu_cd),
                )
            return
        base_cols = (
            "menu_cd, menu_nm, parent_cd, icon_str, page_idx, role_limit, sort_ord, use_yn"
        )
        base_vals = (menu_cd, "농약 사전", None, "📚", 0, "USER", 28, "Y")
        if "module_nm" in col_names and "class_nm" in col_names:
            sql = f"""
                INSERT INTO m_menu_info ({base_cols}, module_nm, class_nm)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            self.execute_query(
                sql,
                base_vals + ("ui.pages.pesticide_info_page", "PesticideInfoPage"),
            )
        else:
            sql = f"INSERT INTO m_menu_info ({base_cols}) VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
            self.execute_query(sql, base_vals)

    def _ensure_pesticide_stats_menu_row(self):
        """m_menu_info에 농약 사용통계 메뉴(MN14) 보장."""
        try:
            cur = self.conn.cursor()
            cur.execute("PRAGMA table_info(m_menu_info)")
            col_names = {row[1] for row in cur.fetchall()}
        except sqlite3.Error:
            return
        except Exception:
            return
        if not col_names:
            return
        menu_cd = "MN14"
        exists = self.execute_query(
            "SELECT 1 FROM m_menu_info WHERE menu_cd = ? LIMIT 1",
            (menu_cd,),
        )
        if exists:
            if "module_nm" in col_names and "class_nm" in col_names:
                self.execute_query(
                    """
                    UPDATE m_menu_info SET module_nm = ?, class_nm = ?
                    WHERE menu_cd = ? AND (module_nm IS NULL OR module_nm = '' OR class_nm IS NULL OR class_nm = '')
                    """,
                    ("ui.pages.pesticide_stats_page", "PesticideStatsPage", menu_cd),
                )
            return
        base_cols = (
            "menu_cd, menu_nm, parent_cd, icon_str, page_idx, role_limit, sort_ord, use_yn"
        )
        base_vals = (menu_cd, "농약 사용통계", None, "📊", 0, "USER", 27, "Y")
        if "module_nm" in col_names and "class_nm" in col_names:
            sql = f"""
                INSERT INTO m_menu_info ({base_cols}, module_nm, class_nm)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            self.execute_query(
                sql,
                base_vals + ("ui.pages.pesticide_stats_page", "PesticideStatsPage"),
            )
        else:
            sql = f"INSERT INTO m_menu_info ({base_cols}) VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
            self.execute_query(sql, base_vals)

    def _ensure_pesticide_use_menu_row(self):
        """m_menu_info에 농약 사용관리 메뉴(MN13) 보장."""
        try:
            cur = self.conn.cursor()
            cur.execute("PRAGMA table_info(m_menu_info)")
            col_names = {row[1] for row in cur.fetchall()}
        except sqlite3.Error:
            return
        except Exception:
            return
        if not col_names:
            return
        menu_cd = "MN13"
        exists = self.execute_query(
            "SELECT 1 FROM m_menu_info WHERE menu_cd = ? LIMIT 1",
            (menu_cd,),
        )
        if exists:
            self.execute_query(
                "UPDATE m_menu_info SET menu_nm = ? WHERE menu_cd = ?",
                ("농약 사용관리", menu_cd),
            )
            if "module_nm" in col_names and "class_nm" in col_names:
                self.execute_query(
                    """
                    UPDATE m_menu_info SET module_nm = ?, class_nm = ?
                    WHERE menu_cd = ? AND (module_nm IS NULL OR module_nm = '' OR class_nm IS NULL OR class_nm = '')
                    """,
                    ("ui.pages.pesticide_use_page", "PesticideUsePage", menu_cd),
                )
            return
        base_cols = (
            "menu_cd, menu_nm, parent_cd, icon_str, page_idx, role_limit, sort_ord, use_yn"
        )
        base_vals = (menu_cd, "농약 사용관리", None, "📝", 0, "USER", 26, "Y")
        if "module_nm" in col_names and "class_nm" in col_names:
            sql = f"""
                INSERT INTO m_menu_info ({base_cols}, module_nm, class_nm)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            self.execute_query(
                sql,
                base_vals + ("ui.pages.pesticide_use_page", "PesticideUsePage"),
            )
        else:
            sql = f"INSERT INTO m_menu_info ({base_cols}) VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
            self.execute_query(sql, base_vals)

    def _migrate_pesticide_item_columns(self):
        """기존 DB: 품목 구분(전착·살충·영양·살균 등) 컬럼."""
        try:
            cur = self.conn.cursor()
            cur.execute("PRAGMA table_info(m_pesticide_item)")
            cols = {row[1] for row in cur.fetchall()}
        except sqlite3.Error:
            return
        if not cols:
            return
        if "pest_category_nm" not in cols:
            self.execute_query(
                "ALTER TABLE m_pesticide_item ADD COLUMN pest_category_nm TEXT DEFAULT ''"
            )

    def _migrate_pesticide_item_info_id(self):
        """재고 품목 ↔ 농약 정보 마스터 연결(선택). 기존 DB에만 ALTER."""
        try:
            cur = self.conn.cursor()
            cur.execute("PRAGMA table_info(m_pesticide_item)")
            cols = {row[1] for row in cur.fetchall()}
        except sqlite3.Error:
            return
        if not cols:
            return
        if "info_id" not in cols:
            self.execute_query(
                "ALTER TABLE m_pesticide_item ADD COLUMN info_id INTEGER"
            )

    def _migrate_pesticide_info_brand_nm(self):
        """상표명(brand_nm)과 규격(spec_nm) 분리. 기존 DB에만 ALTER."""
        try:
            cur = self.conn.cursor()
            cur.execute("PRAGMA table_info(m_pesticide_info)")
            cols = {row[1] for row in cur.fetchall()}
        except sqlite3.Error:
            return
        if not cols:
            return
        if "brand_nm" not in cols:
            self.execute_query(
                "ALTER TABLE m_pesticide_info ADD COLUMN brand_nm TEXT"
            )

    def _migrate_pesticide_use_work_id(self):
        """기존 DB: t_pesticide_use.work_id (영농일지 작업행 연동)."""
        try:
            cur = self.conn.cursor()
            cur.execute("PRAGMA table_info(t_pesticide_use)")
            cols = {row[1] for row in cur.fetchall()}
        except sqlite3.Error:
            return
        if "work_id" in cols:
            return
        try:
            self.execute_query("ALTER TABLE t_pesticide_use ADD COLUMN work_id TEXT")
        except sqlite3.Error as e:
            print(f"[DB] migrate t_pesticide_use.work_id: {e}")

    def _migrate_pesticide_use_cancel_yn(self):
        """기존 DB: t_pesticide_use.cancel_yn (확정 취소 vs 미확정 구분)."""
        try:
            cur = self.conn.cursor()
            cur.execute("PRAGMA table_info(t_pesticide_use)")
            cols = {row[1] for row in cur.fetchall()}
        except sqlite3.Error:
            return
        if "cancel_yn" in cols:
            return
        try:
            self.execute_query(
                "ALTER TABLE t_pesticide_use ADD COLUMN cancel_yn TEXT NOT NULL DEFAULT 'N'"
            )
        except sqlite3.Error as e:
            print(f"[DB] migrate t_pesticide_use.cancel_yn: {e}")

    def _migrate_pesticide_info_psis_crop(self):
        """PSIS·작물·병해충 매핑 연계용 컬럼. 설계: crop_nm, psis_pesti_code, psis_disease_use_seq."""
        try:
            cur = self.conn.cursor()
            cur.execute("PRAGMA table_info(m_pesticide_info)")
            cols = {row[1] for row in cur.fetchall()}
        except sqlite3.Error:
            return
        if not cols:
            return
        if "crop_nm" not in cols:
            self.execute_query("ALTER TABLE m_pesticide_info ADD COLUMN crop_nm TEXT")
        if "psis_pesti_code" not in cols:
            self.execute_query("ALTER TABLE m_pesticide_info ADD COLUMN psis_pesti_code TEXT")
        if "psis_disease_use_seq" not in cols:
            self.execute_query(
                "ALTER TABLE m_pesticide_info ADD COLUMN psis_disease_use_seq TEXT"
            )

    def _ensure_pesticide_pest_map_indexes(self):
        """m_pesticide_pest_map 조회용 인덱스(설계 문서의 pesticide_pest_map N:N)."""
        for sql in (
            """
            CREATE INDEX IF NOT EXISTS idx_m_pesticide_pest_map_info_id
            ON m_pesticide_pest_map(info_id)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_m_pesticide_pest_map_pest_nm
            ON m_pesticide_pest_map(pest_nm)
            """,
        ):
            try:
                self.execute_query(sql.strip())
            except sqlite3.Error:
                pass

    def _migrate_pest_nm_black_spot_to_official(self):
        """레거시 병해충명 '흑성병' → PSIS/DB 표준 '검은별무늬병' 통일(UNIQUE 충돌 방지)."""
        try:
            cur = self.conn.cursor()
            cur.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='m_pesticide_pest_map'"
            )
            if not cur.fetchone():
                return
            self.execute_query(
                """
                DELETE FROM m_pesticide_pest_map
                WHERE pest_nm = '흑성병'
                  AND info_id IN (
                      SELECT info_id FROM m_pesticide_pest_map
                      WHERE pest_nm = '검은별무늬병'
                  )
                """
            )
            self.execute_query(
                """
                UPDATE m_pesticide_pest_map
                SET pest_nm = '검은별무늬병'
                WHERE pest_nm = '흑성병'
                """
            )
            cur.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='t_pest_ai_recommend_log'"
            )
            if cur.fetchone():
                self.execute_query(
                    """
                    UPDATE t_pest_ai_recommend_log
                    SET pests_json = REPLACE(pests_json, '흑성병', '검은별무늬병')
                    WHERE IFNULL(pests_json, '') LIKE '%흑성병%'
                    """
                )
                self.execute_query(
                    """
                    UPDATE t_pest_ai_recommend_log
                    SET pesticides_json = REPLACE(
                        pesticides_json, '흑성병', '검은별무늬병'
                    )
                    WHERE IFNULL(pesticides_json, '') LIKE '%흑성병%'
                    """
                )
        except sqlite3.Error as e:
            print(f"[DB] migrate pest_nm 흑성병→검은별무늬병: {e}")

    def _drop_pesticide_purpose_tables_if_exist(self):
        """용도 마스터·info–용도 매핑 제거(병해충 매핑 m_pesticide_pest_map은 유지)."""
        for sql in (
            "DROP TABLE IF EXISTS t_pesticide_info_purpose",
            "DROP TABLE IF EXISTS m_pesticide_purpose",
        ):
            try:
                self.execute_query(sql)
            except sqlite3.Error as e:
                print(f"[DB] drop pesticide purpose table: {e}")

    def _migrate_pesticide_receipt_columns(self):
        """기존 DB: 입고 명세 재고 반영 컬럼 · 라인 사전(info_id) 연결."""
        try:
            from core.pesticide_receipt_schema import ensure_pesticide_receipt_schema

            ensure_pesticide_receipt_schema(self.db_name)
        except Exception as e:
            print(f"[DB] migrate pesticide receipt columns: {e}")

    def _ensure_pesticide_menu_row(self):
        """m_menu_info에 농약관리 메뉴 1행을 넣는다(이미 있으면 건너뜀)."""
        try:
            cur = self.conn.cursor()
            cur.execute("PRAGMA table_info(m_menu_info)")
            col_names = {row[1] for row in cur.fetchall()}
        except sqlite3.Error:
            return
        except Exception:
            return
        if not col_names:
            return
        menu_cd = "MN12"
        exists = self.execute_query(
            "SELECT 1 FROM m_menu_info WHERE menu_cd = ? LIMIT 1",
            (menu_cd,),
        )
        if exists:
            if "module_nm" in col_names and "class_nm" in col_names:
                self.execute_query(
                    """
                    UPDATE m_menu_info SET module_nm = ?, class_nm = ?
                    WHERE menu_cd = ? AND (module_nm IS NULL OR module_nm = '' OR class_nm IS NULL OR class_nm = '')
                    """,
                    ("ui.pages.pesticide_page", "PesticidePage", menu_cd),
                )
            return
        base_cols = (
            "menu_cd, menu_nm, parent_cd, icon_str, page_idx, role_limit, sort_ord, use_yn"
        )
        base_vals = (menu_cd, "농약관리", None, "🧪", 0, "USER", 25, "Y")
        if "module_nm" in col_names and "class_nm" in col_names:
            sql = f"""
                INSERT INTO m_menu_info ({base_cols}, module_nm, class_nm)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            self.execute_query(
                sql,
                base_vals + ("ui.pages.pesticide_page", "PesticidePage"),
            )
        else:
            sql = f"INSERT INTO m_menu_info ({base_cols}) VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
            self.execute_query(sql, base_vals)

    def _migrate_pesticide_menu_group(self):
        """농약 메뉴 2단 구조: 상위 MN12G(농약관리) + 하위 MN12~15. MN12=농약 재고관리, MN15=농약 사전."""
        try:
            cur = self.conn.cursor()
            cur.execute("PRAGMA table_info(m_menu_info)")
            col_names = {row[1] for row in cur.fetchall()}
        except sqlite3.Error:
            return
        except Exception:
            return
        if not col_names or "parent_cd" not in col_names:
            return

        group_cd = "MN12G"
        child_cds = ("MN12", "MN13", "MN14", "MN15")

        r = self.execute_query(
            "SELECT sort_ord FROM m_menu_info WHERE menu_cd = 'MN12' LIMIT 1"
        )
        base = int(r[0][0]) if r and r[0] is not None and r[0][0] is not None else 25

        ex_g = self.execute_query(
            "SELECT 1 FROM m_menu_info WHERE menu_cd = ? LIMIT 1", (group_cd,)
        )
        if not ex_g:
            if "module_nm" in col_names and "class_nm" in col_names:
                self.execute_query(
                    """
                    INSERT INTO m_menu_info (
                        menu_cd, menu_nm, parent_cd, icon_str, page_idx, role_limit, sort_ord, use_yn,
                        module_nm, class_nm
                    ) VALUES (?, ?, NULL, ?, 0, 'USER', ?, 'Y', NULL, NULL)
                    """,
                    (group_cd, "농약관리", "🧪", base),
                )
            else:
                self.execute_query(
                    """
                    INSERT INTO m_menu_info (
                        menu_cd, menu_nm, parent_cd, icon_str, page_idx, role_limit, sort_ord, use_yn
                    ) VALUES (?, ?, NULL, ?, 0, 'USER', ?, 'Y')
                    """,
                    (group_cd, "농약관리", "🧪", base),
                )
        else:
            self.execute_query(
                """
                UPDATE m_menu_info
                SET menu_nm = '농약관리', parent_cd = NULL, icon_str = COALESCE(NULLIF(TRIM(icon_str), ''), '🧪'),
                    role_limit = 'USER', use_yn = 'Y', sort_ord = ?
                WHERE menu_cd = ?
                """,
                (base, group_cd),
            )
            if "module_nm" in col_names:
                self.execute_query(
                    "UPDATE m_menu_info SET module_nm = NULL, class_nm = NULL WHERE menu_cd = ?",
                    (group_cd,),
                )

        self.execute_query(
            """
            UPDATE m_menu_info
            SET menu_nm = '농약 재고관리', parent_cd = ?, sort_ord = ?
            WHERE menu_cd = 'MN12'
            """,
            (group_cd, base + 1),
        )
        for i, cd in enumerate(("MN13", "MN14", "MN15"), start=2):
            self.execute_query(
                """
                UPDATE m_menu_info SET parent_cd = ?, sort_ord = ?
                WHERE menu_cd = ?
                """,
                (group_cd, base + i, cd),
            )
        self.execute_query(
            "UPDATE m_menu_info SET menu_nm = '농약 사전' WHERE menu_cd = 'MN15'",
            (),
        )

    @staticmethod
    def _materialize_ops_now_sql(query: str) -> str:
        """DML의 datetime('now','localtime') → KST now_ops_str 리터럴.

        DDL DEFAULT 구문은 스키마에 그대로 둔다(전수 변경 금지).
        """
        return materialize_now_ops_sql(query)
    def execute_query(self, query, params=()):
        try:
            cur = self.conn.cursor()
            cur.execute(self._materialize_ops_now_sql(query), params)
            query_start = query.strip().upper()
            if query_start.startswith(("INSERT", "UPDATE", "DELETE", "CREATE", "ALTER", "DROP", "REPLACE")):
                self.conn.commit()
            return cur.fetchall()
        except sqlite3.Error as e:
            print(f"[DB] Query error: {e}")
            return []

    def execute_transaction(self, queries_with_params):
        try:
            self.conn.isolation_level = None
            cur = self.conn.cursor()
            cur.execute("BEGIN TRANSACTION")
            for query, params in queries_with_params:
                cur.execute(self._materialize_ops_now_sql(query), params)
            self.conn.commit()
            return True
        except Exception as e:
            if self.conn:
                try:
                    self.conn.rollback()
                except sqlite3.Error:
                    pass
            print(f"[DB] Transaction rollback: {e}")
            raise e
        finally:
            self.conn.isolation_level = ""

    def transaction(self):
        """동일 connection/cursor 기반 Context Manager.

        yield cursor. 블록 정상 종료 시 commit, 예외 시 rollback.
        중첩 Manager 는 별도 BEGIN/COMMIT 없이 on_cursor API만 사용.
        """
        from contextlib import contextmanager

        @contextmanager
        def _ctx():
            conn = self.conn
            prev_isolation = conn.isolation_level
            try:
                conn.isolation_level = None
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                cur.execute("BEGIN IMMEDIATE")
                yield cur
                conn.commit()
            except Exception:
                try:
                    conn.rollback()
                except sqlite3.Error:
                    pass
                raise
            finally:
                try:
                    conn.isolation_level = prev_isolation if prev_isolation is not None else ""
                except Exception:
                    conn.isolation_level = ""

        return _ctx()

    def register_new_farm(self, farm_name, owner_nm, admin_id, admin_pw):
        try:
            res = self.execute_query("SELECT MAX(farm_cd) FROM m_farm_info WHERE farm_cd LIKE 'OR%'")
            max_cd = res[0][0] if res and res[0][0] else "OR000"
            new_farm_cd = f"OR{int(max_cd[2:]) + 1:03d}"
            now = now_ops().strftime("%Y-%m-%d %H:%M:%S")
            hashed_pw = self.hash_password(admin_pw)
            self.execute_query(
                "INSERT INTO m_farm_info (farm_cd, farm_nm, owner_nm, reg_dt) VALUES (?, ?, ?, ?)",
                (new_farm_cd, farm_name, owner_nm, now)
            )
            self.execute_query("""
                INSERT INTO m_user (user_id, user_pw, user_nm, farm_cd, role_cd, use_yn, reg_id, reg_dt, mod_id, mod_dt)
                VALUES (?, ?, ?, ?, 'ADMIN', 'Y', 'SYSTEM', ?, 'SYSTEM', ?)
            """, (admin_id, hashed_pw, owner_nm, new_farm_cd, now, now))
            return new_farm_cd
        except Exception as e:
            print(f"❌ 농장 등록 실패: {e}")
            return None

    def save_work_log(self, log_data, detail_list):
        cur = self.conn.cursor()
        try:
            cur.execute("""
                INSERT INTO t_work_log (farm_cd, owner_id, work_dt, site_id, weather_cd, temp_min, temp_max, work_rmk, reg_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, log_data)
            log_id = cur.lastrowid
            for detail in detail_list:
                cur.execute(f"""
                    INSERT INTO t_work_detail (log_id, pt_id, work_cd, man_power, unit_price, total_amt, reg_id)
                    VALUES ({log_id}, ?, ?, ?, ?, ?, ?)
                """, detail)
            self.conn.commit()
            return True
        except sqlite3.Error:
            self.conn.rollback()
            return False

    def save_work_details(self, work_dt, farm_cd, work_data_list, user_id):
        try:
            for i, row in enumerate(work_data_list):
                work_id = f"{work_dt.replace('-', '')}-{i+1:02d}"
                sql = """
                    REPLACE INTO t_work_detail (
                        work_id, work_dt, farm_cd, work_main_cd, work_mid_cd,
                        work_loc_id, start_tm, end_tm, status_cd,
                        reg_id, reg_dt, mod_id, mod_dt
                    ) VALUES (?, ?, ?, 'WK01', ?, ?, ?, ?, ?, ?, datetime('now','localtime'), ?, datetime('now','localtime'))
                """
                params = (work_id, work_dt, farm_cd, row['mid_cd'], row['loc_id'],
                          row['start_tm'], row['end_tm'], row['status'], user_id, user_id)
                self.execute_query(sql, params)
            return True
        except Exception as e:
            print(f"[DB] Work detail save error: {e}")
            return False

    def save_weather_data(self, farm_cd, work_dt, weather_data, user_id):
        try:
            params = (
                weather_data.get('day_of_week'),
                weather_data.get('weather_cd'),
                weather_data.get('temp_min'),
                weather_data.get('temp_max'),
                weather_data.get('precip'),
                weather_data.get('humidity'),
                weather_data.get('sun_rise'),
                weather_data.get('sun_set'),
                weather_data.get('sunshine_hr'),
                weather_data.get('wind_max'),
                weather_data.get('wind_min'),
                weather_data.get('work_rmk'),
                user_id,
                farm_cd,
                work_dt
            )
            sql = """
                INSERT INTO t_work_master (
                    day_of_week, weather_cd, temp_min, temp_max, precip, humidity,
                    sun_rise, sun_set, sunshine_hr, wind_max, wind_min,
                    work_rmk, reg_id, farm_cd, work_dt, reg_dt
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now','localtime'))
                ON CONFLICT(work_dt) DO UPDATE SET
                    day_of_week=excluded.day_of_week,
                    weather_cd=excluded.weather_cd, temp_min=excluded.temp_min,
                    temp_max=excluded.temp_max, precip=excluded.precip,
                    humidity=excluded.humidity, sun_rise=excluded.sun_rise,
                    sun_set=excluded.sun_set, sunshine_hr=excluded.sunshine_hr,
                    wind_max=excluded.wind_max, wind_min=excluded.wind_min,
                    work_rmk=excluded.work_rmk,
                    mod_id=excluded.reg_id, mod_dt=datetime('now','localtime')
            """
            self.execute_query(sql, params)
            return True
        except Exception as e:
            print(f"[DB] Weather save error: {e}")
            raise e

    def get_weather_info(self, farm_cd, work_dt):
        sql = "SELECT * FROM t_work_master WHERE farm_cd = ? AND work_dt = ?"
        return self.execute_query(sql, (farm_cd, work_dt))

    def get_work_details(self, farm_cd, work_dt):
        sql = "SELECT * FROM t_work_detail WHERE farm_cd = ? AND work_dt = ? ORDER BY work_id"
        return self.execute_query(sql, (farm_cd, work_dt))

    # 영농일지 상태 분류 상수 (저장 콤보 코드값은 변경하지 않음)
    WORK_LOG_STATUS_KIND_IN_PROGRESS = "in_progress"
    WORK_LOG_STATUS_KIND_DONE = "done"
    WORK_LOG_STATUS_KIND_CANCELLED = "cancelled"
    WORK_LOG_STATUS_KIND_OTHER = "other"

    @staticmethod
    def classify_work_log_status(status_cd, status_nm="") -> str:
        """
        영농일지 작업 상태 분류 헬퍼.
        - 공통코드 명칭(진행/완료/취소 등)을 우선하고, 없으면 WO01·ST01 코드 폴백.
        - UI paintCell이 아니라 월간 집계에서 한 번만 사용한다.
        """
        nm = str(status_nm or "").strip()
        cd = str(status_cd or "").strip().upper()
        if not nm and not cd:
            return DBManager.WORK_LOG_STATUS_KIND_OTHER

        if ("취소" in nm) or ("삭제" in nm):
            return DBManager.WORK_LOG_STATUS_KIND_CANCELLED
        if "진행" in nm:
            return DBManager.WORK_LOG_STATUS_KIND_IN_PROGRESS
        if "완료" in nm:
            return DBManager.WORK_LOG_STATUS_KIND_DONE

        # 명칭 없을 때 코드 폴백 (구 ST01 혼재 대응)
        if cd == "WO010200":
            return DBManager.WORK_LOG_STATUS_KIND_IN_PROGRESS
        if cd in ("WO010300", "ST010400"):
            return DBManager.WORK_LOG_STATUS_KIND_DONE
        if cd in ("WO010400", "ST010500"):
            return DBManager.WORK_LOG_STATUS_KIND_CANCELLED
        # 구데이터 ST010300(배송준비) 등 진행 유사 의미
        if cd == "ST010300":
            return DBManager.WORK_LOG_STATUS_KIND_IN_PROGRESS
        return DBManager.WORK_LOG_STATUS_KIND_OTHER

    def get_work_log_monthly_overview(self, farm_cd, year, month):
        """
        영농일지 월간정보용 집계.
        farm_cd + 해당 연월(work_dt)만 조회하여 일자별/월 요약 dict를 반환한다.
        DB 스키마 변경 없음. UI에서 일자별 반복 쿼리를 하지 않도록 월 단위로 한 번에 조회한다.
        """
        empty = {
            "year": int(year or 0),
            "month": int(month or 0),
            "summary": {
                "work_day_count": 0,
                "work_count": 0,
                "resource_count": 0,
                "labor_sum": 0.0,
                "expense_sum": 0.0,
            },
            "days": {},
        }
        fc = str(farm_cd or "").strip()
        try:
            y = int(year)
            m = int(month)
        except (TypeError, ValueError):
            return empty
        if not fc or y < 1 or m < 1 or m > 12:
            return empty

        start_key = f"{y:04d}{m:02d}01"
        if m == 12:
            end_key = f"{y + 1:04d}0101"
        else:
            end_key = f"{y:04d}{m + 1:02d}01"

        wk = self._work_detail_dt_key_sql("d.work_dt")
        mk = self._work_detail_dt_key_sql("m.work_dt")

        master_sql = f"""
            SELECT
                m.work_dt,
                m.weather_cd,
                COALESCE(w.code_nm, '') AS weather_nm,
                COALESCE(m.work_rmk, '') AS work_rmk
            FROM t_work_master m
            LEFT JOIN m_common_code w
              ON w.farm_cd = m.farm_cd AND w.code_cd = m.weather_cd
            WHERE m.farm_cd = ?
              AND ({mk}) >= ?
              AND ({mk}) < ?
        """
        detail_sql = f"""
            SELECT
                d.work_id,
                d.work_dt,
                d.work_mid_cd,
                d.status_cd,
                COALESCE(st.code_nm, '') AS status_nm,
                COALESCE(NULLIF(TRIM(mid.code_nm), ''), TRIM(d.work_mid_cd), '-') AS work_mid_nm,
                COALESCE(lab.labor_sum, 0) AS labor_sum,
                COALESCE(exp.expense_sum, 0) AS expense_sum,
                COALESCE(rc.resource_count, 0) AS resource_count
            FROM t_work_detail d
            LEFT JOIN m_common_code mid
              ON mid.farm_cd = d.farm_cd AND mid.code_cd = d.work_mid_cd
            LEFT JOIN m_common_code st
              ON st.farm_cd = d.farm_cd AND st.code_cd = d.status_cd
            LEFT JOIN (
                SELECT
                    r.work_id,
                    r.farm_cd,
                    SUM(COALESCE(r.daily_wage, 0)) AS labor_sum
                FROM t_work_resource r
                LEFT JOIN m_partner p
                  ON p.farm_cd = r.farm_cd
                 AND TRIM(CAST(p.pt_id AS TEXT)) = TRIM(CAST(r.emp_cd AS TEXT))
                WHERE {self._partner_in_labor_total_sql("p")}
                GROUP BY r.work_id, r.farm_cd
            ) lab ON lab.work_id = d.work_id AND lab.farm_cd = d.farm_cd
            LEFT JOIN (
                SELECT work_id, farm_cd, COUNT(res_id) AS resource_count
                FROM t_work_resource
                GROUP BY work_id, farm_cd
            ) rc ON rc.work_id = d.work_id AND rc.farm_cd = d.farm_cd
            LEFT JOIN (
                SELECT work_id, farm_cd, SUM(COALESCE(total_amt, 0)) AS expense_sum
                FROM t_work_expense
                GROUP BY work_id, farm_cd
            ) exp ON exp.work_id = d.work_id AND exp.farm_cd = d.farm_cd
            WHERE d.farm_cd = ?
              AND ({wk}) >= ?
              AND ({wk}) < ?
            ORDER BY ({wk}) ASC, d.work_id ASC
        """

        def _row_dict(row):
            if row is None:
                return {}
            if hasattr(row, "keys"):
                return {k: row[k] for k in row.keys()}
            return {}

        def _norm_dt(raw):
            s = str(raw or "").strip()
            if len(s) >= 10 and s[4] == "-":
                return s[:10]
            digits = "".join(ch for ch in s if ch.isdigit())
            if len(digits) >= 8:
                return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"
            return s

        days = {}
        try:
            masters = self.execute_query(master_sql, (fc, start_key, end_key)) or []
            details = self.execute_query(detail_sql, (fc, start_key, end_key)) or []
        except Exception as e:
            print(f"[DB] get_work_log_monthly_overview: {e}")
            return empty

        for row in masters:
            rd = _row_dict(row)
            if not rd and isinstance(row, (tuple, list)) and len(row) >= 4:
                rd = {
                    "work_dt": row[0],
                    "weather_cd": row[1],
                    "weather_nm": row[2],
                    "work_rmk": row[3],
                }
            dt = _norm_dt(rd.get("work_dt"))
            if not dt:
                continue
            rmk = str(rd.get("work_rmk") or "").strip()
            days[dt] = {
                "work_dt": dt,
                "weather_cd": rd.get("weather_cd") or "",
                "weather_nm": str(rd.get("weather_nm") or "").strip() or "-",
                "work_rmk": rmk,
                "has_issue": bool(rmk),
                "work_names": [],
                "work_count": 0,
                "extra_work_count": 0,
                "resource_count": 0,
                "labor_sum": 0.0,
                "expense_sum": 0.0,
                "total_cost": 0.0,
                "has_work": False,
                "has_in_progress": False,
            }

        for row in details:
            rd = _row_dict(row)
            if not rd and isinstance(row, (tuple, list)) and len(row) >= 9:
                rd = {
                    "work_id": row[0],
                    "work_dt": row[1],
                    "work_mid_cd": row[2],
                    "status_cd": row[3],
                    "status_nm": row[4],
                    "work_mid_nm": row[5],
                    "labor_sum": row[6],
                    "expense_sum": row[7],
                    "resource_count": row[8],
                }
            dt = _norm_dt(rd.get("work_dt"))
            if not dt:
                continue
            cell = days.get(dt)
            if cell is None:
                cell = {
                    "work_dt": dt,
                    "weather_cd": "",
                    "weather_nm": "-",
                    "work_rmk": "",
                    "has_issue": False,
                    "work_names": [],
                    "work_count": 0,
                    "extra_work_count": 0,
                    "resource_count": 0,
                    "labor_sum": 0.0,
                    "expense_sum": 0.0,
                    "total_cost": 0.0,
                    "has_work": False,
                    "has_in_progress": False,
                }
                days[dt] = cell

            status_kind = self.classify_work_log_status(
                rd.get("status_cd"), rd.get("status_nm")
            )

            cell["has_work"] = True
            cell["work_count"] = int(cell["work_count"] or 0) + 1
            nm = str(rd.get("work_mid_nm") or "").strip() or "-"
            if nm not in cell["work_names"]:
                cell["work_names"].append(nm)
            try:
                cell["labor_sum"] = float(cell["labor_sum"] or 0) + float(rd.get("labor_sum") or 0)
            except (TypeError, ValueError):
                pass
            try:
                cell["expense_sum"] = float(cell["expense_sum"] or 0) + float(rd.get("expense_sum") or 0)
            except (TypeError, ValueError):
                pass
            try:
                cell["resource_count"] = int(cell["resource_count"] or 0) + int(rd.get("resource_count") or 0)
            except (TypeError, ValueError):
                pass
            # 취소·삭제는 진행 중에서만 제외 (완료·기타는 작업 있음)
            if status_kind == self.WORK_LOG_STATUS_KIND_IN_PROGRESS:
                cell["has_in_progress"] = True

        work_day_count = 0
        work_count = 0
        resource_count = 0
        labor_sum = 0.0
        expense_sum = 0.0
        for cell in days.values():
            names = cell.get("work_names") or []
            if len(names) > 2:
                cell["extra_work_count"] = len(names) - 2
                cell["work_names"] = names[:2]
            else:
                cell["extra_work_count"] = 0
            cell["total_cost"] = float(cell.get("labor_sum") or 0) + float(cell.get("expense_sum") or 0)
            if cell.get("has_work"):
                work_day_count += 1
                work_count += int(cell.get("work_count") or 0)
                resource_count += int(cell.get("resource_count") or 0)
                labor_sum += float(cell.get("labor_sum") or 0)
                expense_sum += float(cell.get("expense_sum") or 0)

        # 관찰 Stage2: 일자 셀에 관찰 뱃지 필드 병합
        _obs_defaults = {
            "observation_count": 0,
            "observation_max_severity": "",
            "has_observation": False,
            "has_observation_warning": False,
            "followup_due_count": 0,
            "followup_overdue_count": 0,
        }
        for cell in days.values():
            for k, v in _obs_defaults.items():
                cell.setdefault(k, v)
        try:
            from core.observation_stage2 import get_observation_monthly_day_map
            obs_map = get_observation_monthly_day_map(self, fc, y, m) or {}
        except Exception as e:
            print(f"[DB] merge observation monthly day map: {e}")
            obs_map = {}
        for dt, obs_cell in obs_map.items():
            cell = days.get(dt)
            if cell is None:
                cell = {
                    "work_dt": dt,
                    "weather_cd": "",
                    "weather_nm": "-",
                    "work_rmk": "",
                    "has_issue": False,
                    "work_names": [],
                    "work_count": 0,
                    "extra_work_count": 0,
                    "resource_count": 0,
                    "labor_sum": 0.0,
                    "expense_sum": 0.0,
                    "total_cost": 0.0,
                    "has_work": False,
                    "has_in_progress": False,
                    **_obs_defaults,
                }
                days[dt] = cell
            cell["observation_count"] = int(obs_cell.get("observation_count") or 0)
            cell["observation_max_severity"] = str(
                obs_cell.get("observation_max_severity") or ""
            )
            cell["has_observation"] = bool(obs_cell.get("has_observation"))
            cell["has_observation_warning"] = bool(
                obs_cell.get("has_observation_warning")
            )
            cell["followup_due_count"] = int(obs_cell.get("followup_due_count") or 0)
            cell["followup_overdue_count"] = int(
                obs_cell.get("followup_overdue_count") or 0
            )

        return {
            "year": y,
            "month": m,
            "summary": {
                "work_day_count": work_day_count,
                "work_count": work_count,
                "resource_count": resource_count,
                "labor_sum": labor_sum,
                "expense_sum": expense_sum,
            },
            "days": days,
        }

    def close(self):
        if self.conn:
            self.conn.close()

    def save_work_resources(self, work_id, res_data_list):
        try:
            self.execute_query("DELETE FROM t_work_resource WHERE work_id = ?", (work_id,))
            for res in res_data_list:
                sql = """
                    INSERT INTO t_work_resource (
                        res_id, work_id, farm_cd, emp_cd, man_hour,
                        daily_wage, meal_cost, other_cost, pay_method_cd,
                        pay_status, reg_id, reg_dt
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now','localtime'))
                """
                params = (
                    res['res_id'], res['work_id'], res['farm_cd'], res['emp_cd'], res['man_hour'],
                    res['daily_wage'], res['meal_cost'], res['other_cost'], res['pay_method_cd'],
                    res['pay_status'], res['reg_id']
                )
                self.execute_query(sql, params)
            return True
        except Exception as e:
            print(f"[DB] Resource save failed: {e}")
            return False

    def add_new_partner(self, farm_cd, pt_nm):
        try:
            sql = (
                "INSERT INTO m_partner (farm_cd, pt_nm, reg_dt, worker_type_cd) "
                "VALUES (?, ?, datetime('now','localtime'), 'EMP')"
            )
            self.execute_query(sql, (farm_cd, pt_nm))
            return True
        except Exception as e:
            print(f"❌ 신규 직원 등록 실패: {e}")
            return False

    def add_new_partner_extended(self, farm_cd, data, user_id):
        """신규 m_partner. 성공 시 pt_id(lastrowid), 실패 시 None."""
        wtc = str(data.get("worker_type_cd") or "EMP").strip().upper() or "EMP"
        if wtc not in DBManager.PARTNER_WORKER_TYPES_IN_LABOR_TOTAL + ("OWNER", "FAMILY"):
            wtc = "EMP"
        uy = str(data.get("use_yn") or "Y").strip().upper()[:1] or "Y"
        if uy not in ("Y", "N"):
            uy = "Y"
        sql = """
            INSERT INTO m_partner (
                farm_cd, pt_nm, pt_tel, base_price, bank_cd, account_no, use_yn, worker_type_cd, reg_id, reg_dt
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now','localtime'))
        """
        params = (
            farm_cd,
            data.get("pt_nm") or "",
            data.get("pt_tel") or "",
            data.get("base_price") or 0,
            data.get("bank_cd"),
            data.get("account_no") or "",
            uy,
            wtc,
            user_id,
        )
        try:
            cur = self.conn.cursor()
            cur.execute(sql, params)
            self.conn.commit()
            return int(cur.lastrowid) if cur.lastrowid else None
        except sqlite3.Error as e:
            print(f"[DB] add_new_partner_extended: {e}")
            if self.conn:
                try:
                    self.conn.rollback()
                except sqlite3.Error:
                    pass
            return None

    def fetch_all(self, query, params=()):
        try:
            self.conn.row_factory = sqlite3.Row
            cursor = self.conn.cursor()
            cursor.execute(query, params)
            return cursor.fetchall()
        except sqlite3.Error as e:
            print(f"[DB] Fetch error: {e}")
            return []

    def save_work_res_data(self, data_list):
        query = """
            INSERT INTO t_work_resource (
                res_id, work_id, farm_cd, trans_dt, emp_cd,
                man_hour, daily_wage, meal_cost, other_cost,
                pay_method_cd, pay_status, reg_id, slip_no, reg_dt
            ) VALUES (
                :res_id, :work_id, :farm_cd, :trans_dt, :emp_cd,
                :man_hour, :daily_wage, :meal_cost, :other_cost,
                :pay_method_cd, :pay_status, :reg_id, :slip_no, datetime('now','localtime')
            )
            ON CONFLICT(res_id) DO UPDATE SET
                work_id = excluded.work_id, farm_cd = excluded.farm_cd, trans_dt = excluded.trans_dt,
                emp_cd = excluded.emp_cd, man_hour = excluded.man_hour, daily_wage = excluded.daily_wage,
                meal_cost = excluded.meal_cost, other_cost = excluded.other_cost,
                pay_method_cd = excluded.pay_method_cd, pay_status = excluded.pay_status,
                reg_id = excluded.reg_id, slip_no = excluded.slip_no,
                mod_dt = datetime('now','localtime')
        """
        refined_list = []
        for d in data_list:
            rid = d.get('res_id')
            if rid is None or str(rid).strip().upper() == 'NEW':
                d['res_id'] = None
            d['meal_cost'] = d.get('meal_cost', 0)
            d['other_cost'] = d.get('other_cost', 0)
            d['slip_no'] = d.get('slip_no', None)
            refined_list.append(d)
        try:
            for d in refined_list:
                self.execute_query(query, d)
            return True
        except Exception as e:
            print(f"[DB] Resource UPSERT error: {e}")
            return False

    def save_work_expense_data(self, data_list):
        query = """
            INSERT INTO t_work_expense (
                exp_id, work_id, farm_cd, trans_dt, acct_cd, item_nm,
                qty, unit_price, total_amt, pay_method_cd, pay_status, reg_id, slip_no, reg_dt
            ) VALUES (
                :exp_id, :work_id, :farm_cd, :trans_dt, :acct_cd, :item_nm,
                :qty, :unit_price, :total_amt, :pay_method_cd, :pay_status, :reg_id, :slip_no, datetime('now','localtime')
            )
            ON CONFLICT(exp_id) DO UPDATE SET
                trans_dt = excluded.trans_dt,
                acct_cd = excluded.acct_cd, item_nm = excluded.item_nm,
                qty = excluded.qty, unit_price = excluded.unit_price, total_amt = excluded.total_amt,
                pay_method_cd = excluded.pay_method_cd, pay_status = excluded.pay_status,
                slip_no = excluded.slip_no, mod_dt = datetime('now','localtime')
        """
        try:
            for d in data_list:
                eid = d.get('exp_id')
                if eid is None or str(eid).strip().upper() == 'NEW':
                    d['exp_id'] = None
                d['slip_no'] = d.get('slip_no', None)
                self.execute_query(query, d)
            return True
        except Exception as e:
            print(f"[DB] Expense UPSERT error: {e}")
            return False

    def get_work_resources(self, work_id):
        sql = """
            SELECT res_id, work_id, emp_cd, man_hour, daily_wage, pay_method_cd, pay_status
            FROM t_work_resource WHERE work_id = ?
        """
        return self.fetch_all(sql, (work_id,))

    def get_work_expenses(self, work_id):
        sql = """
            SELECT exp_id, work_id, farm_cd, trans_dt, acct_cd, item_nm, qty, unit_price, total_amt,
                   pay_method_cd, pay_status
            FROM t_work_expense WHERE work_id = ?
            ORDER BY exp_id
        """
        return self.fetch_all(sql, (work_id,))

    @staticmethod
    def _work_detail_dt_key_sql(alias="d.work_dt"):
        """t_work_detail.work_dt → YYYYMMDD (형식 혼재 대응)."""
        a = alias
        return f"""
            CASE
                WHEN length(COALESCE(trim({a}), '')) >= 10 AND instr(COALESCE(trim({a}), ''), '-') = 5
                    THEN replace(substr(COALESCE(trim({a}), ''), 1, 10), '-', '')
                WHEN length(COALESCE(trim({a}), '')) >= 8
                    THEN substr(COALESCE(trim({a}), ''), 1, 8)
                ELSE ''
            END
        """

    def get_work_resource_detail(self, work_id):
        """작업별 인건비 라인 + 작업자명(m_partner.pt_nm, emp_cd=pt_id)."""
        sql = """
            SELECT
                r.res_id, r.work_id, r.emp_cd, r.man_hour, r.daily_wage,
                r.pay_method_cd, r.pay_status,
                COALESCE(NULLIF(TRIM(p.pt_nm), ''), TRIM(CAST(r.emp_cd AS TEXT)), '') AS emp_nm,
                COALESCE(NULLIF(TRIM(p.worker_type_cd), ''), 'EMP') AS worker_type_cd
            FROM t_work_resource r
            LEFT JOIN m_partner p
              ON p.farm_cd = r.farm_cd
             AND TRIM(CAST(p.pt_id AS TEXT)) = TRIM(CAST(r.emp_cd AS TEXT))
            WHERE r.work_id = ?
            ORDER BY r.res_id
        """
        return self.fetch_all(sql, (work_id,))

    def get_work_expense_detail(self, work_id):
        """작업별 경비 라인 (기존 get_work_expenses와 동일)."""
        return self.get_work_expenses(work_id)

    def get_cost_detail_by_work(
        self,
        farm_cd,
        start_dt,
        end_dt,
        work_loc_id=None,
        work_mid_cd=None,
    ):
        """
        작업(work_dt) 기준 비용 요약: work_id 단위 인건비·경비 합계.
        start_dt, end_dt: YYYY-MM-DD (work_dt 정규화 키 구간 필터).
        """
        fc = str(farm_cd or "").strip()
        if not fc:
            return []
        sk = str(start_dt or "").replace("-", "").strip()[:8]
        ek = str(end_dt or "").replace("-", "").strip()[:8]
        if len(sk) < 8 or len(ek) < 8:
            return []

        wk = self._work_detail_dt_key_sql("d.work_dt")
        wh = [f"d.farm_cd = ?", f"({wk}) BETWEEN ? AND ?"]
        params = [fc, sk, ek]
        if work_loc_id is not None and str(work_loc_id).strip() != "":
            wh.append("TRIM(CAST(d.work_loc_id AS TEXT)) = ?")
            params.append(str(work_loc_id).strip())
        if work_mid_cd is not None and str(work_mid_cd).strip() != "":
            wh.append("d.work_mid_cd = ?")
            params.append(str(work_mid_cd).strip())

        where_sql = " AND ".join(wh)
        sql = f"""
            SELECT
                d.work_id,
                d.work_dt,
                d.work_mid_cd,
                d.work_loc_id,
                COALESCE(mid.code_nm, d.work_mid_cd, '') AS work_mid_nm,
                COALESCE(fs.site_nm, TRIM(CAST(d.work_loc_id AS TEXT)), '') AS site_nm,
                COALESCE(lab.labor_sum, 0) AS labor_sum,
                COALESCE(exp.expense_sum, 0) AS expense_sum
            FROM t_work_detail d
            LEFT JOIN m_common_code mid
              ON mid.farm_cd = d.farm_cd AND mid.code_cd = d.work_mid_cd
            LEFT JOIN m_farm_site fs
              ON fs.farm_cd = d.farm_cd
             AND TRIM(CAST(fs.site_id AS TEXT)) = TRIM(CAST(d.work_loc_id AS TEXT))
            LEFT JOIN (
                SELECT r.work_id, r.farm_cd, SUM(COALESCE(r.daily_wage, 0)) AS labor_sum
                FROM t_work_resource r
                LEFT JOIN m_partner p
                  ON p.farm_cd = r.farm_cd
                 AND TRIM(CAST(p.pt_id AS TEXT)) = TRIM(CAST(r.emp_cd AS TEXT))
                WHERE {self._partner_in_labor_total_sql("p")}
                GROUP BY r.work_id, r.farm_cd
            ) lab ON lab.work_id = d.work_id AND lab.farm_cd = d.farm_cd
            LEFT JOIN (
                SELECT work_id, farm_cd, SUM(COALESCE(total_amt, 0)) AS expense_sum
                FROM t_work_expense
                GROUP BY work_id, farm_cd
            ) exp ON exp.work_id = d.work_id AND exp.farm_cd = d.farm_cd
            WHERE {where_sql}
            ORDER BY ({wk}) DESC, d.work_id DESC
        """
        rows = self.execute_query(sql, tuple(params))
        out = []
        for r in rows or []:
            if hasattr(r, "keys"):
                out.append({k: r[k] for k in r.keys()})
            else:
                out.append(
                    {
                        "work_id": r[0],
                        "work_dt": r[1],
                        "work_mid_cd": r[2],
                        "work_loc_id": r[3],
                        "work_mid_nm": r[4],
                        "site_nm": r[5],
                        "labor_sum": r[6],
                        "expense_sum": r[7],
                    }
                )
        return out

    def get_cost_unpaid_list(
        self,
        farm_cd,
        start_dt,
        end_dt,
        limit=300,
        work_loc_id=None,
        work_mid_cd=None,
    ):
        """미지급 인건비·경비 목록 (작업일 work_dt 구간, 작업장소·작업종류 필터 선택)."""
        fc = str(farm_cd or "").strip()
        if not fc:
            return []
        sk = str(start_dt or "").replace("-", "").strip()[:8]
        ek = str(end_dt or "").replace("-", "").strip()[:8]
        if len(sk) < 8 or len(ek) < 8:
            return []
        wk = self._work_detail_dt_key_sql("d.work_dt")
        extra = ""
        extra_params = []
        if work_loc_id is not None and str(work_loc_id).strip() != "":
            extra += " AND TRIM(CAST(d.work_loc_id AS TEXT)) = ?"
            extra_params.append(str(work_loc_id).strip())
        if work_mid_cd is not None and str(work_mid_cd).strip() != "":
            extra += " AND d.work_mid_cd = ?"
            extra_params.append(str(work_mid_cd).strip())

        sql = f"""
            SELECT kind, work_id, amt, work_dt, descr FROM (
                SELECT
                    '인건비' AS kind,
                    r.work_id AS work_id,
                    COALESCE(r.daily_wage, 0) AS amt,
                    d.work_dt AS work_dt,
                    COALESCE(
                        NULLIF(TRIM(p.pt_nm), ''),
                        TRIM(CAST(r.emp_cd AS TEXT)),
                        ''
                    ) AS descr
                FROM t_work_resource r
                INNER JOIN t_work_detail d
                  ON d.work_id = r.work_id AND d.farm_cd = r.farm_cd
                LEFT JOIN m_partner p
                  ON p.farm_cd = r.farm_cd
                 AND TRIM(CAST(p.pt_id AS TEXT)) = TRIM(CAST(r.emp_cd AS TEXT))
                WHERE r.farm_cd = ?
                  AND upper(ifnull(trim(r.pay_status), 'N')) <> 'Y'
                  AND ({wk}) BETWEEN ? AND ?{extra}
                  AND {self._partner_in_labor_total_sql("p")}

                UNION ALL

                SELECT
                    '경비' AS kind,
                    e.work_id AS work_id,
                    COALESCE(e.total_amt, 0) AS amt,
                    d.work_dt AS work_dt,
                    COALESCE(e.item_nm, '') AS descr
                FROM t_work_expense e
                INNER JOIN t_work_detail d
                  ON d.work_id = e.work_id AND d.farm_cd = e.farm_cd
                WHERE e.farm_cd = ?
                  AND upper(ifnull(trim(e.pay_status), 'N')) <> 'Y'
                  AND ({wk}) BETWEEN ? AND ?{extra}
            )
            ORDER BY work_dt DESC, kind
            LIMIT ?
        """
        params = (fc, sk, ek, *extra_params, fc, sk, ek, *extra_params, int(limit))
        rows = self.execute_query(sql, params)
        out = []
        for r in rows or []:
            if hasattr(r, "keys"):
                out.append({k: r[k] for k in r.keys()})
            else:
                out.append({"kind": r[0], "work_id": r[1], "amt": r[2], "work_dt": r[3], "descr": r[4]})
        return out

    def get_dashboard_cost_summary(self, farm_cd, today_ymd=None):
        """대시보드 비용 현황 카드 요약(인건비/경비 통합)."""
        out = {
            "today_total": 0,
            "month_total": 0,
            "unpaid_total_count": 0,
            "unpaid_total_amount": 0,
            "labor_today": 0,
            "labor_month": 0,
            "labor_unpaid_count": 0,
            "labor_unpaid_amount": 0,
            "expense_today": 0,
            "expense_month": 0,
            "expense_unpaid_count": 0,
            "expense_unpaid_amount": 0,
        }
        fc = str(farm_cd or "").strip()
        if not fc:
            return out

        base_day = str(today_ymd or today_ops().isoformat()).strip()
        day_key = base_day.replace("-", "")
        month_key = f"{day_key[:6]}01" if len(day_key) >= 8 else ""

        # 인건비 집계일: 전표/입력일(trans_dt)가 아닌 실제 작업일(t_work_detail.work_dt)만 사용.
        # work_dt가 YYYY-MM-DD / YYYYMMDD 혼재 시 YYYYMMDD로 정규화.
        labor_dt_key_sql = """
            CASE
                WHEN length(COALESCE(trim(d.work_dt), '')) >= 10
                     AND instr(COALESCE(trim(d.work_dt), ''), '-') = 5
                    THEN replace(substr(COALESCE(trim(d.work_dt), ''), 1, 10), '-', '')
                WHEN length(COALESCE(trim(d.work_dt), '')) >= 8
                    THEN substr(COALESCE(trim(d.work_dt), ''), 1, 8)
                ELSE ''
            END
        """
        expense_dt_key_sql = """
            CASE
                WHEN length(COALESCE(trim(e.trans_dt), '')) >= 10 AND instr(COALESCE(trim(e.trans_dt), ''), '-') = 5
                    THEN replace(substr(COALESCE(trim(e.trans_dt), ''), 1, 10), '-', '')
                WHEN length(COALESCE(trim(e.trans_dt), '')) >= 8
                    THEN substr(COALESCE(trim(e.trans_dt), ''), 1, 8)
                ELSE ''
            END
        """
        unpaid_sql = "upper(ifnull(trim({col}), 'N')) <> 'Y'"

        try:
            labor_row = self.execute_query(
                f"""
                SELECT
                    COALESCE(SUM(CASE WHEN {labor_dt_key_sql} = ? THEN COALESCE(r.daily_wage, 0) ELSE 0 END), 0) AS today_amt,
                    COALESCE(SUM(CASE WHEN {labor_dt_key_sql} BETWEEN ? AND ? THEN COALESCE(r.daily_wage, 0) ELSE 0 END), 0) AS month_amt,
                    COALESCE(SUM(CASE WHEN {unpaid_sql.format(col='r.pay_status')} THEN 1 ELSE 0 END), 0) AS unpaid_cnt,
                    COALESCE(SUM(CASE WHEN {unpaid_sql.format(col='r.pay_status')} THEN COALESCE(r.daily_wage, 0) ELSE 0 END), 0) AS unpaid_amt
                FROM t_work_resource r
                LEFT JOIN t_work_detail d
                  ON d.work_id = r.work_id
                 AND d.farm_cd = r.farm_cd
                LEFT JOIN m_partner p
                  ON p.farm_cd = r.farm_cd
                 AND TRIM(CAST(p.pt_id AS TEXT)) = TRIM(CAST(r.emp_cd AS TEXT))
                WHERE r.farm_cd = ?
                  AND {self._partner_in_labor_total_sql("p")}
                """,
                (day_key, month_key, day_key, fc),
            )
            expense_row = self.execute_query(
                f"""
                SELECT
                    COALESCE(SUM(CASE WHEN {expense_dt_key_sql} = ? THEN COALESCE(e.total_amt, 0) ELSE 0 END), 0) AS today_amt,
                    COALESCE(SUM(CASE WHEN {expense_dt_key_sql} BETWEEN ? AND ? THEN COALESCE(e.total_amt, 0) ELSE 0 END), 0) AS month_amt,
                    COALESCE(SUM(CASE WHEN {unpaid_sql.format(col='e.pay_status')} THEN 1 ELSE 0 END), 0) AS unpaid_cnt,
                    COALESCE(SUM(CASE WHEN {unpaid_sql.format(col='e.pay_status')} THEN COALESCE(e.total_amt, 0) ELSE 0 END), 0) AS unpaid_amt
                FROM t_work_expense e
                WHERE e.farm_cd = ?
                """,
                (day_key, month_key, day_key, fc),
            )
            l = dict(labor_row[0]) if labor_row else {}
            e = dict(expense_row[0]) if expense_row else {}

            labor_today = int(float(l.get("today_amt") or 0))
            expense_today = int(float(e.get("today_amt") or 0))
            labor_month = int(float(l.get("month_amt") or 0))
            expense_month = int(float(e.get("month_amt") or 0))
            labor_unpaid_cnt = int(float(l.get("unpaid_cnt") or 0))
            expense_unpaid_cnt = int(float(e.get("unpaid_cnt") or 0))
            labor_unpaid_amt = int(float(l.get("unpaid_amt") or 0))
            expense_unpaid_amt = int(float(e.get("unpaid_amt") or 0))

            out.update(
                {
                    "today_total": labor_today + expense_today,
                    "month_total": labor_month + expense_month,
                    "unpaid_total_count": labor_unpaid_cnt + expense_unpaid_cnt,
                    "unpaid_total_amount": labor_unpaid_amt + expense_unpaid_amt,
                    "labor_today": labor_today,
                    "labor_month": labor_month,
                    "labor_unpaid_count": labor_unpaid_cnt,
                    "labor_unpaid_amount": labor_unpaid_amt,
                    "expense_today": expense_today,
                    "expense_month": expense_month,
                    "expense_unpaid_count": expense_unpaid_cnt,
                    "expense_unpaid_amount": expense_unpaid_amt,
                }
            )
            return out
        except Exception as e:
            print(f"[DB] get_dashboard_cost_summary failed: {e}")
            return out

    def get_ledger_by_ref(self, ref_id):
        query = "SELECT slip_no, acc_amt, cash_amt FROM t_ledger WHERE ref_id = ?"
        result_list = self.execute_query(query, (ref_id,))
        if result_list and len(result_list) > 0:
            return dict(result_list[0])
        return None

    # --- 인력관리 (m_partner + t_work_resource) ---

    def list_workforce_partners(self, farm_cd, name_q=None, use_yn_y_only=False):
        """인력 목록: 이름·구분·연락처·기본단가·사용여부.

        use_yn_y_only: True면 사용여부 Y(또는 NULL을 Y로 간주)인 행만 표시.
        """
        fc = str(farm_cd or "").strip()
        if not fc:
            return []
        wh = ["mp.farm_cd = ?"]
        params = [fc]
        nq = (name_q or "").strip()
        if nq:
            wh.append("mp.pt_nm LIKE ?")
            params.append(f"%{nq}%")
        if use_yn_y_only:
            wh.append("IFNULL(mp.use_yn, 'Y') = 'Y'")
        sql = f"""
            SELECT mp.pt_id, mp.pt_nm, COALESCE(NULLIF(TRIM(mp.worker_type_cd), ''), 'EMP') AS worker_type_cd,
                   mp.pt_tel, mp.base_price,
                   COALESCE(mp.bank_cd, '') AS bank_cd,
                   COALESCE(mp.account_no, '') AS account_no,
                   IFNULL(mp.use_yn, 'Y') AS use_yn
            FROM m_partner mp
            WHERE {" AND ".join(wh)}
            ORDER BY mp.pt_nm COLLATE NOCASE, mp.pt_id
        """
        rows = self.execute_query(sql, tuple(params)) or []
        out = []
        for r in rows:
            out.append(dict(r) if hasattr(r, "keys") else {})
        return out

    def update_workforce_partner(
        self,
        farm_cd,
        pt_id,
        pt_nm,
        worker_type_cd,
        pt_tel,
        base_price,
        use_yn,
        bank_cd=None,
        account_no=None,
    ):
        """인력 마스터 수정."""
        fc = str(farm_cd or "").strip()
        if not fc or pt_id is None:
            return False
        wtc = str(worker_type_cd or "EMP").strip().upper() or "EMP"
        allowed = set(DBManager.PARTNER_WORKER_TYPES_IN_LABOR_TOTAL + ("OWNER", "FAMILY"))
        if wtc not in allowed:
            wtc = "EMP"
        uy = str(use_yn or "Y").strip().upper()[:1] or "Y"
        if uy not in ("Y", "N"):
            uy = "Y"
        try:
            pid = int(pt_id)
        except (TypeError, ValueError):
            return False
        bnk = str(bank_cd or "").strip() or None
        acc = str(account_no or "").strip()
        sql = """
            UPDATE m_partner
            SET pt_nm = ?, worker_type_cd = ?, pt_tel = ?, base_price = ?, use_yn = ?,
                bank_cd = ?, account_no = ?
            WHERE pt_id = ? AND farm_cd = ?
        """
        params = (
            str(pt_nm or "").strip(),
            wtc,
            str(pt_tel or "").strip(),
            float(base_price or 0),
            uy,
            bnk,
            acc,
            pid,
            fc,
        )
        try:
            cur = self.conn.cursor()
            cur.execute(sql, params)
            self.conn.commit()
            return cur.rowcount > 0
        except sqlite3.Error as e:
            print(f"[DB] update_workforce_partner: {e}")
            if self.conn:
                try:
                    self.conn.rollback()
                except sqlite3.Error:
                    pass
            return False

    def list_workforce_work_names_in_period(self, farm_cd, start_yyyymmdd, end_yyyymmdd):
        """기간 내 투입이 있는 작업명(공통코드명·코드) 목록, 필터 콤보용."""
        fc = str(farm_cd or "").strip()
        sk = str(start_yyyymmdd or "").replace("-", "")[:8]
        ek = str(end_yyyymmdd or "").replace("-", "")[:8]
        if not fc or len(sk) < 8 or len(ek) < 8:
            return []
        wk = self._work_detail_dt_key_sql("d.work_dt")
        sql = f"""
            SELECT DISTINCT TRIM(COALESCE(mid.code_nm, d.work_mid_cd, '')) AS work_mid_nm
            FROM t_work_resource r
            INNER JOIN t_work_detail d
              ON d.work_id = r.work_id AND d.farm_cd = r.farm_cd
            LEFT JOIN m_common_code mid
              ON mid.farm_cd = d.farm_cd AND mid.code_cd = d.work_mid_cd
            WHERE r.farm_cd = ?
              AND ({wk}) BETWEEN ? AND ?
              AND TRIM(COALESCE(mid.code_nm, d.work_mid_cd, '')) != ''
            ORDER BY work_mid_nm COLLATE NOCASE
        """
        rows = self.execute_query(sql, (fc, sk, ek)) or []
        out = []
        for r in rows:
            row = dict(r) if hasattr(r, "keys") else {}
            nm = str(row.get("work_mid_nm") or "").strip()
            if nm:
                out.append(nm)
        return out

    def list_workforce_assignments(
        self, farm_cd, start_yyyymmdd, end_yyyymmdd, emp_pt_id=None, work_mid_nm=None
    ):
        """
        투입 이력: t_work_resource + t_work_detail (작업명·작업일·작업자·투입MH·장소·일당·지급).
        start_yyyymmdd, end_yyyymmdd: YYYYMMDD 8자리.
        """
        fc = str(farm_cd or "").strip()
        sk = str(start_yyyymmdd or "").replace("-", "")[:8]
        ek = str(end_yyyymmdd or "").replace("-", "")[:8]
        if not fc or len(sk) < 8 or len(ek) < 8:
            return []
        wk = self._work_detail_dt_key_sql("d.work_dt")
        wh = [f"r.farm_cd = ?", f"({wk}) BETWEEN ? AND ?"]
        params = [fc, sk, ek]
        if emp_pt_id is not None and str(emp_pt_id).strip() != "":
            wh.append("TRIM(CAST(r.emp_cd AS TEXT)) = ?")
            params.append(str(emp_pt_id).strip())
        wmn = (work_mid_nm or "").strip()
        if wmn:
            wh.append("TRIM(COALESCE(mid.code_nm, d.work_mid_cd, '')) = ?")
            params.append(wmn)
        sql = f"""
            SELECT
                d.work_dt,
                COALESCE(mid.code_nm, d.work_mid_cd, '') AS work_mid_nm,
                COALESCE(fs.site_nm, TRIM(CAST(d.work_loc_id AS TEXT)), '') AS site_nm,
                COALESCE(r.man_hour, 0) AS man_hour,
                COALESCE(r.daily_wage, 0) AS daily_wage,
                r.pay_status,
                COALESCE(NULLIF(TRIM(p.pt_nm), ''), TRIM(CAST(r.emp_cd AS TEXT)), '') AS pt_nm,
                r.res_id,
                d.work_id,
                COALESCE(NULLIF(TRIM(p.worker_type_cd), ''), 'EMP') AS worker_type_cd
            FROM t_work_resource r
            INNER JOIN t_work_detail d
              ON d.work_id = r.work_id AND d.farm_cd = r.farm_cd
            LEFT JOIN m_common_code mid
              ON mid.farm_cd = d.farm_cd AND mid.code_cd = d.work_mid_cd
            LEFT JOIN m_farm_site fs
              ON fs.farm_cd = d.farm_cd
             AND TRIM(CAST(fs.site_id AS TEXT)) = TRIM(CAST(d.work_loc_id AS TEXT))
            LEFT JOIN m_partner p
              ON p.farm_cd = r.farm_cd
             AND TRIM(CAST(p.pt_id AS TEXT)) = TRIM(CAST(r.emp_cd AS TEXT))
            WHERE {" AND ".join(wh)}
            ORDER BY TRIM(COALESCE(mid.code_nm, d.work_mid_cd, '')) COLLATE NOCASE ASC,
                     ({wk}) DESC,
                     COALESCE(NULLIF(TRIM(p.pt_nm), ''), TRIM(CAST(r.emp_cd AS TEXT)), '') COLLATE NOCASE ASC,
                     COALESCE(fs.site_nm, TRIM(CAST(d.work_loc_id AS TEXT)), '') COLLATE NOCASE ASC,
                     d.work_id DESC, r.res_id
        """
        rows = self.execute_query(sql, tuple(params)) or []
        return [dict(r) if hasattr(r, "keys") else {} for r in rows]

    def list_workforce_pay_summary(
        self, farm_cd, start_yyyymmdd, end_yyyymmdd, unpaid_only=False
    ):
        """
        지급/미지급 집계: 인건비 포함 구분(EMP,TEMP) 작업자만.
        unpaid_only=True면 미지급(지급 Y 아님) 투입 건이 1건 이상인 작업자만.
        """
        fc = str(farm_cd or "").strip()
        sk = str(start_yyyymmdd or "").replace("-", "")[:8]
        ek = str(end_yyyymmdd or "").replace("-", "")[:8]
        if not fc or len(sk) < 8 or len(ek) < 8:
            return []
        wk = self._work_detail_dt_key_sql("d.work_dt")
        # 미지급만: SELECT 별칭은 HAVING에서 믿지 않고 집계식 그대로 사용(SQLite 호환)
        unpaid_having = ""
        if unpaid_only:
            unpaid_having = """HAVING SUM(CASE WHEN upper(ifnull(trim(r.pay_status), 'N')) <> 'Y'
                THEN 1 ELSE 0 END) > 0"""
        bill = self._partner_in_labor_total_sql("p")
        sql = f"""
            SELECT
                p.pt_id,
                p.pt_nm,
                SUM(COALESCE(r.daily_wage, 0)) AS total_labor,
                SUM(CASE WHEN upper(ifnull(trim(r.pay_status), 'N')) <> 'Y'
                    AND COALESCE(r.daily_wage, 0) > 0 THEN 1 ELSE 0 END) AS unpaid_cnt,
                SUM(CASE WHEN upper(ifnull(trim(r.pay_status), 'N')) <> 'Y'
                    THEN COALESCE(r.daily_wage, 0) ELSE 0 END) AS unpaid_amt
            FROM m_partner p
            INNER JOIN t_work_resource r
              ON r.farm_cd = p.farm_cd
             AND TRIM(CAST(r.emp_cd AS TEXT)) = TRIM(CAST(p.pt_id AS TEXT))
            INNER JOIN t_work_detail d
              ON d.work_id = r.work_id AND d.farm_cd = r.farm_cd
            WHERE p.farm_cd = ?
              AND ({wk}) BETWEEN ? AND ?
              AND {bill}
            GROUP BY p.pt_id, p.pt_nm
            {unpaid_having}
            ORDER BY p.pt_nm COLLATE NOCASE
        """
        rows = self.execute_query(sql, (fc, sk, ek)) or []
        return [dict(r) if hasattr(r, "keys") else {} for r in rows]

    # --- 농장별 재배작물 (m_farm_crop) ---

    def list_farm_crops(self, farm_cd: str, active_only: bool = True):
        """
        farm_cd 기준 재배작물 목록. active_only=True면 use_yn='Y'만.
        정렬: sort_ord, crop_nm
        """
        if not farm_cd or not str(farm_cd).strip():
            return []
        wh = "farm_cd = ?"
        params = [farm_cd]
        if active_only:
            wh += " AND IFNULL(use_yn, 'Y') = 'Y'"
        sql = f"""
            SELECT crop_id, crop_nm, sort_ord, rmk, use_yn
            FROM m_farm_crop
            WHERE {wh}
            ORDER BY sort_ord, crop_nm
        """
        rows = self.execute_query(sql, tuple(params))
        out = []
        for row in rows or []:
            out.append(
                {
                    "crop_id": row[0],
                    "crop_nm": row[1],
                    "sort_ord": row[2],
                    "rmk": row[3],
                    "use_yn": row[4] if len(row) > 4 else "Y",
                }
            )
        return out

    def _farm_crop_name_exists(
        self, farm_cd: str, crop_nm: str, exclude_crop_id=None
    ) -> bool:
        """동일 농장에서 활성(use_yn='Y') 작물명 중복 여부."""
        sql = """
            SELECT 1 FROM m_farm_crop
            WHERE farm_cd = ? AND IFNULL(use_yn, 'Y') = 'Y'
              AND crop_nm = ?
        """
        params = [farm_cd, crop_nm]
        if exclude_crop_id is not None:
            sql += " AND crop_id <> ?"
            params.append(exclude_crop_id)
        sql += " LIMIT 1"
        r = self.execute_query(sql, tuple(params))
        return bool(r)

    def insert_farm_crop(self, farm_cd, crop_nm, sort_ord=0, rmk=None, user_id=None):
        """
        재배작물 등록. 성공 시 crop_id, 실패(빈 이름·중복) 시 None.
        """
        if not farm_cd or not str(farm_cd).strip():
            return None
        nm = (crop_nm or "").strip()
        if not nm:
            return None
        try:
            so = int(sort_ord)
        except (TypeError, ValueError):
            so = 0
        if self._farm_crop_name_exists(farm_cd, nm):
            return None
        uid = user_id if user_id is not None else ""
        try:
            cur = self.conn.cursor()
            cur.execute(
                """
                INSERT INTO m_farm_crop (farm_cd, crop_nm, sort_ord, rmk, use_yn, reg_id, reg_dt)
                VALUES (?, ?, ?, ?, 'Y', ?, datetime('now','localtime'))
                """,
                (farm_cd, nm, so, rmk, uid),
            )
            self.conn.commit()
            return cur.lastrowid
        except sqlite3.Error as e:
            print(f"[DB] insert_farm_crop error: {e}")
            if self.conn:
                self.conn.rollback()
            return None

    def update_farm_crop(
        self,
        crop_id,
        farm_cd,
        crop_nm,
        sort_ord,
        rmk,
        use_yn,
        user_id=None,
    ):
        """재배작물 수정. 성공 True. farm_cd·crop_id 불일치 시 False."""
        if not farm_cd or not str(farm_cd).strip():
            return False
        if crop_id is None:
            return False
        nm = (crop_nm or "").strip()
        if not nm:
            return False
        try:
            so = int(sort_ord)
        except (TypeError, ValueError):
            so = 0
        uy = (use_yn or "Y").strip().upper()[:1] or "Y"
        if uy not in ("Y", "N"):
            uy = "Y"
        if self._farm_crop_name_exists(farm_cd, nm, exclude_crop_id=crop_id):
            return False
        uid = user_id if user_id is not None else ""
        try:
            cur = self.conn.cursor()
            cur.execute(
                """
                UPDATE m_farm_crop SET
                    crop_nm = ?, sort_ord = ?, rmk = ?, use_yn = ?,
                    mod_id = ?, mod_dt = datetime('now','localtime')
                WHERE crop_id = ? AND farm_cd = ?
                """,
                (nm, so, rmk, uy, uid, crop_id, farm_cd),
            )
            self.conn.commit()
            return cur.rowcount > 0
        except sqlite3.Error as e:
            print(f"[DB] update_farm_crop error: {e}")
            if self.conn:
                self.conn.rollback()
            return False

    def disable_farm_crop(self, crop_id, farm_cd, user_id=None):
        """사용중지(use_yn='N'). 성공 True."""
        if not farm_cd or not str(farm_cd).strip():
            return False
        if crop_id is None:
            return False
        uid = user_id if user_id is not None else ""
        try:
            cur = self.conn.cursor()
            cur.execute(
                """
                UPDATE m_farm_crop SET
                    use_yn = 'N',
                    mod_id = ?, mod_dt = datetime('now','localtime')
                WHERE crop_id = ? AND farm_cd = ?
                """,
                (uid, crop_id, farm_cd),
            )
            self.conn.commit()
            return cur.rowcount > 0
        except sqlite3.Error as e:
            print(f"[DB] disable_farm_crop error: {e}")
            if self.conn:
                self.conn.rollback()
            return False
