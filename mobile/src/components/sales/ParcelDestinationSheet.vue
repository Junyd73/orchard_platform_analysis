<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'

import OdsButton from '@/components/ods/OdsButton.vue'
import OdsFormField from '@/components/ods/OdsFormField.vue'
import OdsInput from '@/components/ods/OdsInput.vue'
import OdsSelect from '@/components/ods/OdsSelect.vue'
import {
  LABEL_RCV_ADDR,
  LABEL_RCV_NAME,
  LABEL_RCV_TEL,
  formatOrderAmt,
} from '@/views/orders/ordersConstants'
import {
  emptyDeliveryDraft,
  type ShipDeliveryDraft,
} from '@/views/sales/shipDeliveryModel'

const LABEL_DEST_SHEET = '배송지 등록'
const LABEL_ADD_DEST = '+ 배송지 추가'
const LABEL_DEST_SAVE = '배송지추가'
const LABEL_DEST_DONE = '완료'
const LABEL_DEST_QTY = '수량'
const LABEL_DEST_FEE = '배송비'
const LABEL_DEST_MEMO = '배송메모'
const LABEL_DEST_PRODUCT = '상품'
const LABEL_DEST_ORDER_QTY = '주문량'
const LABEL_DEST_UNASSIGNED = '미지정'
const LABEL_DEST_COMMON_MEMO = '공통 배송메모'
const LABEL_DEST_MEMO_APPLY = '전체 적용'
const DEST_MEMO_MODE_PRODUCT = 'product'
const DEST_MEMO_MODE_ORDERER = 'orderer'
const DEST_MEMO_MODE_CUSTOM = 'custom'
const DEST_COMMON_MEMO_OPTIONS = [
  { value: DEST_MEMO_MODE_PRODUCT, label: '상품정보' },
  { value: DEST_MEMO_MODE_ORDERER, label: '주문자' },
  { value: DEST_MEMO_MODE_CUSTOM, label: '직접입력' },
] as const
const MSG_SHIP_FEE_NEG = '배송비는 0 이상이어야 합니다.'
const MSG_DEST_INCOMPLETE = '수령인·연락처·주소를 입력해 주세요.'
const MSG_DEST_QTY_OVER = '주문량을 초과할 수 없습니다.'
const MSG_DEST_ADD_OVER = '주문량이 모두 지정되어 배송지를 추가할 수 없습니다.'
const DEST_TIP_MS = 1800
const DEFAULT_TEST_PREFIX = 'sales-preview'

const props = withDefaults(
  defineProps<{
    open: boolean
    productSummary: string
    orderQty: number
    unitLabel: string
    initialDests: ShipDeliveryDraft[]
    customerDefaults: { rcv_name: string; rcv_tel: string }
    ordererName: string
    showShipFee?: boolean
    lockStructure?: boolean
    testIdPrefix?: string
    openFormIndex?: number | null
  }>(),
  {
    showShipFee: true,
    lockStructure: false,
    testIdPrefix: DEFAULT_TEST_PREFIX,
    openFormIndex: null,
  },
)

const emit = defineEmits<{
  close: []
  complete: [ShipDeliveryDraft[]]
}>()

const destFormIdx = ref<number | null>(null)
const destDrafts = ref<ShipDeliveryDraft[]>([])
const destSheetErr = ref('')
const destTip = ref<{ text: string; top: number; left: number } | null>(null)
const destQtyInputKey = ref(0)
let destTipTimer: ReturnType<typeof setTimeout> | null = null
const destCommonMemoMode = ref<string>(DEST_MEMO_MODE_PRODUCT)
const destCommonMemoText = ref('')

const tid = computed(() => props.testIdPrefix || DEFAULT_TEST_PREFIX)

function tidOf(suffix: string): string {
  return `${tid.value}-${suffix}`
}

function normalizeShipFee(raw: unknown): number {
  const n = Number(String(raw ?? '').replace(/,/g, ''))
  if (!Number.isFinite(n) || n < 0) return 0
  return Math.round(n)
}

function formatAmt(n: number): string {
  return formatOrderAmt(n)
}

function cloneInitialDests(): ShipDeliveryDraft[] {
  return (props.initialDests || []).map((a) => ({ ...a }))
}

