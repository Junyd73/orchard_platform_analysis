import { describe, expect, it } from 'vitest'

import {
  LABEL_MIXED_DELIVERY,
  ORDER_STATUS_CANCEL,
  ORDER_STATUS_CONFIRMED,
  ORDER_STATUS_DELIVERED,
  ORDER_STATUS_PREP,
  ORDER_STATUS_RESERVED,
  orderListDateText,
  orderListDeliveryText,
  orderListProductText,
  orderListSecondaryText,
  orderListShipRemainText,
  orderStatusLabelOf,
  orderStatusToneOf,
} from '@/views/orders/ordersConstants'
import type { OrderListItem } from '@/types/order'

const REP = {
  rep_item_cd: 'FR010100',
  rep_variety_cd: 'FR010101',
  rep_variety_nm: '신고',
  rep_grade_cd: 'GR010100',
  rep_grade_nm: '특',
  rep_size_cd: 'FR020101',
  rep_size_nm: '18과',
  rep_weight: 15,
}

const SPEC_TEXT = '신고 · 15kg · 특 · 18과'

function rowOf(extra: Partial<OrderListItem> = {}): OrderListItem {
  return {
    order_no: 'ORD20260817-001',
    order_dt: '2026-08-17',
    custm_id: 'C001',
    customer: '김고객',
    status_cd: ORDER_STATUS_RESERVED,
    status_nm: '예약접수',
    total_qty: 30,
    total_amt: 50000,
    pre_pay_amt: 0,
    line_count: 1,
    delivery_tp_cd: 'LO010200',
    delivery_tp_nm: '택배',
    delivery_tp_count: 1,
    confirmed_shipped_qty: 0,
    remaining_order_qty: 30,
    ...REP,
    ...extra,
  }
}

describe('orderListProductText', () => {
  it('shows the representative spec only for a single line', () => {
    expect(orderListProductText(rowOf())).toBe(SPEC_TEXT)
  })

  it('appends 외 N건 for multi line orders', () => {
    expect(orderListProductText(rowOf({ line_count: 2 }))).toBe(`${SPEC_TEXT} 외 1건`)
    expect(orderListProductText(rowOf({ line_count: 4 }))).toBe(`${SPEC_TEXT} 외 3건`)
  })

  it('falls back to codes when names are missing and empty when no line', () => {
    expect(
      orderListProductText({
        line_count: 1,
        rep_variety_cd: 'FR010101',
        rep_grade_cd: 'GR010100',
        rep_size_cd: 'FR020101',
        rep_weight: 0,
      }),
    ).toBe('FR010101 · GR010100 · FR020101')
    expect(orderListProductText(rowOf({ line_count: 0 }))).toBe('')
  })
})

describe('orderListDeliveryText', () => {
  it('shows the delivery name for a single type', () => {
    expect(orderListDeliveryText(rowOf())).toBe('택배')
  })

  it('shows 복합배송 when more than one type is mixed', () => {
    expect(
      orderListDeliveryText(rowOf({ delivery_tp_count: 2, delivery_tp_cd: '', delivery_tp_nm: '' })),
    ).toBe(LABEL_MIXED_DELIVERY)
  })

  it('is empty when there is no delivery type', () => {
    expect(
      orderListDeliveryText({ delivery_tp_count: 0, delivery_tp_cd: '', delivery_tp_nm: '' }),
    ).toBe('')
  })
})

describe('orderListDateText', () => {
  it('drops the year from ISO dates', () => {
    expect(orderListDateText('2026-08-17')).toBe('08-17')
  })

  it('accepts compact YYYYMMDD', () => {
    expect(orderListDateText('20260817')).toBe('08-17')
  })

  it('returns the raw value when unparsable', () => {
    expect(orderListDateText('')).toBe('')
    expect(orderListDateText(null)).toBe('')
    expect(orderListDateText('N/A')).toBe('N/A')
  })
})

describe('orderListShipRemainText', () => {
  it('renders 출고/잔여 from the server values', () => {
    expect(orderListShipRemainText(rowOf({ confirmed_shipped_qty: 10, remaining_order_qty: 20 }))).toBe(
      '10/20',
    )
  })

  it('is 0/전량 when nothing shipped', () => {
    expect(orderListShipRemainText(rowOf({ confirmed_shipped_qty: 0, remaining_order_qty: 30 }))).toBe(
      '0/30',
    )
  })

  it('is 전량/0 when fully shipped', () => {
    expect(orderListShipRemainText(rowOf({ confirmed_shipped_qty: 30, remaining_order_qty: 0 }))).toBe(
      '30/0',
    )
  })

  it('derives remaining from total_qty when the server omits it', () => {
    expect(orderListShipRemainText({ total_qty: 30, confirmed_shipped_qty: 10 })).toBe('10/20')
    expect(orderListShipRemainText({ total_qty: 30 })).toBe('0/30')
  })
})

describe('orderListSecondaryText', () => {
  it('joins product, delivery and date with a middle dot', () => {
    expect(orderListSecondaryText(rowOf({ line_count: 2 }))).toBe(
      `${SPEC_TEXT} 외 1건 · 택배 · 08-17`,
    )
  })

  it('uses 복합배송 for mixed delivery orders', () => {
    expect(
      orderListSecondaryText(rowOf({ delivery_tp_count: 2, delivery_tp_cd: '', delivery_tp_nm: '' })),
    ).toBe(`${SPEC_TEXT} · ${LABEL_MIXED_DELIVERY} · 08-17`)
  })
})

describe('order status label/tone', () => {
  it('labels ST010300 as 부분출고', () => {
    expect(orderStatusLabelOf(ORDER_STATUS_PREP)).toBe('부분출고')
    expect(orderStatusToneOf(ORDER_STATUS_PREP)).toBe('caution')
  })

  it('maps the remaining ST01 codes', () => {
    expect(orderStatusLabelOf(ORDER_STATUS_RESERVED)).toBe('예약접수')
    expect(orderStatusToneOf(ORDER_STATUS_RESERVED)).toBe('neutral')
    expect(orderStatusLabelOf(ORDER_STATUS_CONFIRMED)).toBe('주문확정')
    expect(orderStatusToneOf(ORDER_STATUS_CONFIRMED)).toBe('ok')
    expect(orderStatusLabelOf(ORDER_STATUS_DELIVERED)).toBe('배송완료')
    expect(orderStatusToneOf(ORDER_STATUS_DELIVERED)).toBe('neutral')
    expect(orderStatusLabelOf(ORDER_STATUS_CANCEL)).toBe('취소')
    expect(orderStatusToneOf(ORDER_STATUS_CANCEL)).toBe('danger')
  })
})
