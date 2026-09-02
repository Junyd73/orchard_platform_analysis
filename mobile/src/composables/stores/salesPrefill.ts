import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import type { ProductionPrefillLine } from '@/api/production'
import type { StockItem } from '@/api/stock'
import {
  SHIP_MODE_DIRECT,
  canUseStockMode,
  defaultShipMode,
  stockDraftKey,
  stockSaleSpecKey,
  DEFAULT_DIRECT_SALES_TYPE_CD,
  DEFAULT_DIRECT_SALES_CATEGORY_CD,
  type ShipDeliveryDraft,
  type ShipDraftLine,
  type ShipEntrySource,
} from '@/views/sales/shipConfirmModel'
import type { ShipMode } from '@/types/shipment'
import type { OrderDetail, OrderLine } from '@/types/order'
import {
  DEFAULT_WAREHOUSE_CD,
  DELIVERY_TP_VISIT,
  isParcelDelivery,
} from '@/views/orders/ordersConstants'
import { emptyDeliveryDraft, QTY_EPS } from '@/views/sales/shipDeliveryModel'
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

/**
 * 주문 배송지 → 출고 배송배분 seed.
 * 배송지별 remaining_qty만 사용하고, 합계는 상품 잔량(cap)을 넘지 않게 마지막 건을 잘라 담는다.
 */
function seedDeliveryAllocations(line: OrderLine, cap: number): ShipDeliveryDraft[] {
  const seeded: ShipDeliveryDraft[] = []
  let left = cap
  for (const d of line.deliveries || []) {
    if (left <= QTY_EPS) break
    const rest = Number(d.remaining_qty ?? 0)
    if (!(rest > QTY_EPS)) continue
    const qty = Math.min(rest, left)
    seeded.push(
      emptyDeliveryDraft({
        order_dlvry_id: d.order_dlvry_id,
        qty,
        rcv_name: d.rcv_name || '',
        rcv_tel: d.rcv_tel || '',
        rcv_addr: d.rcv_addr || '',
        dlvry_msg: d.dlvry_msg || '',
        ship_fee: 0,
      }),
    )
    left -= qty
  }
  return seeded
}

