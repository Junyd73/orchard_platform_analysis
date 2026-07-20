/** 알림 API — NTF-001 */

export type NotificationPayload = {
  /** NTF-001 SSOT 딥링크 키 */
  route?: string
  obs_id?: string
  work_dt?: string
  /** 지시서 호환 */
  route_name?: string
  params?: Record<string, string | number>
  path?: string
  obsId?: string
  workDt?: string
  [key: string]: unknown
}

export type NotificationItem = {
  noti_id: string
  farm_cd: string
  noti_type_cd: string
  noti_type_nm: string
  priority_cd: string
  priority_nm: string
  title: string
  body?: string | null
  payload?: NotificationPayload | null
  source_cd: string
  ref_type?: string | null
  ref_id?: string | null
  event_at: string
  read_yn: string
  read_dt?: string | null
}

export type NotificationSummary = {
  unread_count: number
  urgent_count: number
}

export type NotificationReadResponse = {
  noti_id: string
  read_yn: string
  read_dt?: string | null
}

export type NotificationReadAllResponse = {
  updated_count: number
}
