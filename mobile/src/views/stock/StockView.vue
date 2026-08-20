<script setup lang="ts">
import { computed, inject, ref, unref, watch, type Ref } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'

import { listFruitStock, listStockLogs, adjustStock } from '@/api/stock'
import type { StockItem, StockLog } from '@/api/stock'
import { fetchCommonCodes } from '@/api/commonCodes'
import { ApiClientError } from '@/api/client'
import OdsButton from '@/components/ods/OdsButton.vue'
import OdsInput from '@/components/ods/OdsInput.vue'
import OdsSelect from '@/components/ods/OdsSelect.vue'
import { useAppStore } from '@/composables/stores/app'
import { useSalesPrefillStore } from '@/composables/stores/salesPrefill'
import { stockSaleSpecKey } from '@/views/sales/shipConfirmModel'
import {
  buildStockListEntries,
  type StockListEntry,
} from '@/views/stock/stockSaleList'
import {
  ADJUST_REASON_OPTIONS,
  PARENT_ADJUST_REASON,
  REASON_DISPOSE,
  reasonAllowsIn,
  reasonAllowsOut,
} from '@/views/stock/stockAdjustConstants'

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

// 이력 모달
const logTarget    = ref<StockItem | null>(null)
/** 동일 판매규격에 storage_dt가 여러 개일 때 조정 대상 선택 */
const adjustPickSources = ref<StockItem[] | null>(null)
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

const listEntries = computed(() =>
  buildStockListEntries(rows.value, { raw: isRaw.value }),
)

const filteredEntries = computed(() => listEntries.value)

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

watch([stockType, includeZero, farmCd], load, { immediate: true })

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

