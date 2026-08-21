import { describe, expect, it } from 'vitest'

import {
  allocQtySum,
  deliveryStatusText,
  findParcelDeliveryIssue,
  totalAllocShipFee,
} from '@/features/sales/shipDeliveryModel'
import type { ShipDraftLine } from '@/features/sales/shipConfirmModel'

function line(partial: Partial<ShipDraftLine> & { qty: number }): ShipDraftLine {
  return {
    order_detail_id: null,
    item_cd: 'FR010100',
    variety_cd: 'FR010101',
    grade_cd: 'GR010100',
    size_cd: 'FR020101',
    weight: 5,
    harvest_year: 2026,
    wh_cd: 'WH01',
    unit_price: 1000,
    remaining_qty: null,
    alloc_remaining: 0,
    delivery_allocations: [],
    ...partial,
  }
}

describe('shipDeliveryModel 2C', () => {
  it('deliveryStatusText 미지정/완료/초과', () => {
    expect(deliveryStatusText(3, 0)).toBe('배송 0/3박스 · 3미지정')
    expect(deliveryStatusText(3, 2)).toBe('배송 2/3박스 · 1미지정')
    expect(deliveryStatusText(3, 3)).toBe('배송지 등록 완료')
    expect(deliveryStatusText(3, 4)).toBe('배송 4/3박스 · 1초과')
  })

  it('findParcelDeliveryIssue qty mismatch', () => {
    const ln = line({
      qty: 3,
      delivery_allocations: [
        {
          draft_id: '1',
          qty: 1,
          rcv_name: 'A',
          rcv_tel: '1',
          rcv_addr: 'x',
          dlvry_msg: '',
          ship_fee: 0,
        },
      ],
    })
    expect(findParcelDeliveryIssue([ln])).toContain('합계')
    expect(allocQtySum(ln)).toBe(1)
  })

  it('totalAllocShipFee', () => {
    const lines = [
      line({
        qty: 2,
        delivery_allocations: [
          {
            draft_id: '1',
            qty: 1,
            rcv_name: 'A',
            rcv_tel: '1',
            rcv_addr: 'x',
            dlvry_msg: '',
            ship_fee: 4000,
          },
          {
            draft_id: '2',
            qty: 1,
            rcv_name: 'B',
            rcv_tel: '2',
            rcv_addr: 'y',
            dlvry_msg: '',
            ship_fee: 0,
          },
        ],
      }),
      line({
        qty: 1,
        delivery_allocations: [
          {
            draft_id: '3',
            qty: 1,
            rcv_name: 'C',
            rcv_tel: '3',
            rcv_addr: 'z',
            dlvry_msg: '',
            ship_fee: 2000,
          },
        ],
      }),
    ]
    expect(totalAllocShipFee(lines)).toBe(6000)
  })
})
