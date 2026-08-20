import { describe, expect, it } from 'vitest'

import type { StockItem } from '@/api/stock'
import { stockDraftKey, stockSaleSpecKey } from '@/views/sales/shipConfirmModel'
import {
  aggregateSaleStockSources,
  buildStockListEntries,
} from '@/views/stock/stockSaleList'

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
    weight: 5,
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

describe('stockSaleSpecKey / stockSaleList', () => {
  it('T11 stockSaleSpecKey는 storage_dt에 영향받지 않음', () => {
    const a = stock({ storage_dt: '2026-08-01' })
    const b = stock({ storage_dt: '2026-08-20' })
    expect(stockSaleSpecKey(a)).toBe(stockSaleSpecKey(b))
    expect(stockDraftKey({ ...a, storage_dt: a.storage_dt })).not.toBe(
      stockDraftKey({ ...b, storage_dt: b.storage_dt }),
    )
  })

  it('T8~T9 동일규격 서로 다른 storage_dt → 가용 합계 1행', () => {
    const rows = [
      stock({ storage_dt: '2026-08-01', available_qty: 10, real_qty: 10, reserved_qty: 1 }),
      stock({ storage_dt: '2026-08-20', available_qty: 15, real_qty: 15, reserved_qty: 2 }),
    ]
    const entries = buildStockListEntries(rows, { raw: false })
    expect(entries).toHaveLength(1)
    expect(entries[0].sources).toHaveLength(2)
    expect(entries[0].row.available_qty).toBe(25)
    expect(entries[0].row.real_qty).toBe(25)
    expect(entries[0].row.reserved_qty).toBe(3)
    expect(entries[0].row.storage_dt).toBe('')
    const agg = aggregateSaleStockSources(rows)
    expect(agg.available_qty).toBe(10 + 15)
  })

  it('원물은 storage_dt별 개별 행 유지', () => {
    const rows = [
      stock({ item_cd: 'FR010300', storage_dt: '2026-08-01', available_qty: 10 }),
      stock({ item_cd: 'FR010300', storage_dt: '2026-08-20', available_qty: 15 }),
    ]
    const entries = buildStockListEntries(rows, { raw: true })
    expect(entries).toHaveLength(2)
  })
})
