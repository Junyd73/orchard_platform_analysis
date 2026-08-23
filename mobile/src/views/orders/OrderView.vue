<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'

import { fetchCommonCodes } from '@/api/commonCodes'
import { fetchOrders } from '@/api/orders'
import { fetchSales } from '@/api/sales'
import { ApiClientError } from '@/api/client'
import iconPlus from '@/assets/ods/work-log/icon-plus.svg'
import OdsAppBar from '@/components/ods/OdsAppBar.vue'
import OdsBadge from '@/components/ods/OdsBadge.vue'
import OdsBottomNav from '@/components/ods/OdsBottomNav.vue'
import OdsButton from '@/components/ods/OdsButton.vue'
import OdsEmptyState from '@/components/ods/OdsEmptyState.vue'
import OdsFab from '@/components/ods/OdsFab.vue'
import OdsSkeleton from '@/components/ods/OdsSkeleton.vue'
import OrderLookupPanel, {
  type StatusFilterOption,
} from '@/views/orders/OrderLookupPanel.vue'
import SalesLookupPanel from '@/views/sales/SalesLookupPanel.vue'
import {
  MSG_SALES_EMPTY_FILTER,
  MSG_SALES_EMPTY_FILTER_DESC,
  MSG_SALES_LOAD_FAIL,
  SALES_LIST_PAGE_SIZE,
  paymentStatusLabelOf,
  paymentStatusToneOf,
  salesCustomerLabel,
  salesListAmountLine,
  salesListSecondaryText,
  salesStatusLabelOf,
  salesStatusToneOf,
} from '@/views/sales/salesConstants'
import PackProdPanel from '@/views/production/PackProdPanel.vue'
import StockView from '@/views/stock/StockView.vue'
import {
  CODE_PARENT_STATUS,
  LABEL_FAB_ORDER,
  LABEL_FAB_SALES,
  LABEL_ORDER_LIST_COL_CUSTOMER,
  LABEL_ORDER_LIST_COL_QTY,
  LABEL_ORDER_LIST_COL_SHIP,
  LABEL_ORDER_LIST_COL_STATUS,
  LABEL_PAGE_NEXT,
  LABEL_PAGE_PREV,
  LABEL_SEGMENT_ARIA,
  LABEL_STATUS_ALL,
  MSG_ORDER_EMPTY_DESC,
  MSG_ORDER_EMPTY_FILTER,
  MSG_ORDER_EMPTY_FILTER_DESC,
  MSG_ORDER_EMPTY_TITLE,
  MSG_ORDER_LOAD_FAIL,
  MSG_PACK_PROD_EMPTY_DESC,
  MSG_PACK_PROD_EMPTY_TITLE,
  MSG_SALES_EMPTY_DESC,
  MSG_SALES_EMPTY_TITLE,
  MSG_STOCK_EMPTY_DESC,
  MSG_STOCK_EMPTY_TITLE,
  ORDER_LIST_PAGE_SIZE,
  ORDER_SALES_SEGMENT_OPTIONS,
  ORDER_STATUS_FILTER_FALLBACK,
  STATUS_FILTER_ALL,
  TAB_ORDER,
  TAB_PACK_PROD,
  TAB_SALES,
  TAB_STOCK,
  formatOrderAmt,
  orderListSecondaryText,
  orderListShipRemainText,
  orderStatusLabelOf,
  orderStatusToneOf,
} from '@/views/orders/ordersConstants'
import {
  defaultOrderLookupRange,
  rangeForQuickKey,
  yearStartIso,
} from '@/views/orders/orderLookup'
import { todayIso } from '@/views/work-log/workLogConstants'
import { useAppStore } from '@/composables/stores/app'
import { useSalesPrefillStore } from '@/composables/stores/salesPrefill'
import type { OrderListItem } from '@/types/order'
import type { SalesListItem } from '@/types/sales'

const router = useRouter()
const route = useRoute()
const { farmCd } = storeToRefs(useAppStore())
const salesPrefill = useSalesPrefillStore()

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

