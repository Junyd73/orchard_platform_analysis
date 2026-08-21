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
  formatWeightLabel,
  isJuiceItemCd,
  isParcelDelivery,
  joinDot,
  juiceItemLabel,
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
const LABEL_TOTAL = '총액'
const LABEL_GO_SALE = '판매 진행'
const LABEL_EMPTY_LINES = '판매 품목이 없습니다.'
const LABEL_DLVRY_METHOD = '배송방법'
const LABEL_DLVRY_SHORT = '배송'
const LABEL_PARCEL_SETUP = '설정 ›'
const LABEL_VIEW_DEST = '배송지 편집 ›'
const LABEL_LINES = '판매 품목'
const LABEL_COL_ITEM = '품목'
const LABEL_COL_QTY = '수량'
const LABEL_COL_PRICE = '단가'
const LABEL_DEST_SHEET = '배송지 등록'
const LABEL_ADD_DEST = '+ 배송지 추가'
const LABEL_DEST_SAVE = '배송지추가'
const LABEL_DEST_DONE = '완료'
const LABEL_SALE_QTY = '판매수량'
const LABEL_DEST_QTY = '수량'
const LABEL_DEST_FEE = '배송비'
const LABEL_DEST_MEMO = '배송메모'
const MSG_NEED_CUSTOMER = '고객을 선택해 주세요.'
const MSG_SHIP_FEE_NEG = '배송비는 0 이상이어야 합니다.'
const MSG_SUCCESS = '판매가 완료되었습니다.'
const MSG_CANCEL_PREP = '진행 중인 판매 준비를 취소하시겠습니까?'
const MSG_DEST_INCOMPLETE = '수령인·연락처·주소를 입력해 주세요.'
const HINT_PARCEL_DONE = '배송지 지정 완료'

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
/** sheet 내 편집 중인 배송지 index — null이면 전부 요약 1줄 */
const destFormIdx = ref<number | null>(null)
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

/** 택배 상단 보조 안내 — 미지정/초과 합계만 짧게 */
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
  if (unassigned > 0) return `미지정 ${unassigned}${unitHint.value}`
  if (over > 0) return `초과 ${over}${unitHint.value}`
  return '미지정'
})

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

/** 상단 미지정 bar → 첫 미완료 품목 배송지 sheet */
function openFirstIncompleteDest() {
  const idx = lines.value.findIndex((_, i) => deliveryTone(i) !== 'ok')
  if (idx >= 0) openDestSheet(idx)
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
  destFormIdx.value = null
  destSheetErr.value = ''
  const existing = ln.delivery_allocations || []
  destDrafts.value = existing.length ? existing.map((a) => ({ ...a })) : []
}

