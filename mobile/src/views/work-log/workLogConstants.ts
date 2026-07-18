/** 영농일지 공통코드·필터·계절 Hero (PC WO01 / WK01 / WT01). */
import wxSunny from '@/assets/ods/work-log/wx-sunny.svg'
import wxCloud from '@/assets/ods/work-log/wx-cloud.svg'
import wxRain from '@/assets/ods/work-log/wx-rain.svg'
import wxSnow from '@/assets/ods/work-log/wx-snow.svg'
import iconWork from '@/assets/ods/work-log/icon-work.svg'
import iconLabor from '@/assets/ods/work-log/icon-labor.svg'
import iconExpense from '@/assets/ods/work-log/icon-expense.svg'
import iconPesticide from '@/assets/ods/work-log/icon-pesticide.svg'
import iconFertilizer from '@/assets/ods/work-log/icon-fertilizer.svg'
import iconOther from '@/assets/ods/work-log/icon-other.svg'
import heroSpring from '@/assets/images/work-log/hero-spring.webp'
import heroSummer from '@/assets/images/work-log/hero-summer.webp'
import heroAutumn from '@/assets/images/work-log/hero-autumn.webp'
import heroWinter from '@/assets/images/work-log/hero-winter.webp'

export const WORK_STATUS_PARENT_CD = 'WO01'
export const WORK_TYPE_PARENT_CD = 'WK01'
export const WEATHER_PARENT_CD = 'WT01'

export const MSG_FUTURE_WORK_LOG = '영농일지는 오늘까지만 작성할 수 있습니다.'
export const MSG_HOURLY_FORECAST_PENDING = '시간별 예보 화면은 준비 중입니다.'
export const MSG_DETAIL_PENDING = '준비 중입니다.'
export const MSG_LOAD_MONTH_FAILED = '월간 영농일지를 불러오지 못했습니다.'

/** 작업필터 키 (클라이언트 전용) */
export const WORK_FILTER_WORK = 'work'
export const WORK_FILTER_LABOR = 'labor'
export const WORK_FILTER_EXPENSE = 'expense'
export const WORK_FILTER_PESTICIDE = 'pesticide'
export const WORK_FILTER_FERTILIZER = 'fertilizer'
export const WORK_FILTER_WEATHER = 'weather'
export const WORK_FILTER_OTHER = 'other'

export type WorkFilterKey =
  | typeof WORK_FILTER_WORK
  | typeof WORK_FILTER_LABOR
  | typeof WORK_FILTER_EXPENSE
  | typeof WORK_FILTER_PESTICIDE
  | typeof WORK_FILTER_FERTILIZER
  | typeof WORK_FILTER_WEATHER
  | typeof WORK_FILTER_OTHER

export type CalendarLineKind = WorkFilterKey

export const WORK_FILTER_OPTIONS: ReadonlyArray<{ key: WorkFilterKey; label: string }> = [
  { key: WORK_FILTER_WORK, label: '작업' },
  { key: WORK_FILTER_LABOR, label: '인력' },
  { key: WORK_FILTER_EXPENSE, label: '경비' },
  { key: WORK_FILTER_PESTICIDE, label: '농약' },
  { key: WORK_FILTER_FERTILIZER, label: '비료' },
  { key: WORK_FILTER_WEATHER, label: '기상' },
  { key: WORK_FILTER_OTHER, label: '기타' },
]

export const CALENDAR_KIND_ICON: Record<CalendarLineKind, string> = {
  work: iconWork,
  labor: iconLabor,
  expense: iconExpense,
  pesticide: iconPesticide,
  fertilizer: iconFertilizer,
  weather: wxCloud,
  other: iconOther,
}

/** 시안3 분류 색상 */
export const CALENDAR_KIND_COLOR: Record<CalendarLineKind, string> = {
  work: '#2E7D32',
  labor: '#1E88E5',
  expense: '#FB8C00',
  pesticide: '#C62828',
  fertilizer: '#7B1FA2',
  weather: '#1E88E5',
  other: '#9E9E9E',
}

export function defaultWorkFilters(): Record<WorkFilterKey, boolean> {
  return {
    [WORK_FILTER_WORK]: true,
    [WORK_FILTER_LABOR]: true,
    [WORK_FILTER_EXPENSE]: true,
    [WORK_FILTER_PESTICIDE]: true,
    [WORK_FILTER_FERTILIZER]: true,
    [WORK_FILTER_WEATHER]: true,
    [WORK_FILTER_OTHER]: true,
  }
}

export type HeroSeason = 'spring' | 'summer' | 'autumn' | 'winter'

export function heroSeasonForMonth(month: number): HeroSeason {
  if (month >= 3 && month <= 5) return 'spring'
  if (month >= 6 && month <= 8) return 'summer'
  if (month >= 9 && month <= 11) return 'autumn'
  return 'winter'
}

