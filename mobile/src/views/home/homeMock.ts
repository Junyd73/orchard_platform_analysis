/** 홈 1차 시안용 목업 (2차에서 API 교체) */
import {
  HOME_BRIEFING_KIND,
  type HomeBriefingKind,
} from '@/views/home/homeConstants'

export type HomeBriefingItem = {
  kind: HomeBriefingKind
  title: string
  detail?: string
}

export type HomeWeatherMock = {
  location: string
  tempC: number
  tempMinC: number
  tempMaxC: number
  skyLabel: string
  humidityPct: number
  windMs: number
  precipPct: number
}

export type HomeSmartSprayMock = {
  riskLabel: string
  pestName: string
  hint: string
}

export type HomeRecentItem = {
  id: string
  title: string
  detail: string
  timeLabel: string
  badge?: string
}

export type HomeKpiMock = {
  todayWork: number
  laborCount: number
  pestCaution: number
  sprayPlan: number
}

/** 1차: 한 줄 요약 (상세는 「자세히」·2차 연결) */
export const HOME_MOCK_BRIEFING: HomeBriefingItem[] = [
  {
    kind: HOME_BRIEFING_KIND.WEATHER,
    title: '15시 이후 비 70% · 오전 작업 권장',
  },
  {
    kind: HOME_BRIEFING_KIND.PEST,
    title: '배나무이 위험 높음',
  },
  {
    kind: HOME_BRIEFING_KIND.IN_PROGRESS,
    title: '어제 관수작업 1건 진행중',
  },
  {
    kind: HOME_BRIEFING_KIND.TODAY_SCHEDULE,
    title: '오늘 3건 · 다음 09:00 봉지씌우기',
  },
  {
    kind: HOME_BRIEFING_KIND.OBSERVATION,
    title: '관찰 AI 대기 1건',
  },
]

export const HOME_MOCK_WEATHER: HomeWeatherMock = {
  location: '화성시 정남면',
  tempC: 29,
  tempMinC: 25,
  tempMaxC: 32,
  skyLabel: '맑음',
  humidityPct: 95,
  windMs: 3.5,
  precipPct: 0,
}

export const HOME_MOCK_SMART_SPRAY: HomeSmartSprayMock = {
  riskLabel: '위험 높음',
  pestName: '배나무이',
  hint: '스마트방제에서 확인',
}

export const HOME_MOCK_KPI: HomeKpiMock = {
  todayWork: 3,
  laborCount: 4,
  pestCaution: 2,
  sprayPlan: 1,
}
