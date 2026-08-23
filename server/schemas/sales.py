# -*- coding: utf-8 -*-
"""판매 목록 Stage 5 API 스키마."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class SalesListItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sales_no: str
    sales_dt: str
    custm_id: str
    customer: str
    order_no: str | None = None
    sales_status: str
    sales_source: str = ""
    tot_sales_amt: float
    paid_amt: float
    unpaid_amt: float
    payment_status: str | None = None
    rep_item_cd: str = ""
    rep_variety_cd: str = ""
    rep_variety_nm: str = ""
    rep_weight: float = 0
    rep_grade_cd: str = ""
    rep_grade_nm: str = ""
    rep_size_cd: str = ""
    rep_size_nm: str = ""
    rep_crop_nm: str = ""


class SalesListPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[SalesListItem]
    total: int
    page: int
    page_size: int


class SalesDetailLine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sale_detail_no: str
    order_detail_id: str | None = None
    item_cd: str = ""
    variety_cd: str = ""
    variety_nm: str = ""
    grade_cd: str = ""
    grade_nm: str = ""
    size_cd: str = ""
    size_nm: str = ""
    crop_nm: str = ""
    qty: float = 0
    unit_price: float = 0
    item_amt: float = 0
    wh_cd: str | None = None
    dlvry_tp: str | None = None
    stock_seq: int | None = None


class SalesDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sales_no: str
    sales_dt: str
    custm_id: str
    customer: str
    order_no: str | None = None
    sales_status: str
    sales_source: str = ""
    tot_sales_amt: float
    paid_amt: float
    unpaid_amt: float
    payment_status: str | None = None
    lines: list[SalesDetailLine]