async function openAdjustSheet(item: StockItem) {
  // 조정 시트 진입 시에는 이력 API(listStockLogs)를 자동 호출하지 않습니다.
  adjustPickSources.value = null
  logTarget.value = item
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

/**
 * 행 클릭 → 재고조정.
 * source 1건이면 바로 시트, 복수 storage_dt면 사용자 선택(자동 LOT 선택 금지).
 */
function onListRowClick(entry: StockListEntry) {
  if (entry.sources.length <= 1) {
    void openAdjustSheet(entry.sources[0] || entry.row)
    return
  }
  adjustPickSources.value = entry.sources
}

function closeAdjustPick() {
  adjustPickSources.value = null
}

function pickAdjustSource(item: StockItem) {
  adjustPickSources.value = null
  void openAdjustSheet(item)
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
    logs.value = await listStockLogs(farmCd.value, {
      item_cd: item.item_cd,
      variety_cd: item.variety_cd,
      grade_cd: item.grade_cd,
      size_cd: item.size_cd,
      weight: item.weight,
      harvest_year: item.harvest_year,
      storage_dt: item.storage_dt,
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

async function requestAdjust(ioType: 'IN' | 'OUT') {
  const row = logTarget.value
  if (!row || adjustBusy.value) return

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
    await adjustStock(farmCd.value, {
      wh_cd: row.wh_cd,
      item_cd: row.item_cd,
      variety_cd: row.variety_cd,
      grade_cd: row.grade_cd,
      size_cd: row.size_cd,
      weight: row.weight,
      harvest_year: row.harvest_year,
      storage_dt: row.storage_dt,
      io_type: ioType,
      qty,
      reason_cd: adjustReason.value,
    })
    await load()
    const fresh = rows.value.find(
      (r) =>
        r.item_cd === row.item_cd &&
        r.variety_cd === row.variety_cd &&
        r.grade_cd === row.grade_cd &&
        r.size_cd === row.size_cd &&
        r.weight === row.weight &&
        r.harvest_year === row.harvest_year &&
        r.wh_cd === row.wh_cd &&
        r.storage_dt === row.storage_dt,
    )
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
  adjustPickSources.value = null
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
const stockDraftBoxSum = computed(() =>
  salesPrefill.source === 'STOCK' ? salesPrefill.stockDraftTotalQty : 0,
)

/** transform 조상 회피(Teleport). OdsBottomNav와 동일 중앙(max 480) 정렬 */
const salesFabStyle = {
  position: 'fixed',
  left: '0',
  right: '0',
  maxWidth: '480px',
  marginLeft: 'auto',
  marginRight: 'auto',
  bottom:
    'calc(var(--ods-space-56) + var(--ods-space-8) + var(--ods-space-8) + env(safe-area-inset-bottom, 0px))',
  zIndex: 40,
} as const
</script>

<template>
  <div
    class="stock-view"
    :class="{ 'stock-view--with-batch': showSalesActionBar }"
  >
    <p v-if="pageSuccess" class="stock-view__page-ok">{{ pageSuccess }}</p>

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

    <!-- 필터 바 -->
    <div class="stock-view__filter-bar">
      <label class="stock-view__filter-toggle">
        <input
          v-model="includeZero"
          type="checkbox"
          class="stock-view__filter-check"
          aria-label="소진 재고 포함"
        />
        <span>소진 포함</span>
      </label>
      <button type="button" class="stock-view__refresh-btn" :disabled="loading" @click="load">
        {{ loading ? '로딩 중…' : '새로고침' }}
      </button>
    </div>

    <!-- 오류 -->
    <p v-if="loadError" class="stock-view__error">{{ loadError }}</p>

    <!-- 빈 상태 -->
    <div v-if="!loading && !loadError && filteredEntries.length === 0" class="stock-view__empty">
      <p class="stock-view__empty-title">재고 없음</p>
      <p class="stock-view__empty-desc">
        {{ includeZero ? '등록된 재고가 없습니다.' : '현재 재고가 없습니다. 소진 포함을 선택하면 볼 수 있습니다.' }}
      </p>
    </div>

    <!-- 재고 목록 (1행 compact) -->
    <div class="stock-view__list" role="list" data-testid="stock-sale-list">
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
            <template v-if="isInCart(entry.row)">
              <OdsButton
                type="button"
                :block="false"
                class="stock-view__cart-action"
                data-testid="stock-row-update"
                @click="updateCartQty(entry.row)"
              >
                수정
              </OdsButton>
              <button
                type="button"
                class="stock-view__cart-remove"
                data-testid="stock-row-remove"
                :aria-label="`${cardTitle(entry.row)} 판매예정 제거`"
                @click="removeFromCart(entry.row)"
              >
                ×
              </button>
            </template>
            <OdsButton
              v-else
              type="button"
              :block="false"
              class="stock-view__cart-action"
              data-testid="stock-row-add"
              @click="addToCart(entry.row)"
            >
              담기
            </OdsButton>
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

    <!-- transform 조상(탭 캐러셀) 밖 — 뷰포트 fixed Floating Bar -->
    <Teleport to="body">
      <div
        v-if="showSalesActionBar"
        class="stock-view__batch"
        data-testid="stock-sales-fab"
        role="region"
        aria-label="판매 미리보기"
        :style="salesFabStyle"
      >
        <span class="stock-view__batch-count">
          판매예정 {{ stockDraftLineCount }}품목 · {{ stockDraftBoxSum }}박스
        </span>
        <OdsButton
          type="button"
          :block="false"
          class="stock-view__preview-btn"
          data-testid="stock-preview-btn"
          @click="openSalesPreview"
        >
          판매 미리보기
        </OdsButton>
      </div>
    </Teleport>

    <!-- 동일규격 복수 storage_dt → 조정 대상 선택 (자동 LOT 선택 없음) -->
    <Teleport to="body">
      <div
        v-if="adjustPickSources"
        class="stock-log-overlay"
        role="dialog"
        aria-modal="true"
        aria-label="재고 조정 대상 선택"
        data-testid="stock-adjust-pick"
        @click.self="closeAdjustPick"
      >
        <div class="stock-log-sheet">
          <div class="stock-log-sheet__header">
            <span class="stock-log-sheet__title">조정할 재고 선택</span>
            <button type="button" class="stock-log-sheet__close" aria-label="닫기" @click="closeAdjustPick">✕</button>
          </div>
          <p class="stock-log-sheet__msg">포장/저장일별로 재고를 선택해 주세요.</p>
          <ul class="stock-adjust-pick-list">
            <li v-for="src in adjustPickSources" :key="`${src.storage_dt}_${src.wh_cd}`">
              <button
                type="button"
                class="stock-adjust-pick-btn"
                @click="pickAdjustSource(src)"
              >
                <span>{{ src.storage_dt || '일자 없음' }}</span>
                <span>
                  <strong>{{ src.available_qty }}</strong>{{ stockUnit(src.item_cd) }}
                </span>
              </button>
            </li>
          </ul>
        </div>
      </div>
    </Teleport>

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
  --stock-bottom-nav-h: calc(
    var(--ods-space-56) + var(--ods-space-8) + var(--ods-space-8) + env(safe-area-inset-bottom, 0px)
  );
  --stock-batch-bar-h: 50px;
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-12);
  padding: var(--ods-space-12) var(--ods-space-16);
  min-height: 100%;
  background: var(--ods-color-bg, #FDFBF7);
}
.stock-view--with-batch {
  padding-bottom: calc(
    var(--stock-bottom-nav-h) + var(--stock-batch-bar-h) + var(--ods-space-16)
  );
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
  font: var(--ods-font-footnote);
  color: var(--ods-color-text-secondary);
  cursor: pointer;
}
.stock-view__filter-check {
  width: 16px;
  height: 16px;
  accent-color: var(--ods-color-primary);
  cursor: pointer;
}
.stock-view__refresh-btn {
  font: var(--ods-font-footnote);
  color: var(--ods-color-primary);
  background: transparent;
  border: 1px solid var(--ods-color-primary);
  border-radius: var(--ods-radius-button);
  padding: var(--ods-space-4) var(--ods-space-8);
  cursor: pointer;
}
.stock-view__refresh-btn:disabled {
  opacity: 0.5;
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

/* ── 재고 목록 (1행 compact) ─────────────────────────────────────── */
.stock-view__list {
  display: flex;
  flex-direction: column;
  gap: 0;
  background: var(--ods-color-white, #fff);
  border-radius: var(--ods-radius-card);
  overflow: hidden;
}
.stock-view__row {
  display: flex;
  flex-wrap: nowrap;
  align-items: center;
  gap: var(--ods-space-6);
  min-height: 44px;
  padding: var(--ods-space-6) var(--ods-space-12);
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
  flex: 1 1 auto;
  min-width: 0;
  font: var(--ods-font-body-2);
  font-weight: 600;
  color: var(--ods-color-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.stock-view__row-qty {
  flex: 0 0 auto;
  font: var(--ods-font-footnote);
  color: var(--ods-color-text);
  white-space: nowrap;
}
.stock-view__row-qty strong {
  font-weight: 700;
  color: var(--ods-color-primary);
  margin-right: 1px;
}
.stock-view__row-qty--muted,
.stock-view__row-qty--muted strong {
  color: var(--ods-color-text-secondary);
  font-weight: 500;
}
.stock-view__row-actions {
  flex: 0 0 auto;
  display: inline-flex;
  flex-wrap: nowrap;
  align-items: center;
  gap: var(--ods-space-4);
}
.stock-view__qty-stepper {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  flex-shrink: 0;
}
.stock-view__qty-btn {
  width: 28px;
  height: 28px;
  min-width: 28px;
  padding: 0;
  border: 1px solid var(--ods-color-border);
  border-radius: var(--ods-radius-button);
  background: var(--ods-color-white, #fff);
  color: var(--ods-color-text);
  font-size: 16px;
  line-height: 1;
  cursor: pointer;
}
.stock-view__qty-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
/* bare OdsInput = root 자체가 input.ods-input — 자식 input 셀렉터는 매칭 안 됨 */
:deep(input.stock-view__qty-input.ods-input) {
  width: 38px;
  min-width: 38px;
  max-width: 40px;
  height: 28px;
  min-height: 28px;
  max-height: 30px;
  box-sizing: border-box;
  padding: 0 4px;
  margin: 0;
  text-align: center;
  font-size: 13px;
  line-height: 1.2;
  font-weight: 600;
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
.stock-view__cart-action {
  min-height: 28px !important;
  padding: 0 var(--ods-space-6) !important;
  font-size: 12px !important;
  flex-shrink: 0;
  white-space: nowrap;
}
.stock-view__cart-remove {
  width: 28px;
  height: 28px;
  min-width: 28px;
  padding: 0;
  border: none;
  background: transparent;
  color: var(--ods-color-text-secondary);
  font-size: 18px;
  line-height: 1;
  cursor: pointer;
  flex-shrink: 0;
}
.stock-adjust-pick-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-4);
}
.stock-adjust-pick-btn {
  width: 100%;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--ods-space-8);
  min-height: 44px;
  padding: var(--ods-space-8) var(--ods-space-12);
  border: 1px solid var(--ods-color-border);
  border-radius: var(--ods-radius-button);
  background: var(--ods-color-white, #fff);
  font: var(--ods-font-body-2);
  color: var(--ods-color-text);
  cursor: pointer;
  text-align: left;
}
.stock-adjust-pick-btn strong {
  color: var(--ods-color-primary);
}
.stock-view__batch {
  /* App 탭 캐러셀 transform 밖(body Teleport)에서 viewport 기준 fixed */
  position: fixed;
  left: 0;
  right: 0;
  /* OdsBottomNav: min-height 56 + padding 8+8 + safe-area */
  bottom: calc(
    var(--ods-space-56) + var(--ods-space-8) + var(--ods-space-8) + env(safe-area-inset-bottom, 0px)
  );
  z-index: 40; /* OdsBottomNav(50) 아래 — 시각적으로는 nav 위에 배치 */
  max-width: 480px;
  margin-left: auto;
  margin-right: auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ods-space-8);
  min-height: var(--stock-batch-bar-h, 50px);
  box-sizing: border-box;
  padding: var(--ods-space-6) max(var(--ods-space-12), env(safe-area-inset-left, 0px))
    var(--ods-space-6) max(var(--ods-space-12), env(safe-area-inset-right, 0px));
  background: var(--ods-color-white, #fff);
  border-top: 1px solid var(--ods-color-border);
  box-shadow: 0 -2px 8px rgba(0, 0, 0, 0.06);
}
.stock-view__batch-count {
  font: var(--ods-font-body-2);
  font-weight: 600;
  color: var(--ods-color-text);
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
/* OdsButton 전역(headline/큰 min-height)을 Floating Bar에서만 compact override */
:deep(button.stock-view__preview-btn.ods-btn) {
  min-height: 34px;
  height: 34px;
  padding: 0 12px;
  font-size: 13px;
  font-weight: 600;
  line-height: 1.2;
  white-space: nowrap;
  flex-shrink: 0;
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
