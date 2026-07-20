/**
 * SCR-001 Phase 3 — 주간 관찰 캘린더 집계·카피
 */
import type { ObservationListItem } from '@/types/observation'

export const LABEL_OBS_CALENDAR = '관찰 캘린더'
export const LABEL_OBS_DETAIL_LOOKUP = '관찰상세조회'

export type ObsCalDayCounts = {
  /** 과실(OB010200) · 수체/잎(OB010100) */
  leafFruit: number
  /** AI 파이프라인 진행·결과 (NONE 제외) */
  ai: number
  /** 주의·위험 (OS010300/OS010400) */
  danger: number
}

export type ObsCalLegendKey = keyof ObsCalDayCounts

export const OBS_CAL_LEGEND: ReadonlyArray<{
  key: ObsCalLegendKey
  label: string
  colorVar: string
}> = [
  {
    key: 'leafFruit',
    label: '과실/잎 관찰',
    colorVar: 'var(--ods-color-primary)',
  },
  {
    key: 'ai',
    label: 'AI 분석',
    colorVar: 'var(--ods-color-ai)',
  },
  {
    key: 'danger',
    label: '위험 관찰',
    colorVar: 'var(--ods-color-danger)',
  },
]

const TARGET_LEAF_FRUIT = new Set(['OB010200', 'OB010100'])
const SEVERITY_DANGER = new Set(['OS010300', 'OS010400'])

export function emptyObsCalDay(): ObsCalDayCounts {
  return { leafFruit: 0, ai: 0, danger: 0 }
}

export function aggregateObsCalendar(
  items: ObservationListItem[],
): Record<string, ObsCalDayCounts> {
  const map: Record<string, ObsCalDayCounts> = {}
  for (const item of items) {
    const dt = String(item.obs_dt || '').slice(0, 10)
    if (!/^\d{4}-\d{2}-\d{2}$/.test(dt)) continue
    const row = map[dt] ?? (map[dt] = emptyObsCalDay())
    if (TARGET_LEAF_FRUIT.has(String(item.target_type_cd || '').trim())) {
      row.leafFruit += 1
    }
    const ai = String(item.ai_status || 'NONE').trim().toUpperCase() || 'NONE'
    if (ai !== 'NONE') row.ai += 1
    if (SEVERITY_DANGER.has(String(item.severity_cd || '').trim())) {
      row.danger += 1
    }
  }
  return map
}

function toIso(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

export function weekStartSunday(iso: string): string {
  const d = new Date(`${iso}T12:00:00`)
  d.setDate(d.getDate() - d.getDay())
  return toIso(d)
}

export function shiftIsoDays(iso: string, delta: number): string {
  const d = new Date(`${iso}T12:00:00`)
  d.setDate(d.getDate() + delta)
  return toIso(d)
}

export function shiftIsoMonths(iso: string, delta: number): string {
  const d = new Date(`${iso}T12:00:00`)
  const day = d.getDate()
  d.setDate(1)
  d.setMonth(d.getMonth() + delta)
  const last = new Date(d.getFullYear(), d.getMonth() + 1, 0).getDate()
  d.setDate(Math.min(day, last))
  return toIso(d)
}

export function buildRangeIsos(startIso: string, length = 7): string[] {
  return Array.from({ length }, (_, i) => shiftIsoDays(startIso, i))
}

/** @deprecated use buildRangeIsos — 일~토 고정이 아닌 시작일 기준 7일 */
export function buildWeekIsos(weekStartIso: string): string[] {
  return buildRangeIsos(weekStartIso, 7)
}

export function monthLabelKo(iso: string): string {
  const d = new Date(`${iso}T12:00:00`)
  return `${d.getFullYear()}년 ${d.getMonth() + 1}월`
}

/** ISO(YYYY-MM-DD) → MM/DD */
export function formatMdSlash(iso: string): string {
  const m = String(iso || '')
    .slice(0, 10)
    .match(/^(\d{4})-(\d{2})-(\d{2})$/)
  if (!m) return String(iso || '')
  return `${m[2]}/${m[3]}`
}

/** 관찰내역(MM/DD ~ MM/DD) */
export function formatObsListRangeLabel(fromIso: string, toIso: string): string {
  return `관찰내역(${formatMdSlash(fromIso)} ~ ${formatMdSlash(toIso)})`
}

/** 오늘 포함 과거 7일 시작일 (today − 6) */
export function pastRangeStart(todayIso: string): string {
  return shiftIsoDays(String(todayIso || '').slice(0, 10), -6)
}

/** 시작일 기준 연속 7일 (과거 구간: start = today-6 → 오늘까지) */
export function rangeFromStart(startIso: string): {
  from: string
  to: string
} {
  const from = String(startIso || '').slice(0, 10)
  return { from, to: shiftIsoDays(from, 6) }
}

/** @deprecated use rangeFromStart */
export function weekRangeFromSelected(iso: string): {
  from: string
  to: string
} {
  return rangeFromStart(weekStartSunday(iso))
}
