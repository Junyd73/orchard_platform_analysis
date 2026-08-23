# -*- coding: utf-8 -*-
"""판매 목록 REST 어댑터 — core.SalesQueryService 호출만."""

from __future__ import annotations

from pathlib import Path

from app.core.exceptions import BusinessRuleError, EntityNotFoundError
from app.db.sqlite import get_sqlite_connection
from app.schemas.sales import SalesDetail, SalesDetailLine, SalesListItem, SalesListPage
from app.services._core_path import ensure_repo_root_on_path

ensure_repo_root_on_path()

from core.sales_query_constants import (  # noqa: E402
    SALES_LIST_PAGE_DEFAULT,
    SALES_LIST_PAGE_SIZE_DEFAULT,
)
from core.sales_query_service import (  # noqa: E402
    SalesQueryNotFoundError,
    SalesQueryService,
    SalesQueryValidationError,
)


class SalesApiService:
    def __init__(self, db_path: Path | str):
        self._db_path = Path(db_path)

    def list_sales(
        self,
        farm_cd: str,
        *,
        from_date: str | None = None,
        to_date: str | None = None,
        sales_status: str | None = None,
        payment_status: str | None = None,
        keyword: str | None = None,
        page: int = SALES_LIST_PAGE_DEFAULT,
        page_size: int = SALES_LIST_PAGE_SIZE_DEFAULT,
    ) -> SalesListPage:
        try:
            with get_sqlite_connection(self._db_path) as conn:
                data = SalesQueryService(conn).list_sales(
                    farm_cd,
                    from_date=from_date,
                    to_date=to_date,
                    sales_status=sales_status,
                    payment_status=payment_status,
                    keyword=keyword,
                    page=page,
                    page_size=page_size,
                )
        except SalesQueryValidationError as exc:
            raise BusinessRuleError(exc.message, error_code=exc.code) from exc
        return SalesListPage(
            items=[SalesListItem.model_validate(r) for r in data["items"]],
            total=int(data["total"]),
            page=int(data["page"]),
            page_size=int(data["page_size"]),
        )

    def get_sale_detail(self, farm_cd: str, sales_no: str) -> SalesDetail:
        try:
            with get_sqlite_connection(self._db_path) as conn:
                data = SalesQueryService(conn).get_sale_detail(farm_cd, sales_no)
        except SalesQueryNotFoundError as exc:
            raise EntityNotFoundError(exc.message) from exc
        except SalesQueryValidationError as exc:
            raise BusinessRuleError(exc.message, error_code=exc.code) from exc
        return SalesDetail.model_validate(data)
