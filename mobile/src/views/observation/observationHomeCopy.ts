/** SCR-001 홈 — AI 구간 빈 상태 안내 (숨기지 않음) */
export const MSG_AI_RISK_EMPTY = '오늘은 위험 관찰이 없습니다.'
export const MSG_RECENT_AI_EMPTY = '최근 AI 분석이 없습니다.'
export const MSG_AI_RISK_LOADING = '위험 관찰을 확인하는 중…'
export const MSG_RECENT_AI_LOADING = '최근 AI 분석을 확인하는 중…'
export const LABEL_AI_RISK = 'AI 위험 감지'
export const LABEL_AI_RISK_BADGE = '위험'
export const LABEL_RECENT_AI = '최근 AI 분석'
export const LABEL_RECENT_AI_ALL = '전체 보기'

/** AI 위험 감지 카드(시안 뼈대) */
export type AiRiskCardItem = {
  id: string
  pestName: string
  foundCount: number
  timeLabel: string
  thumbUrl?: string | null
}

/** 시안 샘플 — AI 위험 감지 레이아웃용 */
export const AI_RISK_SKELETON_ITEM: AiRiskCardItem = {
  id: 'skel-risk-1',
  pestName: '미국선녀벌레',
  foundCount: 4,
  timeLabel: '오늘 오전 11:23',
}


/** 최근 AI 분석 카드(시안 뼈대) — API 연동 전 타입 */
export type RecentAiCardItem = {
  id: string
  title: string
  confidencePct: number
  targetLabel: string
  timeLabel: string
  thumbUrl?: string | null
}

/** 시안 샘플 — 레이아웃 확인용 뼈대 데이터 */
export const RECENT_AI_SKELETON_ITEMS: RecentAiCardItem[] = [
  {
    id: 'skel-1',
    title: '갈색무늬병',
    confidencePct: 96,
    targetLabel: '과실 · 잎',
    timeLabel: '7분 전',
  },
  {
    id: 'skel-2',
    title: '배나무이',
    confidencePct: 88,
    targetLabel: '잎 · 신초',
    timeLabel: '오늘 오전 9:41',
  },
  {
    id: 'skel-3',
    title: '적성병',
    confidencePct: 82,
    targetLabel: '잎',
    timeLabel: '어제 오후 3:22',
  },
]
