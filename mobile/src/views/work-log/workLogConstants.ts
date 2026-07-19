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
import iconTabExpense from '@/assets/ods/work-log/icon-tab-expense.svg'
import iconTabPesticide from '@/assets/ods/work-log/icon-tab-pesticide.svg'
import iconTabFertilizer from '@/assets/ods/work-log/icon-tab-fertilizer.svg'
import iconTabPhoto from '@/assets/ods/work-log/icon-tab-photo.svg'
import heroSpring from '@/assets/images/work-log/hero-spring.png'
import heroSummer from '@/assets/images/work-log/hero-summer.png'
import heroAutumn from '@/assets/images/work-log/hero-autumn.png'
import heroWinter from '@/assets/images/work-log/hero-winter.png'

export const WORK_STATUS_PARENT_CD = 'WO01'
export const WORK_TYPE_PARENT_CD = 'WK01'
export const WEATHER_PARENT_CD = 'WT01'

/** m_common_code WK01 — 방제/약제살포 (= 농약 필터) */
export const WORK_MID_CD_PESTICIDE = 'WK010200'
/** m_common_code WK01 — 비료/영양제작업 (= 비료 필터) */
export const WORK_MID_CD_FERTILIZER = 'WK010800'

export const MSG_FUTURE_WORK_LOG = '영농일지는 오늘까지만 작성할 수 있습니다.'
export const MSG_DETAIL_PENDING = '준비 중입니다.'
export const MSG_COPY_HINT =
  '인력·경비·농약·비료·사진은 복사되지 않습니다. 작업 기본정보만 저장됩니다.'
export const MSG_COPY_OK = '작업이 복사되었습니다.'
export const MSG_COPY_DATE_INVALID = '작업일을 확인해 주세요.'
export const LABEL_COPY_WORK_DT = '작업일'
export const MSG_LOAD_MONTH_FAILED = '월간 영농일지를 불러오지 못했습니다.'
export const MSG_LOAD_DAILY_FAILED = '일간 영농일지를 불러오지 못했습니다.'
export const MSG_WEATHER_FETCH_FAILED = '날씨를 가져오지 못했습니다.'
export const MSG_SAVE_OK = '저장되었습니다.'
export const MSG_DRAFT_OK = '임시 저장되었습니다.'
export const MSG_WORK_CONTENT_REQUIRED = '작업내용을 선택해 주세요.'
export const MSG_SAVE_FAILED = '저장에 실패했습니다.'
/** 일간 화면 이탈 시 미저장 등록 데이터 확인 */
export const MSG_UNSAVED_LEAVE_CONFIRM =
  '등록된 데이터가 있습니다. 저장하시겠습니까?'
export const BTN_UNSAVED_LEAVE_SAVE = '저장'
export const BTN_UNSAVED_LEAVE_DISCARD = '저장 안 함'
export const BTN_UNSAVED_LEAVE_STAY = '취소'

/** master/캐시에 표시 가능한 기상 값이 있는지 */
export function hasWorkLogWeather(
  master: {
    weather_cd?: string | null
    weather_nm?: string | null
    temp_min?: number | null
    temp_max?: number | null
  } | null | undefined,
): boolean {
  if (!master) return false
  if (master.temp_min != null || master.temp_max != null) return true
  if (String(master.weather_cd || '').trim()) return true
  const nm = String(master.weather_nm || '').trim()
  return Boolean(nm && nm !== '-')
}

/** Hero 시간대별 인사 (시안4 · 2줄) */
export const HERO_GREETING_MORNING = '오늘 하루도\n힘내세요!!!'
export const HERO_GREETING_AFTERNOON = '오늘 남은 시간도\n아자 아자 화이팅!!!'
export const HERO_GREETING_EVENING = '오늘 하루도\n수고 하셨습니다!!!'
export const HERO_GREETING_HOUR_NOON = 12
export const HERO_GREETING_HOUR_EVENING = 18

/** 현재 시각(시) 기준 Hero 인사말 */
export function heroGreetingForHour(hour: number): string {
  if (hour < HERO_GREETING_HOUR_NOON) return HERO_GREETING_MORNING
  if (hour < HERO_GREETING_HOUR_EVENING) return HERO_GREETING_AFTERNOON
  return HERO_GREETING_EVENING
}

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

