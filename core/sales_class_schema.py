# -*- coding: utf-8 -*-
"""판매분류 컬럼·공통코드 멱등 적용 (S2A).

운영 자동 DDL 금지. 로컬·테스트에서만 호출.
기존 sales_tp / sales_source / season_type_cd 값 변경·백필 없음.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any

from core.sales_class_constants import (
    SALES_CLASS_CHILD_ROWS,
    SALES_CLASS_PARENT_ROWS,
)

logger = logging.getLogger(__name__)

ORDER_SALES_CLASS_COLUMNS: tuple[tuple[str, str], ...] = (
    ("sales_type_cd", "TEXT"),
)

SALES_MASTER_CLASS_COLUMNS: tuple[tuple[str, str], ...] = (
    ("sales_type_cd", "TEXT"),
    ("sales_category_cd", "TEXT"),
    ("sales_route_cd", "TEXT"),
)

MSG_CODE_CONFLICT = "sales class common code conflict"
USE_YN_Y = "Y"
_SAVEPOINT = "orchard_sales_class_schema"


class SalesClassSchemaError(Exception):
    """공통코드 계약 충돌 등 schema helper 실패."""

    def __init__(self, message: str, *, code: str = "SCHEMA") -> None:
        super().__init__(message)
        self.code = code


def ensure_sales_class_schema(db: Path | str | sqlite3.Connection | Any) -> dict[str, Any]:
    """주문/판매 분류 컬럼 + SA01/02/03 공통코드 멱등 적용."""
    stats: dict[str, Any] = {
        "ok": True,
        "columns": [],
        "codes_inserted": [],
        "reason": "",
    }
    conn, owns = _open_conn(db)
    if conn is None:
        stats["ok"] = False
        stats["reason"] = "db_unavailable"
        return stats

    savepoint_open = False
    try:
        conn.execute(f"SAVEPOINT {_SAVEPOINT}")
        savepoint_open = True
        _ensure_table_columns(
            conn,
            table="t_order_master",
            columns=ORDER_SALES_CLASS_COLUMNS,
            stats=stats,
        )
        _ensure_table_columns(
            conn,
            table="t_sales_master",
            columns=SALES_MASTER_CLASS_COLUMNS,
            stats=stats,
        )
        _ensure_sales_class_codes(conn, stats)
        conn.execute(f"RELEASE SAVEPOINT {_SAVEPOINT}")
        savepoint_open = False
        # 외부 connection 트랜잭션은 침범하지 않음. owns 만 commit.
        if owns:
            conn.commit()
    except SalesClassSchemaError as exc:
        _abort_savepoint(conn, savepoint_open=savepoint_open, owns=owns)
        savepoint_open = False
        _clear_pending_stats(stats)
        stats["ok"] = False
        stats["reason"] = str(exc)
        logger.error("ensure_sales_class_schema conflict: %s", exc)
    except Exception as exc:  # noqa: BLE001
        _abort_savepoint(conn, savepoint_open=savepoint_open, owns=owns)
        savepoint_open = False
        _clear_pending_stats(stats)
        stats["ok"] = False
        stats["reason"] = str(exc)
        logger.exception("ensure_sales_class_schema failed")
    finally:
        if owns:
            conn.close()
    return stats


def _clear_pending_stats(stats: dict[str, Any]) -> None:
    """실패 시 미반영 상태와 stats 관측값을 일치."""
    stats["columns"] = []
    stats["codes_inserted"] = []


def _abort_savepoint(
    conn: sqlite3.Connection,
    *,
    savepoint_open: bool,
    owns: bool,
) -> None:
    """SAVEPOINT 만 원복. 외부 트랜잭션은 commit/rollback 하지 않음."""
    if savepoint_open:
        try:
            conn.execute(f"ROLLBACK TO SAVEPOINT {_SAVEPOINT}")
        except sqlite3.Error:
            pass
        try:
            conn.execute(f"RELEASE SAVEPOINT {_SAVEPOINT}")
        except sqlite3.Error:
            pass
    # 우리가 연 파일 연결만 잔여 트랜잭션 종료.
    if owns:
        try:
            conn.rollback()
        except sqlite3.Error:
            pass


def _ensure_table_columns(
    conn: sqlite3.Connection,
    *,
    table: str,
    columns: tuple[tuple[str, str], ...],
    stats: dict[str, Any],
) -> None:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (table,),
    ).fetchone()
    if not row:
        # 테이블 없으면 스킵(단위 테스트가 일부만 만들 수 있음). ok는 유지.
        return
    cols = {
        str(r[1]).strip().lower()
        for r in conn.execute(f"PRAGMA table_info({table})")
    }
    for name, col_def in columns:
        if name.lower() in cols:
            continue
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {col_def}")
        stats["columns"].append(f"{table}.{name}")
        cols.add(name.lower())


def _ensure_sales_class_codes(conn: sqlite3.Connection, stats: dict[str, Any]) -> None:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='m_common_code' LIMIT 1"
    ).fetchone()
    if not row:
        return

    farm_cds = _farm_cds(conn)
    now_sql = "datetime('now','localtime')"
    for farm_cd in farm_cds:
        for code_cd, code_nm in SALES_CLASS_PARENT_ROWS:
            _upsert_or_conflict(
                conn,
                farm_cd=farm_cd,
                code_cd=code_cd,
                code_nm=code_nm,
                parent_cd=None,
                now_sql=now_sql,
                stats=stats,
            )
        for parent_cd, code_cd, code_nm in SALES_CLASS_CHILD_ROWS:
            _upsert_or_conflict(
                conn,
                farm_cd=farm_cd,
                code_cd=code_cd,
                code_nm=code_nm,
                parent_cd=parent_cd,
                now_sql=now_sql,
                stats=stats,
            )


def _upsert_or_conflict(
    conn: sqlite3.Connection,
    *,
    farm_cd: str,
    code_cd: str,
    code_nm: str,
    parent_cd: str | None,
    now_sql: str,
    stats: dict[str, Any],
) -> None:
    existing = conn.execute(
        """
        SELECT code_nm, parent_cd, use_yn
          FROM m_common_code
         WHERE farm_cd = ? AND code_cd = ?
        """,
        (farm_cd, code_cd),
    ).fetchone()
    if existing is not None:
        if isinstance(existing, sqlite3.Row):
            ex_nm = str(existing["code_nm"])
            ex_parent = existing["parent_cd"]
            ex_use = existing["use_yn"]
        else:
            ex_nm = str(existing[0])
            ex_parent = existing[1]
            ex_use = existing[2]
        if ex_parent is not None:
            ex_parent = str(ex_parent)
        want_parent = None if parent_cd is None else str(parent_cd)
        ex_use_n = str(ex_use or "").strip()
        if (
            ex_nm != code_nm
            or (ex_parent or None) != want_parent
            or ex_use_n != USE_YN_Y
        ):
            raise SalesClassSchemaError(
                f"{MSG_CODE_CONFLICT}: farm={farm_cd} code={code_cd} "
                f"have=({ex_nm!r},{ex_parent!r},{ex_use_n!r}) "
                f"want=({code_nm!r},{want_parent!r},{USE_YN_Y!r})",
                code="CODE_CONFLICT",
            )
        return

    if parent_cd is None:
        conn.execute(
            f"""
            INSERT INTO m_common_code (
                farm_cd, code_cd, code_nm, parent_cd, use_yn,
                reg_id, reg_dt, mod_id, mod_dt
            ) VALUES (?, ?, ?, NULL, ?, 'SYSTEM', {now_sql}, 'SYSTEM', {now_sql})
            """,
            (farm_cd, code_cd, code_nm, USE_YN_Y),
        )
    else:
        conn.execute(
            f"""
            INSERT INTO m_common_code (
                farm_cd, code_cd, code_nm, parent_cd, use_yn,
                reg_id, reg_dt, mod_id, mod_dt
            ) VALUES (?, ?, ?, ?, ?, 'SYSTEM', {now_sql}, 'SYSTEM', {now_sql})
            """,
            (farm_cd, code_cd, code_nm, parent_cd, USE_YN_Y),
        )
    stats["codes_inserted"].append(f"{farm_cd}:{code_cd}")


def _farm_cds(conn: sqlite3.Connection) -> list[str]:
    has_farm = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='m_farm_info' LIMIT 1"
    ).fetchone()
    if has_farm:
        rows = conn.execute("SELECT farm_cd FROM m_farm_info").fetchall()
        out = [str(r[0]).strip() for r in rows if r and r[0]]
        if out:
            return out
    # m_common_code에 이미 있는 farm 또는 기본 OR001
    rows = conn.execute(
        "SELECT DISTINCT farm_cd FROM m_common_code WHERE farm_cd IS NOT NULL AND TRIM(farm_cd) != ''"
    ).fetchall()
    out = [str(r[0]).strip() for r in rows if r and r[0]]
    return out or ["OR001"]


def _open_conn(db: Path | str | sqlite3.Connection | Any) -> tuple[sqlite3.Connection | None, bool]:
    if isinstance(db, sqlite3.Connection):
        return db, False
    if hasattr(db, "conn") and getattr(db, "conn", None) is not None:
        return db.conn, False  # type: ignore[return-value]
    path = Path(str(db))
    if not path.is_file():
        return None, False
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn, True
