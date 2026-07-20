/** Analysis 미러용 API 스텁 — 런타임 HTTP 없음. Private는 mobile/src/api/notifications.ts */

export type NotificationListQuery = {
  unread_only?: boolean
  noti_type_cd?: string
  limit?: number
}

export declare function fetchNotificationSummary(farmCd: string): Promise<{
  unread_count: number
  urgent_count: number
}>

export declare function fetchNotifications(
  farmCd: string,
  query?: NotificationListQuery,
): Promise<unknown[]>

export declare function markNotificationRead(
  farmCd: string,
  notiId: string,
): Promise<{ noti_id: string; read_yn: string }>

export declare function markAllNotificationsRead(
  farmCd: string,
): Promise<{ updated_count: number }>
