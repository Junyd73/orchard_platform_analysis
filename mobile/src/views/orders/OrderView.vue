<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'

import { fetchCommonCodes } from '@/api/commonCodes'
import { fetchOrders } from '@/api/orders'
import { ApiClientError } from '@/api/client'
import iconPlus from '@/assets/ods/work-log/icon-plus.svg'
import OdsAppBar from '@/components/ods/OdsAppBar.vue'
import OdsBottomNav from '@/components/ods/OdsBottomNav.vue'
import OdsButton from '@/components/ods/OdsButton.vue'
import OdsCard from '@/components/ods/OdsCard.vue'
import OdsEmptyState from '@/components/ods/OdsEmptyState.vue'
import OdsFab from '@/components/ods/OdsFab.vue'
import OdsSegmented from '@/components/ods/OdsSegmented.vue'
import OdsSkeleton from '@/components/ods/OdsSkeleton.vue'
import OrderLookupPanel, {
  type StatusFilterOption,
} from '@/views/orders/OrderLookupPanel.vue'
import {
  CODE_PARENT_STATUS,
  LABEL_FAB_ORDER,
  LABEL_FAB_SALES,
  LABEL_PAGE_NEXT,
  LABEL_PAGE_PREV,
  LABEL_SEGMENT_ARIA,
  LABEL_STATUS_ALL,
  MSG_ORDER_EMPTY_DESC,
  MSG_ORDER_EMPTY_FILTER,
  MSG_ORDER_EMPTY_FILTER_DESC,
  MSG_ORDER_EMPTY_TITLE,
  MSG_ORDER_LOAD_FAIL,
  MSG_SALES_EMPTY_DESC,
  MSG_SALES_EMPTY_TITLE,
  MSG_STAGE_LATER,
  ORDER_LIST_PAGE_SIZE,
  ORDER_SALES_SEGMENT_OPTIONS,
  ORDER_STATUS_FILTER_FALLBACK,
  STATUS_FILTER_ALL,
  TAB_ORDER,
  formatOrderAmt,
} from '@/views/orders/ordersConstants'
import {
  defaultOrderLookupRange,
  rangeForQuickKey,
  yearStartIso,
} from '@/views/orders/orderLookup'
import { todayIso } from '@/views/work-log/workLogConstants'
import { useAppStore } from '@/composables/stores/app'
import type { OrderListItem } from '@/types/order'

const router = useRouter()
const route = useRoute()
const { farmCd } = storeToRefs(useAppStore())

const segment = ref<string>(TAB_ORDER)
const toastMsg = ref('')
let toastTimer = 0

const initialRange = defaultOrderLookupRange()
const filterExpanded = ref(false)
const draftFrom = ref(initialRange.from)
const draftTo = ref(initialRange.to)
const draftStatus = ref(STATUS_FILTER_ALL)
const draftKeyword = ref('')
const appliedFrom = ref(initialRange.from)
const appliedTo = ref(initialRange.to)
const appliedStatus = ref(STATUS_FILTER_ALL)
const appliedKeyword = ref('')
const page = ref(1)
const total = ref(0)
const pageSize = ref(ORDER_LIST_PAGE_SIZE)

const loading = ref(true)
const loadError = ref('')
const orders = ref<OrderListItem[]>([])
const statusOptions = ref<StatusFilterOption[]>(
  ORDER_STATUS_FILTER_FALLBACK.map((row) => ({
    value: row.value,
    label: row.label,
  })),
)

const segmentOptions = ORDER_SALES_SEGMENT_OPTIONS.map((opt) => ({
  value: opt.value,
  label: opt.label,
}))

const isOrderTab = computed(() => segment.value === TAB_ORDER)
const fabLabel = computed(() => (isOrderTab.value ? LABEL_FAB_ORDER : LABEL_FAB_SALES))
const statusSelectOptions = computed(() => [
  { value: STATUS_FILTER_ALL, label: LABEL_STATUS_ALL },
  ...statusOptions.value,
])
const hasExtraFilter = computed(() => {
  const today = todayIso()
  return (
    Boolean(appliedKeyword.value.trim()) ||
    Boolean(appliedStatus.value) ||
    appliedFrom.value !== yearStartIso(today) ||
    appliedTo.value !== today
  )
})
const emptyTitle = computed(() => {
  if (!isOrderTab.value) return MSG_SALES_EMPTY_TITLE
  return hasExtraFilter.value ? MSG_ORDER_EMPTY_FILTER : MSG_ORDER_EMPTY_TITLE
})
const emptyDesc = computed(() => {
  if (!isOrderTab.value) return MSG_SALES_EMPTY_DESC
  return hasExtraFilter.value ? MSG_ORDER_EMPTY_FILTER_DESC : MSG_ORDER_EMPTY_DESC
})
const showOrderEmpty = computed(
  () => isOrderTab.value && !loading.value && !loadError.value && orders.value.length === 0,
)
const showOrderList = computed(
  () => isOrderTab.value && !loading.value && !loadError.value && orders.value.length > 0,
)
const totalPages = computed(() =>
  Math.max(1, Math.ceil(total.value / Math.max(1, pageSize.value))),
)
const showPager = computed(
  () => isOrderTab.value && !loading.value && !loadError.value && total.value > 0,
)

