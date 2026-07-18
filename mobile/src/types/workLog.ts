export type WorkLogMonthSummary = {
  work_day_count: number
  work_count: number
  resource_count: number
  labor_sum: number
  expense_sum: number
}

export type WorkLogDayCell = {
  work_dt: string
  weather_cd?: string
  weather_nm?: string
  work_rmk?: string
  has_issue: boolean
  work_names: string[]
  work_count: number
  extra_work_count: number
  resource_count: number
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
}

export type WorkLogDailyResponse = {
  success: boolean
  work_dt: string
  farm_cd: string
  master: WorkLogMasterDto | null
  works: WorkLogWorkItem[]
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
