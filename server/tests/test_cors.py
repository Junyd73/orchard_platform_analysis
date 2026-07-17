# -*- coding: utf-8 -*-
"""CORS 설정 회귀 테스트."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import get_settings, parse_cors_origins
from app.main import app

client = TestClient(app)


def test_parse_cors_origins_trims_and_drops_empty() -> None:
    assert parse_cors_origins(" http://a.com , ,http://b.com ") == [
        "http://a.com",
        "http://b.com",
    ]
    assert parse_cors_origins([]) == []


def test_settings_cors_list_from_env() -> None:
    get_settings.cache_clear()
    origins = get_settings().cors_origin_list
    assert isinstance(origins, list)
    assert all(isinstance(x, str) and x for x in origins)
    assert "*" not in origins or get_settings().app_env.lower() in {
        "development",
        "dev",
        "local",
        "test",
    }


def test_preflight_allowed_origin() -> None:
    get_settings.cache_clear()
    allowed = get_settings().cors_origin_list
    assert allowed, "CORS_ORIGINS 가 비어 있으면 안 됩니다"
    origin = allowed[0]
    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code in (200, 204)
    assert response.headers.get("access-control-allow-origin") == origin


def test_disallowed_origin_not_reflected() -> None:
    bad = "http://evil.example"
    get_settings.cache_clear()
    assert bad not in get_settings().cors_origin_list
    response = client.get(
        "/api/v1/health",
        headers={"Origin": bad},
    )
    # 요청 자체는 성공할 수 있으나, 허용 Origin이 헤더에 반영되면 안 됨
    assert response.status_code == 200
    allow = response.headers.get("access-control-allow-origin")
    assert allow != bad
    assert allow != "*"
