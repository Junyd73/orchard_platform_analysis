/** 홈(SCR-000) 상수 · 계절 Hero · 브리핑 유형 */
import homeIllustSpring from '@/assets/images/home/home_illust_spring.jpg'
import homeIllustSummer from '@/assets/images/home/home_illust_summer.jpg'
import homeIllustAutumn from '@/assets/images/home/home_illust_autumn.jpg'
import homeIllustWinter from '@/assets/images/home/home_illust_winter.jpg'
import {
  heroGreetingForHour,
  heroSeasonForMonth,
  STATUS_PREPARING_CD,
  type HeroSeason,
} from '@/views/work-log/workLogConstants'

export { heroGreetingForHour, heroSeasonForMonth }
export type { HeroSeason }

/** ODS 원본: docs/ODS/assets/home_illust_*.png (봄 파일명 srping 오타) */
export const HOME_HERO_IMAGE_BY_SEASON: Record<HeroSeason, string> = {
  spring: homeIllustSpring,
  summer: homeIllustSummer,
  autumn: homeIllustAutumn,
  winter: homeIllustWinter,
}

export function homeHeroImageForMonth(month: number): string {
  return HOME_HERO_IMAGE_BY_SEASON[heroSeasonForMonth(month)]
}

/** 화면 확인용: true면 5초마다 4계절 순환 (확인 후 false로) */
export const HOME_HERO_SEASON_PREVIEW = false
export const HOME_HERO_SEASON_PREVIEW_MS = 5000
/** 계절 전환 크로스페이드(ms) */
export const HOME_HERO_SEASON_FADE_MS = 1200
export const HOME_HERO_SEASON_ORDER: HeroSeason[] = [
  'spring',
  'summer',
  'autumn',
  'winter',
]
export const HOME_HERO_SEASON_LABEL: Record<HeroSeason, string> = {
  spring: '봄',
  summer: '여름',
  autumn: '가을',
  winter: '겨울',
}

/** 브리핑 줄 유형 (우선순위 1→5, 데이터 없으면 숨김) */
export const HOME_BRIEFING_KIND = {
  WEATHER: 'weather',
  PEST: 'pest',
  IN_PROGRESS: 'in_progress',
  TODAY_SCHEDULE: 'today_schedule',
  OBSERVATION: 'observation',
} as const

export type HomeBriefingKind =
  (typeof HOME_BRIEFING_KIND)[keyof typeof HOME_BRIEFING_KIND]

export const HOME_BRIEFING_KIND_ORDER: HomeBriefingKind[] = [
  HOME_BRIEFING_KIND.WEATHER,
  HOME_BRIEFING_KIND.PEST,
  HOME_BRIEFING_KIND.IN_PROGRESS,
  HOME_BRIEFING_KIND.TODAY_SCHEDULE,
  HOME_BRIEFING_KIND.OBSERVATION,
]

export const HOME_BRIEFING_KIND_LABEL: Record<HomeBriefingKind, string> = {
  weather: '기상',
  pest: '병해충 주의',
  in_progress: '진행중 일정',
  today_schedule: '오늘 일정',
  observation: '관찰 대기',
}

export const LABEL_HOME_BRIEFING = '오늘 간략 브리핑'
export const LABEL_HOME_WEATHER = '현재 날씨'
export const LABEL_HOME_SMART_SPRAY = '스마트 방제'
export const LABEL_HOME_QUICK = '빠른 실행'
export const LABEL_HOME_RECENT = '최근 활동'
/** 카드 타이틀 우측 공통 CTA (날씨·스마트방제 등) */
export const BTN_HOME_DETAIL = '상세보기'
export const MSG_HOME_ORDER_SOON = '준비 중입니다.'
export const MSG_HOME_BRIEFING_EMPTY =
  '오늘은 특이 이슈가 없습니다. 일정·날씨만 확인해 주세요.'
export const MSG_HOME_RECENT_EMPTY = '최근 활동이 없습니다.'

/** 홈 최근 활동 — 표시 최대 건수 */
export const HOME_RECENT_LIMIT = 5
/** 홈 최근 활동 — 관찰 조회 일수 */
export const HOME_RECENT_OBS_DAYS = 7
export const HOME_RECENT_TITLE_OBS = '관찰 등록'
export const HOME_RECENT_TITLE_WORK = '영농일지 등록'
export const HOME_RECENT_BADGE_AI_PENDING = 'AI 분석 대기'
export const HOME_RECENT_TIME_TODAY = '오늘'
export const HOME_RECENT_TIME_YESTERDAY = '어제'

