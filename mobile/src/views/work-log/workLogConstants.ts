/** 영농일지 공통코드 부모 (PC WO01 / WK01 / WT01). */
export const WORK_STATUS_PARENT_CD = 'WO01'
export const WORK_TYPE_PARENT_CD = 'WK01'
export const WEATHER_PARENT_CD = 'WT01'

export const MSG_FUTURE_WORK_LOG = '영농일지는 오늘까지만 작성할 수 있습니다.'

export const WEATHER_ICON_BY_CD: Record<string, string> = {
  WT010100: '☀',
  WT010200: '⛅',
  WT010300: '☁',
  WT010400: '☂',
  WT010500: '🌧',
  WT010600: '❄',
  WT010700: '⛈',
  WT019900: '•',
}

export function weatherIconForCd(weatherCd?: string | null, weatherNm?: string | null): string {
  const cd = String(weatherCd || '').trim()
  if (cd && WEATHER_ICON_BY_CD[cd]) return WEATHER_ICON_BY_CD[cd]
  const nm = String(weatherNm || '')
  if (nm.includes('비') && nm.includes('눈')) return '🌧'
  if (nm.includes('비')) return '☂'
  if (nm.includes('눈')) return '❄'
  if (nm.includes('구름') || nm.includes('흐림')) return '☁'
  if (nm.includes('맑')) return '☀'
  return ''
}

export function formatWon(amount?: number | null): string {
  const n = Math.round(Number(amount || 0))
  if (!Number.isFinite(n) || n <= 0) return '0'
  return n.toLocaleString('ko-KR')
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

export function isFutureDate(iso: string, today = todayIso()): boolean {
  return iso > today
}

export function daysInMonth(year: number, month: number): number {
  return new Date(year, month, 0).getDate()
}

/** 0=일 … 6=토 — JS getDay */
export function firstWeekdaySun0(year: number, month: number): number {
  return new Date(year, month - 1, 1).getDay()
}

export const WEEKDAY_LABELS = ['일', '월', '화', '수', '목', '금', '토'] as const
