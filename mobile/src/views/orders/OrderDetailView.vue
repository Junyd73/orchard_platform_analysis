<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'

import { cancelOrder, fetchOrder } from '@/api/orders'
import { ApiClientError } from '@/api/client'
import iconEdit from '@/assets/ods/scr004/icon-edit.svg'
import OdsAppBar from '@/components/ods/OdsAppBar.vue'
import OdsBadge from '@/components/ods/OdsBadge.vue'
import OdsBottomNav from '@/components/ods/OdsBottomNav.vue'
import OdsButton from '@/components/ods/OdsButton.vue'
import OdsCard from '@/components/ods/OdsCard.vue'
import OdsSkeleton from '@/components/ods/OdsSkeleton.vue'
import {
  LABEL_CANCEL_ORDER,
  LABEL_CLOSE,
  LABEL_EDIT,
  LABEL_LINE,
  LABEL_ORDER_DETAIL,
  LABEL_QTY,
  LABEL_SHIP,
  LABEL_UNIT_PRICE,
  MSG_ORDER_CANCEL_CONFIRM,
  MSG_ORDER_CANCEL_FAIL,
  ORDER_STATUS_CANCEL,
  ORDER_STATUS_DELIVERED,
  ORDER_STATUS_PREP,
  ORDER_STATUS_RESERVED,
  LABEL_SHIP_BATCH,
  LABEL_SHIP_SELECTED,
  HINT_ORDER_NEXT_RESERVED,
  HINT_ORDER_NEXT_CONFIRMED,
  HINT_ORDER_NEXT_PREP,
  ORDER_STATUS_CONFIRMED,
  canCancelOrder,
  canEnterOrderEdit,
  formatOrderAmt,
  formatOrderLineShip,
  formatOrderLineSpec,
  isOrderEditLocked,
  orderEditLockMessage,
} from '@/views/orders/ordersConstants'
import { useAppStore } from '@/composables/stores/app'
import { useSalesPrefillStore } from '@/composables/stores/salesPrefill'
import type { OrderDetail, OrderLine } from '@/types/order'

const route = useRoute()
const router = useRouter()
const { farmCd } = storeToRefs(useAppStore())
const salesPrefill = useSalesPrefillStore()
const loading = ref(true)
const cancelling = ref(false)
const confirmOpen = ref(false)
const errorMsg = ref('')
const detail = ref<OrderDetail | null>(null)

const orderNo = computed(() => String(route.params.orderNo || ''))
const canEdit = computed(() => canEnterOrderEdit(detail.value?.status_cd || ''))
const editLocked = computed(() => isOrderEditLocked(detail.value?.status_cd || ''))
const canCancel = computed(() => canCancelOrder(detail.value?.status_cd || ''))
const lockHint = computed(() => orderEditLockMessage(detail.value?.status_cd || ''))
const statusNm = computed(() => detail.value?.status_nm || detail.value?.status_cd || '')
const statusTone = computed<'ok' | 'caution' | 'danger' | 'neutral'>(() => {
  const cd = detail.value?.status_cd || ''
  if (cd === ORDER_STATUS_CANCEL) return 'danger'
  if (cd === ORDER_STATUS_PREP) return 'caution'
  if (cd === ORDER_STATUS_DELIVERED) return 'neutral'
  return 'ok'
})
const canShip = computed(() => {
  const cd = detail.value?.status_cd || ''
  return cd !== ORDER_STATUS_CANCEL && cd !== ORDER_STATUS_DELIVERED
})
const totalAmt = computed(() =>
  formatOrderAmt(detail.value?.tot_order_amt || detail.value?.total_amt || 0),
)

function remainingQty(line: OrderLine): number {
  if (line.remaining_order_qty != null && !Number.isNaN(Number(line.remaining_order_qty))) {
    return Number(line.remaining_order_qty)
  }
  const row = salesPrefill.remainingFor(line.order_detail_id)
  if (row) return Number(row.remaining_order_qty)
  return Number(line.qty)
}

function remainingText(line: OrderLine): string {
  const shipped =
    line.confirmed_shipped_qty != null && !Number.isNaN(Number(line.confirmed_shipped_qty))
      ? Number(line.confirmed_shipped_qty)
      : null
  const rem = remainingQty(line)
  if (shipped != null && (shipped > 1e-9 || rem > 1e-9)) {
    return `출고 ${formatOrderAmt(shipped)} / 잔여 ${formatOrderAmt(rem)}`
  }
  const row = salesPrefill.remainingFor(line.order_detail_id)
  if (!row) return ''
  return `출고 ${formatOrderAmt(row.confirmed_shipped_qty)} / 잔여 ${formatOrderAmt(row.remaining_order_qty)}`
}

