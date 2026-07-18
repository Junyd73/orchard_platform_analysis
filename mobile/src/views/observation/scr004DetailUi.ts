import type { ObservationDetail } from '@/types/observation'
import { OBS_AI_DURATION_NOTICE } from '@/composables/constants/app'

/** AI 결과 필드 — API 연동 전 optional */
export type ObservationAiResult = {
  ai_disease_nm?: string | null
  ai_confidence?: number | null
  ai_summary?: string | null
  ai_recommendation?: string | null
}

export function severityTone(cd: string): 'ok' | 'caution' | 'danger' | 'neutral' {
  if (cd === 'OS010400') return 'danger'
  if (cd === 'OS010300') return 'caution'
  if (cd === 'OS010100') return 'ok'
  return 'neutral'
}

export function aiTone(status: string): 'ai' | 'ok' | 'neutral' | 'caution' {
  const s = status.toUpperCase()
  if (s === 'CONFIRMED' || s === 'ANALYZED' || s === 'COMPLETED') return 'ok'
  if (s === 'PENDING' || s === 'NONE' || s === 'REVIEW_REQUIRED') return 'ai'
  if (s === 'FAILED') return 'caution'
  return 'neutral'
}

export function aiLabel(status: string): string {
  const s = status.toUpperCase()
  if (s === 'NONE' || s === 'PENDING') return 'AI 대기'
  if (s === 'ANALYZING') return '분석 중'
  if (s === 'ANALYZED') return '분석 완료'
  if (s === 'COMPLETED') return '분석 완료'
  if (s === 'CONFIRMED') return '후보 확정'
  if (s === 'FAILED') return '분석 실패'
  if (s === 'REVIEW_REQUIRED') return '검토 필요'
  if (s === 'HOLD') return '보류'
  return s ? `상태: ${s}` : 'AI'
}

export function aiHint(status: string): string {
  const s = status.toUpperCase()
  if (s === 'NONE' || s === 'PENDING') {
    return '사진 업로드 후 AI 분석을 요청할 수 있습니다.'
  }
  if (s === 'ANALYZING') {
    return `분석이 진행 중입니다. ${OBS_AI_DURATION_NOTICE}`
  }
  if (s === 'FAILED') return '분석에 실패했습니다. 재분석을 요청할 수 있습니다.'
  if (s === 'REVIEW_REQUIRED') return '분석 결과 검토가 필요합니다.'
  if (s === 'ANALYZED' || s === 'COMPLETED') {
    return '분석 결과입니다. 후보를 선택한 뒤 확정해 주세요.'
  }
  if (s === 'CONFIRMED') {
    return '후보가 확정되었습니다. 스마트 방제 가이드를 확인할 수 있습니다.'
  }
  return '분석 상태를 확인해 주세요.'
}

export function isAiCompleteStatus(status: string): boolean {
  const s = status.toUpperCase()
  return s === 'ANALYZED' || s === 'COMPLETED' || s === 'CONFIRMED'
}

export function hasAiResultData(d: ObservationDetail | null): boolean {
  if (!d) return false
  const r = d as ObservationDetail & ObservationAiResult
  if (String(r.ai_disease_nm || '').trim()) return true
  if (r.ai_confidence != null && !Number.isNaN(Number(r.ai_confidence))) return true
  if (String(r.ai_summary || '').trim()) return true
  if (String(r.ai_recommendation || '').trim()) return true
  return false
}

export const PSIS_UNLINKED_LABEL = '방제 가이드'
export const PSIS_UNLINKED_HINT = '방제 정보를 찾을 수 없습니다.'
/** 카드 제목 (사용자 표시) */
export const PSIS_CARD_TITLE = '스마트 방제 가이드'
/** 결과 영역 제목 */
export const PSIS_RESULT_TITLE = '방제 가이드'
export const PSIS_PREPARING = '방제 가이드를 준비하고 있습니다.'
export const PSIS_NOT_FOUND = '방제 정보를 찾을 수 없습니다.'
export const PSIS_LOAD_FAILED = '방제 정보를 불러오지 못했습니다.'
export const PSIS_AI_GUIDE_INTRO =
  'AI 분석 결과를 바탕으로 방제 가이드를 제공합니다.'

export const PSIS_STOCK_SECTION = '보유 농약(재고 우선)'
export const PSIS_RECOMMEND_SECTION = '추천 농약'
export const PSIS_USAGE_SECTION = '사용 방법'

export const PSIS_USAGE_FIELDS = [
  '적용 병해충',
  '적용 작물',
  '희석배수',
  '사용 시기',
  '안전사용기준',
  '주의사항',
] as const

/** 스마트 방제 가이드(2단계) — Smart Spray Guide API 연동 문구 */
export const GUIDE_LOADING = '방제 가이드를 불러오는 중…'
export const GUIDE_EMPTY = '등록된 스마트 방제 정보가 없습니다.'
export const GUIDE_NO_CANDIDATE = 'AI 후보를 먼저 확정하세요.'
export const GUIDE_ERROR = '스마트 방제 정보를 불러오지 못했습니다.'
export const GUIDE_STOCK_EMPTY = '보유 재고가 없습니다.'
export const GUIDE_DASH = '—'

export type GuideUiPhase =
  | 'idle'
  | 'loading'
  | 'ready'
  | 'empty'
  | 'no_candidate'
  | 'error'

/** 서버 guide_status → UI phase (PARTIAL은 데이터 있음 → ready) */
export function guideUiPhaseFromStatus(status: string): GuideUiPhase {
  const s = String(status || '')
    .trim()
    .toUpperCase()
  if (s === 'READY' || s === 'PARTIAL') return 'ready'
  if (s === 'EMPTY') return 'empty'
  if (s === 'NO_CANDIDATE') return 'no_candidate'
  if (s === 'ERROR') return 'error'
  return 'idle'
}

