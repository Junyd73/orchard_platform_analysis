# -*- coding: utf-8 -*-
"""알림 라우터 — NTF-001 Phase1."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query

from app.api.dependencies import get_notification_service
from app.schemas.notification import (
    NotificationItem,
    NotificationReadAllResponse,
    NotificationReadResponse,
    NotificationSummary,
)
from app.services.notification_service import NotificationService

router = APIRouter(
    prefix="/farms/{farm_cd}/notifications",
    tags=["notifications"],
)


def _user_header(
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> str | None:
    return x_user_id


@router.get("/summary", response_model=NotificationSummary)
def get_notification_summary(
    farm_cd: str,
    x_user_id: str | None = Depends(_user_header),
    service: NotificationService = Depends(get_notification_service),
) -> NotificationSummary:
    return service.get_summary(farm_cd, user_id=x_user_id)


@router.get("", response_model=list[NotificationItem])
def list_notifications(
    farm_cd: str,
    unread_only: bool = Query(False),
    noti_type_cd: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    x_user_id: str | None = Depends(_user_header),
    service: NotificationService = Depends(get_notification_service),
) -> list[NotificationItem]:
    return service.list_notifications(
        farm_cd,
        user_id=x_user_id,
        unread_only=unread_only,
        noti_type_cd=noti_type_cd,
        limit=limit,
    )


@router.put("/read-all", response_model=NotificationReadAllResponse)
def mark_all_read(
    farm_cd: str,
    x_user_id: str | None = Depends(_user_header),
    service: NotificationService = Depends(get_notification_service),
) -> NotificationReadAllResponse:
    return service.mark_read_all(farm_cd, user_id=x_user_id)


@router.put("/{noti_id}/read", response_model=NotificationReadResponse)
def mark_one_read(
    farm_cd: str,
    noti_id: str,
    x_user_id: str | None = Depends(_user_header),
    service: NotificationService = Depends(get_notification_service),
) -> NotificationReadResponse:
    return service.mark_read(farm_cd, noti_id, user_id=x_user_id)
