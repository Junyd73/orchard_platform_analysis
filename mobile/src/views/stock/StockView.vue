<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'

import OdsButton from '@/components/ods/OdsButton.vue'
import OdsCard from '@/components/ods/OdsCard.vue'
import { listFruitStock, listStockLogs } from '@/api/stock'
import type { StockItem, StockLog } from '@/api/stock'
import { useAppStore } from '@/composables/stores/app'
import { useSalesPrefillStore } from '@/composables/stores/salesPrefill'

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
const logs         = ref<StockLog[]>([])
const logsLoading  = ref(false)
const logsError    = ref('')

// ── computed ─────────────────────────────────────────────────────────
const isRaw = computed(() => stockType.value === ITEM_RAW)

const filteredRows = computed(() => {
  // 상단 탭으로 item_cd 필터링은 이미 서버에서 처리.
  // 클라이언트에서 추가 정렬: 상품은 품종→중량→등급→과수, 원물은 최근 입고일 우선
  if (isRaw.value) {
    return [...rows.value].sort((a, b) =>
      b.storage_dt.localeCompare(a.storage_dt) ||
      a.variety_cd.localeCompare(b.variety_cd),
    )
  }
  return [...rows.value].sort((a, b) =>
    a.variety_cd.localeCompare(b.variety_cd) ||
    a.weight - b.weight ||
    a.grade_cd.localeCompare(b.grade_cd) ||
    a.size_cd.localeCompare(b.size_cd),
  )
})

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

// ── 이력 조회 ─────────────────────────────────────────────────────────
async function openLog(item: StockItem) {
  logTarget.value = item
  logs.value      = []
  logsError.value = ''
  logsLoading.value = true
  try {
    logs.value = await listStockLogs(farmCd.value, {
      item_cd:      item.item_cd,
      variety_cd:   item.variety_cd,
      grade_cd:     item.grade_cd,
      size_cd:      item.size_cd,
      weight:       item.weight,
      harvest_year: item.harvest_year,
    })
  } catch {
    logsError.value = '이력을 불러오지 못했습니다.'
  } finally {
    logsLoading.value = false
  }
}

function sellProduct(row: StockItem) {
  if (row.item_cd !== ITEM_PRODUCT && !JUICE_STOCK_CDS.includes(row.item_cd as typeof JUICE_STOCK_CDS[number])) return
  salesPrefill.setFromStock(row)
  void router.push({ name: 'ship-confirm' })
}

