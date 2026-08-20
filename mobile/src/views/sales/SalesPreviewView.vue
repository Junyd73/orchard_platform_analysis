<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
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
  LABEL_DELIVERY_TP,
  LABEL_RCV_ADDR,
  LABEL_RCV_NAME,
  LABEL_RCV_TEL,
  LABEL_UNIT_PRICE,
  formatOrderAmt,
  formatOrderLineSpec,
  isParcelDelivery,
} from '@/views/orders/ordersConstants'
import {
  MSG_NO_PREFILL,
  buildShipConfirmRequest,
  findShipQtyIssue,
  mapShipApiError,
} from '@/views/sales/shipConfirmModel'
import { todayBizIso } from '@/shared/bizDate'
import { useAppStore } from '@/composables/stores/app'
import { useSalesPrefillStore } from '@/composables/stores/salesPrefill'
import type { CustomerListItem } from '@/types/order'

const LABEL_PAGE = '판매 미리보기'
const LABEL_ADD_ITEM = '+ 품목 추가'
const LABEL_SHIP_FEE = '배송비'
const LABEL_GO_SALE = '판매 진행'
const MSG_NEED_CUSTOMER = '고객을 선택해 주세요.'
const MSG_NEED_ADDR = '택배는 받는분·연락처·주소가 필요합니다.'
const MSG_SUCCESS = '판매가 완료되었습니다.'

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

const lines = computed(() => prefill.shipLines)
const custmId = computed({
  get: () => prefill.custmId || '',
  set: (v: string) => {
    const c = customers.value.find((x) => x.custm_id === v)
    prefill.setCustomer(v || null, c?.custm_nm || '')
    if (c && !prefill.rcvName) {
      prefill.setDelivery({
        rcvName: c.custm_nm || '',
        rcvTel: c.mobile || '',
      })
    }
  },
})

const showAddress = computed(() => isParcelDelivery(prefill.dlvryTp))
const itemAmt = computed(() =>
  lines.value.reduce((s, ln) => s + Number(ln.qty) * Number(ln.unit_price), 0),
)
const totalQty = computed(() =>
  lines.value.reduce((s, ln) => s + Number(ln.qty), 0),
)
const payAmt = computed(() => itemAmt.value + Number(prefill.shipFee || 0))

function lineSubtotal(idx: number) {
  const ln = lines.value[idx]
  if (!ln) return 0
  return Number(ln.qty) * Number(ln.unit_price)
}

function bumpQty(idx: number, delta: number) {
  const ln = lines.value[idx]
  if (!ln) return
  const next = Math.max(1, Math.floor(Number(ln.qty) + delta))
  const max = ln.available_qty != null ? Number(ln.available_qty) : next
  prefill.updateShipLine(idx, { qty: Math.min(next, max) })
}

function setQty(idx: number, raw: string) {
  const n = Number(raw)
  if (!Number.isFinite(n) || n < 1) {
    prefill.updateShipLine(idx, { qty: 1 })
    return
  }
  const ln = lines.value[idx]
  const max = ln?.available_qty != null ? Number(ln.available_qty) : n
  prefill.updateShipLine(idx, { qty: Math.min(Math.floor(n), max) })
}

function setPrice(idx: number, raw: string) {
  const n = Number(raw)
  prefill.updateShipLine(idx, { unit_price: Number.isFinite(n) && n >= 0 ? n : 0 })
}

function removeLine(idx: number) {
  prefill.removeShipLine(idx)
}

function addMoreItems() {
  void router.push({ name: 'orders', query: { tab: 'stock' } })
}

function validateBeforeConfirm(): string {
  if (!lines.value.length) return MSG_NO_PREFILL
  const qtyIssue = findShipQtyIssue(lines.value)
  if (qtyIssue) return qtyIssue
  if (!String(prefill.custmId || '').trim()) return MSG_NEED_CUSTOMER
  if (showAddress.value) {
    if (!prefill.rcvName.trim() || !prefill.rcvTel.trim() || !prefill.rcvAddr.trim()) {
      return MSG_NEED_ADDR
    }
  }
  return ''
}

