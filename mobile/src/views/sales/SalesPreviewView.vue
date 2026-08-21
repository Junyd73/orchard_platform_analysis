<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'

import { confirmShipment } from '@/api/shipments'
import { fetchCustomers } from '@/api/orders'
import { fetchCommonCodes } from '@/api/commonCodes'
import ParcelDestinationSheet from '@/components/sales/ParcelDestinationSheet.vue'
import ParcelSenderSheet from '@/components/sales/ParcelSenderSheet.vue'
import OdsAppBar from '@/components/ods/OdsAppBar.vue'
import OdsBottomNav from '@/components/ods/OdsBottomNav.vue'
import OdsButton from '@/components/ods/OdsButton.vue'
import OdsCard from '@/components/ods/OdsCard.vue'
import OdsInput from '@/components/ods/OdsInput.vue'
import OdsSelect from '@/components/ods/OdsSelect.vue'
import {
  DELIVERY_TP_DIRECT,
  DELIVERY_TP_PARCEL,
  DELIVERY_TP_VISIT,
  CODE_PARENT_DELIVERY,
  LABEL_CUSTOMER,
  MSG_NEED_SENDER,
  formatOrderAmt,
  formatWeightLabel,
  isJuiceItemCd,
  isParcelDelivery,
  joinDot,
  juiceItemLabel,
  saleUnitLabel,
} from '@/views/orders/ordersConstants'
import {
  MSG_NO_PREFILL,
  buildShipConfirmRequest,
  findShipQtyIssue,
  mapShipApiError,
  stockSaleSpecKey,
  type ShipDeliveryDraft,
} from '@/views/sales/shipConfirmModel'
import {
  allocQtySum,
  deliveryStatusText,
  findParcelDeliveryIssue,
  totalAllocShipFee,
} from '@/views/sales/shipDeliveryModel'
import { todayBizIso } from '@/shared/bizDate'
import { useAppStore } from '@/composables/stores/app'
import { useSalesPrefillStore } from '@/composables/stores/salesPrefill'
import type { CustomerListItem } from '@/types/order'

const LABEL_PAGE = '판매 미리보기'
const LABEL_ADD_ITEM = '+ 품목 추가'
const LABEL_CANCEL_PREP = '판매 준비 취소'
const LABEL_SHIP_FEE = '배송비'
const LABEL_TOTAL = '총액'
const LABEL_GO_SALE = '판매 진행'
const LABEL_EMPTY_LINES = '판매 품목이 없습니다.'
const LABEL_DLVRY_METHOD = '배송방법'
const LABEL_DLVRY_SHORT = '배송'
const LABEL_SENDER = '보내는 사람'
const LABEL_SENDER_UNSET = '미설정'
const LABEL_SENDER_SETUP = '설정 ›'
const LABEL_SENDER_EDIT = '편집 ›'
const LABEL_VIEW_DEST = '배송지 편집 ›'
const LABEL_LINES = '판매 품목'
const LABEL_COL_ITEM = '품목'
const LABEL_COL_QTY = '수량'
const LABEL_COL_PRICE = '단가'
const MSG_NEED_CUSTOMER = '고객을 선택해 주세요.'
const MSG_SHIP_FEE_NEG = '배송비는 0 이상이어야 합니다.'
const MSG_SUCCESS = '판매가 완료되었습니다.'
const MSG_CANCEL_PREP = '진행 중인 판매 준비를 취소하시겠습니까?'

const router = useRouter()
const appStore = useAppStore()
const { farmCd, farm } = storeToRefs(appStore)
const prefill = useSalesPrefillStore()

const busy = ref(false)
const errorMsg = ref('')
const successMsg = ref('')
const customers = ref<CustomerListItem[]>([])
const deliveryOptions = ref<{ value: string; label: string }[]>([
  { value: DELIVERY_TP_VISIT, label: '방문수령' },
  { value: DELIVERY_TP_PARCEL, label: '택배' },
  { value: DELIVERY_TP_DIRECT, label: '직접배송' },
])

const destEditIdx = ref<number | null>(null)

const lines = computed(() => prefill.shipLines)
const isParcel = computed(() => isParcelDelivery(prefill.dlvryTp))
const custmId = computed({
  get: () => prefill.custmId || '',
  set: (v: string) => {
    const c = customers.value.find((x) => x.custm_id === v)
    prefill.setCustomer(v || null, c?.custm_nm || '')
  },
})

