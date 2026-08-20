<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'

import { confirmShipment } from '@/api/shipments'
import { fetchCustomers } from '@/api/orders'
import { fetchCommonCodes } from '@/api/commonCodes'
import OdsAppBar from '@/components/ods/OdsAppBar.vue'
import OdsBottomNav from '@/components/ods/OdsBottomNav.vue'
import OdsButton from '@/components/ods/OdsButton.vue'
import OdsCard from '@/components/ods/OdsCard.vue'
import OdsFormField from '@/components/ods/OdsFormField.vue'
import OdsInput from '@/components/ods/OdsInput.vue'
import OdsSelect from '@/components/ods/OdsSelect.vue'
import {
  DELIVERY_TP_DIRECT,
  DELIVERY_TP_PARCEL,
  DELIVERY_TP_VISIT,
  CODE_PARENT_DELIVERY,
  LABEL_CUSTOMER,
  LABEL_RCV_ADDR,
  LABEL_RCV_NAME,
  LABEL_RCV_TEL,
  formatOrderAmt,
  formatOrderLineSpec,
  isParcelDelivery,
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
  emptyDeliveryDraft,
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
const LABEL_ITEM_AMT = '상품금액'
const LABEL_TOTAL = '총액'
const LABEL_GO_SALE = '판매 진행'
const LABEL_EMPTY_LINES = '판매 품목이 없습니다.'
const LABEL_DLVRY_METHOD = '배송방법'
const LABEL_VIEW_DEST = '배송지 편집 ›'
const LABEL_LINES = '판매 품목'
const LABEL_DEST_SHEET = '배송지 배분'
const LABEL_ADD_DEST = '+ 배송지 추가'
const LABEL_DEST_DONE = '완료'
const LABEL_SALE_QTY = '판매수량'
const MSG_NEED_CUSTOMER = '고객을 선택해 주세요.'
const MSG_SHIP_FEE_NEG = '배송비는 0 이상이어야 합니다.'
const MSG_SUCCESS = '판매가 완료되었습니다.'
const MSG_CANCEL_PREP = '진행 중인 판매 준비를 취소하시겠습니까?'
const MSG_DEST_INCOMPLETE = '수령인·연락처·주소를 입력해 주세요.'
const HINT_PARCEL_NEED = '배송지 배분이 필요한 품목이 있습니다.'
const HINT_PARCEL_DONE = '모든 품목의 배송지가 지정되었습니다.'

const router = useRouter()
const { farmCd } = storeToRefs(useAppStore())
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
const destDrafts = ref<ShipDeliveryDraft[]>([])
const destSheetErr = ref('')

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
const unitHint = computed(() =>
  lines.value[0]?.item_cd === 'FR010300' ? '통' : '박스',
)

/** 택배 상단 보조 안내 — 미지정 합계만 요약 */
const parcelHeaderHint = computed(() => {
  if (!isParcel.value || !lines.value.length) return ''
  let unassigned = 0
  let over = 0
  let incomplete = false
  for (const ln of lines.value) {
    const sale = Math.floor(Number(ln.qty) || 0)
    const got = Math.floor(allocQtySum(ln))
    if (got < sale) {
      unassigned += sale - got
      incomplete = true
    } else if (got > sale) {
      over += got - sale
      incomplete = true
    }
  }
  if (!incomplete) return HINT_PARCEL_DONE
  if (unassigned > 0) return `${HINT_PARCEL_NEED} · 미지정 ${unassigned}${unitHint.value}`
  if (over > 0) return `${HINT_PARCEL_NEED} · 초과 ${over}${unitHint.value}`
  return HINT_PARCEL_NEED
})

function normalizeShipFee(raw: unknown): number {
  const n = Number(raw)
  if (!Number.isFinite(n) || n < 0) return 0
  return Math.round(n)
}

const canSubmit = computed(() => {
  if (busy.value || successMsg.value) return false
  if (!lines.value.length) return false
  if (!String(prefill.custmId || '').trim()) return false
  if (qtyIssue.value) return false
  if (lines.value.some((ln) => Number(ln.unit_price) < 0)) return false
  if (isParcel.value) {
    if (parcelIssue.value) return false
  } else if (Number(prefill.shipFee) < 0) {
    return false
  }
  return true
})

function lineKey(ln: (typeof lines.value)[number], idx: number) {
  return `${stockSaleSpecKey(ln)}#${idx}`
}

function lineSubtotal(idx: number) {
  const ln = lines.value[idx]
  if (!ln) return 0
  return Number(ln.qty) * Number(ln.unit_price)
}

function lineUnit(ln: (typeof lines.value)[number]) {
  return ln.item_cd === 'FR010300' ? '통' : '박스'
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

function maxQty(idx: number) {
  const ln = lines.value[idx]
  if (!ln) return 1
  if (ln.available_qty != null) return Math.max(1, Math.floor(Number(ln.available_qty)))
  return Math.max(1, Math.floor(Number(ln.qty) || 1))
}

function bumpQty(idx: number, delta: number) {
  const ln = lines.value[idx]
  if (!ln) return
  const next = Math.max(1, Math.floor(Number(ln.qty) + delta))
  prefill.updateShipLine(idx, { qty: Math.min(next, maxQty(idx)) })
}

function setQty(idx: number, raw: string) {
  const n = Number(raw)
  if (!Number.isFinite(n) || n < 1) {
    prefill.updateShipLine(idx, { qty: 1 })
    return
  }
  prefill.updateShipLine(idx, { qty: Math.min(Math.floor(n), maxQty(idx)) })
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

function addMoreItems() {
  void router.push({ name: 'orders', query: { tab: 'stock' } })
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
  destSheetErr.value = ''
  const existing = ln.delivery_allocations || []
  destDrafts.value = existing.length ? existing.map((a) => ({ ...a })) : []
}

function closeDestSheet() {
  destEditIdx.value = null
  destDrafts.value = []
  destSheetErr.value = ''
}

function customerDefaults() {
  const c = customers.value.find((x) => x.custm_id === prefill.custmId)
  return {
    rcv_name: c?.custm_nm || '',
    rcv_tel: c?.mobile || '',
  }
}

function addDestDraft() {
  const defs = customerDefaults()
  destDrafts.value = [
    ...destDrafts.value,
    emptyDeliveryDraft({
      qty: 1,
      rcv_name: defs.rcv_name,
      rcv_tel: defs.rcv_tel,
    }),
  ]
}

function removeDestDraft(di: number) {
  destDrafts.value = destDrafts.value.filter((_, i) => i !== di)
}

function patchDestDraft(di: number, patch: Partial<ShipDeliveryDraft>) {
  destDrafts.value = destDrafts.value.map((d, i) => (i === di ? { ...d, ...patch } : d))
}

function destAssignedSum() {
  return destDrafts.value.reduce((s, d) => s + Number(d.qty || 0), 0)
}

function destSheetSummary() {
  const ln = destEditIdx.value != null ? lines.value[destEditIdx.value] : null
  if (!ln) return ''
  const sale = Number(ln.qty)
  const got = destAssignedSum()
  const remain = sale - got
  const unit = lineUnit(ln)
  if (remain > 0) return `지정 ${got} / ${sale}${unit} · 미지정 ${remain}${unit}`
  if (remain < 0) return `지정 ${got} / ${sale}${unit} · ${-remain}초과`
  return `지정 ${got} / ${sale}${unit}`
}

function commitDestSheet() {
  if (destEditIdx.value == null) return
  for (const d of destDrafts.value) {
    if (!(Number(d.qty) >= 1)) {
      destSheetErr.value = '배송수량은 1 이상이어야 합니다.'
      return
    }
    if (Number(d.ship_fee) < 0) {
      destSheetErr.value = MSG_SHIP_FEE_NEG
      return
    }
    if (!String(d.rcv_name).trim() || !String(d.rcv_tel).trim() || !String(d.rcv_addr).trim()) {
      destSheetErr.value = MSG_DEST_INCOMPLETE
      return
    }
  }
  const cleaned = destDrafts.value.map((d) => ({
    ...d,
    qty: Math.max(1, Math.floor(Number(d.qty))),
    ship_fee: Math.max(0, Math.round(Number(d.ship_fee) || 0)),
    rcv_name: String(d.rcv_name).trim(),
    rcv_tel: String(d.rcv_tel).trim(),
    rcv_addr: String(d.rcv_addr).trim(),
    dlvry_msg: String(d.dlvry_msg || '').trim(),
  }))
  prefill.setShipLineDeliveries(destEditIdx.value, cleaned)
  closeDestSheet()
}

function validateBeforeConfirm(): string {
  if (!lines.value.length) return MSG_NO_PREFILL
  if (qtyIssue.value) return qtyIssue.value
  if (!String(prefill.custmId || '').trim()) return MSG_NEED_CUSTOMER
  if (isParcel.value) {
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

const destLineSpec = computed(() => {
  if (destEditIdx.value == null) return ''
  const ln = lines.value[destEditIdx.value]
  return ln ? formatOrderLineSpec(ln) : ''
})

const destSaleQty = computed(() => {
  if (destEditIdx.value == null) return 0
  return Number(lines.value[destEditIdx.value]?.qty || 0)
})

/** Sheet 상단 단위 — 현재 편집 품목 기준 (footer unitHint와 분리) */
const destSaleUnit = computed(() => {
  if (destEditIdx.value == null) return '박스'
  const ln = lines.value[destEditIdx.value]
  return ln ? lineUnit(ln) : '박스'
})

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
            <OdsFormField :label="LABEL_CUSTOMER">
              <OdsSelect v-model="custmId" variant="form" aria-label="고객 선택">
                <option value="">고객 선택</option>
                <option v-for="c in customers" :key="c.custm_id" :value="c.custm_id">
                  {{ c.custm_nm }} · {{ c.mobile }}
                </option>
              </OdsSelect>
            </OdsFormField>
            <OdsFormField :label="LABEL_DLVRY_METHOD">
              <OdsSelect
                :model-value="prefill.dlvryTp"
                variant="form"
                aria-label="배송방법"
                @update:model-value="prefill.setDelivery({ dlvryTp: $event })"
              >
                <option v-for="d in deliveryOptions" :key="d.value" :value="d.value">
                  {{ d.label }}
                </option>
              </OdsSelect>
            </OdsFormField>
          </div>
          <p
            v-if="isParcel && parcelHeaderHint"
            class="header-hint"
            :class="{
              'header-hint--ok': !parcelIssue,
              'header-hint--warn': Boolean(parcelIssue),
            }"
            data-testid="sales-preview-parcel-hint"
          >
            {{ parcelHeaderHint }}
          </p>
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

          <ul v-else class="lines__list">
            <li
              v-for="(ln, idx) in lines"
              :key="lineKey(ln, idx)"
              class="line"
              data-testid="sales-preview-line"
            >
              <div class="line__r1">
                <span class="line__title">{{ formatOrderLineSpec(ln) }}</span>
                <button
                  type="button"
                  class="line__remove"
                  data-testid="sales-preview-remove"
                  :aria-label="`${formatOrderLineSpec(ln)} 삭제`"
                  @click="removeLine(idx)"
                >
                  ×
                </button>
              </div>
              <div class="line__r2">
                <div class="qty" data-testid="sales-preview-qty">
                  <button
                    type="button"
                    class="qty__btn"
                    :disabled="Number(ln.qty) <= 1"
                    aria-label="수량 감소"
                    @click="bumpQty(idx, -1)"
                  >
                    −
                  </button>
                  <OdsInput
                    :model-value="String(ln.qty)"
                    type="number"
                    min="1"
                    :max="maxQty(idx)"
                    step="1"
                    inputmode="numeric"
                    variant="form"
                    bare
                    class="qty__input"
                    aria-label="판매 수량"
                    @update:model-value="setQty(idx, $event)"
                  />
                  <button
                    type="button"
                    class="qty__btn"
                    :disabled="Number(ln.qty) >= maxQty(idx)"
                    aria-label="수량 증가"
                    @click="bumpQty(idx, 1)"
                  >
                    +
                  </button>
                </div>
                <label class="price">
                  <span class="price__lbl">단가</span>
                  <OdsInput
                    :model-value="String(ln.unit_price)"
                    type="number"
                    min="0"
                    step="1"
                    inputmode="numeric"
                    variant="form"
                    bare
                    class="price__input"
                    data-testid="sales-preview-price"
                    aria-label="단가"
                    @update:model-value="setPrice(idx, $event)"
                  />
                </label>
                <span class="line__sub" data-testid="sales-preview-subtotal">
                  {{ formatOrderAmt(lineSubtotal(idx)) }}원
                </span>
              </div>
              <div
                v-if="isParcel"
                class="line__r3"
                :class="`line__r3--${deliveryTone(idx)}`"
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
            <p class="footer__count">{{ lines.length }}품목 · {{ totalQty }}{{ unitHint }}</p>
            <p class="footer__row">
              <span class="footer__lbl">{{ LABEL_ITEM_AMT }}</span>
              <span class="footer__val">{{ formatOrderAmt(itemAmt) }}원</span>
            </p>
            <p class="footer__row">
              <span class="footer__lbl">{{ LABEL_SHIP_FEE }}</span>
              <span class="footer__val footer__val--fee">
                <template v-if="isParcel">
                  <span data-testid="sales-preview-ship-fee-sum">{{ formatOrderAmt(safeShipFee) }}</span>원
                </template>
                <template v-else>
                  <OdsInput
                    :model-value="String(safeShipFee)"
                    type="number"
                    min="0"
                    step="1"
                    inputmode="numeric"
                    variant="form"
                    bare
                    class="footer__fee"
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
              <strong>{{ formatOrderAmt(payAmt) }}원</strong>
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

    <Teleport to="body">
      <div
        v-if="destEditIdx != null"
        class="dest-overlay"
        role="dialog"
        aria-modal="true"
        :aria-label="LABEL_DEST_SHEET"
        data-testid="sales-preview-dest-sheet"
        @click.self="closeDestSheet"
      >
        <div class="dest-sheet">
          <header class="dest-sheet__head">
            <div>
              <h3 class="dest-sheet__title">{{ LABEL_DEST_SHEET }}</h3>
              <p class="dest-sheet__spec">{{ destLineSpec }}</p>
              <p class="dest-sheet__qty">{{ LABEL_SALE_QTY }} {{ destSaleQty }}{{ destSaleUnit }}</p>
            </div>
            <button type="button" class="dest-sheet__x" aria-label="닫기" @click="closeDestSheet">✕</button>
          </header>

          <div class="dest-sheet__body">
            <div
              v-for="(d, di) in destDrafts"
              :key="d.draft_id"
              class="dest-card"
              data-testid="sales-preview-dest-row"
            >
              <p class="dest-card__lbl">배송지 {{ di + 1 }}</p>
              <OdsFormField label="수량" required>
                <OdsInput
                  :model-value="String(d.qty)"
                  type="number"
                  min="1"
                  step="1"
                  inputmode="numeric"
                  variant="form"
                  bare
                  @update:model-value="patchDestDraft(di, { qty: Math.max(1, Math.floor(Number($event) || 1)) })"
                />
              </OdsFormField>
              <OdsFormField :label="LABEL_RCV_NAME" required>
                <OdsInput
                  :model-value="d.rcv_name"
                  variant="form"
                  bare
                  @update:model-value="patchDestDraft(di, { rcv_name: $event })"
                />
              </OdsFormField>
              <OdsFormField :label="LABEL_RCV_TEL" required>
                <OdsInput
                  :model-value="d.rcv_tel"
                  variant="form"
                  bare
                  @update:model-value="patchDestDraft(di, { rcv_tel: $event })"
                />
              </OdsFormField>
              <OdsFormField :label="LABEL_RCV_ADDR" required>
                <OdsInput
                  :model-value="d.rcv_addr"
                  variant="form"
                  bare
                  @update:model-value="patchDestDraft(di, { rcv_addr: $event })"
                />
              </OdsFormField>
              <OdsFormField label="배송메모" optional>
                <OdsInput
                  :model-value="d.dlvry_msg"
                  variant="form"
                  bare
                  @update:model-value="patchDestDraft(di, { dlvry_msg: $event })"
                />
              </OdsFormField>
              <OdsFormField label="배송비" required>
                <OdsInput
                  :model-value="String(d.ship_fee)"
                  type="number"
                  min="0"
                  step="1"
                  inputmode="numeric"
                  variant="form"
                  bare
                  data-testid="sales-preview-dest-fee"
                  @update:model-value="patchDestDraft(di, { ship_fee: normalizeShipFee($event) })"
                />
              </OdsFormField>
              <button
                type="button"
                class="dest-card__del"
                data-testid="sales-preview-dest-remove"
                @click="removeDestDraft(di)"
              >
                삭제
              </button>
            </div>

            <OdsButton
              type="button"
              variant="secondary"
              data-testid="sales-preview-dest-add"
              @click="addDestDraft"
            >
              {{ LABEL_ADD_DEST }}
            </OdsButton>

            <p class="dest-sheet__sum" data-testid="sales-preview-dest-summary">
              {{ destSheetSummary() }}
            </p>
            <p v-if="destSheetErr" class="dest-sheet__err" role="alert">{{ destSheetErr }}</p>
          </div>

          <footer class="dest-sheet__foot">
            <OdsButton type="button" data-testid="sales-preview-dest-done" @click="commitDestSheet">
              {{ LABEL_DEST_DONE }}
            </OdsButton>
          </footer>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>

.page {
  /* OdsBottomNav: min-height 56 + pad 8+8 + safe-area (SalesPreview 전용, Nav 미수정) */
  --sales-preview-nav-h: calc(
    var(--ods-space-56) + var(--ods-space-8) + var(--ods-space-8)
      + env(safe-area-inset-bottom, 0px)
  );
  --sales-preview-footer-h: 16.5rem;
  --sales-preview-footer-gap: var(--ods-space-8);
  --sales-preview-frame-max: var(--ods-page-content-max, 480px);
  --preview-qty-visual: 26px;
  --preview-qty-touch: 36px;
  min-height: 100%;
  width: 100%;
  background: var(--ods-color-bg-muted, #f5f5f5);
  overflow-x: hidden;
  box-sizing: border-box;
}
.content {
  gap: var(--ods-space-12);
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
  gap: var(--ods-space-12);
  min-width: 0;
}
.preview-card--compact {
  padding: var(--ods-space-12);
}
.preview-card--lines {
  padding: 0;
  overflow: hidden;
}
.header-fields {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-12);
  min-width: 0;
}
.header-hint {
  margin: 0;
  padding: var(--ods-space-8) var(--ods-space-12);
  border-radius: var(--ods-radius-button);
  font: var(--ods-font-form-help);
  background: var(--ods-color-bg-muted);
  color: var(--ods-color-text-secondary);
}
.header-hint--ok {
  background: var(--ods-color-primary-subtle, #f0f7f4);
  color: var(--ods-color-primary);
}
.header-hint--warn {
  background: color-mix(in srgb, var(--ods-color-caution) 18%, white);
  color: var(--ods-color-gray-900);
}

.lines__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--ods-space-8);
  padding: var(--ods-space-12) var(--ods-space-16) var(--ods-space-8);
  border-bottom: 1px solid var(--ods-color-border);
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
  padding: var(--ods-space-24) var(--ods-space-16);
  font: var(--ods-font-body-2);
  color: var(--ods-color-text-secondary);
  text-align: center;
}
.lines__list {
  list-style: none;
  margin: 0;
  padding: 0;
  background: var(--ods-color-white);
}
.line {
  padding: var(--ods-space-10) var(--ods-space-16);
  border-bottom: 1px solid var(--ods-color-border);
  min-width: 0;
}
.line:last-child {
  border-bottom: none;
}
.line__r1 {
  display: grid;
  grid-template-columns: minmax(0, 1fr) var(--preview-qty-touch);
  gap: var(--ods-space-8);
  align-items: center;
  margin-bottom: var(--ods-space-6);
}
.line__title {
  font-size: var(--ods-font-size-footnote, 12px);
  line-height: 1.35;
  font-weight: 700;
  color: var(--ods-color-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}
.line__remove {
  width: var(--preview-qty-touch);
  height: var(--preview-qty-touch);
  padding: 0;
  border: none;
  border-radius: var(--ods-radius-button);
  background: transparent;
  color: var(--ods-color-text-secondary);
  font-size: 18px;
  line-height: 1;
  cursor: pointer;
}
.line__remove:active {
  background: var(--ods-color-bg-muted);
}
.line__r2 {
  display: flex;
  align-items: center;
  gap: var(--ods-space-8);
  min-width: 0;
  flex-wrap: nowrap;
}
.qty {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  flex: 0 0 auto;
}
.qty__btn {
  position: relative;
  isolation: isolate;
  width: var(--preview-qty-touch);
  height: var(--preview-qty-touch);
  min-width: var(--preview-qty-touch);
  padding: 0;
  border: none;
  background: transparent;
  color: var(--ods-color-text);
  font-size: var(--ods-font-size-footnote, 12px);
  line-height: 1;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.qty__btn::after {
  content: '';
  box-sizing: border-box;
  width: var(--preview-qty-visual);
  height: var(--preview-qty-visual);
  border: 1px solid var(--ods-color-border);
  border-radius: var(--ods-radius-button);
  background: var(--ods-color-white);
  position: absolute;
  inset: 0;
  margin: auto;
  z-index: -1;
}
.qty__btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.qty :deep(input.ods-input),
.qty :deep(.qty__input.ods-input) {
  width: 34px;
  min-width: 34px;
  max-width: 34px;
  height: var(--preview-qty-visual);
  min-height: var(--preview-qty-visual);
  padding: 0 1px;
  text-align: center;
  font-size: var(--ods-font-size-footnote, 12px);
  line-height: 1.35;
  border-radius: var(--ods-radius-button);
  background: var(--ods-color-white);
}
.qty :deep(input.ods-input::-webkit-outer-spin-button),
.qty :deep(input.ods-input::-webkit-inner-spin-button) {
  -webkit-appearance: none;
  margin: 0;
}
.price {
  display: inline-flex;
  align-items: center;
  gap: var(--ods-space-4);
  flex: 1 1 auto;
  min-width: 0;
}
.price__lbl {
  flex-shrink: 0;
  font-size: var(--ods-font-size-footnote, 12px);
  color: var(--ods-color-text-secondary);
}
.price :deep(input.ods-input),
.price :deep(.price__input.ods-input) {
  width: 100%;
  min-width: 56px;
  max-width: 88px;
  height: var(--preview-qty-visual);
  min-height: var(--preview-qty-visual);
  padding: 0 var(--ods-space-4);
  text-align: right;
  font-size: var(--ods-font-size-footnote, 12px);
  border-radius: var(--ods-radius-button);
}
.line__sub {
  flex: 0 0 auto;
  margin-left: auto;
  font-size: var(--ods-font-size-footnote, 12px);
  font-weight: 700;
  color: var(--ods-color-text);
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}

.line__r3 {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ods-space-8);
  margin-top: var(--ods-space-6);
  min-width: 0;
}
.line__dest-status {
  font-size: var(--ods-font-size-footnote, 12px);
  font-weight: 600;
  color: var(--ods-color-text-secondary);
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.line__r3--ok .line__dest-status {
  color: var(--ods-color-primary);
}
.line__r3--warn .line__dest-status {
  color: var(--ods-color-caution);
}
.line__r3--danger .line__dest-status {
  color: var(--ods-color-danger);
}
.line__dest-btn {
  flex-shrink: 0;
  border: none;
  background: transparent;
  color: var(--ods-color-primary);
  font-size: var(--ods-font-size-footnote, 12px);
  font-weight: 700;
  cursor: pointer;
  padding: var(--ods-space-4) 0;
  white-space: nowrap;
}

.lines__actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--ods-space-8);
  padding: var(--ods-space-12) var(--ods-space-16) var(--ods-space-16);
  border-top: 1px solid var(--ods-color-border);
}

/* 재고 판매예정 floating 계열 + 전체폭 primary CTA */
.footer {
  position: fixed;
  left: 0;
  right: 0;
  bottom: var(--sales-preview-nav-h);
  z-index: 40;
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-8);
  width: 100%;
  max-width: var(--sales-preview-frame-max);
  margin: 0 auto;
  box-sizing: border-box;
  padding: var(--ods-space-10) var(--ods-page-padding-x, var(--ods-space-16));
  background: var(--ods-color-bg-muted, #f5f5f5);
  border-top: 1px solid var(--ods-color-border);
}
.footer__panel {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-4);
  min-width: 0;
  padding: var(--ods-space-12) var(--ods-space-16);
  background: var(--ods-color-primary-subtle, #e8f5ee);
  border: 1px solid var(--ods-color-secondary, #66bb6a);
  border-radius: var(--ods-radius-card);
  box-shadow: 0 2px 10px rgba(46, 125, 50, 0.12);
}
.footer__count {
  margin: 0 0 var(--ods-space-4);
  font: var(--ods-font-body-2);
  font-weight: 600;
  color: var(--ods-color-text);
}
.footer__row {
  margin: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ods-space-8);
  font: var(--ods-font-body-2);
  color: var(--ods-color-text-secondary);
}
.footer__lbl {
  flex-shrink: 0;
}
.footer__val {
  font-variant-numeric: tabular-nums;
  color: var(--ods-color-text);
}
.footer__val--fee {
  display: inline-flex;
  align-items: center;
  gap: var(--ods-space-4);
}
.footer__divider {
  height: 1px;
  margin: var(--ods-space-6) 0;
  background: color-mix(in srgb, var(--ods-color-secondary, #66bb6a) 45%, white);
}
.footer__total {
  margin: 0;
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--ods-space-8);
  font: var(--ods-font-headline);
  color: var(--ods-color-text);
}
.footer__total strong {
  font: var(--ods-font-title-2);
  color: var(--ods-color-primary);
  font-variant-numeric: tabular-nums;
}
.footer__fee {
  display: inline-block;
  width: 72px;
  vertical-align: middle;
}
.footer :deep(.footer__fee.ods-input),
.footer :deep(input.footer__fee) {
  width: 72px;
  height: 28px;
  min-height: 28px;
  padding: 0 var(--ods-space-4);
  text-align: right;
  font: var(--ods-font-form-value);
  background: var(--ods-color-white);
}
.footer__go {
  width: 100%;
  min-height: 48px;
  flex-shrink: 0;
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
  .line__r2 {
    gap: var(--ods-space-4);
  }
  .price :deep(input.ods-input),
  .price :deep(.price__input.ods-input) {
    max-width: 76px;
    min-width: 48px;
  }
}

.dest-overlay {
  position: fixed;
  inset: 0;
  z-index: 80;
  background: rgba(0, 0, 0, 0.35);
  display: flex;
  align-items: flex-end;
  justify-content: center;
}
.dest-sheet {
  width: min(100%, var(--sales-preview-frame-max, 480px));
  max-height: min(88vh, 720px);
  background: var(--ods-color-bg, #FDFBF7);
  border-radius: 16px 16px 0 0;
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
  overflow: hidden;
}
.dest-sheet__head {
  display: flex;
  justify-content: space-between;
  gap: var(--ods-space-8);
  padding: var(--ods-space-16);
  border-bottom: 1px solid var(--ods-color-border);
}
.dest-sheet__title {
  margin: 0;
  font: var(--ods-font-title-3);
}
.dest-sheet__spec,
.dest-sheet__qty {
  margin: var(--ods-space-4) 0 0;
  font: var(--ods-font-footnote, 12px);
  color: var(--ods-color-text-secondary);
}
.dest-sheet__x {
  border: none;
  background: transparent;
  font-size: 18px;
  cursor: pointer;
  color: var(--ods-color-text-secondary);
}
.dest-sheet__body {
  overflow-y: auto;
  padding: var(--ods-space-12) var(--ods-space-16);
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-12);
  min-width: 0;
}
.dest-card {
  border-bottom: 1px solid var(--ods-color-border);
  padding-bottom: var(--ods-space-12);
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-8);
  min-width: 0;
}
.dest-card__lbl {
  margin: 0;
  font: var(--ods-font-body-2);
  font-weight: 700;
}
.dest-card__del {
  align-self: flex-end;
  border: none;
  background: transparent;
  color: var(--ods-color-text-secondary);
  cursor: pointer;
  font: var(--ods-font-footnote, 12px);
}
.dest-sheet__sum {
  margin: 0;
  font: var(--ods-font-footnote, 12px);
  color: var(--ods-color-text-secondary);
}
.dest-sheet__err {
  margin: 0;
  color: var(--ods-color-danger, #b00020);
  font: var(--ods-font-footnote, 12px);
}
.dest-sheet__foot {
  padding: var(--ods-space-12) var(--ods-space-16) calc(var(--ods-space-12) + env(safe-area-inset-bottom, 0px));
  border-top: 1px solid var(--ods-color-border);
}

</style>
