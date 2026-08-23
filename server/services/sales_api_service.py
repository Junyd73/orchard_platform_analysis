# -*- coding: utf-8 -*-
"""판매 목록/상세/수금내역 REST 어댑터 — Core 호출만."""

from __future__ import annotations

from pathlib import Path

from app.core.exceptions import BusinessRuleError, EntityNotFoundError
from app.db.sqlite import get_sqlite_connection, get_sqlite_write_connection
from app.schemas.sales import (
    SalesDetail,
    SalesListItem,
    SalesListPage,
    SalesPaymentCreateRequest,
    SalesPaymentHistory,
    SalesPaymentItem,
)
from app.services._core_path import ensure_repo_root_on_path

ensure_repo_root_on_path()

from core.sales_payment_service import (  # noqa: E402
    PaymentAddIn,
    PaymentError,
    PaymentNotFoundError,
    PaymentValidationError,
    SalesPaymentService,
)
from core.sales_query_constants import (  # noqa: E402
    SALES_LIST_PAGE_DEFAULT,
    SALES_LIST_PAGE_SIZE_DEFAULT,
)
from core.sales_query_service import (  # noqa: E402
    SalesQueryNotFoundError,
    SalesQueryService,
    SalesQueryValidationError,
)


def _map_payment_history(data: dict, *, sales_no: str = "") -> SalesPaymentHistory:
    payments = [
        SalesPaymentItem(
            paid_detail_no=str(p.get("paid_detail_no") or ""),
            pay_dt=str(p.get("pay_dt") or ""),
            pay_method_cd=str(p.get("pay_method_cd") or ""),
            pay_method_nm=str(p.get("pay_method_nm") or ""),
            pay_amt=float(p.get("pay_amt") or 0),
            payment_source=str(p.get("payment_source") or ""),
            source_order_no=p.get("source_order_no"),
        )
        for p in (data.get("payments") or [])
    ]
    return SalesPaymentHistory(
        sales_no=str(data.get("sales_no") or sales_no),
        sales_status=str(data.get("sales_status") or ""),
        tot_sales_amt=float(data.get("tot_sales_amt") or 0),
        paid_amt=float(data.get("tot_paid_amt") or 0),
        unpaid_amt=float(data.get("tot_unpaid_amt") or 0),
        payment_status=data.get("payment_status"),
        payments=payments,
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

    def get_sale_payments(self, farm_cd: str, sales_no: str) -> SalesPaymentHistory:
        try:
            with get_sqlite_connection(self._db_path) as conn:
                data = SalesPaymentService(conn).get_payment_summary(farm_cd, sales_no)
        except PaymentNotFoundError as exc:
            raise EntityNotFoundError(str(exc)) from exc
        except PaymentValidationError as exc:
            raise BusinessRuleError(str(exc), error_code=exc.code) from exc
        except PaymentError as exc:
            raise BusinessRuleError(str(exc), error_code=exc.code) from exc
        return _map_payment_history(data, sales_no=sales_no)

    def add_sale_payment(
        self,
        farm_cd: str,
        sales_no: str,
        body: SalesPaymentCreateRequest,
        *,
        user_id: str | None,
    ) -> SalesPaymentHistory:
        uid = (user_id or "").strip() or "MOBILE"
        try:
            with get_sqlite_write_connection(self._db_path) as conn:
                data = SalesPaymentService(conn).add_payment(
                    PaymentAddIn(
                        farm_cd=farm_cd,
                        sales_no=sales_no,
                        pay_amt=body.pay_amt,
                        pay_method_cd=body.pay_method_cd,
                        pay_dt=body.pay_dt,
                        rmk="",
                        user_id=uid,
                        source_order_no=None,
                    )
                )
        except PaymentNotFoundError as exc:
            raise EntityNotFoundError(str(exc)) from exc
        except PaymentValidationError as exc:
            raise BusinessRuleError(str(exc), error_code=exc.code) from exc
        except PaymentError as exc:
            raise BusinessRuleError(str(exc), error_code=exc.code) from exc
        return _map_payment_history(data, sales_no=sales_no)
