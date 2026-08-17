# -*- coding: utf-8 -*-
"""Analysis 미러 preflight 회귀 테스트."""

from __future__ import annotations

from pathlib import Path

from scripts.mirror._manifest import collect_mirror_files, collect_mirror_pairs
from scripts.mirror.preflight import run_preflight

_REPO = Path(__file__).resolve().parents[2]


def test_manifest_collects_mobile_ods() -> None:
    files = collect_mirror_files(_REPO)
    assert any("mobile/src/components/ods" in f for f in files)
    assert any("mobile/docs/ODS" in f for f in files)
    assert any(f.endswith("tokens.css") for f in files)


def test_features_map_to_views() -> None:
    pairs = collect_mirror_pairs(_REPO)
    mapped = {src: dest for src, dest in pairs}
    assert "mobile/src/features/home/HomeView.vue" in mapped
    assert mapped["mobile/src/features/home/HomeView.vue"].startswith(
        "mobile/src/views/"
    )


def test_excludes_api_client_and_env() -> None:
    files = collect_mirror_files(_REPO)
    assert not any(f.startswith("mobile/src/api/") for f in files)
    assert not any(".env" in f for f in files)


def test_manifest_includes_pc_observation_ai() -> None:
    files = collect_mirror_files(_REPO)
    assert any(f.startswith("core/ai/") for f in files)
    assert "core/observation_stage3.py" in files
    assert "ui/widgets/observation/ai_analysis_panel.py" in files
    assert "ui/widgets/observation/ai_analysis_worker.py" in files
    assert not any(".orchard.env" in f for f in files)


def test_manifest_includes_mobile_order_sales_docs() -> None:
    files = collect_mirror_files(_REPO)
    expected = [
        "docs/mobile_order_sales/README.md",
        "docs/mobile_order_sales/01_overview.md",
        "docs/mobile_order_sales/02_domain_flow.md",
        "docs/mobile_order_sales/03_data_contract.md",
        "docs/mobile_order_sales/04_mobile_screen.md",
        "docs/mobile_order_sales/05_api_contract.md",
        "docs/mobile_order_sales/06_development_progress.md",
        "docs/mobile_order_sales/07_decisions.md",
        "docs/mobile_order_sales/08_pc_change_scope.md",
    ]
    for rel in expected:
        assert rel in files
    pairs = dict(collect_mirror_pairs(_REPO))
    for rel in expected:
        assert pairs[rel] == rel


def test_preflight_passes_on_whitelist() -> None:
    assert run_preflight(_REPO) == 0
