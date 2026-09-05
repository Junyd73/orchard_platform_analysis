<script setup lang="ts">
import { computed, inject, ref, unref, watch, type Ref } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'

import { listFruitStock, listStockLogs, adjustStock, adjustStockBySpec } from '@/api/stock'
import type { StockItem, StockLog } from '@/api/stock'
import { fetchCommonCodes } from '@/api/commonCodes'
import { ApiClientError } from '@/api/client'
import iconChevronDown from '@/assets/ods/common/icon-chevron-down.svg'
import OdsButton from '@/components/ods/OdsButton.vue'
import OdsCard from '@/components/ods/OdsCard.vue'
import OdsInput from '@/components/ods/OdsInput.vue'
import OdsSelect from '@/components/ods/OdsSelect.vue'
import { useAppStore } from '@/composables/stores/app'
import { useSalesPrefillStore } from '@/composables/stores/salesPrefill'
import { stockSaleSpecKey } from '@/views/sales/shipConfirmModel'
import {
  buildStockListEntries,
  filterStockEntriesByAvailable,
  type StockListEntry,
} from '@/views/stock/stockSaleList'
import {
  ADJUST_REASON_OPTIONS,
  PARENT_ADJUST_REASON,
  REASON_DISPOSE,
  reasonAllowsIn,
  reasonAllowsOut,
} from '@/views/stock/stockAdjustConstants'
import { cancelAuctionShipment, listAuctionShipments } from '@/api/auctionShipments'
import type { AuctionShipmentListItem } from '@/types/auctionShipment'
import AuctionShipConfirmSheet from '@/views/stock/AuctionShipConfirmSheet.vue'
import AuctionMatchSheet from '@/views/stock/AuctionMatchSheet.vue'
import AuctionReopenConfirmSheet from '@/views/stock/AuctionReopenConfirmSheet.vue'
import {
  auctionShipmentStatusLabel,
  AUCTION_STATUS_CANCELLED,
  AUCTION_STATUS_COMPLETED,
  AUCTION_STATUS_FILTER_ALL,
  AUCTION_STATUS_FILTER_DEFAULT,
  AUCTION_STATUS_FILTER_OPTIONS,
  AUCTION_STATUS_IN_TRANSIT,
  filterShipmentsByStatus,
  isAuctionCancelAllowed,
  isAuctionMatchFetchAllowed,
  isAuctionReopenAllowed,
  MSG_AUCTION_SHIP_OK,
  MSG_AUCTION_STOCK_REFRESH_FAIL,
  refreshAuctionShipLines,
} from '@/views/stock/auctionShipModel'
import {
  auctionMatchUserMessage,
  formatWon,
  isStatusConflictError,
  filterShipmentsByYearMonth,
  formatShipmentYearMonthLabel,
  mergeShipmentLists,
  MSG_AUCTION_CANCEL_CONFIRM,
  MSG_AUCTION_CANCEL_OK,
  MSG_AUCTION_REOPEN_NOT_FOUND,
  MSG_AUCTION_REOPEN_OK,
  MSG_AUCTION_REOPEN_STATUS,
  sortAuctionShipments,
  uniqueShipmentYearMonths,
} from '@/views/stock/auctionMatchModel'

// ── item_cd 상수 (core/stock_constants.py 일치) ──────────────────────
const ITEM_PRODUCT = 'FR010100'
const ITEM_RAW     = 'FR010300'
const STOCK_TAB_JUICE = 'JUICE'
const JUICE_STOCK_CDS = ['FR010200', 'FR010202', 'FR010201'] as const
const JUICE_LABEL: Record<string, string> = {
  FR010202: '일반배즙',
  FR010201: '도라지배즙',
  FR010200: '배즙',
}

const STOCK_TYPES = [
  { value: ITEM_PRODUCT, label: '상품'  },
  { value: ITEM_RAW,     label: '원물'  },
  { value: STOCK_TAB_JUICE, label: '배즙'  },
] as const

// ── store ────────────────────────────────────────────────────────────
const { farmCd } = storeToRefs(useAppStore())
const router = useRouter()
const salesPrefill = useSalesPrefillStore()

// ── 상태 ─────────────────────────────────────────────────────────────
const stockType   = ref(ITEM_PRODUCT)
const includeZero = ref(false)
const loading     = ref(false)
const loadError   = ref('')
const rows        = ref<StockItem[]>([])

/** 조회 조건 (리스트박스 초안) / 적용값 — 빈 문자열 = 전체 */
const FILTER_ALL = ''
const draftVariety = ref(FILTER_ALL)
const draftWeight = ref(FILTER_ALL)
const draftSize = ref(FILTER_ALL)
const draftGrade = ref(FILTER_ALL)
const appliedVariety = ref(FILTER_ALL)
const appliedWeight = ref(FILTER_ALL)
const appliedSize = ref(FILTER_ALL)
const appliedGrade = ref(FILTER_ALL)

// 이력 모달
const logTarget    = ref<StockItem | null>(null)
/** 조정 중인 목록 엔트리(집계 row + sources). 날짜 LOT 선택 UI 없음. */
const adjustEntry  = ref<StockListEntry | null>(null)
const logs         = ref<StockLog[]>([])
const logsLoading  = ref(false)
const logsError    = ref('')
const historyOpen  = ref(false) // 조정 시트 open 시 이력 자동 조회를 하지 않습니다.
const historyLoaded = ref(false) // 최초 펼침 1회만 listStockLogs 호출
/** 미담기/수정 전 행 수량(키 → qty). Store 반영 전 로컬 초안 */
const rowQtyByKey = ref<Record<string, number>>({})
const adjustQty = ref('1')
const adjustReason = ref(REASON_DISPOSE)
const adjustDirection = ref<'IN' | 'OUT'>('OUT')
const adjustBusy = ref(false)
const adjustError = ref('')
/** 시트 닫힌 뒤 메인 화면에서 보이는 성공 안내 */
const pageSuccess = ref('')
const adjustReasons = ref<{ value: string; label: string }[]>(
  ADJUST_REASON_OPTIONS.map((r) => ({ value: r.value, label: r.label })),
)
const canAdjustIn = computed(() => reasonAllowsIn(adjustReason.value))
const canAdjustOut = computed(() => reasonAllowsOut(adjustReason.value))

const adjustQtyNum = computed(() => {
  const n = Number(adjustQty.value)
  return Number.isFinite(n) ? n : NaN
})
const adjustDirNm = computed(() => (adjustDirection.value === 'IN' ? '증가' : '감소'))
const adjustReasonLabel = computed(
  () => adjustReasons.value.find((r) => r.value === adjustReason.value)?.label || adjustReason.value,
)

/** 사유에 맞게 미리보기/실행 방향을 즉시 정합 */
function syncDirectionForReason() {
  const allowIn = reasonAllowsIn(adjustReason.value)
  const allowOut = reasonAllowsOut(adjustReason.value)
  if (allowOut && !allowIn) {
    adjustDirection.value = 'OUT'
    return
  }
  if (allowIn && !allowOut) {
    adjustDirection.value = 'IN'
    return
  }
  // 실사차이/기타: 현재 방향이 유효하면 유지, 아니면 OUT 기본
  if (adjustDirection.value !== 'IN' && adjustDirection.value !== 'OUT') {
    adjustDirection.value = 'OUT'
  }
}

const previewWarnOut = computed(() => {
  if (!logTarget.value) return false
  if (adjustDirection.value !== 'OUT') return false
  if (!(adjustQtyNum.value >= 1)) return false
  return adjustQtyNum.value > logTarget.value.available_qty + 1e-9
})

const hasValidAdjustQty = computed(() => Number.isFinite(adjustQtyNum.value) && adjustQtyNum.value >= 1)

const previewAfterQty = computed(() => {
  if (!logTarget.value) return 0
  const curr = Number(logTarget.value.real_qty || 0)
  const qty = hasValidAdjustQty.value ? adjustQtyNum.value : 0
  return adjustDirection.value === 'IN' ? curr + qty : curr - qty
})

const previewText = computed(() => {
  if (!logTarget.value) return ''
  if (!hasValidAdjustQty.value) return '조정 수량은 1 이상 입력해 주세요.'
  const unit = stockUnit(logTarget.value.item_cd)
  const qty = adjustQtyNum.value
  const warn = previewWarnOut.value ? '\n(가용재고 초과)' : ''
  return `${adjustReasonLabel.value} · ${qty}${unit} ${adjustDirNm.value}\n현재 ${logTarget.value.real_qty}${unit} → 조정 후 ${previewAfterQty.value}${unit}${warn}`
})

watch(adjustReason, () => {
  syncDirectionForReason()
  adjustError.value = ''
})

// ── computed ─────────────────────────────────────────────────────────
const isRaw = computed(() => stockType.value === ITEM_RAW)

type FilterOption = { value: string; label: string }

