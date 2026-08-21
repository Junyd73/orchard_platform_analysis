/** 재고조정 사유 — core/stock_adjust_constants.py 와 동일 코드값. */

export const PARENT_ADJUST_REASON = 'AD010100'

export const REASON_DISPOSE = 'AD010101'
export const REASON_DAMAGE = 'AD010102'
export const REASON_GIFT = 'AD010103'
export const REASON_RETURN = 'AD010104'
export const REASON_COUNT_DIFF = 'AD010105'
export const REASON_OTHER = 'AD010106'

export const ADJUST_REASON_OPTIONS = [
  { value: REASON_DISPOSE, label: '폐기' },
  { value: REASON_DAMAGE, label: '파손' },
  { value: REASON_GIFT, label: '증정' },
  { value: REASON_RETURN, label: '반품' },
  { value: REASON_COUNT_DIFF, label: '실사차이' },
  { value: REASON_OTHER, label: '기타' },
] as const

const OUT_ONLY = new Set([REASON_DISPOSE, REASON_DAMAGE, REASON_GIFT])
const IN_ONLY = new Set([REASON_RETURN])

export function reasonAllowsIn(reasonCd: string): boolean {
  return !OUT_ONLY.has(reasonCd)
}

export function reasonAllowsOut(reasonCd: string): boolean {
  return !IN_ONLY.has(reasonCd)
}