function draftFromOrderLine(line: OrderLine): ShipDraftLine {
  const alloc = Number(line.reserved_unshipped_qty ?? 0)
  const remaining = Number(line.remaining_order_qty ?? line.qty)
  const untracked = Number(line.untracked_delivery_shipped_qty ?? 0)
  const draft: ShipDraftLine = {
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
    dlvry_tp: line.dlvry_tp,
    untracked_delivery_shipped_qty: untracked,
  }
  // 추적 불가 출고이력이 있으면 배송지 매칭을 신뢰할 수 없어 사용자가 직접 지정한다.
  if (isParcelDelivery(line.dlvry_tp) && untracked <= QTY_EPS) {
    draft.delivery_allocations = seedDeliveryAllocations(line, remaining)
  }
  return draft
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
    // 판매 식별에 storage_dt 미사용 — OUT은 Core DIRECT FIFO
    storage_dt: '',
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
  /** 판매 전체 공통 — 보내는 사람 (택배) */
  const senderName = ref('')
  const senderTel = ref('')
  const senderAddr = ref('')

  /** S4A 직접판매 분류 (무주문만). 주문 출고는 사용하지 않음. */
  const salesTypeCd = ref(DEFAULT_DIRECT_SALES_TYPE_CD)
  const salesCategoryCd = ref(DEFAULT_DIRECT_SALES_CATEGORY_CD)

  function resetDirectSalesClassDefaults() {
    salesTypeCd.value = DEFAULT_DIRECT_SALES_TYPE_CD
    salesCategoryCd.value = DEFAULT_DIRECT_SALES_CATEGORY_CD
  }

  function clearDirectSalesClass() {
    salesTypeCd.value = ''
    salesCategoryCd.value = ''
  }

  const draftCount = computed(() => shipLines.value.length)
  /** STOCK 판매는 규격키, 그 외는 기존 draft key */
  const draftKeys = computed(
    () =>
      new Set(
        shipLines.value.map((ln) =>
          source.value === 'STOCK' ? stockSaleSpecKey(ln) : stockDraftKey(ln),
        ),
      ),
  )

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
    resetDirectSalesClassDefaults()
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
    clearDirectSalesClass()
    // 주문 line의 배송방식을 그대로 이어받는다(혼합 배송방식은 호출측에서 차단).
    const lineDlvryTp = String(orderLines[0]?.dlvry_tp || '').trim()
    if (lineDlvryTp) dlvryTp.value = lineDlvryTp
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
   * STOCK 판매 세션 여부.
   * shipLines 가 비어도 source===STOCK 이면 동일 세션으로 유지한다.
   */
  function isStockSaleSession(): boolean {
    return source.value === 'STOCK'
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
    resetDirectSalesClassDefaults()
  }

  /**
   * 재고 판매 세션 보장.
   * 이미 STOCK이면 헤더/라인/분류 유지. 다른 source에서 전환 시에만 초기화.
   */
  function ensureStockSaleSession() {
    if (isStockSaleSession()) {
      shipMode.value = SHIP_MODE_DIRECT
      orderNo.value = null
      returnTo.value = 'stock'
      allowModeChange.value = false
      lastResult.value = null
      return
    }
    source.value = 'STOCK'
    lines.value = []
    shipLines.value = []
    shipMode.value = SHIP_MODE_DIRECT
    orderNo.value = null
    returnTo.value = 'stock'
    allowModeChange.value = false
    lastResult.value = null
    resetStockSaleHeader()
    resetDirectSalesClassDefaults()
  }

  function getStockLine(key: string): ShipDraftLine | undefined {
    return shipLines.value.find((ln) => stockSaleSpecKey(ln) === key)
  }

  function hasStockLine(key: string): boolean {
    return Boolean(getStockLine(key))
  }

  function clampStockQty(qty: number, available: number): number {
    const max = Math.max(1, Math.floor(Number(available) || 0))
    const n = Math.floor(Number(qty))
    if (!Number.isFinite(n) || n < 1) return 1
    return Math.min(n, max)
  }

  /** 미등록 상품 담기. 동일 판매규격 중복 line 금지(있으면 qty만 갱신). */
  function addStockLine(row: StockItem, qty: number) {
    ensureStockSaleSession()
    const draft = draftFromStock(row)
    const key = stockSaleSpecKey(draft)
    const available = Number(row.available_qty) || 0
    draft.qty = clampStockQty(qty, available)
    draft.available_qty = available
    const idx = shipLines.value.findIndex((ln) => stockSaleSpecKey(ln) === key)
    if (idx >= 0) {
      shipLines.value = shipLines.value.map((ln, i) =>
        i === idx ? { ...ln, qty: draft.qty, available_qty: available } : ln,
      )
      return
    }
    shipLines.value = [...shipLines.value, draft]
  }

  function updateStockLineQty(key: string, qty: number) {
    const idx = shipLines.value.findIndex((ln) => stockSaleSpecKey(ln) === key)
    if (idx < 0) return
    const cur = shipLines.value[idx]
    const available = cur.available_qty != null ? Number(cur.available_qty) : Number(qty)
    const nextQty = clampStockQty(qty, available > 0 ? available : qty)
    shipLines.value = shipLines.value.map((ln, i) =>
      i === idx ? { ...ln, qty: nextQty } : ln,
    )
  }

  /** 경매 확인 직전 — available_qty 스냅샷만 갱신(qty·규격 유지) */
  function applyStockLineAvailability(refreshedLines: ShipDraftLine[]) {
    if (source.value !== 'STOCK' || !refreshedLines.length) return
    const byKey = new Map(refreshedLines.map((ln) => [stockSaleSpecKey(ln), ln]))
    shipLines.value = shipLines.value.map((ln) => {
      const next = byKey.get(stockSaleSpecKey(ln))
      if (!next) return ln
      return { ...ln, available_qty: next.available_qty }
    })
  }

  function removeStockLineByKey(key: string) {
    shipLines.value = shipLines.value.filter((ln) => stockSaleSpecKey(ln) !== key)
  }

  const stockDraftTotalQty = computed(() =>
    source.value === 'STOCK'
      ? shipLines.value.reduce((s, ln) => s + Number(ln.qty || 0), 0)
      : 0,
  )

  /** 동일 판매규격 중복 line 금지, 기존 qty 유지. 신규만 추가(호환용). */
  function mergeFromStockRows(rows: StockItem[]) {
    ensureStockSaleSession()
    const next = [...shipLines.value]
    const seen = new Set(next.map((ln) => stockSaleSpecKey(ln)))
    for (const row of rows) {
      const draft = draftFromStock(row)
      const key = stockSaleSpecKey(draft)
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
    patch: Partial<Pick<ShipDraftLine, 'qty' | 'unit_price' | 'delivery_allocations'>>,
  ) {
    const cur = shipLines.value[index]
    if (!cur) return
    const next = { ...cur, ...patch }
    shipLines.value = shipLines.value.map((ln, i) => (i === index ? next : ln))
  }

  /** 수량 변경 시 allocations는 유지(자동 축소/삭제 금지). */
  function setShipLineDeliveries(index: number, allocations: ShipDraftLine['delivery_allocations']) {
    updateShipLine(index, { delivery_allocations: allocations })
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

  function setSender(input: { name?: string; tel?: string; addr?: string }) {
    if (input.name != null) senderName.value = String(input.name || '').trim()
    if (input.tel != null) senderTel.value = String(input.tel || '').trim()
    if (input.addr != null) senderAddr.value = String(input.addr || '').trim()
  }

  function resetDelivery() {
    dlvryTp.value = DELIVERY_TP_VISIT
    shipFee.value = 0
    rcvName.value = ''
    rcvTel.value = ''
    rcvAddr.value = ''
    dlvryMsg.value = ''
    senderName.value = ''
    senderTel.value = ''
    senderAddr.value = ''
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
    clearDirectSalesClass()
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
    senderName,
    senderTel,
    senderAddr,
    salesTypeCd,
    salesCategoryCd,
    draftCount,
    draftKeys,
    stockDraftTotalQty,
    setFromProduction,
    setFromOrder,
    setFromOrderLines,
    setFromStock,
    setFromStockRows,
    mergeFromStockRows,
    ensureStockSaleSession,
    getStockLine,
    hasStockLine,
    addStockLine,
    updateStockLineQty,
    applyStockLineAvailability,
    removeStockLineByKey,
    removeShipLine,
    updateShipLine,
    setShipLineDeliveries,
    setCustomer,
    setDelivery,
    setSender,
    resetDelivery,
    consume,
    rememberResult,
    remainingFor,
    clear,
    hasDraftKey,
    isStockSaleSession,
  }
})
