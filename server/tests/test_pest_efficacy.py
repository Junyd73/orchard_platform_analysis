# -*- coding: utf-8 -*-
"""병해충 잔효(efficacy_days) 기초 단위 테스트."""

from __future__ import annotations

import unittest
from datetime import date, timedelta

from core.pest_efficacy import evaluate_efficacy, efficacy_days_for_pest
from core.pest_outbreak_param_service import PestOutbreakParamService
from core.pesticide_ai_recommend_manager import PEST_RULES


class PestEfficacyTest(unittest.TestCase):
    def test_rules_have_efficacy_days(self) -> None:
        for pest, spec in PEST_RULES.items():
            self.assertIn("efficacy_days", spec, pest)
            self.assertGreaterEqual(int(spec["efficacy_days"]), 1, pest)

    def test_evaluate_active_window(self) -> None:
        today = date(2026, 7, 26)
        last = (today - timedelta(days=3)).isoformat()
        st = evaluate_efficacy(
            last_spray_dt=last, efficacy_days=10, as_of=today
        )
        self.assertTrue(st["efficacy_active"])
        self.assertEqual(st["efficacy_days_left"], 7)

    def test_evaluate_expired(self) -> None:
        today = date(2026, 7, 26)
        last = (today - timedelta(days=15)).isoformat()
        st = evaluate_efficacy(
            last_spray_dt=last, efficacy_days=10, as_of=today
        )
        self.assertFalse(st["efficacy_active"])
        self.assertEqual(st["efficacy_days_left"], 0)

    def test_resolve_efficacy_overlay(self) -> None:
        import os
        import sqlite3
        import tempfile
        from pathlib import Path

        fd, name = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        path = Path(name)
        path.unlink(missing_ok=True)
        conn = sqlite3.connect(str(path))
        conn.execute(
            "CREATE TABLE m_farm_info (farm_cd TEXT PRIMARY KEY, farm_nm TEXT)"
        )
        conn.execute("INSERT INTO m_farm_info VALUES ('OR001', 't')")
        conn.commit()

        class Bridge:
            def __init__(self, c: sqlite3.Connection) -> None:
                self.conn = c
                self.conn.row_factory = sqlite3.Row

            def execute_query(self, query, params=()):
                cur = self.conn.cursor()
                cur.execute(query, params)
                q = query.strip().upper()
                if q.startswith(("INSERT", "UPDATE", "DELETE", "CREATE", "REPLACE")):
                    self.conn.commit()
                return cur.fetchall()

        bridge = Bridge(conn)
        svc = PestOutbreakParamService(bridge)
        sys_days = efficacy_days_for_pest("응애")
        svc.upsert(
            "OR001",
            user_id=None,
            pest_nm="응애",
            param_key="efficacy_days",
            param_value=str(sys_days + 5),
            actor_id="admin",
            as_farm_default=True,
        )
        rules = svc.resolve_pest_rules("OR001", None)
        self.assertEqual(int(rules["응애"]["efficacy_days"]), sys_days + 5)
        conn.close()
        path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
