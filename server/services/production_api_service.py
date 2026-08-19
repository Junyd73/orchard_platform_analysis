# -*- coding: utf-8 -*-
"""생산확정 REST — core.ProductionService 어댑터."""

from __future__ import annotations

from app.core.exceptions import BusinessRuleError
from app.db.sqlite import get_sqlite_connection, get_sqlite_write_connection
from app.schemas.production import (
    HarvestRecordOut,
    ProductionConfirmRequest,
    ProductionConfirmResponse,
    ProductionPrefillLineOut,
    RawStockItemOut,
)
from app.services._core_path import ensure_repo_root_on_path

ensure_repo_root_on_path()

from core.production_service import (  # noqa: E402
    ProductionConfirmIn,
    ProductionError,
    ProductionLineIn,
    ProductionService,
    RawStockConsumptionIn,
)
from core.work_harvest_schema import ensure_work_harvest_schema  # noqa: E402


def _map_error(exc: ProductionError) -> BusinessRuleError:
    return BusinessRuleError(str(exc.message), error_code=exc.code)


class ProductionApiService:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def list_harvest_records(
        self,
        farm_cd: str,
        *,
        from_dt: str | None = None,
        to_dt: str | None = None,
        variety_cd: str | None = None,
        limit: int = 50,
    ) -> list[HarvestRecordOut]:
        ensure_work_harvest_schema(self.db_path)
        with get_sqlite_connection(self.db_path) as conn:
            svc = ProductionService(conn)
            rows = svc.list_harvest_records(
                farm_cd,
                from_dt=from_dt,
                to_dt=to_dt,
                variety_cd=variety_cd,
                limit=limit,
            )
        return [HarvestRecordOut(**row) for row in rows]

    def list_raw_stock(
        self,
        farm_cd: str,
        *,
        variety_cd: str | None = None,
    ) -> list[RawStockItemOut]:
        with get_sqlite_connection(self.db_path) as conn:
            svc = ProductionService(conn)
            rows = svc.list_raw_stock(farm_cd, variety_cd=variety_cd)
        return [RawStockItemOut(**row) for row in rows]

    def confirm(
        self,
        farm_cd: str,
        user_id: str,
        body: ProductionConfirmRequest,
    ) -> ProductionConfirmResponse:
        payload = ProductionConfirmIn(
            farm_cd=farm_cd,
            prod_type=body.prod_type,
            input_source=body.input_source,
            variety_cd=body.variety_cd,
            wh_cd=body.wh_cd,
            pack_weight=body.pack_weight,
            lines=[
                ProductionLineIn(
                    grade_cd=ln.grade_cd,
                    size_cd=ln.size_cd,
                    qty=ln.qty,
                    weight=getattr(ln, "weight", 0.0) or 0.0,
                )
                for ln in body.lines
            ],
            raw_consumptions=[
                RawStockConsumptionIn(
                    wh_cd=r.wh_cd,
                    variety_cd=r.variety_cd,
                    size_cd=r.size_cd,
                    weight=r.weight,
                    harvest_year=r.harvest_year,
                    storage_dt=r.storage_dt,
                    qty=r.qty,
                )
                for r in body.raw_consumptions
            ],
            work_ids=list(body.work_ids or []),
            harvest_work_id=body.harvest_work_id,
            juice_qty=body.juice_qty,
            juice_grade_cd=body.juice_grade_cd,
        )
        with get_sqlite_write_connection(self.db_path) as conn:
            svc = ProductionService(conn)
            try:
                result = svc.confirm(user_id, payload)
            except ProductionError as exc:
                raise _map_error(exc) from exc
        return ProductionConfirmResponse(
            ok=bool(result.get("ok")),
            prefill_lines=[
                ProductionPrefillLineOut(**ln)
                for ln in result.get("prefill_lines") or []
            ],
        )
