# -*- coding: utf-8 -*-
"""FastAPI 의존성 — Repository/Service 조립 (라우터는 구체 클래스 미생성)."""

from __future__ import annotations

from functools import lru_cache

from app.core.config import get_settings
from app.db.observation_lifecycle_migrate import ensure_observation_lifecycle_schema
from app.repository.interfaces.common_code_repository import CommonCodeRepository
from app.repository.interfaces.farm_repository import FarmRepository
from app.repository.interfaces.observation_photo_repository import (
    ObservationPhotoRepository,
)
from app.repository.interfaces.observation_repository import ObservationRepository
from app.repository.sqlite.common_code_repository import SqliteCommonCodeRepository
from app.repository.sqlite.farm_repository import SqliteFarmRepository
from app.repository.sqlite.observation_photo_repository import (
    SqliteObservationPhotoRepository,
)
from app.repository.sqlite.observation_repository import SqliteObservationRepository
from app.services.common_code_service import CommonCodeService
from app.services.farm_service import FarmService
from app.services.observation_ai_api_service import ObservationAiApiService
from app.services.observation_candidate_confirm_api_service import (
    ObservationCandidateConfirmApiService,
)
from app.services.observation_photo_service import ObservationPhotoService
from app.services.observation_psis_api_service import ObservationPsisApiService
from app.services.observation_service import ObservationService
from app.services.observation_smart_spray_guide_api_service import (
    ObservationSmartSprayGuideApiService,
)
from app.services.observation_fruit_api_service import ObservationFruitApiService
from app.services.google_calendar_service import GoogleCalendarService
from app.services.notification_service import NotificationService
from app.services.order_api_service import OrderApiService
from app.services.order_ship_api_service import OrderShipApiService
from app.services.production_api_service import ProductionApiService
from app.services.stock_adjust_api_service import StockAdjustApiService
from app.services.pesticide_service import PesticideService
from app.services.smart_spray_service import SmartSprayService
from app.services.weather_service import WeatherService
from app.services.work_log_service import WorkLogService
from app.services.work_photo_service import WorkPhotoService
from app.services.work_schedule_service import WorkScheduleService


@lru_cache
def get_farm_repository() -> FarmRepository:
    settings = get_settings()
    return SqliteFarmRepository(settings.sqlite_path)


@lru_cache
def get_common_code_repository() -> CommonCodeRepository:
    settings = get_settings()
    return SqliteCommonCodeRepository(settings.sqlite_path)


@lru_cache
def get_observation_repository() -> ObservationRepository:
    settings = get_settings()
    ensure_observation_lifecycle_schema(settings.sqlite_path)
    return SqliteObservationRepository(settings.sqlite_path)


@lru_cache
def get_observation_photo_repository() -> ObservationPhotoRepository:
    settings = get_settings()
    ensure_observation_lifecycle_schema(settings.sqlite_path)
    return SqliteObservationPhotoRepository(settings.sqlite_path)


def get_farm_service() -> FarmService:
    return FarmService(get_farm_repository())


def get_common_code_service() -> CommonCodeService:
    return CommonCodeService(get_common_code_repository())


def get_observation_service() -> ObservationService:
    settings = get_settings()
    return ObservationService(
        get_observation_repository(),
        photo_repo=get_observation_photo_repository(),
        media_root=settings.observation_media_root,
    )


def get_observation_photo_service() -> ObservationPhotoService:
    settings = get_settings()
    return ObservationPhotoService(
        get_observation_photo_repository(),
        media_root=settings.observation_media_root,
        db_path=settings.sqlite_path,
        default_user_id=settings.default_user_id,
    )


def get_observation_ai_api_service() -> ObservationAiApiService:
    """관찰 AI REST — ApplicationService 공통 엔진 어댑터."""
    settings = get_settings()
    return ObservationAiApiService(
        db_path=settings.sqlite_path,
        media_root=settings.observation_media_root,
        photo_repo=get_observation_photo_repository(),
        default_user_id=settings.default_user_id,
    )


