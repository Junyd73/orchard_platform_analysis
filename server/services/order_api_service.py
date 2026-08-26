# -*- coding: utf-8 -*-
"""주문 REST 어댑터 — core.OrderService 호출만."""

from __future__ import annotations

from pathlib import Path

from app.core.exceptions import BusinessRuleError, DataIntegrityError, EntityNotFoundError
from app.db.sqlite import get_sqlite_connection, get_sqlite_write_connection
from app.schemas.order import (
    AllocationCreateRequest,
    AllocationReleaseRequest,
    AllocationSummaryOut,
    CustomerCreateRequest,
    CustomerListItem,
    FruitStockItemOut,
    OrderCreateRequest,
    OrderDetail,
    OrderLineIn,
    OrderListItem,
    OrderListPage,
)
from app.services._core_path import ensure_repo_root_on_path

ensure_repo_root_on_path()

from core.customer_service import (  # noqa: E402
    CustomerDuplicateError,
    CustomerSaveError,
    CustomerService,
    CustomerValidationError,
)
from core.order_constants import (  # noqa: E402
    ORDER_LIST_PAGE_DEFAULT,
    ORDER_LIST_PAGE_SIZE_DEFAULT,
    WAREHOUSE_CD_DEFAULT,
)
from core.order_service import (  # noqa: E402
    OrderDeliveryInput,
    OrderLineInput,
    OrderNotFoundError,
    OrderSaveError,
    OrderSaveInput,
    OrderService,
    OrderValidationError,
)
from core.order_allocation_service import (  # noqa: E402
    AllocationConflictError,
    OrderAllocationService,
)


def _to_line_input(line: OrderLineIn) -> OrderLineInput:
    return OrderLineInput(
        variety_cd=line.variety_cd,
        weight=line.weight,
        grade_cd=line.grade_cd,
        size_cd=line.size_cd,
        qty=line.qty,
        unit_price=line.unit_price,
        harvest_year=line.harvest_year,
        warehouse_cd=line.warehouse_cd or WAREHOUSE_CD_DEFAULT,
        item_cd=line.item_cd,
        dlvry_tp=line.dlvry_tp,
        deliveries=[
            OrderDeliveryInput(
                delivery_tp_cd=d.delivery_tp_cd,
                qty=d.qty,
                planned_dt=d.planned_dt,
                snd_name=d.snd_name,
                snd_tel=d.snd_tel,
                snd_addr=d.snd_addr,
                rcv_name=d.rcv_name,
                rcv_tel=d.rcv_tel,
                rcv_addr=d.rcv_addr,
                dlvry_msg=d.dlvry_msg,
            )
            for d in line.deliveries
        ],
    )


def _to_save_input(body: OrderCreateRequest) -> OrderSaveInput:
    return OrderSaveInput(
        custm_id=body.custm_id,
        order_dt=body.order_dt,
        sales_type_cd=body.sales_type_cd or "",
        season_type_cd=body.season_type_cd or "",
        pre_pay_amt=body.pre_pay_amt,
        pre_pay_method_cd=body.pre_pay_method_cd,
        tot_ship_fee=body.tot_ship_fee,
        rmk=body.rmk or "",
        lines=[_to_line_input(line) for line in body.lines],
    )


