import type { StockItem } from '@/api/stock'
import { stockDraftKey, stockSaleSpecKey } from '@/views/sales/shipConfirmModel'

/** 판매/원물 목록 1행. sources는 실제 t_stock_master 행(재고조정용). */
export type StockListEntry = {
  /** 목록·판매바구니 key (판매=규격, 원물=storage 포함) */
  listKey: string
  /** 화면 표시용 (판매 시 qty 합계 반영) */
  row: StockItem
  /** 조정 대상이 되는 원본 stock row들 */
  sources: StockItem[]
}

function sumQty(rows: StockItem[], field: 'available_qty' | 'real_qty' | 'reserved_qty' | 'in_qty' | 'out_qty') {
  return rows.reduce((s, r) => s + (Number(r[field]) || 0), 0)
}

/** 동일 판매규격 source rows → 표시용 1행 */
export function aggregateSaleStockSources(sources: StockItem[]): StockItem {
  const base = sources[0]
  return {
    ...base,
    storage_dt: '',
    available_qty: sumQty(sources, 'available_qty'),
    real_qty: sumQty(sources, 'real_qty'),
    reserved_qty: sumQty(sources, 'reserved_qty'),
    in_qty: sumQty(sources, 'in_qty'),
    out_qty: sumQty(sources, 'out_qty'),
  }
}

/**
 * 상품/배즙: 판매규격(storage_dt 제외)으로 집계.
 * 원물: storage_dt별 개별 행 유지(생산 원료 LOT 추적 — 화면에는 일자 미표시).
 */
export function buildStockListEntries(rows: StockItem[], opts: { raw: boolean }): StockListEntry[] {
  if (opts.raw) {
    return [...rows]
      .sort(
        (a, b) =>
          b.storage_dt.localeCompare(a.storage_dt) ||
          a.variety_cd.localeCompare(b.variety_cd),
      )
      .map((r) => ({
        listKey: stockDraftKey({
          item_cd: r.item_cd,
          variety_cd: r.variety_cd,
          grade_cd: r.grade_cd,
          size_cd: r.size_cd,
          weight: r.weight,
          harvest_year: r.harvest_year,
          storage_dt: r.storage_dt || '',
          wh_cd: r.wh_cd,
        }),
        row: r,
        sources: [r],
      }))
  }

  const groups = new Map<string, StockItem[]>()
  for (const r of rows) {
    const key = stockSaleSpecKey(r)
    const list = groups.get(key)
    if (list) list.push(r)
    else groups.set(key, [r])
  }

  const entries: StockListEntry[] = []
  for (const [listKey, sources] of groups) {
    const sorted = [...sources].sort((a, b) => a.storage_dt.localeCompare(b.storage_dt))
    entries.push({
      listKey,
      row: aggregateSaleStockSources(sorted),
      sources: sorted,
    })
  }

  return entries.sort(
    (a, b) =>
      a.row.variety_cd.localeCompare(b.row.variety_cd) ||
      a.row.weight - b.row.weight ||
      a.row.grade_cd.localeCompare(b.row.grade_cd) ||
      a.row.size_cd.localeCompare(b.row.size_cd),
  )
}

/** `재고(0)포함` — 화면 가용수량(entry.row.available_qty)과 동일 기준 */
export function filterStockEntriesByAvailable(
  entries: StockListEntry[],
  includeZero: boolean,
): StockListEntry[] {
  if (includeZero) return entries
  return entries.filter((entry) => Number(entry.row.available_qty) > 0)
}
