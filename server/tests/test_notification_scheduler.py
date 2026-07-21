# -*- coding: utf-8 -*-
"""알림 스케줄러 — 병해충 계절 주기."""

from __future__ import annotations

import unittest
from datetime import date


class PestScheduleSeasonTest(unittest.TestCase):
    def test_warm_cold_constants_match_season_label(self) -> None:
        from app.scheduler import (
            PEST_COLD_DOW,
            PEST_COLD_MONTHS,
            PEST_HOUR,
            PEST_WARM_DOW,
            PEST_WARM_MONTHS,
        )
        from core.ai.observation_ai_context import season_label

        self.assertEqual(PEST_HOUR, 7)
        self.assertEqual(PEST_WARM_MONTHS, "3-8")
        self.assertEqual(PEST_COLD_MONTHS, "9-12,1-2")
        self.assertEqual(PEST_WARM_DOW, "mon,wed,fri")
        self.assertEqual(PEST_COLD_DOW, "mon")

        warm_months = {3, 4, 5, 6, 7, 8}
        for m in range(1, 13):
            label = season_label(date(2026, m, 15))
            if m in warm_months:
                self.assertIn(label, ("봄", "여름"), msg=f"month={m}")
            else:
                self.assertIn(label, ("가을", "겨울"), msg=f"month={m}")


if __name__ == "__main__":
    unittest.main()