const itemAmt = computed(() =>
  lines.value.reduce((s, ln) => s + Number(ln.qty) * Number(ln.unit_price), 0),
)
const totalQty = computed(() =>
  lines.value.reduce((s, ln) => s + Number(ln.qty), 0),
)
const safeShipFee = computed(() => {
  if (isParcel.value) return totalAllocShipFee(lines.value)
  return normalizeShipFee(prefill.shipFee)
})
const payAmt = computed(() => itemAmt.value + safeShipFee.value)
const qtyIssue = computed(() => findShipQtyIssue(lines.value))
const parcelIssue = computed(() =>
  isParcel.value ? findParcelDeliveryIssue(lines.value) : '',
)
const farmAddress = computed(() => String(farm.value?.address || '').trim())
const senderConfigured = computed(() => {
  const name = String(prefill.senderName || '').trim()
  const tel = String(prefill.senderTel || '').trim()
  const addr = String(prefill.senderAddr || '').trim()
  return Boolean(name && tel && addr)
})
const senderSummary = computed(() => {
  if (!senderConfigured.value) return ''
  return joinDot([prefill.senderName, prefill.senderTel])
})
const senderIssue = computed(() => {
  if (!isParcel.value) return ''
  if (!senderConfigured.value) return MSG_NEED_SENDER
  return ''
})
const unitHint = computed(() => saleUnitLabel(lines.value[0]?.item_cd))

/** 택배 상단 — 보내는 사람만 (배송 미지정 합계는 품목별 상세에만) */
const showSenderBar = computed(() => isParcel.value && lines.value.length > 0)

function normalizeShipFee(raw: unknown): number {
  const n = Number(String(raw ?? '').replace(/,/g, ''))
  if (!Number.isFinite(n) || n < 0) return 0
  return Math.round(n)
}

/** 화면 금액 표시 — #,##0 */
function formatAmt(n: number): string {
  return formatOrderAmt(n)
}

const canSubmit = computed(() => {
  if (busy.value || successMsg.value) return false
  if (!lines.value.length) return false
  if (!String(prefill.custmId || '').trim()) return false
  if (qtyIssue.value) return false
  if (lines.value.some((ln) => Number(ln.unit_price) < 0)) return false
  if (isParcel.value) {
    if (senderIssue.value) return false
    if (parcelIssue.value) return false
  } else if (Number(prefill.shipFee) < 0) {
    return false
  }
  return true
})

function lineKey(ln: (typeof lines.value)[number], idx: number) {
  return `${stockSaleSpecKey(ln)}#${idx}`
}

/** 미리보기 전용 표기 — 재고 cardTitle 계열(품종·중량·등급·규격). 공통 formatOrderLineSpec 미변경 */
function formatPreviewLineSpec(ln: (typeof lines.value)[number]): string {
  if (isJuiceItemCd(ln.item_cd)) {
    return juiceItemLabel(ln.item_cd, ln.item_nm)
  }
  return joinDot([
    ln.variety_nm || ln.variety_cd,
    formatWeightLabel(ln.weight),
    ln.grade_nm || ln.grade_cd,
    ln.size_nm || ln.size_cd,
  ])
}

function lineUnit(ln: (typeof lines.value)[number]) {
  return saleUnitLabel(ln.item_cd)
}

function lineDeliveryStatus(idx: number) {
  const ln = lines.value[idx]
  if (!ln) return ''
  return deliveryStatusText(Number(ln.qty), allocQtySum(ln), lineUnit(ln))
}

/** ok | warn | danger — 배송상태 시각 구분 */
function deliveryTone(idx: number): 'ok' | 'warn' | 'danger' {
  const ln = lines.value[idx]
  if (!ln) return 'warn'
  const sale = Number(ln.qty)
  const got = allocQtySum(ln)
  if (Math.abs(got - sale) <= 1e-9) return 'ok'
  if (got > sale) return 'danger'
  return 'warn'
}

function setPrice(idx: number, raw: string) {
  const n = Number(String(raw).replace(/,/g, ''))
  prefill.updateShipLine(idx, { unit_price: Number.isFinite(n) && n >= 0 ? n : 0 })
}

function setShipFee(raw: string) {
  if (isParcel.value) return
  prefill.setDelivery({ shipFee: normalizeShipFee(raw) })
}

function removeLine(idx: number) {
  prefill.removeShipLine(idx)
}

/** 재고 탭으로 이동 — salesPrefill(동일 stockSaleSpecKey 행) 유지 */
function goStockTab() {
  void router.push({ name: 'orders', query: { tab: 'stock' } })
}

function addMoreItems() {
  goStockTab()
}

/** 수량/규격은 재고 화면의 담기·수정(updateStockLineQty)으로 갱신 */
function editLineInStock() {
  goStockTab()
}

const senderSheetOpen = ref(false)

function openSenderSheet() {
  senderSheetOpen.value = true
}

function closeSenderSheet() {
  senderSheetOpen.value = false
}

function onSenderSave(input: { name: string; tel: string; addr: string }) {
  prefill.setSender(input)
  senderSheetOpen.value = false
}

function cancelSalePrep() {
  if (!window.confirm(MSG_CANCEL_PREP)) return
  prefill.clear()
  void router.replace({ name: 'orders', query: { tab: 'stock' } })
}

