# -*- coding: utf-8 -*-
"""API v1 aggregate router."""

from fastapi import APIRouter

from app.routers import (
    common_codes,
    customers,
    farms,
    fruit_stock,
    google_calendar,
    health,
    notifications,
    observation_ai,
    observation_candidates,
    observation_fruit,
    observation_photos,
    observation_psis,
    observation_smart_spray_guide,
    observations,
    orders,
    production,
    shipments,
    stock_adjust,
    pesticide,
    smart_spray,
    weather,
    work_logs,
    work_photos,
    work_schedules,
)

api_v1_router = APIRouter()
api_v1_router.include_router(health.router)
api_v1_router.include_router(farms.router)
api_v1_router.include_router(observations.router)
api_v1_router.include_router(observation_photos.router)
api_v1_router.include_router(observation_fruit.router)
api_v1_router.include_router(observation_ai.router)
api_v1_router.include_router(observation_candidates.router)
api_v1_router.include_router(observation_psis.router)
api_v1_router.include_router(observation_smart_spray_guide.router)
api_v1_router.include_router(pesticide.router)
api_v1_router.include_router(smart_spray.router)
api_v1_router.include_router(work_logs.router)
api_v1_router.include_router(weather.router)
api_v1_router.include_router(work_photos.router)
api_v1_router.include_router(work_schedules.router)
api_v1_router.include_router(google_calendar.router)
api_v1_router.include_router(notifications.router)
api_v1_router.include_router(common_codes.router)
api_v1_router.include_router(customers.router)
api_v1_router.include_router(orders.router)
api_v1_router.include_router(fruit_stock.router)
api_v1_router.include_router(stock_adjust.router)
api_v1_router.include_router(production.router)
api_v1_router.include_router(shipments.router)
