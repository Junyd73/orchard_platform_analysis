import { describe, expect, it } from 'vitest'

import {
  MSG_PARCEL_DEST_INCOMPLETE,
  MSG_PARCEL_DEST_QTY,
  MSG_PARCEL_QTY_OVER,
} from '@/views/orders/ordersConstants'
import {
  destQtySum,
  effectiveDests,
  emptyDest,
  emptyLine,
  findSaveIssue,
  isBlankDestDraft,
  type EditLine,
} from '@/views/orders/orderFormModel'

function parcelLine(qty: number, dests: EditLine['dests']): EditLine {
  return {
    ...emptyLine(),
    variety_cd: 'FR010101',
    weight_cd: 'SZ010100',
    grade_cd: 'GR010100',
    size_cd: 'FR020101',
    qty: String(qty),
    unit_price: '1000',
    delivery_tp_cd: 'LO010200',
    dests,
  }
}

function weight(): number {
  return 15
}

describe('orderFormModel parcel save rules', () => {
  it('allows parcel with zero destinations', () => {
    const line = parcelLine(30, [emptyDest()])
    expect(isBlankDestDraft(line.dests[0])).toBe(true)
    expect(effectiveDests(line)).toHaveLength(0)
    expect(findSaveIssue([line], weight)).toBeNull()
  })

  it('allows partial destination assignment', () => {
    const line = parcelLine(30, [
      {
        qty: '10',
        rcv_name: '홍길동',
        rcv_tel: '010-1111-2222',
        rcv_addr: '서울',
        dlvry_msg: '',
      },
    ])
    expect(destQtySum(line)).toBe(10)
    expect(findSaveIssue([line], weight)).toBeNull()
  })

  it('allows full destination assignment', () => {
    const line = parcelLine(30, [
      {
        qty: '30',
        rcv_name: '홍길동',
        rcv_tel: '010-1111-2222',
        rcv_addr: '서울',
        dlvry_msg: '',
      },
    ])
    expect(findSaveIssue([line], weight)).toBeNull()
  })

  it('rejects over-assignment', () => {
    const line = parcelLine(30, [
      {
        qty: '31',
        rcv_name: '홍길동',
        rcv_tel: '010-1111-2222',
        rcv_addr: '서울',
        dlvry_msg: '',
      },
    ])
    expect(findSaveIssue([line], weight)?.message).toBe(MSG_PARCEL_QTY_OVER)
  })

  it('rejects incomplete destination fields', () => {
    const base = {
      qty: '5',
      rcv_name: '홍',
      rcv_tel: '010',
      rcv_addr: '서울',
      dlvry_msg: '',
    }
    expect(
      findSaveIssue([parcelLine(30, [{ ...base, qty: '0' }])], weight)?.message,
    ).toBe(MSG_PARCEL_DEST_QTY)
    expect(
      findSaveIssue([parcelLine(30, [{ ...base, rcv_name: '' }])], weight)?.message,
    ).toBe(MSG_PARCEL_DEST_INCOMPLETE)
    expect(
      findSaveIssue([parcelLine(30, [{ ...base, rcv_tel: '' }])], weight)?.message,
    ).toBe(MSG_PARCEL_DEST_INCOMPLETE)
    expect(
      findSaveIssue([parcelLine(30, [{ ...base, rcv_addr: '' }])], weight)?.message,
    ).toBe(MSG_PARCEL_DEST_INCOMPLETE)
  })

  it('treats blank draft with default qty 1 as zero destinations', () => {
    const line = parcelLine(30, [{ ...emptyDest(), qty: '1' }])
    expect(effectiveDests(line)).toHaveLength(0)
    expect(destQtySum(line)).toBe(0)
    expect(findSaveIssue([line], weight)).toBeNull()
  })
})
