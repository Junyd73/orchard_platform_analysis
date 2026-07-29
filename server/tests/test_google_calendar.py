# -*- coding: utf-8 -*-
"""구글 캘린더 Phase4 — 상태·state·실적 이벤트 본문 테스트."""

from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

_SERVER = Path(__file__).resolve().parents[1]
_REPO = _SERVER.parent
for p in (_REPO, _SERVER):
    s = str(p)
    if s in sys.path:
        sys.path.remove(s)
    sys.path.insert(0, s)

from app.core.exceptions import BusinessRuleError  # noqa: E402
from app.services.google_calendar_service import (  # noqa: E402
    GoogleCalendarService,
    _parse_event_start,
    build_work_event_description,
    build_work_event_summary,
)
from core.google_calendar_constants import (  # noqa: E402
    ERR_GOOGLE_NOT_CONFIGURED,
    MSG_GOOGLE_IMPORT_EMPTY,
)
from core.work_schedule_constants import GOOGLE_EVENT_TIMEZONE  # noqa: E402


def _tmp_db() -> Path:
    fd, name = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    path = Path(name)
    path.unlink(missing_ok=True)
    conn = sqlite3.connect(str(path))
    conn.executescript(
        """
        CREATE TABLE m_farm_info (farm_cd TEXT PRIMARY KEY, farm_nm TEXT);
        INSERT INTO m_farm_info VALUES ('OR001', '테스트');
        CREATE TABLE m_common_code (
            farm_cd TEXT, code_cd TEXT, code_nm TEXT, parent_cd TEXT,
            use_yn TEXT, reg_id TEXT, reg_dt TEXT, mod_id TEXT, mod_dt TEXT
        );
        CREATE TABLE t_work_detail (
            work_id TEXT, work_dt TEXT, farm_cd TEXT,
            work_main_cd TEXT, work_mid_cd TEXT, work_loc_id TEXT,
            start_tm TEXT, end_tm TEXT, status_cd TEXT, rmk TEXT,
            google_event_id TEXT, sync_status TEXT, last_synced_at TEXT,
            reg_id TEXT, reg_dt TEXT, mod_id TEXT, mod_dt TEXT
        );
        CREATE TABLE t_work_master (
            work_dt TEXT, farm_cd TEXT, day_of_week TEXT,
            reg_id TEXT, reg_dt TEXT, mod_id TEXT, mod_dt TEXT
        );
        CREATE TABLE m_farm_site (
            farm_cd TEXT, site_id TEXT, site_nm TEXT
        );
        """
    )
    conn.commit()
    conn.close()
    return path


class GoogleCalendarServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db = _tmp_db()
        self.settings = SimpleNamespace(
            google_oauth_configured=False,
            google_oauth_client_id="",
            google_oauth_client_secret="",
            google_oauth_redirect_uri="",
            google_oauth_success_redirect="http://127.0.0.1:5173/work-log",
            default_user_id="MOBILE",
        )
        self.svc = GoogleCalendarService(self.db, settings=self.settings)

    def tearDown(self) -> None:
        self.db.unlink(missing_ok=True)

    def test_status_not_configured(self) -> None:
        st = self.svc.status("OR001")
        self.assertFalse(st["configured"])
        self.assertFalse(st["connected"])

    def test_auth_url_requires_config(self) -> None:
        with self.assertRaises(BusinessRuleError) as ctx:
            self.svc.build_auth_url("OR001")
        self.assertEqual(ctx.exception.error_code, ERR_GOOGLE_NOT_CONFIGURED)

    def test_state_roundtrip(self) -> None:
        raw = {"farm_cd": "OR001", "user_id": "u1", "success_redirect": "http://x"}
        enc = GoogleCalendarService._encode_state(raw)
        dec = GoogleCalendarService._decode_state(enc)
        self.assertEqual(dec["farm_cd"], "OR001")
        self.assertEqual(dec["user_id"], "u1")

    def test_parse_event_start_allday_and_timed(self) -> None:
        self.assertEqual(
            _parse_event_start({"date": "2026-07-20"}),
            ("2026-07-20", None),
        )
        parsed = _parse_event_start({"dateTime": "2026-07-20T07:30:00+09:00"})
        self.assertEqual(parsed, ("2026-07-20", "07:30"))

    def test_work_event_summary_and_description(self) -> None:
        self.assertEqual(
            build_work_event_summary(loc_nm="앞밭", mid_nm="경운작업"),
            "앞밭 경운작업",
        )
        desc = build_work_event_description(
            status_nm="완료",
            rmk="로터리작업(기계고장)",
            work_id="20260721-01",
        )
        self.assertIn("상태: 완료", desc)
        self.assertIn("로터리작업(기계고장)", desc)
        self.assertIn("20260721-01", desc)

    def test_schedule_event_body_timed_vs_allday(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute(
            """
            CREATE TABLE t (
              sched_id TEXT, work_dt TEXT, work_tm TEXT,
              title TEXT, contents TEXT, work_mid_cd TEXT, work_mid_nm TEXT
            )
            """
        )
        conn.execute(
            "INSERT INTO t VALUES ('SCH20260720-001','2026-07-20','07:30','테스트',NULL,'WK010100','전정')"
        )
        row = conn.execute("SELECT * FROM t").fetchone()
        body = self.svc._schedule_event_body("OR001", row)
        self.assertIn("dateTime", body["start"])
        self.assertEqual(body["start"]["timeZone"], GOOGLE_EVENT_TIMEZONE)
        self.assertTrue(body["start"]["dateTime"].startswith("2026-07-20T07:30"))

        conn.execute("UPDATE t SET work_tm = NULL")
        row2 = conn.execute("SELECT * FROM t").fetchone()
        body2 = self.svc._schedule_event_body("OR001", row2)
        self.assertEqual(body2["start"]["date"], "2026-07-20")
        self.assertEqual(body2["end"]["date"], "2026-07-21")

    def test_import_empty_message_constant(self) -> None:
        self.assertEqual(MSG_GOOGLE_IMPORT_EMPTY, "등록된 구글 일정이 없습니다.")


if __name__ == "__main__":
    unittest.main()
