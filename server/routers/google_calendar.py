# -*- coding: utf-8 -*-
"""구글 캘린더 OAuth·명시적 연동 라우터 — WLS-001 Phase4."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel

from app.api.dependencies import get_google_calendar_service
from app.services.google_calendar_service import GoogleCalendarService

router = APIRouter(tags=["google-calendar"])


def _user_header(
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> str | None:
    return x_user_id


class GoogleAuthUrlRequest(BaseModel):
    success_redirect: str | None = None


class GoogleStatusResponse(BaseModel):
    configured: bool
    connected: bool
    connected_email: str | None = None
    calendar_id: str = "primary"


class GoogleImportConfirmRequest(BaseModel):
    google_event_id: str
    work_dt: str
    kind: str | None = None
    title: str | None = None
    description: str | None = None
    start_tm: str | None = None
    end_tm: str | None = None
    work_mid_cd: str | None = None
    work_loc_id: str | None = None
    status_cd: str | None = None
    work_id: str | None = None
    sched_id: str | None = None


@router.get(
    "/farms/{farm_cd}/google-calendar/status",
    response_model=GoogleStatusResponse,
)
def google_calendar_status(
    farm_cd: str,
    service: GoogleCalendarService = Depends(get_google_calendar_service),
) -> GoogleStatusResponse:
    data = service.status(farm_cd)
    return GoogleStatusResponse(**data)


@router.post("/farms/{farm_cd}/google-calendar/auth-url")
def google_calendar_auth_url(
    farm_cd: str,
    body: GoogleAuthUrlRequest | None = None,
    user_id: str | None = Depends(_user_header),
    service: GoogleCalendarService = Depends(get_google_calendar_service),
) -> dict:
    req = body or GoogleAuthUrlRequest()
    return service.build_auth_url(
        farm_cd,
        user_id=user_id,
        success_redirect=req.success_redirect,
    )


@router.get("/google-calendar/oauth/callback")
def google_calendar_oauth_callback(
    code: str = Query(...),
    state: str = Query(...),
    service: GoogleCalendarService = Depends(get_google_calendar_service),
) -> RedirectResponse:
    url = service.handle_oauth_callback(code=code, state=state)
    return RedirectResponse(url=url, status_code=302)


@router.post("/farms/{farm_cd}/google-calendar/disconnect")
def google_calendar_disconnect(
    farm_cd: str,
    user_id: str | None = Depends(_user_header),
    service: GoogleCalendarService = Depends(get_google_calendar_service),
) -> dict:
    return service.disconnect(farm_cd, user_id=user_id)


@router.post("/farms/{farm_cd}/google-calendar/works/{work_id}/push")
def google_calendar_push_work(
    farm_cd: str,
    work_id: str,
    user_id: str | None = Depends(_user_header),
    service: GoogleCalendarService = Depends(get_google_calendar_service),
) -> dict:
    return service.push_work(farm_cd, work_id, user_id=user_id)


@router.post("/farms/{farm_cd}/google-calendar/schedules/{sched_id}/push")
def google_calendar_push_schedule_gone(
    farm_cd: str,
    sched_id: str,
) -> JSONResponse:
    return JSONResponse(
        status_code=410,
        content={
            "success": False,
            "message": (
                "예정 일정 push는 폐기되었습니다. "
                "작업(준비중) 저장 후 works/{work_id}/push를 사용해 주세요."
            ),
            "error_code": "WORK_SCHEDULE_PUSH_GONE",
        },
    )


@router.get("/farms/{farm_cd}/google-calendar/import-preview")
def google_calendar_import_preview(
    farm_cd: str,
    work_dt: str = Query(...),
    service: GoogleCalendarService = Depends(get_google_calendar_service),
) -> dict:
    return service.preview_import(farm_cd, work_dt)


@router.post("/farms/{farm_cd}/google-calendar/import-confirm")
def google_calendar_import_confirm(
    farm_cd: str,
    body: GoogleImportConfirmRequest,
    user_id: str | None = Depends(_user_header),
    service: GoogleCalendarService = Depends(get_google_calendar_service),
) -> dict:
    return service.confirm_import(
        farm_cd,
        body.model_dump(),
        user_id=user_id,
    )