function uniqOptions(
  items: StockItem[],
  pick: (r: StockItem) => { value: string; label: string },
): FilterOption[] {
  const map = new Map<string, string>()
  for (const r of items) {
    const { value, label } = pick(r)
    if (!value || map.has(value)) continue
    map.set(value, label || value)
  }
  return [...map.entries()]
    .map(([value, label]) => ({ value, label }))
    .sort((a, b) => a.label.localeCompare(b.label, 'ko'))
}

const varietyOptions = computed(() =>
  uniqOptions(rows.value, (r) => ({
    value: r.variety_cd,
    label: r.variety_nm || r.variety_cd,
  })),
)
const weightOptions = computed(() =>
  uniqOptions(rows.value, (r) => ({
    value: String(r.weight),
    label: r.weight > 0 ? `${r.weight}kg` : String(r.weight),
  })),
)
const sizeOptions = computed(() =>
  uniqOptions(rows.value, (r) => ({
    value: r.size_cd,
    label: r.size_nm || r.size_cd,
  })),
)
const gradeOptions = computed(() =>
  uniqOptions(rows.value, (r) => ({
    value: r.grade_cd,
    label: r.grade_nm || r.grade_cd,
  })),
)

const listEntries = computed(() =>
  buildStockListEntries(rows.value, { raw: isRaw.value }),
)

const filteredEntries = computed(() => {
  let entries = filterStockEntriesByAvailable(listEntries.value, includeZero.value)
  const v = appliedVariety.value
  const w = appliedWeight.value
  const s = appliedSize.value
  const g = appliedGrade.value
  if (!v && !w && !s && !g) return entries
  return entries.filter((entry) => {
    const row = entry.row
    if (v && row.variety_cd !== v) return false
    if (w && String(row.weight) !== w) return false
    if (s && row.size_cd !== s) return false
    if (g && row.grade_cd !== g) return false
    return true
  })
})

function resetQueryFilters() {
  draftVariety.value = FILTER_ALL
  draftWeight.value = FILTER_ALL
  draftSize.value = FILTER_ALL
  draftGrade.value = FILTER_ALL
  appliedVariety.value = FILTER_ALL
  appliedWeight.value = FILTER_ALL
  appliedSize.value = FILTER_ALL
  appliedGrade.value = FILTER_ALL
}

function applyQuerySearch() {
  appliedVariety.value = draftVariety.value
  appliedWeight.value = draftWeight.value
  appliedSize.value = draftSize.value
  appliedGrade.value = draftGrade.value
}

// ── 데이터 로드 ───────────────────────────────────────────────────────
async function load() {
  if (!farmCd.value) return
  loading.value  = true
  loadError.value = ''
  try {
    if (stockType.value === STOCK_TAB_JUICE) {
      const groups = await Promise.all(
        JUICE_STOCK_CDS.map((item_cd) =>
          listFruitStock(farmCd.value, {
            item_cd,
            include_zero: includeZero.value,
          }),
        ),
      )
      rows.value = groups.flat()
    } else {
      rows.value = await listFruitStock(farmCd.value, {
        item_cd: stockType.value,
        include_zero: includeZero.value,
      })
    }
  } catch {
    loadError.value = '재고를 불러오지 못했습니다.'
  } finally {
    loading.value = false
  }
}

watch([includeZero, farmCd], load, { immediate: true })
watch(stockType, () => {
  resetQueryFilters()
  void load()
})

async function loadAdjustReasons() {
  try {
    const allowed = new Set<string>(ADJUST_REASON_OPTIONS.map((r) => r.value))
    const codes = await fetchCommonCodes(farmCd.value, PARENT_ADJUST_REASON)
    const mapped = codes
      .filter((c) => allowed.has(c.code_cd))
      .map((c) => ({ value: c.code_cd, label: c.code_nm || c.code_cd }))
    if (mapped.length) {
      adjustReasons.value = mapped
      if (!adjustReasons.value.some((r) => r.value === adjustReason.value)) {
        adjustReason.value = adjustReasons.value[0].value
      }
    }
  } catch {
    /* 로컬 기본 사유 코드 유지 */
  }
}

async function openAdjustSheet(entry: StockListEntry) {
  // 조정 시트 진입 시에는 이력 API(listStockLogs)를 자동 호출하지 않습니다.
  adjustEntry.value = entry
  logTarget.value = entry.row
  logs.value = []
  logsError.value = ''
  logsLoading.value = false
  historyOpen.value = false
  historyLoaded.value = false

  adjustError.value = ''
  pageSuccess.value = ''
  adjustQty.value = '1'
  adjustReason.value = REASON_DISPOSE
  syncDirectionForReason()

  await loadAdjustReasons()
  syncDirectionForReason()
}

/** 행 클릭 → 재고조정 (날짜/LOT 선택 단계 없음) */
function onListRowClick(entry: StockListEntry) {
  void openAdjustSheet(entry)
}

async function openHistoryLogs() {
  if (!logTarget.value) return
  if (logsLoading.value) return

  // 이미 펼쳐서 조회한 적이 있으면 재호출하지 않습니다.
  historyOpen.value = true
  if (historyLoaded.value) return

  logsLoading.value = true
  logsError.value = ''
  logs.value = []
  try {
    const item = logTarget.value
    // storage_dt 필터 없음 — 규격 단위 이력 (t_stock_log에 storage_dt 컬럼 없음)
    logs.value = await listStockLogs(farmCd.value, {
      item_cd: item.item_cd,
      variety_cd: item.variety_cd,
      grade_cd: item.grade_cd,
      size_cd: item.size_cd,
      weight: item.weight,
      harvest_year: item.harvest_year,
    })
  } catch {
    logsError.value = '이력을 불러오지 못했습니다.'
  } finally {
    logsLoading.value = false
    historyLoaded.value = true
  }
}

function closeHistoryAccordion() {
  historyOpen.value = false
}

function saleKey(row: StockItem): string {
  return stockSaleSpecKey(row)
}

function isSellable(row: StockItem): boolean {
  return row.item_cd !== ITEM_RAW && row.available_qty > 0
}

function isInCart(row: StockItem): boolean {
  return salesPrefill.source === 'STOCK' && salesPrefill.hasStockLine(saleKey(row))
}

function maxQty(row: StockItem): number {
  return Math.max(1, Math.floor(Number(row.available_qty) || 0))
}

function clampRowQty(row: StockItem, qty: number): number {
  const max = maxQty(row)
  const n = Math.floor(Number(qty))
  if (!Number.isFinite(n) || n < 1) return 1
  return Math.min(n, max)
}

/** 행에 표시하는 수량: 로컬 초안 > Store(담김) > 1 */
function displayQty(row: StockItem): number {
  const key = saleKey(row)
  if (Object.prototype.hasOwnProperty.call(rowQtyByKey.value, key)) {
    return clampRowQty(row, rowQtyByKey.value[key])
  }
  if (isInCart(row)) {
    const ln = salesPrefill.getStockLine(key)
    return clampRowQty(row, Number(ln?.qty) || 1)
  }
  return 1
}

function setDisplayQty(row: StockItem, qty: number) {
  const key = saleKey(row)
  rowQtyByKey.value = { ...rowQtyByKey.value, [key]: clampRowQty(row, qty) }
}

function bumpQty(row: StockItem, delta: number) {
  setDisplayQty(row, displayQty(row) + delta)
}

function onQtyInput(row: StockItem, raw: string | number) {
  setDisplayQty(row, Number(raw))
}

function clearLocalQty(key: string) {
  if (!Object.prototype.hasOwnProperty.call(rowQtyByKey.value, key)) return
  const next = { ...rowQtyByKey.value }
  delete next[key]
  rowQtyByKey.value = next
}

function addToCart(row: StockItem) {
  if (!isSellable(row)) return
  const key = saleKey(row)
  const qty = displayQty(row)
  salesPrefill.addStockLine(row, qty)
  clearLocalQty(key)
}

function updateCartQty(row: StockItem) {
  if (!isInCart(row)) return
  const key = saleKey(row)
  salesPrefill.updateStockLineQty(key, displayQty(row))
  clearLocalQty(key)
}

function removeFromCart(row: StockItem) {
  const key = saleKey(row)
  salesPrefill.removeStockLineByKey(key)
  rowQtyByKey.value = { ...rowQtyByKey.value, [key]: 1 }
}

/** Store에 이미 담긴 shipLines만 미리보기 — merge 없음 */
function openSalesPreview() {
  if (salesPrefill.source !== 'STOCK' || !salesPrefill.shipLines.length) return
  void router.push({ name: 'sales-preview' })
}