function resetFromOpen() {
  destFormIdx.value =
    props.openFormIndex != null && props.openFormIndex >= 0 ? props.openFormIndex : null
  destSheetErr.value = ''
  destCommonMemoMode.value = DEST_MEMO_MODE_PRODUCT
  destCommonMemoText.value = String(props.productSummary || '').trim()
  destDrafts.value = cloneInitialDests()
  hideDestTip()
}

watch(
  () => props.open,
  (isOpen) => {
    if (isOpen) resetFromOpen()
    else hideDestTip()
  },
  { immediate: true },
)

function closeSheet() {
  emit('close')
}

function commonMemoTemplate(mode: string): string {
  if (mode === DEST_MEMO_MODE_ORDERER) {
    return String(props.ordererName || props.customerDefaults.rcv_name || '').trim()
  }
  if (mode === DEST_MEMO_MODE_CUSTOM) {
    return String(destCommonMemoText.value || '').trim()
  }
  return String(props.productSummary || '').trim()
}

function resolveCommonMemo(): string {
  return String(destCommonMemoText.value || '').trim()
}

function applyCommonMemoToAll() {
  const msg = resolveCommonMemo()
  destDrafts.value = destDrafts.value.map((d) => ({ ...d, dlvry_msg: msg }))
}

function setCommonMemoMode(mode: string) {
  destCommonMemoMode.value = mode
  if (mode !== DEST_MEMO_MODE_CUSTOM) {
    destCommonMemoText.value = commonMemoTemplate(mode)
  }
  applyCommonMemoToAll()
}

function setCommonMemoText(raw: string) {
  destCommonMemoText.value = raw
  destCommonMemoMode.value = DEST_MEMO_MODE_CUSTOM
  applyCommonMemoToAll()
}

function formatDestSummaryPrimary(d: ShipDeliveryDraft): string {
  const unit = props.unitLabel || '박스'
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
  if (props.showShipFee && Number(d.ship_fee) < 0) return MSG_SHIP_FEE_NEG
  if (!String(d.rcv_name).trim() || !String(d.rcv_tel).trim() || !String(d.rcv_addr).trim()) {
    return MSG_DEST_INCOMPLETE
  }
  return ''
}

function orderQtyNum(): number {
  return Math.max(0, Math.floor(Number(props.orderQty) || 0))
}

function destAssignedSumExcept(di: number): number {
  return destDrafts.value.reduce(
    (s, d, i) => (i === di ? s : s + Math.max(0, Math.floor(Number(d.qty) || 0))),
    0,
  )
}

function destMaxQtyForRow(di: number): number {
  return Math.max(0, orderQtyNum() - destAssignedSumExcept(di))
}

function hideDestTip() {
  destTip.value = null
  if (destTipTimer != null) {
    clearTimeout(destTipTimer)
    destTipTimer = null
  }
}

function showDestTipNear(selector: string, text: string) {
  const el = document.querySelector(selector) as HTMLElement | null
  const r = el?.getBoundingClientRect()
  destTip.value = {
    text,
    top: r ? r.top - 6 : 96,
    left: r ? r.left + r.width / 2 : Math.round(window.innerWidth / 2),
  }
  if (destTipTimer != null) clearTimeout(destTipTimer)
  destTipTimer = setTimeout(() => {
    destTip.value = null
    destTipTimer = null
  }, DEST_TIP_MS)
}

function setDestQty(di: number, raw: string) {
  if (props.lockStructure) {
    destQtyInputKey.value += 1
    showDestTipNear(`[data-testid="${tidOf('dest-qty')}"]`, MSG_DEST_QTY_OVER)
    return
  }
  const maxForRow = destMaxQtyForRow(di)
  const wanted = Math.max(1, Math.floor(Number(String(raw).replace(/,/g, '')) || 1))
  if (wanted > maxForRow || maxForRow < 1) {
    destQtyInputKey.value += 1
    showDestTipNear(`[data-testid="${tidOf('dest-qty')}"]`, MSG_DEST_QTY_OVER)
    return
  }
  patchDestDraft(di, { qty: wanted })
  hideDestTip()
}

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
  if (destAssignedSum() > orderQtyNum()) {
    destQtyInputKey.value += 1
    showDestTipNear(`[data-testid="${tidOf('dest-qty')}"]`, MSG_DEST_QTY_OVER)
    return false
  }
  destFormIdx.value = null
  destSheetErr.value = ''
  hideDestTip()
  return true
}

