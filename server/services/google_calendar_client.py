# -*- coding: utf-8 -*-
"""구글 OAuth2 · 캘린더 API 클라이언트 (httpx)."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

import httpx

from core.google_calendar_constants import (
    GOOGLE_AUTH_URL,
    GOOGLE_CALENDAR_API,
    GOOGLE_CALENDAR_ID_PRIMARY,
    GOOGLE_OAUTH_SCOPES,
    GOOGLE_REVOKE_URL,
    GOOGLE_TOKEN_URL,
)

logger = logging.getLogger(__name__)


class GoogleCalendarClientError(Exception):
    def __init__(self, message: str, *, code: str = "GOOGLE_API_ERROR"):
        super().__init__(message)
        self.message = message
        self.code = code


def build_authorization_url(
    *,
    client_id: str,
    redirect_uri: str,
    state: str,
) -> str:
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(GOOGLE_OAUTH_SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


def exchange_code_for_tokens(
    *,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    code: str,
) -> dict[str, Any]:
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
    if resp.status_code >= 400:
        raise GoogleCalendarClientError(
            f"토큰 교환 실패 ({resp.status_code})",
            code="TOKEN_EXCHANGE_FAILED",
        )
    return resp.json()


def refresh_access_token(
    *,
    client_id: str,
    client_secret: str,
    refresh_token: str,
) -> dict[str, Any]:
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
    if resp.status_code >= 400:
        raise GoogleCalendarClientError(
            f"토큰 갱신 실패 ({resp.status_code})",
            code="TOKEN_REFRESH_FAILED",
        )
    return resp.json()


def revoke_token(token: str) -> None:
    try:
        with httpx.Client(timeout=15.0) as client:
            client.post(GOOGLE_REVOKE_URL, params={"token": token})
    except Exception:  # noqa: BLE001
        logger.exception("google token revoke failed")


def fetch_user_email(access_token: str) -> str:
    with httpx.Client(timeout=15.0) as client:
        resp = client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
    if resp.status_code >= 400:
        return ""
    data = resp.json()
    return str(data.get("email") or "").strip()


def expiry_iso_from_expires_in(expires_in: int | None) -> str:
    sec = int(expires_in or 3600)
    dt = datetime.now(timezone.utc) + timedelta(seconds=max(60, sec - 60))
    return dt.isoformat()


def _auth_headers(access_token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def upsert_event(
    *,
    access_token: str,
    calendar_id: str,
    event_id: str | None,
    body: dict[str, Any],
) -> dict[str, Any]:
    cal = calendar_id or GOOGLE_CALENDAR_ID_PRIMARY
    with httpx.Client(timeout=30.0) as client:
        if event_id:
            resp = client.put(
                f"{GOOGLE_CALENDAR_API}/calendars/{cal}/events/{event_id}",
                headers=_auth_headers(access_token),
                json=body,
            )
        else:
            resp = client.post(
                f"{GOOGLE_CALENDAR_API}/calendars/{cal}/events",
                headers=_auth_headers(access_token),
                json=body,
            )
    if resp.status_code >= 400:
        raise GoogleCalendarClientError(
            f"이벤트 저장 실패 ({resp.status_code}): {resp.text[:200]}",
            code="EVENT_UPSERT_FAILED",
        )
    return resp.json()


def delete_event(
    *,
    access_token: str,
    calendar_id: str,
    event_id: str,
) -> None:
    cal = calendar_id or GOOGLE_CALENDAR_ID_PRIMARY
    with httpx.Client(timeout=30.0) as client:
        resp = client.delete(
            f"{GOOGLE_CALENDAR_API}/calendars/{cal}/events/{event_id}",
            headers=_auth_headers(access_token),
        )
    # 404 = 이미 없음 → 성공 취급
    if resp.status_code >= 400 and resp.status_code != 404:
        raise GoogleCalendarClientError(
            f"이벤트 삭제 실패 ({resp.status_code})",
            code="EVENT_DELETE_FAILED",
        )


def list_events(
    *,
    access_token: str,
    calendar_id: str,
    time_min: str,
    time_max: str,
    private_farm_cd: str | None = None,
) -> list[dict[str, Any]]:
    cal = calendar_id or GOOGLE_CALENDAR_ID_PRIMARY
    params: dict[str, Any] = {
        "singleEvents": "true",
        "orderBy": "startTime",
        "timeMin": time_min,
        "timeMax": time_max,
        "maxResults": 250,
    }
    if private_farm_cd:
        params["privateExtendedProperty"] = f"orchard_farm_cd={private_farm_cd}"
    out: list[dict[str, Any]] = []
    page_token: str | None = None
    with httpx.Client(timeout=30.0) as client:
        while True:
            p = dict(params)
            if page_token:
                p["pageToken"] = page_token
            resp = client.get(
                f"{GOOGLE_CALENDAR_API}/calendars/{cal}/events",
                headers=_auth_headers(access_token),
                params=p,
            )
            if resp.status_code >= 400:
                raise GoogleCalendarClientError(
                    f"이벤트 목록 실패 ({resp.status_code})",
                    code="EVENT_LIST_FAILED",
                )
            data = resp.json()
            out.extend(list(data.get("items") or []))
            page_token = data.get("nextPageToken")
            if not page_token:
                break
    return out