const auctionSheetOpen = ref(false)
const auctionOpening = ref(false)
const auctionRefreshError = ref('')
const transitOpen = ref(false)
const transitLoading = ref(false)
const transitError = ref('')
const transitShipments = ref<AuctionShipmentListItem[]>([])
const transitYearMonth = ref('')
const transitMonthOptions = computed(() =>
  uniqueShipmentYearMonths(transitShipments.value).map((yearMonth) => ({
    value: yearMonth,
    label: formatShipmentYearMonthLabel(yearMonth),
  })),
)
const transitStatus = ref(AUCTION_STATUS_FILTER_DEFAULT)
const filteredTransitShipments = computed(() =>
  filterShipmentsByStatus(
    filterShipmentsByYearMonth(transitShipments.value, transitYearMonth.value),
    transitStatus.value,
  ),
)
/** 출하중 목록은 접힘 기본 · 한 번에 1건만 확장 */
const expandedShipmentId = ref('')
watch(transitShipments, (items) => {
  expandedShipmentId.value = ''
  // 선택 상태에 건이 없으면 빈 목록 대신 전체로 보정 (년월 필터와 동일한 방식)
  if (
    transitStatus.value !== AUCTION_STATUS_FILTER_ALL &&
    !filterShipmentsByStatus(items, transitStatus.value).length
  ) {
    transitStatus.value = AUCTION_STATUS_FILTER_ALL
  }
  const months = uniqueShipmentYearMonths(items)
  if (!months.length) {
    transitYearMonth.value = ''
    return
  }
  if (!months.includes(transitYearMonth.value)) {
    transitYearMonth.value = months[0]
  }
})
watch([transitYearMonth, transitStatus], () => {
  expandedShipmentId.value = ''
})

function isTransitCancelled(ship: AuctionShipmentListItem): boolean {
  return ship.status === AUCTION_STATUS_CANCELLED
}

function isTransitExpanded(ship: AuctionShipmentListItem): boolean {
  return expandedShipmentId.value === ship.shipment_id
}

function toggleTransitExpand(ship: AuctionShipmentListItem) {
  if (isTransitCancelled(ship)) return
  expandedShipmentId.value = isTransitExpanded(ship) ? '' : ship.shipment_id
}

function transitActionsId(ship: AuctionShipmentListItem): string {
  return `auction-transit-actions-${ship.shipment_id}`
}

/** 취소건은 read-only div, 그 외는 aria-expanded toggle button */
function transitInfoAttrs(ship: AuctionShipmentListItem): Record<string, unknown> {
  if (isTransitCancelled(ship)) return {}
  const expanded = isTransitExpanded(ship)
  return {
    type: 'button',
    'aria-expanded': String(expanded),
    'aria-controls': expanded ? transitActionsId(ship) : undefined,
    'data-testid': 'auction-transit-item-toggle',
  }
}
const transitCancelBusy = ref(false)
const matchSheetOpen = ref(false)
const matchShipmentId = ref('')
const reopenSheetOpen = ref(false)
const reopenShipmentId = ref('')

function closeAuctionSheet() {
  auctionSheetOpen.value = false
}

async function syncAuctionCartFromLatestStock(): Promise<boolean> {
  if (!farmCd.value || salesPrefill.source !== 'STOCK' || !salesPrefill.shipLines.length) {
    return false
  }
  const latest = await listFruitStock(farmCd.value, {
    item_cd: ITEM_PRODUCT,
    include_zero: includeZero.value,
  })
  const { lines } = refreshAuctionShipLines(salesPrefill.shipLines, latest)
  salesPrefill.applyStockLineAvailability(lines)
  if (stockType.value === ITEM_PRODUCT) {
    rows.value = latest
  }
  return true
}

async function openAuctionSheet() {
  if (!canAuctionShip.value || auctionOpening.value) return
  auctionOpening.value = true
  auctionRefreshError.value = ''
  try {
    await syncAuctionCartFromLatestStock()
    auctionSheetOpen.value = true
  } catch {
    auctionRefreshError.value = MSG_AUCTION_STOCK_REFRESH_FAIL
  } finally {
    auctionOpening.value = false
  }
}

function clearStockSelection() {
  if (salesPrefill.source !== 'STOCK') return
  const keys = salesPrefill.shipLines.map((ln) => stockSaleSpecKey(ln))
  for (const key of keys) {
    salesPrefill.removeStockLineByKey(key)
  }
  rowQtyByKey.value = {}
}

async function loadTransitShipments() {
  if (!farmCd.value) return
  transitLoading.value = true
  transitError.value = ''
  try {
    const pages = await Promise.all([
      listAuctionShipments(farmCd.value, { status: AUCTION_STATUS_IN_TRANSIT }),
      listAuctionShipments(farmCd.value, { status: AUCTION_STATUS_COMPLETED }),
      listAuctionShipments(farmCd.value, { status: AUCTION_STATUS_CANCELLED }),
    ])
    transitShipments.value = sortAuctionShipments(mergeShipmentLists(pages))
  } catch {
    transitShipments.value = []
    transitError.value = '경매출하 목록을 불러오지 못했습니다.'
  } finally {
    transitLoading.value = false
  }
}

function openAuctionMatch(ship: AuctionShipmentListItem) {
  if (!isAuctionMatchFetchAllowed(ship) || transitCancelBusy.value || reopenSheetOpen.value) return
  matchShipmentId.value = ship.shipment_id
  matchSheetOpen.value = true
}

function closeAuctionMatch() {
  matchSheetOpen.value = false
  matchShipmentId.value = ''
}

function openAuctionReopen(ship: AuctionShipmentListItem) {
  if (!isAuctionReopenAllowed(ship) || transitCancelBusy.value || reopenSheetOpen.value) return
  reopenShipmentId.value = ship.shipment_id
  reopenSheetOpen.value = true
}

function closeAuctionReopen() {
  reopenSheetOpen.value = false
  reopenShipmentId.value = ''
}

function onAuctionReopenSuccess() {
  reopenSheetOpen.value = false
  reopenShipmentId.value = ''
  closeAuctionMatch()
  pageSuccess.value = MSG_AUCTION_REOPEN_OK
  void load()
  void loadTransitShipments()
}

function onAuctionReopenSettled() {
  void loadTransitShipments()
}

function onAuctionReopenStatusConflict() {
  transitError.value = MSG_AUCTION_REOPEN_STATUS
}

function onAuctionReopenNotFound() {
  closeAuctionMatch()
  transitError.value = MSG_AUCTION_REOPEN_NOT_FOUND
}

function onAuctionMatchSuccess() {
  void load()
  void loadTransitShipments()
}

function onAuctionMatchStatusConflict() {
  pageSuccess.value = ''
  closeAuctionMatch()
  void load()
  void loadTransitShipments()
}

async function cancelTransitShipment(ship: AuctionShipmentListItem) {
  if (
    !isAuctionCancelAllowed(ship)
    || transitCancelBusy.value
    || reopenSheetOpen.value
    || !farmCd.value
  ) return
  if (!window.confirm(MSG_AUCTION_CANCEL_CONFIRM)) return
  transitCancelBusy.value = true
  transitError.value = ''
  try {
    await cancelAuctionShipment(farmCd.value, ship.shipment_id)
    pageSuccess.value = MSG_AUCTION_CANCEL_OK
    void load()
    void loadTransitShipments()
  } catch (err) {
    transitError.value = auctionMatchUserMessage(err)
    if (isStatusConflictError(err)) {
      void loadTransitShipments()
    }
  } finally {
    transitCancelBusy.value = false
  }
}

function onAuctionShipSuccess() {
  pageSuccess.value = MSG_AUCTION_SHIP_OK
  clearStockSelection()
  void load()
  void loadTransitShipments()
}

function onAuctionQtyUnavailable() {
  void (async () => {
    try {
      await syncAuctionCartFromLatestStock()
    } catch {
      await load()
    }
  })()
}

watch(farmCd, () => {
  void loadTransitShipments()
}, { immediate: true })