function openDestSheet(idx: number) {
  const ln = lines.value[idx]
  if (!ln) return
  destEditIdx.value = idx
}

function closeDestSheet() {
  destEditIdx.value = null
}

function customerDefaults() {
  const c = customers.value.find((x) => x.custm_id === prefill.custmId)
  return {
    rcv_name: c?.custm_nm || '',
    rcv_tel: c?.mobile || '',
  }
}

const destSheetLine = computed(() =>
  destEditIdx.value != null ? lines.value[destEditIdx.value] ?? null : null,
)

const destProductSummary = computed(() =>
  destSheetLine.value ? formatPreviewLineSpec(destSheetLine.value) : '',
)

const destOrderQty = computed(() =>
  Math.max(0, Math.floor(Number(destSheetLine.value?.qty || 0))),
)

const destSaleUnit = computed(() => {
  const ln = destSheetLine.value
  return ln ? lineUnit(ln) : '박스'
})

const destInitialDests = computed((): ShipDeliveryDraft[] => {
  const existing = destSheetLine.value?.delivery_allocations || []
  return existing.map((a) => ({ ...a }))
})

const destOrdererName = computed(
  () => String(prefill.customerNm || customerDefaults().rcv_name || '').trim(),
)

function onDestComplete(cleaned: ShipDeliveryDraft[]) {
  if (destEditIdx.value == null) return
  prefill.setShipLineDeliveries(destEditIdx.value, cleaned)
  closeDestSheet()
}

function validateBeforeConfirm(): string {
  if (!lines.value.length) return MSG_NO_PREFILL
  if (qtyIssue.value) return qtyIssue.value
  if (!String(prefill.custmId || '').trim()) return MSG_NEED_CUSTOMER
  if (isParcel.value) {
    if (senderIssue.value) return senderIssue.value
    if (parcelIssue.value) return parcelIssue.value
  } else if (Number(prefill.shipFee) < 0) {
    return MSG_SHIP_FEE_NEG
  }
  return ''
}

async function onSubmit() {
  if (!canSubmit.value) {
    errorMsg.value = validateBeforeConfirm()
    return
  }
  errorMsg.value = ''

  const confirmText =
    `${prefill.customerNm || prefill.custmId} / ${deliveryLabel(prefill.dlvryTp)}\n` +
    `${lines.value.length}품목 · 총 ${totalQty.value}${unitHint.value}\n` +
    `상품 ${formatOrderAmt(itemAmt.value)}원\n` +
    `배송비 ${formatOrderAmt(safeShipFee.value)}원\n` +
    `최종 ${formatOrderAmt(payAmt.value)}원\n\n` +
    '판매를 확정하시겠습니까?'
  if (!window.confirm(confirmText)) return

  busy.value = true
  errorMsg.value = ''
  try {
    const parcel = isParcel.value
    const firstAlloc = lines.value[0]?.delivery_allocations?.[0]
    const res = await confirmShipment(
      farmCd.value,
      buildShipConfirmRequest({
        shipMode: 'DIRECT',
        salesDt: todayBizIso(),
        orderNo: null,
        custmId: prefill.custmId,
        lines: lines.value,
        dlvryTp: prefill.dlvryTp,
        shipFee: safeShipFee.value,
        rcvName: parcel ? (firstAlloc?.rcv_name || '') : prefill.rcvName,
        rcvTel: parcel ? (firstAlloc?.rcv_tel || '') : prefill.rcvTel,
        rcvAddr: parcel ? (firstAlloc?.rcv_addr || '') : prefill.rcvAddr,
        dlvryMsg: parcel ? (firstAlloc?.dlvry_msg || '') : prefill.dlvryMsg,
        sndName: parcel ? prefill.senderName : '',
        sndTel: parcel ? prefill.senderTel : '',
        sndAddr: parcel ? prefill.senderAddr : '',
        includeDeliveryAllocations: parcel,
      }),
    )
    successMsg.value =
      `${MSG_SUCCESS}\n${res.sales_no} / ${lines.value.length}품목 / ` +
      `${totalQty.value}${unitHint.value} / ${formatOrderAmt(payAmt.value)}원`
    prefill.clear()
  } catch (err) {
    errorMsg.value = mapShipApiError(err)
  } finally {
    busy.value = false
  }
}

function deliveryLabel(cd: string) {
  return deliveryOptions.value.find((d) => d.value === cd)?.label || cd
}

function goStock() {
  void router.replace({ name: 'orders', query: { tab: 'stock' } })
}

