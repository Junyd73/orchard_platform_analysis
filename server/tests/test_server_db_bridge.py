# -*- coding: utf-8 -*-
"""ServerDbBridge SQL 오류·트랜잭션 동작 테스트."""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest

from app.services.observation_ai_db_bridge import ServerDbBridge


def test_execute_query_raises_on_sql_error() -> None:
    fd, name = tempfile.mkstemp(suffix=".db")
    path = Path(name)
    conn = None
    try:
        import os

        os.close(fd)
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        db = ServerDbBridge(conn)
        with pytest.raises(sqlite3.Error):
            db.execute_query("SELECT * FROM no_such_table_xyz")
    finally:
        if conn is not None:
            conn.close()
        path.unlink(missing_ok=True)


def test_execute_transaction_no_partial_commit_on_error() -> None:
    fd, name = tempfile.mkstemp(suffix=".db")
    path = Path(name)
    conn = None
    try:
        import os

        os.close(fd)
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        db = ServerDbBridge(conn)
        db.execute_query("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
        with pytest.raises(sqlite3.Error):
            db.execute_transaction(
                [
                    ("INSERT INTO t (id, v) VALUES (1, 'a')", ()),
                    ("INSERT INTO t (id, v) VALUES (1, 'dup')", ()),
                ]
            )
        rows = db.execute_query("SELECT COUNT(*) AS c FROM t")
        assert int(rows[0]["c"]) == 0
    finally:
        if conn is not None:
            conn.close()
        path.unlink(missing_ok=True)