async function onSubmit() {
  if (busy.value || successMsg.value) return
  errorMsg.value = validateBeforeConfirm()
  if (errorMsg.value) return

  const unitHint = lines.value[0]?.item_cd === 'FR010300' ? '통' : '박스'
  const confirmText =
    `${prefill.customerNm || prefill.custmId} / ${deliveryLabel(prefill.dlvryTp)}\n` +
    `${lines.value.length}품목 · 총 ${totalQty.value}${unitHint}\n` +
    `상품 ${formatOrderAmt(itemAmt.value)}원\n` +
    `배송비 ${formatOrderAmt(prefill.shipFee)}원\n` +
    `최종 ${formatOrderAmt(payAmt.value)}원\n\n` +
    '판매를 확정하시겠습니까?'
  if (!window.confirm(confirmText)) return

  busy.value = true
  errorMsg.value = ''
  try {
    const res = await confirmShipment(
      farmCd.value,
      buildShipConfirmRequest({
        shipMode: 'DIRECT',
        salesDt: todayBizIso(),
        orderNo: null,
        custmId: prefill.custmId,
        lines: lines.value,
        dlvryTp: prefill.dlvryTp,
        shipFee: prefill.shipFee,
        rcvName: prefill.rcvName,
        rcvTel: prefill.rcvTel,
        rcvAddr: prefill.rcvAddr,
        dlvryMsg: prefill.dlvryMsg,
      }),
    )
    successMsg.value =
      `${MSG_SUCCESS}\n${res.sales_no} / ${lines.value.length}품목 / ` +
      `${totalQty.value}${unitHint} / ${formatOrderAmt(payAmt.value)}원`
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

watch(
  () => prefill.dlvryTp,
  (tp) => {
    if (!isParcelDelivery(tp)) {
      // 방문/직배는 주소 필수 아님 — 값은 유지
    }
  },
)

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
  <div class="page">
    <main class="content ods-page-content">
      <OdsAppBar :show-back="true" back-fallback="orders" />

      <OdsCard>
        <h2 class="title">{{ LABEL_PAGE }}</h2>
        <p class="meta">고객 1명 · 배송방법 1개 · 배송지 1곳</p>
      </OdsCard>

      <p v-if="successMsg" class="ok" role="status">{{ successMsg }}</p>
      <p v-if="errorMsg" class="err" role="alert">{{ errorMsg }}</p>

      <template v-if="!successMsg">
        <OdsCard title="고객 / 배송">
          <div class="grid2">
            <OdsFormField :label="LABEL_CUSTOMER" required>
              <OdsSelect v-model="custmId" variant="form">
                <option value="">고객 선택</option>
                <option v-for="c in customers" :key="c.custm_id" :value="c.custm_id">
                  {{ c.custm_nm }} · {{ c.mobile }}
                </option>
              </OdsSelect>
            </OdsFormField>
            <OdsFormField :label="LABEL_DELIVERY_TP" required>
              <OdsSelect
                :model-value="prefill.dlvryTp"
                variant="form"
                @update:model-value="prefill.setDelivery({ dlvryTp: $event })"
              >
                <option v-for="d in deliveryOptions" :key="d.value" :value="d.value">
                  {{ d.label }}
                </option>
              </OdsSelect>
            </OdsFormField>
          </div>

          <div v-if="showAddress" class="addr">
            <OdsFormField :label="LABEL_RCV_NAME" required>
              <OdsInput
                :model-value="prefill.rcvName"
                variant="form"
                bare
                @update:model-value="prefill.setDelivery({ rcvName: $event })"
              />
            </OdsFormField>
            <OdsFormField :label="LABEL_RCV_TEL" required>
              <OdsInput
                :model-value="prefill.rcvTel"
                variant="form"
                bare
                @update:model-value="prefill.setDelivery({ rcvTel: $event })"
              />
            </OdsFormField>
            <OdsFormField :label="LABEL_RCV_ADDR" required>
              <OdsInput
                :model-value="prefill.rcvAddr"
                variant="form"
                bare
                @update:model-value="prefill.setDelivery({ rcvAddr: $event })"
              />
            </OdsFormField>
            <OdsFormField label="배송메모" optional>
              <OdsInput
                :model-value="prefill.dlvryMsg"
                variant="form"
                bare
                @update:model-value="prefill.setDelivery({ dlvryMsg: $event })"
              />
            </OdsFormField>
          </div>
        </OdsCard>

        <OdsCard :title="`판매 품목 ${lines.length}건`">
          <p v-if="!lines.length" class="err">{{ MSG_NO_PREFILL }}</p>
          <div v-for="(ln, idx) in lines" :key="idx" class="line">
            <p class="line__title">{{ formatOrderLineSpec(ln) }}</p>
            <div class="line__row">
              <div class="qty">
                <button type="button" class="qty__btn" @click="bumpQty(idx, -1)">-</button>
                <OdsInput
                  :model-value="String(ln.qty)"
                  type="number"
                  min="1"
                  step="1"
                  variant="form"
                  bare
                  class="qty__input"
                  @update:model-value="setQty(idx, $event)"
                />
                <button type="button" class="qty__btn" @click="bumpQty(idx, 1)">+</button>
              </div>
              <OdsFormField :label="LABEL_UNIT_PRICE">
                <OdsInput
                  :model-value="String(ln.unit_price)"
                  type="number"
                  min="0"
                  step="1"
                  variant="form"
                  bare
                  @update:model-value="setPrice(idx, $event)"
                />
              </OdsFormField>
            </div>
            <div class="line__foot">
              <span>소계 {{ formatOrderAmt(lineSubtotal(idx)) }}원</span>
              <button type="button" class="link" @click="removeLine(idx)">삭제</button>
            </div>
          </div>
          <OdsButton type="button" variant="secondary" @click="addMoreItems">
            {{ LABEL_ADD_ITEM }}
          </OdsButton>
        </OdsCard>

        <div class="footer">
          <p class="footer__sum">
            {{ lines.length }}품목 · 총 {{ totalQty }}
          </p>
          <div class="footer__row">
            <span>상품금액</span>
            <strong>{{ formatOrderAmt(itemAmt) }}원</strong>
          </div>
          <div class="footer__row">
            <span>{{ LABEL_SHIP_FEE }}</span>
            <OdsInput
              :model-value="String(prefill.shipFee)"
              type="number"
              min="0"
              step="1"
              variant="form"
              bare
              class="fee"
              @update:model-value="prefill.setDelivery({ shipFee: Number($event) || 0 })"
            />
          </div>
          <div class="footer__row footer__row--total">
            <span>결제예정금액</span>
            <strong>{{ formatOrderAmt(payAmt) }}원</strong>
          </div>
          <OdsButton type="button" :disabled="busy || !lines.length" @click="onSubmit">
            {{ busy ? '처리 중…' : LABEL_GO_SALE }}
          </OdsButton>
        </div>
      </template>

      <OdsButton v-else type="button" @click="goStock">재고로 돌아가기</OdsButton>
    </main>
    <OdsBottomNav />
  </div>
</template>

<style scoped>
.page { min-height: 100%; background: var(--ods-color-bg, #FDFBF7); }
.content { display: flex; flex-direction: column; gap: var(--ods-space-12); padding-bottom: 120px; }
.title { margin: 0; font: var(--ods-font-title-3); }
.meta { margin: var(--ods-space-4) 0 0; font: var(--ods-font-footnote); color: var(--ods-color-text-secondary); }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: var(--ods-space-8); }
.addr { display: flex; flex-direction: column; gap: var(--ods-space-8); margin-top: var(--ods-space-8); }
.line { padding: var(--ods-space-8) 0; border-bottom: 1px solid var(--ods-color-border); }
.line__title { margin: 0 0 var(--ods-space-8); font: var(--ods-font-body-2); font-weight: 700; }
.line__row { display: grid; grid-template-columns: 1fr 1fr; gap: var(--ods-space-8); align-items: end; }
.line__foot { display: flex; justify-content: space-between; margin-top: var(--ods-space-8); font: var(--ods-font-body-2); }
.qty { display: flex; align-items: center; gap: var(--ods-space-4); }
.qty__btn { width: 32px; height: 32px; border: 1px solid var(--ods-color-border); border-radius: var(--ods-radius-button); background: #fff; }
.qty__input { width: 64px; text-align: center; }
.link { border: none; background: transparent; color: var(--ods-color-danger); font: var(--ods-font-footnote); }
.footer {
  position: sticky; bottom: 56px; z-index: 5;
  background: var(--ods-color-white, #fff);
  border: 1px solid var(--ods-color-border);
  border-radius: var(--ods-radius-card);
  padding: var(--ods-space-12);
  display: flex; flex-direction: column; gap: var(--ods-space-8);
}
.footer__sum { margin: 0; font-weight: 700; }
.footer__row { display: flex; justify-content: space-between; align-items: center; font: var(--ods-font-body-2); }
.footer__row--total { font-size: 16px; }
.fee { width: 120px; text-align: right; }
.err { color: var(--ods-color-danger); white-space: pre-line; }
.ok { color: #2F855A; white-space: pre-line; background: #E6F4EA; padding: var(--ods-space-8); border-radius: var(--ods-radius-card); }
@media (max-width: 430px) {
  .grid2, .line__row { grid-template-columns: 1fr; }
}
</style>
