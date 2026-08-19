# -*- coding: utf-8 -*-
"""영농일지 MVP 스키마 — 월간·일간(기상·이슈·작업)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class WorkLogMonthSummary(BaseModel):
    work_day_count: int = 0
    work_count: int = 0
    resource_count: int = 0
    labor_hour_sum: float = 0.0
    labor_sum: float = 0.0
    expense_sum: float = 0.0
    pesticide_count: int = 0
    fertilizer_count: int = 0


class WorkLogDayWorkItem(BaseModel):
    """월간 셀용 작업 한 건 — 농약/비료/기타 필터는 mid_cd 기준."""

    work_mid_cd: str = ""
    work_mid_nm: str = ""
    status_cd: str | None = None
    # 작업 메모 — 기타작업(WK010600) 캘린더 표시용
    rmk: str | None = None


class WorkLogDayCell(BaseModel):
    work_dt: str
    weather_cd: str = ""
    weather_nm: str = ""
    work_rmk: str = ""
    has_issue: bool = False
    work_names: list[str] = Field(default_factory=list)
    work_items: list[WorkLogDayWorkItem] = Field(default_factory=list)
    work_count: int = 0
    extra_work_count: int = 0
    resource_count: int = 0
    labor_hour_sum: float = 0.0
    labor_sum: float = 0.0
    expense_sum: float = 0.0
    total_cost: float = 0.0
    has_work: bool = False
    has_in_progress: bool = False


class WorkLogMonthlyResponse(BaseModel):
    success: bool = True
    year: int
    month: int
    summary: WorkLogMonthSummary
    days: dict[str, WorkLogDayCell] = Field(default_factory=dict)


class WorkLogMasterDto(BaseModel):
    work_dt: str
    farm_cd: str
    day_of_week: str | None = None
    weather_cd: str | None = None
    weather_nm: str | None = None
    temp_min: float | None = None
    temp_max: float | None = None
    precip: float | None = None
    humidity: float | None = None
    sun_rise: str | None = None
    sun_set: str | None = None
    sunshine_hr: float | None = None
    wind_max: float | None = None
    wind_min: float | None = None
    work_rmk: str | None = None


class WorkLogWorkItem(BaseModel):
    work_id: str
    work_dt: str
    farm_cd: str
    work_main_cd: str = "WK01"
    work_mid_cd: str | None = None
    work_mid_nm: str | None = None
    work_loc_id: str | None = None
    work_loc_nm: str | None = None
    rmk: str | None = None
    start_tm: str | None = None
    end_tm: str | None = None
    status_cd: str | None = None
    status_nm: str | None = None
    google_event_id: str | None = None
    sync_status: str | None = None
    variety_cd: str | None = None
    variety_nm: str | None = None
    harvest_container_qty: int | None = None


class WorkLogDailyResponse(BaseModel):
    success: bool = True
    work_dt: str
    farm_cd: str
    master: WorkLogMasterDto | None = None
    works: list[WorkLogWorkItem] = Field(default_factory=list)
    resources: list["WorkLogResourceDto"] = Field(default_factory=list)
    expenses: list["WorkLogExpenseDto"] = Field(default_factory=list)
    pesticides: list["WorkLogPesticideDocDto"] = Field(default_factory=list)


class WorkLogResourceDto(BaseModel):
    res_id: int | None = None
    work_id: str
    emp_cd: str = ""
    emp_nm: str = ""
    man_hour: float = 0.0
    daily_wage: float = 0.0
    pay_method_cd: str = ""
    pay_method_nm: str = ""
    pay_status: str = "N"
    slip_no: str | None = None


class WorkLogExpenseDto(BaseModel):
    exp_id: int | None = None
    work_id: str
    trans_dt: str = ""
    acct_cd: str = ""
    acct_nm: str = ""
    item_nm: str = ""
    total_amt: float = 0.0
    pay_method_cd: str = ""
    pay_method_nm: str = ""
    pay_status: str = "N"
    slip_no: str | None = None


class WorkLogPesticideLineDto(BaseModel):
    item_id: int
    use_qty: int = 0
    item_nm_snapshot: str = ""
    spec_nm_snapshot: str = ""
    purpose_nm: str = ""
    line_rmk: str = ""


class WorkLogPesticideDocDto(BaseModel):
    work_id: str
    use_id: int | None = None
    stock_applied_yn: str = "N"
    lines: list[WorkLogPesticideLineDto] = Field(default_factory=list)


class WorkLogLaborUpsertItem(BaseModel):
    status: str = "INS"  # INS/MOD/ORG
    res_id: int | None = None
    emp_cd: str
    emp_nm: str | None = None
    man_hour: float = 0.0
    daily_wage: float = 0.0
    pay_method_cd: str = ""
    pay_status: str = "N"


class WorkLogExpenseUpsertItem(BaseModel):
    status: str = "INS"
    exp_id: int | None = None
    acct_cd: str
    item_nm: str | None = None
    amt: float = 0.0
    pay_method_cd: str = ""
    pay_status: str = "N"
    trans_dt: str | None = None


class WorkLogPesticideLineUpsert(BaseModel):
    item_id: int
    use_qty: int = 0
    item_nm_snapshot: str | None = None
    spec_nm_snapshot: str | None = None
    purpose_nm: str | None = None
    line_rmk: str | None = None


class WorkLogWorkIntegratedItem(BaseModel):
    work_id: str | None = None
    work_mid_cd: str
    work_mid_nm: str | None = None
    work_loc_id: str | None = None
    rmk: str | None = None
    start_tm: str | None = None
    end_tm: str | None = None
    status_cd: str | None = None
    pesticide_lines: list[WorkLogPesticideLineUpsert] = Field(default_factory=list)
    replace_pesticide_use_id: int | None = None
    variety_cd: str | None = None
    harvest_container_qty: int | None = None


class WorkLogIntegratedSaveRequest(BaseModel):
    """PC 최종승인과 동일 — Core WorkLogIntegratedSaveService."""

    master: WorkLogMasterUpsertRequest | None = None
    works: list[WorkLogWorkIntegratedItem] = Field(default_factory=list)
    labor_work_id: str | None = None
    labor_rows: list[WorkLogLaborUpsertItem] = Field(default_factory=list)
    removed_res_ids: list[int] = Field(default_factory=list)
    expense_work_id: str | None = None
    expense_rows: list[WorkLogExpenseUpsertItem] = Field(default_factory=list)
    removed_exp_ids: list[int] = Field(default_factory=list)
    worker_nm: str | None = None


class WorkLogPesticideCancelRequest(BaseModel):
    use_id: int


class WorkLogPesticideCancelAllRequest(BaseModel):
    work_id: str


class WorkLogPesticideReplaceRequest(BaseModel):
    use_id: int
    use_dt: str
    work_id: str | None = None
    site_id: str | None = None
    worker_nm: str | None = None
    work_type_nm: str | None = None
    rmk: str | None = None
    lines: list[WorkLogPesticideLineUpsert] = Field(default_factory=list)


class WorkLogPesticideCancelResponse(BaseModel):
    success: bool = True
    message: str = "농약 사용이 취소되었습니다."


class WorkLogDeletePreviewResponse(BaseModel):
    """삭제 확인 모달 — work_id 연관정보 요약."""

    success: bool = True
    work_id: str
    work_dt: str
    farm_cd: str
    work_mid_cd: str | None = None
    work_mid_nm: str | None = None
    rmk: str | None = None
    status_cd: str | None = None
    labor_count: int = 0
    labor_amount: float = 0.0
    expense_count: int = 0
    expense_amount: float = 0.0
    pesticide_count: int = 0
    pesticide_item_names: list[str] = Field(default_factory=list)
    fertilizer_count: int = 0
    fertilizer_item_names: list[str] = Field(default_factory=list)
    is_fertilizer_work: bool = False
    fertilizer_note: str | None = None
    photo_count: int = 0
    google_calendar_linked: bool = False
    has_related: bool = False


class WorkLogMasterUpsertRequest(BaseModel):
    day_of_week: str | None = None
    weather_cd: str | None = None
    temp_min: float | None = None
    temp_max: float | None = None
    precip: float | None = None
    humidity: float | None = None
    sun_rise: str | None = None
    sun_set: str | None = None
    sunshine_hr: float | None = None
    wind_max: float | None = None
    wind_min: float | None = None
    work_rmk: str | None = None


class WorkLogWorkUpsertItem(BaseModel):
    work_id: str | None = None
    work_mid_cd: str
    work_loc_id: str | None = None
    rmk: str | None = None
    start_tm: str | None = None
    end_tm: str | None = None
    status_cd: str | None = None
    variety_cd: str | None = None
    harvest_container_qty: int | None = None


class WorkLogWorksUpsertRequest(BaseModel):
    works: list[WorkLogWorkUpsertItem] = Field(default_factory=list)


class WorkLogSaveResponse(BaseModel):
    success: bool = True
    work_dt: str
    farm_cd: str
    message: str = "저장되었습니다."
    work_ids: list[str] = Field(default_factory=list)


class WorkLogWeatherFetchRequest(BaseModel):
    """PC ‘날씨 가져오기’와 동일 — force_refresh 시 캐시 무시."""

    force_refresh: bool = False


class WorkLogWeatherFetchResponse(BaseModel):
    """외부 API/캐시 조회 결과. master 자동 저장은 하지 않음(PC와 동일)."""

    success: bool = True
    work_dt: str
    farm_cd: str
    source: str = ""
    elapsed: float = 0.0
    message: str = "날씨 조회가 완료되었습니다."
    master: WorkLogMasterDto | None = None


# --- SCR-011 입력 피커 마스터 (PC 콤보와 동일 소스) ---


class WorkLogPartnerOption(BaseModel):
    pt_id: str
    pt_nm: str
    base_price: float | None = None
    worker_type_cd: str | None = None


class WorkLogAccountCodeOption(BaseModel):
    acct_cd: str
    acct_nm: str
    acct_level: int | None = None


class WorkLogPesticideItemOption(BaseModel):
    item_id: int
    item_nm: str
    spec_nm: str | None = None
    qty_piece: int = 0
    pest_category_nm: str | None = None