async function requestAdjust(ioType: 'IN' | 'OUT') {
  const row = logTarget.value
  const entry = adjustEntry.value
  if (!row || !entry || adjustBusy.value) return

  adjustDirection.value = ioType
  adjustError.value = ''
  pageSuccess.value = ''

  const qty = adjustQtyNum.value
  if (!Number.isFinite(qty) || qty < 1) {
    adjustError.value = '조정 수량은 1 이상 입력해 주세요.'
    return
  }

  if ((ioType === 'IN' && !canAdjustIn.value) || (ioType === 'OUT' && !canAdjustOut.value)) {
    adjustError.value = '이 사유로는 선택한 조정을 할 수 없습니다.'
    return
  }

  if (ioType === 'OUT' && qty > row.available_qty + 1e-9) {
    adjustError.value = '가용재고보다 많이 줄일 수 없습니다.'
    return
  }

  const unit = stockUnit(row.item_cd)
  const dirNm = ioType === 'IN' ? '증가' : '감소'
  const after = ioType === 'IN' ? Number(row.real_qty) + qty : Number(row.real_qty) - qty
  const confirmMsg =
    `${adjustReasonLabel.value} 사유로 ${qty}${unit}를 ${dirNm}하시겠습니까?\n\n` +
    `현재 ${row.real_qty}${unit} → 조정 후 ${after}${unit}`
  if (!window.confirm(confirmMsg)) return

  adjustBusy.value = true
  try {
    const isRaw = row.item_cd === ITEM_RAW
    if (isRaw) {
      const src = entry.sources[0] || row
      await adjustStock(farmCd.value, {
        wh_cd: src.wh_cd,
        item_cd: src.item_cd,
        variety_cd: src.variety_cd,
        grade_cd: src.grade_cd,
        size_cd: src.size_cd,
        weight: src.weight,
        harvest_year: src.harvest_year,
        storage_dt: src.storage_dt,
        io_type: ioType,
        qty,
        reason_cd: adjustReason.value,
      })
    } else {
      await adjustStockBySpec(farmCd.value, {
        wh_cd: row.wh_cd,
        item_cd: row.item_cd,
        variety_cd: row.variety_cd,
        grade_cd: row.grade_cd,
        size_cd: row.size_cd,
        weight: row.weight,
        harvest_year: row.harvest_year,
        io_type: ioType,
        qty,
        reason_cd: adjustReason.value,
      })
    }
    await load()
    const freshEntry = filteredEntries.value.find((e) => e.listKey === entry.listKey)
    const fresh = freshEntry?.row
    const currentQty = fresh ? fresh.real_qty : after
    const title = fresh ? cardTitle(fresh) : cardTitle(row)
    pageSuccess.value =
      `재고 조정이 완료되었습니다.\n${title} · ${adjustReasonLabel.value} · ${qty}${unit} ${dirNm} · 현재 ${currentQty}${unit}`
    closeLog()
  } catch (err) {
    adjustError.value = err instanceof ApiClientError ? err.message : '재고를 조정하지 못했습니다.'
  } finally {
    adjustBusy.value = false
  }
}

function closeLog() {
  logTarget.value = null
  adjustEntry.value = null
  historyOpen.value = false
  historyLoaded.value = false
  logs.value = []
  logsError.value = ''
  logsLoading.value = false
  adjustError.value = ''
}

// ── 헬퍼 ─────────────────────────────────────────────────────────────
function stockUnit(itemCd: string) {
  return itemCd === ITEM_RAW ? '통' : '박스'
}

function cardTitle(row: StockItem): string {
  if (row.item_cd === ITEM_RAW) {
    // 원물: 품종 · 원물구분
    const parts = [row.variety_nm || row.variety_cd]
    if (row.size_nm) parts.push(row.size_nm)
    return parts.join(' · ')
  }
  if (JUICE_STOCK_CDS.includes(row.item_cd as typeof JUICE_STOCK_CDS[number])) {
    return JUICE_LABEL[row.item_cd] || row.item_nm || '배즙'
  }
  // 상품: 중량 · 과수 · 등급
  const wStr = row.weight > 0 ? `${row.weight}kg` : ''
  const parts = [row.variety_nm || row.variety_cd, wStr, row.size_nm || row.size_cd, row.grade_nm || row.grade_cd]
  return parts.filter(Boolean).join(' · ')
}

function logSign(log: StockLog) {
  if (log.io_type === 'IN') return '+'
  if (log.io_type === 'OUT') return '-'
  return ''
}

function logDirNm(log: StockLog) {
  if (log.io_type === 'IN') return '증가'
  if (log.io_type === 'OUT') return '감소'
  return log.io_type_nm
}

function logQtyClass(log: StockLog) {
  if (log.io_type === 'IN') return 'stock-log__qty--in'
  if (log.io_type === 'OUT') return 'stock-log__qty--out'
  return ''
}

function formatRegDt(dt: string) {
  if (!dt) return ''
  return dt.slice(5, 10).replace('-', '/')
}

/** 캐러셀에서 OrderView가 비활성 탭이면 FAB 숨김 (StockView mounted 유지 가능) */
const mainTabPanelIndex = inject<Ref<number> | null>('mainTabPanelIndex', null)
const mainTabActiveIndex = inject<Ref<number> | null>('mainTabActiveIndex', null)
const isOrdersMainTabActive = computed(() => {
  if (mainTabPanelIndex == null || mainTabActiveIndex == null) return true
  return unref(mainTabPanelIndex) === unref(mainTabActiveIndex)
})

const showSalesActionBar = computed(
  () =>
    isOrdersMainTabActive.value &&
    salesPrefill.source === 'STOCK' &&
    salesPrefill.shipLines.length > 0,
)

const stockDraftLineCount = computed(() =>
  salesPrefill.source === 'STOCK' ? salesPrefill.shipLines.length : 0,
)

const stockDraftTotalQty = computed(() =>
  salesPrefill.source === 'STOCK' ? salesPrefill.stockDraftTotalQty : 0,
)

const canAuctionShip = computed(
  () =>
    showSalesActionBar.value &&
    stockType.value === ITEM_PRODUCT &&
    salesPrefill.shipLines.every((ln) => ln.item_cd === ITEM_PRODUCT),
)

/** 탭 캐러셀 transform 회피(Teleport) · nav 바로 위 viewport dock */
const stockBatchDockStyle = {
  position: 'fixed',
  left: '50%',
  transform: 'translateX(-50%)',
  bottom:
    'calc(var(--ods-space-56) + var(--ods-space-8) + var(--ods-space-8) + env(safe-area-inset-bottom, 0px))',
  zIndex: 40,
} as const
</script>