export const HERO_IMAGE_BY_SEASON: Record<HeroSeason, string> = {
  spring: heroSpring,
  summer: heroSummer,
  autumn: heroAutumn,
  winter: heroWinter,
}

export function heroImageForMonth(month: number): string {
  return HERO_IMAGE_BY_SEASON[heroSeasonForMonth(month)]
}

export const WEATHER_ICON_SRC_BY_CD: Record<string, string> = {
  WT010100: wxSunny,
  WT010200: wxCloud,
  WT010300: wxCloud,
  WT010400: wxRain,
  WT010500: wxRain,
  WT010600: wxSnow,
  WT010700: wxRain,
  WT019900: wxCloud,
}

export function weatherIconSrc(
  weatherCd?: string | null,
  weatherNm?: string | null,
): string {
  const cd = String(weatherCd || '').trim()
  if (cd && WEATHER_ICON_SRC_BY_CD[cd]) return WEATHER_ICON_SRC_BY_CD[cd]
  const nm = String(weatherNm || '')
  if (nm.includes('눈')) return wxSnow
  if (nm.includes('비')) return wxRain
  if (nm.includes('맑')) return wxSunny
  return wxCloud
}

export function formatWon(amount?: number | null): string {
  const n = Math.round(Number(amount || 0))
  if (!Number.isFinite(n) || n <= 0) return '0'
  return n.toLocaleString('ko-KR')
}

export function formatWonWithUnit(amount?: number | null): string {
  return `${formatWon(amount)}원`
}

export function todayIso(): string {
  const d = new Date()
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

export function pad2(n: number): string {
  return String(n).padStart(2, '0')
}

export function monthLabel(year: number, month: number): string {
  return `${year}년 ${month}월`
}

export function monthRangeLabel(year: number, month: number): string {
  const last = daysInMonth(year, month)
  return `(${month}.${1} ~ ${month}.${last})`
}

export function isFutureDate(iso: string, today = todayIso()): boolean {
  return iso > today
}

export function daysInMonth(year: number, month: number): number {
  return new Date(year, month, 0).getDate()
}

/** 시안3: 월요일 시작 (0=월 … 6=일) */
export function firstWeekdayMon0(year: number, month: number): number {
  return (new Date(year, month - 1, 1).getDay() + 6) % 7
}

export const WEEKDAY_LABELS_MON = ['월', '화', '수', '목', '금', '토', '일'] as const

/** @deprecated 일요일 시작 — 일간 등 레거시 */
export const WEEKDAY_LABELS = ['일', '월', '화', '수', '목', '금', '토'] as const

export type CalendarLine = { kind: CalendarLineKind; text: string }

export function buildCalendarLines(
  cell: {
    work_names?: string[]
    has_work?: boolean
    resource_count?: number
    labor_sum?: number
    expense_sum?: number
    weather_nm?: string
    weather_cd?: string
    has_issue?: boolean
    work_rmk?: string
  } | null,
  filters: Record<WorkFilterKey, boolean>,
): { lines: CalendarLine[]; extra: number } {
  if (!cell) return { lines: [], extra: 0 }
  const all: CalendarLine[] = []
  if (filters[WORK_FILTER_WORK] && cell.has_work) {
    for (const nm of cell.work_names || []) {
      all.push({ kind: WORK_FILTER_WORK, text: nm })
    }
  }
  if (filters[WORK_FILTER_LABOR] && Number(cell.resource_count || 0) > 0) {
    all.push({ kind: WORK_FILTER_LABOR, text: `인력 ${cell.resource_count}` })
  }
  const cost = Number(cell.labor_sum || 0) + Number(cell.expense_sum || 0)
  if (filters[WORK_FILTER_EXPENSE] && cost > 0) {
    all.push({ kind: WORK_FILTER_EXPENSE, text: '경비' })
  }
  const weatherLabel = String(cell.weather_nm || '').trim()
  const hasWeather =
    Boolean(cell.weather_cd) || (Boolean(weatherLabel) && weatherLabel !== '-')
  if (filters[WORK_FILTER_WEATHER] && hasWeather) {
    all.push({
      kind: WORK_FILTER_WEATHER,
      text: weatherLabel && weatherLabel !== '-' ? weatherLabel : '기상',
    })
  }
  if (filters[WORK_FILTER_OTHER] && cell.has_issue) {
    all.push({ kind: WORK_FILTER_OTHER, text: '이슈' })
  }
  const max = 3
  if (all.length <= max) return { lines: all, extra: 0 }
  return { lines: all.slice(0, max), extra: all.length - max }
}

export function shiftMonth(
  year: number,
  month: number,
  delta: number,
): { year: number; month: number } {
  const d = new Date(year, month - 1 + delta, 1)
  return { year: d.getFullYear(), month: d.getMonth() + 1 }
}
