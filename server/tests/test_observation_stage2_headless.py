# -*- coding: utf-8 -*-
"""Stage2 headless — PyQt 없이 import·과실 upsert 회귀."""

from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

_SERVER = Path(__file__).resolve().parents[1]
_REPO = _SERVER.parent
# 저장소 루트 app/ 이 server/app 을 가리지 않도록 server 를 앞에 둔다
for p in (str(_SERVER), str(_REPO)):
    if p in sys.path:
        sys.path.remove(p)
sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(_SERVER))


class ObservationStage2HeadlessTests(unittest.TestCase):
    def test_import_stage2_without_pyqt(self) -> None:
        if "core.db_manager" in sys.modules:
            del sys.modules["core.db_manager"]
        if "core.observation_stage2" in sys.modules:
            del sys.modules["core.observation_stage2"]

        import core.observation_stage2 as stage2  # noqa: WPS433

        self.assertTrue(hasattr(stage2, "save_fruit_measurement"))
        self.assertNotIn("core.db_manager", sys.modules)

    def test_fruit_api_import_stage2(self) -> None:
        from app.services.observation_fruit_api_service import (  # noqa: WPS433
            _import_stage2,
        )

        stage2 = _import_stage2()
        self.assertTrue(callable(stage2.save_fruit_measurement))

    def test_constants_ssot_values(self) -> None:
        from core import observation_stage2_constants as c  # noqa: WPS433
        import core.observation_stage2 as stage2  # noqa: WPS433

        self.assertEqual(c.OBS_SHOT_PARENT_CD, "OH01")
        self.assertEqual(c.OBS_FRUIT_SHAPE_PARENT_CD, "FS01")
        self.assertEqual(c.OBS_FRUIT_COLOR_PARENT_CD, "FC01")
        self.assertEqual(c.OBS_STALK_PARENT_CD, "FK01")
        self.assertEqual(c.OBS_CALYX_PARENT_CD, "FY01")
        self.assertEqual(c.OBS_TARGET_FRUIT_CD, "OB010200")
        self.assertEqual(c.OBS_PROGRESS_DONE_CDS, frozenset({"OP010400", "OP010500"}))
        self.assertEqual(
            c.OBS_SEVERITY_RANK,
            {
                "OS010100": 1,
                "OS010200": 2,
                "OS010300": 3,
                "OS010400": 4,
            },
        )
        self.assertIs(stage2.OBS_TARGET_FRUIT_CD, c.OBS_TARGET_FRUIT_CD)
        self.assertEqual(stage2.OBS_SEVERITY_RANK, c.OBS_SEVERITY_RANK)

    def test_db_manager_constants_match_ssot_with_mocked_pyqt(self) -> None:
        """PC DBManager 클래스 상수가 SSOT와 동일한지 (PyQt는 mock)."""
        import types

        def _ensure_mod(name: str):
            if name not in sys.modules:
                sys.modules[name] = types.ModuleType(name)
            return sys.modules[name]

        pyqt = _ensure_mod("PyQt6")
        qtcore = _ensure_mod("PyQt6.QtCore")
        for attr in ("QDate", "Qt", "QTimer", "QTime"):
            setattr(qtcore, attr, type(attr, (), {}))
        qtw = _ensure_mod("PyQt6.QtWidgets")
        qtg = _ensure_mod("PyQt6.QtGui")
        pyqt.QtCore = qtcore
        pyqt.QtWidgets = qtw
        pyqt.QtGui = qtg

        for mod in list(sys.modules):
            if mod == "core.db_manager" or mod.startswith("core.db_manager."):
                del sys.modules[mod]

        from core import observation_stage2_constants as c  # noqa: WPS433
        from core.db_manager import DBManager  # noqa: WPS433

        self.assertEqual(DBManager.OBS_TARGET_FRUIT_CD, c.OBS_TARGET_FRUIT_CD)
        self.assertEqual(DBManager.OBS_SHOT_PARENT_CD, c.OBS_SHOT_PARENT_CD)
        self.assertEqual(DBManager.OBS_FRUIT_SHAPE_PARENT_CD, c.OBS_FRUIT_SHAPE_PARENT_CD)
        self.assertEqual(DBManager.OBS_FRUIT_COLOR_PARENT_CD, c.OBS_FRUIT_COLOR_PARENT_CD)
        self.assertEqual(DBManager.OBS_STALK_PARENT_CD, c.OBS_STALK_PARENT_CD)
        self.assertEqual(DBManager.OBS_CALYX_PARENT_CD, c.OBS_CALYX_PARENT_CD)
        self.assertEqual(DBManager.OBS_PROGRESS_DONE_CDS, c.OBS_PROGRESS_DONE_CDS)
        self.assertEqual(DBManager.OBS_SEVERITY_RANK, c.OBS_SEVERITY_RANK)

    def test_save_fruit_measurement_upsert(self) -> None:
        from app.services.observation_ai_db_bridge import ServerDbBridge  # noqa: WPS433
        import core.observation_stage2 as stage2  # noqa: WPS433

        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            conn = sqlite3.connect(path)
            conn.row_factory = sqlite3.Row
            conn.executescript(
                """
                CREATE TABLE m_farm_site (farm_cd TEXT, site_id TEXT, site_nm TEXT);
                CREATE TABLE m_common_code (farm_cd TEXT, code_cd TEXT, code_nm TEXT);
                CREATE TABLE t_observation_master (
                    farm_cd TEXT, obs_id TEXT, use_yn TEXT, target_type_cd TEXT,
                    obs_type_cd TEXT, severity_cd TEXT, progress_status_cd TEXT,
                    site_id TEXT,
                    PRIMARY KEY(farm_cd, obs_id)
                );
                INSERT INTO t_observation_master VALUES (
                    'OR001','OBS20260817-001','Y','OB010200',
                    'OY010300','OS010100','OP010100', NULL
                );
                """
            )
            conn.commit()
            db = ServerDbBridge(conn)
            stage2._ensure_observation_fruit_table(db)

            ok, msg = stage2.save_fruit_measurement(
                db,
                "OR001",
                "OBS20260817-001",
                {
                    "width_mm": 70.5,
                    "height_mm": 65.0,
                    "asymmetry_level": 2,
                    "spot_yn": "Y",
                    "wound_yn": "N",
                    "shape_cd": "FS010100",
                    "skin_color_cd": "FC010100",
                    "stalk_status_cd": "FK010100",
                    "calyx_status_cd": "FY010100",
                    "fruit_rmk": "headless upsert",
                },
                "TEST_USER",
            )
            self.assertTrue(ok, msg)
            row = stage2.get_fruit_measurement(db, "OR001", "OBS20260817-001")
            self.assertIsNotNone(row)
            assert row is not None
            self.assertEqual(float(row["width_mm"]), 70.5)
            self.assertEqual(int(row["asymmetry_level"]), 2)
            self.assertEqual(row["spot_yn"], "Y")
            self.assertEqual(row["fruit_rmk"], "headless upsert")

            ok2, msg2 = stage2.save_fruit_measurement(
                db,
                "OR001",
                "OBS20260817-001",
                {
                    "width_mm": 71.0,
                    "asymmetry_level": 3,
                    "spot_yn": "N",
                    "fruit_rmk": "updated",
                },
                "TEST_USER",
            )
            self.assertTrue(ok2, msg2)
            row2 = stage2.get_fruit_measurement(db, "OR001", "OBS20260817-001")
            assert row2 is not None
            self.assertEqual(float(row2["width_mm"]), 71.0)
            self.assertEqual(int(row2["asymmetry_level"]), 3)
            self.assertEqual(row2["fruit_rmk"], "updated")
            conn.close()
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
