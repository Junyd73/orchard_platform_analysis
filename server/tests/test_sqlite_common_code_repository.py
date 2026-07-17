# -*- coding: utf-8 -*-
"""SqliteCommonCodeRepository 단위 테스트 (임시 DB)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.repository.sqlite.common_code_repository import SqliteCommonCodeRepository


@pytest.fixture()
def code_db(tmp_path: Path) -> Path:
    db = tmp_path / "code_test.db"
    conn = sqlite3.connect(db)
    try:
        conn.executescript(
            """
            CREATE TABLE m_common_code (
                farm_cd TEXT,
                code_cd TEXT,
                code_nm TEXT NOT NULL,
                parent_cd TEXT,
                use_yn TEXT DEFAULT 'Y',
                PRIMARY KEY (farm_cd, code_cd)
            );
            INSERT INTO m_common_code (farm_cd, code_cd, code_nm, parent_cd, use_yn) VALUES
                ('OR001', 'WT0101', '맑음', 'WT01', 'Y'),
                ('OR001', 'WT0102', '비', 'WT01', 'Y'),
                ('OR001', 'WT0199', '폐기', 'WT01', 'N'),
                ('OR001', 'OB0101', '나무', 'OB01', 'Y'),
                ('OR002', 'WT0101', '타농장맑음', 'WT01', 'Y');
            """
        )
        conn.commit()
    finally:
        conn.close()
    return db


def test_list_codes_by_parent(code_db: Path) -> None:
    repo = SqliteCommonCodeRepository(code_db)
    rows = repo.list_codes("OR001", "WT01", active_only=True)
    codes = [r.code_cd for r in rows]
    assert codes == ["WT0101", "WT0102"]
    assert all(r.farm_cd == "OR001" for r in rows)


def test_list_codes_active_only_false(code_db: Path) -> None:
    repo = SqliteCommonCodeRepository(code_db)
    rows = repo.list_codes("OR001", "WT01", active_only=False)
    assert {r.code_cd for r in rows} == {"WT0101", "WT0102", "WT0199"}


def test_list_codes_requires_farm_and_parent(code_db: Path) -> None:
    repo = SqliteCommonCodeRepository(code_db)
    assert repo.list_codes("", "WT01") == []
    assert repo.list_codes("OR001", "") == []


def test_list_codes_farm_isolation(code_db: Path) -> None:
    repo = SqliteCommonCodeRepository(code_db)
    rows = repo.list_codes("OR001", "WT01", active_only=True)
    assert all(r.code_nm != "타농장맑음" for r in rows)
