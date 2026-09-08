<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'

import { createSalePayment, fetchSaleDetail, fetchSalePayments } from '@/api/sales'
import { fetchWorkLogAccountCodes, type WorkLogAccountCodeOption } from '@/api/workLogs'
import { ApiClientError } from '@/api/client'
import iconFarm from '@/assets/ods/common/icon-farm.svg'
import iconChevronDown from '@/assets/ods/common/icon-chevron-down.svg'
import iconStock from '@/assets/ods/pesticide/icon-kpi-stock.svg'
import iconExpense from '@/assets/ods/work-log/icon-expense.svg'
import OdsAppBar from '@/components/ods/OdsAppBar.vue'
import OdsBadge from '@/components/ods/OdsBadge.vue'
import OdsBottomNav from '@/components/ods/OdsBottomNav.vue'
import OdsButton from '@/components/ods/OdsButton.vue'
import OdsCard from '@/components/ods/OdsCard.vue'
import OdsFormField from '@/components/ods/OdsFormField.vue'
import OdsInput from '@/components/ods/OdsInput.vue'
import OdsSelect from '@/components/ods/OdsSelect.vue'
import OdsSkeleton from '@/components/ods/OdsSkeleton.vue'
import { formatOrderAmt, TAB_SALES } from '@/views/orders/ordersConstants'
import { num } from '@/views/orders/orderFormModel'
import {
  LABEL_LINE_AMOUNT,
  LABEL_ORDER_NO,
  LABEL_PAID_AMOUNT,
  LABEL_PAYMENT_HISTORY,
  LABEL_PAYMENT_REGISTER,
  LABEL_PAY_AMOUNT,
  LABEL_PAY_CANCEL,
  LABEL_PAY_DT,
  LABEL_PAY_DT_COL,
  LABEL_PAY_MEMO,
  LABEL_PAY_METHOD,
  LABEL_PAY_METHOD_COL,
  LABEL_PAY_SUBMIT,
  LABEL_PAY_TOTAL,
  LABEL_PRODUCT_SPEC,
  LABEL_PRODUCTS_LESS,
  LABEL_PRODUCTS_MORE,
  LABEL_QTY,
  LABEL_SALES_AMOUNT,
  LABEL_SALES_DETAIL,
  LABEL_SALES_PARTY,
  LABEL_SALES_PRODUCTS,
  LABEL_SALES_ROUTE,
  LABEL_UNIT_PRICE,
  LABEL_UNPAID_AMOUNT,
  MSG_PAYMENT_HISTORY_EMPTY,
  MSG_PAYMENT_HISTORY_LOAD_FAIL,
  MSG_PAYMENT_RESULT_CHECK,
  MSG_PAY_AMOUNT_INVALID,
  MSG_PAY_METHOD_REQUIRED,
  MSG_SALES_DETAIL_LOAD_FAIL,
  PAY_METHOD_ACCT_LEVEL,
  PAY_METHOD_ACCT_PREFIX,
  SALES_DETAIL_PRODUCT_PREVIEW,
  SALES_STATUS_CONFIRMED,
  groupSalesDetailLines,
  paymentMemoText,
  paymentStatusLabelOf,
  paymentStatusToneOf,
  salesCustomerLabel,
  salesDetailProductText,
  salesProductsCountLabel,
  salesRouteLabel,
  salesStatusLabelOf,
  salesStatusToneOf,
} from '@/views/sales/salesConstants'
import { todayBizIso } from '@/shared/bizDate'
import { useAppStore } from '@/composables/stores/app'
import type { SalesDetail, SalesPaymentItem } from '@/types/sales'

const route = useRoute()
const router = useRouter()
const { farmCd } = storeToRefs(useAppStore())

const loading = ref(true)
const errorMsg = ref('')
const detail = ref<SalesDetail | null>(null)

const paymentLoading = ref(false)
const paymentError = ref('')
const payments = ref<SalesPaymentItem[]>([])

const showPaymentForm = ref(false)
const payDt = ref(todayBizIso())
const payAmt = ref('')
const payMethodCd = ref('')
const payMethodOptions = ref<WorkLogAccountCodeOption[]>([])
const payMethodsLoading = ref(false)
const formError = ref('')
const submitting = ref(false)
const productsExpanded = ref(false)