/** PC WeatherManager._dashboard_weather_text 와 동일 — 코드→표시명 */
export const WEATHER_NM_BY_CD: Record<string, string> = {
  WT010100: '맑음',
  WT010200: '구름많음',
  WT010300: '흐림',
  WT010400: '비',
  WT010500: '비/눈',
  WT010600: '눈',
  WT010700: '소나기',
  WT019900: '정보 없음',
}

export function weatherNmForCd(weatherCd?: string | null): string {
  const cd = String(weatherCd || '').trim()
  return (cd && WEATHER_NM_BY_CD[cd]) || ''
}

export function displayWeatherNm(
  weatherCd?: string | null,
  weatherNm?: string | null,
): string {
  const nm = String(weatherNm || '').trim()
  const cd = String(weatherCd || '').trim()
  if (nm && nm !== '-' && nm !== cd && !/^WT\d+/i.test(nm)) return nm
  return weatherNmForCd(cd) || (nm && nm !== '-' ? nm : '')
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

/** 투입시간 표시 (예: 7h, 7.5h) */
export function formatLaborHours(hours?: number | null): string {
  const n = Number(hours || 0)
  if (!Number.isFinite(n) || n <= 0) return '0h'
  const rounded = Math.round(n * 10) / 10
  return `${rounded}h`
}

/** 투입 인력 요약: 3명 · 21h */
export function formatLaborSummary(
  people?: number | null,
  hours?: number | null,
): string {
  const p = Math.max(0, Math.floor(Number(people || 0)))
  return `${p}명 · ${formatLaborHours(hours)}`
}

/** Hero KPI용 — 축약 없이 전체 숫자 + 원 */
export function formatHeroWonWithUnit(amount?: number | null): string {
  return formatWonWithUnit(amount)
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

/** 시안4: 일요일 시작 (0=일 … 6=토) */
export function firstWeekdaySun0(year: number, month: number): number {
  return new Date(year, month - 1, 1).getDay()
}

/** @deprecated 월요일 시작 — 필요 시 호환용 */
export function firstWeekdayMon0(year: number, month: number): number {
  return (new Date(year, month - 1, 1).getDay() + 6) % 7
}

export const WEEKDAY_LABELS_MON = ['월', '화', '수', '목', '금', '토', '일'] as const

/** 일~토 (SCR-010 캘린더 · Hero 요일) */
export const WEEKDAY_LABELS = ['일', '월', '화', '수', '목', '금', '토'] as const

/** 양력 고정 공휴·기념일 (MM-DD). 제헌절(07-17) 2026부터 공휴 복원 */
const FIXED_HOLIDAY_MD = new Set([
  '01-01', // 신정
  '03-01', // 삼일절
  '05-01', // 근로자의 날
  '05-05', // 어린이날
  '06-06', // 현충일
  '07-17', // 제헌절
  '08-15', // 광복절
  '10-03', // 개천절
  '10-09', // 한글날
  '12-25', // 성탄절
])

/**
 * 연도별 이동·대체 공휴 (ISO).
 * 설·추석·부처님오신날·대체공휴일 등 — 연도 추가 시 목록만 보강.
 */
const EXTRA_HOLIDAYS_BY_YEAR: Record<number, readonly string[]> = {
  2026: [
    '2026-02-16',
    '2026-02-17',
    '2026-02-18', // 설 연휴
    '2026-03-02', // 삼일절 대체
    '2026-05-24',
    '2026-05-25', // 부처님오신날 · 대체
    '2026-06-03', // 지방선거
    '2026-08-17', // 광복절 대체
    '2026-09-24',
    '2026-09-25',
    '2026-09-26', // 추석 연휴
    '2026-10-05', // 개천절 대체
  ],
}

export function isWeekend(iso: string): boolean {
  const day = new Date(`${iso}T12:00:00`).getDay()
  return day === 0 || day === 6
}

export function isPublicHoliday(iso: string): boolean {
  const md = iso.slice(5, 10)
  if (FIXED_HOLIDAY_MD.has(md)) return true
  const year = Number(iso.slice(0, 4))
  return (EXTRA_HOLIDAYS_BY_YEAR[year] || []).includes(iso)
}

/** 쉬는 날: 토·일 + 공휴일 → 캘린더 빨강 */
export function isRestDay(iso: string): boolean {
  return isWeekend(iso) || isPublicHoliday(iso)
}

export type CalendarLine = { kind: CalendarLineKind; text: string }

/** 방제/약제살포 작업 여부 (PC is_pesticide_work와 동일 기준) */
export function isPesticideWork(midCd: string, midNm: string): boolean {
  const cd = String(midCd || '').trim().toUpperCase()
  if (cd === WORK_MID_CD_PESTICIDE) return true
  const nm = String(midNm || '').trim()
  if (nm.includes('방제')) return true
  if (nm.includes('약제살포') || (nm.includes('약제') && nm.includes('살포'))) {
    return true
  }
  return false
}

function isFertilizerWork(midCd: string, midNm: string): boolean {
  const cd = String(midCd || '').trim().toUpperCase()
  if (cd === WORK_MID_CD_FERTILIZER) return true
  const nm = String(midNm || '')
  return nm.includes('비료') || nm.includes('영양제')
}

export function buildCalendarLines(
  cell: {
    work_names?: string[]
    work_items?: { work_mid_cd?: string; work_mid_nm?: string }[]
    has_work?: boolean
    resource_count?: number
    labor_hour_sum?: number
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

  const items =
    cell.work_items && cell.work_items.length > 0
      ? cell.work_items.map((it) => ({
          cd: String(it.work_mid_cd || '').trim(),
          nm: String(it.work_mid_nm || '').trim() || '-',
        }))
      : (cell.work_names || []).map((nm) => ({ cd: '', nm: String(nm || '').trim() || '-' }))

  for (const it of items) {
    if (isPesticideWork(it.cd, it.nm)) {
      if (filters[WORK_FILTER_PESTICIDE]) {
        all.push({ kind: WORK_FILTER_PESTICIDE, text: it.nm })
      }
      continue
    }
    if (isFertilizerWork(it.cd, it.nm)) {
      if (filters[WORK_FILTER_FERTILIZER]) {
        all.push({ kind: WORK_FILTER_FERTILIZER, text: it.nm })
      }
      continue
    }
    if (filters[WORK_FILTER_WORK] && cell.has_work) {
      all.push({ kind: WORK_FILTER_WORK, text: it.nm })
    }
  }

  if (filters[WORK_FILTER_LABOR]) {
    const people = Number(cell.resource_count || 0)
    const hours = Number(cell.labor_hour_sum || 0)
    if (people > 0 || hours > 0) {
      all.push({
        kind: WORK_FILTER_LABOR,
        text: formatLaborSummary(people, hours),
      })
    }
  }
  const cost = Number(cell.labor_sum || 0) + Number(cell.expense_sum || 0)
  if (filters[WORK_FILTER_EXPENSE] && cost > 0) {
    all.push({ kind: WORK_FILTER_EXPENSE, text: '경비' })
  }
  const weatherLabel = displayWeatherNm(cell.weather_cd, cell.weather_nm)
  const hasWeather = Boolean(cell.weather_cd) || Boolean(weatherLabel)
  if (filters[WORK_FILTER_WEATHER] && hasWeather) {
    all.push({
      kind: WORK_FILTER_WEATHER,
      text: weatherLabel || '기상',
    })
  }
  if (filters[WORK_FILTER_OTHER] && cell.has_issue) {
    all.push({ kind: WORK_FILTER_OTHER, text: '이슈' })
  }
  const max = 2
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

/* ─── SCR-011 일간 UI Shell ─── */

export const DAILY_TAB_WORK = 'work'
export const DAILY_TAB_LABOR = 'labor'
export const DAILY_TAB_EXPENSE = 'expense'
export const DAILY_TAB_PESTICIDE = 'pesticide'
export const DAILY_TAB_FERTILIZER = 'fertilizer'
export const DAILY_TAB_PHOTO = 'photo'

export type DailyWorkTabKey =
  | typeof DAILY_TAB_WORK
  | typeof DAILY_TAB_LABOR
  | typeof DAILY_TAB_EXPENSE
  | typeof DAILY_TAB_PESTICIDE
  | typeof DAILY_TAB_FERTILIZER
  | typeof DAILY_TAB_PHOTO

export const DAILY_WORK_TABS: ReadonlyArray<{
  key: DailyWorkTabKey
  label: string
  icon: string
}> = [
  { key: DAILY_TAB_WORK, label: '작업', icon: iconWork },
  { key: DAILY_TAB_LABOR, label: '인력', icon: iconLabor },
  { key: DAILY_TAB_EXPENSE, label: '경비', icon: iconTabExpense },
  { key: DAILY_TAB_PESTICIDE, label: '농약', icon: iconTabPesticide },
  { key: DAILY_TAB_FERTILIZER, label: '비료', icon: iconTabFertilizer },
  { key: DAILY_TAB_PHOTO, label: '사진', icon: iconTabPhoto },
]

/** 작업 결과 사진 — 관찰 사진과 별개 · 작업 1건당 최대 */
export const WORK_PHOTO_MAX_COUNT = 5

/** Shell: true면 더미 작업으로「작업 있음」조회 모드 시연 */
export const SHELL_PREVIEW_WITH_WORKS = false

export const MSG_TIMELINE_EMPTY =
  '등록된 작업이 없습니다.\n새로운 작업을 기록해 주세요.'
export const MSG_SUMMARY_EMPTY = '등록된 작업이 없어 요약할 내용이 없습니다.'
export const MSG_OBS_EMPTY = '이 날짜에 등록된 생육관찰이 없습니다.'
export const MSG_OBS_LOADING = '생육관찰을 불러오는 중…'
export const MSG_OBS_PHOTO_EMPTY = '등록된 사진이 없습니다.'
export const MSG_OBS_TITLE_EMPTY = '(제목 없음)'
export const MSG_OBS_LOCATION_FALLBACK = '필지'
/** 일간 생육관찰 사진 미리보기 칸 수 */
export const DAILY_OBS_PHOTO_PREVIEW_MAX = 4
export const MSG_WORK_FORM_TIP =
  '작업내용만 선택해도 타임라인에 추가할 수 있습니다.'
export const MSG_FERTILIZER_PENDING =
  '비료 사용·재고 연동은 준비 중입니다.'
export const MSG_PESTICIDE_HINT =
  '방제·약제살포 작업일 때 사용 농약을 등록합니다.'
export const MSG_LABOR_EMPTY = '등록된 인력이 없습니다.'
export const MSG_EXPENSE_EMPTY = '등록된 경비가 없습니다.'
export const MSG_PESTICIDE_EMPTY = '등록된 사용 농약이 없습니다.'
/** PC와 동일: 방제/약제살포가 아닐 때 */
export const MSG_PESTICIDE_NOT_TARGET =
  '농약등록은 방제/약제살포 작업에서 가능합니다.'
export const MSG_LABOR_REMOVE_CONFIRM = '등록된 인력을 삭제하시겠습니까?'
export const MSG_LABOR_REMOVE_PAID_CONFIRM =
  '지급된 인력입니다. 삭제 시 관련 전표가 역분개됩니다. 계속하시겠습니까?'
export const MSG_EXPENSE_REMOVE_CONFIRM = '등록된 경비를 삭제하시겠습니까?'
export const MSG_EXPENSE_REMOVE_PAID_CONFIRM =
  '지불된 경비입니다. 삭제 시 관련 전표가 역분개됩니다. 계속하시겠습니까?'
export const MSG_WORK_PHOTO_EMPTY = '작업 결과 사진이 없습니다.'
export const MSG_WORK_PHOTO_LIMIT = `최대 ${WORK_PHOTO_MAX_COUNT}장까지 등록할 수 있습니다.`

export const PLACEHOLDER_SELECT = '선택하세요'
export const PLACEHOLDER_WORK_RMK = '비고'

/** PC 지급/지불방식 계정 prefix·level */
export const PAY_METHOD_ACCT_PREFIX = 'AS0101'
export const PAY_METHOD_ACCT_LEVEL = 4
/** PC 지출내용 계정 */
export const EXPENSE_ACCT_PREFIX = 'EX'
export const EXPENSE_ACCT_LEVEL = 4

export type DailyWorkFormModel = {
  workId: string | null
  /** WK01 작업내용 */
  workMidCd: string
  workContent: string
  workLocId: string
  siteNm: string
  startTime: string
  endTime: string
  statusCd: string
  statusNm: string
  rmk: string
}

export function createEmptyWorkForm(): DailyWorkFormModel {
  return {
    workId: null,
    workMidCd: '',
    workContent: '',
    workLocId: '',
    siteNm: '',
    startTime: '08:00',
    endTime: '09:00',
    statusCd: '',
    statusNm: '',
    rmk: '',
  }
}

/** Shell — 인력 행 */
export type DailyShellLaborRow = {
  id: string
  resId?: number | null
  empCd: string
  empNm: string
  manHour: string
  dayPay: string
  payMethodCd: string
  payMethod: string
  paidYn: string
  status?: string
}

/** Shell — 경비 행 */
export type DailyShellExpenseRow = {
  id: string
  expId?: number | null
  occurDt: string
  acctCd: string
  expenseNm: string
  detail: string
  amount: string
  unitPrice: string
  qty: string
  payMethodCd: string
  payMethod: string
  paidYn: string
  status?: string
}

/** Shell — 사용 농약 행 */
export type DailyShellPesticideRow = {
  id: string
  itemId: number | null
  itemNm: string
  spec: string
  useQty: string
  purpose: string
  rmk: string
}

export function createEmptyLaborRow(id: string): DailyShellLaborRow {
  return {
    id,
    resId: null,
    empCd: '',
    empNm: '',
    manHour: '0',
    dayPay: '0',
    payMethodCd: '',
    payMethod: '',
    paidYn: 'N',
    status: 'INS',
  }
}

export function createEmptyExpenseRow(
  id: string,
  occurDt = '',
): DailyShellExpenseRow {
  return {
    id,
    expId: null,
    occurDt,
    acctCd: '',
    expenseNm: '',
    detail: '',
    amount: '0',
    unitPrice: '0',
    qty: '1',
    payMethodCd: '',
    payMethod: '',
    paidYn: 'N',
    status: 'INS',
  }
}

export function createEmptyPesticideRow(id: string): DailyShellPesticideRow {
  return {
    id,
    itemId: null,
    itemNm: '',
    spec: '',
    useQty: '0',
    purpose: '',
    rmk: '',
  }
}

export type DailyTimelineTone = 'mint' | 'forest' | 'gold' | 'violet'

export type DailyTimelineItem = {
  id: string
  /** WK01 작업 중분류 코드 */
  workMidCd?: string
  title: string
  time: string
  endTime: string
  durationLabel: string
  tone: DailyTimelineTone
  icon: string
  statusLabel: string
  location: string
  /** 작업 비고 (PC rmk) */
  rmk: string
}

/** Shell용 더미 타임라인 (시안: 적과→SS방제→제초→비료) */
export const DAILY_SHELL_TIMELINE: readonly DailyTimelineItem[] = [
  {
    id: 'shell-1',
    title: '적과',
    time: '07:30',
    endTime: '09:00',
    durationLabel: '1시간 30분',
    tone: 'mint',
    icon: iconWork,
    statusLabel: '진행완료',
    location: '1-1 과수원',
    rmk: '상단부 과밀 제거',
  },
  {
    id: 'shell-2',
    title: 'SS방제',
    time: '09:20',
    endTime: '11:10',
    durationLabel: '1시간 50분',
    tone: 'forest',
    icon: iconPesticide,
    statusLabel: '진행완료',
    location: '1-1 과수원 (청실필지)',
    rmk: '전착제(마쿠피카) 혼용 살포',
  },
  {
    id: 'shell-3',
    title: '제초',
    time: '14:00',
    endTime: '15:30',
    durationLabel: '1시간 30분',
    tone: 'gold',
    icon: iconOther,
    statusLabel: '진행완료',
    location: '2구역',
    rmk: '이랑 사이 제초',
  },
  {
    id: 'shell-4',
    title: '비료/영양제',
    time: '16:30',
    endTime: '17:20',
    durationLabel: '50분',
    tone: 'violet',
    icon: iconFertilizer,
    statusLabel: '진행완료',
    location: '1-1 과수원 (청실필지)',
    rmk: '수용성 비료 40kg',
  },
]

export type DailyShellSummaryLine = {
  label: string
  value: string
}

export type DailyShellSummaryCard = {
  key: string
  label: string
  icon: string
  tone: 'labor' | 'expense' | 'pesticide' | 'fertilizer'
  lines: readonly DailyShellSummaryLine[]
}

/** Shell 더미 요약은 제거 — buildDailySummaryCards 사용 */

const DAILY_SUMMARY_PEST_MAX_LINES = 3
const MSG_SUMMARY_NONE = '없음'
const MSG_SUMMARY_FERTILIZER_PENDING = '준비 중'

/** 일간 API resources/expenses/pesticides → 오늘 작업 요약 카드 */
export function buildDailySummaryCards(input: {
  resources?: readonly {
    emp_cd?: string | null
    man_hour?: number | null
    daily_wage?: number | null
  }[]
  expenses?: readonly { total_amt?: number | null }[]
  pesticides?: readonly {
    lines?: readonly {
      item_id?: number | null
      item_nm_snapshot?: string | null
      use_qty?: number | null
    }[]
  }[]
}): DailyShellSummaryCard[] {
  const resources = input.resources || []
  const expenses = input.expenses || []
  const pesticides = input.pesticides || []

  const empKeys = new Set(
    resources
      .map((r) => String(r.emp_cd || '').trim())
      .filter(Boolean),
  )
  const people = empKeys.size || resources.length
  const hours = resources.reduce((s, r) => s + Number(r.man_hour || 0), 0)
  const laborAmt = resources.reduce((s, r) => s + Number(r.daily_wage || 0), 0)

  const expenseCnt = expenses.length
  const expenseAmt = expenses.reduce((s, e) => s + Number(e.total_amt || 0), 0)

  const pestQty = new Map<string, number>()
  for (const doc of pesticides) {
    for (const ln of doc.lines || []) {
      const qty = Number(ln.use_qty || 0)
      if (!(qty > 0)) continue
      const nm =
        String(ln.item_nm_snapshot || '').trim() ||
        (ln.item_id ? `품목#${ln.item_id}` : '농약')
      pestQty.set(nm, (pestQty.get(nm) || 0) + qty)
    }
  }
  const pestEntries = [...pestQty.entries()].sort((a, b) => b[1] - a[1])
  const pestLines: DailyShellSummaryLine[] =
    pestEntries.length === 0
      ? [{ label: '사용', value: MSG_SUMMARY_NONE }]
      : pestEntries.slice(0, DAILY_SUMMARY_PEST_MAX_LINES).map(([nm, qty]) => ({
          label: nm,
          value: `${Math.round(qty)}`,
        }))
  if (pestEntries.length > DAILY_SUMMARY_PEST_MAX_LINES) {
    pestLines.push({
      label: '기타',
      value: `${pestEntries.length - DAILY_SUMMARY_PEST_MAX_LINES}종`,
    })
  }

  return [
    {
      key: 'labor',
      label: '인력',
      icon: iconLabor,
      tone: 'labor',
      lines: [
        { label: '인원', value: `${people}명` },
        { label: '투입시간', value: formatLaborHours(hours) },
        { label: '인건비', value: formatWonWithUnit(laborAmt) },
      ],
    },
    {
      key: 'expense',
      label: '경비',
      icon: iconExpense,
      tone: 'expense',
      lines: [
        { label: '건수', value: `${expenseCnt}건` },
        { label: '금액', value: formatWonWithUnit(expenseAmt) },
      ],
    },
    {
      key: 'pesticide',
      label: '농약',
      icon: iconPesticide,
      tone: 'pesticide',
      lines: pestLines,
    },
    {
      key: 'fertilizer',
      label: '비료',
      icon: iconFertilizer,
      tone: 'fertilizer',
      lines: [{ label: '등록', value: MSG_SUMMARY_FERTILIZER_PENDING }],
    },
  ]
}

/** 일간 생육관찰 목록 제목 */
export function formatDailyObsTitle(title: string | null | undefined): string {
  const t = String(title || '').trim()
  return t || MSG_OBS_TITLE_EMPTY
}

/** 일간 생육관찰 목록 메타 (대상유형 · 위치) */
export function formatDailyObsMeta(item: {
  target_type_nm?: string | null
  location_text?: string | null
  site_nm?: string | null
}): string {
  const typeNm = String(item.target_type_nm || '').trim() || '관찰'
  const loc =
    String(item.location_text || '').trim() ||
    String(item.site_nm || '').trim() ||
    MSG_OBS_LOCATION_FALLBACK
  return `${typeNm} · ${loc}`
}

/** YYYY-MM-DD → 2026.07.18 (토) */
export function formatDailyDateLabel(iso: string): string {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(iso)) return iso || '—'
  const d = new Date(`${iso}T12:00:00`)
  const wd = WEEKDAY_LABELS[d.getDay()] || ''
  const [y, m, day] = iso.split('-')
  return `${y}.${m}.${day} (${wd})`
}

export function formatDailyTimeRange(item: DailyTimelineItem): string {
  return `${item.time} ~ ${item.endTime} (${item.durationLabel})`
}

/** HH:MM / HHMM / HH:MM:SS → HH:MM */
export function formatWorkTimeHm(raw: string | null | undefined): string {
  const s = String(raw || '').trim()
  if (!s) return '—'
  const m = s.match(/^(\d{1,2}):(\d{2})/)
  if (m) return `${m[1].padStart(2, '0')}:${m[2]}`
  if (/^\d{4}$/.test(s)) return `${s.slice(0, 2)}:${s.slice(2)}`
  return s.slice(0, 5)
}

function durationLabelBetween(startHm: string, endHm: string): string {
  if (startHm === '—' || endHm === '—') return '—'
  const [sh, sm] = startHm.split(':').map(Number)
  const [eh, em] = endHm.split(':').map(Number)
  if ([sh, sm, eh, em].some((n) => Number.isNaN(n))) return '—'
  let mins = eh * 60 + em - (sh * 60 + sm)
  if (mins < 0) mins += 24 * 60
  const h = Math.floor(mins / 60)
  const m = mins % 60
  if (h <= 0) return `${m}분`
  if (m <= 0) return `${h}시간`
  return `${h}시간 ${m}분`
}

const TIMELINE_TONES: readonly DailyTimelineTone[] = [
  'mint',
  'forest',
  'gold',
  'violet',
]

/** API 작업행 → 타임라인 칩 */
export function mapWorkItemToTimeline(
  work: {
    work_id: string
    work_mid_cd?: string | null
    work_mid_nm?: string | null
    work_loc_nm?: string | null
    rmk?: string | null
    start_tm?: string | null
    end_tm?: string | null
    status_nm?: string | null
  },
  index = 0,
): DailyTimelineItem {
  const midCd = String(work.work_mid_cd || '')
  const midNm = String(work.work_mid_nm || '').trim() || '작업'
  const start = formatWorkTimeHm(work.start_tm)
  const end = formatWorkTimeHm(work.end_tm)
  let tone: DailyTimelineTone = TIMELINE_TONES[index % TIMELINE_TONES.length] || 'mint'
  let icon = iconWork
  if (isPesticideWork(midCd, midNm)) {
    tone = 'forest'
    icon = iconPesticide
  } else if (isFertilizerWork(midCd, midNm)) {
    tone = 'violet'
    icon = iconFertilizer
  }
  return {
    id: work.work_id,
    workMidCd: midCd,
    title: midNm,
    time: start,
    endTime: end,
    durationLabel: durationLabelBetween(start, end),
    tone,
    icon,
    statusLabel: String(work.status_nm || '').trim() || '—',
    location: String(work.work_loc_nm || '').trim() || '—',
    rmk: String(work.rmk || '').trim(),
  }
}

/** 타임라인·표시용: 시작시각 오름차순 (동일 시 work_id) */
export function sortWorksByStartTime<
  T extends { start_tm?: string | null; work_id?: string | null },
>(works: readonly T[]): T[] {
  return [...works].sort((a, b) => {
    const ta = formatWorkTimeHm(a.start_tm)
    const tb = formatWorkTimeHm(b.start_tm)
    if (ta !== tb) return ta.localeCompare(tb)
    return String(a.work_id || '').localeCompare(String(b.work_id || ''))
  })
}

