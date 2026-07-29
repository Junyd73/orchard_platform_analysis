/** 홈 대시보드 — 기존 REST 병렬 조회·매핑 (신규 홈 API 없음) */
import { fetchObservations, fetchObservationSummary } from '@/api/observations'
import { fetchSmartSprayBriefing } from '@/api/smartSpray'
import type { SmartSprayBriefingCard } from '@/api/smartSpray'
import { fetchWorkLogDaily, fetchWorkLogWeather } from '@/api/workLogs'
import { fetchWorkSchedules } from '@/api/workSchedules'
import {
  HOME_BRIEFING_KIND,
  HOME_BRIEFING_PRECIP_CAUTION_PCT,
  HOME_BRIEFING_WORK_FALLBACK,
  HOME_RECENT_BADGE_AI_PENDING,
  HOME_RECENT_LIMIT,
  HOME_RECENT_OBS_DAYS,
  HOME_RECENT_TIME_TODAY,
  HOME_RECENT_TIME_YESTERDAY,
  HOME_RECENT_TITLE_OBS,
  HOME_RECENT_TITLE_WORK,
  HOME_SMART_SPRAY_EMPTY_HINT,
  HOME_SMART_SPRAY_EMPTY_PEST,
  HOME_SMART_SPRAY_EMPTY_RISK,
  HOME_SMART_SPRAY_HINT_FALLBACK,
  HOME_SPRAY_RISK_CAUTION,
  HOME_SPRAY_RISK_DANGER,
  HOME_SPRAY_TITLE_KEYWORD,
  HOME_WEATHER_SKY_FALLBACK,
  HOME_WORK_STATUS_CANCELLED_CD,
  HOME_WORK_STATUS_IN_PROGRESS_CD,
} from '@/views/home/homeConstants'
import type {
  HomeBriefingItem,
  HomeKpiMock,
  HomeRecentItem,
  HomeSmartSprayMock,
  HomeWeatherMock,
} from '@/views/home/homeMock'
import { todayIso, WORK_MID_CD_PESTICIDE } from '@/views/work-log/workLogConstants'
import type { ObservationListItem } from '@/types/observation'
import type {
  WorkLogDailyResponse,
  WorkLogMasterDto,
  WorkLogWorkItem,
} from '@/types/workLog'
import {
  SCHED_STATUS_PENDING,
  type WorkScheduleItem,
} from '@/types/workSchedule'

export type HomeDashboardData = {
  kpi: HomeKpiMock
  smartSpray: HomeSmartSprayMock
  weather: HomeWeatherMock
  briefing: HomeBriefingItem[]
  recent: HomeRecentItem[]
}

export type LoadHomeDashboardOptions = {
  farmNm?: string | null
  farmAddress?: string | null
}

export const HOME_KPI_EMPTY: HomeKpiMock = {
  todayWork: 0,
  laborCount: 0,
  pestCaution: 0,
  sprayPlan: 0,
}

export const HOME_SMART_SPRAY_EMPTY: HomeSmartSprayMock = {
  pestName: HOME_SMART_SPRAY_EMPTY_PEST,
  riskLabel: HOME_SMART_SPRAY_EMPTY_RISK,
  hint: HOME_SMART_SPRAY_EMPTY_HINT,
}

export const HOME_WEATHER_EMPTY: HomeWeatherMock = {
  location: '',
  tempC: 0,
  tempMinC: 0,
  tempMaxC: 0,
  skyLabel: HOME_WEATHER_SKY_FALLBACK,
  humidityPct: 0,
  windMs: 0,
  precipPct: 0,
}

/** AI 대기·진행 중 — 최근 활동 뱃지 */
const AI_PENDING_STATUSES = new Set([
  'PENDING',
  'ANALYZING',
  'REVIEW_REQUIRED',
  'HOLD',
])

type RecentSortable = HomeRecentItem & { sortKey: string }

function settledValue<T>(r: PromiseSettledResult<T>): T | null {
  return r.status === 'fulfilled' ? r.value : null
}

