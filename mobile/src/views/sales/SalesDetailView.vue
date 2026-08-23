<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'

import { createSalePayment, fetchSaleDetail, fetchSalePayments } from '@/api/sales'
import { fetchWorkLogAccountCodes, type WorkLogAccountCodeOption } from '@/api/workLogs'
import { ApiClientError } from '@/api/client'
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
  LABEL_PAY_METHOD,
  LABEL_PAY_SUBMIT,
  LABEL_QTY,
  LABEL_SALES_AMOUNT,
  LABEL_SALES_DETAIL,
  LABEL_SALES_PRODUCTS,
  LABEL_SALES_ROUTE,
  LABEL_SALES_SUMMARY,
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
  SALES_STATUS_CONFIRMED,
  groupSalesDetailLines,
  paymentSourceLabelOf,
  paymentStatusLabelOf,
  paymentStatusToneOf,
  salesCustomerLabel,
  salesDetailProductText,
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

const salesNo = computed(() => String(route.params.salesNo || ''))
const todayIso = computed(() => todayBizIso())

const displayLines = computed(() =>
  detail.value ? groupSalesDetailLines(detail.value.lines) : [],
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
        <OdsCard class="hero" :aria-label="LABEL_SALES_DETAIL">
          <p class="hero__ctx">{{ LABEL_SALES_DETAIL }}</p>
          <h2 class="hero__title">{{ salesCustomerLabel(detail) }}</h2>
          <div class="hero__badges">
            <OdsBadge :tone="salesStatusToneOf(detail.sales_status)">
              {{ salesStatusLabelOf(detail.sales_status) }}
            </OdsBadge>
            <OdsBadge :tone="paymentStatusToneOf(detail)">
              {{ paymentStatusLabelOf(detail) }}
            </OdsBadge>
          </div>
          <p class="hero__id">{{ detail.sales_no }} · {{ detail.sales_dt }}</p>
        </OdsCard>

        <OdsCard class="summary" :aria-label="LABEL_SALES_SUMMARY">
          <h3 class="section-title">{{ LABEL_SALES_SUMMARY }}</h3>
          <dl class="summary-grid">
            <div class="summary-grid__row">
              <dt>{{ LABEL_SALES_ROUTE }}</dt>
              <dd>{{ salesRouteLabel(detail) }}</dd>
            </div>
            <div v-if="detail.order_no" class="summary-grid__row">
              <dt>{{ LABEL_ORDER_NO }}</dt>
              <dd>{{ detail.order_no }}</dd>
            </div>
            <div class="summary-grid__row">
              <dt>{{ LABEL_SALES_AMOUNT }}</dt>
              <dd>{{ formatOrderAmt(detail.tot_sales_amt) }}원</dd>
            </div>
            <div class="summary-grid__row">
              <dt>{{ LABEL_PAID_AMOUNT }}</dt>
              <dd>{{ formatOrderAmt(detail.paid_amt) }}원</dd>
            </div>
            <div class="summary-grid__row">
              <dt>{{ LABEL_UNPAID_AMOUNT }}</dt>
              <dd>{{ formatOrderAmt(detail.unpaid_amt) }}원</dd>
            </div>
          </dl>
        </OdsCard>

        <section class="products" :aria-label="LABEL_SALES_PRODUCTS">
          <h3 class="section-title">{{ LABEL_SALES_PRODUCTS }}</h3>
          <OdsCard
            v-for="(line, idx) in displayLines"
            :key="`${line.sale_detail_no}-${idx}`"
            class="product-card"
          >
            <p class="product-card__name">{{ salesDetailProductText(line) || '-' }}</p>
            <dl class="product-grid">
              <div class="product-grid__row">
                <dt>{{ LABEL_QTY }}</dt>
                <dd>{{ formatOrderAmt(line.qty) }}</dd>
              </div>
              <div class="product-grid__row">
                <dt>{{ LABEL_UNIT_PRICE }}</dt>
                <dd>{{ formatOrderAmt(line.unit_price) }}원</dd>
              </div>
              <div class="product-grid__row">
                <dt>{{ LABEL_LINE_AMOUNT }}</dt>
                <dd>{{ formatOrderAmt(line.item_amt) }}원</dd>
              </div>
            </dl>
          </OdsCard>
        </section>

        <section class="payments" :aria-label="LABEL_PAYMENT_HISTORY">
          <div class="payments-head">
            <h3 class="section-title">{{ LABEL_PAYMENT_HISTORY }}</h3>
            <OdsButton
              v-if="canShowPaymentButton && !showPaymentForm"
              type="button"
              variant="secondary"
              size="sm"
              data-testid="payment-register-btn"
              @click="openPaymentForm"
            >
              {{ LABEL_PAYMENT_REGISTER }}
            </OdsButton>
          </div>

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

          <OdsSkeleton v-if="paymentLoading" />
          <p v-else-if="paymentError" class="err" role="alert">{{ paymentError }}</p>
          <p v-else-if="!payments.length" class="payments-empty">
            {{ MSG_PAYMENT_HISTORY_EMPTY }}
          </p>
          <template v-else>
            <OdsCard
              v-for="pay in payments"
              :key="pay.paid_detail_no"
              class="payment-card"
            >
              <div class="payment-card__row">
                <span class="payment-card__dt">{{ pay.pay_dt }}</span>
                <span class="payment-card__method">{{ pay.pay_method_nm || pay.pay_method_cd }}</span>
                <span class="payment-card__amt">{{ formatOrderAmt(pay.pay_amt) }}원</span>
              </div>
              <p class="payment-card__source">{{ paymentSourceLabelOf(pay) }}</p>
            </OdsCard>
          </template>
        </section>
      </template>
    </main>
    <OdsBottomNav />
  </div>
</template>

<style scoped>
.page {
  min-height: 100dvh;
  background: var(--ods-color-bg-muted);
  padding-bottom: calc(140px + env(safe-area-inset-bottom));
}
.hero {
  margin-bottom: var(--ods-space-12);
}
.hero__ctx {
  margin: 0 0 var(--ods-space-4);
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
}
.hero__title {
  margin: 0;
  font: var(--ods-font-title-3);
  color: var(--ods-color-text);
}
.hero__badges {
  display: flex;
  flex-wrap: wrap;
  gap: var(--ods-space-6);
  margin-top: var(--ods-space-8);
}
.hero__id {
  margin: var(--ods-space-8) 0 0;
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
}
.section-title {
  margin: 0;
  font: var(--ods-font-card-emphasis);
  color: var(--ods-color-text);
}
.summary {
  margin-bottom: var(--ods-space-12);
}
.summary-grid,
.product-grid {
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-6);
}
.summary-grid__row,
.product-grid__row {
  display: grid;
  grid-template-columns: 5.5rem minmax(0, 1fr);
  gap: var(--ods-space-8);
  align-items: baseline;
}
.summary-grid__row dt,
.product-grid__row dt {
  margin: 0;
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
}
.summary-grid__row dd,
.product-grid__row dd {
  margin: 0;
  font: var(--ods-font-body-2);
  color: var(--ods-color-text);
  text-align: right;
  font-variant-numeric: tabular-nums;
}
.products,
.payments {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-8);
  margin-bottom: var(--ods-space-12);
}
.payments-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ods-space-8);
}
.product-card__name {
  margin: 0 0 var(--ods-space-8);
  font: var(--ods-font-body-2);
  font-weight: 600;
  color: var(--ods-color-text);
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
.payment-card__row {
  display: grid;
  grid-template-columns: auto 1fr auto;
  gap: var(--ods-space-8);
  align-items: baseline;
}
.payment-card__dt,
.payment-card__method {
  font: var(--ods-font-body-2);
  color: var(--ods-color-text);
}
.payment-card__amt {
  font: var(--ods-font-body-2);
  font-weight: 600;
  color: var(--ods-color-text);
  font-variant-numeric: tabular-nums;
}
.payment-card__source {
  margin: var(--ods-space-6) 0 0;
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
}
.err {
  margin: var(--ods-space-8) 0;
  color: var(--ods-color-danger, #c0392b);
  font: var(--ods-font-body-2);
}
</style>