def get_observation_psis_api_service() -> ObservationPsisApiService:
    """관찰 PSIS REST — ApplicationService 공통 엔진 어댑터."""
    settings = get_settings()
    return ObservationPsisApiService(
        db_path=settings.sqlite_path,
        photo_repo=get_observation_photo_repository(),
        default_user_id=settings.default_user_id,
    )


def get_observation_candidate_confirm_api_service() -> (
    ObservationCandidateConfirmApiService
):
    """관찰 AI 후보 확정 REST — ApplicationService 공통 엔진 어댑터."""
    settings = get_settings()
    return ObservationCandidateConfirmApiService(
        db_path=settings.sqlite_path,
        photo_repo=get_observation_photo_repository(),
    )


def get_observation_smart_spray_guide_api_service() -> (
    ObservationSmartSprayGuideApiService
):
    """스마트 방제 가이드 REST — 읽기 전용 통합 ApplicationService 어댑터."""
    settings = get_settings()
    return ObservationSmartSprayGuideApiService(
        db_path=settings.sqlite_path,
        photo_repo=get_observation_photo_repository(),
    )


def get_observation_fruit_api_service() -> ObservationFruitApiService:
    """과실 측정·추적 REST — Stage2 어댑터."""
    settings = get_settings()
    return ObservationFruitApiService(
        db_path=settings.sqlite_path,
        photo_repo=get_observation_photo_repository(),
        default_user_id=settings.default_user_id,
    )


def get_pesticide_service() -> PesticideService:
    """농약 재고 조회 REST — SCR-020."""
    settings = get_settings()
    return PesticideService(db_path=settings.sqlite_path)


def get_smart_spray_service() -> SmartSprayService:
    """SPR-001 스마트방제·발병여건 REST."""
    settings = get_settings()
    return SmartSprayService(db_path=settings.sqlite_path)


def get_work_log_service() -> WorkLogService:
    """영농일지 MVP REST."""
    settings = get_settings()
    return WorkLogService(db_path=settings.sqlite_path)


def get_weather_service() -> WeatherService:
    """모바일 날씨 상세 REST."""
    settings = get_settings()
    return WeatherService(db_path=settings.sqlite_path)


def get_work_photo_service() -> WorkPhotoService:
    """작업 결과 사진 REST — 관찰 사진과 분리."""
    settings = get_settings()
    return WorkPhotoService(
        db_path=settings.sqlite_path,
        media_root=settings.work_photo_media_root,
        default_user_id=settings.default_user_id,
    )


def get_work_schedule_service() -> WorkScheduleService:
    """영농 일정(Schedule) REST — WLS-001 Phase1."""
    settings = get_settings()
    return WorkScheduleService(db_path=settings.sqlite_path)


def get_google_calendar_service() -> GoogleCalendarService:
    """구글 캘린더 OAuth·동기화 — WLS-001 Phase3."""
    settings = get_settings()
    return GoogleCalendarService(db_path=settings.sqlite_path, settings=settings)


def get_notification_service() -> NotificationService:
    """알림 목록·읽음 REST (NTF-001 Phase1)."""
    settings = get_settings()
    return NotificationService(db_path=settings.sqlite_path)


def get_order_api_service() -> OrderApiService:
    """주문 조회/등록 REST — core.OrderService 어댑터."""
    settings = get_settings()
    return OrderApiService(db_path=settings.sqlite_path)


def get_order_ship_api_service() -> OrderShipApiService:
    """판매출고 confirm REST — core.OrderShipService 어댑터."""
    settings = get_settings()
    return OrderShipApiService(db_path=settings.sqlite_path)


def get_production_api_service() -> ProductionApiService:
    """생산확정 REST — core.ProductionService 어댑터."""
    settings = get_settings()
    return ProductionApiService(db_path=settings.sqlite_path)


def get_stock_adjust_api_service() -> StockAdjustApiService:
    settings = get_settings()
    return StockAdjustApiService(db_path=settings.sqlite_path)