const isPackProdTab = computed(() => segment.value === TAB_PACK_PROD)
const isStockTab = computed(() => segment.value === TAB_STOCK)
const isOrderTab = computed(() => segment.value === TAB_ORDER)
const isSalesTab = computed(() => segment.value === TAB_SALES)
const showFab = computed(() => isOrderTab.value || isSalesTab.value)
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
  if (isPackProdTab.value) return MSG_PACK_PROD_EMPTY_TITLE
  if (isStockTab.value) return MSG_STOCK_EMPTY_TITLE
  if (isSalesTab.value) return MSG_SALES_EMPTY_TITLE
  return hasExtraFilter.value ? MSG_ORDER_EMPTY_FILTER : MSG_ORDER_EMPTY_TITLE
})
const emptyDesc = computed(() => {
  if (isPackProdTab.value) return MSG_PACK_PROD_EMPTY_DESC
  if (isStockTab.value) return MSG_STOCK_EMPTY_DESC
  if (isSalesTab.value) return MSG_SALES_EMPTY_DESC
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

const salesInitialRange = defaultOrderLookupRange()
const salesFilterExpanded = ref(false)
const salesDraftFrom = ref(salesInitialRange.from)
const salesDraftTo = ref(salesInitialRange.to)
const salesDraftStatus = ref('')
const salesDraftPaymentStatus = ref('')
const salesDraftKeyword = ref('')
const salesAppliedFrom = ref(salesInitialRange.from)
const salesAppliedTo = ref(salesInitialRange.to)
const salesAppliedStatus = ref('')
const salesAppliedPaymentStatus = ref('')
const salesAppliedKeyword = ref('')
const salesPage = ref(1)
const salesTotal = ref(0)
const salesPageSize = ref(SALES_LIST_PAGE_SIZE)

const salesLoading = ref(false)
const salesLoadError = ref('')
const salesItems = ref<SalesListItem[]>([])

const hasExtraSalesFilter = computed(() => {
  const today = todayIso()
  return (
    Boolean(salesAppliedKeyword.value.trim()) ||
    Boolean(salesAppliedStatus.value) ||
    Boolean(salesAppliedPaymentStatus.value) ||
    salesAppliedFrom.value !== yearStartIso(today) ||
    salesAppliedTo.value !== today
  )
})
const showSalesEmpty = computed(
  () =>
    isSalesTab.value &&
    !salesLoading.value &&
    !salesLoadError.value &&
    salesItems.value.length === 0,
)
const showSalesList = computed(
  () =>
    isSalesTab.value &&
    !salesLoading.value &&
    !salesLoadError.value &&
    salesItems.value.length > 0,
)
const salesTotalPages = computed(() =>
  Math.max(1, Math.ceil(salesTotal.value / Math.max(1, salesPageSize.value))),
)
const showSalesPager = computed(
  () =>
    isSalesTab.value &&
    !salesLoading.value &&
    !salesLoadError.value &&
    salesTotal.value > 0,
)
const salesEmptyTitle = computed(() =>
  hasExtraSalesFilter.value ? MSG_SALES_EMPTY_FILTER : MSG_SALES_EMPTY_TITLE,
)
const salesEmptyDesc = computed(() =>
  hasExtraSalesFilter.value ? MSG_SALES_EMPTY_FILTER_DESC : MSG_SALES_EMPTY_DESC,
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

async function loadSales() {
  salesLoading.value = true
  salesLoadError.value = ''
  try {
    const res = await fetchSales(farmCd.value, {
      from_date: salesAppliedFrom.value,
      to_date: salesAppliedTo.value,
      sales_status: salesAppliedStatus.value || undefined,
      payment_status: salesAppliedPaymentStatus.value || undefined,
      keyword: salesAppliedKeyword.value.trim() || undefined,
      page: salesPage.value,
      page_size: SALES_LIST_PAGE_SIZE,
    })
    salesItems.value = res.items
    salesTotal.value = res.total
    salesPage.value = res.page
    salesPageSize.value = res.page_size
  } catch (err) {
    salesItems.value = []
    salesTotal.value = 0
    salesLoadError.value =
      err instanceof ApiClientError ? err.message : MSG_SALES_LOAD_FAIL
  } finally {
    salesLoading.value = false
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

function applySalesLookup() {
  salesAppliedFrom.value = salesDraftFrom.value
  salesAppliedTo.value = salesDraftTo.value
  salesAppliedStatus.value = salesDraftStatus.value
  salesAppliedPaymentStatus.value = salesDraftPaymentStatus.value
  salesAppliedKeyword.value = salesDraftKeyword.value.trim()
  salesDraftKeyword.value = salesAppliedKeyword.value
  salesPage.value = 1
  void loadSales()
}

function resetSalesLookup() {
  const range = defaultOrderLookupRange()
  salesDraftFrom.value = range.from
  salesDraftTo.value = range.to
  salesDraftStatus.value = ''
  salesDraftPaymentStatus.value = ''
  salesDraftKeyword.value = ''
  applySalesLookup()
}

function onSalesQuickRange(key: string) {
  const range = rangeForQuickKey(key)
  salesDraftFrom.value = range.from
  salesDraftTo.value = range.to
}

function goSalesPrevPage() {
  if (salesPage.value <= 1) return
  salesPage.value -= 1
  void loadSales()
}

function goSalesNextPage() {
  if (salesPage.value >= salesTotalPages.value) return
  salesPage.value += 1
  void loadSales()
}

function reloadActiveTabList() {
  if (segment.value === TAB_SALES) void loadSales()
  else if (segment.value === TAB_ORDER) void loadOrders()
}

function onGoSalesFromProduction() {
  void router.push({ name: 'ship-confirm' })
}

function onProductionToast(msg: string) {
  showToast(msg)
}

function onFab() {
  if (isOrderTab.value) {
    void router.push({ name: 'order-new' })
    return
  }
  if (salesPrefill.shipLines.length) {
    void router.push({ name: 'ship-confirm' })
    return
  }
  segment.value = TAB_STOCK
  showToast('상품 재고에서 판매를 선택하세요.')
}

function openOrder(orderNo: string) {
  void router.push({ name: 'order-detail', params: { orderNo } })
}

function isOrdersListPath(path: string): boolean {
  return path === '/orders' || path.startsWith('/orders?')
}

function applyTabQuery(tab: unknown) {
  const v = String(tab || '')
  if (v === TAB_STOCK || v === TAB_SALES || v === TAB_ORDER || v === TAB_PACK_PROD) {
    segment.value = v
  }
}

watch(
  () => route.path,
  (path) => {
    if (isOrdersListPath(path)) reloadActiveTabList()
  },
)

watch(segment, (tab, prev) => {
  if (!isOrdersListPath(route.path)) return
  if (tab === TAB_SALES && prev !== TAB_SALES) void loadSales()
  if (tab === TAB_ORDER && prev !== TAB_ORDER) void loadOrders()
})

watch(
  () => route.query.tab,
  (tab) => {
    applyTabQuery(tab)
    if (String(tab) === TAB_STOCK && isOrdersListPath(route.path)) {
      /* StockView watch farmCd already loads */
    }
  },
)

watch(farmCd, () => {
  if (isOrdersListPath(route.path)) {
    void loadStatusOptions()
    reloadActiveTabList()
  }
})

onMounted(() => {
  applyTabQuery(route.query.tab)
  if (isOrdersListPath(route.path)) {
    void loadStatusOptions()
    reloadActiveTabList()
  }
})
</script>

<template>
  <div class="page">
    <main class="content ods-page-content">
      <OdsAppBar />
      <header class="head">
        <nav class="tab-bar" role="tablist" :aria-label="LABEL_SEGMENT_ARIA">
          <button
            v-for="opt in segmentOptions"
            :key="opt.value"
            type="button"
            role="tab"
            class="tab-bar__btn"
            :class="{ 'tab-bar__btn--on': segment === opt.value }"
            :aria-selected="segment === opt.value"
            @click="segment = opt.value"
          >
            {{ opt.label }}
          </button>
        </nav>
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
      <ul v-else-if="showOrderList" class="order-list">
        <li class="order-list__head" aria-hidden="true">
          <span class="order-list__head-cust">{{ LABEL_ORDER_LIST_COL_CUSTOMER }}</span>
          <span class="order-list__head-qty">{{ LABEL_ORDER_LIST_COL_QTY }}</span>
          <span class="order-list__head-ship">{{ LABEL_ORDER_LIST_COL_SHIP }}</span>
          <span class="order-list__head-status">{{ LABEL_ORDER_LIST_COL_STATUS }}</span>
        </li>
        <li v-for="row in orders" :key="row.order_no" class="order-list__item">
          <button
            type="button"
            class="order-list__row"
            :aria-label="`${row.customer || row.custm_id} ${row.order_no}`"
            @click="openOrder(row.order_no)"
          >
            <div class="order-list__line1">
              <span class="order-list__cust">{{ row.customer || row.custm_id }}</span>
              <span class="order-list__qty">{{ formatOrderAmt(row.total_qty) }}</span>
              <span class="order-list__ship">{{ orderListShipRemainText(row) }}</span>
              <OdsBadge class="order-list__status" :tone="orderStatusToneOf(row.status_cd)">
                {{ orderStatusLabelOf(row.status_cd) }}
              </OdsBadge>
            </div>
            <div class="order-list__line2">
              <span class="order-list__meta">{{ orderListSecondaryText(row) }}</span>
              <span class="order-list__amt">{{ formatOrderAmt(row.total_amt) }}원</span>
            </div>
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
      <PackProdPanel
        v-else-if="isPackProdTab"
        @toast="onProductionToast"
        @go-sales="onGoSalesFromProduction"
      />
      <StockView v-else-if="isStockTab" :key="`stock-${farmCd}`" />
      <template v-else-if="isSalesTab">
        <SalesLookupPanel
          v-model:expanded="salesFilterExpanded"
          v-model:from-date="salesDraftFrom"
          v-model:to-date="salesDraftTo"
          v-model:sales-status="salesDraftStatus"
          v-model:payment-status="salesDraftPaymentStatus"
          v-model:keyword="salesDraftKeyword"
          :applied-from="salesAppliedFrom"
          :applied-to="salesAppliedTo"
          :searching="salesLoading"
          @apply="applySalesLookup"
          @reset="resetSalesLookup"
          @quick-range="onSalesQuickRange"
        />
        <OdsSkeleton v-if="salesLoading" />
        <p v-else-if="salesLoadError" class="err" role="alert">{{ salesLoadError }}</p>
        <OdsEmptyState
          v-else-if="showSalesEmpty"
          :title="salesEmptyTitle"
          :description="salesEmptyDesc"
        />
        <ul v-else-if="showSalesList" class="sales-list">
          <li v-for="row in salesItems" :key="row.sales_no" class="sales-list__item">
            <div class="sales-list__row">
              <div class="sales-list__line1">
                <span class="sales-list__cust">{{ salesCustomerLabel(row) }}</span>
                <span class="sales-list__amt">{{ salesListAmountLine(row) }}</span>
                <OdsBadge
                  class="sales-list__pay"
                  :tone="paymentStatusToneOf(row)"
                >
                  {{ paymentStatusLabelOf(row) }}
                </OdsBadge>
              </div>
              <div class="sales-list__line2">
                <span class="sales-list__meta">{{ salesListSecondaryText(row) }}</span>
                <OdsBadge
                  class="sales-list__status"
                  :tone="salesStatusToneOf(row.sales_status)"
                >
                  {{ salesStatusLabelOf(row.sales_status) }}
                </OdsBadge>
              </div>
            </div>
          </li>
        </ul>
        <div v-if="showSalesPager" class="pager">
          <OdsButton
            variant="secondary"
            :block="false"
            :disabled="salesPage <= 1 || salesLoading"
            @click="goSalesPrevPage"
          >
            {{ LABEL_PAGE_PREV }}
          </OdsButton>
          <span class="pager__pos">{{ salesPage }} / {{ salesTotalPages }}</span>
          <OdsButton
            variant="secondary"
            :block="false"
            :disabled="salesPage >= salesTotalPages || salesLoading"
            @click="goSalesNextPage"
          >
            {{ LABEL_PAGE_NEXT }}
          </OdsButton>
        </div>
      </template>
    </main>
    <!-- eslint-disable vue/attribute-hyphenation -->
    <OdsFab v-if="showFab" :label="fabLabel" :ariaLabel="fabLabel" @click="onFab">
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

/* text tab + underline */
.tab-bar {
  display: grid;
  grid-auto-flow: column;
  grid-auto-columns: 1fr;
  border-bottom: 1px solid var(--ods-color-border);
}
.tab-bar__btn {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 44px;
  padding: 0 var(--ods-space-4);
  border: none;
  border-bottom: 2px solid transparent;
  background: transparent;
  font: var(--ods-font-body-2);
  color: var(--ods-color-text-secondary);
  white-space: nowrap;
  cursor: pointer;
  margin-bottom: -1px;
}
.tab-bar__btn--on {
  color: var(--ods-color-primary);
  border-bottom-color: var(--ods-color-primary);
  font-weight: 700;
}
.order-list {
  --order-col-qty: 2.75rem;
  --order-col-ship: 3.5rem;
  --order-col-status: 4.25rem;
  list-style: none;
  /* 페이지 padding 유지 — 재고 목록(ods-page-content 안쪽 폭)과 동일 */
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0;
  background: var(--ods-color-white, #fff);
}
.order-list__head,
.order-list__line1 {
  display: grid;
  grid-template-columns:
    minmax(0, 1fr)
    var(--order-col-qty)
    var(--order-col-ship)
    var(--order-col-status);
  align-items: center;
  column-gap: var(--ods-space-6);
  /* 재고 row와 동일: 리스트 가장자리 + 16 → 텍스트 들여쓰기 */
  padding: 0 var(--ods-space-16);
}
.order-list__head {
  min-height: 32px;
  border-bottom: 1px solid var(--ods-color-border);
  color: var(--ods-color-text-secondary);
  font: var(--ods-font-caption);
  font-weight: 600;
  user-select: none;
}
.order-list__head-cust {
  min-width: 0;
  white-space: nowrap;
}
.order-list__head-qty,
.order-list__head-ship {
  text-align: right;
  white-space: nowrap;
}
.order-list__head-status {
  text-align: right;
  white-space: nowrap;
}
.order-list__item {
  border-bottom: 1px solid var(--ods-color-border);
}
.order-list__item:last-child {
  border-bottom: none;
}
.order-list__row {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 2px;
  width: 100%;
  min-height: 60px;
  padding: var(--ods-space-8) 0;
  border: 0;
  background: transparent;
  text-align: left;
  color: inherit;
  cursor: pointer;
}
.order-list__row:active {
  background: var(--ods-color-primary-subtle, #f0f7f4);
}
.order-list__line1 {
  font: var(--ods-font-body-2);
}
.order-list__cust {
  min-width: 0;
  font-weight: 600;
  color: var(--ods-color-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.order-list__qty,
.order-list__ship {
  text-align: right;
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
  color: var(--ods-color-text);
}
.order-list__status {
  justify-self: end;
  white-space: nowrap;
}
.order-list__line2 {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--ods-space-8);
  padding: 0 var(--ods-space-16);
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
}
.order-list__meta {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.order-list__amt {
  flex-shrink: 0;
  white-space: nowrap;
  text-align: right;
  font-variant-numeric: tabular-nums;
  color: var(--ods-color-text);
  font-weight: 600;
}
.sales-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0;
  background: var(--ods-color-white, #fff);
}
.sales-list__item {
  border-bottom: 1px solid var(--ods-color-border);
}
.sales-list__item:last-child {
  border-bottom: none;
}
.sales-list__row {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 2px;
  width: 100%;
  min-height: 60px;
  padding: var(--ods-space-8) 0;
}
.sales-list__line1 {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.35fr) auto;
  align-items: center;
  column-gap: var(--ods-space-6);
  padding: 0 var(--ods-space-16);
  font: var(--ods-font-body-2);
}
.sales-list__cust {
  min-width: 0;
  font-weight: 600;
  color: var(--ods-color-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.sales-list__amt {
  min-width: 0;
  text-align: right;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-variant-numeric: tabular-nums;
  color: var(--ods-color-text);
}
.sales-list__pay {
  justify-self: end;
  white-space: nowrap;
}
.sales-list__line2 {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--ods-space-8);
  padding: 0 var(--ods-space-16);
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
}
.sales-list__meta {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sales-list__status {
  flex-shrink: 0;
  white-space: nowrap;
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
