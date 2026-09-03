# -*- coding: utf-8 -*-
"""SQLITE_DB_PATH process env 우선순위 (Mobile TEST launcher)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest


def _touch_sqlite(path: Path) -> None:
    conn = sqlite3.connect(str(path))
    conn.execute("CREATE TABLE IF NOT EXISTS _probe (id INTEGER)")
    conn.commit()
    conn.close()


def test_process_env_overrides_env_file(monkeypatch, tmp_path: Path) -> None:
    """Mobile TEST launcher: process SQLITE_DB_PATH가 server/.env보다 우선."""
    from app.core.config import Settings, get_settings

    db_a = tmp_path / "mobile_test.db"
    db_b = tmp_path / "pc_dev.db"
    _touch_sqlite(db_a)
    _touch_sqlite(db_b)

    monkeypatch.setenv("SQLITE_DB_PATH", str(db_a))
    monkeypatch.setenv("DB_HOST", "localhost")
    monkeypatch.setenv("DB_PORT", "5432")
    monkeypatch.setenv("DB_NAME", "orchard_platform")
    monkeypatch.setenv("DB_USER", "orchard_admin")
    monkeypatch.setenv("DB_PASSWORD", "test")

    get_settings.cache_clear()
    settings = Settings(_env_file=tmp_path / "missing.env")
    assert str(settings.sqlite_path) == str(db_a.resolve())

    monkeypatch.setenv("SQLITE_DB_PATH", str(db_b))
    get_settings.cache_clear()
    settings_b = Settings(_env_file=tmp_path / "missing.env")
    assert str(settings_b.sqlite_path) == str(db_b.resolve())

    get_settings.cache_clear()
