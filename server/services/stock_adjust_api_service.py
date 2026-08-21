# -*- coding: utf-8 -*-
"""재고 증감 REST — core.StockAdjustService 어댑터. 전표 없음."""

from __future__ import annotations

from app.core.exceptions import BusinessRuleError, EntityNotFoundError
from app.db.sqlite import get_sqlite_write_connection
from app.schemas.stock_adjust import (
    StockAdjustBySpecRequest,
    StockAdjustRequest,
    StockAdjustResponse,
)
from app.services._core_path import ensure_repo_root_on_path

ensure_repo_root_on_path()

from core.stock_adjust_service import (  # noqa: E402
    StockAdjustBySpecIn,
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
            memo=getattr(body, "memo", "") or "",
        )
        return self._run(payload, user_id=user_id, by_spec=False)

    def adjust_by_sale_spec(
        self,
        farm_cd: str,
        body: StockAdjustBySpecRequest,
        *,
        user_id: str | None,
    ) -> StockAdjustResponse:
        payload = StockAdjustBySpecIn(
            farm_cd=farm_cd,
            wh_cd=body.wh_cd,
            item_cd=body.item_cd,
            variety_cd=body.variety_cd,
            grade_cd=body.grade_cd,
            size_cd=body.size_cd,
            weight=body.weight,
            harvest_year=body.harvest_year,
            io_type=body.io_type,
            qty=body.qty,
            reason_cd=body.reason_cd,
            memo=getattr(body, "memo", "") or "",
        )
        return self._run(payload, user_id=user_id, by_spec=True)

    def _run(
        self,
        payload: StockAdjustIn | StockAdjustBySpecIn,
        *,
        user_id: str | None,
        by_spec: bool,
    ) -> StockAdjustResponse:
        with get_sqlite_write_connection(self.db_path) as conn:
            try:
                svc = StockAdjustService(conn)
                uid = str(user_id or "").strip() or "MOBILE"
                out = (
                    svc.adjust_by_sale_spec(payload, user_id=uid)  # type: ignore[arg-type]
                    if by_spec
                    else svc.adjust(payload, user_id=uid)  # type: ignore[arg-type]
                )
            except StockAdjustError as exc:
                if exc.code == "STOCK_NOT_FOUND":
                    raise EntityNotFoundError(exc.message) from exc
                raise BusinessRuleError(exc.message, error_code=exc.code) from exc
        return StockAdjustResponse(**out)