const nextStepHint = computed(() => {
  const cd = detail.value?.status_cd || ''
  if (cd === ORDER_STATUS_RESERVED) return HINT_ORDER_NEXT_RESERVED
  if (cd === ORDER_STATUS_CONFIRMED) return HINT_ORDER_NEXT_CONFIRMED
  if (cd === ORDER_STATUS_PREP) return HINT_ORDER_NEXT_PREP
  return ''
})
const selectedIds = ref<string[]>([])

function shipableLines(): OrderLine[] {
  return (detail.value?.lines || []).filter((ln) => remainingQty(ln) > 1e-9)
}

function applyRemaining(lines: OrderLine[]) {
  if (!detail.value) return
  salesPrefill.setFromOrderLines(detail.value, lines)
  for (const d of salesPrefill.shipLines) {
    const src = lines.find((ln) => ln.order_detail_id === d.order_detail_id)
    if (!src) continue
    const rem = remainingQty(src)
    d.qty = rem
    d.remaining_qty = rem
  }
}

function goShip(line: OrderLine) {
  if (!canShip.value || !detail.value) return
  applyRemaining([line])
  void router.push({ name: 'ship-confirm' })
}

function toggleSelect(id: string) {
  if (selectedIds.value.includes(id)) {
    selectedIds.value = selectedIds.value.filter((x) => x !== id)
    return
  }
  selectedIds.value = [...selectedIds.value, id]
}

function goShipSelected() {
  if (!canShip.value || !detail.value) return
  const lines = shipableLines().filter((ln) => selectedIds.value.includes(ln.order_detail_id))
  if (!lines.length) return
  applyRemaining(lines)
  void router.push({ name: 'ship-confirm' })
}

function goShipBatch() {
  if (!canShip.value || !detail.value) return
  const lines = shipableLines()
  if (!lines.length) return
  applyRemaining(lines)
  void router.push({ name: 'ship-confirm' })
}

function lineTitle(idx: number): string {
  return `${LABEL_LINE} ${idx + 1}`
}

function lineQtyAmtText(line: OrderLine): string {
  return [
    `${LABEL_QTY} ${formatOrderAmt(line.qty)}`,
    `${LABEL_UNIT_PRICE} ${formatOrderAmt(line.unit_price)}원`,
    `${formatOrderAmt(line.item_amt)}원`,
  ].join(' · ')
}

function goEdit() {
  if (!canEdit.value || !orderNo.value) return
  void router.push({ name: 'order-edit', params: { orderNo: orderNo.value } })
}

function openCancelConfirm() {
  if (!canCancel.value || cancelling.value) return
  errorMsg.value = ''
  confirmOpen.value = true
}

function closeCancelConfirm() {
  if (cancelling.value) return
  confirmOpen.value = false
}

async function confirmCancel() {
  if (!canCancel.value || !orderNo.value || cancelling.value) return
  cancelling.value = true
  errorMsg.value = ''
  try {
    detail.value = await cancelOrder(farmCd.value, orderNo.value)
    confirmOpen.value = false
  } catch (err) {
    errorMsg.value = err instanceof ApiClientError ? err.message : MSG_ORDER_CANCEL_FAIL
  } finally {
    cancelling.value = false
  }
}

async function load() {
  loading.value = true
  errorMsg.value = ''
  try {
    detail.value = await fetchOrder(farmCd.value, orderNo.value)
  } catch (err) {
    detail.value = null
    errorMsg.value = err instanceof ApiClientError ? err.message : '주문을 불러오지 못했습니다.'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  void load()
})

watch(orderNo, () => {
  void load()
})
</script>

