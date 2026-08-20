import { describe, expect, it } from 'vitest'

import {
  REASON_COUNT_DIFF,
  REASON_DAMAGE,
  REASON_DISPOSE,
  REASON_GIFT,
  REASON_OTHER,
  REASON_RETURN,
  reasonAllowsIn,
  reasonAllowsOut,
} from '@/views/stock/stockAdjustConstants'

describe('stockAdjustConstants', () => {
  it('T2-T4 폐기/파손/증정은 감소만', () => {
    for (const cd of [REASON_DISPOSE, REASON_DAMAGE, REASON_GIFT]) {
      expect(reasonAllowsOut(cd)).toBe(true)
      expect(reasonAllowsIn(cd)).toBe(false)
    }
  })

  it('T5 반품은 증가만', () => {
    expect(reasonAllowsIn(REASON_RETURN)).toBe(true)
    expect(reasonAllowsOut(REASON_RETURN)).toBe(false)
  })

  it('T6-T8 실사차이·기타는 증가/감소 모두', () => {
    for (const cd of [REASON_COUNT_DIFF, REASON_OTHER]) {
      expect(reasonAllowsIn(cd)).toBe(true)
      expect(reasonAllowsOut(cd)).toBe(true)
    }
  })
})