function closeDestSheet() {
  destEditIdx.value = null
  destFormIdx.value = null
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

function formatDestSummaryPrimary(d: ShipDeliveryDraft): string {
  const unit = destSaleUnit.value
  const name = String(d.rcv_name || '').trim() || '수령인 미입력'
  const tel = String(d.rcv_tel || '').trim()
  const qty = `${Math.max(0, Math.floor(Number(d.qty) || 0))}${unit}`
  return [name, tel, qty].filter(Boolean).join(' · ')
}

function formatDestSummaryAddr(d: ShipDeliveryDraft): string {
  return String(d.rcv_addr || '').trim()
}

function formatDestSummaryMemo(d: ShipDeliveryDraft): string {
  return String(d.dlvry_msg || '').trim()
}

function destDraftFieldError(d: ShipDeliveryDraft): string {
  if (!(Number(d.qty) >= 1)) return '배송수량은 1 이상이어야 합니다.'
  if (Number(d.ship_fee) < 0) return MSG_SHIP_FEE_NEG
  if (!String(d.rcv_name).trim() || !String(d.rcv_tel).trim() || !String(d.rcv_addr).trim()) {
    return MSG_DEST_INCOMPLETE
  }
  return ''
}

/** 편집 폼 → 상단 요약. 유효하지 않으면 false */
function collapseDestForm(): boolean {
  if (destFormIdx.value == null) return true
  const d = destDrafts.value[destFormIdx.value]
  if (!d) {
    destFormIdx.value = null
    return true
  }
  const err = destDraftFieldError(d)
  if (err) {
    destSheetErr.value = err
    return false
  }
  destFormIdx.value = null
  destSheetErr.value = ''
  return true
}

function addDestDraft() {
  if (destFormIdx.value != null && !collapseDestForm()) return
  const defs = customerDefaults()
  destDrafts.value = [
    ...destDrafts.value,
    emptyDeliveryDraft({
      qty: 1,
      rcv_name: defs.rcv_name,
      rcv_tel: defs.rcv_tel,
    }),
  ]
  destFormIdx.value = destDrafts.value.length - 1
  destSheetErr.value = ''
}

function editDestDraft(di: number) {
  if (destFormIdx.value != null && destFormIdx.value !== di && !collapseDestForm()) return
  destFormIdx.value = di
  destSheetErr.value = ''
}

function removeDestDraft(di: number) {
  destDrafts.value = destDrafts.value.filter((_, i) => i !== di)
  if (destFormIdx.value == null) return
  if (destFormIdx.value === di) destFormIdx.value = null
  else if (destFormIdx.value > di) destFormIdx.value -= 1
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
  if (destFormIdx.value != null && !collapseDestForm()) return
  for (const d of destDrafts.value) {
    const err = destDraftFieldError(d)
    if (err) {
      destSheetErr.value = err
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
              v-if="isParcel && parcelHeaderHint"
              class="header-hint"
              :class="{
                'header-hint--ok': !parcelIssue,
                'header-hint--warn': Boolean(parcelIssue),
              }"
              data-testid="sales-preview-parcel-hint"
            >
              <span class="header-hint__txt">{{ parcelHeaderHint }}</span>
              <button
                v-if="parcelIssue"
                type="button"
                class="header-hint__act"
                data-testid="sales-preview-parcel-setup"
                @click="openFirstIncompleteDest"
              >
                {{ LABEL_PARCEL_SETUP }}
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
            <div class="dest-sheet__head-main">
              <div class="dest-sheet__title-row">
                <h3 class="dest-sheet__title">{{ LABEL_DEST_SHEET }}</h3>
                <button type="button" class="dest-sheet__x" aria-label="닫기" @click="closeDestSheet">
                  ✕
                </button>
              </div>
              <div class="dest-sheet__product" data-testid="sales-preview-dest-product">
                <p class="dest-sheet__spec">{{ destLineSpec }}</p>
                <p class="dest-sheet__qty">
                  <span class="dest-sheet__qty-lbl">{{ LABEL_SALE_QTY }}</span>
                  <strong class="dest-sheet__qty-val">{{ destSaleQty }}{{ destSaleUnit }}</strong>
                </p>
                <p class="dest-sheet__sum" data-testid="sales-preview-dest-summary">
                  {{ destSheetSummary() }}
                </p>
              </div>
            </div>
          </header>

          <div class="dest-sheet__body">
            <ul v-if="destDrafts.length" class="dest-summary-list" aria-label="배송지 목록">
              <li
                v-for="(d, di) in destDrafts"
                v-show="di !== destFormIdx"
                :key="d.draft_id"
                class="dest-summary"
                data-testid="sales-preview-dest-summary-row"
              >
                <div class="dest-summary__body">
                  <p class="dest-summary__line1">{{ formatDestSummaryPrimary(d) }}</p>
                  <p class="dest-summary__line2">
                    <span
                      class="dest-summary__addr"
                      :title="formatDestSummaryAddr(d) || undefined"
                    >{{ formatDestSummaryAddr(d) || '주소 미입력' }}</span>
                    <template v-if="formatDestSummaryMemo(d)">
                      <span class="dest-summary__sep" aria-hidden="true"> · </span>
                      <span class="dest-summary__memo">{{ formatDestSummaryMemo(d) }}</span>
                    </template>
                  </p>
                </div>
                <div class="dest-summary__actions">
                  <button
                    type="button"
                    class="line__icon-btn"
                    data-testid="sales-preview-dest-edit"
                    :aria-label="`배송지 ${di + 1} 수정`"
                    title="수정"
                    @click="editDestDraft(di)"
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
                    data-testid="sales-preview-dest-remove"
                    :aria-label="`배송지 ${di + 1} 삭제`"
                    title="삭제"
                    @click="removeDestDraft(di)"
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
                        d="M7.5 8.2v6M10 8.2v6M12.5 8.2v6"
                        stroke="currentColor"
                        stroke-width="1.4"
                        stroke-linecap="round"
                      />
                      <path
                        d="M6.2 6.2l.6 10.2a1 1 0 001 .8h4.4a1 1 0 001-.8l.6-10.2"
                        stroke="currentColor"
                        stroke-width="1.4"
                        stroke-linejoin="round"
                      />
                    </svg>
                  </button>
                </div>
              </li>
            </ul>

            <div
              v-if="destFormIdx != null && destDrafts[destFormIdx]"
              class="dest-form"
              data-testid="sales-preview-dest-row"
            >
              <div class="dest-form__row dest-form__row--top">
                <OdsFormField :label="LABEL_RCV_NAME" required>
                  <OdsInput
                    :model-value="destDrafts[destFormIdx].rcv_name"
                    variant="form"
                    bare
                    @update:model-value="patchDestDraft(destFormIdx, { rcv_name: $event })"
                  />
                </OdsFormField>
                <OdsFormField :label="LABEL_RCV_TEL" required>
                  <OdsInput
                    :model-value="destDrafts[destFormIdx].rcv_tel"
                    variant="form"
                    bare
                    @update:model-value="patchDestDraft(destFormIdx, { rcv_tel: $event })"
                  />
                </OdsFormField>
                <OdsFormField :label="LABEL_DEST_QTY" required>
                  <OdsInput
                    :model-value="String(destDrafts[destFormIdx].qty)"
                    type="number"
                    min="1"
                    step="1"
                    inputmode="numeric"
                    variant="form"
                    bare
                    class="dest-form__qty"
                    @update:model-value="
                      patchDestDraft(destFormIdx, {
                        qty: Math.max(1, Math.floor(Number($event) || 1)),
                      })
                    "
                  />
                </OdsFormField>
                <OdsFormField :label="LABEL_DEST_FEE" required>
                  <OdsInput
                    :model-value="formatAmt(Number(destDrafts[destFormIdx].ship_fee))"
                    type="text"
                    inputmode="numeric"
                    variant="form"
                    bare
                    class="amt-input dest-form__fee"
                    data-testid="sales-preview-dest-fee"
                    @update:model-value="
                      patchDestDraft(destFormIdx, { ship_fee: normalizeShipFee($event) })
                    "
                  />
                </OdsFormField>
              </div>
              <OdsFormField :label="LABEL_RCV_ADDR" required>
                <OdsInput
                  :model-value="destDrafts[destFormIdx].rcv_addr"
                  variant="form"
                  bare
                  @update:model-value="patchDestDraft(destFormIdx, { rcv_addr: $event })"
                />
              </OdsFormField>
              <OdsFormField :label="LABEL_DEST_MEMO" optional>
                <OdsInput
                  :model-value="destDrafts[destFormIdx].dlvry_msg"
                  variant="form"
                  bare
                  @update:model-value="patchDestDraft(destFormIdx, { dlvry_msg: $event })"
                />
              </OdsFormField>
              <OdsButton
                type="button"
                variant="secondary"
                data-testid="sales-preview-dest-save"
                @click="collapseDestForm"
              >
                {{ LABEL_DEST_SAVE }}
              </OdsButton>
            </div>

            <OdsButton
              v-if="destFormIdx == null"
              type="button"
              variant="secondary"
              data-testid="sales-preview-dest-add"
              @click="addDestDraft"
            >
              {{ LABEL_ADD_DEST }}
            </OdsButton>

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
  --sales-preview-footer-h: 11rem;
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
  padding: var(--ods-space-12);
  gap: var(--ods-space-8);
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
  gap: var(--ods-space-8);
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
  color: var(--ods-color-primary);
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
  gap: var(--ods-space-8);
  width: 100%;
  max-width: var(--sales-preview-frame-max);
  margin: 0 auto;
  box-sizing: border-box;
  padding: var(--ods-space-8) var(--sales-preview-inline);
  background: var(--ods-color-bg-muted, #f5f5f5);
  border-top: 1px solid var(--ods-color-border);
}
.footer__panel {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-4);
  min-width: 0;
  box-sizing: border-box;
  padding: var(--ods-space-12);
  background: var(--ods-color-primary-subtle, #e8f5ee);
  border: 1px solid var(--ods-color-secondary, #66bb6a);
  border-radius: var(--ods-radius-card);
  box-shadow: none;
}
.footer__top {
  margin: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ods-space-8);
  min-height: 24px;
  min-width: 0;
}
.footer__count {
  margin: 0;
  font: var(--ods-font-body-2);
  font-weight: 600;
  color: var(--ods-color-text);
  white-space: nowrap;
}
.footer__item-amt {
  font: var(--ods-font-body-2);
  font-weight: 600;
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
  min-height: 28px;
  font: var(--ods-font-body-2);
  line-height: 1.35;
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
  margin: var(--ods-space-4) 0;
  background: color-mix(in srgb, var(--ods-color-secondary, #66bb6a) 40%, white);
}
.footer__total {
  margin: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ods-space-8);
  min-height: 28px;
  font: var(--ods-font-headline);
  color: var(--ods-color-text);
}
.footer__total strong {
  font: var(--ods-font-title-2);
  color: var(--ods-color-primary);
  font-variant-numeric: tabular-nums;
  text-align: right;
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
  box-sizing: border-box;
}
.footer__go {
  width: 100%;
  min-height: var(--ods-button-height, 48px);
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
  padding: var(--ods-space-12) var(--ods-space-16);
  border-bottom: 1px solid var(--ods-color-border);
}
.dest-sheet__head-main {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-8);
  min-width: 0;
  width: 100%;
}
.dest-sheet__title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ods-space-8);
  min-width: 0;
}
.dest-sheet__title {
  margin: 0;
  font: var(--ods-font-title-3);
}
.dest-sheet__product {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-4);
  min-width: 0;
  padding: var(--ods-space-8) var(--ods-space-12);
  border-radius: var(--ods-radius-button);
  background: var(--ods-color-bg-muted, #f3f4f0);
  box-sizing: border-box;
}
.dest-sheet__spec {
  margin: 0;
  font: var(--ods-font-body-2);
  font-weight: 700;
  color: var(--ods-color-text);
  line-height: 1.35;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.dest-sheet__qty {
  margin: 0;
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--ods-space-8);
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
}
.dest-sheet__qty-lbl {
  flex-shrink: 0;
}
.dest-sheet__qty-val {
  font: var(--ods-font-body-2);
  font-weight: 700;
  color: var(--ods-color-primary);
  font-variant-numeric: tabular-nums;
}
.dest-sheet__sum {
  margin: 0;
  padding-top: var(--ods-space-4);
  border-top: 1px solid color-mix(in srgb, var(--ods-color-border) 70%, transparent);
  font: var(--ods-font-caption);
  font-weight: 600;
  color: var(--ods-color-text-secondary);
  font-variant-numeric: tabular-nums;
}
.dest-sheet__x {
  border: none;
  background: transparent;
  font-size: 18px;
  cursor: pointer;
  color: var(--ods-color-text-secondary);
  flex-shrink: 0;
  line-height: 1;
  padding: var(--ods-space-4);
}
.dest-sheet__body {
  overflow-y: auto;
  padding: var(--ods-space-12) var(--ods-space-16);
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-12);
  min-width: 0;
}
.dest-summary-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-4);
  min-width: 0;
}
.dest-summary {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--ods-space-8);
  min-height: var(--preview-icon-touch, 40px);
  padding: var(--ods-space-8) 0;
  border-bottom: 1px solid var(--ods-color-border);
  min-width: 0;
}
.dest-summary__body {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.dest-summary__line1 {
  margin: 0;
  font: var(--ods-font-body-2);
  font-weight: 700;
  color: var(--ods-color-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.dest-summary__line2 {
  margin: 0;
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.dest-summary__addr {
  cursor: help;
}
.dest-summary__memo {
  color: var(--ods-color-text-secondary);
}
.dest-summary__actions {
  display: inline-flex;
  align-items: center;
  gap: var(--ods-space-4);
  flex-shrink: 0;
  align-self: center;
}
.dest-form {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-8);
  min-width: 0;
  padding-bottom: var(--ods-space-4);
  border-bottom: 1px solid var(--ods-color-border);
}
.dest-form__row--top {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(0, 1.1fr) 52px 72px;
  gap: var(--ods-space-8);
  align-items: start;
  min-width: 0;
}
.dest-form :deep(.ods-form-field__label) {
  font: var(--ods-font-caption);
  font-weight: 700;
}
.dest-form :deep(input.ods-input) {
  height: 36px;
  min-height: 36px;
  padding: 0 var(--ods-space-8);
  box-sizing: border-box;
}
.dest-form__qty :deep(input.ods-input),
.dest-form :deep(input.dest-form__qty.ods-input),
.dest-form :deep(.dest-form__qty.ods-input) {
  text-align: right;
  font-variant-numeric: tabular-nums;
  padding-inline: var(--ods-space-4);
}
.dest-form__fee :deep(input.ods-input),
.dest-form :deep(input.dest-form__fee.ods-input),
.dest-form :deep(.dest-form__fee.ods-input) {
  text-align: right;
  font-variant-numeric: tabular-nums;
  padding-inline: var(--ods-space-4);
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

@media (max-width: 360px) {
  .dest-form__row--top {
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  }
}

</style>
