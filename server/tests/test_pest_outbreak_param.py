# -*- coding: utf-8 -*-
"""SPR-001 발병여건 파라미터 resolve·CRUD 테스트."""

from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path


def _tmp_db() -> Path:
    fd, name = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    path = Path(name)
    path.unlink(missing_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute(
        """
        CREATE TABLE m_farm_info (
            farm_cd TEXT PRIMARY KEY, farm_nm TEXT
        )
        """
    )
    conn.execute("INSERT INTO m_farm_info VALUES ('OR001', '테스트')")
    conn.commit()
    conn.close()
    return path


class _Bridge:
    def __init__(self, path: Path) -> None:
        self.conn = sqlite3.connect(str(path))
        self.conn.row_factory = sqlite3.Row

    def execute_query(self, query, params=()):
        cur = self.conn.cursor()
        cur.execute(query, params)
        q = query.strip().upper()
        if q.startswith(("INSERT", "UPDATE", "DELETE", "CREATE", "ALTER", "REPLACE")):
            self.conn.commit()
        return cur.fetchall()


class PestOutbreakParamResolveTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db = _tmp_db()
        self.bridge = _Bridge(self.db)

    def tearDown(self) -> None:
        self.bridge.conn.close()
        self.db.unlink(missing_ok=True)

    def test_user_overrides_farm_and_system(self) -> None:
        from core.pest_outbreak_param_service import PestOutbreakParamService
        from core.pesticide_ai_recommend_manager import PEST_RULES

        svc = PestOutbreakParamService(self.bridge)
        sys_min = int(PEST_RULES["검은별무늬병"]["min_score"])
        svc.upsert(
            "OR001",
            user_id=None,
            pest_nm="검은별무늬병",
            param_key="min_score",
            param_value=str(sys_min + 1),
            actor_id="admin",
            as_farm_default=True,
        )
        svc.upsert(
            "OR001",
            user_id="u1",
            pest_nm="검은별무늬병",
            param_key="min_score",
            param_value=str(sys_min + 5),
            actor_id="u1",
            as_farm_default=False,
        )
        farm_rules = svc.resolve_pest_rules("OR001", None)
        user_rules = svc.resolve_pest_rules("OR001", "u1")
        self.assertEqual(
            int(farm_rules["검은별무늬병"]["min_score"]), sys_min + 1
        )
        self.assertEqual(
            int(user_rules["검은별무늬병"]["min_score"]), sys_min + 5
        )

    def test_efficacy_days_in_system_defaults(self) -> None:
        from core.pest_outbreak_param_service import PestOutbreakParamService

        svc = PestOutbreakParamService(self.bridge)
        defaults = svc.list_system_defaults()
        self.assertTrue(
            any(
                d["pest_nm"] == "응애" and d["param_key"] == "efficacy_days"
                for d in defaults
            )
        )

    def test_parse_month_formats(self) -> None:
        from core.pest_outbreak_param_value import eval_rule_value, parse_param_value

        single = parse_param_value("5", param_key="current_month")
        self.assertEqual(single.op, "==")
        self.assertEqual(single.value, 5)
        self.assertTrue(eval_rule_value(5, single.op, single.value))
        self.assertFalse(eval_rule_value(6, single.op, single.value))

        rng = parse_param_value("5~9", param_key="current_month")
        self.assertEqual(rng.op, "in_range")
        self.assertEqual(rng.value, (5, 9))
        self.assertTrue(eval_rule_value(6, rng.op, rng.value))
        self.assertFalse(eval_rule_value(4, rng.op, rng.value))

        st = parse_param_value("5,7,9", param_key="current_month")
        self.assertEqual(st.op, "in_set")
        self.assertEqual(st.value, [5, 7, 9])
        self.assertTrue(eval_rule_value(7, st.op, st.value))
        self.assertFalse(eval_rule_value(6, st.op, st.value))

    def test_parse_compare_prefix(self) -> None:
        from core.pest_outbreak_param_value import parse_param_value

        p = parse_param_value("<=5", param_key="rain_sum_7d")
        self.assertEqual(p.op, "<=")
        self.assertEqual(p.value, 5)
        self.assertEqual(p.display_value, "5")

    def test_resolve_month_range_overlay(self) -> None:
        from core.pest_outbreak_param_service import PestOutbreakParamService
        from core.pest_outbreak_param_value import eval_rule_value

        svc = PestOutbreakParamService(self.bridge)
        svc.upsert(
            "OR001",
            user_id="u1",
            pest_nm="미국선녀벌레",
            param_key="current_month",
            param_value="5~9",
            actor_id="u1",
            as_farm_default=False,
        )
        rules = svc.resolve_pest_rules("OR001", "u1")
        month_rules = [
            r
            for r in rules["미국선녀벌레"]["rules"]
            if r.get("field") == "current_month"
        ]
        self.assertEqual(len(month_rules), 1)
        self.assertEqual(month_rules[0]["op"], "in_range")
        self.assertTrue(
            eval_rule_value(7, month_rules[0]["op"], month_rules[0]["value"])
        )

    def test_list_includes_op_and_example(self) -> None:
        from core.pest_outbreak_param_service import PestOutbreakParamService

        svc = PestOutbreakParamService(self.bridge)
        rows = svc.list_rows("OR001", user_id="u1", scope="effective")
        rain = next(
            r
            for r in rows
            if r["pest_nm"] == "검은별무늬병" and r["param_key"] == "rain_sum_7d"
        )
        self.assertTrue(rain.get("compare_enabled"))
        self.assertIn(rain.get("param_op"), (">=", "<="))
        self.assertTrue(rain.get("example"))

    def test_overlay_preserves_secondary_rain_threshold(self) -> None:
        """동일 field 복수 규칙 시 첫 규칙만 덮어 2차 임계값 유지."""
        from core.pest_outbreak_param_service import PestOutbreakParamService

        svc = PestOutbreakParamService(self.bridge)
        svc.upsert(
            "OR001",
            user_id="u1",
            pest_nm="검은별무늬병",
            param_key="rain_sum_7d",
            param_value=">=45",
            actor_id="u1",
            as_farm_default=False,
        )
        rules = [
            r
            for r in svc.resolve_pest_rules("OR001", "u1")["검은별무늬병"]["rules"]
            if r.get("field") == "rain_sum_7d"
        ]
        self.assertGreaterEqual(len(rules), 2)
        self.assertEqual(rules[0]["op"], ">=")
        self.assertEqual(rules[0]["value"], 45)
        self.assertEqual(rules[1]["value"], 60)

    def test_mite_system_month_range(self) -> None:
        from core.pest_outbreak_param_service import PestOutbreakParamService
        from core.pest_outbreak_param_value import eval_rule_value

        svc = PestOutbreakParamService(self.bridge)
        rows = svc.list_system_defaults()
        mite_month = next(
            r
            for r in rows
            if r["pest_nm"] == "응애" and r["param_key"] == "current_month"
        )
        self.assertEqual(mite_month["param_value"], "6~9")
        rules = svc.resolve_pest_rules("OR001", None)["응애"]["rules"]
        month = next(r for r in rules if r.get("field") == "current_month")
        self.assertEqual(month["op"], "in_range")
        self.assertTrue(eval_rule_value(7, month["op"], month["value"]))
        self.assertFalse(eval_rule_value(5, month["op"], month["value"]))

    def test_pest_dict_seed_matches_pest_rules(self) -> None:
        """모바일 병해충사전 시드명·min·잔효가 PEST_RULES와 일치하는지."""
        import re
        from pathlib import Path

        from core.pesticide_ai_recommend_manager import PEST_RULES

        path = (
            Path(__file__).resolve().parents[2]
            / "mobile"
            / "src"
            / "features"
            / "pesticide"
            / "pestDictConstants.ts"
        )
        text = path.read_text(encoding="utf-8")
        # TEMP_PEST_DICT 블록만
        block = text.split("export const TEMP_PEST_DICT")[1].split(
            "export function filterPestDict"
        )[0]
        names = re.findall(r"pest_nm:\s*'([^']+)'", block)
        mins = [int(x) for x in re.findall(r"min_score:\s*(\d+)", block)]
        effs = [int(x) for x in re.findall(r"efficacy_days:\s*(\d+)", block)]
        self.assertEqual(names, list(PEST_RULES.keys()))
        self.assertEqual(len(names), len(mins), len(effs))
        for i, nm in enumerate(names):
            spec = PEST_RULES[nm]
            self.assertEqual(mins[i], int(spec["min_score"]), nm)
            self.assertEqual(effs[i], int(spec["efficacy_days"]), nm)

    def test_parse_temp_range(self) -> None:
        from core.pest_outbreak_param_value import eval_rule_value, parse_param_value

        p = parse_param_value("22~25", param_key="avg_temp_3d")
        self.assertEqual(p.op, "in_range")
        self.assertEqual(p.value, (22, 25))
        self.assertTrue(eval_rule_value(23, p.op, p.value))
        self.assertTrue(eval_rule_value(25, p.op, p.value))
        self.assertFalse(eval_rule_value(21, p.op, p.value))
        self.assertFalse(eval_rule_value(30, p.op, p.value))

    def test_uslf_temp_system_default_and_scoring(self) -> None:
        from core.pest_outbreak_param_service import PestOutbreakParamService
        from core.pest_outbreak_param_value import eval_rule_value

        svc = PestOutbreakParamService(self.bridge)
        rows = svc.list_system_defaults()
        temp = next(
            r
            for r in rows
            if r["pest_nm"] == "미국선녀벌레" and r["param_key"] == "avg_temp_3d"
        )
        self.assertEqual(temp["param_value"], "22~25")
        self.assertFalse(temp.get("compare_enabled"))
        self.assertEqual(temp.get("param_op"), "match")

        month = next(
            r
            for r in rows
            if r["pest_nm"] == "미국선녀벌레" and r["param_key"] == "current_month"
        )
        self.assertEqual(month["param_value"], "5~9")

        rules = [
            r
            for r in svc.resolve_pest_rules("OR001", None)["미국선녀벌레"]["rules"]
            if r.get("field") == "avg_temp_3d"
        ]
        self.assertGreaterEqual(len(rules), 2)
        self.assertEqual(rules[0]["op"], "in_range")
        self.assertEqual(rules[0]["value"], (22, 25))
        self.assertEqual(rules[1]["op"], ">=")
        self.assertEqual(rules[1]["value"], 25)
        self.assertTrue(eval_rule_value(23, rules[0]["op"], rules[0]["value"]))
        self.assertFalse(eval_rule_value(23, rules[1]["op"], rules[1]["value"]))
        self.assertTrue(eval_rule_value(25, rules[0]["op"], rules[0]["value"]))
        self.assertTrue(eval_rule_value(25, rules[1]["op"], rules[1]["value"]))

    def test_season_gate_off_season_zero(self) -> None:
        from core.pesticide_ai_recommend_manager import (
            REASON_OFF_SEASON,
            PesticideAIRecommendManager,
        )

        mgr = PesticideAIRecommendManager(None)
        # 기상은 충족해도 10월이면 미국선녀 0
        ctx = {
            "current_month": 10,
            "avg_temp_3d": 28,
            "rain_sum_7d": 0,
            "rain_days_7d": 0,
            "avg_humidity_7d": 50,
        }
        rows = {r["pest_nm"]: r for r in mgr.calculate_pest_scores(ctx)}
        self.assertEqual(rows["미국선녀벌레"]["score"], 0)
        self.assertEqual(rows["미국선녀벌레"]["reasons"], [REASON_OFF_SEASON])
        self.assertEqual(rows["응애"]["score"], 0)
        self.assertEqual(rows["응애"]["reasons"], [REASON_OFF_SEASON])

    def test_season_gate_in_season_scores(self) -> None:
        from core.pesticide_ai_recommend_manager import PesticideAIRecommendManager

        mgr = PesticideAIRecommendManager(None)
        ctx = {
            "current_month": 7,
            "avg_temp_3d": 26,
            "rain_sum_7d": 0,
            "rain_days_7d": 0,
            "avg_humidity_7d": 50,
        }
        rows = {r["pest_nm"]: r for r in mgr.calculate_pest_scores(ctx)}
        uslf = rows["미국선녀벌레"]
        self.assertGreater(uslf["score"], 0)
        self.assertNotIn("발병 시즌 외", uslf["reasons"])
        # 5~9 +2, 기온 in_range 22~25? 26은 미통과, >=25 +1 → 최소 3
        self.assertGreaterEqual(uslf["score"], 3)

    def test_scale_insect_season_default(self) -> None:
        from core.pest_outbreak_param_service import PestOutbreakParamService

        svc = PestOutbreakParamService(self.bridge)
        row = next(
            r
            for r in svc.list_system_defaults()
            if r["pest_nm"] == "깍지벌레" and r["param_key"] == "current_month"
        )
        self.assertEqual(row["param_value"], "4~8")


if __name__ == "__main__":
    unittest.main()
