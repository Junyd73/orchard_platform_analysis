/** 배즙 신규 재고등록 v1 — UI/payload 모델 */

import {
  DEFAULT_JUICE_SIZE_CD,
  DEFAULT_JUICE_WEIGHT,
  DEFAULT_WH_CD,
  ITEM_JUICE_DORAJI,
  ITEM_JUICE_PLAIN,
  MSG_INITIAL_SPEC_EXISTS,
  PARENT_JUICE_QTY,
} from '@/views/stock/stockInitialConstants'
import { REASON_OTHER } from '@/views/stock/stockAdjustConstants'

export {
  DEFAULT_JUICE_SIZE_CD,
  DEFAULT_JUICE_WEIGHT,
  DEFAULT_WH_CD,
  ITEM_JUICE_DORAJI,
  ITEM_JUICE_PLAIN,
  MSG_INITIAL_SPEC_EXISTS,
  PARENT_JUICE_QTY,
}

export const LABEL_STOCK_INITIAL = '재고 등록'
export const LABEL_STOCK_INITIAL_BTN = '+ 재고 등록'
export const LABEL_JUICE_KIND = '배즙 종류'
export const LABEL_PACK = '포장규격'
export const LABEL_YEAR = '재고연도'
export const LABEL_WH = '창고'
export const LABEL_QTY = '초기수량'
export const LABEL_REASON = '등록사유'
export const LABEL_MEMO = '메모'
export const DEFAULT_INITIAL_MEMO = '배즙 초기재고 등록'

export const JUICE_INITIAL_ITEM_OPTIONS = [
  { value: ITEM_JUICE_DORAJI, label: '도라지배즙' },
  { value: ITEM_JUICE_PLAIN, label: '일반배즙' },
] as const

export type JuiceInitialDraft = {
  item_cd: string
  grade_cd: string
  harvest_year: string
  wh_cd: string
  qty: string
  reason_cd: string
  memo: string
}

export type JuiceInitialPayload = {
  item_cd: string
  variety_cd: string
  weight: number
  grade_cd: string
  size_cd: string
  harvest_year: number
  wh_cd: string
  initial_qty: number
  reason_cd: string
  memo: string
}

export function emptyJuiceInitialDraft(year: number): JuiceInitialDraft {
  return {
    item_cd: ITEM_JUICE_DORAJI,
    grade_cd: '',
    harvest_year: String(year),
    wh_cd: DEFAULT_WH_CD,
    qty: '50',
    reason_cd: REASON_OTHER,
    memo: DEFAULT_INITIAL_MEMO,
  }
}

export function resolveDefaultVarietyCd(
  codes: { code_cd: string }[],
): string {
  const preferred = 'FR010101'
  if (codes.some((c) => c.code_cd === preferred)) return preferred
  const leaf = codes.find((c) => {
    const cd = String(c.code_cd || '')
    return cd.length === 8 && !cd.endsWith('00')
  })
  return leaf?.code_cd || ''
}

export function buildJuiceInitialPayload(
  draft: JuiceInitialDraft,
  opts: { variety_cd: string },
): JuiceInitialPayload | { error: string } {
  const item = String(draft.item_cd || '').trim()
  if (item !== ITEM_JUICE_DORAJI && item !== ITEM_JUICE_PLAIN) {
    return { error: '배즙 종류를 선택해 주세요.' }
  }
  const grade = String(draft.grade_cd || '').trim()
  if (!grade) return { error: '포장규격을 선택해 주세요.' }
  const year = Number(draft.harvest_year)
  if (!Number.isInteger(year) || year < 2000 || year > 2100) {
    return { error: '재고연도가 올바르지 않습니다.' }
  }
  const qty = Number(draft.qty)
  if (!Number.isFinite(qty) || qty <= 0) {
    return { error: '초기수량은 1 이상 입력해 주세요.' }
  }
  const wh = String(draft.wh_cd || '').trim() || DEFAULT_WH_CD
  const variety = String(opts.variety_cd || '').trim()
  if (!variety) return { error: '품종 정보를 확인할 수 없습니다.' }
  const reason = String(draft.reason_cd || '').trim()
  if (!reason) return { error: '등록사유를 선택해 주세요.' }
  return {
    item_cd: item,
    variety_cd: variety,
    weight: DEFAULT_JUICE_WEIGHT,
    grade_cd: grade,
    size_cd: DEFAULT_JUICE_SIZE_CD,
    harvest_year: year,
    wh_cd: wh,
    initial_qty: qty,
    reason_cd: reason,
    memo: String(draft.memo || '').trim(),
  }
}

export function juiceInitialSummary(input: {
  itemLabel: string
  packLabel: string
  qty: number | string
  wh_cd: string
}): string {
  return `${input.itemLabel} · ${input.packLabel} · ${input.qty}박스 · ${input.wh_cd}`
}

export function isJuiceInitialDuplicateError(err: {
  errorCode?: string
  message?: string
}): boolean {
  if (err.errorCode === 'STOCK_SPEC_EXISTS') return true
  return String(err.message || '').includes('동일 규격 재고가 존재합니다')
}