const salesNo = computed(() => String(route.params.salesNo || ''))
const todayIso = computed(() => todayBizIso())

const displayLines = computed(() =>
  detail.value ? groupSalesDetailLines(detail.value.lines) : [],
)

const visibleLines = computed(() => {
  if (productsExpanded.value || displayLines.value.length <= SALES_DETAIL_PRODUCT_PREVIEW) {
    return displayLines.value
  }
  return displayLines.value.slice(0, SALES_DETAIL_PRODUCT_PREVIEW)
})

const canExpandProducts = computed(
  () => displayLines.value.length > SALES_DETAIL_PRODUCT_PREVIEW,
)

const canShowPaymentButton = computed(
  () =>
    detail.value?.sales_status === SALES_STATUS_CONFIRMED &&
    (detail.value?.unpaid_amt ?? 0) > 0,
)

const canSubmitPayment = computed(() => {
  if (submitting.value || payMethodsLoading.value) return false
  if (!payDt.value.trim() || !payMethodCd.value || !payMethodOptions.value.length) return false
  const amt = num(payAmt.value)
  const unpaid = detail.value?.unpaid_amt ?? 0
  return amt > 0 && amt <= unpaid + 1e-9
})

function goBackToSalesTab() {
  void router.replace({ name: 'orders', query: { tab: TAB_SALES } })
}

function resetPaymentFormDefaults() {
  payDt.value = todayIso.value
  payAmt.value = String(detail.value?.unpaid_amt ?? '')
  payMethodCd.value = ''
  formError.value = ''
}

function openPaymentForm() {
  resetPaymentFormDefaults()
  showPaymentForm.value = true
}

function closePaymentForm() {
  if (submitting.value) return
  showPaymentForm.value = false
  formError.value = ''
}

function toggleProductsExpanded() {
  productsExpanded.value = !productsExpanded.value
}

async function loadPayMethods() {
  payMethodsLoading.value = true
  try {
    payMethodOptions.value = await fetchWorkLogAccountCodes(
      farmCd.value,
      PAY_METHOD_ACCT_PREFIX,
      PAY_METHOD_ACCT_LEVEL,
    )
  } catch {
    payMethodOptions.value = []
  } finally {
    payMethodsLoading.value = false
  }
}

async function loadDetail() {
  if (!salesNo.value) {
    detail.value = null
    errorMsg.value = MSG_SALES_DETAIL_LOAD_FAIL
    loading.value = false
    return
  }
  loading.value = true
  errorMsg.value = ''
  try {
    detail.value = await fetchSaleDetail(farmCd.value, salesNo.value)
  } catch (err) {
    detail.value = null
    errorMsg.value = err instanceof ApiClientError ? err.message : MSG_SALES_DETAIL_LOAD_FAIL
  } finally {
    loading.value = false
  }
}

async function loadPayments() {
  if (!salesNo.value) {
    payments.value = []
    paymentError.value = ''
    paymentLoading.value = false
    return
  }
  paymentLoading.value = true
  paymentError.value = ''
  try {
    const hist = await fetchSalePayments(farmCd.value, salesNo.value)
    payments.value = hist.payments
  } catch (err) {
    payments.value = []
    paymentError.value =
      err instanceof ApiClientError ? err.message : MSG_PAYMENT_HISTORY_LOAD_FAIL
  } finally {
    paymentLoading.value = false
  }
}

async function load() {
  await Promise.all([loadDetail(), loadPayments(), loadPayMethods()])
}

async function submitPayment() {
  if (submitting.value || !canSubmitPayment.value || !detail.value) return
  if (!payMethodCd.value) {
    formError.value = MSG_PAY_METHOD_REQUIRED
    return
  }
  const amt = num(payAmt.value)
  if (amt <= 0 || amt > detail.value.unpaid_amt + 1e-9) {
    formError.value = MSG_PAY_AMOUNT_INVALID
    return
  }

  submitting.value = true
  formError.value = ''
  try {
    await createSalePayment(farmCd.value, salesNo.value, {
      pay_dt: payDt.value,
      pay_amt: amt,
      pay_method_cd: payMethodCd.value,
    })
    showPaymentForm.value = false
    await loadDetail()
    await loadPayments()
  } catch (err) {
    if (err instanceof ApiClientError && err.status === 400) {
      formError.value = err.message
    } else {
      formError.value = MSG_PAYMENT_RESULT_CHECK
      await loadDetail()
      await loadPayments()
    }
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  void load()
})

