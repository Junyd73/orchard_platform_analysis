/**
 * SCR-001 생육관찰 Hero 카탈로그 (STEP 1+)
 * — 선택 로직은 enabled+날짜 해시만 사용. 메타는 STEP2+ 확장용.
 */
import heroDefaultWebp from '@/assets/images/observation/observation-default-01.webp'

export type ObservationHeroCategory = 'default' | 'ai' | 'seasonal'
export type ObservationHeroSeason =
  | 'spring'
  | 'summer'
  | 'autumn'
  | 'winter'
  | 'any'
export type ObservationHeroAiFocus =
  | 'leaf'
  | 'fruit'
  | 'pest'
  | 'shoot'
  | 'bloom'
  | 'bag'
  | 'harvest'
  | 'none'
export type ObservationHeroWeather =
  | 'clear'
  | 'cloudy'
  | 'rain'
  | 'fog'
  | 'any'

export type ObservationHeroItem = {
  id: string
  /** Vite 해석 URL (import 결과) */
  image: string
  /** `\n`으로 줄바꿈 */
  title: string
  description: string
  alt: string
  enabled: boolean
  /** STEP2+ 확장 메타 (선택 로직 미사용) */
  category?: ObservationHeroCategory
  season?: ObservationHeroSeason
  aiFocus?: ObservationHeroAiFocus
  priority?: number
  weather?: ObservationHeroWeather
}

const HERO_META_DEFAULT = {
  category: 'default' as const,
  season: 'any' as const,
  aiFocus: 'none' as const,
  priority: 100,
  weather: 'any' as const,
}

/** 카탈로그·선택 실패 시 안전 기본값 */
export const OBSERVATION_HERO_FALLBACK: ObservationHeroItem = {
  id: 'observation-fallback',
  image: heroDefaultWebp,
  title: '오늘도 과수원을\n꼼꼼히 살펴보세요',
  description:
    'AI가 잎과 과실의 생육 상태를 분석하여 건강한 과수원 관리를 도와드립니다.',
  alt: '과수원에서 햇살 아래 사과 생육을 살펴보는 모습',
  enabled: true,
  ...HERO_META_DEFAULT,
}

/**
 * STEP 1: 승인 Hero 1종만 등록.
 * STEP 2: 이 배열에 항목을 추가하면 일별 선택이 자동 적용된다.
 */
export const OBSERVATION_HERO_ITEMS: ObservationHeroItem[] = [
  {
    id: 'observation-default-01',
    image: heroDefaultWebp,
    title: '오늘도 과수원을\n꼼꼼히 살펴보세요',
    description:
      'AI가 잎과 과실의 생육 상태를 분석하여 건강한 과수원 관리를 도와드립니다.',
    alt: '과수원에서 햇살 아래 사과 생육을 살펴보는 모습',
    enabled: true,
    ...HERO_META_DEFAULT,
  },
]
