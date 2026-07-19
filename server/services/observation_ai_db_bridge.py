# -*- coding: utf-8 -*-
"""PC DBManager 덕 타이핑 브리지 — REST 가 ApplicationService 에 넘길 DB 핸들.

PyQt DBManager 인스턴스를 생성하지 않고, Stage3/ApplicationService 가 기대하는
메서드·상수만 제공한다.
"""

from __future__ import annotations

import sqlite3
from typing import Any


class ServerDbBridge:
    """sqlite3.Connection 기반 DBManager 호환 파사드."""

    OBS_AI_STATUS_NONE = "NONE"
    OBS_AI_STATUS_PENDING = "PENDING"
    OBS_AI_STATUS_COMPLETED = "COMPLETED"
    OBS_AI_STATUS_CONFIRMED = "CONFIRMED"
    OBS_AI_STATUS_HOLD = "HOLD"
    OBS_AI_STATUS_FAILED = "FAILED"
    OBS_AI_STATUS_ANALYZING = "ANALYZING"
    OBS_AI_STATUS_ANALYZED = "ANALYZED"
    OBS_AI_STATUS_REVIEW_REQUIRED = "REVIEW_REQUIRED"
    OBS_AI_STATUS_VALUES = frozenset(
        {
            OBS_AI_STATUS_NONE,
            OBS_AI_STATUS_PENDING,
            OBS_AI_STATUS_COMPLETED,
            OBS_AI_STATUS_CONFIRMED,
            OBS_AI_STATUS_HOLD,
            OBS_AI_STATUS_FAILED,
            OBS_AI_STATUS_ANALYZING,
            OBS_AI_STATUS_ANALYZED,
            OBS_AI_STATUS_REVIEW_REQUIRED,
        }
    )

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self._txn_depth = 0
        if self.conn.row_factory is None:
            self.conn.row_factory = sqlite3.Row

    @classmethod
    def normalize_obs_ai_status(cls, value, fallback=None) -> str:
        raw = str(value or "").strip().upper()
        if raw in cls.OBS_AI_STATUS_VALUES:
            return raw
        fb = str(fallback or "").strip().upper()
        if fb in cls.OBS_AI_STATUS_VALUES:
            return fb
        return cls.OBS_AI_STATUS_NONE

    def execute_query(self, query, params=()):
        try:
            cur = self.conn.cursor()
            cur.execute(query, params)
            query_start = query.strip().upper()
            # 명시적 트랜잭션 안에서는 개별 commit 금지
            if self._txn_depth == 0 and query_start.startswith(
                ("INSERT", "UPDATE", "DELETE", "CREATE", "ALTER", "DROP", "REPLACE")
            ):
                self.conn.commit()
            return cur.fetchall()
        except sqlite3.Error as e:
            try:
                self.conn.rollback()
            except sqlite3.Error:
                pass
            # SQL·경로·개인정보 미출력
            print(f"[ServerDbBridge] Query error: code=DB_ERROR exc={type(e).__name__}")
            raise

    def execute_transaction(self, queries_with_params):
        self._txn_depth += 1
        try:
            self.conn.isolation_level = None
            cur = self.conn.cursor()
            cur.execute("BEGIN TRANSACTION")
            for query, params in queries_with_params:
                cur.execute(query, params)
            self.conn.commit()
            return True
        except Exception as e:
            try:
                self.conn.rollback()
            except sqlite3.Error:
                pass
            print(f"[ServerDbBridge] Transaction error: code=DB_ERROR exc={type(e).__name__}")
            raise
        finally:
            self._txn_depth = max(0, self._txn_depth - 1)
            try:
                self.conn.isolation_level = ""
            except Exception:
                pass

    def fetch_all(self, query, params=()):
        """AccountManager 등 PC DBManager.fetch_all 호환."""
        return self.execute_query(query, params)

    def transaction(self):
        """동일 connection/cursor Context Manager (DBManager.transaction 호환)."""
        from contextlib import contextmanager

        @contextmanager
        def _ctx():
            conn = self.conn
            prev_isolation = conn.isolation_level
            self._txn_depth += 1
            try:
                conn.isolation_level = None
                if conn.row_factory is None:
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
                self._txn_depth = max(0, self._txn_depth - 1)
                try:
                    conn.isolation_level = (
                        prev_isolation if prev_isolation is not None else ""
                    )
                except Exception:
                    conn.isolation_level = ""

        return _ctx()

    def get_observation(self, farm_cd: str, obs_id: str) -> dict[str, Any] | None:
        farm = str(farm_cd or "").strip()
        oid = str(obs_id or "").strip()
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