<template>
  <div
    class="stock-view"
    :class="{ 'stock-view--with-dock': showSalesActionBar }"
  >
    <p v-if="pageSuccess" class="stock-view__page-ok">{{ pageSuccess }}</p>
    <p v-if="auctionRefreshError" class="stock-view__error">{{ auctionRefreshError }}</p>

    <!-- Level 2: 원물 / 상품 / 배즙 탭 -->
    <div class="stock-view__type-tabs" role="tablist" aria-label="재고 종류">
      <button
        v-for="t in STOCK_TYPES"
        :key="t.value"
        type="button"
        role="tab"
        class="stock-view__type-btn"
        :class="{ 'stock-view__type-btn--on': stockType === t.value }"
        :aria-selected="stockType === t.value"
        @click="stockType = t.value"
      >
        {{ t.label }}
      </button>
    </div>

    <!-- 출하중 (경매) — 상품 탭에서만 -->
    <OdsCard
      v-if="stockType === ITEM_PRODUCT"
      class="stock-view__transit"
      aria-label="경매출하"
      data-testid="auction-transit-section"
    >
      <div class="stock-view__transit-head">
        <OdsSelect
          v-model="transitYearMonth"
          class="stock-view__transit-month"
          aria-label="출하 년월"
          data-testid="auction-transit-month"
          :disabled="!transitMonthOptions.length"
        >
          <option v-if="!transitMonthOptions.length" value="">년월</option>
          <option
            v-for="option in transitMonthOptions"
            :key="option.value"
            :value="option.value"
          >
            {{ option.label }}
          </option>
        </OdsSelect>
        <OdsSelect
          v-model="transitStatus"
          class="stock-view__transit-status"
          aria-label="출하 상태"
          data-testid="auction-transit-status"
        >
          <option
            v-for="option in AUCTION_STATUS_FILTER_OPTIONS"
            :key="option.value"
            :value="option.value"
          >
            {{ option.label }}
          </option>
        </OdsSelect>
        <span
          v-if="transitLoading"
          class="stock-view__transit-count"
          data-testid="auction-transit-count"
        >불러오는 중…</span>
        <span
          v-else
          class="stock-view__transit-count"
          data-testid="auction-transit-count"
        >{{ filteredTransitShipments.length }}건</span>
        <button
          type="button"
          class="stock-view__transit-toggle"
          :aria-label="transitOpen ? '경매출하 목록 접기' : '경매출하 목록 보기'"
          :aria-expanded="transitOpen"
          data-testid="auction-transit-toggle"
          @click="transitOpen = !transitOpen"
        >
          <svg class="stock-view__transit-toggle-icon" viewBox="0 0 20 20" fill="none" aria-hidden="true">
            <circle cx="8.5" cy="8.5" r="5.2" stroke="currentColor" stroke-width="1.6" />
            <path d="M12.5 12.5L16.2 16.2" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
          </svg>
        </button>
      </div>
      <p v-if="transitError" class="stock-view__transit-err">{{ transitError }}</p>
      <ul v-if="transitOpen && filteredTransitShipments.length" class="stock-view__transit-list">
        <li
          v-for="ship in filteredTransitShipments"
          :key="ship.shipment_id"
          class="stock-view__transit-item"
          :class="{
            'stock-view__transit-item--cancelled': isTransitCancelled(ship),
          }"
          data-testid="auction-transit-item"
        >
          <component
            :is="isTransitCancelled(ship) ? 'div' : 'button'"
            class="stock-view__transit-info"
            :class="{ 'stock-view__transit-info--toggle': !isTransitCancelled(ship) }"
            v-bind="transitInfoAttrs(ship)"
            @click="toggleTransitExpand(ship)"
          >
            <span class="stock-view__transit-lines">
              <span class="stock-view__transit-main">
                {{ ship.ship_dt }} · {{ ship.market_name }} · {{ ship.corporation_name }}
              </span>
              <span class="stock-view__transit-sub">
                출하 {{ ship.total_shipped_qty }}박스 · {{ auctionShipmentStatusLabel(ship.status) }}
                <template v-if="ship.status === AUCTION_STATUS_COMPLETED && ship.gross_sales_amount">
                  · {{ formatWon(ship.gross_sales_amount) }}
                </template>
              </span>
            </span>
            <img
              v-if="!isTransitCancelled(ship)"
              class="stock-view__transit-chev"
              :class="{ 'stock-view__transit-chev--open': isTransitExpanded(ship) }"
              :src="iconChevronDown"
              alt=""
              aria-hidden="true"
            >
          </component>
          <div
            v-if="isTransitExpanded(ship)"
            :id="transitActionsId(ship)"
            class="stock-view__transit-actions"
            data-testid="auction-transit-actions"
          >
            <button
              v-if="isAuctionMatchFetchAllowed(ship)"
              type="button"
              class="stock-view__transit-action stock-view__transit-action--strong"
              :disabled="transitCancelBusy || reopenSheetOpen"
              data-testid="auction-match-open"
              @click.stop="openAuctionMatch(ship)"
            >
              경락가 가져오기
            </button>
            <button
              v-if="isAuctionReopenAllowed(ship)"
              type="button"
              class="stock-view__transit-action stock-view__transit-action--strong"
              :disabled="transitCancelBusy || matchSheetOpen || reopenSheetOpen"
              data-testid="auction-reopen-open"
              @click.stop="openAuctionReopen(ship)"
            >
              경락매칭 정정
            </button>
            <button
              v-if="isAuctionCancelAllowed(ship)"
              type="button"
              class="stock-view__transit-action"
              :disabled="transitCancelBusy || matchSheetOpen || reopenSheetOpen"
              data-testid="auction-ship-cancel"
              @click.stop="cancelTransitShipment(ship)"
            >
              경매출하 취소
            </button>
          </div>
        </li>
      </ul>
      <p
        v-else-if="transitOpen && !transitLoading && !filteredTransitShipments.length"
        class="stock-view__transit-empty"
      >
        {{ transitShipments.length ? '조건에 맞는 출하 건이 없습니다.' : '경매출하 건이 없습니다.' }}
      </p>
    </OdsCard>

    <!-- 필터 바 -->
    <div class="stock-view__filter-bar">
      <label class="stock-view__filter-toggle">
        <input
          v-model="includeZero"
          type="checkbox"
          class="stock-view__filter-check"
          aria-label="재고(0)포함"
        />
        <span>재고(0)포함</span>
      </label>
    </div>

    <!-- 조회 조건: 상품 리스트와 구분되는 카드 -->
    <OdsCard class="stock-view__query-card" aria-label="조회조건" data-testid="stock-query-bar">
      <div class="stock-view__query-bar">
        <OdsSelect
          v-model="draftVariety"
          class="stock-view__query-select"
          aria-label="품종"
          data-testid="stock-filter-variety"
        >
          <option :value="FILTER_ALL">품종</option>
          <option v-for="o in varietyOptions" :key="o.value" :value="o.value">{{ o.label }}</option>
        </OdsSelect>
        <OdsSelect
          v-model="draftWeight"
          class="stock-view__query-select"
          aria-label="중량"
          data-testid="stock-filter-weight"
        >
          <option :value="FILTER_ALL">중량</option>
          <option v-for="o in weightOptions" :key="o.value" :value="o.value">{{ o.label }}</option>
        </OdsSelect>
        <OdsSelect
          v-model="draftSize"
          class="stock-view__query-select"
          aria-label="크기"
          data-testid="stock-filter-size"
        >
          <option :value="FILTER_ALL">크기</option>
          <option v-for="o in sizeOptions" :key="o.value" :value="o.value">{{ o.label }}</option>
        </OdsSelect>
        <OdsSelect
          v-model="draftGrade"
          class="stock-view__query-select"
          aria-label="등급"
          data-testid="stock-filter-grade"
        >
          <option :value="FILTER_ALL">등급</option>
          <option v-for="o in gradeOptions" :key="o.value" :value="o.value">{{ o.label }}</option>
        </OdsSelect>
        <button
          type="button"
          class="stock-view__query-btn"
          data-testid="stock-search"
          aria-label="조회"
          title="조회"
          @click="applyQuerySearch"
        >
          <svg class="stock-view__query-icon" viewBox="0 0 20 20" fill="none" aria-hidden="true">
            <circle cx="8.5" cy="8.5" r="5.2" stroke="currentColor" stroke-width="1.6" />
            <path d="M12.5 12.5L16.2 16.2" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
          </svg>
        </button>
        <button
          type="button"
          class="stock-view__refresh-btn"
          data-testid="stock-refresh"
          :disabled="loading"
          :aria-label="loading ? '로딩 중' : '새로고침'"
          :title="loading ? '로딩 중…' : '새로고침'"
          @click="load"
        >
          <svg class="stock-view__refresh-icon" :class="{ 'is-spinning': loading }" viewBox="0 0 20 20" fill="none" aria-hidden="true">
            <path d="M16.2 10a6.2 6.2 0 11-1.7-4.3" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
            <path d="M14.2 3.8v3.4h3.4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
        </button>
      </div>
    </OdsCard>

    <!-- 오류 -->
    <p v-if="loadError" class="stock-view__error">{{ loadError }}</p>

    <!-- 빈 상태 -->
    <div v-if="!loading && !loadError && filteredEntries.length === 0" class="stock-view__empty">
      <p class="stock-view__empty-title">재고 없음</p>
      <p class="stock-view__empty-desc">
        {{ includeZero ? '등록된 재고가 없습니다.' : '현재 재고가 없습니다. 재고(0)포함을 선택하면 볼 수 있습니다.' }}
      </p>
    </div>

    <!-- 재고 목록 (1행 compact) -->
    <div
      v-if="!loading && !loadError && filteredEntries.length > 0"
      class="stock-view__list"
      role="list"
      data-testid="stock-sale-list"
    >
      <div class="stock-view__list-head" role="row" data-testid="stock-list-head">
        <span class="stock-view__head-title">상품</span>
        <span class="stock-view__head-qty">가용수량</span>
        <span class="stock-view__head-pack">판매수량</span>
      </div>
      <div
        v-for="entry in filteredEntries"
        :key="entry.listKey"
        class="stock-view__row"
        :class="{
          'stock-view__row--in-cart': isSellable(entry.row) && isInCart(entry.row),
          'stock-view__row--zero': entry.row.available_qty <= 0,
        }"
        role="listitem"
        data-testid="stock-sale-row"
        @click="onListRowClick(entry)"
      >
        <span class="stock-view__row-title">{{ cardTitle(entry.row) }}</span>

        <template v-if="isSellable(entry.row)">
          <span
            class="stock-view__row-qty"
            data-testid="stock-row-available"
          >
            <strong>{{ entry.row.available_qty }}</strong>{{ stockUnit(entry.row.item_cd) }}
          </span>
          <div class="stock-view__row-actions" @click.stop>
            <div class="stock-view__qty-stepper" data-testid="stock-row-stepper">
              <button
                type="button"
                class="stock-view__qty-btn"
                :disabled="displayQty(entry.row) <= 1"
                :aria-label="`${cardTitle(entry.row)} 수량 감소`"
                @click="bumpQty(entry.row, -1)"
              >
                −
              </button>
              <OdsInput
                bare
                class="stock-view__qty-input"
                data-testid="stock-row-qty-input"
                type="number"
                inputmode="numeric"
                min="1"
                :max="maxQty(entry.row)"
                step="1"
                :model-value="String(displayQty(entry.row))"
                :aria-label="`${cardTitle(entry.row)} 판매 수량`"
                @update:model-value="onQtyInput(entry.row, $event)"
              />
              <button
                type="button"
                class="stock-view__qty-btn"
                :disabled="displayQty(entry.row) >= maxQty(entry.row)"
                :aria-label="`${cardTitle(entry.row)} 수량 증가`"
                @click="bumpQty(entry.row, 1)"
              >
                +
              </button>
            </div>
            <!-- 아이콘 3개 고정: 담기 / 수정 / 비우기 — 상황에 따라 enabled -->
            <div class="stock-view__icon-slot" data-testid="stock-row-icons">
              <button
                type="button"
                class="stock-view__icon-btn stock-view__icon-btn--add"
                data-testid="stock-row-add"
                :disabled="isInCart(entry.row)"
                :aria-label="`${cardTitle(entry.row)} 담기`"
                title="담기"
                @click="addToCart(entry.row)"
              >
                <svg class="stock-view__icon" viewBox="0 0 20 20" fill="none" aria-hidden="true">
                  <path d="M3.5 5h1.2l1.1 8.2a1.4 1.4 0 001.4 1.2h6.6a1.4 1.4 0 001.4-1.15L16.2 7H6.1" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
                  <path d="M8.2 16.6a.9.9 0 100 1.8.9.9 0 000-1.8zM14 16.6a.9.9 0 100 1.8.9.9 0 000-1.8z" fill="currentColor" />
                </svg>
              </button>
              <button
                type="button"
                class="stock-view__icon-btn stock-view__icon-btn--update"
                data-testid="stock-row-update"
                :disabled="!isInCart(entry.row)"
                :aria-label="`${cardTitle(entry.row)} 수량 수정`"
                title="수정"
                @click="updateCartQty(entry.row)"
              >
                <svg class="stock-view__icon" viewBox="0 0 20 20" fill="none" aria-hidden="true">
                  <path d="M12.2 3.6l4.2 4.2" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
                  <path d="M4 16l.7-3.6L13.2 4l2.8 2.8L7.6 15.3 4 16z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round" />
                </svg>
              </button>
              <button
                type="button"
                class="stock-view__icon-btn stock-view__icon-btn--remove"
                data-testid="stock-row-remove"
                :disabled="!isInCart(entry.row)"
                :aria-label="`${cardTitle(entry.row)} 판매예정 제거`"
                title="비우기"
                @click="removeFromCart(entry.row)"
              >
                <svg class="stock-view__icon" viewBox="0 0 20 20" fill="none" aria-hidden="true">
                  <path d="M5.2 6.2h9.6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
                  <path d="M8 4.2h4l.8 2H7.2L8 4.2z" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round" />
                  <path d="M6.4 6.2l.7 9.2a1.4 1.4 0 001.4 1.3h3a1.4 1.4 0 001.4-1.3l.7-9.2" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round" />
                  <path d="M8.6 9.2v5M11.4 9.2v5" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" />
                </svg>
              </button>
            </div>
          </div>
        </template>
        <span
          v-else
          class="stock-view__row-qty"
          :class="{ 'stock-view__row-qty--muted': entry.row.available_qty <= 0 }"
        >
          <strong>{{ entry.row.available_qty }}</strong>{{ stockUnit(entry.row.item_cd) }}
        </span>
      </div>
    </div>

    <!-- 선택 액션 — viewport 하단 dock (스크롤해도 nav 위 고정) -->
    <Teleport to="body">
      <div
        v-if="showSalesActionBar"
        class="stock-view__batch"
        data-testid="stock-sales-fab"
        role="region"
        aria-label="재고 선택 액션"
        :style="stockBatchDockStyle"
      >
        <span class="stock-view__batch-count" data-testid="stock-batch-count">
          선택 {{ stockDraftLineCount }}품목 {{ stockDraftTotalQty }}상자
        </span>
        <div class="stock-view__batch-actions">
          <OdsButton
            type="button"
            :block="false"
            class="stock-view__action-btn"
            data-testid="stock-direct-sale-btn"
            @click="openSalesPreview"
          >
            직접 판매
          </OdsButton>
          <OdsButton
            v-if="canAuctionShip"
            type="button"
            variant="secondary"
            :block="false"
            class="stock-view__action-btn"
            data-testid="stock-auction-btn"
            :busy="auctionOpening"
            :disabled="auctionOpening"
            @click="openAuctionSheet"
          >
            경매 넘기기
          </OdsButton>
        </div>
      </div>
    </Teleport>

    <AuctionShipConfirmSheet
      :open="auctionSheetOpen"
      :farm-cd="farmCd || ''"
      :lines="salesPrefill.shipLines"
      @close="closeAuctionSheet"
      @success="onAuctionShipSuccess"
      @qty-unavailable="onAuctionQtyUnavailable"
    />
    <AuctionMatchSheet
      :open="matchSheetOpen"
      :farm-cd="farmCd || ''"
      :shipment-id="matchShipmentId"
      @close="closeAuctionMatch"
      @success="onAuctionMatchSuccess"
      @status-conflict="onAuctionMatchStatusConflict"
    />
    <AuctionReopenConfirmSheet
      :open="reopenSheetOpen"
      :farm-cd="farmCd || ''"
      :shipment-id="reopenShipmentId"
      @close="closeAuctionReopen"
      @success="onAuctionReopenSuccess"
      @settled="onAuctionReopenSettled"
      @status-conflict="onAuctionReopenStatusConflict"
      @not-found="onAuctionReopenNotFound"
    />

    <!-- 재고 이력 bottom sheet -->
    <Teleport to="body">
      <div
        v-if="logTarget"
        class="stock-log-overlay"
        role="dialog"
        aria-modal="true"
        aria-label="재고 조정"
        @click.self="closeLog"
      >
        <div class="stock-log-sheet">
          <div class="stock-log-sheet__header">
            <span class="stock-log-sheet__title">{{ cardTitle(logTarget) }}</span>
            <button type="button" class="stock-log-sheet__close" aria-label="닫기" @click="closeLog">✕</button>
          </div>

          <div v-if="logTarget" class="stock-log-adjust">
            <div class="stock-log-adjust__row">
              <p class="stock-log-adjust__lbl">조정 사유</p>
              <OdsSelect v-model="adjustReason" variant="form" class="stock-log-adjust__reason">
                <option v-for="r in adjustReasons" :key="r.value" :value="r.value">
                  {{ r.label }}
                </option>
              </OdsSelect>
              <OdsInput
                v-model="adjustQty"
                type="number"
                min="1"
                step="1"
                inputmode="numeric"
                variant="form"
                bare
                class="stock-log-adjust__qty"
                aria-label="조정 수량"
              />
            </div>

            <div class="stock-log-adjust__btns">
              <OdsButton
                type="button"
                variant="primary"
                :disabled="adjustBusy || !canAdjustIn"
                @click="requestAdjust('IN')"
              >
                증가
              </OdsButton>
              <OdsButton
                type="button"
                variant="primary"
                :disabled="adjustBusy || !canAdjustOut"
                @click="requestAdjust('OUT')"
              >
                감소
              </OdsButton>
            </div>

            <p v-if="previewText" class="stock-log-adjust__preview">{{ previewText }}</p>
            <p v-if="adjustError" class="stock-log-sheet__msg stock-log-sheet__msg--err">{{ adjustError }}</p>

            <!-- 이력은 “필요할 때만” 버튼으로 분리해서 조회 -->
            <div class="stock-log-history">
              <OdsButton
                type="button"
                variant="secondary"
                class="stock-log-history-accordion-btn"
                @click="historyOpen ? closeHistoryAccordion() : openHistoryLogs()"
              >
                {{ historyOpen ? '조정 이력 접기 ▲' : '조정 이력 보기 ▼' }}
              </OdsButton>

              <div v-if="historyOpen" class="stock-log-history__body">
                <p v-if="logsLoading" class="stock-log-sheet__msg">로딩 중…</p>
                <p v-else-if="logsError" class="stock-log-sheet__msg stock-log-sheet__msg--err">{{ logsError }}</p>
                <p v-else-if="logs.length === 0" class="stock-log-sheet__msg">이력이 없습니다.</p>

                <ul v-else class="stock-log-list">
                  <li
                    v-for="log in logs"
                    :key="log.log_id"
                    class="stock-log__row"
                  >
                    <span class="stock-log__date">{{ formatRegDt(log.reg_dt) }}</span>
                    <span class="stock-log__type">
                      <template v-if="log.io_type === 'IN' || log.io_type === 'OUT'">{{ logDirNm(log) }} · {{ log.io_type_nm }}</template>
                      <template v-else>{{ log.io_type_nm }}</template>
                    </span>
                    <span class="stock-log__qty" :class="logQtyClass(log)">
                      {{ logSign(log) }}{{ log.qty }}{{ stockUnit(log.item_cd) }}
                    </span>
                    <span v-if="log.remark" class="stock-log__rmk">{{ log.remark }}</span>
                  </li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Teleport>

  </div>
