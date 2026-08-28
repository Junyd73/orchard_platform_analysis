# -*- coding: utf-8 -*-
"""PC HARVEST N:M client helper (ui.production_harvest_helper) unit tests."""

from __future__ import annotations

from core.production_service import ProductionError
from ui.production_harvest_helper import (
    build_harvest_consumptions,
    can_select_harvest_row,
    format_harvest_row_label,
    harvest_selection_anchor,
    harvest_selection_summary,
    is_harvest_selectable,
    map_production_harvest_error,
    validate_harvest_client_selections,
    MSG_HARVEST_UI_EXCEED,
    MSG_HARVEST_UI_MIXED_VARIETY,
    MSG_HARVEST_UI_MIXED_YEAR,
)


def _row(
    work_id: str,
    *,
    variety_cd: str = "FR010101",
    harvest_year: int = 2026,
    original: int = 30,
    consumed: int = 0,
    remaining: int | None = None,
) -> dict:
    rem = original - consumed if remaining is None else remaining
    return {
        "work_id": work_id,
        "work_dt": "2026-08-27",
        "variety_cd": variety_cd,
        "variety_nm": "신고",
        "harvest_year": harvest_year,
        "harvest_container_qty": original,
        "consumed_container_qty": consumed,
        "remaining_container_qty": rem,
    }


class TestProductionHarvestClientHelper:
    def test_remaining_display_and_selectable(self) -> None:
        row = _row("A", original=30, consumed=20, remaining=10)
        assert is_harvest_selectable(row) is True
        assert "수확 30 · 사용 20 · 남음 10" in format_harvest_row_label(row)
        assert is_harvest_selectable(_row("Z", remaining=0)) is False

    def test_build_nm_consumptions(self) -> None:
        rows = {
            "A": _row("A", remaining=10),
            "B": _row("B", original=40, remaining=40),
        }
        selections = {"A": 8, "B": 15}
        items = build_harvest_consumptions(rows, selections)
        assert [(i.work_id, i.qty) for i in items] == [("A", 8), ("B", 15)]

    def test_validate_exceed_and_mixed(self) -> None:
        rows = {
            "A": _row("A", variety_cd="FR010101", harvest_year=2026, remaining=10),
            "B": _row("B", variety_cd="FR010102", harvest_year=2026, remaining=40),
        }
        assert validate_harvest_client_selections(rows, {"A": 11}) == MSG_HARVEST_UI_EXCEED
        assert (
            validate_harvest_client_selections(rows, {"A": 5, "B": 5})
            == MSG_HARVEST_UI_MIXED_VARIETY
        )
        rows["B"]["variety_cd"] = "FR010101"
        rows["B"]["harvest_year"] = 2027
        assert (
            validate_harvest_client_selections(rows, {"A": 5, "B": 5})
            == MSG_HARVEST_UI_MIXED_YEAR
        )

    def test_can_select_harvest_row_anchor(self) -> None:
        anchor = _row("A")
        ok, msg = can_select_harvest_row(_row("B", variety_cd="FR010102"), anchor)
        assert ok is False
        assert msg == MSG_HARVEST_UI_MIXED_VARIETY

    def test_summary_and_error_map(self) -> None:
        assert harvest_selection_summary({"A": 20, "B": 15}) == "수확기록 2건 · 사용 35상자"
        assert harvest_selection_anchor({"A": _row("A")}, {"A": 5}) is not None
        assert map_production_harvest_error(
            ProductionError("x", code="HARVEST_EXCEED"),
        ) == MSG_HARVEST_UI_EXCEED
