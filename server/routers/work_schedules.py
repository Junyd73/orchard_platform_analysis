# -*- coding: utf-8 -*-
"""영농 일정(Schedule) API — t_work_detail 통합 후 폐기(410)."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

MSG_SCHEDULE_GONE = (
    "예정 일정 API는 폐기되었습니다. "
    "미래 일정은 영농일지 작업(준비중 WO010100)으로 등록해 주세요."
)

router = APIRouter(
    prefix="/farms/{farm_cd}/work-schedules",
    tags=["work-schedules"],
)


def _gone() -> JSONResponse:
    return JSONResponse(
        status_code=410,
        content={
            "success": False,
            "message": MSG_SCHEDULE_GONE,
            "error_code": "WORK_SCHEDULE_GONE",
        },
    )


@router.api_route("", methods=["GET", "POST"])
@router.api_route("/{sched_id}", methods=["GET", "PUT", "DELETE"])
@router.api_route("/{sched_id}/convert-to-draft", methods=["POST"])
def work_schedules_gone(farm_cd: str, sched_id: str | None = None) -> JSONResponse:
    return _gone()