</template>

<style scoped>
/* ── 전체 컨테이너 ────────────────────────────────────────────────── */
.stock-view {
  --stock-batch-dock-h: calc(
    var(--ods-space-8) + var(--ods-space-8) + 11px * 1.3 + var(--ods-space-12) + 28px + var(--ods-space-8)
  );
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-12);
  padding: var(--ods-space-12) var(--ods-space-16);
  background: var(--ods-color-bg, #FDFBF7);
}
.stock-view--with-dock {
  padding-bottom: calc(var(--stock-batch-dock-h) + var(--ods-space-8));
}
.stock-view__page-ok {
  margin: 0;
  padding: var(--ods-space-8) var(--ods-space-12);
  font: var(--ods-font-body-2);
  color: #2F855A;
  background: #E6F4EA;
  border-radius: var(--ods-radius-card);
  white-space: pre-line;
}

/* ── Level 2 탭 (상품/원물/배즙) — 상단 4탭보다 작게 ─────────────── */
.stock-view__type-tabs {
  display: flex;
  gap: 0;
  border-bottom: 1px solid var(--ods-color-border);
}
.stock-view__type-btn {
  flex: 1;
  padding: var(--ods-space-8) 0;
  font: var(--ods-font-body-2);
  color: var(--ods-color-text-secondary);
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  cursor: pointer;
  transition: color 0.15s, border-color 0.15s;
}
.stock-view__type-btn--on {
  font-weight: 600;
  color: var(--ods-color-primary);
  border-bottom-color: var(--ods-color-primary);
}

