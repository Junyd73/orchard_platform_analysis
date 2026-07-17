# -*- coding: utf-8 -*-
"""SqliteFarmRepository 단위 테스트 (임시 DB, 운영 DB 미변경)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.core.exceptions import EntityNotFoundError
from app.repository.sqlite.farm_repository import SqliteFarmRepository


@pytest.fixture()
def farm_db(tmp_path: Path) -> Path:
    db = tmp_path / "farm_test.db"
    conn = sqlite3.connect(db)
    try:
        conn.executescript(
            """
            CREATE TABLE m_farm_info (
                farm_cd TEXT PRIMARY KEY,
                farm_nm TEXT,
                owner_nm TEXT,
                address TEXT,
                lat REAL,
                lon REAL,
                nx INTEGER,
                ny INTEGER,
                reg_dt TEXT
            );
            CREATE TABLE m_farm_site (
                site_id TEXT PRIMARY KEY,
                farm_cd TEXT,
                site_nm TEXT,
                use_yn TEXT DEFAULT 'Y',
                reg_id TEXT,
                reg_dt TEXT,
                mod_id TEXT,
                mod_dt TEXT
            );
            INSERT INTO m_farm_info (farm_cd, farm_nm, owner_nm, address, lat, lon, nx, ny, reg_dt)
            VALUES ('OR001', '테스트농장', '홍길동', '주소', 36.1, 128.2, 1, 2, '2026-01-01');
            INSERT INTO m_farm_site (site_id, farm_cd, site_nm, use_yn, reg_dt)
            VALUES
                ('SITE01', 'OR001', '1구역', 'Y', '2026-01-01'),
                ('SITE02', 'OR001', '중단구역', 'N', '2026-01-02'),
                ('SITE99', 'OR999', '타농장', 'Y', '2026-01-03');
            """
        )
        conn.commit()
    finally:
        conn.close()
    return db


def test_get_farm_ok(farm_db: Path) -> None:
    repo = SqliteFarmRepository(farm_db)
    farm = repo.get_farm("OR001")
    assert farm.farm_cd == "OR001"
    assert farm.farm_nm == "테스트농장"
    assert farm.nx == 1


def test_get_farm_not_found(farm_db: Path) -> None:
    repo = SqliteFarmRepository(farm_db)
    with pytest.raises(EntityNotFoundError):
        repo.get_farm("NOPE")


def test_list_sites_active_only(farm_db: Path) -> None:
    repo = SqliteFarmRepository(farm_db)
    active = repo.list_sites("OR001", active_only=True)
    assert [s.site_id for s in active] == ["SITE01"]
    all_sites = repo.list_sites("OR001", active_only=False)
    assert {s.site_id for s in all_sites} == {"SITE01", "SITE02"}


def test_list_sites_farm_isolation(farm_db: Path) -> None:
    repo = SqliteFarmRepository(farm_db)
    sites = repo.list_sites("OR001", active_only=False)
    assert all(s.site_id != "SITE99" for s in sites)


def test_get_site_ok_and_missing(farm_db: Path) -> None:
    repo = SqliteFarmRepository(farm_db)
    site = repo.get_site("OR001", "SITE01")
    assert site.site_nm == "1구역"
    with pytest.raises(EntityNotFoundError):
        repo.get_site("OR001", "SITE99")  # 타 농장 격리
    with pytest.raises(EntityNotFoundError):
        repo.get_site("OR001", "MISSING")
