import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import type { StockItem } from '@/api/stock'
import { stockDraftKey } from '@/views/sales/shipConfirmModel'
import { useSalesPrefillStore } from '@/composables/stores/salesPrefill'

function stock(partial: Partial<StockItem> = {}): StockItem {
  return {
    farm_cd: 'OR001',
    wh_cd: 'WH01',
    item_cd: 'FR010100',
    item_nm: '배',
    variety_cd: 'FR010101',
    variety_nm: '신고',
    grade_cd: 'GR010100',
    grade_nm: '특',
    size_cd: 'FR020101',
    size_nm: '25과',
    weight: 15,
    harvest_year: 2026,
    storage_dt: '2026-08-19',
    in_qty: 10,
    out_qty: 0,
    real_qty: 10,
    reserved_qty: 0,
    available_qty: 10,
    ...partial,
  }
}

describe('salesPrefill stock helpers (2A)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('T1 addStockLine: qty 반영 + 1 line', () => {
    const store = useSalesPrefillStore()
    store.addStockLine(stock(), 3)
    expect(store.source).toBe('STOCK')
    expect(store.shipLines).toHaveLength(1)
    expect(store.shipLines[0].qty).toBe(3)
    expect(store.stockDraftTotalQty).toBe(3)
  })

  it('T2 updateStockLineQty: 동일 line qty만 변경, 중복 없음', () => {
    const store = useSalesPrefillStore()
    const row = stock()
    store.addStockLine(row, 3)
    const key = stockDraftKey(store.shipLines[0])
    store.updateStockLineQty(key, 5)
    expect(store.shipLines).toHaveLength(1)
    expect(store.shipLines[0].qty).toBe(5)
  })

  it('T3 removeStockLineByKey: 제거 후 STOCK 세션 유지(빈 lines 허용)', () => {
    const store = useSalesPrefillStore()
    const row = stock()
    store.addStockLine(row, 2)
    store.setCustomer('C1', '홍길동')
    const key = stockDraftKey(store.shipLines[0])
    store.removeStockLineByKey(key)
    expect(store.shipLines).toHaveLength(0)
    expect(store.source).toBe('STOCK')
    expect(store.isStockSaleSession()).toBe(true)
    expect(store.custmId).toBe('C1')
  })

  it('T12 같은 상품 반복 담기 → 중복 line 없음(qty 갱신)', () => {
    const store = useSalesPrefillStore()
    const row = stock()
    store.addStockLine(row, 3)
    store.addStockLine(row, 4)
    expect(store.shipLines).toHaveLength(1)
    expect(store.shipLines[0].qty).toBe(4)
  })

  it('T9 ORDER shipLines는 STOCK 바구니로 취급하지 않음', () => {
    const store = useSalesPrefillStore()
    store.setFromOrderLines(
      {
        order_no: 'ORD1',
        custm_id: 'A1',
        customer: '고객A',
        order_dt: '2026-08-01',
        status_cd: 'ST010100',
        status_nm: '',
        tot_order_amt: 0,
        tot_ship_fee: 0,
        tot_pay_amt: 0,
        lines: [],
      } as never,
      [{
        order_detail_id: 'ORD1-01',
        item_cd: 'FR010100',
        variety_cd: 'FR010101',
        grade_cd: 'GR010100',
        size_cd: 'FR020101',
        weight: 15,
        qty: 2,
        unit_price: 1000,
        item_amt: 2000,
        harvest_year: 2026,
        wh_cd: 'WH01',
        dlvry_tp: 'DL010100',
        remaining_order_qty: 2,
        reserved_unshipped_qty: 0,
      } as never],
    )
    expect(store.source).toBe('ORDER')
    expect(store.shipLines.length).toBeGreaterThan(0)
    expect(store.isStockSaleSession()).toBe(false)
    expect(store.stockDraftTotalQty).toBe(0)
  })

  it('가용 초과 qty는 clamp', () => {
    const store = useSalesPrefillStore()
    store.addStockLine(stock({ available_qty: 2 }), 99)
    expect(store.shipLines[0].qty).toBe(2)
  })
})