watch(salesNo, () => {
  showPaymentForm.value = false
  productsExpanded.value = false
  void load()
})
</script>

<template>
  <div class="page">
    <main class="content ods-page-content">
      <OdsAppBar :show-back="true" back-mode="emit" @back="goBackToSalesTab" />
      <OdsSkeleton v-if="loading" />
      <p v-else-if="errorMsg" class="err" role="alert">{{ errorMsg }}</p>
      <template v-else-if="detail">
        <header class="page-head">
          <h1 class="page-head__title">{{ LABEL_SALES_DETAIL }}</h1>
        </header>

        <OdsCard class="party" :aria-label="LABEL_SALES_PARTY">
          <div class="party__top">
            <div class="party__main">
              <span class="party__ico-well" aria-hidden="true">
                <img class="party__ico" :src="iconFarm" alt="" />
              </span>
              <div class="party__text">
                <p class="party__lbl">{{ LABEL_SALES_PARTY }}</p>
                <h2 class="party__name">{{ salesCustomerLabel(detail) }}</h2>
                <p class="party__meta">{{ detail.sales_no }} · {{ detail.sales_dt }}</p>
              </div>
            </div>
            <div class="party__badges">
              <OdsBadge :tone="salesStatusToneOf(detail.sales_status)">
                {{ salesStatusLabelOf(detail.sales_status) }}
              </OdsBadge>
              <OdsBadge :tone="paymentStatusToneOf(detail)">
                {{ paymentStatusLabelOf(detail) }}
              </OdsBadge>
            </div>
          </div>

          <div class="party__summary">
            <dl class="party__col">
              <div class="party__row">
                <dt>{{ LABEL_SALES_ROUTE }}</dt>
                <dd>{{ salesRouteLabel(detail) }}</dd>
              </div>
              <div v-if="detail.order_no" class="party__row">
                <dt>{{ LABEL_ORDER_NO }}</dt>
                <dd>{{ detail.order_no }}</dd>
              </div>
              <div class="party__row">
                <dt>{{ LABEL_SALES_AMOUNT }}</dt>
                <dd class="party__amt">{{ formatOrderAmt(detail.tot_sales_amt) }}원</dd>
              </div>
            </dl>
            <dl class="party__col">
              <div class="party__row">
                <dt>{{ LABEL_PAID_AMOUNT }}</dt>
                <dd>{{ formatOrderAmt(detail.paid_amt) }}원</dd>
              </div>
              <div class="party__row">
                <dt>{{ LABEL_UNPAID_AMOUNT }}</dt>
                <dd class="party__amt">{{ formatOrderAmt(detail.unpaid_amt) }}원</dd>
              </div>
            </dl>
          </div>
        </OdsCard>

        <OdsCard class="products" :aria-label="LABEL_SALES_PRODUCTS">
          <div class="products__head">
            <div class="products__title-wrap">
              <img class="products__ico" :src="iconStock" alt="" aria-hidden="true" />
              <h3 class="products__title">{{ LABEL_SALES_PRODUCTS }}</h3>
            </div>
            <p class="products__count">{{ salesProductsCountLabel(displayLines.length) }}</p>
          </div>

          <table class="products__table">
            <colgroup>
              <col class="products__col--spec" />
              <col class="products__col--qty" />
              <col class="products__col--price" />
              <col class="products__col--amt" />
            </colgroup>
            <thead>
              <tr>
                <th scope="col">{{ LABEL_PRODUCT_SPEC }}</th>
                <th scope="col">{{ LABEL_QTY }}</th>
                <th scope="col">{{ LABEL_UNIT_PRICE }}</th>
                <th scope="col">{{ LABEL_LINE_AMOUNT }}</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(line, idx) in visibleLines"
                :key="`${line.sale_detail_no}-${idx}`"
              >
                <td class="products__spec">{{ salesDetailProductText(line) || '-' }}</td>
                <td class="products__num">{{ formatOrderAmt(line.qty) }}</td>
                <td class="products__num">{{ formatOrderAmt(line.unit_price) }}원</td>
                <td class="products__num">{{ formatOrderAmt(line.item_amt) }}원</td>
              </tr>
            </tbody>
          </table>

          <button
            v-if="canExpandProducts"
            type="button"
            class="products__more"
            data-testid="sales-detail-products-more"
            @click="toggleProductsExpanded"
          >
            {{ productsExpanded ? LABEL_PRODUCTS_LESS : LABEL_PRODUCTS_MORE }}
            <img
              class="products__more-ico"
              :class="{ 'products__more-ico--up': productsExpanded }"
              :src="iconChevronDown"
              alt=""
              aria-hidden="true"
            />
          </button>
        </OdsCard>

        <OdsCard class="payments" :aria-label="LABEL_PAYMENT_HISTORY">
          <div class="payments__head">
            <div class="payments__title-wrap">
              <img class="payments__ico" :src="iconExpense" alt="" aria-hidden="true" />
              <h3 class="payments__title">{{ LABEL_PAYMENT_HISTORY }}</h3>
            </div>
          </div>

          <OdsSkeleton v-if="paymentLoading" />
          <p v-else-if="paymentError" class="err" role="alert">{{ paymentError }}</p>
          <p v-else-if="!payments.length" class="payments-empty">
            {{ MSG_PAYMENT_HISTORY_EMPTY }}
          </p>
          <template v-else>
            <table class="payments__table">
              <colgroup>
                <col class="payments__col--dt" />
                <col class="payments__col--method" />
                <col class="payments__col--memo" />
                <col class="payments__col--amt" />
              </colgroup>
              <thead>
                <tr>
                  <th scope="col">{{ LABEL_PAY_DT_COL }}</th>
                  <th scope="col">{{ LABEL_PAY_METHOD_COL }}</th>
                  <th scope="col">{{ LABEL_PAY_MEMO }}</th>
                  <th scope="col">{{ LABEL_PAY_AMOUNT }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="pay in payments" :key="pay.paid_detail_no">
                  <td class="payments__dt">{{ pay.pay_dt }}</td>
                  <td class="payments__method">{{ pay.pay_method_nm || pay.pay_method_cd }}</td>
                  <td class="payments__memo">{{ paymentMemoText(pay) }}</td>
                  <td class="payments__amt">{{ formatOrderAmt(pay.pay_amt) }}원</td>
                </tr>
              </tbody>
            </table>
            <div class="payments__total" data-testid="payment-total-row">
              <span>{{ LABEL_PAY_TOTAL }}</span>
              <strong>{{ formatOrderAmt(detail.paid_amt) }}원</strong>
            </div>
          </template>

          <OdsCard v-if="showPaymentForm" class="payment-form" data-testid="payment-form">
            <OdsFormField :label="LABEL_PAY_DT" required>
              <div class="date-iso">
                <span class="date-iso__value">{{ payDt }}</span>
                <input
                  v-model="payDt"
                  class="date-iso__native"
                  type="date"
                  :aria-label="LABEL_PAY_DT"
                  :min="detail.sales_dt"
                  :max="todayIso"
                  :disabled="submitting"
                />
              </div>
            </OdsFormField>
            <OdsFormField :label="LABEL_PAY_AMOUNT" required>
              <OdsInput
                v-model="payAmt"
                type="number"
                variant="form"
                bare
                :disabled="submitting"
              />
            </OdsFormField>
            <OdsFormField :label="LABEL_PAY_METHOD" required>
              <OdsSelect
                v-model="payMethodCd"
                variant="form"
                required
                data-testid="payment-method-select"
                :disabled="submitting || payMethodsLoading || !payMethodOptions.length"
              >
                <option value="">선택</option>
                <option
                  v-for="opt in payMethodOptions"
                  :key="opt.acct_cd"
                  :value="opt.acct_cd"
                >
                  {{ opt.acct_nm }}
                </option>
              </OdsSelect>
            </OdsFormField>
            <p v-if="formError" class="err" role="alert">{{ formError }}</p>
            <div class="payment-form__actions">
              <OdsButton
                type="button"
                variant="secondary"
                :disabled="submitting"
                @click="closePaymentForm"
              >
                {{ LABEL_PAY_CANCEL }}
              </OdsButton>
              <OdsButton
                type="button"
                variant="primary"
                data-testid="payment-submit-btn"
                :disabled="!canSubmitPayment"
                @click="submitPayment"
              >
                {{ LABEL_PAY_SUBMIT }}
              </OdsButton>
            </div>
          </OdsCard>

        </OdsCard>
      </template>
    </main>

    <div
      v-if="detail && canShowPaymentButton && !showPaymentForm"
      class="pay-fab"
      role="region"
      :aria-label="LABEL_PAYMENT_REGISTER"
    >
      <OdsButton
        type="button"
        :block="false"
        class="pay-fab__btn"
        data-testid="payment-register-btn"
        @click="openPaymentForm"
      >
        {{ LABEL_PAYMENT_REGISTER }}
      </OdsButton>
    </div>

    <OdsBottomNav />
  </div>
</template>

<style scoped>
.page {
  min-height: 100dvh;
  background: var(--ods-color-bg-muted);
  padding-bottom: calc(96px + env(safe-area-inset-bottom));
}
.page-head {
  margin: 0 0 var(--ods-space-8);
}
.page-head__title {
  margin: 0;
  font: var(--ods-font-title-1);
  color: var(--ods-color-text);
}
.party {
  margin-bottom: var(--ods-space-8);
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-12);
}
.party__top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--ods-space-8);
}
.party__main {
  display: flex;
  align-items: flex-start;
  gap: var(--ods-space-8);
  min-width: 0;
}
.party__ico-well {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  border-radius: var(--ods-radius-badge);
  background: color-mix(in srgb, var(--ods-color-primary) 14%, var(--ods-color-white));
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.party__ico {
  width: var(--ods-icon-md);
  height: var(--ods-icon-md);
}
.party__text {
  min-width: 0;
}
.party__lbl {
  margin: 0;
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
}
.party__name {
  margin: 2px 0 0;
  font: var(--ods-font-title-2);
  color: var(--ods-color-text);
  word-break: keep-all;
}
.party__meta {
  margin: var(--ods-space-4) 0 0;
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
  font-variant-numeric: tabular-nums;
}
.party__badges {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: var(--ods-space-4);
  flex-shrink: 0;
}
.party__summary {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--ods-space-12);
  padding-top: var(--ods-space-12);
  border-top: 1px solid var(--ods-color-border);
}
.party__col {
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-8);
  min-width: 0;
}
.party__col + .party__col {
  padding-left: var(--ods-space-12);
  border-left: 1px solid var(--ods-color-border);
}
.party__row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--ods-space-8);
}
.party__row dt {
  margin: 0;
  flex-shrink: 0;
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
}
.party__row dd {
  margin: 0;
  font: var(--ods-font-body-2);
  color: var(--ods-color-text);
  text-align: right;
  font-variant-numeric: tabular-nums;
  word-break: keep-all;
}
.party__amt {
  font-weight: 700;
}
.products {
  margin-bottom: var(--ods-space-8);
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-8);
  min-width: 0;
}
.products__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ods-space-8);
}
.products__title-wrap {
  display: flex;
  align-items: center;
  gap: var(--ods-space-8);
  min-width: 0;
}
.products__ico {
  width: var(--ods-icon-sm);
  height: var(--ods-icon-sm);
  flex-shrink: 0;
}
.products__title {
  margin: 0;
  font: var(--ods-font-card-section);
  color: var(--ods-color-text);
}
.products__count {
  margin: 0;
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
  white-space: nowrap;
}
.products__table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
}
.products__col--spec {
  width: auto;
}
.products__col--qty {
  width: 2.75rem;
}
.products__col--price {
  width: 4.5rem;
}
.products__col--amt {
  width: 5rem;
}
.products__table th,
.products__table td {
  box-sizing: border-box;
  padding: var(--ods-space-8) var(--ods-space-4);
  border-bottom: 1px solid var(--ods-color-border);
  vertical-align: middle;
  line-height: 1.3;
}
.products__table thead th {
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
  font-weight: 500;
  text-align: right;
  white-space: nowrap;
}
.products__table thead th:first-child {
  text-align: left;
  padding-left: 0;
}
.products__table tbody tr:last-child td {
  border-bottom: none;
}
.products__spec {
  font: var(--ods-font-caption);
  font-weight: 600;
  letter-spacing: -0.02em;
  color: var(--ods-color-text);
  text-align: left;
  padding-left: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.products__num {
  font: var(--ods-font-caption);
  font-variant-numeric: tabular-nums;
  text-align: right;
  white-space: nowrap;
  color: var(--ods-color-text);
}
.products__more {
  align-self: center;
  display: inline-flex;
  align-items: center;
  gap: var(--ods-space-4);
  margin: 0;
  padding: var(--ods-space-4) var(--ods-space-8);
  border: none;
  background: transparent;
  color: var(--ods-color-text-secondary);
  font: var(--ods-font-caption);
  cursor: pointer;
}
.products__more-ico {
  width: var(--ods-icon-sm);
  height: var(--ods-icon-sm);
  opacity: 0.7;
  transition: transform 0.15s ease;
}
.products__more-ico--up {
  transform: rotate(180deg);
}
.section-title {
  margin: 0;
  font: var(--ods-font-card-emphasis);
  color: var(--ods-color-text);
}
.payments {
  margin-bottom: var(--ods-space-8);
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-8);
  min-width: 0;
}
.payments__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ods-space-8);
}
.payments__title-wrap {
  display: flex;
  align-items: center;
  gap: var(--ods-space-8);
  min-width: 0;
}
.payments__ico {
  width: var(--ods-icon-sm);
  height: var(--ods-icon-sm);
  flex-shrink: 0;
}
.payments__title {
  margin: 0;
  font: var(--ods-font-card-section);
  color: var(--ods-color-text);
}
.payments__table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
}
.payments__col--dt {
  width: 5.5rem;
}
.payments__col--method {
  width: 4.5rem;
}
.payments__col--memo {
  width: auto;
}
.payments__col--amt {
  width: 5.25rem;
}
.payments__table th,
.payments__table td {
  box-sizing: border-box;
  padding: var(--ods-space-8) var(--ods-space-4);
  border-bottom: 1px solid var(--ods-color-border);
  vertical-align: middle;
  line-height: 1.3;
}
.payments__table thead th {
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
  font-weight: 500;
  text-align: left;
  white-space: nowrap;
}
.payments__table thead th:last-child {
  text-align: right;
}
.payments__table tbody tr:last-child td {
  border-bottom: none;
}
.payments__dt,
.payments__method,
.payments__memo {
  font: var(--ods-font-caption);
  color: var(--ods-color-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.payments__dt {
  font-variant-numeric: tabular-nums;
}
.payments__amt {
  font: var(--ods-font-caption);
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  text-align: right;
  white-space: nowrap;
  color: var(--ods-color-text);
}
.payments__total {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ods-space-8);
  margin-top: var(--ods-space-4);
  padding: var(--ods-space-8) var(--ods-space-12);
  border-radius: var(--ods-radius-button);
  background: color-mix(in srgb, var(--ods-color-primary) 10%, var(--ods-color-white));
  font: var(--ods-font-body-2);
  color: var(--ods-color-primary);
}
.payments__total strong {
  font: var(--ods-font-headline);
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  color: var(--ods-color-primary);
}
.pay-fab {
  position: fixed;
  right: max(var(--ods-space-16), env(safe-area-inset-right));
  bottom: calc(64px + var(--ods-space-12) + env(safe-area-inset-bottom));
  z-index: 40;
  box-sizing: border-box;
  padding: var(--ods-space-8);
  border: 1px solid var(--ods-color-border);
  border-radius: var(--ods-radius-card);
  background: var(--ods-color-white);
  box-shadow: var(--ods-shadow-elevated);
}
.pay-fab :deep(button.pay-fab__btn.ods-btn) {
  min-height: 28px;
  height: 28px;
  width: auto;
  padding: 0 var(--ods-space-12);
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}
.payments-empty {
  margin: 0;
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
}
.payment-form {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-8);
}
.payment-form__actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--ods-space-8);
}
.date-iso {
  position: relative;
  display: flex;
  align-items: center;
  min-height: 2.5rem;
}
.date-iso__value {
  font: var(--ods-font-body-2);
  color: var(--ods-color-text);
}
.date-iso__native {
  position: absolute;
  inset: 0;
  opacity: 0;
  width: 100%;
  height: 100%;
  cursor: pointer;
}
.err {
  margin: var(--ods-space-8) 0;
  color: var(--ods-color-danger);
  font: var(--ods-font-body-2);
}
</style>
