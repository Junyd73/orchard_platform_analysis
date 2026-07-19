/**
 * SCR-001 생육관찰 Hero 카탈로그 (STEP 1)
 * — 레이아웃/시즌·날씨 연동은 후속. 이미지·문구만 교체 가능하도록 분리.
 */
import heroDefaultWebp from '@/assets/images/observation/observation-default-01.webp'

export type ObservationHeroItem = {
  id: string
  /** Vite 해석 URL (import 결과) */
  image: string
  /** `\n`으로 줄바꿈 */
  title: string
  description: string
  alt: string
  enabled: boolean
}

/** 카탈로그·선택 실패 시 안전 기본값 */
export const OBSERVATION_HERO_FALLBACK: ObservationHeroItem = {
  id: 'observation-fallback',
  image: heroDefaultWebp,
  title: '오늘도 과수원을\n꼼꼼히 살펴보세요',
  description:
    'AI가 잎과 과실의 생육 상태를 분석하여 건강한 과수원 관리를 도와드립니다.',
  alt: '배 과수원의 잎과 과실을 AI로 관찰하는 모습',
  enabled: true,
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
    alt: '배 과수원의 잎과 과실을 AI로 관찰하는 모습',
    enabled: true,
  },
]
