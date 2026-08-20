import { defineStore } from 'pinia'
import { ref } from 'vue'

import type { ProductionPrefillLine } from '@/api/production'
import type { StockItem } from '@/api/stock'
import {
  SHIP_MODE_DIRECT,
  canUseStockMode,
  defaultShipMode,
  type ShipDraftLine,
  type ShipEntrySource,
} from '@/views/sales/shipConfirmModel'
import type { ShipMode } from '@/types/shipment'
import type { OrderDetail, OrderLine } from '@/types/order'
import { DEFAULT_WAREHOUSE_CD } from '@/views/orders/ordersConstants'
import type { RemainingOrderLine, ShipConfirmResponse } from '@/types/shipment'

export type ShipReturnTo = 'sales' | 'order-detail' | 'stock'

function draftFromProduction(ln: ProductionPrefillLine): ShipDraftLine {
  return {
    order_detail_id: null,
    item_cd: ln.item_cd,
    variety_cd: ln.variety_cd,
    grade_cd: ln.grade_cd,
    size_cd: ln.size_cd,
    weight: Number(ln.weight) || 0,
    harvest_year: Number(ln.harvest_year) || 0,
    wh_cd: ln.wh_cd || DEFAULT_WAREHOUSE_CD,
    qty: Number(ln.qty) || 0,
    unit_price: 0,
    remaining_qty: null,
    alloc_remaining: 0,
    variety_nm: ln.variety_nm,
    grade_nm: ln.grade_nm,
    size_nm: ln.size_nm,
    item_nm: ln.item_nm,
  }
}

function draftFromOrderLine(line: OrderLine): ShipDraftLine {
  const alloc = Number(line.reserved_unshipped_qty ?? 0)
  const remaining = Number(line.remaining_order_qty ?? line.qty)
  return {
    order_detail_id: line.order_detail_id,
    item_cd: line.item_cd,
    variety_cd: line.variety_cd,
    grade_cd: line.grade_cd,
    size_cd: line.size_cd,
    weight: Number(line.weight) || 0,
    harvest_year: Number(line.harvest_year) || 0,
    wh_cd: line.wh_cd || DEFAULT_WAREHOUSE_CD,
    qty: remaining,
    unit_price: Number(line.unit_price) || 0,
    remaining_qty: remaining,
    alloc_remaining: alloc,
    variety_nm: line.variety_nm,
    grade_nm: line.grade_nm,
    size_nm: line.size_nm,
  }
}

function draftFromStock(row: StockItem): ShipDraftLine {
  return {
    order_detail_id: null,
    item_cd: row.item_cd,
    variety_cd: row.variety_cd,
    grade_cd: row.grade_cd,
    size_cd: row.size_cd,
    weight: Number(row.weight) || 0,
    harvest_year: Number(row.harvest_year) || 0,
    wh_cd: row.wh_cd || DEFAULT_WAREHOUSE_CD,
    qty: Number(row.available_qty) || 0,
    unit_price: 0,
    remaining_qty: null,
    alloc_remaining: 0,
    variety_nm: row.variety_nm,
    grade_nm: row.grade_nm,
    size_nm: row.size_nm,
    item_nm: row.item_nm,
  }
}

/** 생산확정 → 판매 탭 prefill + Stage 6 출고 초안 */
export const useSalesPrefillStore = defineStore('salesPrefill', () => {
  const lines = ref<ProductionPrefillLine[]>([])
  const source = ref<'production' | ShipEntrySource | null>(null)
  const shipLines = ref<ShipDraftLine[]>([])
  const shipMode = ref<ShipMode>(SHIP_MODE_DIRECT)
  const orderNo = ref<string | null>(null)
  const custmId = ref<string | null>(null)
  const customerNm = ref('')
  const returnTo = ref<ShipReturnTo>('sales')
  const allowModeChange = ref(true)
  const lastResult = ref<ShipConfirmResponse | null>(null)
  const lastRemaining = ref<RemainingOrderLine[]>([])

  function setFromProduction(prefill: ProductionPrefillLine[]) {
    lines.value = prefill.map((ln) => ({ ...ln }))
    source.value = 'PRODUCTION'
    shipLines.value = prefill.map(draftFromProduction)
    shipMode.value = SHIP_MODE_DIRECT
    orderNo.value = null
    custmId.value = null
    customerNm.value = ''
    returnTo.value = 'sales'
    allowModeChange.value = true
    lastResult.value = null
  }

  function setFromOrder(detail: OrderDetail, line: OrderLine) {
    setFromOrderLines(detail, [line])
  }

  function setFromOrderLines(detail: OrderDetail, orderLines: OrderLine[]) {
    const drafts = orderLines.map(draftFromOrderLine)
    source.value = 'ORDER'
    lines.value = []
    shipLines.value = drafts
    orderNo.value = detail.order_no
    custmId.value = detail.custm_id
    customerNm.value = detail.customer || detail.custm_id
    const allStock = canUseStockMode(drafts)
    shipMode.value = defaultShipMode(allStock ? 1 : 0, true)
    returnTo.value = 'order-detail'
    allowModeChange.value = true
    lastResult.value = null
  }

  function setFromStock(row: StockItem) {
    setFromStockRows([row])
  }

  function setFromStockRows(rows: StockItem[]) {
    source.value = 'STOCK'
    lines.value = []
    shipLines.value = rows.map(draftFromStock)
    shipMode.value = SHIP_MODE_DIRECT
    orderNo.value = null
    custmId.value = null
    customerNm.value = ''
    returnTo.value = 'stock'
    allowModeChange.value = false
    lastResult.value = null
  }

  function consume(): ProductionPrefillLine[] {
    const v = lines.value.map((ln) => ({ ...ln }))
    lines.value = []
    if (source.value === 'production' || source.value === 'PRODUCTION') {
      source.value = null
    }
    return v
  }

  function rememberResult(res: ShipConfirmResponse) {
    lastResult.value = res
    lastRemaining.value = res.remaining_order || []
  }

  function remainingFor(orderDetailId: string): RemainingOrderLine | undefined {
    return lastRemaining.value.find((r) => r.order_detail_id === orderDetailId)
  }

  function clear() {
    lines.value = []
    source.value = null
    shipLines.value = []
    shipMode.value = SHIP_MODE_DIRECT
    orderNo.value = null
    custmId.value = null
    customerNm.value = ''
    returnTo.value = 'sales'
    allowModeChange.value = true
    lastResult.value = null
    lastRemaining.value = []
  }

  return {
    lines,
    source,
    shipLines,
    shipMode,
    orderNo,
    custmId,
    customerNm,
    returnTo,
    allowModeChange,
    lastResult,
    lastRemaining,
    setFromProduction,
    setFromOrder,
    setFromOrderLines,
    setFromStock,
    setFromStockRows,
    consume,
    rememberResult,
    remainingFor,
    clear,
  }
})