/* ── 필터 바 ──────────────────────────────────────────────────────── */
.stock-view__filter-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ods-space-8);
}
.stock-view__filter-toggle {
  display: flex;
  align-items: center;
  gap: var(--ods-space-4);
  font-size: var(--ods-font-size-footnote, 12px);
  line-height: 1.35;
  font-weight: 500;
  color: var(--ods-color-text-secondary);
  cursor: pointer;
}
.stock-view__filter-check {
  width: 14px;
  height: 14px;
  accent-color: var(--ods-color-primary);
  cursor: pointer;
}
.stock-view__query-card {
  padding: var(--ods-space-8) var(--ods-space-12);
  background: var(--ods-color-bg-muted);
  box-shadow: none;
}
.stock-view__query-bar {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr)) 28px 28px;
  align-items: center;
  gap: var(--ods-space-4);
}
.stock-view__query-select {
  min-width: 0;
  width: 100%;
}
.stock-view__query-bar :deep(select.ods-select) {
  width: 100%;
  height: 28px;
  min-height: 28px;
  max-height: 28px;
  padding: 0 4px;
  font-size: var(--ods-font-size-footnote, 12px);
  line-height: 1.2;
}
.stock-view__query-btn,
.stock-view__refresh-btn {
  width: 28px;
  height: 28px;
  min-width: 28px;
  padding: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--ods-color-primary);
  background: transparent;
  border: none;
  border-radius: var(--ods-radius-button);
  cursor: pointer;
}
.stock-view__query-btn:disabled,
.stock-view__refresh-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.stock-view__query-icon,
.stock-view__refresh-icon {
  width: 18px;
  height: 18px;
  display: block;
}
.stock-view__refresh-icon.is-spinning {
  animation: stock-view-spin 0.8s linear infinite;
}
@keyframes stock-view-spin {
  to { transform: rotate(360deg); }
}

/* ── 오류/빈 상태 ─────────────────────────────────────────────────── */
.stock-view__error {
  font: var(--ods-font-body-2);
  color: var(--ods-color-danger);
  text-align: center;
  padding: var(--ods-space-24) 0;
}
.stock-view__empty {
  text-align: center;
  padding: var(--ods-space-40) var(--ods-space-16);
}
.stock-view__empty-title {
  font: var(--ods-font-title-3);
  color: var(--ods-color-text);
  margin-bottom: var(--ods-space-4);
}
.stock-view__empty-desc {
  font: var(--ods-font-body-2);
  color: var(--ods-color-text-secondary);
}