class OrderApiService:
    def __init__(self, db_path: str | Path):
        self._db_path = db_path

    def list_customers(
        self, farm_cd: str, q: str | None = None
    ) -> list[CustomerListItem]:
        with get_sqlite_connection(self._db_path) as conn:
            rows = OrderService(conn).list_customers(farm_cd, q=q)
        return [CustomerListItem.model_validate(r) for r in rows]

    def create_customer(
        self,
        farm_cd: str,
        body: CustomerCreateRequest,
        *,
        user_id: str | None,
    ) -> CustomerListItem:
        try:
            with get_sqlite_write_connection(self._db_path) as conn:
                row = CustomerService(conn).create_customer(
                    farm_cd,
                    custm_nm=body.custm_nm,
                    mobile=body.mobile,
                    addr1=body.addr1,
                    addr2=body.addr2,
                    rmk=body.rmk,
                    user_id=user_id or "MOBILE",
                )
        except CustomerValidationError as exc:
            raise BusinessRuleError(exc.message, error_code=exc.code) from exc
        except CustomerDuplicateError as exc:
            raise BusinessRuleError(exc.message, error_code=exc.code) from exc
        except CustomerSaveError as exc:
            raise BusinessRuleError(exc.message, error_code=exc.code) from exc
        return CustomerListItem(
            custm_id=str(row["custm_id"]),
            custm_nm=str(row["custm_nm"]),
            mobile=str(row.get("mobile") or ""),
        )

    def list_orders(
        self,
        farm_cd: str,
        *,
        from_date: str | None = None,
        to_date: str | None = None,
        status_cd: str | None = None,
        keyword: str | None = None,
        page: int = ORDER_LIST_PAGE_DEFAULT,
        page_size: int = ORDER_LIST_PAGE_SIZE_DEFAULT,
    ) -> OrderListPage:
        try:
            with get_sqlite_connection(self._db_path) as conn:
                data = OrderService(conn).list_orders(
                    farm_cd,
                    from_date=from_date,
                    to_date=to_date,
                    status_cd=status_cd,
                    keyword=keyword,
                    page=page,
                    page_size=page_size,
                )
        except OrderValidationError as exc:
            raise BusinessRuleError(exc.message, error_code=exc.code) from exc
        return OrderListPage(
            items=[OrderListItem.model_validate(r) for r in data["items"]],
            total=int(data["total"]),
            page=int(data["page"]),
            page_size=int(data["page_size"]),
        )

    def get_order(self, farm_cd: str, order_no: str) -> OrderDetail:
        try:
            with get_sqlite_connection(self._db_path) as conn:
                data = OrderService(conn).get_order(farm_cd, order_no)
        except OrderNotFoundError as exc:
            raise EntityNotFoundError(exc.message) from exc
        return OrderDetail.model_validate(data)

    def create_order(
        self,
        farm_cd: str,
        body: OrderCreateRequest,
        *,
        user_id: str | None,
    ) -> OrderDetail:
        payload = _to_save_input(body)
        try:
            with get_sqlite_write_connection(self._db_path) as conn:
                order_no = OrderService(conn).create_order(
                    farm_cd, payload, user_id=user_id or "MOBILE"
                )
        except OrderValidationError as exc:
            raise BusinessRuleError(exc.message, error_code=exc.code) from exc
        except OrderSaveError as exc:
            raise BusinessRuleError(exc.message, error_code=exc.code) from exc
        return self.get_order(farm_cd, order_no)

    def replace_order(
        self,
        farm_cd: str,
        order_no: str,
        body: OrderCreateRequest,
        *,
        user_id: str | None,
    ) -> OrderDetail:
        payload = _to_save_input(body)
        try:
            with get_sqlite_write_connection(self._db_path) as conn:
                OrderService(conn).replace_order(
                    farm_cd, order_no, payload, user_id=user_id or "MOBILE"
                )
        except OrderNotFoundError as exc:
            raise EntityNotFoundError(exc.message) from exc
        except OrderSaveError as exc:
            raise BusinessRuleError(exc.message, error_code=exc.code) from exc
        return self.get_order(farm_cd, order_no)

    def cancel_order(
        self,
        farm_cd: str,
        order_no: str,
        *,
        user_id: str | None,
    ) -> OrderDetail:
        try:
            with get_sqlite_write_connection(self._db_path) as conn:
                OrderService(conn).cancel_order(
                    farm_cd, order_no, user_id=user_id or "MOBILE"
                )
        except OrderNotFoundError as exc:
            raise EntityNotFoundError(exc.message) from exc
        except OrderValidationError as exc:
            raise BusinessRuleError(exc.message, error_code=exc.code) from exc
        except OrderSaveError as exc:
            raise BusinessRuleError(exc.message, error_code=exc.code) from exc
        return self.get_order(farm_cd, order_no)

    def confirm_order(
        self,
        farm_cd: str,
        order_no: str,
        *,
        user_id: str | None,
    ) -> OrderDetail:
        try:
            with get_sqlite_write_connection(self._db_path) as conn:
                OrderService(conn).confirm_order(
                    farm_cd, order_no, user_id=user_id or "MOBILE"
                )
        except OrderNotFoundError as exc:
            raise EntityNotFoundError(exc.message) from exc
        except OrderValidationError as exc:
            raise BusinessRuleError(exc.message, error_code=exc.code) from exc
        except OrderSaveError as exc:
            raise BusinessRuleError(exc.message, error_code=exc.code) from exc
        return self.get_order(farm_cd, order_no)

    def list_allocations(self, farm_cd: str, order_no: str) -> AllocationSummaryOut:
        try:
            with get_sqlite_connection(self._db_path) as conn:
                data = OrderAllocationService(conn).get_allocation_summary(
                    farm_cd, order_no
                )
        except OrderNotFoundError as exc:
            raise EntityNotFoundError(exc.message) from exc
        except OrderValidationError as exc:
            raise BusinessRuleError(exc.message, error_code=exc.code) from exc
        return AllocationSummaryOut.model_validate(data)

    def allocate(
        self,
        farm_cd: str,
        order_no: str,
        body: AllocationCreateRequest,
        *,
        user_id: str | None,
    ) -> AllocationSummaryOut:
        auto = bool(body.auto or body.qty is None)
        try:
            with get_sqlite_write_connection(self._db_path) as conn:
                data = OrderAllocationService(conn).allocate(
                    farm_cd,
                    order_no,
                    order_detail_id=body.order_detail_id,
                    qty=body.qty,
                    auto=auto,
                    user_id=user_id or "MOBILE",
                )
        except OrderNotFoundError as exc:
            raise EntityNotFoundError(exc.message) from exc
        except AllocationConflictError as exc:
            raise DataIntegrityError(exc.message) from exc
        except OrderValidationError as exc:
            raise BusinessRuleError(exc.message, error_code=exc.code) from exc
        except OrderSaveError as exc:
            raise BusinessRuleError(exc.message, error_code=exc.code) from exc
        return AllocationSummaryOut.model_validate(data)

    def release_allocation(
        self,
        farm_cd: str,
        order_no: str,
        body: AllocationReleaseRequest,
        *,
        user_id: str | None,
    ) -> AllocationSummaryOut:
        try:
            with get_sqlite_write_connection(self._db_path) as conn:
                data = OrderAllocationService(conn).release(
                    farm_cd,
                    order_no,
                    order_detail_id=body.order_detail_id,
                    qty=body.qty,
                    user_id=user_id or "MOBILE",
                )
        except OrderNotFoundError as exc:
            raise EntityNotFoundError(exc.message) from exc
        except AllocationConflictError as exc:
            raise DataIntegrityError(exc.message) from exc
        except OrderValidationError as exc:
            raise BusinessRuleError(exc.message, error_code=exc.code) from exc
        except OrderSaveError as exc:
            raise BusinessRuleError(exc.message, error_code=exc.code) from exc
        return AllocationSummaryOut.model_validate(data)

    def list_fruit_stock(
        self,
        farm_cd: str,
        *,
        item_cd: str | None = None,
        variety_cd: str | None = None,
        wh_cd: str | None = None,
        include_zero: bool = False,
    ) -> list[FruitStockItemOut]:
        with get_sqlite_connection(self._db_path) as conn:
            rows = OrderAllocationService(conn).get_available_stock(
                farm_cd, item_cd=item_cd, variety_cd=variety_cd,
                wh_cd=wh_cd, include_zero=include_zero,
            )
        return [FruitStockItemOut.model_validate(r) for r in rows]

    def list_stock_logs(
        self,
        farm_cd: str,
        *,
        item_cd: str | None = None,
        variety_cd: str | None = None,
        grade_cd: str | None = None,
        size_cd: str | None = None,
        weight: float | None = None,
        storage_dt: str | None = None,
        harvest_year: int | None = None,
        limit: int = 50,
    ) -> list["StockLogOut"]:
        from app.schemas.order import StockLogOut
        with get_sqlite_connection(self._db_path) as conn:
            rows = OrderAllocationService(conn).list_stock_logs(
                farm_cd,
                item_cd=item_cd,
                variety_cd=variety_cd,
                grade_cd=grade_cd,
                size_cd=size_cd,
                weight=weight,
                storage_dt=storage_dt,
                harvest_year=harvest_year,
                limit=limit,
            )
        return [StockLogOut.model_validate(r) for r in rows]
