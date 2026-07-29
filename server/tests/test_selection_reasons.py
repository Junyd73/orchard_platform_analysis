# -*- coding: utf-8 -*-
"""스마트방제 선정사유 표준화·사다리 접기."""

from __future__ import annotations

import unittest

from core.pesticide_ai_recommend_manager import PesticideAIRecommendManager


class _Bridge:
    def execute_query(self, *args, **kwargs):
        return []


class TestSelectionReasons(unittest.TestCase):
    def setUp(self) -> None:
        self.mgr = PesticideAIRecommendManager(_Bridge())

    def test_collapse_ladder_keeps_highest(self) -> None:
        matched = [
            {
                "field": "avg_temp_3d",
                "op": ">=",
                "value": 15,
                "reason": "활동 시작(기온)",
            },
            {
                "field": "avg_temp_3d",
                "op": ">=",
                "value": 20,
                "reason": "활동 증가(기온)",
            },
            {
                "field": "current_month",
                "op": "in_range",
                "value": (4, 9),
                "reason": "발생 적기(4~9월)",
            },
        ]
        reasons = PesticideAIRecommendManager.collapse_selection_reasons(matched)
        self.assertEqual(reasons, ["활동 증가(기온)", "발생 적기(4~9월)"])

    def test_collapse_same_phrase_dedupes(self) -> None:
        matched = [
            {
                "field": "avg_temp_3d",
                "op": ">=",
                "value": 28,
                "reason": "최근 평균기온 높음",
            },
            {
                "field": "avg_temp_3d",
                "op": ">=",
                "value": 30,
                "reason": "최근 평균기온 높음",
            },
        ]
        reasons = PesticideAIRecommendManager.collapse_selection_reasons(matched)
        self.assertEqual(reasons, ["최근 평균기온 높음"])

    def test_mite_and_uslf_standardized(self) -> None:
        ctx = {
            "current_month": 7,
            "avg_temp_3d": 28.0,
            "rain_sum_7d": 116.0,
            "rain_days_7d": 6,
            "avg_humidity_7d": 94.0,
        }
        rows = {r["pest_nm"]: r for r in self.mgr.calculate_pest_scores(ctx)}
        mite = rows["응애"]
        self.assertEqual(mite["score"], 5)
        self.assertEqual(
            mite["reasons"],
            ["발생 적기(6~9월)", "최근 평균기온 높음"],
        )
        uslf = rows["미국선녀벌레"]
        self.assertEqual(uslf["score"], 3)
        self.assertEqual(
            uslf["reasons"],
            ["발생 적기(5~9월)", "최근 기온 상승"],
        )
        pear = rows["배나무이"]
        # 시즌(+1) + 활동 증가 상위만(+4), 활동 시작(+2) 미가점
        self.assertEqual(pear["score"], 5)
        self.assertEqual(
            pear["reasons"],
            ["발생 적기(4~9월)", "활동 증가(기온)"],
        )

    def test_ladder_score_not_accumulated(self) -> None:
        """동일 기온 사다리는 상위 임계 점수만 반영."""
        ctx_mid = {
            "current_month": 7,
            "avg_temp_3d": 18.0,
            "rain_sum_7d": 10.0,
            "rain_days_7d": 1,
            "avg_humidity_7d": 60.0,
        }
        ctx_high = dict(ctx_mid)
        ctx_high["avg_temp_3d"] = 28.0
        rows_mid = {r["pest_nm"]: r for r in self.mgr.calculate_pest_scores(ctx_mid)}
        rows_high = {r["pest_nm"]: r for r in self.mgr.calculate_pest_scores(ctx_high)}
        # 배나무이: 18℃ → 시작(+2)+시즌(+1)=3 / 28℃ → 증가(+4)+시즌(+1)=5 (시작 미가점)
        self.assertEqual(rows_mid["배나무이"]["score"], 3)
        self.assertEqual(rows_high["배나무이"]["score"], 5)
        self.assertNotIn("활동 시작(기온)", rows_high["배나무이"]["reasons"])
        # 응애 32℃: 시즌(+2)+상위기온(+5)=7 (28℃ 단계 +3 미가점)
        ctx_hot = dict(ctx_high)
        ctx_hot["avg_temp_3d"] = 32.0
        rows_hot = {r["pest_nm"]: r for r in self.mgr.calculate_pest_scores(ctx_hot)}
        self.assertEqual(rows_hot["응애"]["score"], 7)


if __name__ == "__main__":
    unittest.main()
