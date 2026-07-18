# -*- coding: utf-8 -*-
"""영농일지 MVP 라우터 — SCR-010/011."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query

from app.api.dependencies import get_work_log_service
from app.schemas.work_log import (
    WorkLogDailyResponse,
    WorkLogMasterUpsertRequest,
    WorkLogMonthlyResponse,
    WorkLogSaveResponse,
    WorkLogWorksUpsertRequest,
)
from app.services.work_log_service import WorkLogService

router = APIRouter(
    prefix="/farms/{farm_cd}/work-logs",
    tags=["work-logs"],
)


def _user_header(
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> str | None:
    return x_user_id


@router.get("/monthly", response_model=WorkLogMonthlyResponse)
def get_work_log_monthly(
    farm_cd: str,
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    service: WorkLogService = Depends(get_work_log_service),
) -> WorkLogMonthlyResponse:
    return service.get_monthly(farm_cd, year=year, month=month)


@router.get("/daily/{work_dt}", response_model=WorkLogDailyResponse)
def get_work_log_daily(
    farm_cd: str,
    work_dt: str,
    service: WorkLogService = Depends(get_work_log_service),
) -> WorkLogDailyResponse:
    return service.get_daily(farm_cd, work_dt)


@router.put("/daily/{work_dt}/master", response_model=WorkLogSaveResponse)
def upsert_work_log_master(
    farm_cd: str,
    work_dt: str,
    body: WorkLogMasterUpsertRequest,
    user_id: str | None = Depends(_user_header),
    service: WorkLogService = Depends(get_work_log_service),
) -> WorkLogSaveResponse:
    return service.upsert_master(farm_cd, work_dt, body, user_id=user_id)


@router.put("/daily/{work_dt}/works", response_model=WorkLogSaveResponse)
def upsert_work_log_works(
    farm_cd: str,
    work_dt: str,
    body: WorkLogWorksUpsertRequest,
    user_id: str | None = Depends(_user_header),
    service: WorkLogService = Depends(get_work_log_service),
) -> WorkLogSaveResponse:
    return service.upsert_works(farm_cd, work_dt, body, user_id=user_id)


@router.delete("/works/{work_id}", response_model=WorkLogSaveResponse)
def delete_work_log_work(
    farm_cd: str,
    work_id: str,
    user_id: str | None = Depends(_user_header),
    service: WorkLogService = Depends(get_work_log_service),
) -> WorkLogSaveResponse:
    return service.delete_work(farm_cd, work_id, user_id=user_id)