function showToast(msg: string) {
  toastMsg.value = msg
  window.clearTimeout(toastTimer)
  toastTimer = window.setTimeout(() => {
    toastMsg.value = ''
  }, 1800)
}

async function loadStatusOptions() {
  try {
    const rows = await fetchCommonCodes(farmCd.value, CODE_PARENT_STATUS)
    const mapped = rows
      .filter((row) => String(row.code_cd || '').length === 8)
      .map((row) => ({
        value: row.code_cd,
        label: row.code_nm || row.code_cd,
      }))
    if (mapped.length) statusOptions.value = mapped
  } catch {
    /* ST01 fallback 유지 */
  }
}

async function loadOrders() {
  loading.value = true
  loadError.value = ''
  try {
    const res = await fetchOrders(farmCd.value, {
      from_date: appliedFrom.value,
      to_date: appliedTo.value,
      status_cd: appliedStatus.value || undefined,
      keyword: appliedKeyword.value.trim() || undefined,
      page: page.value,
      page_size: ORDER_LIST_PAGE_SIZE,
    })
    orders.value = res.items
    total.value = res.total
    page.value = res.page
    pageSize.value = res.page_size
  } catch (err) {
    orders.value = []
    total.value = 0
    loadError.value = err instanceof ApiClientError ? err.message : MSG_ORDER_LOAD_FAIL
  } finally {
    loading.value = false
  }
}

function applyLookup() {
  appliedFrom.value = draftFrom.value
  appliedTo.value = draftTo.value
  appliedStatus.value = draftStatus.value
  appliedKeyword.value = draftKeyword.value.trim()
  draftKeyword.value = appliedKeyword.value
  page.value = 1
  void loadOrders()
}

function resetLookup() {
  const range = defaultOrderLookupRange()
  draftFrom.value = range.from
  draftTo.value = range.to
  draftStatus.value = STATUS_FILTER_ALL
  draftKeyword.value = ''
  applyLookup()
}

function onQuickRange(key: string) {
  const range = rangeForQuickKey(key)
  draftFrom.value = range.from
  draftTo.value = range.to
}

function goPrevPage() {
  if (page.value <= 1) return
  page.value -= 1
  void loadOrders()
}

function goNextPage() {
  if (page.value >= totalPages.value) return
  page.value += 1
  void loadOrders()
}

function onFab() {
  if (isOrderTab.value) {
    void router.push({ name: 'order-new' })
    return
  }
  showToast(MSG_STAGE_LATER)
}

function openOrder(orderNo: string) {
  void router.push({ name: 'order-detail', params: { orderNo } })
}

function isOrdersListPath(path: string): boolean {
  return path === '/orders' || path.startsWith('/orders?')
}

watch(
  () => route.path,
  (path) => {
    if (isOrdersListPath(path)) void loadOrders()
  },
)

watch(farmCd, () => {
  if (isOrdersListPath(route.path)) {
    void loadStatusOptions()
    void loadOrders()
  }
})

onMounted(() => {
  if (isOrdersListPath(route.path)) {
    void loadStatusOptions()
    void loadOrders()
  }
})
</script>

