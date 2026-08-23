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


class SalesListPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[SalesListItem]
    total: int
    page: int
    page_size: int