function addDestDraft() {
  if (props.lockStructure) return
  if (destFormIdx.value != null && !collapseDestForm()) return
  const sale = orderQtyNum()
  const got = destAssignedSum()
  if (got >= sale) {
    showDestTipNear(`[data-testid="${tidOf('dest-add')}"]`, MSG_DEST_ADD_OVER)
    return
  }
  const defs = props.customerDefaults
  const remain = Math.max(1, sale - got)
  destDrafts.value = [
    ...destDrafts.value,
    emptyDeliveryDraft({
      qty: Math.min(1, remain),
      rcv_name: defs.rcv_name,
      rcv_tel: defs.rcv_tel,
      ship_fee: 0,
      dlvry_msg: resolveCommonMemo(),
    }),
  ]
  destFormIdx.value = destDrafts.value.length - 1
  destSheetErr.value = ''
  hideDestTip()
}

function editDestDraft(di: number) {
  if (destFormIdx.value != null && destFormIdx.value !== di && !collapseDestForm()) return
  destFormIdx.value = di
  destSheetErr.value = ''
}

function removeDestDraft(di: number) {
  if (props.lockStructure) return
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

function destSheetRemainQty(): string {
  const sale = orderQtyNum()
  const got = destAssignedSum()
  const remain = sale - got
  const unit = props.unitLabel || '박스'
  if (remain < 0) return `초과 ${-remain}${unit}`
  return `${Math.max(0, remain)}${unit}`
}

function destSheetOrderQty(): string {
  return `${orderQtyNum()}${props.unitLabel || '박스'}`
}

function commitDestSheet() {
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
    ship_fee: props.showShipFee
      ? Math.max(0, Math.round(Number(d.ship_fee) || 0))
      : 0,
    rcv_name: String(d.rcv_name).trim(),
    rcv_tel: String(d.rcv_tel).trim(),
    rcv_addr: String(d.rcv_addr).trim(),
    dlvry_msg: String(d.dlvry_msg || '').trim(),
  }))
  emit('complete', cleaned)
}