<template>
  <div class="page">
    <main class="content ods-page-content">
      <OdsAppBar />
      <header class="head">
        <OdsSegmented
          v-model="segment"
          :options="segmentOptions"
          :aria-label="LABEL_SEGMENT_ARIA"
        />
      </header>
      <OrderLookupPanel
        v-if="isOrderTab"
        v-model:expanded="filterExpanded"
        v-model:from-date="draftFrom"
        v-model:to-date="draftTo"
        v-model:status-cd="draftStatus"
        v-model:keyword="draftKeyword"
        :applied-from="appliedFrom"
        :applied-to="appliedTo"
        :status-options="statusSelectOptions"
        :searching="loading"
        @apply="applyLookup"
        @reset="resetLookup"
        @quick-range="onQuickRange"
      />
      <template v-if="isOrderTab && loading">
        <OdsSkeleton />
      </template>
      <p v-else-if="isOrderTab && loadError" class="err" role="alert">{{ loadError }}</p>
      <OdsEmptyState v-else-if="showOrderEmpty" :title="emptyTitle" :description="emptyDesc" />
      <ul v-else-if="showOrderList" class="list">
        <li v-for="row in orders" :key="row.order_no">
          <button type="button" class="card-btn" @click="openOrder(row.order_no)">
            <OdsCard>
              <div class="row-top">
                <strong>{{ row.customer || row.custm_id }}</strong>
                <span class="status">{{ row.status_nm || row.status_cd }}</span>
              </div>
              <p class="meta">{{ row.order_no }} · {{ row.order_dt }}</p>
              <p class="meta">
                수량 {{ formatOrderAmt(row.total_qty) }} ·
                {{ formatOrderAmt(row.total_amt) }}원
                <template v-if="row.pre_pay_amt">
                  · 선입 {{ formatOrderAmt(row.pre_pay_amt) }}원
                </template>
              </p>
            </OdsCard>
          </button>
        </li>
      </ul>
      <div v-if="showPager" class="pager">
        <OdsButton
          variant="secondary"
          :block="false"
          :disabled="page <= 1 || loading"
          @click="goPrevPage"
        >
          {{ LABEL_PAGE_PREV }}
        </OdsButton>
        <span class="pager__pos">{{ page }} / {{ totalPages }}</span>
        <OdsButton
          variant="secondary"
          :block="false"
          :disabled="page >= totalPages || loading"
          @click="goNextPage"
        >
          {{ LABEL_PAGE_NEXT }}
        </OdsButton>
      </div>
      <OdsEmptyState v-else-if="!isOrderTab" :title="emptyTitle" :description="emptyDesc" />
    </main>
    <!-- eslint-disable vue/attribute-hyphenation -->
    <OdsFab :label="fabLabel" :ariaLabel="fabLabel" @click="onFab">
      <img :src="iconPlus" alt="">
    </OdsFab>
    <!-- eslint-enable vue/attribute-hyphenation -->
    <p v-if="toastMsg" class="toast" role="status">{{ toastMsg }}</p>
    <OdsBottomNav />
  </div>
</template>

<style scoped>
.page {
  min-height: 100dvh;
  background: var(--ods-color-bg-muted);
  padding-bottom: calc(140px + env(safe-area-inset-bottom));
}
.content {
  --ods-page-content-gap: var(--ods-space-12);
}
.head {
  margin: 0;
}
.head :deep(.ods-segmented) {
  width: 100%;
  max-width: none;
}
.list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-12);
}
.card-btn {
  display: block;
  width: 100%;
  padding: 0;
  border: 0;
  background: transparent;
  text-align: left;
  color: inherit;
}
.row-top {
  display: flex;
  justify-content: space-between;
  gap: var(--ods-space-8);
  align-items: baseline;
}
.status {
  font: var(--ods-font-form-help);
  color: var(--ods-color-text-secondary);
}
.meta {
  margin: var(--ods-space-8) 0 0;
  font: var(--ods-font-form-help);
  color: var(--ods-color-text-secondary);
}
.pager {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ods-space-8);
}
.pager :deep(.ods-btn) {
  min-width: var(--ods-touch-min);
  padding: 0 var(--ods-space-16);
}
.pager__pos {
  font: var(--ods-font-form-value);
  font-weight: 700;
  color: var(--ods-color-text);
  font-variant-numeric: tabular-nums;
}
.err {
  margin: 0;
  color: var(--ods-color-danger);
  font: var(--ods-font-form-help);
}
.toast {
  position: fixed;
  left: 50%;
  bottom: calc(var(--ods-space-64) + var(--ods-space-8) + env(safe-area-inset-bottom));
  transform: translateX(-50%);
  z-index: 60;
  margin: 0;
  padding: var(--ods-space-8) var(--ods-space-16);
  border-radius: var(--ods-radius-button);
  background: var(--ods-color-gray-900);
  color: var(--ods-color-white);
  font: var(--ods-font-form-help);
}
</style>
