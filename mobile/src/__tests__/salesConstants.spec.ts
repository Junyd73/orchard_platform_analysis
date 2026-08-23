import { describe, expect, it } from 'vitest'

import {
  PAYMENT_STATUS_PARTIAL,
  PAYMENT_STATUS_UNPAID,
  SALES_SOURCE_AUCTION_RT,
  SALES_STATUS_CONFIRMED,
  SALES_STATUS_DRAFT,
  paymentStatusLabelOf,
  paymentStatusToneOf,
  salesListSecondaryText,
  salesRouteLabel,
  salesStatusLabelOf,
} from '@/features/sales/salesConstants'
import type { SalesListItem } from '@/types/sales'

const BASE: SalesListItem = {
  sales_no: '20260822-01',
  sales_dt: '2026-08-22',
  custm_id: 'C001',
  customer: '홍길동',
  order_no: null,
  sales_status: SALES_STATUS_CONFIRMED,
  sales_source: 'ORDER',
  tot_sales_amt: 950000,
  paid_amt: 800000,
  unpaid_amt: 150000,
  payment_status: PAYMENT_STATUS_PARTIAL,
  rep_item_cd: 'FR010100',
  rep_variety_cd: 'FR010101',
  rep_variety_nm: '신고',
  rep_weight: 15,
  rep_grade_cd: 'GR010100',
  rep_grade_nm: '특',
  rep_size_cd: 'SZ010100',
  rep_size_nm: '20과',
}

describe('salesConstants', () => {
  it('판매/수금 배지 라벨·tone', () => {
    expect(salesStatusLabelOf(SALES_STATUS_CONFIRMED)).toBe('판매확정')
    expect(salesStatusLabelOf(SALES_STATUS_DRAFT)).toBe('초안')
    expect(paymentStatusLabelOf({ sales_status: SALES_STATUS_DRAFT, payment_status: null })).toBe(
      '수금대기',
    )
    expect(paymentStatusLabelOf(BASE)).toBe('부분수금')
    expect(paymentStatusToneOf(BASE)).toBe('caution')
    expect(paymentStatusToneOf({ sales_status: SALES_STATUS_DRAFT, payment_status: null })).toBe(
      'neutral',
    )
    expect(
      paymentStatusToneOf({
        sales_status: SALES_STATUS_CONFIRMED,
        payment_status: PAYMENT_STATUS_UNPAID,
      }),
    ).toBe('danger')
  })

  it('판매경로 helper', () => {
    expect(salesRouteLabel({ sales_source: SALES_SOURCE_AUCTION_RT, order_no: null })).toBe('경매')
    expect(salesRouteLabel({ sales_source: 'ORDER', order_no: 'ORD001' })).toBe('주문출고')
    expect(salesRouteLabel({ sales_source: 'ORDER', order_no: null })).toBe('직접판매')
  })

  it('2줄 보조문구', () => {
    const text = salesListSecondaryText(BASE)
    expect(text).toContain('신고')
    expect(text).toContain('08-22')
    expect(text).toContain('직접판매')
  })
})
