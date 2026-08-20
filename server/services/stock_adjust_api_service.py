# -*- coding: utf-8 -*-
"""재고 증감 REST — core.StockAdjustService 어댑터. 전표 없음."""

from __future__ import annotations

from app.core.exceptions import BusinessRuleError, EntityNotFoundError
from app.db.sqlite import get_sqlite_write_connection
from app.schemas.stock_adjust import StockAdjustRequest, StockAdjustResponse
from app.services._core_path import ensure_repo_root_on_path

ensure_repo_root_on_path()

from core.stock_adjust_service import (  # noqa: E402
    StockAdjustError,
    StockAdjustIn,
    StockAdjustService,
)


class StockAdjustApiService:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def adjust(
        self,
        farm_cd: str,
        body: StockAdjustRequest,
        *,
        user_id: str | None,
    ) -> StockAdjustResponse:
        payload = StockAdjustIn(
            farm_cd=farm_cd,
            wh_cd=body.wh_cd,
            item_cd=body.item_cd,
            variety_cd=body.variety_cd,
            grade_cd=body.grade_cd,
            size_cd=body.size_cd,
            weight=body.weight,
            harvest_year=body.harvest_year,
            storage_dt=body.storage_dt,
            io_type=body.io_type,
            qty=body.qty,
            reason_cd=body.reason_cd,
        )
        with get_sqlite_write_connection(self.db_path) as conn:
            try:
                out = StockAdjustService(conn).adjust(
                    payload, user_id=str(user_id or "").strip() or "MOBILE",
                )
            except StockAdjustError as exc:
                if exc.code == "STOCK_NOT_FOUND":
                    raise EntityNotFoundError(exc.message) from exc
                raise BusinessRuleError(exc.message, error_code=exc.code) from exc
        return StockAdjustResponse(**out)
