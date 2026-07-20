# -*- coding: utf-8 -*-
"""알림 API Phase1 스모크 테스트."""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

_SERVER = Path(__file__).resolve().parents[1]
_REPO = _SERVER.parent
# server/app 이 루트 app 패키지보다 우선해야 함
for p in (_REPO, _SERVER):
    s = str(p)
    if s in sys.path:
        sys.path.remove(s)
sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(_SERVER))

from core.notification_schema import (  # noqa: E402
    PRIORITY_URGENT_CD,
    ensure_notification_schema,
)
from app.services.notification_service import NotificationService  # noqa: E402


def _build_tmp_db() -> Path:
    fd, name = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    path = Path(name)
    path.unlink(missing_ok=True)
    conn = sqlite3.connect(str(path))
    conn.executescript(
        """
        CREATE TABLE m_farm_info (
            farm_cd TEXT PRIMARY KEY, farm_nm TEXT
        );
        INSERT INTO m_farm_info VALUES ('OR001', '테스트농장');

        CREATE TABLE m_common_code (
            farm_cd TEXT, code_cd TEXT, code_nm TEXT NOT NULL,
            parent_cd TEXT, use_yn TEXT DEFAULT 'Y',
            reg_id TEXT, reg_dt TEXT, mod_id TEXT, mod_dt TEXT,
            PRIMARY KEY (farm_cd, code_cd)
        );
        """
    )
    conn.commit()
    conn.close()
    ensure_notification_schema(path)
    return path


def _insert_noti(
    path: Path,
    *,
    noti_id: str,
    priority_cd: str = "NP010200",
    noti_type_cd: str = "NT010200",
    title: str = "테스트 알림",
    payload: dict | None = None,
) -> None:
    conn = sqlite3.connect(str(path))
    conn.execute(
        """
        INSERT INTO t_notification (
            noti_id, farm_cd, noti_type_cd, priority_cd, title, body,
            payload_json, source_cd, ref_type, ref_id, event_at,
            dedupe_key, use_yn, reg_id, reg_dt
        ) VALUES (?, 'OR001', ?, ?, ?, ?, ?, 'INTERNAL', 'OBSERVATION', 'OBS1',
                  datetime('now','localtime'), ?, 'Y', 'SYSTEM',
                  datetime('now','localtime'))
        """,
        (
            noti_id,
            noti_type_cd,
            priority_cd,
            title,
            "본문",
            json.dumps(payload or {}, ensure_ascii=False),
            f"DEDUP:{noti_id}",
        ),
    )
    conn.commit()
    conn.close()


class NotificationServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = _build_tmp_db()
        self.svc = NotificationService(self.db)

    def tearDown(self) -> None:
        try:
            self.db.unlink(missing_ok=True)
        except OSError:
            pass

    def test_schema_seeds_codes(self) -> None:
        conn = sqlite3.connect(str(self.db))
        row = conn.execute(
            "SELECT code_nm FROM m_common_code WHERE farm_cd='OR001' AND code_cd='NT01'"
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], "알림유형")
        conn.close()

    def test_list_summary_and_read(self) -> None:
        _insert_noti(
            self.db,
            noti_id="NTF20260720-001",
            priority_cd=PRIORITY_URGENT_CD,
            title="위험 관찰",
            payload={"route": "observation-detail", "obs_id": "OBS1"},
        )
        _insert_noti(
            self.db,
            noti_id="NTF20260720-002",
            title="일반 알림",
        )
        items = self.svc.list_notifications("OR001", user_id="u1")
        self.assertEqual(len(items), 2)
        by_id = {it.noti_id: it for it in items}
        urgent = by_id["NTF20260720-001"]
        self.assertEqual(urgent.read_yn, "N")
        self.assertEqual(urgent.payload.get("route"), "observation-detail")

        summary = self.svc.get_summary("OR001", user_id="u1")
        self.assertEqual(summary.unread_count, 2)
        self.assertEqual(summary.urgent_count, 1)

        one = self.svc.mark_read("OR001", "NTF20260720-001", user_id="u1")
        self.assertEqual(one.read_yn, "Y")
        summary2 = self.svc.get_summary("OR001", user_id="u1")
        self.assertEqual(summary2.unread_count, 1)
        self.assertEqual(summary2.urgent_count, 0)

        all_res = self.svc.mark_read_all("OR001", user_id="u1")
        self.assertEqual(all_res.updated_count, 1)
        summary3 = self.svc.get_summary("OR001", user_id="u1")
        self.assertEqual(summary3.unread_count, 0)

    def test_mark_read_idempotent_and_payload(self) -> None:
        _insert_noti(
            self.db,
            noti_id="NTF20260720-010",
            title="상세 딥링크",
            payload={
                "route": "observation-detail",
                "obs_id": "OBS20260719-001",
            },
        )
        first = self.svc.mark_read("OR001", "NTF20260720-010", user_id="u2")
        second = self.svc.mark_read("OR001", "NTF20260720-010", user_id="u2")
        self.assertEqual(first.read_yn, "Y")
        self.assertEqual(second.read_yn, "Y")
        items = self.svc.list_notifications("OR001", user_id="u2")
        hit = next(i for i in items if i.noti_id == "NTF20260720-010")
        self.assertEqual(hit.read_yn, "Y")
        self.assertEqual(hit.payload.get("obs_id"), "OBS20260719-001")
        self.assertEqual(hit.payload.get("route"), "observation-detail")


if __name__ == "__main__":
    unittest.main()
