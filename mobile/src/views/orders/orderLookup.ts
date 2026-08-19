import { todayIso } from '@/views/work-log/workLogConstants'
import {
  ORDER_QUICK_RANGE_OPTIONS,
  QUICK_RANGE_1M,
  QUICK_RANGE_3M,
  QUICK_RANGE_YEAR,
} from '@/views/orders/ordersConstants'

export function yearStartIso(today = todayIso()): string {
  return `${today.slice(0, 4)}-01-01`
}

export function defaultOrderLookupRange(today = todayIso()): { from: string; to: string } {
  return { from: yearStartIso(today), to: today }
}

/** 달력 월 이동. 말일 넘침은 해당 월 말일로 보정. */
export function shiftIsoMonths(iso: string, deltaMonths: number): string {
  const [y, m, d] = String(iso || '')
    .slice(0, 10)
    .split('-')
    .map(Number)
  if (!y || !m || !d) return iso
  let year = y
  let month = m + deltaMonths
  while (month < 1) {
    month += 12
    year -= 1
  }
  while (month > 12) {
    month -= 12
    year += 1
  }
  const last = new Date(Date.UTC(year, month, 0)).getUTCDate()
  const day = Math.min(d, last)
  return `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`
}

export function rangeForQuickKey(
  key: string,
  today = todayIso(),
): { from: string; to: string } {
  if (key === QUICK_RANGE_1M) {
    return { from: shiftIsoMonths(today, -1), to: today }
  }
  if (key === QUICK_RANGE_3M) {
    return { from: shiftIsoMonths(today, -3), to: today }
  }
  return defaultOrderLookupRange(today)
}

export function quickKeyForRange(
  from: string,
  to: string,
  today = todayIso(),
): string {
  if (to !== today) return ''
  if (from === yearStartIso(today)) return QUICK_RANGE_YEAR
  if (from === shiftIsoMonths(today, -1)) return QUICK_RANGE_1M
  if (from === shiftIsoMonths(today, -3)) return QUICK_RANGE_3M
  return ''
}

export const ORDER_QUICK_SEGMENT_OPTIONS = ORDER_QUICK_RANGE_OPTIONS.map((opt) => ({
  value: opt.value,
  label: opt.label,
}))
