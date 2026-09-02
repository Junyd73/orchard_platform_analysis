import { shiftIsoMonths } from '@/views/orders/orderLookup'
import {
  MSG_HARVEST_RANGE_INVALID,
  MSG_HARVEST_RANGE_REQUIRED,
} from '@/views/production/productionConstants'
import { todayIso } from '@/views/work-log/workLogConstants'

/** 수확기록 조회 기본: 오늘 포함 최근 1개월 */
export function defaultHarvestRecordRange(today = todayIso()): { from: string; to: string } {
  return { from: shiftIsoMonths(today, -1), to: today }
}

export function validateHarvestDateRange(from: string, to: string): string {
  const f = String(from || '').slice(0, 10)
  const t = String(to || '').slice(0, 10)
  if (!f || !t) return MSG_HARVEST_RANGE_REQUIRED
  if (f > t) return MSG_HARVEST_RANGE_INVALID
  return ''
}
