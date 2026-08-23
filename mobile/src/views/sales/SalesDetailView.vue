<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'

import { fetchSaleDetail, fetchSalePayments } from '@/api/sales'
import { ApiClientError } from '@/api/client'
import OdsAppBar from '@/components/ods/OdsAppBar.vue'
import OdsBadge from '@/components/ods/OdsBadge.vue'
import OdsBottomNav from '@/components/ods/OdsBottomNav.vue'
import OdsCard from '@/components/ods/OdsCard.vue'
import OdsSkeleton from '@/components/ods/OdsSkeleton.vue'
import { formatOrderAmt, TAB_SALES } from '@/views/orders/ordersConstants'
import {
  LABEL_LINE_AMOUNT,
  LABEL_ORDER_NO,
  LABEL_PAID_AMOUNT,
  LABEL_PAYMENT_HISTORY,
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
  MSG_SALES_DETAIL_LOAD_FAIL,
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

const salesNo = computed(() => String(route.params.salesNo || ''))

const displayLines = computed(() =>
  detail.value ? groupSalesDetailLines(detail.value.lines) : [],
)

function goBackToSalesTab() {
  void router.replace({ name: 'orders', query: { tab: TAB_SALES } })
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
  await Promise.all([loadDetail(), loadPayments()])
}

onMounted(() => {
  void load()
})

watch(salesNo, () => {
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
          <h3 class="section-title">{{ LABEL_PAYMENT_HISTORY }}</h3>
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
  margin: 0 0 var(--ods-space-8);
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
