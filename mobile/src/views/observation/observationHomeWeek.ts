/**
 * SCR-001 홈 — 최근 7일 목록 기반 KPI·AI 위험·최근 AI 실데이터 집계
 */
import { observationListThumbSrc } from '@/api/observationPhotos'
import {
  formatMdSlash,
  pastRangeStart,
  shiftIsoDays,
} from '@/views/observation/observationCalendar'
import type {
  AiRiskCardItem,
  RecentAiCardItem,
} from '@/views/observation/observationHomeCopy'
import {
  OBS_SEVERITY_CAUTION_CD,
  OBS_SEVERITY_DANGER_CD,
  OBS_TARGET_FRUIT_CD,
  OBS_TARGET_PEST_CD,
} from '@/composables/constants/app'
import type {
  ObservationListItem,
  ObservationSummary,
} from '@/types/observation'

function listThumbUrl(item: ObservationListItem): string | null {
  const src = observationListThumbSrc(item).trim()
  return src || null
}

const SEVERITY_RISK = new Set([OBS_SEVERITY_CAUTION_CD, OBS_SEVERITY_DANGER_CD])

const AI_ACTIVE = new Set([
  'ANALYZING',
  'ANALYZED',
  'COMPLETED',
  'CONFIRMED',
  'FAILED',
  'REVIEW_REQUIRED',
  'HOLD',
])

export const LABEL_HOME_WEEK_LIST = '최근 7일 관찰 내역'
export const HOME_WEEK_LIMIT = 200

export function homeWeekRange(today: string): { from: string; to: string } {
  const to = String(today || '').slice(0, 10)
  return { from: pastRangeStart(to), to }
}

export function isDefaultHomeWeekRange(
  from: string,
  to: string,
  today: string,
): boolean {
  const range = homeWeekRange(today)
  return (
    String(from || '').slice(0, 10) === range.from &&
    String(to || '').slice(0, 10) === range.to
  )
}

export function formatHomeObsTimeLabel(obsDt: string, today: string): string {
  const day = String(obsDt || '').slice(0, 10)
  const t = String(today || '').slice(0, 10)
  if (day === t) return '오늘'
  if (day === shiftIsoDays(t, -1)) return '어제'
  return formatMdSlash(day)
}

function aiStatus(item: ObservationListItem): string {
  return String(item.ai_status || 'NONE').trim().toUpperCase() || 'NONE'
}

export function isAiActiveStatus(status: string): boolean {
  return AI_ACTIVE.has(String(status || '').trim().toUpperCase())
}

export function isRiskSeverity(cd: string): boolean {
  return SEVERITY_RISK.has(String(cd || '').trim())
}

/** Hero KPI용 — ObservationSummary 형태 (ai_pending_count = 7일 AI 관여 건수) */
export function summarizeHomeWeek(
  items: ObservationListItem[],
  today: string,
): ObservationSummary {
  let pest = 0
  let fruit = 0
  let ai = 0
  let danger = 0
  let todayCount = 0
  const t = String(today || '').slice(0, 10)
  for (const item of items) {
    const target = String(item.target_type_cd || '').trim()
    if (target === OBS_TARGET_PEST_CD) pest += 1
    if (target === OBS_TARGET_FRUIT_CD) fruit += 1
    if (isAiActiveStatus(aiStatus(item))) ai += 1
    if (isRiskSeverity(String(item.severity_cd || ''))) danger += 1
    if (String(item.obs_dt || '').slice(0, 10) === t) todayCount += 1
  }
  return {
    today_count: todayCount,
    pest_count: pest,
    fruit_count: fruit,
    ai_pending_count: ai,
    danger_count: danger,
    as_of_date: t,
  }
}

function pestDisplayName(item: ObservationListItem): string {
  const title = String(item.obs_title || '').trim()
  if (title) return title
  const target = String(item.target_type_nm || '').trim()
  const sev = String(item.severity_nm || '').trim()
  if (target && sev) return `${target} · ${sev}`
  return target || sev || '관찰'
}

/** AI 위험 카드 타이틀 — 병해충명 우선 */
function riskPestName(item: ObservationListItem): string {
  const pest = String(item.ai_pest_nm || '').trim()
  if (pest) return pest
  return pestDisplayName(item)
}

/** 주의·위험 관찰 → AI 위험 슬라이드 */
export function mapHomeRiskItems(
  items: ObservationListItem[],
  today: string,
): AiRiskCardItem[] {
  return items
    .filter((item) => isRiskSeverity(String(item.severity_cd || '')))
    .map((item) => ({
      id: item.obs_id,
      pestName: riskPestName(item),
      severityLabel: String(item.severity_nm || '').trim() || '위험',
      timeLabel: formatHomeObsTimeLabel(item.obs_dt, today),
      thumbUrl: listThumbUrl(item),
    }))
}

/** AI 관여 관찰 → 최근 AI 분석 카드 */
export function mapHomeRecentAiItems(
  items: ObservationListItem[],
  today: string,
  limit = 12,
): RecentAiCardItem[] {
  return items
    .filter((item) => isAiActiveStatus(aiStatus(item)))
    .slice(0, limit)
    .map((item) => {
      const target = String(item.target_type_nm || '').trim()
      const site = String(item.site_nm || item.location_text || '').trim()
      const targetLabel = [target, site].filter(Boolean).join(' · ') || '관찰'
      return {
        id: item.obs_id,
        title: pestDisplayName(item),
        confidencePct: null,
        targetLabel,
        timeLabel: formatHomeObsTimeLabel(item.obs_dt, today),
        thumbUrl: listThumbUrl(item),
      }
    })
}