/* ── 재고 목록 (1행 compact · 컬럼 정렬) ──────────────────────────── */
.stock-view__list {
  --stock-col-qty: 3.25rem;
  --stock-col-stepper: 5.75rem;
  --stock-col-icons: 5.25rem; /* 28px × 3 */
  display: flex;
  flex-direction: column;
  gap: 0;
  margin: 0 calc(var(--ods-space-16) * -1); /* 화면 좌우에 맞춤 */
  background: var(--ods-color-white, #fff);
  border-radius: 0;
  overflow: hidden;
}
/* 리스트 본문 — footnote(12px)로 한 단계 축소 */
.stock-view__list-head,
.stock-view__row,
.stock-view__row-title,
.stock-view__row-qty,
.stock-view__row-qty strong {
  font-size: var(--ods-font-size-footnote, 12px);
  line-height: 1.35;
}
.stock-view__list-head,
.stock-view__row {
  display: grid;
  grid-template-columns:
    minmax(0, 1fr)
    var(--stock-col-qty)
    var(--stock-col-stepper)
    var(--stock-col-icons);
  align-items: center;
  column-gap: var(--ods-space-6);
  padding: var(--ods-space-4) var(--ods-space-16);
}
.stock-view__list-head {
  min-height: 32px;
  border-bottom: 1px solid var(--ods-color-border);
  background: transparent;
  color: var(--ods-color-text-secondary);
  font-weight: 600;
  cursor: default;
  user-select: none;
}
.stock-view__head-title {
  min-width: 0;
  white-space: nowrap;
}
.stock-view__head-qty {
  white-space: nowrap;
  text-align: right;
}
.stock-view__head-pack {
  grid-column: 3;
  white-space: nowrap;
  text-align: center;
}
.stock-view__row {
  min-height: 40px;
  border-bottom: 1px solid var(--ods-color-border);
  cursor: pointer;
  background: transparent;
}
.stock-view__row:last-child {
  border-bottom: none;
}
.stock-view__row--in-cart {
  background: var(--ods-color-primary-subtle, #f0f7f4);
}
.stock-view__row-title {
  min-width: 0;
  font-weight: 500;
  color: var(--ods-color-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.stock-view__row-qty {
  text-align: right;
  font-weight: 500;
  color: var(--ods-color-text);
  white-space: nowrap;
}
.stock-view__row-qty strong {
  font-weight: 500;
  color: var(--ods-color-primary);
  margin-right: 1px;
}
.stock-view__row-qty--muted,
.stock-view__row-qty--muted strong {
  color: var(--ods-color-text-secondary);
  font-weight: 500;
}
.stock-view__row-actions {
  grid-column: 3 / 5;
  display: grid;
  grid-template-columns: var(--stock-col-stepper) var(--stock-col-icons);
  align-items: center;
  column-gap: var(--ods-space-6);
  min-width: 0;
}
.stock-view__qty-stepper {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 2px;
  flex-shrink: 0;
}
.stock-view__qty-btn {
  width: 26px;
  height: 26px;
  min-width: 26px;
  padding: 0;
  border: 1px solid var(--ods-color-border);
  border-radius: var(--ods-radius-button);
  background: var(--ods-color-white, #fff);
  color: var(--ods-color-text);
  font-size: var(--ods-font-size-footnote, 12px);
  line-height: 1;
  cursor: pointer;
}
.stock-view__qty-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
/* bare OdsInput = root 자체가 input.ods-input — 자식 input 셀렉터는 매칭 안 됨 */
:deep(input.stock-view__qty-input.ods-input) {
  width: 34px;
  min-width: 34px;
  max-width: 36px;
  height: 26px;
  min-height: 26px;
  max-height: 28px;
  box-sizing: border-box;
  padding: 0 2px;
  margin: 0;
  text-align: center;
  font-size: var(--ods-font-size-footnote, 12px);
  line-height: 1.2;
  font-weight: 500;
  color: var(--ods-color-text);
  flex-shrink: 0;
  -moz-appearance: textfield;
  appearance: textfield;
}
:deep(input.stock-view__qty-input.ods-input::-webkit-outer-spin-button),
:deep(input.stock-view__qty-input.ods-input::-webkit-inner-spin-button) {
  -webkit-appearance: none;
  margin: 0;
}
/* 아이콘 3칸 고정 슬롯 — enabled만 진하게 */
.stock-view__icon-slot {
  display: grid;
  grid-template-columns: repeat(3, 28px);
  justify-content: end;
  align-items: center;
  width: var(--stock-col-icons);
}
.stock-view__icon-btn {
  width: 28px;
  height: 28px;
  min-width: 28px;
  padding: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 0;
  cursor: pointer;
  flex-shrink: 0;
  background: transparent;
}
.stock-view__icon-btn:disabled {
  opacity: 0.28;
  cursor: not-allowed;
  color: var(--ods-color-text-secondary) !important;
}
.stock-view__icon {
  width: 18px;
  height: 18px;
  display: block;
}
.stock-view__icon-btn--add {
  color: var(--ods-color-primary);
}
.stock-view__icon-btn--update {
  color: var(--ods-color-primary);
}
.stock-view__icon-btn--remove {
  color: var(--ods-color-danger, #c53030);
}
.stock-view__transit {
  margin-bottom: var(--ods-space-8);
}
.stock-view__transit-head {
  display: flex;
  align-items: center;
  gap: var(--ods-space-8);
  padding: var(--ods-space-8) var(--ods-space-4);
}
/* 년월·상태 필터는 내용폭, 건수는 우측 정렬 (360px에서도 1행 유지) */
.stock-view__transit-month,
.stock-view__transit-status {
  flex: 0 1 auto;
  width: auto;
  min-width: 0;
}
.stock-view__transit-month {
  max-width: 42%;
}
.stock-view__transit-status {
  max-width: 32%;
}
.stock-view__transit-count {
  margin-left: auto;
  font: var(--ods-font-caption);
  font-weight: 500;
  color: var(--ods-color-text-secondary);
  white-space: nowrap;
}
/* 건수는 표시만 — 펼침은 우측 돋보기 아이콘으로만 */
.stock-view__transit-toggle {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: var(--ods-touch-min);
  height: var(--ods-touch-min);
  margin: 0;
  padding: 0;
  border: none;
  border-radius: var(--ods-radius-button);
  background: transparent;
  color: var(--ods-color-text-secondary);
  cursor: pointer;
}
.stock-view__transit-toggle-icon {
  width: var(--ods-icon-lg);
  height: var(--ods-icon-lg);
  display: block;
}
.stock-view__transit-list {
  list-style: none;
  margin: 0;
  padding: 0 var(--ods-space-4) var(--ods-space-8);
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-6);
}
.stock-view__transit-item {
  display: flex;
  flex-direction: column;
  border-radius: var(--ods-radius-card);
  background: var(--ods-color-surface-muted, #faf8f4);
  overflow: hidden;
}
.stock-view__transit-item--cancelled {
  background: var(--ods-color-bg-muted);
}
/* 접힘 상태 기본 2줄 — 날짜/시장/회사 + 수량/상태 */
.stock-view__transit-info {
  display: flex;
  align-items: center;
  gap: var(--ods-space-8);
  width: 100%;
  margin: 0;
  padding: var(--ods-space-8);
  border: none;
  background: transparent;
  color: inherit;
  text-align: left;
}
.stock-view__transit-info--toggle {
  cursor: pointer;
}
.stock-view__transit-lines {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-2);
}
.stock-view__transit-chev {
  flex: 0 0 auto;
  width: var(--ods-icon-lg);
  height: var(--ods-icon-lg);
  opacity: 0.55;
  transition: transform 180ms ease;
}
.stock-view__transit-chev--open {
  transform: rotate(180deg);
}
.stock-view__transit-main {
  font: var(--ods-font-body-2);
  font-weight: 600;
  color: var(--ods-color-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.stock-view__transit-item--cancelled .stock-view__transit-main {
  font-weight: 500;
  color: var(--ods-color-text-secondary);
}
.stock-view__transit-sub {
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.stock-view__transit-item--cancelled .stock-view__transit-sub {
  color: var(--ods-color-gray-500);
}
/* 확장 시에만 노출되는 무채색 chip 액션 — 좌측 정렬, 구분선 없이 여백으로만 분리 */
.stock-view__transit-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-start;
  align-items: center;
  gap: var(--ods-space-8);
  padding: 0 var(--ods-space-8) var(--ods-space-8);
}
.stock-view__transit-action {
  flex: 0 0 auto;
  min-height: 36px;
  margin: 0;
  padding: 0 var(--ods-space-12);
  border: 1px solid var(--ods-color-border);
  border-radius: var(--ods-radius-badge);
  background: var(--ods-color-bg);
  box-shadow: none;
  color: var(--ods-color-text);
  font: var(--ods-font-body-2);
  font-weight: 400;
  text-align: center;
  white-space: nowrap;
  cursor: pointer;
}
.stock-view__transit-action--strong {
  font-weight: 600;
}
/* ODS disabled — gray-300 배경 + gray-500 텍스트 */
.stock-view__transit-action:disabled {
  border-color: var(--ods-color-gray-300);
  background: var(--ods-color-gray-300);
  color: var(--ods-color-gray-500);
  cursor: default;
}
.stock-view__transit-err,
.stock-view__transit-empty {
  margin: 0;
  padding: 0 var(--ods-space-4) var(--ods-space-8);
  font: var(--ods-font-footnote);
  color: var(--ods-color-text-secondary);
}
.stock-view__transit-err {
  color: var(--ods-color-danger);
}
.stock-view__batch {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 0;
  width: min(74%, 15rem);
  max-width: 15rem;
  box-sizing: border-box;
  padding: var(--ods-space-8);
  border: 1px solid var(--ods-color-border);
  border-radius: var(--ods-radius-card);
  background: var(--ods-color-white);
  box-shadow: var(--ods-shadow-elevated);
}
.stock-view__batch-count {
  display: block;
  width: 100%;
  padding: 0 var(--ods-space-4);
  font: var(--ods-font-caption);
  font-weight: 700;
  color: var(--ods-color-text);
  line-height: 1.3;
  white-space: nowrap;
  text-align: center;
}
.stock-view__batch-actions {
  display: flex;
  width: 100%;
  gap: var(--ods-space-6);
  justify-content: stretch;
  margin-top: var(--ods-space-12);
}
.stock-view__batch-actions > * {
  flex: 1 1 0;
  min-width: 0;
}
/* Floating panel — compact 버튼 */
:deep(button.stock-view__action-btn.ods-btn) {
  min-height: 28px;
  height: 28px;
  width: 100%;
  padding: 0 var(--ods-space-6);
  font-size: 12px;
  font-weight: 600;
  line-height: 1.2;
  white-space: nowrap;
}

/* ── 이력 bottom sheet ────────────────────────────────────────────── */
.stock-log-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  z-index: 300;
  display: flex;
  align-items: flex-end;
}
.stock-log-sheet {
  width: calc(100% - 24px);
  max-width: 480px;
  margin: 0 auto;
  max-height: 70vh;
  background: var(--ods-color-white, #fff);
  border-radius: var(--ods-radius-card) var(--ods-radius-card) 0 0;
  padding: var(--ods-space-16);
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-12);
}
.stock-log-sheet__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: var(--ods-space-4);
}
.stock-log-sheet__title {
  font: var(--ods-font-heading-5, var(--ods-font-title-3, var(--ods-font-body-1)));
  font-size: calc(var(--ods-font-size-body-1, 16px) + 1px);
  font-weight: 700;
  color: var(--ods-color-text);
  text-align: left;
  flex: 1;
}
.stock-log-sheet__close {
  padding: var(--ods-space-4);
  background: transparent;
  border: none;
  font-size: 16px;
  color: var(--ods-color-text-secondary);
  cursor: pointer;
}
.stock-log-sheet__msg {
  font: var(--ods-font-body-2);
  color: var(--ods-color-text-secondary);
  text-align: center;
  padding: var(--ods-space-8) 0;
}
.stock-log-sheet__msg--err {
  color: var(--ods-color-danger);
}

/* ── 이력 행 ──────────────────────────────────────────────────────── */
.stock-log-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-4);
}
.stock-log__row {
  display: grid;
  grid-template-columns: 3rem 1fr auto;
  align-items: center;
  gap: var(--ods-space-8);
  padding: var(--ods-space-6) 0;
  border-bottom: 1px solid var(--ods-color-border-light, #f0ede8);
}
.stock-log__date {
  font: var(--ods-font-footnote);
  color: var(--ods-color-text-secondary);
}
.stock-log__type {
  font: var(--ods-font-body-2);
  color: var(--ods-color-text);
}
.stock-log__qty {
  font: var(--ods-font-body-2);
  font-weight: 600;
  color: var(--ods-color-text);
}
.stock-log__qty--in  { color: var(--ods-color-primary); }
.stock-log__qty--out { color: var(--ods-color-danger); }
.stock-log__rmk {
  grid-column: 1 / -1;
  font: var(--ods-font-footnote);
  color: var(--ods-color-text-secondary);
}
.stock-log-adjust {
  padding-top: var(--ods-space-8);
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-8);
}
.stock-log-adjust__row {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) minmax(72px, 88px);
  gap: var(--ods-space-8);
  align-items: center;
}
.stock-log-adjust__btns {
  display: flex;
  gap: var(--ods-space-8);
}

.stock-log-adjust__lbl {
  margin: 0;
  font: var(--ods-font-form-label, var(--ods-font-body-2));
  font-size: calc(var(--ods-font-size-body-2, 14px) + 1px);
  font-weight: 700;
  color: var(--ods-color-text);
  white-space: nowrap;
}
.stock-log-adjust__row :deep(.ods-select),
.stock-log-adjust__row :deep(.ods-input) {
  font: var(--ods-font-form-value, var(--ods-font-body-1));
  font-weight: 600;
  color: var(--ods-color-text);
}
.stock-log-adjust__row :deep(.stock-log-adjust__qty) {
  text-align: center;
}

.stock-log-adjust__preview {
  margin: 0;
  font: var(--ods-font-body-2);
  color: var(--ods-color-text-secondary);
  padding: var(--ods-space-8) var(--ods-space-12);
  border: 1px dashed var(--ods-color-border);
  border-radius: var(--ods-radius-card);
  white-space: pre-line;
}

.stock-log-history {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-8);
  margin-top: var(--ods-space-4);
  padding-top: var(--ods-space-8);
  border-top: 1px solid var(--ods-color-border);
}

.stock-log-history__body {
  margin-top: var(--ods-space-4);
}

.stock-log-history-accordion-btn {
  align-self: stretch;
}
</style>
