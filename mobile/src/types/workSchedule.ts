/** 영농 일정(Schedule) — WLS-001 */

export const SCHED_STATUS_PENDING = 'WS010100'
export const SCHED_STATUS_CONVERTED = 'WS010200'
export const SCHED_STATUS_CANCELLED = 'WS010300'

export type WorkScheduleItem = {
  farm_cd: string
  sched_id: string
  work_dt: string
  work_main_cd: string
  work_mid_cd: string
  work_loc_id?: string | null
  title?: string | null
  contents?: string | null
  sched_status_cd: string
  converted_work_id?: string | null
  google_event_id?: string | null
  sync_status?: string
  last_synced_at?: string | null
}

export type WorkScheduleListResponse = {
  success: boolean
  data: WorkScheduleItem[]
}

export type WorkScheduleCreatePayload = {
  work_dt: string
  work_mid_cd: string
  work_loc_id?: string | null
  title?: string | null
  contents?: string | null
}

export type WorkScheduleCreateResponse = {
  success: boolean
  data: {
    sched_id: string
    sched_status_cd: string
  }
}

export type WorkScheduleConvertResponse = {
  success: boolean
  data: {
    sched_id: string
    work_id: string
    prefilled_data: {
      work_dt: string
      work_mid_cd: string
      work_loc_id?: string | null
      memo: string
    }
  }
}
