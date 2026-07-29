# -*- coding: utf-8 -*-
"""SPR-001 smart-spray 스냅샷·패치 단위 테스트."""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from app.schemas.smart_spray import OutbreakParamUpsertRequest
from app.services.smart_spray_service import SmartSprayService
from core.smart_spray_briefing_schema import TABLE_SMART_SPRAY_BRIEFING


def _tmp_db() -> Path:
    fd, name = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    path = Path(name)
    path.unlink(missing_ok=True)
    conn = sqlite3.connect(str(path))
    conn.executescript(
        """
        CREATE TABLE m_farm_info (
            farm_cd TEXT PRIMARY KEY, farm_nm TEXT,
            lat REAL, lon REAL, nx INTEGER, ny INTEGER
        );
        INSERT INTO m_farm_info VALUES ('OR001', '테스트', 37.2, 126.8, 60, 120);
        CREATE TABLE m_user (
            user_id TEXT PRIMARY KEY, role_cd TEXT, farm_cd TEXT, use_yn TEXT
        );
        INSERT INTO m_user VALUES ('admin1', 'ADMIN', 'OR001', 'Y');
        INSERT INTO m_user VALUES ('user1', 'USER', 'OR001', 'Y');
        """
    )
    conn.commit()
    conn.close()
    return path


class SmartSprayServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db = _tmp_db()
        self.svc = SmartSprayService(db_path=self.db)

    def tearDown(self) -> None:
        self.db.unlink(missing_ok=True)

    def test_upsert_mine_and_list(self) -> None:
        self.svc.upsert_outbreak_param(
            "OR001",
            OutbreakParamUpsertRequest(
                pest_nm="응애",
                param_key="avg_temp_3d",
                param_value="29",
                as_farm_default=False,
            ),
            user_id="user1",
        )
        lst = self.svc.list_outbreak_params(
            "OR001", user_id="user1", scope="mine"
        )
        self.assertTrue(
            any(
                i.pest_nm == "응애" and i.param_key == "avg_temp_3d"
                for i in lst.items
            )
        )

    def test_farm_default_requires_admin(self) -> None:
        from app.core.exceptions import BusinessRuleError

        with self.assertRaises(BusinessRuleError):
            self.svc.upsert_outbreak_param(
                "OR001",
                OutbreakParamUpsertRequest(
                    pest_nm="응애",
                    param_key="min_score",
                    param_value="6",
                    as_farm_default=True,
                ),
                user_id="user1",
            )

    def test_briefing_fallback_persists_snapshot(self) -> None:
        res = self.svc.get_briefing("OR001", user_id="user1")
        self.assertTrue(res.success)
        self.assertIsInstance(res.cards, list)
        self.assertEqual(res.source, "fallback_build")
        self.assertTrue(res.computed_at)

        conn = sqlite3.connect(str(self.db))
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            f"SELECT * FROM {TABLE_SMART_SPRAY_BRIEFING} WHERE farm_cd=? AND work_dt=?",
            ("OR001", date.today().isoformat()),
        ).fetchone()
        conn.close()
        self.assertIsNotNone(row)
        self.assertEqual(row["dirty_yn"], "N")
        cards = json.loads(row["cards_json"])
        self.assertIsInstance(cards, list)

    def test_briefing_second_call_hits_snapshot(self) -> None:
        first = self.svc.get_briefing("OR001", user_id="user1")
        self.assertEqual(first.source, "fallback_build")
        second = self.svc.get_briefing("OR001", user_id="user1")
        self.assertEqual(second.source, "snapshot")
        self.assertEqual(second.computed_at, first.computed_at)

    def test_farm_param_marks_dirty_then_rebuild(self) -> None:
        self.svc.get_briefing("OR001", user_id="admin1")
        self.svc.upsert_outbreak_param(
            "OR001",
            OutbreakParamUpsertRequest(
                pest_nm="응애",
                param_key="min_score",
                param_value="1",
                as_farm_default=True,
            ),
            user_id="admin1",
        )
        conn = sqlite3.connect(str(self.db))
        dirty = conn.execute(
            f"SELECT dirty_yn FROM {TABLE_SMART_SPRAY_BRIEFING} WHERE farm_cd=?",
            ("OR001",),
        ).fetchone()[0]
        conn.close()
        self.assertEqual(dirty, "Y")

        rebuilt = self.svc.get_briefing("OR001", user_id="admin1")
        self.assertEqual(rebuilt.source, "dirty_rebuild")

    def test_personal_rescore_skips_weather_api(self) -> None:
        # seed snapshot without personal
        self.svc.get_briefing("OR001", user_id=None)
        self.svc.upsert_outbreak_param(
            "OR001",
            OutbreakParamUpsertRequest(
                pest_nm="응애",
                param_key="min_score",
                param_value="1",
                as_farm_default=False,
            ),
            user_id="user1",
        )
        with patch.object(
            SmartSprayService,
            "fetch_weather_ctx",
            side_effect=AssertionError("weather must not be fetched"),
        ):
            res = self.svc.get_briefing("OR001", user_id="user1")
        self.assertTrue(res.patched.personal)
        self.assertEqual(res.source, "snapshot")

    def test_job_persist_snapshot(self) -> None:
        from app.jobs.smart_spray_job import run_smart_spray_prefetch

        out = run_smart_spray_prefetch(self.db)
        self.assertGreaterEqual(out.get("fetched", 0), 1)
        conn = sqlite3.connect(str(self.db))
        n = conn.execute(
            f"SELECT COUNT(*) FROM {TABLE_SMART_SPRAY_BRIEFING}"
        ).fetchone()[0]
        conn.close()
        self.assertEqual(n, 1)


if __name__ == "__main__":
    unittest.main()
