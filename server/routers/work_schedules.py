# -*- coding: utf-8 -*-
"""영농 일정(Schedule) 라우터 — WLS-001 Phase1."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query

from app.api.dependencies import get_work_schedule_service
from app.schemas.work_schedule import (
    WorkScheduleConvertResponse,
    WorkScheduleCreateRequest,
    WorkScheduleCreateResponse,
    WorkScheduleItem,
    WorkScheduleListResponse,
    WorkScheduleMessageResponse,
    WorkScheduleUpdateRequest,
)
from app.services.work_schedule_service import WorkScheduleService

router = APIRouter(
    prefix="/farms/{farm_cd}/work-schedules",
    tags=["work-schedules"],
)


def _user_header(
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> str | None:
    return x_user_id


@router.get("", response_model=WorkScheduleListResponse)
def list_work_schedules(
    farm_cd: str,
    start_dt: str | None = Query(None),
    end_dt: str | None = Query(None),
    status_cd: str | None = Query(None),
    service: WorkScheduleService = Depends(get_work_schedule_service),
) -> WorkScheduleListResponse:
    return service.list_schedules(
        farm_cd, start_dt=start_dt, end_dt=end_dt, status_cd=status_cd
    )


@router.post("", response_model=WorkScheduleCreateResponse, status_code=201)
def create_work_schedule(
    farm_cd: str,
    body: WorkScheduleCreateRequest,
    user_id: str | None = Depends(_user_header),
    service: WorkScheduleService = Depends(get_work_schedule_service),
) -> WorkScheduleCreateResponse:
    return service.create(farm_cd, body, user_id=user_id)


@router.put("/{sched_id}", response_model=WorkScheduleItem)
def update_work_schedule(
    farm_cd: str,
    sched_id: str,
    body: WorkScheduleUpdateRequest,
    user_id: str | None = Depends(_user_header),
    service: WorkScheduleService = Depends(get_work_schedule_service),
) -> WorkScheduleItem:
    return service.update(farm_cd, sched_id, body, user_id=user_id)


@router.delete("/{sched_id}", response_model=WorkScheduleMessageResponse)
def delete_work_schedule(
    farm_cd: str,
    sched_id: str,
    user_id: str | None = Depends(_user_header),
    service: WorkScheduleService = Depends(get_work_schedule_service),
) -> WorkScheduleMessageResponse:
    return service.delete(farm_cd, sched_id, user_id=user_id)


@router.post(
    "/{sched_id}/convert-to-draft",
    response_model=WorkScheduleConvertResponse,
)
def convert_work_schedule_to_draft(
    farm_cd: str,
    sched_id: str,
    user_id: str | None = Depends(_user_header),
    service: WorkScheduleService = Depends(get_work_schedule_service),
) -> WorkScheduleConvertResponse:
    return service.convert_to_draft(farm_cd, sched_id, user_id=user_id)
