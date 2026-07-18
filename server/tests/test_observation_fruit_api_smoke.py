# -*- coding: utf-8 -*-
"""과실 측정·추적 REST 스모크 테스트."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

_REPO = Path(__file__).resolve().parents[1]
_SERVER = _REPO / "server"
for p in (_SERVER, _REPO):
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)

from app.schemas.observation_fruit import FruitMeasurementUpsertRequest  # noqa: E402
from app.services.observation_fruit_api_service import (  # noqa: E402
    ObservationFruitApiService,
    _delta,
)


class DeltaTests(unittest.TestCase):
    def test_delta(self):
        self.assertEqual(_delta(10, 8), 2.0)
        self.assertIsNone(_delta(None, 8))
        self.assertIsNone(_delta(10, None))


class ServiceSmokeTests(unittest.TestCase):
    def test_service_construct(self):
        svc = ObservationFruitApiService(
            db_path=_REPO / "orchard_platform.db",
            photo_repo=MagicMock(),
        )
        self.assertTrue(hasattr(svc, "list_track"))
        body = FruitMeasurementUpsertRequest(width_mm=50.0)
        self.assertEqual(body.width_mm, 50.0)


if __name__ == "__main__":
    unittest.main()