/** 로컬 정오 기준 ±일 (타임존 경계 완화) */
export function shiftIsoDays(iso: string, delta: number): string {
  const d = new Date(`${iso}T12:00:00`)
  d.setDate(d.getDate() + delta)
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function numOrZero(v: number | null | undefined): number {
  return v == null || Number.isNaN(Number(v)) ? 0 : Number(v)
}

function avgTempC(min: number | null | undefined, max: number | null | undefined): number {
  if (min != null && max != null) return Math.round((Number(min) + Number(max)) / 2)
  if (max != null) return Math.round(Number(max))
  if (min != null) return Math.round(Number(min))
  return 0
}

function isSprayCautionRisk(level: string): boolean {
  return level === HOME_SPRAY_RISK_CAUTION || level === HOME_SPRAY_RISK_DANGER
}

function isPendingSpraySchedule(s: WorkScheduleItem): boolean {
  if (s.sched_status_cd !== SCHED_STATUS_PENDING) return false
  if (String(s.work_mid_cd || '').trim() === WORK_MID_CD_PESTICIDE) return true
  return String(s.title || '').includes(HOME_SPRAY_TITLE_KEYWORD)
}

function topSprayCard(cards: SmartSprayBriefingCard[]): SmartSprayBriefingCard | null {
  if (!cards.length) return null
  return [...cards].sort((a, b) => Number(b.score || 0) - Number(a.score || 0))[0] ?? null
}

function formatRecentDayLabel(day: string, today: string): string {
  const d = String(day || '').slice(0, 10)
  const t = String(today || '').slice(0, 10)
  if (d === t) return HOME_RECENT_TIME_TODAY
  if (d === shiftIsoDays(t, -1)) return HOME_RECENT_TIME_YESTERDAY
  if (/^\d{4}-\d{2}-\d{2}$/.test(d)) {
    return `${d.slice(5, 7)}/${d.slice(8, 10)}`
  }
  return d || HOME_RECENT_TIME_TODAY
}

function obsAiBadge(item: ObservationListItem): string | undefined {
  const st = String(item.ai_status || '').trim().toUpperCase()
  if (AI_PENDING_STATUSES.has(st)) return HOME_RECENT_BADGE_AI_PENDING
  const prog = String(item.progress_status_nm || '').trim()
  if (prog && /대기|분석/.test(prog)) return prog
  return undefined
}

function mapObservationRecent(
  items: ObservationListItem[],
  today: string,
): RecentSortable[] {
  return (items || []).map((item) => {
    const day = String(item.obs_dt || '').slice(0, 10)
    const detail =
      String(item.obs_title || '').trim() ||
      String(item.target_type_nm || '').trim() ||
      String(item.site_nm || item.location_text || '').trim() ||
      HOME_BRIEFING_WORK_FALLBACK
    return {
      id: `obs:${item.obs_id}`,
      title: HOME_RECENT_TITLE_OBS,
      detail,
      timeLabel: formatRecentDayLabel(day, today),
      badge: obsAiBadge(item),
      sortKey: `${day}T99:${item.obs_id}`,
    }
  })
}

function mapWorkRecent(
  daily: WorkLogDailyResponse | null,
  today: string,
): RecentSortable[] {
  if (!daily) return []
  const day = String(daily.work_dt || '').slice(0, 10)
  const works = (daily.works || []).filter(
    (w) => String(w.status_cd || '').trim() !== HOME_WORK_STATUS_CANCELLED_CD,
  )
  return works.map((w: WorkLogWorkItem, idx: number) => {
    const tm = String(w.start_tm || w.end_tm || '').trim() || '00:00'
    const detail =
      String(w.work_mid_nm || '').trim() || HOME_BRIEFING_WORK_FALLBACK
    return {
      id: `work:${w.work_id || `${day}-${idx}`}`,
      title: HOME_RECENT_TITLE_WORK,
      detail,
      timeLabel: formatRecentDayLabel(day, today),
      sortKey: `${day}T${tm}:${w.work_id || idx}`,
    }
  })
}

export function mapHomeRecent(input: {
  observations: ObservationListItem[]
  todayDaily: WorkLogDailyResponse | null
  yesterdayDaily: WorkLogDailyResponse | null
  today: string
  limit?: number
}): HomeRecentItem[] {
  const limit = input.limit ?? HOME_RECENT_LIMIT
  const merged: RecentSortable[] = [
    ...mapObservationRecent(input.observations, input.today),
    ...mapWorkRecent(input.todayDaily, input.today),
    ...mapWorkRecent(input.yesterdayDaily, input.today),
  ]
  merged.sort((a, b) => b.sortKey.localeCompare(a.sortKey))
  return merged.slice(0, limit).map(({ sortKey: _sk, ...rest }) => rest)
}

export function mapHomeKpi(
  daily: WorkLogDailyResponse | null,
  cards: SmartSprayBriefingCard[],
  schedules: WorkScheduleItem[],
): HomeKpiMock {
  const works = daily?.works ?? []
  const todayWork = works.filter(
    (w) => String(w.status_cd || '').trim() !== HOME_WORK_STATUS_CANCELLED_CD,
  ).length

  const empSet = new Set<string>()
  for (const r of daily?.resources ?? []) {
    const cd = String(r.emp_cd || '').trim()
    if (cd) empSet.add(cd)
  }

  return {
    todayWork,
    laborCount: empSet.size,
    pestCaution: cards.filter((c) => isSprayCautionRisk(String(c.risk_level || '').trim()))
      .length,
    sprayPlan: schedules.filter(isPendingSpraySchedule).length,
  }
}

export function mapHomeSmartSpray(cards: SmartSprayBriefingCard[]): HomeSmartSprayMock {
  const top = topSprayCard(cards)
  if (!top) return { ...HOME_SMART_SPRAY_EMPTY }
  const hint =
    (top.reasons || []).map((r) => String(r || '').trim()).find(Boolean) ||
    HOME_SMART_SPRAY_HINT_FALLBACK
  return {
    pestName: String(top.pest_nm || '').trim() || HOME_SMART_SPRAY_EMPTY_PEST,
    riskLabel: String(top.risk_level || '').trim() || HOME_SMART_SPRAY_EMPTY_RISK,
    hint,
  }
}

export function mapHomeWeather(
  master: WorkLogMasterDto | null | undefined,
  options?: LoadHomeDashboardOptions,
): HomeWeatherMock {
  const address = String(options?.farmAddress || '').trim()
  const farmNm = String(options?.farmNm || '').trim()
  const location = address || farmNm
  if (!master) {
    return { ...HOME_WEATHER_EMPTY, location }
  }
  const tempMinC = numOrZero(master.temp_min)
  const tempMaxC = numOrZero(master.temp_max)
  return {
    location,
    tempC: avgTempC(master.temp_min, master.temp_max),
    tempMinC,
    tempMaxC,
    skyLabel: String(master.weather_nm || '').trim() || HOME_WEATHER_SKY_FALLBACK,
    humidityPct: numOrZero(master.humidity),
    windMs: numOrZero(master.wind_max),
    precipPct: numOrZero(master.precip),
  }
}

function formatWorkTm(tm: string | null | undefined): string {
  const raw = String(tm || '').trim()
  if (!raw) return ''
  if (/^\d{1,2}:\d{2}/.test(raw)) return raw.slice(0, 5)
  if (/^\d{3,4}$/.test(raw)) {
    const p = raw.padStart(4, '0')
    return `${p.slice(0, 2)}:${p.slice(2)}`
  }
  return raw
}

function buildWeatherBriefing(weather: HomeWeatherMock): HomeBriefingItem | null {
  const precip = weather.precipPct
  if (precip >= HOME_BRIEFING_PRECIP_CAUTION_PCT) {
    return {
      kind: HOME_BRIEFING_KIND.WEATHER,
      title: `강수확률 ${precip}% · 비 주의`,
    }
  }
  const sky = String(weather.skyLabel || '').trim()
  const hasSky = Boolean(sky && sky !== HOME_WEATHER_SKY_FALLBACK)
  const hasTemp = weather.tempMinC !== 0 || weather.tempMaxC !== 0 || weather.tempC !== 0
  if (!hasSky && !hasTemp) return null
  const skyPart = hasSky ? sky : HOME_WEATHER_SKY_FALLBACK
  return {
    kind: HOME_BRIEFING_KIND.WEATHER,
    title: `${skyPart} · ${weather.tempMinC}~${weather.tempMaxC}℃`,
  }
}

function buildPestBriefing(cards: SmartSprayBriefingCard[]): HomeBriefingItem | null {
  const top = topSprayCard(cards)
  if (!top) return null
  const pest = String(top.pest_nm || '').trim()
  const risk = String(top.risk_level || '').trim()
  if (!pest && !risk) return null
  return {
    kind: HOME_BRIEFING_KIND.PEST,
    title: `「${pest || HOME_SMART_SPRAY_EMPTY_PEST} ${risk || HOME_SMART_SPRAY_EMPTY_RISK}」`,
  }
}

function inProgressWorks(daily: WorkLogDailyResponse | null) {
  return (daily?.works ?? []).filter(
    (w) => String(w.status_cd || '').trim() === HOME_WORK_STATUS_IN_PROGRESS_CD,
  )
}

function buildInProgressBriefing(
  todayDaily: WorkLogDailyResponse | null,
  yesterdayDaily: WorkLogDailyResponse | null,
): HomeBriefingItem | null {
  const today = inProgressWorks(todayDaily)
  if (today.length) {
    const name =
      String(today[0]?.work_mid_nm || '').trim() || HOME_BRIEFING_WORK_FALLBACK
    return {
      kind: HOME_BRIEFING_KIND.IN_PROGRESS,
      title: `오늘 ${name} ${today.length}건 진행중`,
    }
  }
  const yest = inProgressWorks(yesterdayDaily)
  if (yest.length) {
    const name =
      String(yest[0]?.work_mid_nm || '').trim() || HOME_BRIEFING_WORK_FALLBACK
    return {
      kind: HOME_BRIEFING_KIND.IN_PROGRESS,
      title: `어제 ${name} ${yest.length}건 진행중`,
    }
  }
  return null
}

function buildScheduleBriefing(schedules: WorkScheduleItem[]): HomeBriefingItem | null {
  const pending = schedules.filter((s) => s.sched_status_cd === SCHED_STATUS_PENDING)
  if (!pending.length) return null
  const sorted = [...pending].sort((a, b) => {
    const ta = formatWorkTm(a.work_tm) || '99:99'
    const tb = formatWorkTm(b.work_tm) || '99:99'
    return ta.localeCompare(tb)
  })
  const first = sorted[0]
  const tm = formatWorkTm(first?.work_tm)
  const title =
    String(first?.title || '').trim() || HOME_BRIEFING_WORK_FALLBACK
  const nextPart = tm ? `다음 ${tm} ${title}` : `다음 ${title}`
  return {
    kind: HOME_BRIEFING_KIND.TODAY_SCHEDULE,
    title: `오늘 ${pending.length}건 · ${nextPart}`,
  }
}

function buildObservationBriefing(aiPending: number): HomeBriefingItem | null {
  if (aiPending <= 0) return null
  return {
    kind: HOME_BRIEFING_KIND.OBSERVATION,
    title: `관찰 AI 대기 ${aiPending}건`,
  }
}

export function mapHomeBriefing(input: {
  weather: HomeWeatherMock
  cards: SmartSprayBriefingCard[]
  todayDaily: WorkLogDailyResponse | null
  yesterdayDaily: WorkLogDailyResponse | null
  schedules: WorkScheduleItem[]
  aiPendingCount: number
}): HomeBriefingItem[] {
  const items: HomeBriefingItem[] = []
  const weather = buildWeatherBriefing(input.weather)
  if (weather) items.push(weather)
  const pest = buildPestBriefing(input.cards)
  if (pest) items.push(pest)
  const inProg = buildInProgressBriefing(input.todayDaily, input.yesterdayDaily)
  if (inProg) items.push(inProg)
  const sched = buildScheduleBriefing(input.schedules)
  if (sched) items.push(sched)
  const obs = buildObservationBriefing(input.aiPendingCount)
  if (obs) items.push(obs)
  return items
}

export async function loadHomeDashboard(
  farmCd: string,
  options?: LoadHomeDashboardOptions,
): Promise<HomeDashboardData> {
  const today = todayIso()
  const yesterday = shiftIsoDays(today, -1)
  const obsFrom = shiftIsoDays(today, -(HOME_RECENT_OBS_DAYS - 1))

  const [
    dailyRes,
    weatherRes,
    sprayRes,
    schedRes,
    obsRes,
    yestRes,
    obsListRes,
  ] = await Promise.allSettled([
    fetchWorkLogDaily(farmCd, today),
    fetchWorkLogWeather(farmCd, today, { force_refresh: false }),
    fetchSmartSprayBriefing(farmCd),
    fetchWorkSchedules(farmCd, {
      start_dt: today,
      end_dt: today,
      status_cd: SCHED_STATUS_PENDING,
    }),
    fetchObservationSummary(farmCd, today),
    fetchWorkLogDaily(farmCd, yesterday),
    fetchObservations(farmCd, {
      date_from: obsFrom,
      date_to: today,
      sort: 'obs_dt_desc',
      limit: 30,
    }),
  ])

  const todayDaily = settledValue(dailyRes)
  const weatherPayload = settledValue(weatherRes)
  const sprayPayload = settledValue(sprayRes)
  const schedPayload = settledValue(schedRes)
  const obsPayload = settledValue(obsRes)
  const yesterdayDaily = settledValue(yestRes)
  const observations = settledValue(obsListRes) ?? []

  const cards = sprayPayload?.cards ?? []
  const schedules = schedPayload?.data ?? []

  const weather = mapHomeWeather(weatherPayload?.master ?? null, options)
  const kpi = mapHomeKpi(todayDaily, cards, schedules)
  const smartSpray = mapHomeSmartSpray(cards)
  const briefing = mapHomeBriefing({
    weather,
    cards,
    todayDaily,
    yesterdayDaily,
    schedules,
    aiPendingCount: Number(obsPayload?.ai_pending_count || 0),
  })
  const recent = mapHomeRecent({
    observations,
    todayDaily,
    yesterdayDaily,
    today,
  })

  return { kpi, smartSpray, weather, briefing, recent }
}