export const LABEL_KPI_TODAY_WORK = '오늘 작업'
export const LABEL_KPI_LABOR = '투입 예정 인력'
export const LABEL_KPI_PEST = '주의 병해충'
export const LABEL_KPI_SPRAY = '예정 방제'

/** 영농일지 WO01 — 취소(KPI 제외) */
export const HOME_WORK_STATUS_CANCELLED_CD = 'WO010400'
/** 영농일지 WO01 — 진행중(브리핑) */
export const HOME_WORK_STATUS_IN_PROGRESS_CD = 'WO010200'

/** 스마트방제 risk_level — KPI「주의 병해충」 */
export const HOME_SPRAY_RISK_CAUTION = '주의'
export const HOME_SPRAY_RISK_DANGER = '위험'

/** 예정 방제 일정 제목 키워드 (work_mid_cd 외 보조) */
export const HOME_SPRAY_TITLE_KEYWORD = '방제'

/** 브리핑 기상 — 강수확률 주의 기준(%) */
export const HOME_BRIEFING_PRECIP_CAUTION_PCT = 50

/** 스마트방제 카드 빈 상태 */
export const HOME_SMART_SPRAY_EMPTY_PEST = '해당 없음'
export const HOME_SMART_SPRAY_EMPTY_RISK = '낮음'
export const HOME_SMART_SPRAY_EMPTY_HINT = '특이 주의 병해충 없음'
export const HOME_SMART_SPRAY_HINT_FALLBACK = '스마트방제에서 확인'

export const HOME_WEATHER_SKY_FALLBACK = '-'
export const HOME_BRIEFING_WORK_FALLBACK = '작업'

export const HOME_QUICK_ACTIONS = [
  {
    key: 'observation',
    label: '새 관찰 등록',
    sub: 'AI 분석',
    ready: true,
    to: '/observation/new',
  },
  {
    key: 'work_log',
    label: '영농일지 등록',
    sub: '작업 · 인력',
    ready: true,
    /** HomeQuickActions에서 당일 daily로 동적 이동 */
    to: '',
  },
  {
    key: 'pesticide',
    label: '농약 사용 등록',
    sub: '방제 기록',
    ready: true,
    /** 간략등록 모달 */
    to: '',
  },
  {
    key: 'order',
    label: '주문 등록',
    sub: '고객 · 품목',
    ready: false,
    to: '',
  },
] as const

export type HomeQuickActionKey = (typeof HOME_QUICK_ACTIONS)[number]['key']

/** 농약 간략등록 모달 */
export const LABEL_PEST_QUICK_TITLE = '농약 사용 등록'
export const LABEL_PEST_QUICK_DATE = '날짜'
export const LABEL_PEST_QUICK_WORK_GROUP = '작업그룹'
export const LABEL_PEST_QUICK_WORK_GROUP_FIXED = '방제/약제살포'
export const LABEL_PEST_QUICK_SITE = '작업장소'
export const LABEL_PEST_QUICK_TIME = '시간'
export const LABEL_PEST_QUICK_WORKER = '작업자'
export const LABEL_PEST_QUICK_MEMO = '메모'
export const LABEL_PEST_QUICK_STATUS = '상태'
export const LABEL_PEST_QUICK_GOOGLE = '구글 캘린더 반영'
export const BTN_PEST_QUICK_CANCEL = '취소'
export const BTN_PEST_QUICK_SAVE = '저장'
export const MSG_PEST_QUICK_SAVE_OK = '농약 사용이 등록되었습니다.'
export const MSG_PEST_QUICK_SAVE_FAIL = '농약 사용 등록에 실패했습니다.'
export const MSG_PEST_QUICK_SITE_OPTIONAL = '선택'
/** 상태 기본값 = 완료 (WO01, 일정/일간 등록과 동일 코드체계) */
export const PEST_QUICK_STATUS_DEFAULT_CD = 'WO010300'
export const PEST_QUICK_STATUS_PREPARING_CD = STATUS_PREPARING_CD
export const HOME_DAILY_NEW_QUERY = '1'