export function guideIntroMessage(phase: GuideUiPhase): string {
  if (phase === 'loading') return GUIDE_LOADING
  if (phase === 'empty') return GUIDE_EMPTY
  if (phase === 'no_candidate') return GUIDE_NO_CANDIDATE
  if (phase === 'error') return GUIDE_ERROR
  if (phase === 'ready') return PSIS_AI_GUIDE_INTRO
  return ''
}

/** match_level → 사용자 표시 (내부 코드 비노출) */
export function guideMatchLabel(matchLevel?: string | null): string {
  const s = String(matchLevel || '')
    .trim()
    .toUpperCase()
  if (s === 'MATCH') return '등록됨'
  if (s === 'PARTIAL') return '부분 일치'
  if (s === 'NOT_FOUND') return '정보 부족'
  return '정보 부족'
}

export function guideDisplayText(value?: string | number | null): string {
  if (value == null) return GUIDE_DASH
  const s = String(value).trim()
  return s || GUIDE_DASH
}

/** 물 1L(1000㎖) 기준: N배 희석 → 1000/N (g 또는 ml)/L */
const DILUTION_WATER_ML_PER_L = 1000

export type DilutionMassUnit = 'g' | 'ml' | ''

function _parseDilutionNumber(raw: string): number | null {
  const n = Number(String(raw).replace(/,/g, '').trim())
  if (!Number.isFinite(n) || n <= 0) return null
  return n
}

function _formatPerLiterAmount(amount: number): string {
  if (Number.isInteger(amount)) return String(amount)
  const rounded = Math.round(amount * 1000) / 1000
  return String(rounded)
}

function _perLiterFromFold(fold: number): number | null {
  if (!Number.isFinite(fold) || fold <= 0) return null
  return DILUTION_WATER_ML_PER_L / fold
}

function _unitLabel(unit?: string | null): string {
  const u = String(unit || '')
    .trim()
    .toLowerCase()
  if (u === 'ml') return 'ml'
  if (u === 'g') return 'g'
  // 규격 불명 시 g/ml 병기 (오표기 방지)
  return 'g·ml'
}

/**
 * 규격·품목명으로 희석 단위 판별.
 * 예: 250ml/1L → ml, 250g/1kg → g
 */
export function resolveDilutionUnitFromSpec(
  ...hints: Array<string | null | undefined>
): DilutionMassUnit {
  const blob = hints
    .map((h) => String(h || '').trim())
    .filter(Boolean)
    .join(' ')
    .toLowerCase()
  if (!blob) return ''
  if (/\d\s*(?:ml|㎖)\b/i.test(blob) || /\d\s*l\b/i.test(blob)) return 'ml'
  if (/유제|액제|수현탁|액상수화|미탁제/.test(blob)) return 'ml'
  if (/\d\s*(?:g|kg)\b/i.test(blob)) return 'g'
  if (/수화제|입제|분제|수용제|입상수화/.test(blob)) return 'g'
  return ''
}

/**
 * 희석배수 표시: "2000배" + 단위 → "2000배 (0.5ml/L)" 또는 "(0.5g/L)"
 * 물 1L 기준 약제량 = 1000 ÷ 배수
 */
export function formatDilutionWithPerLiter(
  raw?: string | null,
  unit?: string | null,
): string {
  const base = guideDisplayText(raw)
  if (base === GUIDE_DASH) return base
  if (/\d\s*(?:g|㎖|ml)\s*(?:·\s*ml)?\s*\/\s*L/i.test(base)) return base

  const unitText = _unitLabel(unit)
  const range = base.match(
    /(\d+(?:[.,]\d+)?)\s*[~～\-–—]\s*(\d+(?:[.,]\d+)?)\s*배/,
  )
  if (range) {
    const a = _perLiterFromFold(_parseDilutionNumber(range[1]) ?? 0)
    const b = _perLiterFromFold(_parseDilutionNumber(range[2]) ?? 0)
    if (a != null && b != null) {
      return `${base} (${_formatPerLiterAmount(a)}~${_formatPerLiterAmount(b)}${unitText}/L)`
    }
    return base
  }

  const single = base.match(/(\d+(?:[.,]\d+)?)\s*배/)
  if (single) {
    const amount = _perLiterFromFold(_parseDilutionNumber(single[1]) ?? 0)
    if (amount != null) {
      return `${base} (${_formatPerLiterAmount(amount)}${unitText}/L)`
    }
  }
  return base
}

export const GUIDE_USAGE_ROWS = [
  { key: 'dilution', label: '희석배수' },
  { key: 'phi', label: 'PHI(수확 전 안전사용기간)' },
  { key: 'max_use_count', label: '최대 사용횟수' },
  { key: 'usage_method', label: '사용방법' },
  { key: 'toxicity', label: '주의사항' },
] as const

/** ② 추천 등록 농약 — 보유 재고 제외 표시 상한 (정렬·추천 로직 보완 후 사용) */
export const GUIDE_RECOMMEND_LIMIT = 10

/** ② 추천 영역 — 정렬/추천 기준 보완 전까지 안내 */
export const GUIDE_RECOMMEND_PENDING = '보완 개발 중'

export const GUIDE_USAGE_PICK_HINT = '농약을 선택하면 사용 기준이 표시됩니다.'
export const GUIDE_USAGE_FOR_PREFIX = '선택:'

export const AI_PENDING_API_HINT =
  'AI 분석 결과가 없습니다. 아래에서 분석을 요청해 주세요.'
