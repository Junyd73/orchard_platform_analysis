import type { RouteLocationRaw } from 'vue-router'

import type { NotificationPayload } from '@/types/notification'

/** NTF-001 route 키 → Vue Router name */
const ROUTE_ALIAS: Record<string, string> = {
  'observation-detail': 'observation-detail',
  'observation-list': 'observation',
  observation: 'observation',
  'work-log-daily': 'work-log-daily',
  'work-log': 'work-log',
}

/**
 * payload_json → Vue Router 이동 대상.
 * SSOT: NTF-001 `{ route, obs_id?, work_dt? }`
 * 호환: `{ route_name, params }` / `{ path }`
 * 딥링크 없으면 null (읽음만 처리)
 */
export function resolveNotificationDeepLink(
  payload: NotificationPayload | null | undefined,
): RouteLocationRaw | null {
  if (!payload || typeof payload !== 'object') return null

  const path = String(payload.path || '').trim()
  if (path.startsWith('/')) {
    return path
  }

  const routeNameRaw = String(
    payload.route_name || payload.route || '',
  ).trim()
  if (!routeNameRaw) return null

  const name = ROUTE_ALIAS[routeNameRaw] || routeNameRaw

  if (payload.params && typeof payload.params === 'object' && !Array.isArray(payload.params)) {
    const params: Record<string, string> = {}
    for (const [k, v] of Object.entries(payload.params as Record<string, unknown>)) {
      if (v == null) continue
      params[k] = String(v)
    }
    if (Object.keys(params).length > 0) {
      return { name, params }
    }
  }

  if (name === 'observation-detail') {
    const obsId = String(payload.obs_id || payload.obsId || '').trim()
    if (!obsId) return null
    return { name: 'observation-detail', params: { obsId } }
  }

  if (name === 'work-log-daily') {
    const workDt = String(payload.work_dt || payload.workDt || '').trim()
    if (!workDt) return null
    return { name: 'work-log-daily', params: { workDt } }
  }

  if (name === 'observation' || name === 'work-log') {
    return { name }
  }

  return { name }
}