onMounted(async () => {
  try {
    customers.value = await fetchCustomers(farmCd.value)
  } catch {
    customers.value = []
  }
  try {
    const codes = await fetchCommonCodes(farmCd.value, CODE_PARENT_DELIVERY)
    const allowed = new Set([DELIVERY_TP_VISIT, DELIVERY_TP_PARCEL, DELIVERY_TP_DIRECT])
    const mapped = codes
      .filter((c) => allowed.has(c.code_cd))
      .map((c) => ({ value: c.code_cd, label: c.code_nm || c.code_cd }))
    if (mapped.length) deliveryOptions.value = mapped
  } catch {
    /* 로컬 기본 유지 */
  }
})
</script>

<template>
  <div class="page sales-preview-frame" data-testid="sales-preview-page">
    <main class="content ods-page-content" data-testid="sales-preview-frame">
      <OdsAppBar :show-back="true" back-fallback="orders" />

      <h2 class="title">{{ LABEL_PAGE }}</h2>

      <p v-if="successMsg" class="ok" role="status">{{ successMsg }}</p>
      <p v-if="errorMsg" class="err" role="alert">{{ errorMsg }}</p>

      <template v-if="!successMsg">
        <!-- A. 상단 정보 — 포장/생산 compact card 계열 -->
        <OdsCard
          class="preview-card preview-card--compact"
          aria-label="고객 배송"
          data-testid="sales-preview-header"
        >
          <div class="header-fields">
            <div class="header-row">
              <span class="header-row__lbl">{{ LABEL_CUSTOMER }}</span>
              <OdsSelect
                v-model="custmId"
                variant="form"
                class="header-row__ctrl"
                aria-label="고객 선택"
              >
                <option value="">고객 선택</option>
                <option v-for="c in customers" :key="c.custm_id" :value="c.custm_id">
                  {{ c.custm_nm }} · {{ c.mobile }}
                </option>
              </OdsSelect>
            </div>
            <div class="header-row">
              <span class="header-row__lbl">{{ LABEL_DLVRY_SHORT }}</span>
              <OdsSelect
                class="header-row__ctrl"
                :model-value="prefill.dlvryTp"
                variant="form"
                :aria-label="LABEL_DLVRY_METHOD"
                @update:model-value="prefill.setDelivery({ dlvryTp: $event })"
              >
                <option v-for="d in deliveryOptions" :key="d.value" :value="d.value">
                  {{ d.label }}
                </option>
              </OdsSelect>
            </div>
            <div
              v-if="showSenderBar"
              class="header-hint"
              :class="{
                'header-hint--ok': senderConfigured,
                'header-hint--warn': !senderConfigured,
              }"
              data-testid="sales-preview-sender-bar"
            >
              <span class="header-hint__txt" data-testid="sales-preview-sender-summary">
                <template v-if="senderSummary">{{ LABEL_SENDER }} · {{ senderSummary }}</template>
                <template v-else>{{ LABEL_SENDER }} · {{ LABEL_SENDER_UNSET }}</template>
              </span>
              <button
                type="button"
                class="header-hint__act"
                data-testid="sales-preview-sender-setup"
                :aria-label="LABEL_SENDER"
                @click="openSenderSheet"
              >
                {{ senderConfigured ? LABEL_SENDER_EDIT : LABEL_SENDER_SETUP }}
              </button>
            </div>
          </div>
        </OdsCard>

        <!-- B. 판매 품목 — 재고 compact list 계열 (품목별 카드 반복 없음) -->
        <OdsCard
          class="preview-card preview-card--lines"
          aria-label="판매 품목"
          data-testid="sales-preview-lines"
        >
          <div class="lines__head">
            <h3 class="lines__title">{{ LABEL_LINES }}</h3>
            <span class="lines__count">{{ lines.length }}건</span>
          </div>

          <p v-if="!lines.length" class="lines__empty" data-testid="sales-preview-empty">
            {{ LABEL_EMPTY_LINES }}
          </p>

          <template v-else>
            <div class="lines__cols" aria-hidden="true">
              <span class="lines__cols-item">{{ LABEL_COL_ITEM }}</span>
              <span class="lines__cols-qty">{{ LABEL_COL_QTY }}</span>
              <span class="lines__cols-price">{{ LABEL_COL_PRICE }}</span>
              <span class="lines__cols-actions" aria-hidden="true" />
            </div>
            <ul class="lines__list">
              <li
                v-for="(ln, idx) in lines"
                :key="lineKey(ln, idx)"
                class="line"
                data-testid="sales-preview-line"
              >
                <div class="line__row">
                  <span class="line__title">{{ formatPreviewLineSpec(ln) }}</span>
                  <span class="line__qty" data-testid="sales-preview-qty">{{ ln.qty }}</span>
                  <OdsInput
                    :model-value="formatAmt(Number(ln.unit_price))"
                    type="text"
                    inputmode="numeric"
                    variant="form"
                    bare
                    class="line__price amt-input"
                    data-testid="sales-preview-price"
                    aria-label="단가"
                    @update:model-value="setPrice(idx, $event)"
                  />
                  <div class="line__actions">
                    <button
                      type="button"
                      class="line__icon-btn"
                      data-testid="sales-preview-edit"
                      :aria-label="`${formatPreviewLineSpec(ln)} 수량 수정`"
                      title="수정"
                      @click="editLineInStock"
                    >
                      <svg class="line__icon" viewBox="0 0 20 20" fill="none" aria-hidden="true">
                        <path
                          d="M12.2 3.6l4.2 4.2"
                          stroke="currentColor"
                          stroke-width="1.5"
                          stroke-linecap="round"
                        />
                        <path
                          d="M4 16l.7-3.6L13.2 4l2.8 2.8L7.6 15.3 4 16z"
                          stroke="currentColor"
                          stroke-width="1.5"
                          stroke-linejoin="round"
                        />
                      </svg>
                    </button>
                    <button
                      type="button"
                      class="line__icon-btn line__icon-btn--danger"
                      data-testid="sales-preview-remove"
                      :aria-label="`${formatPreviewLineSpec(ln)} 삭제`"
                      title="삭제"
                      @click="removeLine(idx)"
                    >
                      <svg class="line__icon" viewBox="0 0 20 20" fill="none" aria-hidden="true">
                        <path
                          d="M5.2 6.2h9.6"
                          stroke="currentColor"
                          stroke-width="1.5"
                          stroke-linecap="round"
                        />
                        <path
                          d="M8 4.2h4l.8 2H7.2L8 4.2z"
                          stroke="currentColor"
                          stroke-width="1.4"
                          stroke-linejoin="round"
                        />
                        <path
                          d="M6.4 6.2l.7 9.2a1.4 1.4 0 001.4 1.3h3a1.4 1.4 0 001.4-1.3l.7-9.2"
                          stroke="currentColor"
                          stroke-width="1.5"
                          stroke-linejoin="round"
                        />
                        <path
                          d="M8.6 9.2v5M11.4 9.2v5"
                          stroke="currentColor"
                          stroke-width="1.4"
                          stroke-linecap="round"
                        />
                      </svg>
                    </button>
                  </div>
                </div>
                <div
                  v-if="isParcel"
                  class="line__dest"
                  :class="`line__dest--${deliveryTone(idx)}`"
                  data-testid="sales-preview-delivery-status"
                >
                  <span class="line__dest-status">{{ lineDeliveryStatus(idx) }}</span>
                  <button
                    type="button"
                    class="line__dest-btn"
                    data-testid="sales-preview-dest-open"
                    @click="openDestSheet(idx)"
                  >
                    {{ LABEL_VIEW_DEST }}
                  </button>
                </div>
              </li>
            </ul>
          </template>

          <!-- C. 보조 액션 -->
          <div class="lines__actions">
            <OdsButton
              type="button"
              variant="secondary"
              :block="false"
              data-testid="sales-preview-add"
              @click="addMoreItems"
            >
              {{ LABEL_ADD_ITEM }}
            </OdsButton>
            <OdsButton
              type="button"
              variant="secondary"
              :block="false"
              data-testid="sales-preview-cancel-prep"
              @click="cancelSalePrep"
            >
              {{ LABEL_CANCEL_PREP }}
            </OdsButton>
          </div>
        </OdsCard>

        <!-- D. sticky summary — 재고 판매예정 bar 계열 + 전체폭 CTA -->
        <div class="footer" data-testid="sales-preview-footer" role="region" aria-label="합계">
          <div class="footer__panel">
            <p class="footer__top">
              <span class="footer__count">{{ lines.length }}품목 · {{ totalQty }}{{ unitHint }}</span>
              <span class="footer__item-amt">상품 {{ formatAmt(itemAmt) }}원</span>
            </p>
            <p class="footer__row">
              <span class="footer__lbl">{{ LABEL_SHIP_FEE }}</span>
              <span class="footer__val footer__val--fee">
                <template v-if="isParcel">
                  <span data-testid="sales-preview-ship-fee-sum">{{ formatAmt(safeShipFee) }}</span>원
                </template>
                <template v-else>
                  <OdsInput
                    :model-value="formatAmt(safeShipFee)"
                    type="text"
                    inputmode="numeric"
                    variant="form"
                    bare
                    class="footer__fee amt-input"
                    data-testid="sales-preview-ship-fee"
                    aria-label="배송비"
                    @update:model-value="setShipFee($event)"
                  />
                  원
                </template>
              </span>
            </p>
            <div class="footer__divider" aria-hidden="true" />
            <p class="footer__total">
              <span class="footer__lbl">{{ LABEL_TOTAL }}</span>
              <strong>{{ formatAmt(payAmt) }}원</strong>
            </p>
          </div>
          <OdsButton
            type="button"
            class="footer__go"
            data-testid="sales-preview-submit"
            :disabled="!canSubmit"
            @click="onSubmit"
          >
            {{ busy ? '처리 중…' : LABEL_GO_SALE }}
          </OdsButton>
        </div>
      </template>

      <OdsButton v-else type="button" data-testid="sales-preview-back-stock" @click="goStock">
        재고로 돌아가기
      </OdsButton>
    </main>
    <OdsBottomNav />

    <ParcelDestinationSheet
      :open="destEditIdx != null"
      :product-summary="destProductSummary"
      :order-qty="destOrderQty"
      :unit-label="destSaleUnit"
      :initial-dests="destInitialDests"
      :customer-defaults="customerDefaults()"
      :orderer-name="destOrdererName"
      :show-ship-fee="true"
      test-id-prefix="sales-preview"
      @close="closeDestSheet"
      @complete="onDestComplete"
    />

    <ParcelSenderSheet
      :open="senderSheetOpen"
      :sender-name="prefill.senderName"
      :sender-tel="prefill.senderTel"
      :sender-addr="prefill.senderAddr"
      :farm-address="farmAddress"
      test-id-prefix="sales-preview"
      @close="closeSenderSheet"
      @save="onSenderSave"
    />
  </div>
