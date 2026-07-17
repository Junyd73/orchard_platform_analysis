# -*- coding: utf-8 -*-
"""Health API 회귀 테스트 (TestClient)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.db.session import check_database_connection
from app.main import app

client = TestClient(app)


def test_root() -> None:
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body.get("status") == "running"
    assert "service" in body


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_api_v1_health() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def _db_available() -> bool:
    return check_database_connection().get("status") == "ok"


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL 연결 불가")
def test_health_db() -> None:
    response = client.get("/health/db")
    assert response.status_code == 200
    body = response.json()
    assert body.get("status") == "ok"
    assert body.get("database")
    assert body.get("user")


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL 연결 불가")
def test_api_v1_health_db() -> None:
    response = client.get("/api/v1/health/db")
    assert response.status_code == 200
    body = response.json()
    assert body.get("status") == "ok"
    assert body.get("database")
    assert body.get("user")