onBeforeUnmount(() => {
  hideDestTip()
})
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="dest-overlay"
      role="dialog"
      aria-modal="true"
      :aria-label="LABEL_DEST_SHEET"
      :data-testid="tidOf('dest-sheet')"
      @click.self="closeSheet"
    >
      <div class="dest-sheet">
        <header class="dest-sheet__head">
          <div class="dest-sheet__head-main">
            <div class="dest-sheet__title-row">
              <h3 class="dest-sheet__title">{{ LABEL_DEST_SHEET }}</h3>
              <button type="button" class="dest-sheet__x" aria-label="닫기" @click="closeSheet">
                ✕
              </button>
            </div>
            <div class="dest-sheet__product" :data-testid="tidOf('dest-product')">
              <p class="dest-sheet__product-line" :data-testid="tidOf('dest-summary')">
                <span class="dest-sheet__meta">
                  <span class="dest-sheet__meta-lbl">{{ LABEL_DEST_PRODUCT }} :</span>
                  <span class="dest-sheet__meta-val">{{ productSummary }}</span>
                </span>
                <span class="dest-sheet__meta">
                  <span class="dest-sheet__meta-lbl">{{ LABEL_DEST_ORDER_QTY }} :</span>
                  <span class="dest-sheet__meta-val">{{ destSheetOrderQty() }}</span>
                </span>
                <span class="dest-sheet__meta">
                  <span class="dest-sheet__meta-lbl">{{ LABEL_DEST_UNASSIGNED }} :</span>
                  <span class="dest-sheet__meta-val">{{ destSheetRemainQty() }}</span>
                </span>
              </p>
            </div>
          </div>
        </header>

        <div class="dest-sheet__body">
          <div class="dest-common-memo" :data-testid="tidOf('dest-common-memo')">
            <OdsFormField :label="LABEL_DEST_COMMON_MEMO">
              <div class="dest-common-memo__row">
                <OdsSelect
                  :model-value="destCommonMemoMode"
                  variant="form"
                  class="dest-common-memo__mode"
                  :data-testid="tidOf('dest-common-mode')"
                  @update:model-value="setCommonMemoMode"
                >
                  <option
                    v-for="opt in DEST_COMMON_MEMO_OPTIONS"
                    :key="opt.value"
                    :value="opt.value"
                  >
                    {{ opt.label }}
                  </option>
                </OdsSelect>
                <OdsInput
                  :model-value="destCommonMemoText"
                  variant="form"
                  bare
                  class="dest-common-memo__input"
                  :data-testid="tidOf('dest-common-input')"
                  :aria-label="LABEL_DEST_COMMON_MEMO"
                  @update:model-value="setCommonMemoText"
                />
                <OdsButton
                  type="button"
                  variant="secondary"
                  class="dest-common-memo__apply"
                  :data-testid="tidOf('dest-common-apply')"
                  :disabled="!destDrafts.length"
                  @click="applyCommonMemoToAll"
                >
                  {{ LABEL_DEST_MEMO_APPLY }}
                </OdsButton>
              </div>
            </OdsFormField>
          </div>

          <ul v-if="destDrafts.length" class="dest-summary-list" aria-label="배송지 목록">
            <li
              v-for="(d, di) in destDrafts"
              v-show="di !== destFormIdx"
              :key="d.draft_id"
              class="dest-summary"
              :data-testid="tidOf('dest-summary-row')"
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
                  :data-testid="tidOf('dest-edit')"
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
                  v-if="!lockStructure"
                  type="button"
                  class="line__icon-btn line__icon-btn--danger"
                  :data-testid="tidOf('dest-remove')"
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
            :data-testid="tidOf('dest-row')"
          >
            <div
              class="dest-form__row dest-form__row--top"
              :class="{ 'dest-form__row--no-fee': !showShipFee }"
            >
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
                  :key="`dest-qty-${destFormIdx}-${destQtyInputKey}`"
                  :model-value="String(destDrafts[destFormIdx].qty)"
                  type="number"
                  min="1"
                  step="1"
                  inputmode="numeric"
                  variant="form"
                  bare
                  class="dest-form__qty"
                  :data-testid="tidOf('dest-qty')"
                  :disabled="lockStructure"
                  @update:model-value="setDestQty(destFormIdx, $event)"
                />
              </OdsFormField>
              <OdsFormField v-if="showShipFee" :label="LABEL_DEST_FEE" required>
                <OdsInput
                  :model-value="formatAmt(Number(destDrafts[destFormIdx].ship_fee))"
                  type="text"
                  inputmode="numeric"
                  variant="form"
                  bare
                  class="amt-input dest-form__fee"
                  :data-testid="tidOf('dest-fee')"
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
              :data-testid="tidOf('dest-save')"
              @click="collapseDestForm"
            >
              {{ LABEL_DEST_SAVE }}
            </OdsButton>
          </div>

          <OdsButton
            v-if="destFormIdx == null && !lockStructure"
            type="button"
            variant="secondary"
            :data-testid="tidOf('dest-add')"
            @click="addDestDraft"
          >
            {{ LABEL_ADD_DEST }}
          </OdsButton>

          <p
            v-if="destSheetErr"
            class="dest-sheet__err"
            role="alert"
            :data-testid="tidOf('dest-err')"
          >
            {{ destSheetErr }}
          </p>
        </div>

        <footer class="dest-sheet__foot">
          <OdsButton type="button" :data-testid="tidOf('dest-done')" @click="commitDestSheet">
            {{ LABEL_DEST_DONE }}
          </OdsButton>
        </footer>
      </div>
    </div>
    <div
      v-if="destTip"
      class="dest-tip"
      :data-testid="tidOf('dest-tip')"
      role="status"
      :style="{ top: `${destTip.top}px`, left: `${destTip.left}px` }"
    >
      {{ destTip.text }}
    </div>
  </Teleport>
</template>

