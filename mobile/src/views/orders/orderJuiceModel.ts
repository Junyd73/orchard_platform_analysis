/** 주문 배즙 포장규격 — 실제 fruit-stock 판매규격 기반 */

import type { StockItem } from '@/api/stock'
import { stockSaleSpecKey } from '@/views/sales/shipConfirmModel'
import {
  ITEM_JUICE_DORAJI,
  ITEM_JUICE_PLAIN,
  juiceItemLabel,
} from '@/views/orders/ordersConstants'
import { buildStockListEntries } from '@/views/stock/stockSaleList'

const JUICE_ORDER_ITEM_CDS = new Set([ITEM_JUICE_PLAIN, ITEM_JUICE_DORAJI])

export type JuicePackOption = {
  key: string
  label: string
  item_cd: string
  variety_cd: string
  grade_cd: string
  size_cd: string
  weight: number
  wh_cd: string
  harvest_year: number
  available_qty: number
}

export function isJuiceOrderItemCd(itemCd: string | null | undefined): boolean {
  return JUICE_ORDER_ITEM_CDS.has(String(itemCd || '').trim())
}

/** 대표 표시: grade_nm(예: 30포) 우선 */
export function juicePackLabel(row: Pick<StockItem, 'grade_nm' | 'size_nm' | 'weight'>): string {
  const grade = String(row.grade_nm || '').trim()
  if (grade) return grade
  const size = String(row.size_nm || '').trim()
  if (size) return size
  const w = Number(row.weight)
  return Number.isFinite(w) && w > 0 ? `${w}` : ''
}

export function buildJuicePackOptions(rows: StockItem[]): JuicePackOption[] {
  const sellable = rows.filter(
    (r) => isJuiceOrderItemCd(r.item_cd) && Number(r.available_qty) > 0,
  )
  const entries = buildStockListEntries(sellable, { raw: false })
  return entries.map((e) => {
    const row = e.row
    return {
      key: e.listKey,
      label: juicePackLabel(row),
      item_cd: row.item_cd,
      variety_cd: row.variety_cd,
      grade_cd: row.grade_cd,
      size_cd: row.size_cd,
      weight: Number(row.weight) || 0,
      wh_cd: row.wh_cd,
      harvest_year: Number(row.harvest_year) || 0,
      available_qty: Number(row.available_qty) || 0,
    }
  })
}

export function juicePackOptionsForItem(
  options: JuicePackOption[],
  itemCd: string,
): JuicePackOption[] {
  const cd = String(itemCd || '').trim()
  return options.filter((o) => o.item_cd === cd)
}

export function findJuicePackOption(
  options: JuicePackOption[],
  key: string,
): JuicePackOption | undefined {
  return options.find((o) => o.key === key)
}

/**
 * 포장규격 선택 규칙:
 * - available 규격 0 → null (호출측 clear)
 * - 현재 key가 유효하면 유지
 * - 규격 1개 → 자동선택
 * - 규격 2개 이상 + key 없음/무효 → null (dropdown 재선택)
 */
export function resolveJuicePackSelection(
  packs: JuicePackOption[],
  currentKey: string | null | undefined,
): JuicePackOption | null {
  if (!packs.length) return null
  const key = String(currentKey || '').trim()
  if (key) {
    const hit = packs.find((p) => p.key === key)
    if (hit) return hit
  }
  if (packs.length === 1) return packs[0]
  return null
}

export function juiceLineSummaryText(line: {
  item_cd: string
  item_nm?: string
  juice_pack_label?: string
  grade_nm?: string
}): string {
  const kind = juiceItemLabel(line.item_cd, line.item_nm)
  const pack = String(line.juice_pack_label || line.grade_nm || '').trim()
  return pack ? `${kind} · ${pack}` : kind
}

export function juicePackKeyFromStockFields(row: {
  wh_cd: string
  item_cd: string
  variety_cd: string
  grade_cd: string
  size_cd: string
  weight: number
  harvest_year: number
}): string {
  return stockSaleSpecKey(row)
}
