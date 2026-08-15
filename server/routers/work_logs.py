# -*- coding: utf-8 -*-
"""영농일지 MVP 라우터 — SCR-010/011."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query

from app.api.dependencies import get_work_log_service
from app.schemas.work_log import (
    WorkLogAccountCodeOption,
    WorkLogDailyResponse,
    WorkLogDeletePreviewResponse,
    WorkLogIntegratedSaveRequest,
    WorkLogMasterUpsertRequest,
    WorkLogMonthlyResponse,
    WorkLogPartnerOption,
    WorkLogPesticideCancelAllRequest,
    WorkLogPesticideCancelRequest,
    WorkLogPesticideCancelResponse,
    WorkLogPesticideItemOption,
    WorkLogPesticideReplaceRequest,
    WorkLogSaveResponse,
    WorkLogWeatherFetchRequest,
    WorkLogWeatherFetchResponse,
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


@router.get("/masters/partners", response_model=list[WorkLogPartnerOption])
def list_work_log_partners(
    farm_cd: str,
    service: WorkLogService = Depends(get_work_log_service),
) -> list[WorkLogPartnerOption]:
    """인력 직원 선택 — PC m_partner 콤보와 동일."""
    return service.list_partners(farm_cd)


@router.get("/masters/account-codes", response_model=list[WorkLogAccountCodeOption])
def list_work_log_account_codes(
    farm_cd: str,
    prefix: str = Query(..., min_length=1, description="AS0101|EX 등"),
    level: int | None = Query(None, ge=1, le=9),
    service: WorkLogService = Depends(get_work_log_service),
) -> list[WorkLogAccountCodeOption]:
    """지급방식·지출내용 — PC m_account_code 콤보와 동일."""
    return service.list_account_codes(farm_cd, prefix=prefix, level=level)


@router.get(
    "/masters/pesticide-items",
    response_model=list[WorkLogPesticideItemOption],
)
def list_work_log_pesticide_items(
    farm_cd: str,
    service: WorkLogService = Depends(get_work_log_service),
) -> list[WorkLogPesticideItemOption]:
    """농약 품목 — PC list_items 와 동일."""
    return service.list_pesticide_items(farm_cd)


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


@router.post(
    "/daily/{work_dt}/weather/fetch",
    response_model=WorkLogWeatherFetchResponse,
)
def fetch_work_log_weather(
    farm_cd: str,
    work_dt: str,
    body: WorkLogWeatherFetchRequest | None = None,
    service: WorkLogService = Depends(get_work_log_service),
) -> WorkLogWeatherFetchResponse:
    """PC WeatherManager.fetch_work_log_weather 위임 (캐시→외부 API)."""
    req = body or WorkLogWeatherFetchRequest()
    return service.fetch_weather(
        farm_cd, work_dt, force_refresh=bool(req.force_refresh)
    )


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


@router.put("/daily/{work_dt}/integrated", response_model=WorkLogSaveResponse)
def save_work_log_integrated(
    farm_cd: str,
    work_dt: str,
    body: WorkLogIntegratedSaveRequest,
    user_id: str | None = Depends(_user_header),
    service: WorkLogService = Depends(get_work_log_service),
) -> WorkLogSaveResponse:
    """PC 최종승인과 동일 — 인력/경비 Ledger + 농약 재고 확정."""
    return service.save_integrated(farm_cd, work_dt, body, user_id=user_id)


@router.post(
    "/pesticide/cancel",
    response_model=WorkLogPesticideCancelResponse,
)
def cancel_work_log_pesticide(
    farm_cd: str,
    body: WorkLogPesticideCancelRequest,
    user_id: str | None = Depends(_user_header),
    service: WorkLogService = Depends(get_work_log_service),
) -> WorkLogPesticideCancelResponse:
    """농약 사용 취소 — use_id 단위."""
    return service.cancel_pesticide_use(farm_cd, body, user_id=user_id)


@router.post(
    "/pesticide/cancel-all",
    response_model=WorkLogPesticideCancelResponse,
)
def cancel_all_work_log_pesticide(
    farm_cd: str,
    body: WorkLogPesticideCancelAllRequest,
    user_id: str | None = Depends(_user_header),
    service: WorkLogService = Depends(get_work_log_service),
) -> WorkLogPesticideCancelResponse:
    """작업 연결 확정 농약 전건 취소."""
    return service.cancel_all_pesticide_uses_for_work(
        farm_cd, body.work_id, user_id=user_id
    )


@router.post(
    "/pesticide/replace",
    response_model=WorkLogPesticideCancelResponse,
)
def replace_work_log_pesticide(
    farm_cd: str,
    body: WorkLogPesticideReplaceRequest,
    user_id: str | None = Depends(_user_header),
    service: WorkLogService = Depends(get_work_log_service),
) -> WorkLogPesticideCancelResponse:
    """확정 농약 수정 저장: 취소·복원·신규·차감 단일 TX."""
    return service.replace_pesticide_use(farm_cd, body, user_id=user_id)


@router.get(
    "/works/{work_id}/delete-preview",
    response_model=WorkLogDeletePreviewResponse,
)
def preview_delete_work_log_work(
    farm_cd: str,
    work_id: str,
    service: WorkLogService = Depends(get_work_log_service),
) -> WorkLogDeletePreviewResponse:
    """삭제 확인 모달용 연관정보."""
    return service.get_delete_preview(farm_cd, work_id)


@router.delete("/works/{work_id}", response_model=WorkLogSaveResponse)
def delete_work_log_work(
    farm_cd: str,
    work_id: str,
    user_id: str | None = Depends(_user_header),
    service: WorkLogService = Depends(get_work_log_service),
) -> WorkLogSaveResponse:
    """작업 및 연관정보 삭제 — 장부 역분개·농약 취소·사진 soft 포함."""
    return service.delete_work(farm_cd, work_id, user_id=user_id)
