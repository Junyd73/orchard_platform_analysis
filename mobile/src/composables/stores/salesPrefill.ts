import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import type { ProductionPrefillLine } from '@/api/production'
import type { StockItem } from '@/api/stock'
import {
  SHIP_MODE_DIRECT,
  canUseStockMode,
  defaultShipMode,
  stockDraftKey,
  type ShipDraftLine,
  type ShipEntrySource,
} from '@/views/sales/shipConfirmModel'
import type { ShipMode } from '@/types/shipment'
import type { OrderDetail, OrderLine } from '@/types/order'
import {
  DEFAULT_WAREHOUSE_CD,
  DELIVERY_TP_VISIT,
} from '@/views/orders/ordersConstants'
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
  const available = Number(row.available_qty) || 0
  return {
    order_detail_id: null,
    item_cd: row.item_cd,
    variety_cd: row.variety_cd,
    grade_cd: row.grade_cd,
    size_cd: row.size_cd,
    weight: Number(row.weight) || 0,
    harvest_year: Number(row.harvest_year) || 0,
    wh_cd: row.wh_cd || DEFAULT_WAREHOUSE_CD,
    storage_dt: row.storage_dt || '',
    available_qty: available,
    qty: available > 0 ? 1 : 0,
    unit_price: 0,
    remaining_qty: null,
    alloc_remaining: 0,
    variety_nm: row.variety_nm,
    grade_nm: row.grade_nm,
    size_nm: row.size_nm,
    item_nm: row.item_nm,
  }
}

/** 생산확정 → 판매 탭 prefill + Stage 6 출고 초안 + Stage2 판매 draft */
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

  /** 판매 미리보기 공통 헤더 (1고객·1배송) */
  const dlvryTp = ref(DELIVERY_TP_VISIT)
  const shipFee = ref(0)
  const rcvName = ref('')
  const rcvTel = ref('')
  const rcvAddr = ref('')
  const dlvryMsg = ref('')

  const draftCount = computed(() => shipLines.value.length)
  const draftKeys = computed(() => new Set(shipLines.value.map((ln) => stockDraftKey(ln))))

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
    resetDelivery()
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
    resetDelivery()
  }

  function setFromStock(row: StockItem) {
    setFromStockRows([row])
  }

  /** 재고 직접판매 헤더(고객·배송) 초기화 — 최초 STOCK 진입용 */
  function resetStockSaleHeader() {
    custmId.value = null
    customerNm.value = ''
    resetDelivery()
  }

  /**
   * 신규 STOCK 판매 시작 여부.
   * 이미 STOCK + shipLines 가 있으면 품목추가(헤더 유지), 그 외는 최초 진입.
   */
  function isContinuingStockSale(): boolean {
    return source.value === 'STOCK' && shipLines.value.length > 0
  }

  /** 재고 선택으로 draft를 교체(기존 동작). 항상 신규 판매 시작으로 취급. */
  function setFromStockRows(rows: StockItem[]) {
    source.value = 'STOCK'
    lines.value = []
    shipLines.value = rows.map(draftFromStock)
    shipMode.value = SHIP_MODE_DIRECT
    orderNo.value = null
    returnTo.value = 'stock'
    allowModeChange.value = false
    lastResult.value = null
    resetStockSaleHeader()
  }

  /**
   * 판매미리보기용 병합: 동일 stock 중복 line 금지, 기존 qty/단가 유지.
   * 신규만 추가한다.
   * 최초 STOCK 진입 시 고객/배송 초기화, 품목추가 병합 시 헤더 유지.
   */
  function mergeFromStockRows(rows: StockItem[]) {
    const keepHeader = isContinuingStockSale()
    source.value = 'STOCK'
    lines.value = []
    shipMode.value = SHIP_MODE_DIRECT
    orderNo.value = null
    returnTo.value = 'stock'
    allowModeChange.value = false
    lastResult.value = null
    if (!keepHeader) {
      resetStockSaleHeader()
      // 주문/생산 draft 잔여 line 제거 — 신규 재고판매만 시작
      shipLines.value = []
    }

    const next = [...shipLines.value]
    const seen = new Set(next.map((ln) => stockDraftKey(ln)))
    for (const row of rows) {
      const draft = draftFromStock(row)
      const key = stockDraftKey(draft)
      if (seen.has(key)) continue
      seen.add(key)
      next.push(draft)
    }
    shipLines.value = next
  }

  function removeShipLine(index: number) {
    if (index < 0 || index >= shipLines.value.length) return
    shipLines.value = shipLines.value.filter((_, i) => i !== index)
  }

  function updateShipLine(
    index: number,
    patch: Partial<Pick<ShipDraftLine, 'qty' | 'unit_price'>>,
  ) {
    const cur = shipLines.value[index]
    if (!cur) return
    const next = { ...cur, ...patch }
    shipLines.value = shipLines.value.map((ln, i) => (i === index ? next : ln))
  }

  function setCustomer(id: string | null, name = '') {
    custmId.value = id
    customerNm.value = name
  }

  function setDelivery(input: {
    dlvryTp?: string
    shipFee?: number
    rcvName?: string
    rcvTel?: string
    rcvAddr?: string
    dlvryMsg?: string
  }) {
    if (input.dlvryTp != null) dlvryTp.value = input.dlvryTp
    if (input.shipFee != null) shipFee.value = Number(input.shipFee) || 0
    if (input.rcvName != null) rcvName.value = input.rcvName
    if (input.rcvTel != null) rcvTel.value = input.rcvTel
    if (input.rcvAddr != null) rcvAddr.value = input.rcvAddr
    if (input.dlvryMsg != null) dlvryMsg.value = input.dlvryMsg
  }

  function resetDelivery() {
    dlvryTp.value = DELIVERY_TP_VISIT
    shipFee.value = 0
    rcvName.value = ''
    rcvTel.value = ''
    rcvAddr.value = ''
    dlvryMsg.value = ''
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
    resetDelivery()
  }

  function hasDraftKey(key: string): boolean {
    return draftKeys.value.has(key)
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
    dlvryTp,
    shipFee,
    rcvName,
    rcvTel,
    rcvAddr,
    dlvryMsg,
    draftCount,
    draftKeys,
    setFromProduction,
    setFromOrder,
    setFromOrderLines,
    setFromStock,
    setFromStockRows,
    mergeFromStockRows,
    removeShipLine,
    updateShipLine,
    setCustomer,
    setDelivery,
    resetDelivery,
    consume,
    rememberResult,
    remainingFor,
    clear,
    hasDraftKey,
  }
})
