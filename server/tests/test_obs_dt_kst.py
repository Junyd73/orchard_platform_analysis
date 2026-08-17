# -*- coding: utf-8 -*-
"""OPS 업무일(KST) · 관찰일자 미래일 검증 회귀."""

from __future__ import annotations

import sys
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_SERVER = Path(__file__).resolve().parents[1]
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

from app.core.exceptions import BusinessRuleError
from app.core.observation_constants import OBS_TARGET_FRUIT_CD
from app.core.ops_biz_date import today_ops
from app.schemas.observation import ObservationBasicCreateRequest
from app.services.observation_service import ObservationService

# UTC 2026-08-16 23:30 == KST 2026-08-17 08:30
_UTC_BOUNDARY = datetime(2026, 8, 16, 23, 30, tzinfo=timezone.utc)


def test_today_ops_kst_when_utc_is_previous_calendar_day() -> None:
    with patch("core.ops_biz_date.datetime") as mock_dt:
        mock_dt.now.side_effect = lambda tz=None: (
            _UTC_BOUNDARY.astimezone(tz) if tz is not None else _UTC_BOUNDARY
        )
        assert today_ops() == date(2026, 8, 17)


def test_normalize_basic_allows_kst_today_rejects_kst_tomorrow() -> None:
    svc = ObservationService(repo=MagicMock())
    site = "SITE1"

    with patch(
        "app.services.observation_service.today_ops",
        return_value=date(2026, 8, 17),
    ):
        ok_body = ObservationBasicCreateRequest(
            obs_dt="2026-08-17",
            target_type_cd=OBS_TARGET_FRUIT_CD,
            site_id=site,
            obs_title="KST 오늘",
            obs_content="허용",
        )
        row = svc._normalize_basic(ok_body)
        assert row["obs_dt"] == "2026-08-17"

        bad_body = ObservationBasicCreateRequest(
            obs_dt="2026-08-18",
            target_type_cd=OBS_TARGET_FRUIT_CD,
            site_id=site,
            obs_title="KST 내일",
            obs_content="차단",
        )
        with pytest.raises(BusinessRuleError) as exc:
            svc._normalize_basic(bad_body)
        assert "오늘까지만" in str(exc.value.message or exc.value)
