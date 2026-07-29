# -*- coding: utf-8 -*-
"""농약 API 확장 스키마 — 통계·사전·입고·재고 CRUD."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PesticideYearlyStatsItemDto(BaseModel):
    item_id: int
    item_nm: str
    spec_nm: str | None = None
    pest_category_nm: str | None = None
    total_qty: int = 0
    current_stock: int = 0
    daily: dict[str, int] = Field(default_factory=dict)


class PesticideYearlyStatsResponse(BaseModel):
    year: int
    spray_count_total: int = 0
    monthly_spray_counts: dict[str, int] = Field(default_factory=dict)
    items: list[PesticideYearlyStatsItemDto] = Field(default_factory=list)


class PesticideInfoSummaryDto(BaseModel):
    info_id: int
    pesticide_nm: str
    maker_nm: str | None = None
    ingredient_nm: str | None = None
    category_nm: str | None = None
    brand_nm: str | None = None
    stock_qty: int = 0


class PesticideInfoListResponse(BaseModel):
    items: list[PesticideInfoSummaryDto] = Field(default_factory=list)


class PesticideInfoDetailDto(BaseModel):
    info_id: int
    pesticide_nm: str
    maker_nm: str | None = None
    ingredient_nm: str | None = None
    category_nm: str | None = None
    brand_nm: str | None = None
    spec_nm: str | None = None
    dilution_guide: str | None = None
    usage_note: str | None = None
    caution_note: str | None = None
    rmk: str | None = None
    stock_qty: int = 0
    last_use_dt: str | None = None
    annual_use_qty: int = 0
    annual_use_cnt: int = 0
    pest_target_nm: str | None = None


class PesticideSupplierDto(BaseModel):
    supplier_id: int
    supplier_nm: str
    biz_reg_no: str | None = None
    ceo_nm: str | None = None
    addr: str | None = None


class PesticideSupplierListResponse(BaseModel):
    items: list[PesticideSupplierDto] = Field(default_factory=list)


class PesticideReceiptLineDto(BaseModel):
    line_id: int | None = None
    line_no: int = 1
    link_item_id: int | None = None
    info_id: int | None = None
    item_nm: str
    spec_nm: str | None = None
    qty: int = 0
    unit_price: float | None = None
    supply_amt: float | None = None
    tax_amt: float | None = None
    line_rmk: str | None = None


class PesticideReceiptSummaryDto(BaseModel):
    receipt_id: int
    receipt_dt: str
    supplier_id: int | None = None
    supplier_nm: str | None = None
    recipient_nm: str | None = None
    rmk: str | None = None
    stock_applied_yn: str = "N"
    line_count: int = 0
    total_qty: int = 0


class PesticideReceiptListResponse(BaseModel):
    items: list[PesticideReceiptSummaryDto] = Field(default_factory=list)


class PesticideReceiptDetailDto(BaseModel):
    receipt_id: int
    receipt_dt: str
    supplier_id: int | None = None
    supplier_nm_text: str | None = None
    recipient_nm: str | None = None
    rmk: str | None = None
    stock_applied_yn: str = "N"
    stock_applied_dt: str | None = None
    lines: list[PesticideReceiptLineDto] = Field(default_factory=list)


class PesticideReceiptSaveRequest(BaseModel):
    receipt_dt: str
    supplier_id: int | None = None
    supplier_nm_text: str = ""
    recipient_nm: str = ""
    rmk: str = ""
    lines: list[PesticideReceiptLineDto] = Field(default_factory=list)


class PesticideReceiptSaveResponse(BaseModel):
    receipt_id: int
    message: str = "저장되었습니다."


class PesticideReceiptApplyResponse(BaseModel):
    applied_count: int = 0
    created_names: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    message: str = ""


class PesticideMessageResponse(BaseModel):
    message: str


class PesticideItemUpdateRequest(BaseModel):
    item_nm: str
    spec_nm: str = ""
    pest_category_nm: str = ""
    qty_piece: int = 0
    warn_piece_below: int | None = None
    rmk: str = ""
    info_id: int | None = None


class PesticideStockOutRequest(BaseModel):
    """개인 판매 등 수동 출고."""

    qty: int = Field(..., ge=1)
    buyer_nm: str = ""
    rmk: str = ""


class PesticideStockOutResponse(BaseModel):
    item_id: int
    qty: int
    qty_after: int
    message: str


class PesticideStockHistRowDto(BaseModel):
    hist_id: int
    trans_type: str
    ref_table: str | None = None
    ref_id: int | None = None
    qty_delta: int = 0
    qty_after: int | None = None
    trans_dt: str
    rmk: str | None = None
    receipt_dt: str | None = None
    supplier_nm: str | None = None


class PesticideStockHistListResponse(BaseModel):
    item_id: int
    item_nm: str
    rows: list[PesticideStockHistRowDto] = Field(default_factory=list)
