export type WorkLogMonthSummary = {
  work_day_count: number
  work_count: number
  resource_count: number
  labor_hour_sum: number
  labor_sum: number
  expense_sum: number
  pesticide_count: number
  fertilizer_count: number
}

export type WorkLogDayWorkItem = {
  work_mid_cd: string
  work_mid_nm: string
  status_cd?: string | null
  /** 작업 메모 — 기타작업 캘린더 표시 */
  rmk?: string | null
}

export type WorkLogDayCell = {
  work_dt: string
  weather_cd?: string
  weather_nm?: string
  work_rmk?: string
  has_issue: boolean
  work_names: string[]
  work_items?: WorkLogDayWorkItem[]
  work_count: number
  extra_work_count: number
  resource_count: number
  labor_hour_sum?: number
  labor_sum: number
  expense_sum: number
  total_cost: number
  has_work: boolean
  has_in_progress: boolean
}

export type WorkLogMonthlyResponse = {
  success: boolean
  year: number
  month: number
  summary: WorkLogMonthSummary
  days: Record<string, WorkLogDayCell>
}

export type WorkLogMasterDto = {
  work_dt: string
  farm_cd: string
  day_of_week?: string | null
  weather_cd?: string | null
  weather_nm?: string | null
  temp_min?: number | null
  temp_max?: number | null
  precip?: number | null
  humidity?: number | null
  sun_rise?: string | null
  sun_set?: string | null
  sunshine_hr?: number | null
  wind_max?: number | null
  wind_min?: number | null
  work_rmk?: string | null
}

export type WorkLogWorkItem = {
  work_id: string
  work_dt: string
  farm_cd: string
  work_main_cd?: string
  work_mid_cd?: string | null
  work_mid_nm?: string | null
  work_loc_id?: string | null
  work_loc_nm?: string | null
  rmk?: string | null
  start_tm?: string | null
  end_tm?: string | null
  status_cd?: string | null
  status_nm?: string | null
  google_event_id?: string | null
  sync_status?: string | null
}

export type WorkLogDailyResponse = {
  success: boolean
  work_dt: string
  farm_cd: string
  master: WorkLogMasterDto | null
  works: WorkLogWorkItem[]
  resources?: WorkLogResourceDto[]
  expenses?: WorkLogExpenseDto[]
  pesticides?: WorkLogPesticideDocDto[]
}

export type WorkLogResourceDto = {
  res_id?: number | null
  work_id: string
  emp_cd: string
  emp_nm?: string
  man_hour: number
  daily_wage: number
  pay_method_cd?: string
  pay_method_nm?: string
  pay_status?: string
  slip_no?: string | null
}

export type WorkLogExpenseDto = {
  exp_id?: number | null
  work_id: string
  trans_dt?: string
  acct_cd: string
  acct_nm?: string
  item_nm?: string
  total_amt: number
  pay_method_cd?: string
  pay_method_nm?: string
  pay_status?: string
  slip_no?: string | null
}

export type WorkLogPesticideLineDto = {
  item_id: number
  use_qty: number
  item_nm_snapshot?: string
  spec_nm_snapshot?: string
  purpose_nm?: string
  line_rmk?: string
}

export type WorkLogPesticideDocDto = {
  work_id: string
  use_id?: number | null
  stock_applied_yn?: string
  lines: WorkLogPesticideLineDto[]
}

export type WorkLogLaborUpsertItem = {
  status?: string
  res_id?: number | null
  emp_cd: string
  emp_nm?: string | null
  man_hour?: number
  daily_wage?: number
  pay_method_cd?: string
  pay_status?: string
}

export type WorkLogExpenseUpsertItem = {
  status?: string
  exp_id?: number | null
  acct_cd: string
  item_nm?: string | null
  amt?: number
  pay_method_cd?: string
  pay_status?: string
  trans_dt?: string | null
}

export type WorkLogPesticideLineUpsert = {
  item_id: number
  use_qty?: number
  item_nm_snapshot?: string | null
  spec_nm_snapshot?: string | null
  purpose_nm?: string | null
  line_rmk?: string | null
}

export type WorkLogWorkIntegratedItem = {
  work_id?: string | null
  work_mid_cd: string
  work_mid_nm?: string | null
  work_loc_id?: string | null
  rmk?: string | null
  start_tm?: string | null
  end_tm?: string | null
  status_cd?: string | null
  pesticide_lines?: WorkLogPesticideLineUpsert[]
  replace_pesticide_use_id?: number | null
}

export type WorkLogIntegratedSavePayload = {
  master?: WorkLogMasterUpsertPayload | null
  works: WorkLogWorkIntegratedItem[]
  labor_work_id?: string | null
  labor_rows?: WorkLogLaborUpsertItem[]
  removed_res_ids?: number[]
  expense_work_id?: string | null
  expense_rows?: WorkLogExpenseUpsertItem[]
  removed_exp_ids?: number[]
  worker_nm?: string | null
}

export type WorkLogPesticideCancelPayload = {
  use_id: number
}


export type WorkLogMasterUpsertPayload = {
  day_of_week?: string | null
  weather_cd?: string | null
  temp_min?: number | null
  temp_max?: number | null
  precip?: number | null
  humidity?: number | null
  sun_rise?: string | null
  sun_set?: string | null
  sunshine_hr?: number | null
  wind_max?: number | null
  wind_min?: number | null
  work_rmk?: string | null
}

export type WorkLogWorkUpsertItem = {
  work_id?: string | null
  work_mid_cd: string
  work_loc_id?: string | null
  rmk?: string | null
  start_tm?: string | null
  end_tm?: string | null
  status_cd?: string | null
}

export type WorkLogWorksUpsertPayload = {
  works: WorkLogWorkUpsertItem[]
}

export type WorkLogSaveResponse = {
  success: boolean
  work_dt: string
  farm_cd: string
  message: string
  work_ids: string[]
}

export type WorkLogDeletePreviewResponse = {
  success: boolean
  work_id: string
  work_dt: string
  farm_cd: string
  work_mid_cd?: string | null
  work_mid_nm?: string | null
  rmk?: string | null
  status_cd?: string | null
  labor_count: number
  labor_amount: number
  expense_count: number
  expense_amount: number
  pesticide_count: number
  pesticide_item_names: string[]
  fertilizer_count: number
  fertilizer_item_names: string[]
  is_fertilizer_work: boolean
  fertilizer_note?: string | null
  photo_count: number
  google_calendar_linked: boolean
  has_related: boolean
}

export type WorkLogWeatherFetchPayload = {
  force_refresh?: boolean
}

export type WorkLogWeatherFetchResponse = {
  success: boolean
  work_dt: string
  farm_cd: string
  source: string
  elapsed: number
  message: string
  master: WorkLogMasterDto | null
}
