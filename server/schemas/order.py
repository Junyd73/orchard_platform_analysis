# -*- coding: utf-8 -*-
"""주문 Stage 2 API 스키마."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class OrderDeliveryIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    delivery_tp_cd: str = Field(..., min_length=1)
    qty: float = Field(..., gt=0)
    planned_dt: str | None = None
    snd_name: str = ""
    snd_tel: str = ""
    snd_addr: str = ""
    rcv_name: str = ""
    rcv_tel: str = ""
    rcv_addr: str = ""
    dlvry_msg: str = ""


class OrderLineIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    variety_cd: str = Field(..., min_length=8, max_length=8)
    weight: float = Field(..., ge=0)
    grade_cd: str = Field(..., min_length=1)
    size_cd: str = Field(..., min_length=1)
    qty: float = Field(..., gt=0)
    unit_price: float = Field(..., ge=0)
    harvest_year: int | None = None
    warehouse_cd: str | None = None
    item_cd: str | None = None
    dlvry_tp: str | None = None
    deliveries: list[OrderDeliveryIn]


class OrderCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    custm_id: str = Field(..., min_length=1)
    order_dt: str | None = None
    season_type_cd: str = ""
    pre_pay_amt: float = 0
    tot_ship_fee: float = 0
    rmk: str = ""
    lines: list[OrderLineIn]


class OrderDeliveryOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_dlvry_id: str
    order_detail_id: str
    delivery_tp_cd: str
    qty: float
    planned_dt: str
    snd_name: str = ""
    snd_tel: str = ""
    snd_addr: str = ""
    rcv_name: str = ""
    rcv_tel: str = ""
    rcv_addr: str = ""
    dlvry_msg: str = ""
    delivery_tp_nm: str = ""


class OrderLineOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_detail_id: str
    item_cd: str
    variety_cd: str
    grade_cd: str
    size_cd: str
    weight: float
    qty: float
    unit_price: float
    item_amt: float
    harvest_year: int
    wh_cd: str
    dlvry_tp: str
    variety_nm: str = ""
    grade_nm: str = ""
    size_nm: str = ""
    dlvry_tp_nm: str = ""
    deliveries: list[OrderDeliveryOut]


class OrderListItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_no: str
    order_dt: str
    custm_id: str
    customer: str
    status_cd: str
    status_nm: str
    total_qty: float
    total_amt: float
    pre_pay_amt: float


class OrderListPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[OrderListItem]
    total: int
    page: int
    page_size: int


class OrderDetail(OrderListItem):
    mobile: str = ""
    stock_status: str = "N"
    season_type_cd: str = ""
    tot_order_amt: float = 0
    tot_ship_fee: float = 0
    tot_pay_amt: float = 0
    rmk: str = ""
    sales_no: str = ""
    lines: list[OrderLineOut]


class CustomerCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    custm_nm: str = Field(..., min_length=1)
    mobile: str = Field(..., min_length=1)
    addr1: str = ""
    addr2: str = ""
    rmk: str = ""


class CustomerListItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    custm_id: str
    custm_nm: str
    mobile: str = ""