</template>

<style scoped>

.page {
  /* OdsBottomNav: min-height 56 + pad 8+8 + safe-area (SalesPreview 전용, Nav 미수정) */
  --sales-preview-nav-h: calc(
    var(--ods-space-56) + var(--ods-space-8) + var(--ods-space-8)
      + env(safe-area-inset-bottom, 0px)
  );
  --sales-preview-footer-h: 8.25rem;
  --sales-preview-footer-gap: var(--ods-space-8);
  --sales-preview-frame-max: var(--ods-page-content-max, 480px);
  --sales-preview-inline: var(--ods-page-padding-x, var(--ods-space-16));
  --preview-icon-touch: 36px;
  min-height: 100%;
  width: 100%;
  background: var(--ods-color-bg-muted, #f5f5f5);
  overflow-x: hidden;
  box-sizing: border-box;
}
.content {
  gap: var(--ods-space-8);
  width: 100%;
  max-width: var(--sales-preview-frame-max);
  margin-inline: auto;
  box-sizing: border-box;
  min-width: 0;
  padding-bottom: calc(
    var(--sales-preview-nav-h) + var(--sales-preview-footer-h) + var(--sales-preview-footer-gap)
  );
}
.title {
  margin: 0;
  font: var(--ods-font-title-2);
  color: var(--ods-color-text);
}

/* 포장/생산 OdsCard 계열 */
.preview-card {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-8);
  min-width: 0;
}
.preview-card--compact {
  padding: var(--ods-space-8) var(--ods-space-12);
  gap: var(--ods-space-6, 6px);
}
.preview-card--lines {
  padding: 0;
  overflow: hidden;
  /* header / row 공통 column — 동일 변수 공유 */
  --line-col-qty: 42px;
  --line-col-price: 72px;
  --line-col-actions: 80px;
  --line-gap: var(--ods-space-8);
  --line-pad-x: var(--ods-space-16);
}
.header-fields {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-6, 6px);
  min-width: 0;
}
.header-row {
  display: grid;
  grid-template-columns: 3.25rem minmax(0, 1fr);
  column-gap: var(--ods-space-8);
  align-items: center;
  min-width: 0;
}
.header-row__lbl {
  font: var(--ods-font-form-label);
  color: var(--ods-color-text-label);
  white-space: nowrap;
}
.header-row__ctrl {
  min-width: 0;
  width: 100%;
}
.header-row :deep(select.ods-select) {
  height: 38px;
  min-height: 38px;
  max-height: 38px;
}
.header-hint {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ods-space-8);
  box-sizing: border-box;
  min-height: 28px;
  max-height: 32px;
  margin: 0;
  padding: 0 var(--ods-space-8);
  border-radius: var(--ods-radius-button);
  font: var(--ods-font-caption);
  font-weight: 600;
  background: var(--ods-color-bg-muted);
  color: var(--ods-color-text-secondary);
}
.header-hint--ok {
  background: var(--ods-color-primary-subtle, #f0f7f4);
  color: var(--ods-color-primary);
}
.header-hint--warn {
  background: var(--ods-color-caution-soft);
  color: var(--ods-color-gray-900);
}
.header-hint__txt {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.header-hint__act {
  flex-shrink: 0;
  border: none;
  background: transparent;
  color: var(--ods-color-text);
  font: var(--ods-font-caption);
  font-weight: 700;
  cursor: pointer;
  padding: 0;
  min-height: 28px;
  white-space: nowrap;
}
.header-hint__act:focus-visible {
  outline: 2px solid var(--ods-color-primary);
  outline-offset: 2px;
}

.lines__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ods-space-8);
  min-height: 34px;
  padding: var(--ods-space-4) var(--line-pad-x, var(--ods-space-16));
  box-sizing: border-box;
}
.lines__title {
  margin: 0;
  font: var(--ods-font-form-label);
  color: var(--ods-color-text);
}
.lines__count {
  font: var(--ods-font-body-2);
  font-weight: 600;
  color: var(--ods-color-text-secondary);
  white-space: nowrap;
}
.lines__empty {
  margin: 0;
  padding: var(--ods-space-24) var(--line-pad-x, var(--ods-space-16));
  font: var(--ods-font-body-2);
  color: var(--ods-color-text-secondary);
  text-align: center;
}
/* 품목 | 수량 | 단가 | 액션 — header/row 동일 grid */
.lines__cols,
.line__row {
  display: grid;
  grid-template-columns:
    minmax(0, 1fr)
    var(--line-col-qty)
    var(--line-col-price)
    var(--line-col-actions);
  column-gap: var(--line-gap);
  align-items: center;
  min-width: 0;
  box-sizing: border-box;
  padding-inline: var(--line-pad-x, var(--ods-space-16));
}
.lines__cols {
  min-height: 28px;
  padding-block: var(--ods-space-4);
  border-bottom: 1px solid var(--ods-color-border);
  font: var(--ods-font-caption);
  font-weight: 600;
  color: var(--ods-color-text-secondary);
}
.lines__cols-item {
  text-align: left;
}
.lines__cols-qty,
.line__qty {
  text-align: center;
  justify-self: stretch;
}
.lines__cols-price {
  text-align: right;
  justify-self: stretch;
}
.lines__cols-actions {
  min-width: 0;
}
.lines__list {
  list-style: none;
  margin: 0;
  padding: 0;
  background: var(--ods-color-white);
}
.line {
  padding: var(--ods-space-4) 0;
  border-bottom: 1px solid var(--ods-color-border);
  min-width: 0;
}
.line:last-child {
  border-bottom: none;
}
.line__title {
  font: var(--ods-font-body-1);
  font-weight: 700;
  line-height: 1.35;
  color: var(--ods-color-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}
.line__qty {
  font: var(--ods-font-body-2);
  font-weight: 600;
  color: var(--ods-color-text);
  font-variant-numeric: tabular-nums;
}
.line__price {
  width: 100%;
  min-width: 0;
  justify-self: stretch;
}
.line :deep(input.line__price.ods-input),
.line :deep(.line__price.ods-input) {
  width: 100%;
  max-width: 100%;
  height: 28px;
  min-height: 28px;
  padding: 0 var(--ods-space-4);
  text-align: right;
  font: var(--ods-font-body-2);
  font-variant-numeric: tabular-nums;
  border-radius: var(--ods-radius-button);
  box-sizing: border-box;
}
.amt-input :deep(input.ods-input),
:deep(input.amt-input.ods-input),
:deep(.amt-input.ods-input) {
  text-align: right;
  font-variant-numeric: tabular-nums;
}
.line :deep(input.line__price.ods-input::-webkit-outer-spin-button),
.line :deep(input.line__price.ods-input::-webkit-inner-spin-button) {
  -webkit-appearance: none;
  margin: 0;
}
.line__actions {
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  justify-self: end;
  gap: var(--ods-space-8);
  min-width: 0;
  width: 100%;
}
.line__icon-btn {
  width: var(--preview-icon-touch);
  height: var(--preview-icon-touch);
  min-width: var(--preview-icon-touch);
  padding: 0;
  border: none;
  border-radius: var(--ods-radius-button);
  background: transparent;
  color: var(--ods-color-text-secondary);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.line__icon-btn:hover:not(.line__icon-btn--danger),
.line__icon-btn:active:not(.line__icon-btn--danger) {
  color: var(--ods-color-primary);
}
.line__icon-btn--danger:hover,
.line__icon-btn--danger:active {
  color: var(--ods-color-danger);
}
.line__icon-btn:focus-visible {
  outline: 2px solid var(--ods-color-primary);
  outline-offset: 2px;
}
.line__icon {
  width: 18px;
  height: 18px;
  display: block;
  flex-shrink: 0;
}
.line__dest {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ods-space-8);
  box-sizing: border-box;
  min-height: 26px;
  max-height: 28px;
  margin: 2px var(--line-pad-x, var(--ods-space-16)) 0;
  padding: 0 var(--ods-space-8);
  border-radius: var(--ods-radius-button);
  min-width: 0;
}
.line__dest--ok {
  background: var(--ods-color-primary-subtle, #f0f7f4);
}
.line__dest--warn {
  background: var(--ods-color-caution-soft);
}
.line__dest--danger {
  background: var(--ods-color-danger-soft);
}
.line__dest-status {
  font: var(--ods-font-caption);
  font-weight: 600;
  color: var(--ods-color-text-secondary);
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.line__dest--ok .line__dest-status {
  color: var(--ods-color-primary);
}
.line__dest--warn .line__dest-status {
  color: var(--ods-color-caution);
}
.line__dest--danger .line__dest-status {
  color: var(--ods-color-danger);
}
.line__dest-btn {
  flex-shrink: 0;
  border: none;
  background: transparent;
  color: var(--ods-color-primary);
  font: var(--ods-font-caption);
  font-weight: 700;
  cursor: pointer;
  padding: 0;
  min-height: 26px;
  white-space: nowrap;
}
.line__dest-btn:focus-visible {
  outline: 2px solid var(--ods-color-primary);
  outline-offset: 2px;
}

.lines__actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--ods-space-8);
  padding: var(--ods-space-8) var(--line-pad-x, var(--ods-space-16)) var(--ods-space-12);
  border-top: 1px solid var(--ods-color-border);
}

/* sticky summary + full-width CTA
 * fixed는 viewport 기준 — page inset과 동일 좌우선
 */
.footer {
  position: fixed;
  left: 0;
  right: 0;
  bottom: var(--sales-preview-nav-h);
  z-index: 40;
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-4);
  width: 100%;
  max-width: var(--sales-preview-frame-max);
  margin: 0 auto;
  box-sizing: border-box;
  padding: var(--ods-space-4) var(--sales-preview-inline) var(--ods-space-6, 6px);
  background: var(--ods-color-bg-muted, #f5f5f5);
  border-top: 1px solid var(--ods-color-border);
}
.footer__panel {
  display: flex;
  flex-direction: column;
  gap: 0;
  min-width: 0;
  box-sizing: border-box;
  padding: var(--ods-space-6, 6px) var(--ods-space-10, 10px);
  background: var(--ods-color-primary-subtle, #e8f5ee);
  border: 1px solid var(--ods-color-secondary, #66bb6a);
  border-radius: var(--ods-radius-card);
  box-shadow: none;
  line-height: 1.25;
}
.footer__top {
  margin: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ods-space-8);
  min-height: 0;
  min-width: 0;
  padding: 1px 0;
}
.footer__count {
  margin: 0;
  font: var(--ods-font-caption);
  font-weight: 700;
  color: var(--ods-color-text);
  white-space: nowrap;
}
.footer__item-amt {
  font: var(--ods-font-caption);
  font-weight: 700;
  color: var(--ods-color-text);
  font-variant-numeric: tabular-nums;
  text-align: right;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.footer__row {
  margin: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ods-space-8);
  min-height: 0;
  padding: 1px 0;
  font: var(--ods-font-caption);
  line-height: 1.25;
  color: var(--ods-color-text-secondary);
}
.footer__lbl {
  flex-shrink: 0;
}
.footer__val {
  font-variant-numeric: tabular-nums;
  text-align: right;
  color: var(--ods-color-text);
}
.footer__val--fee {
  display: inline-flex;
  align-items: center;
  gap: var(--ods-space-4);
}
.footer__divider {
  height: 1px;
  width: 100%;
  margin: 3px 0;
  background: color-mix(in srgb, var(--ods-color-secondary, #66bb6a) 40%, white);
}
.footer__total {
  margin: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ods-space-8);
  min-height: 0;
  padding: 1px 0;
  font: var(--ods-font-caption);
  font-weight: 700;
  color: var(--ods-color-text);
}
.footer__total strong {
  font: var(--ods-font-body);
  font-weight: 800;
  color: var(--ods-color-primary);
  font-variant-numeric: tabular-nums;
  text-align: right;
}
.footer__fee {
  display: inline-block;
  width: 64px;
  vertical-align: middle;
}
.footer :deep(.footer__fee.ods-input),
.footer :deep(input.footer__fee) {
  width: 64px;
  height: 24px;
  min-height: 24px;
  padding: 0 var(--ods-space-4);
  text-align: right;
  font: var(--ods-font-caption);
  background: var(--ods-color-white);
  box-sizing: border-box;
}
.footer__go {
  width: 100%;
  min-height: 44px;
  flex-shrink: 0;
  margin: 0;
}

.err {
  color: var(--ods-color-danger);
  white-space: pre-line;
  font: var(--ods-font-body-2);
}
.ok {
  color: var(--ods-color-primary);
  white-space: pre-line;
  background: var(--ods-color-primary-subtle, #f0f7f4);
  padding: var(--ods-space-8) var(--ods-space-12);
  border-radius: var(--ods-radius-button);
  font: var(--ods-font-body-2);
}

@media (max-width: 360px) {
  .preview-card--lines {
    --line-col-qty: 40px;
    --line-col-price: 64px;
    --line-col-actions: 80px;
    --line-gap: var(--ods-space-4);
  }
}

</style>