function closeLog() {
  logTarget.value = null
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

function logQtyClass(log: StockLog) {
  if (log.io_type === 'IN') return 'stock-log__qty--in'
  if (log.io_type === 'OUT') return 'stock-log__qty--out'
  return ''
}

function formatRegDt(dt: string) {
  if (!dt) return ''
  return dt.slice(5, 10).replace('-', '/')
}
</script>

<template>
  <div class="stock-view">

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
    <div v-if="!loading && !loadError && filteredRows.length === 0" class="stock-view__empty">
      <p class="stock-view__empty-title">재고 없음</p>
      <p class="stock-view__empty-desc">
        {{ includeZero ? '등록된 재고가 없습니다.' : '현재 재고가 없습니다. 소진 포함을 선택하면 볼 수 있습니다.' }}
      </p>
    </div>

    <!-- 재고 목록 -->
    <div class="stock-view__list">
      <OdsCard
        v-for="row in filteredRows"
        :key="`${row.item_cd}_${row.variety_cd}_${row.grade_cd}_${row.size_cd}_${row.weight}_${row.storage_dt}`"
        class="stock-view__card"
        @click="openLog(row)"
      >
        <!-- 카드 헤더 -->
        <div class="stock-view__card-head">
          <span class="stock-view__card-title">{{ cardTitle(row) }}</span>
          <template v-if="isRaw">
            <span class="stock-view__card-sub">{{ row.storage_dt }}</span>
          </template>
        </div>

        <!-- 수량 표시 (Level 4) -->
        <div class="stock-view__qty-row">
          <!-- 가용재고가 핵심 -->
          <div class="stock-view__qty-main">
            <span class="stock-view__qty-val">{{ row.available_qty }}</span>
            <span class="stock-view__qty-unit">{{ stockUnit(row.item_cd) }}</span>
            <span class="stock-view__qty-lbl">가용</span>
          </div>
          <!-- 현재·배정 보조 -->
          <div class="stock-view__qty-sub-row">
            <span class="stock-view__qty-sub">현재 {{ row.real_qty }}</span>
            <span v-if="row.reserved_qty > 0" class="stock-view__qty-sub">
              · 배정 {{ row.reserved_qty }}
            </span>
          </div>
        </div>

        <!-- 소진 표시 -->
        <p v-if="row.real_qty <= 0" class="stock-view__zero-badge">소진</p>
        <OdsButton
          v-if="row.item_cd !== ITEM_RAW && row.available_qty > 0"
          type="button"
          variant="secondary"
          :block="false"
          class="stock-view__sell"
          @click.stop="sellProduct(row)"
        >
          판매
        </OdsButton>
      </OdsCard>
    </div>

    <!-- 재고 이력 bottom sheet -->
    <Teleport to="body">
      <div
        v-if="logTarget"
        class="stock-log-overlay"
        role="dialog"
        aria-modal="true"
        aria-label="재고 이력"
        @click.self="closeLog"
      >
        <div class="stock-log-sheet">
          <div class="stock-log-sheet__header">
            <span class="stock-log-sheet__title">{{ cardTitle(logTarget) }} 이력</span>
            <button type="button" class="stock-log-sheet__close" aria-label="닫기" @click="closeLog">✕</button>
          </div>

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
              <span class="stock-log__type">{{ log.io_type_nm }}</span>
              <span class="stock-log__qty" :class="logQtyClass(log)">
                {{ logSign(log) }}{{ log.qty }}{{ stockUnit(log.item_cd) }}
              </span>
            </li>
          </ul>

          <!-- 현재고 요약 -->
          <div v-if="logTarget" class="stock-log-sheet__summary">
            <span>현재 {{ logTarget.real_qty }} · 배정 {{ logTarget.reserved_qty }} · 가용 {{ logTarget.available_qty }}</span>
          </div>
        </div>
      </div>
    </Teleport>

  </div>
</template>

<style scoped>
/* ── 전체 컨테이너 ────────────────────────────────────────────────── */
.stock-view {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-12);
  padding: var(--ods-space-12) var(--ods-space-16);
  min-height: 100%;
  background: var(--ods-color-bg, #FDFBF7);
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

/* ── 재고 목록 ────────────────────────────────────────────────────── */
.stock-view__list {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-8);
}
.stock-view__card {
  cursor: pointer;
  padding: var(--ods-space-12) var(--ods-space-16);
}
.stock-view__card-head {
  display: flex;
  align-items: baseline;
  gap: var(--ods-space-8);
  margin-bottom: var(--ods-space-8);
}
.stock-view__card-title {
  font: var(--ods-font-body-1);
  font-weight: 600;
  color: var(--ods-color-text);
}
.stock-view__card-sub {
  font: var(--ods-font-footnote);
  color: var(--ods-color-text-secondary);
}

/* ── 수량 표시 (Level 4) ──────────────────────────────────────────── */
.stock-view__qty-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ods-space-8);
}
.stock-view__qty-main {
  display: flex;
  align-items: baseline;
  gap: var(--ods-space-4);
}
.stock-view__qty-val {
  font-size: var(--ods-font-size-xl, 22px);
  font-weight: 700;
  color: var(--ods-color-primary);
}
.stock-view__qty-unit {
  font: var(--ods-font-body-2);
  color: var(--ods-color-text-secondary);
}
.stock-view__qty-lbl {
  font: var(--ods-font-footnote);
  color: var(--ods-color-text-secondary);
  background: var(--ods-color-primary-subtle, #f0f7f4);
  border-radius: 4px;
  padding: 1px 6px;
}
.stock-view__qty-sub-row {
  font: var(--ods-font-footnote);
  color: var(--ods-color-text-tertiary, #999);
}
.stock-view__zero-badge {
  display: inline-block;
  font: var(--ods-font-footnote);
  color: var(--ods-color-text-secondary);
  background: var(--ods-color-surface);
  border: 1px solid var(--ods-color-border);
  border-radius: 4px;
  padding: 1px 6px;
  margin-top: var(--ods-space-4);
}
.stock-view__sell {
  margin-top: var(--ods-space-8);
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
  width: 100%;
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
}
.stock-log-sheet__title {
  font: var(--ods-font-body-1);
  font-weight: 600;
  color: var(--ods-color-text);
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
  padding: var(--ods-space-16) 0;
}
.stock-log-sheet__msg--err {
  color: var(--ods-color-danger);
}
.stock-log-sheet__summary {
  border-top: 1px solid var(--ods-color-border);
  padding-top: var(--ods-space-8);
  font: var(--ods-font-footnote);
  color: var(--ods-color-text-secondary);
  text-align: right;
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
</style>
