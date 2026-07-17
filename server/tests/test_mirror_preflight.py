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


def test_preflight_passes_on_whitelist() -> None:
    assert run_preflight(_REPO) == 0
