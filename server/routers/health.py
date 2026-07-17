# -*- coding: utf-8 -*-
"""Health / DB connectivity endpoints."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.db.session import check_database_connection

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/db")
def database_health_check():
    result = check_database_connection()

    if result["status"] != "ok":
        return JSONResponse(status_code=503, content=result)

    return result
