/** SCR-001 홈 — AI 구간 빈 상태 안내 (숨기지 않음) */
export const MSG_AI_RISK_EMPTY = '최근 7일 위험 관찰이 없습니다.'
export const MSG_RECENT_AI_EMPTY = '최근 7일 AI 분석이 없습니다.'
export const MSG_AI_RISK_LOADING = '위험 관찰을 확인하는 중…'
export const MSG_RECENT_AI_LOADING = '최근 7일 AI 분석을 확인하는 중…'
export const LABEL_AI_RISK = 'AI 위험 감지'
export const LABEL_AI_RISK_BADGE = '위험'
export const LABEL_RECENT_AI = '최근 AI 분석(최근7일)'
export const LABEL_RECENT_AI_ALL = '전체 보기'

/** AI 위험 감지 카드 */
export type AiRiskCardItem = {
  id: string
  pestName: string
  /** 주의·위험 등 severity_nm */
  severityLabel: string
  timeLabel: string
  thumbUrl?: string | null
}

/** @deprecated 시안 샘플 — 레이아웃 확인용 */
export const AI_RISK_SKELETON_ITEM: AiRiskCardItem = {
  id: 'skel-risk-1',
  pestName: '미국선녀벌레',
  severityLabel: '위험',
  timeLabel: '오늘',
}

/** 최근 AI 분석 카드 */
export type RecentAiCardItem = {
  id: string
  title: string
  /** 목록 API에 신뢰도 없으면 null */
  confidencePct: number | null
  targetLabel: string
  timeLabel: string
  thumbUrl?: string | null
}

/** @deprecated 시안 샘플 — 레이아웃 확인용 */
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
    timeLabel: '오늘',
  },
  {
    id: 'skel-3',
    title: '적성병',
    confidencePct: 82,
    targetLabel: '잎',
    timeLabel: '어제',
  },
]