<template>
  <div class="page">
    <main class="content ods-page-content">
      <OdsAppBar :show-back="true" back-fallback="orders" />
      <OdsSkeleton v-if="loading" />
      <p v-if="!loading && errorMsg && !confirmOpen" class="err" role="alert">{{ errorMsg }}</p>
      <template v-if="!loading && detail">
        <OdsCard class="hero" aria-label="주문 요약">
          <p class="hero__ctx">{{ LABEL_ORDER_DETAIL }}</p>
          <h2 class="hero__title">{{ detail.customer || detail.custm_id }}</h2>
          <div class="hero__badges">
            <OdsBadge :tone="statusTone">{{ statusNm }}</OdsBadge>
          </div>
          <p class="hero__id">{{ detail.order_no }} · {{ detail.order_dt }}</p>
          <p class="hero__sum">
            수량 {{ formatOrderAmt(detail.total_qty) }}
            · {{ totalAmt }}원
            <template v-if="detail.pre_pay_amt">
              · 선입 {{ formatOrderAmt(detail.pre_pay_amt) }}원
            </template>
          </p>
          <p v-if="detail.rmk" class="hero__rmk">{{ detail.rmk }}</p>
        </OdsCard>
        <p v-if="lockHint" class="hint" role="status">{{ lockHint }}</p>
        <p v-else-if="nextStepHint" class="hint" role="status">{{ nextStepHint }}</p>
        <OdsCard
          v-for="(line, idx) in detail.lines"
          :key="line.order_detail_id"
          :title="lineTitle(idx)"
        >
          <label v-if="canShip && remainingQty(line) > 0" class="pick">
            <input
              type="checkbox"
              :checked="selectedIds.includes(line.order_detail_id)"
              @change="toggleSelect(line.order_detail_id)"
            >
            출고 선택
          </label>
          <p class="spec">{{ formatOrderLineSpec(line) }}</p>
          <p class="meta">{{ lineQtyAmtText(line) }}</p>
          <p v-if="remainingText(line)" class="meta">{{ remainingText(line) }}</p>
          <p class="meta">배송 {{ formatOrderLineShip(line) }}</p>
          <OdsButton
            v-if="canShip && remainingQty(line) > 0"
            type="button"
            variant="secondary"
            :block="false"
            class="ship-btn"
            @click="goShip(line)"
          >
            {{ LABEL_SHIP }}
          </OdsButton>
        </OdsCard>
      </template>
    </main>
    <div v-if="detail && !loading" class="footer-actions">
      <OdsButton
        v-if="canShip && shipableLines().length > 1"
        class="footer-btn"
        variant="secondary"
        type="button"
        :block="false"
        @click="goShipBatch"
      >
        {{ LABEL_SHIP_BATCH }}
      </OdsButton>
      <OdsButton
        v-if="canShip && selectedIds.length"
        class="footer-btn"
        variant="secondary"
        type="button"
        :block="false"
        @click="goShipSelected"
      >
        {{ LABEL_SHIP_SELECTED }}
      </OdsButton>
      <OdsButton
        v-if="canEdit || editLocked"
        class="footer-btn"
        variant="secondary"
        type="button"
        :block="false"
        :disabled="editLocked || cancelling"
        @click="goEdit"
      >
        <span class="footer-btn__inner">
          <img :src="iconEdit" alt="" aria-hidden="true">
          {{ LABEL_EDIT }}
        </span>
      </OdsButton>
      <OdsButton
        v-if="canCancel"
        class="footer-btn"
        variant="danger"
        type="button"
        :block="false"
        :disabled="cancelling"
        @click="openCancelConfirm"
      >
        {{ LABEL_CANCEL_ORDER }}
      </OdsButton>
    </div>
    <OdsBottomNav />
    <div
      v-if="confirmOpen"
      class="dlg"
      role="dialog"
      aria-modal="true"
      aria-labelledby="order-cancel-title"
      @keydown.esc.prevent="closeCancelConfirm"
    >
      <div class="dlg__panel">
        <h2 id="order-cancel-title" class="dlg__title">{{ LABEL_CANCEL_ORDER }}</h2>
        <p class="dlg__lead">{{ MSG_ORDER_CANCEL_CONFIRM }}</p>
        <p v-if="errorMsg" class="dlg__err" role="alert">{{ errorMsg }}</p>
        <div class="dlg__actions">
          <OdsButton
            variant="secondary"
            type="button"
            :block="false"
            :disabled="cancelling"
            @click="closeCancelConfirm"
          >
            {{ LABEL_CLOSE }}
          </OdsButton>
          <OdsButton
            variant="danger"
            type="button"
            :block="false"
            :busy="cancelling"
            @click="confirmCancel"
          >
            {{ LABEL_CANCEL_ORDER }}
          </OdsButton>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.page {
  min-height: 100dvh;
  background: var(--ods-color-bg-muted);
  padding-bottom: calc(148px + env(safe-area-inset-bottom, 0px));
}
.content {
  --ods-page-content-gap: var(--ods-card-block-gap, var(--ods-space-16));
}
.hero {
  position: relative;
  overflow: hidden;
  background: linear-gradient(
    135deg,
    var(--ods-color-white) 55%,
    color-mix(in srgb, var(--ods-color-secondary) 22%, white)
  );
}
.hero__ctx {
  margin: 0;
  font: var(--ods-font-form-value);
  font-weight: 700;
  color: var(--ods-color-primary);
}
.hero__title {
  margin: var(--ods-space-8) 0 0;
  font: var(--ods-font-title-2);
  color: var(--ods-color-text);
  word-break: break-word;
}
.hero__badges {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--ods-space-8);
  margin-top: var(--ods-space-8);
}
.hero__id,
.hero__sum,
.hero__rmk {
  margin: var(--ods-space-8) 0 0;
  font: var(--ods-font-card-meta);
  color: var(--ods-color-text-secondary);
}
.hero__sum {
  font: var(--ods-font-card-body);
  color: var(--ods-color-text);
}
.spec {
  margin: 0;
  font: var(--ods-font-card-body);
  color: var(--ods-color-text);
}
.ship-btn {
  margin-top: var(--ods-space-12);
}
.meta {
  margin: var(--ods-space-8) 0 0;
  font: var(--ods-font-card-meta);
  color: var(--ods-color-text-secondary);
}
.hint {
  margin: 0;
  font: var(--ods-font-form-help);
  color: var(--ods-color-text-secondary);
}
.pick {
  display: flex;
  align-items: center;
  gap: var(--ods-space-8);
  margin: 0 0 var(--ods-space-8);
  font: var(--ods-font-form-help);
}
.err {
  margin: 0;
  font: var(--ods-font-form-help);
  font-weight: 600;
  color: var(--ods-color-danger);
}
.footer-actions {
  position: fixed;
  left: 0;
  right: 0;
  bottom: calc(64px + env(safe-area-inset-bottom, 0px));
  z-index: 30;
  display: flex;
  gap: var(--ods-space-8);
  max-width: var(--ods-page-content-max, 480px);
  margin: 0 auto;
  padding: var(--ods-space-8) var(--ods-page-padding-x)
    calc(var(--ods-space-8) + env(safe-area-inset-bottom, 0px));
  background: color-mix(in srgb, var(--ods-color-bg-muted) 92%, transparent);
  backdrop-filter: blur(8px);
}
.footer-btn {
  flex: 1;
}
.footer-actions :deep(.footer-btn.ods-btn--secondary) {
  background: color-mix(in srgb, var(--ods-color-primary) 12%, white);
  color: var(--ods-color-primary);
  border: 1px solid color-mix(in srgb, var(--ods-color-primary) 20%, white);
}
.footer-btn__inner {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--ods-space-8);
}
.footer-btn__inner img {
  width: var(--ods-icon-lg);
  height: var(--ods-icon-lg);
}
.footer-actions :deep(.ods-btn) {
  min-height: var(--ods-button-height, 48px);
}
.dlg {
  position: fixed;
  inset: 0;
  z-index: 80;
  background: color-mix(in srgb, var(--ods-color-gray-900) 50%, transparent);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--ods-space-16);
}
.dlg__panel {
  width: 100%;
  max-width: min(400px, var(--ods-page-content-max, 480px));
  background: var(--ods-color-white);
  border-radius: var(--ods-radius-card);
  padding: var(--ods-card-padding, var(--ods-space-16));
  box-shadow: var(--ods-shadow-card);
}
.dlg__title {
  margin: 0;
  font: var(--ods-font-form-label);
  color: var(--ods-color-text);
}
.dlg__lead {
  margin: var(--ods-form-label-gap, var(--ods-space-8)) 0 0;
  font: var(--ods-font-form-help);
  color: var(--ods-color-text);
}
.dlg__err {
  margin: var(--ods-space-8) 0 0;
  font: var(--ods-font-form-help);
  color: var(--ods-color-danger);
}
.dlg__actions {
  display: flex;
  gap: var(--ods-space-8);
  margin-top: var(--ods-space-16);
}
.dlg__actions :deep(.ods-btn) {
  flex: 1;
}
</style>
