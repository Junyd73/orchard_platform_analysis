# -*- coding: utf-8 -*-
"""OPS P2 — PyQt/core·SQL now 재료화 + KST 자정 경계."""

from __future__ import annotations

import os
import sys
import time
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import patch

_SERVER = Path(__file__).resolve().parents[1]
_REPO = _SERVER.parent
for p in (str(_SERVER), str(_REPO)):
    if p not in sys.path:
        sys.path.insert(0, p)

os.environ["TZ"] = "UTC"
time.tzset()

import types

_qt_mod = types.ModuleType("PyQt6")
_qt_core = types.ModuleType("PyQt6.QtCore")
_qt_widgets = types.ModuleType("PyQt6.QtWidgets")
_qt_gui = types.ModuleType("PyQt6.QtGui")
for name, mod in (
    ("PyQt6", _qt_mod),
    ("PyQt6.QtCore", _qt_core),
    ("PyQt6.QtWidgets", _qt_widgets),
    ("PyQt6.QtGui", _qt_gui),
):
    sys.modules.setdefault(name, mod)
_qt_core.QDate = object
_qt_core.Qt = object
_qt_core.QTimer = object
_qt_core.QTime = object

from core.db_manager import DBManager
from core.ops_biz_date import (
    materialize_now_ops_sql,
    now_ops,
    now_ops_str,
    today_ops,
    today_ops_iso,
)

# UTC 2026-08-17 15:30 == KST 2026-08-18 00:30
_UTC_BOUNDARY = datetime(2026, 8, 17, 15, 30, tzinfo=timezone.utc)


def _freeze_ops(frozen_utc: datetime):
    class _FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):  # noqa: ANN001
            if tz is not None:
                return frozen_utc.astimezone(tz)
            return frozen_utc.replace(tzinfo=None)

    return patch("core.ops_biz_date.datetime", _FrozenDateTime)


class OpsBizDateP2BoundaryTest(unittest.TestCase):
    def test_os_tz_utc(self) -> None:
        self.assertEqual(os.environ.get("TZ"), "UTC")

    def test_boundary_today_and_now_str(self) -> None:
        with _freeze_ops(_UTC_BOUNDARY):
            self.assertEqual(today_ops(), date(2026, 8, 18))
            self.assertEqual(today_ops_iso(), "2026-08-18")
            self.assertEqual(now_ops().strftime("%Y-%m-%d %H:%M"), "2026-08-18 00:30")
            self.assertTrue(now_ops_str().startswith("2026-08-18 00:30"))
            self.assertEqual(_UTC_BOUNDARY.astimezone(timezone.utc).date(), date(2026, 8, 17))


class OpsBizDateP2SqlMaterializeTest(unittest.TestCase):
    def test_a_bare_datetime_now_unchanged(self) -> None:
        sql = "SELECT datetime('now')"
        with _freeze_ops(_UTC_BOUNDARY):
            self.assertEqual(materialize_now_ops_sql(sql), sql)

    def test_b_localtime_materialized(self) -> None:
        sql = "UPDATE t SET mod_dt = datetime('now','localtime') WHERE id = ?"
        with _freeze_ops(_UTC_BOUNDARY):
            out = materialize_now_ops_sql(sql)
        self.assertNotIn("datetime('now'", out.lower().replace(" ", ""))
        self.assertIn("'2026-08-18 00:30:00'", out)

    def test_c_date_now_unchanged(self) -> None:
        sql = "SELECT date('now'), date('now', '-14 days')"
        with _freeze_ops(_UTC_BOUNDARY):
            self.assertEqual(materialize_now_ops_sql(sql), sql)

    def test_d_case_and_whitespace_variants(self) -> None:
        variants = [
            "UPDATE t SET m = DATETIME('now','localtime')",
            "UPDATE t SET m = datetime( 'now' , 'localtime' )",
            "UPDATE t SET m = datetime('now',  'localtime')",
        ]
        with _freeze_ops(_UTC_BOUNDARY):
            for sql in variants:
                out = materialize_now_ops_sql(sql)
                self.assertIn("'2026-08-18 00:30:00'", out, msg=sql)
                self.assertNotIn("localtime", out.lower())

    def test_e_string_literal_preserved(self) -> None:
        sql_sq = "INSERT INTO t (rmk) VALUES ('uses datetime(''now'') idiom')"
        sql_dq = "INSERT INTO t (rmk) VALUES (\"note: datetime('now','localtime') docs\")"
        with _freeze_ops(_UTC_BOUNDARY):
            self.assertEqual(materialize_now_ops_sql(sql_sq), sql_sq)
            self.assertEqual(materialize_now_ops_sql(sql_dq), sql_dq)

    def test_f_ddl_default_not_materialized(self) -> None:
        ddl = (
            "CREATE TABLE IF NOT EXISTS t ("
            "reg_dt TEXT DEFAULT (datetime('now','localtime')))"
        )
        alter = "ALTER TABLE t ADD COLUMN x TEXT DEFAULT (datetime('now','localtime'))"
        with _freeze_ops(_UTC_BOUNDARY):
            self.assertEqual(materialize_now_ops_sql(ddl), ddl)
            self.assertEqual(materialize_now_ops_sql(alter), alter)
            self.assertEqual(DBManager._materialize_ops_now_sql(ddl), ddl)


if __name__ == "__main__":
    unittest.main()