<style scoped>
.dest-overlay {
  position: fixed;
  inset: 0;
  z-index: 200;
  background: rgba(0, 0, 0, 0.35);
  display: flex;
  align-items: flex-end;
  justify-content: center;
}
.dest-sheet {
  --preview-icon-touch: 36px;
  width: min(100%, var(--ods-page-content-max, 480px));
  max-height: min(88vh, 720px);
  background: var(--ods-color-bg, #fdfbf7);
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
  font-weight: 700;
}
.dest-sheet__product {
  min-width: 0;
  padding: var(--ods-space-8) var(--ods-space-12);
  border-radius: var(--ods-radius-button);
  background: var(--ods-color-bg-muted, #f3f4f0);
  box-sizing: border-box;
}
.dest-sheet__product-line {
  margin: 0;
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: var(--ods-space-4) var(--ods-space-16);
  min-width: 0;
  font: var(--ods-font-body-2);
  line-height: 1.35;
  font-variant-numeric: tabular-nums;
}
.dest-sheet__meta {
  display: inline-flex;
  align-items: baseline;
  gap: var(--ods-space-4);
  min-width: 0;
}
.dest-sheet__meta-lbl {
  flex-shrink: 0;
  font: var(--ods-font-caption);
  font-weight: 700;
  color: var(--ods-color-text-secondary);
}
.dest-sheet__meta-val {
  font: var(--ods-font-body-2);
  font-weight: 700;
  color: var(--ods-color-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
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
.dest-common-memo {
  min-width: 0;
}
.dest-common-memo :deep(.ods-form-field) {
  gap: var(--ods-space-4);
}
.dest-common-memo :deep(.ods-form-field__label) {
  font: var(--ods-font-caption);
  font-weight: 700;
  color: var(--ods-color-text-secondary);
}
.dest-common-memo__row {
  display: grid;
  grid-template-columns: minmax(5.5rem, 6.5rem) minmax(0, 1fr) auto;
  gap: var(--ods-space-4);
  align-items: center;
  min-width: 0;
}
.dest-common-memo__mode {
  width: 100%;
  min-width: 0;
  height: 28px;
  min-height: 28px;
  max-height: 28px;
  font: var(--ods-font-caption);
  font-weight: 600;
  padding-inline: var(--ods-space-4);
  box-sizing: border-box;
}
.dest-common-memo__input {
  min-width: 0;
  width: 100%;
}
.dest-common-memo :deep(input.ods-input),
.dest-common-memo :deep(.dest-common-memo__input.ods-input) {
  height: 28px;
  min-height: 28px;
  padding: 0 var(--ods-space-8);
  font: var(--ods-font-caption);
  font-weight: 600;
  box-sizing: border-box;
}
.dest-common-memo__apply {
  flex-shrink: 0;
  min-height: 28px !important;
  height: 28px;
  padding-inline: var(--ods-space-8);
  font: var(--ods-font-caption) !important;
  font-weight: 700 !important;
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
.dest-form__row--no-fee {
  grid-template-columns: minmax(0, 1.2fr) minmax(0, 1.1fr) 52px;
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
.amt-input :deep(input.ods-input),
:deep(input.amt-input.ods-input),
:deep(.amt-input.ods-input) {
  text-align: right;
  font-variant-numeric: tabular-nums;
}
.dest-sheet__err {
  margin: 0;
  color: var(--ods-color-danger, #b00020);
  font: var(--ods-font-footnote, 12px);
}
.dest-tip {
  position: fixed;
  z-index: 210;
  transform: translate(-50%, -100%);
  max-width: min(280px, calc(100vw - 24px));
  padding: var(--ods-space-4) var(--ods-space-8);
  border-radius: var(--ods-radius-button);
  background: color-mix(in srgb, var(--ods-color-text) 88%, transparent);
  color: var(--ods-color-white, #fff);
  font: var(--ods-font-caption);
  font-weight: 600;
  line-height: 1.35;
  text-align: center;
  pointer-events: none;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.18);
  white-space: normal;
}
.dest-sheet__foot {
  padding: var(--ods-space-12) var(--ods-space-16)
    calc(var(--ods-space-12) + env(safe-area-inset-bottom, 0px));
  border-top: 1px solid var(--ods-color-border);
}

@media (max-width: 360px) {
  .dest-form__row--top {
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  }
}
</style>
