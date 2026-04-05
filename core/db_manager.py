import sqlite3
import os
import hashlib
import sys
import datetime
from PyQt6.QtCore import QDate, Qt, QTimer, QTime
from PyQt6.QtWidgets import *
from PyQt6.QtGui import *

class DBManager:
    # ---------------------------------------------------------
    # [핵심] 모든 메서드는 클래스 안쪽으로 4칸 들여쓰기 되어야 합니다.
    # ---------------------------------------------------------

    ROLE_HIERARCHY = {
        'SYS_ADMIN': 30,
        'ADMIN': 20,
        'USER': 10
    }

    def has_permission(self, current_role, limit_role):
        user_weight = self.ROLE_HIERARCHY.get(current_role, 0)
        limit_weight = self.ROLE_HIERARCHY.get(limit_role, 10)
        return user_weight >= limit_weight

    def hash_password(self, password):
        return hashlib.sha256(password.encode()).hexdigest()

    def login_check(self, user_id, user_pw):
        hashed_pw = self.hash_password(user_pw)
        sql = """
            SELECT u.user_id, u.user_nm, u.farm_cd, u.role_cd, f.farm_nm AS farm_nm
            FROM m_user u
            LEFT JOIN m_farm_info f ON u.farm_cd = f.farm_cd
            WHERE u.user_id = ? AND u.user_pw = ?
        """
        res = self.execute_query(sql, (user_id, hashed_pw))
        return dict(res[0]) if res else None

    def __init__(self, db_name="orchard_platform.db"):
        # core/ 내부에 있어도 프로젝트 루트 기준 DB 경로
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.db_name = os.path.join(base_dir, db_name)
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
        except sqlite3.Error as e:
            print(f"[DB] Connect failed: {e}")

    def ensure_pesticide_schema(self):
        """농약관리 테이블 및 사이드 메뉴 행 보장(기존 DB에도 안전하게 적용)."""
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
                stock_applied_yn TEXT NOT NULL DEFAULT 'N',
                stock_applied_dt TEXT,
                stock_applied_by TEXT,
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
            CREATE TABLE IF NOT EXISTS m_pesticide_purpose (
                purpose_id INTEGER PRIMARY KEY AUTOINCREMENT,
                purpose_group_nm TEXT,
                purpose_nm TEXT NOT NULL,
                sort_ord INTEGER DEFAULT 0,
                use_yn TEXT DEFAULT 'Y',
                rmk TEXT,
                reg_id TEXT,
                reg_dt TEXT DEFAULT (datetime('now','localtime')),
                mod_id TEXT,
                mod_dt TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS t_pesticide_info_purpose (
                map_id INTEGER PRIMARY KEY AUTOINCREMENT,
                info_id INTEGER NOT NULL,
                purpose_id INTEGER NOT NULL,
                sort_ord INTEGER DEFAULT 0,
                rmk TEXT,
                reg_id TEXT,
                reg_dt TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (info_id) REFERENCES m_pesticide_info(info_id) ON DELETE CASCADE,
                FOREIGN KEY (purpose_id) REFERENCES m_pesticide_purpose(purpose_id)
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
        self._ensure_pesticide_pest_map_indexes()
        self._seed_default_pesticide_purposes()
        self._ensure_pesticide_menu_row()
        self._ensure_pesticide_use_menu_row()
        self._ensure_pesticide_stats_menu_row()
        self._ensure_pesticide_info_menu_row()

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
        base_vals = (menu_cd, "농약정보", None, "📚", 0, "USER", 28, "Y")
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
        """m_menu_info에 농약 사용이력 메뉴(MN13) 보장."""
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
        base_vals = (menu_cd, "농약 사용이력", None, "📝", 0, "USER", 26, "Y")
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

    def _seed_default_pesticide_purposes(self):
        """용도 마스터가 비어 있을 때만 기본 용도 몇 건 등록."""
        try:
            cur = self.conn.cursor()
            cur.execute("SELECT COUNT(*) AS c FROM m_pesticide_purpose")
            row = cur.fetchone()
            if row and int(row[0] or 0) > 0:
                return
        except sqlite3.Error:
            return
        seeds = [
            ("", "살충", 10),
            ("", "살균", 20),
            ("", "응애", 30),
            ("", "깍지벌레", 40),
            ("", "진딧물", 50),
            ("", "전착", 60),
        ]
        for grp, nm, so in seeds:
            self.execute_query(
                """
                INSERT INTO m_pesticide_purpose (purpose_group_nm, purpose_nm, sort_ord, use_yn)
                VALUES (?, ?, ?, 'Y')
                """,
                (grp, nm, so),
            )

    def _migrate_pesticide_receipt_columns(self):
        """기존 DB: 입고 명세 재고 반영 중복 방지 컬럼."""
        try:
            cur = self.conn.cursor()
            cur.execute("PRAGMA table_info(t_pesticide_receipt)")
            cols = {row[1] for row in cur.fetchall()}
        except sqlite3.Error:
            return
        if not cols:
            return
        if "stock_applied_yn" not in cols:
            self.execute_query(
                """
                ALTER TABLE t_pesticide_receipt
                ADD COLUMN stock_applied_yn TEXT NOT NULL DEFAULT 'N'
                """
            )
        cur.execute("PRAGMA table_info(t_pesticide_receipt)")
        cols = {row[1] for row in cur.fetchall()}
        if "stock_applied_dt" not in cols:
            self.execute_query(
                "ALTER TABLE t_pesticide_receipt ADD COLUMN stock_applied_dt TEXT"
            )
        if "stock_applied_by" not in cols:
            self.execute_query(
                "ALTER TABLE t_pesticide_receipt ADD COLUMN stock_applied_by TEXT"
            )

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

    def execute_query(self, query, params=()):
        try:
            cur = self.conn.cursor()
            cur.execute(query, params)
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
                cur.execute(query, params)
            self.conn.commit()
            return True
        except Exception as e:
            if self.conn:
                self.conn.rollback()
            print(f"[DB] Transaction rollback: {e}")
            raise e
        finally:
            self.conn.isolation_level = ""

    def register_new_farm(self, farm_name, owner_nm, admin_id, admin_pw):
        try:
            res = self.execute_query("SELECT MAX(farm_cd) FROM m_farm_info WHERE farm_cd LIKE 'OR%'")
            max_cd = res[0][0] if res and res[0][0] else "OR000"
            new_farm_cd = f"OR{int(max_cd[2:]) + 1:03d}"
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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
            sql = "INSERT INTO m_partner (farm_cd, pt_nm, reg_dt) VALUES (?, ?, datetime('now','localtime'))"
            self.execute_query(sql, (farm_cd, pt_nm))
            return True
        except Exception as e:
            print(f"❌ 신규 직원 등록 실패: {e}")
            return False

    def add_new_partner_extended(self, farm_cd, data, user_id):
        sql = """
            INSERT INTO m_partner (
                farm_cd, pt_nm, pt_tel, base_price, bank_cd, account_no, use_yn, reg_id, reg_dt
            ) VALUES (?, ?, ?, ?, ?, ?, 'Y', ?, datetime('now','localtime'))
        """
        params = (
            farm_cd, data['pt_nm'], data['pt_tel'],
            data['base_price'], data['bank_cd'], data['account_no'], user_id
        )
        return self.execute_query(sql, params) is not None

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
            SELECT exp_id, work_id, acct_cd, item_nm, qty, unit_price, total_amt, pay_method_cd, pay_status
            FROM t_work_expense WHERE work_id = ?
        """
        return self.fetch_all(sql, (work_id,))

    def get_ledger_by_ref(self, ref_id):
        query = "SELECT slip_no, acc_amt, cash_amt FROM t_ledger WHERE ref_id = ?"
        result_list = self.execute_query(query, (ref_id,))
        if result_list and len(result_list) > 0:
            return dict(result_list[0])
        return None

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
