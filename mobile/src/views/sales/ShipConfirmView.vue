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
import OdsFormField from '@/components/ods/OdsFormField.vue'
import OdsInput from '@/components/ods/OdsInput.vue'
import OdsSelect from '@/components/ods/OdsSelect.vue'
import {
  LABEL_CUSTOMER,
  LABEL_QTY,
  LABEL_UNIT_PRICE,
  MSG_NEED_SENDER,
  MSG_UNTRACKED_DEST_RECHECK,
  formatOrderAmt,
  formatOrderLineSpec,
  isParcelDelivery,
  joinDot,
  saleUnitLabel,
} from '@/views/orders/ordersConstants'
import {
  CODE_PARENT_SALES_CATEGORY,
  CODE_PARENT_SALES_TYPE,
  LABEL_CONFIRM_SHIP,
  LABEL_MODE,
  LABEL_MODE_DIRECT,
  LABEL_MODE_STOCK,
  LABEL_ORDER,
  LABEL_REMAINING,
  LABEL_SALES_CATEGORY,
  LABEL_SALES_CLASS,
  LABEL_SALES_TYPE,
  LABEL_SHIP_LINE,
  LABEL_SHIP_PAGE,
  HINT_SHIP_ORDER,
  HINT_SHIP_PRODUCTION,
  HINT_SHIP_STOCK,
  MSG_CONFIRM_OK,
  MSG_DIRECT_SALES_CATEGORY_REQUIRED,
  MSG_DIRECT_SALES_TYPE_REQUIRED,
  MSG_NO_PREFILL,
  MSG_STOCK_MODE_NEED_ALLOC,
  MSG_STOCK_MODE_PARTIAL_ALLOC,
  SALES_CATEGORY_AUCTION_CD,
  SHIP_MODE_DIRECT,
  SHIP_MODE_STOCK,
  buildShipConfirmRequest,
  canUseStockMode,
  findShipQtyIssue,
  findStockModeIssue,
  mapShipApiError,
  orderStatusLabel,
  type ShipDeliveryDraft,
  type ShipDraftLine,
} from '@/views/sales/shipConfirmModel'
import {
  QTY_EPS,
  allocQtySum,
  deliveryQtyTone,
  findParcelDeliveryIssue,
  orderParcelStatusText,
  totalAllocShipFee,
} from '@/views/sales/shipDeliveryModel'
import { todayBizIso } from '@/shared/bizDate'
import { useAppStore } from '@/composables/stores/app'
import { useSalesPrefillStore } from '@/composables/stores/salesPrefill'
import type { CommonCodeItem } from '@/types/commonCode'
import type { CustomerListItem } from '@/types/order'
import type { ShipConfirmResponse, ShipMode } from '@/types/shipment'

const LABEL_SENDER = '보내는 사람'
const LABEL_SENDER_UNSET = '미설정'
const LABEL_SENDER_SETUP = '설정 ›'
const LABEL_SENDER_EDIT = '편집 ›'
const LABEL_VIEW_DEST = '배송지 편집 ›'
const LABEL_SHIP_FEE = '배송비'
const TEST_PREFIX = 'ship-confirm'

const router = useRouter()
const { farmCd, farm } = storeToRefs(useAppStore())
const prefill = useSalesPrefillStore()

const busy = ref(false)
const errorMsg = ref('')
const done = ref<ShipConfirmResponse | null>(null)
const customers = ref<CustomerListItem[]>([])
const salesTypes = ref<CommonCodeItem[]>([])
const salesCategories = ref<CommonCodeItem[]>([])
const lines = ref<ShipDraftLine[]>([])
const shipMode = ref<ShipMode>(SHIP_MODE_DIRECT)
const custmId = ref('')

const salesTypeCd = computed({
  get: () => prefill.salesTypeCd || '',
  set: (v: string) => {
    prefill.salesTypeCd = v
  },
})
const salesCategoryCd = computed({
  get: () => prefill.salesCategoryCd || '',
  set: (v: string) => {
    prefill.salesCategoryCd = v
  },
})

const source = computed(() => prefill.source)
const hasOrder = computed(() => Boolean(prefill.orderNo))
const canPickStockMode = computed(
  () => hasOrder.value && canUseStockMode(lines.value),
)
const stockModeHint = computed(() => {
  if (!hasOrder.value || canPickStockMode.value) return ''
  const anyAlloc = lines.value.some((ln) => ln.alloc_remaining > 1e-9)
  return anyAlloc ? MSG_STOCK_MODE_PARTIAL_ALLOC : MSG_STOCK_MODE_NEED_ALLOC
})
const stockModeBlocked = computed(
  () => shipMode.value === SHIP_MODE_STOCK && !canPickStockMode.value,
)
const contextText = computed(() => {
  if (source.value === 'PRODUCTION') return '생산 직후 판매'
  if (source.value === 'ORDER') return '주문 출고'
  if (source.value === 'STOCK') return '재고 직접 판매'
  return LABEL_SHIP_PAGE
})
const contextHint = computed(() => {
  if (source.value === 'PRODUCTION') return HINT_SHIP_PRODUCTION
  if (source.value === 'ORDER') return HINT_SHIP_ORDER
  if (source.value === 'STOCK') return HINT_SHIP_STOCK
  return ''
})
const showModeToggle = computed(
  () => prefill.allowModeChange && hasOrder.value,
)

/** 주문 택배 출고 — 상품별 배송지 지정 + 판매 공통 보내는 사람 */
const isOrderParcel = computed(
  () => source.value === 'ORDER' && isParcelDelivery(prefill.dlvryTp),
)
const senderConfigured = computed(() =>
  Boolean(
    String(prefill.senderName || '').trim()
    && String(prefill.senderTel || '').trim()
    && String(prefill.senderAddr || '').trim(),
  ),
)
const senderSummary = computed(() =>
  senderConfigured.value ? joinDot([prefill.senderName, prefill.senderTel]) : '',
)
const senderIssue = computed(() => {
  if (!isOrderParcel.value) return ''
  return senderConfigured.value ? '' : MSG_NEED_SENDER
})
const parcelIssue = computed(() =>
  isOrderParcel.value ? findParcelDeliveryIssue(lines.value) : '',
)
const parcelShipFee = computed(() => totalAllocShipFee(lines.value))
/** order_dlvry_id 없는 과거 출고분이 있으면 seed를 신뢰할 수 없어 재확인을 안내 */
const untrackedHint = computed(() => {
  if (!isOrderParcel.value) return ''
  const hasUntracked = lines.value.some(
    (ln) => Number(ln.untracked_delivery_shipped_qty || 0) > QTY_EPS,
  )
  return hasUntracked ? MSG_UNTRACKED_DEST_RECHECK : ''
})

function specText(ln: ShipDraftLine): string {
  return formatOrderLineSpec(ln)
}

function lineUnit(ln: ShipDraftLine): string {
  return saleUnitLabel(ln.item_cd)
}

function lineDestStatus(ln: ShipDraftLine): string {
  return orderParcelStatusText(Number(ln.qty), allocQtySum(ln), lineUnit(ln))
}

function lineDestTone(ln: ShipDraftLine): 'ok' | 'warn' | 'danger' {
  return deliveryQtyTone(Number(ln.qty), allocQtySum(ln))
}

const destEditIdx = ref<number | null>(null)
const destSheetLine = computed(() =>
  destEditIdx.value != null ? lines.value[destEditIdx.value] ?? null : null,
)
const destProductSummary = computed(() =>
  destSheetLine.value ? formatOrderLineSpec(destSheetLine.value) : '',
)
const destOrderQty = computed(() =>
  Math.max(0, Math.floor(Number(destSheetLine.value?.qty || 0))),
)
const destUnitLabel = computed(() =>
  destSheetLine.value ? lineUnit(destSheetLine.value) : saleUnitLabel(''),
)
const destInitialDests = computed((): ShipDeliveryDraft[] =>
  (destSheetLine.value?.delivery_allocations || []).map((a) => ({ ...a })),
)
const destCustomerDefaults = computed(() => ({
  rcv_name: String(prefill.customerNm || '').trim(),
  rcv_tel: '',
}))

function openDestSheet(idx: number) {
  if (!lines.value[idx]) return
  destEditIdx.value = idx
}

function closeDestSheet() {
  destEditIdx.value = null
}

/** 수량 변경과 무관하게 사용자가 확정한 배송지만 반영한다(자동 축소·삭제 없음). */
function onDestComplete(cleaned: ShipDeliveryDraft[]) {
  const idx = destEditIdx.value
  if (idx == null || !lines.value[idx]) return
  lines.value[idx].delivery_allocations = cleaned
  closeDestSheet()
}

const senderSheetOpen = ref(false)
const farmAddress = computed(() => String(farm.value?.address || '').trim())

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

function goBackAfterSuccess() {
  const to = prefill.returnTo
  const orderNo = prefill.orderNo
  prefill.clear()
  if (to === 'order-detail' && orderNo) {
    void router.replace({ name: 'order-detail', params: { orderNo } })
    return
  }
  if (to === 'stock') {
    void router.replace({ name: 'orders', query: { tab: 'stock' } })
    return
  }
  void router.replace({ name: 'orders', query: { tab: 'sales' } })
}

async function onConfirm() {
  if (busy.value || done.value) return
  errorMsg.value = findShipQtyIssue(lines.value)
  if (errorMsg.value) return
  if (!lines.value.length) {
    errorMsg.value = MSG_NO_PREFILL
    return
  }
  if (shipMode.value === SHIP_MODE_STOCK && !hasOrder.value) {
    errorMsg.value = MSG_STOCK_MODE_NEED_ALLOC
    return
  }
  if (shipMode.value === SHIP_MODE_STOCK) {
    errorMsg.value = findStockModeIssue(lines.value)
    if (errorMsg.value) return
  }
  if (isOrderParcel.value) {
    errorMsg.value = senderIssue.value || parcelIssue.value
    if (errorMsg.value) return
  }
  if (!hasOrder.value) {
    if (!String(prefill.salesTypeCd || '').trim()) {
      errorMsg.value = MSG_DIRECT_SALES_TYPE_REQUIRED
      return
    }
    if (!String(prefill.salesCategoryCd || '').trim()) {
      errorMsg.value = MSG_DIRECT_SALES_CATEGORY_REQUIRED
      return
    }
  }
  busy.value = true
  errorMsg.value = ''
  try {
    const parcel = isOrderParcel.value
    const firstAlloc = lines.value[0]?.delivery_allocations?.[0]
    const payload = buildShipConfirmRequest({
      shipMode: shipMode.value,
      salesDt: todayBizIso(),
      orderNo: prefill.orderNo,
      custmId: custmId.value.trim() || prefill.custmId,
      lines: lines.value,
      dlvryTp: parcel ? prefill.dlvryTp : '',
      shipFee: parcel ? parcelShipFee.value : 0,
      rcvName: parcel ? firstAlloc?.rcv_name : '',
      rcvTel: parcel ? firstAlloc?.rcv_tel : '',
      rcvAddr: parcel ? firstAlloc?.rcv_addr : '',
      dlvryMsg: parcel ? firstAlloc?.dlvry_msg : '',
      sndName: parcel ? prefill.senderName : '',
      sndTel: parcel ? prefill.senderTel : '',
      sndAddr: parcel ? prefill.senderAddr : '',
      includeDeliveryAllocations: parcel,
      salesTypeCd: hasOrder.value ? null : prefill.salesTypeCd,
      salesCategoryCd: hasOrder.value ? null : prefill.salesCategoryCd,
    })
    const res = await confirmShipment(farmCd.value, payload)
    prefill.rememberResult(res)
    done.value = res
  } catch (err) {
    errorMsg.value = mapShipApiError(err)
  } finally {
    busy.value = false
  }
}

onMounted(() => {
  lines.value = prefill.shipLines.map((ln) => ({ ...ln }))
  shipMode.value = prefill.shipMode
  custmId.value = prefill.custmId || ''
  if (!hasOrder.value) {
    void fetchCustomers(farmCd.value)
      .then((rows) => {
        customers.value = rows
      })
      .catch(() => {
        customers.value = []
      })
    void Promise.all([
      fetchCommonCodes(farmCd.value, CODE_PARENT_SALES_TYPE),
      fetchCommonCodes(farmCd.value, CODE_PARENT_SALES_CATEGORY),
    ])
      .then(([salesTypeCodes, salesCategoryCodes]) => {
        salesTypes.value = salesTypeCodes
        salesCategories.value = salesCategoryCodes.filter(
          (c) => c.code_cd !== SALES_CATEGORY_AUCTION_CD,
        )
      })
      .catch(() => {
        salesTypes.value = []
        salesCategories.value = []
      })
  }
})
</script>

<template>
  <div class="page">
    <main class="content ods-page-content">
      <OdsAppBar :show-back="true" back-fallback="orders" />
      <OdsCard>
        <p class="ctx">{{ LABEL_SHIP_PAGE }}</p>
        <h2 class="title">{{ contextText }}</h2>
        <p v-if="contextHint" class="meta">{{ contextHint }}</p>
        <p v-if="prefill.orderNo" class="meta">
          {{ LABEL_ORDER }} {{ prefill.orderNo }}
          <template v-if="prefill.customerNm"> · {{ prefill.customerNm }}</template>
        </p>
      </OdsCard>

      <p v-if="!lines.length && !done" class="err" role="alert">{{ MSG_NO_PREFILL }}</p>

      <OdsCard v-if="isOrderParcel && !done" :title="LABEL_SENDER">
        <div
          class="sender-bar"
          :class="senderConfigured ? 'sender-bar--ok' : 'sender-bar--warn'"
          data-testid="ship-confirm-sender-bar"
        >
          <span class="sender-bar__txt" data-testid="ship-confirm-sender-summary">
            {{ senderSummary || LABEL_SENDER_UNSET }}
          </span>
          <button
            type="button"
            class="sender-bar__act"
            data-testid="ship-confirm-sender-setup"
            :aria-label="LABEL_SENDER"
            @click="openSenderSheet"
          >
            {{ senderConfigured ? LABEL_SENDER_EDIT : LABEL_SENDER_SETUP }}
          </button>
        </div>
        <p v-if="untrackedHint" class="hint" role="status" data-testid="ship-confirm-untracked-hint">
          {{ untrackedHint }}
        </p>
        <p class="meta">{{ LABEL_SHIP_FEE }} {{ formatOrderAmt(parcelShipFee) }}원</p>
      </OdsCard>

      <OdsCard
        v-if="!hasOrder && !done"
        :title="LABEL_SALES_CLASS"
        data-testid="ship-confirm-sales-class"
      >
        <OdsFormField :label="LABEL_SALES_TYPE" required>
          <OdsSelect
            v-model="salesTypeCd"
            variant="form"
            required
            data-testid="ship-confirm-sales-type"
          >
            <option value="">선택</option>
            <option v-for="c in salesTypes" :key="c.code_cd" :value="c.code_cd">
              {{ c.code_nm }}
            </option>
          </OdsSelect>
        </OdsFormField>
        <OdsFormField :label="LABEL_SALES_CATEGORY" required>
          <OdsSelect
            v-model="salesCategoryCd"
            variant="form"
            required
            data-testid="ship-confirm-sales-category"
          >
            <option value="">선택</option>
            <option v-for="c in salesCategories" :key="c.code_cd" :value="c.code_cd">
              {{ c.code_nm }}
            </option>
          </OdsSelect>
        </OdsFormField>
      </OdsCard>

      <OdsCard v-if="!hasOrder && !done" :title="LABEL_CUSTOMER">
        <OdsFormField :label="LABEL_CUSTOMER" optional>
          <OdsSelect v-model="custmId" variant="form">
            <option value="">선택 안 함</option>
            <option v-for="c in customers" :key="c.custm_id" :value="c.custm_id">
              {{ c.custm_nm }}
            </option>
          </OdsSelect>
        </OdsFormField>
      </OdsCard>

      <OdsCard
        v-for="(ln, idx) in lines"
        :key="ln.order_detail_id || `${ln.item_cd}-${idx}`"
        :title="`${LABEL_SHIP_LINE} ${idx + 1}`"
      >
        <p class="spec">{{ specText(ln) }}</p>
        <p v-if="ln.remaining_qty != null" class="meta">
          {{ LABEL_REMAINING }} {{ formatOrderAmt(ln.remaining_qty) }}
        </p>
        <OdsFormField :label="LABEL_QTY" required>
          <OdsInput
            :model-value="String(ln.qty)"
            type="number"
            variant="form"
            bare
            :disabled="busy || Boolean(done)"
            @update:model-value="ln.qty = Number($event)"
          />
        </OdsFormField>
        <OdsFormField :label="LABEL_UNIT_PRICE">
          <OdsInput
            :model-value="String(ln.unit_price)"
            type="number"
            variant="form"
            bare
            :disabled="busy || Boolean(done)"
            @update:model-value="ln.unit_price = Number($event)"
          />
        </OdsFormField>
        <div
          v-if="isOrderParcel && !done"
          class="line__dest"
          :class="`line__dest--${lineDestTone(ln)}`"
          data-testid="ship-confirm-delivery-status"
        >
          <span class="line__dest-status">{{ lineDestStatus(ln) }}</span>
          <button
            type="button"
            class="line__dest-btn"
            data-testid="ship-confirm-dest-open"
            @click="openDestSheet(idx)"
          >
            {{ LABEL_VIEW_DEST }}
          </button>
        </div>
      </OdsCard>

      <OdsCard v-if="showModeToggle && !done" :title="LABEL_MODE">
        <OdsFormField :label="LABEL_MODE">
          <OdsSelect v-model="shipMode" variant="form" :disabled="busy">
            <option :value="SHIP_MODE_DIRECT">{{ LABEL_MODE_DIRECT }}</option>
            <option :value="SHIP_MODE_STOCK" :disabled="!canPickStockMode">
              {{ LABEL_MODE_STOCK }}
            </option>
          </OdsSelect>
        </OdsFormField>
        <p v-if="stockModeHint" class="hint">{{ stockModeHint }}</p>
        <p v-if="stockModeBlocked" class="err" role="alert">{{ MSG_STOCK_MODE_PARTIAL_ALLOC }}</p>
      </OdsCard>
      <OdsCard v-else-if="!done && lines.length && source === 'STOCK'">
        <p class="meta">{{ LABEL_MODE }} · {{ LABEL_MODE_DIRECT }}</p>
      </OdsCard>
      <OdsCard v-else-if="!done && lines.length && source === 'PRODUCTION'">
        <p class="meta">{{ LABEL_MODE }} · {{ LABEL_MODE_DIRECT }}</p>
      </OdsCard>

      <p v-if="errorMsg" class="err" role="alert">{{ errorMsg }}</p>

      <OdsCard v-if="done">
        <p class="ok" role="status">{{ MSG_CONFIRM_OK }}</p>
        <p class="meta">판매번호 {{ done.sales_no }}</p>
        <p class="meta">
          수량
          {{ formatOrderAmt(done.details.reduce((s, d) => s + Number(d.qty), 0)) }}
        </p>
        <p v-if="done.order_status" class="meta">
          주문 {{ orderStatusLabel(done.order_status) }}
        </p>
        <ul v-if="done.remaining_order.length" class="remain">
          <li v-for="row in done.remaining_order" :key="row.order_detail_id">
            잔여 {{ formatOrderAmt(row.remaining_order_qty) }}
            / 주문 {{ formatOrderAmt(row.order_qty) }}
          </li>
        </ul>
        <OdsButton type="button" :disabled="busy" @click="goBackAfterSuccess">확인</OdsButton>
      </OdsCard>
    </main>
    <div v-if="!done" class="footer-actions">
      <OdsButton
        type="button"
        :disabled="busy || !lines.length"
        @click="onConfirm"
      >
        {{ LABEL_CONFIRM_SHIP }}
      </OdsButton>
    </div>
    <OdsBottomNav />

    <ParcelDestinationSheet
      :open="destEditIdx != null"
      :product-summary="destProductSummary"
      :order-qty="destOrderQty"
      :unit-label="destUnitLabel"
      :initial-dests="destInitialDests"
      :customer-defaults="destCustomerDefaults"
      :orderer-name="prefill.customerNm"
      :show-ship-fee="true"
      :test-id-prefix="TEST_PREFIX"
      @close="closeDestSheet"
      @complete="onDestComplete"
    />

    <ParcelSenderSheet
      :open="senderSheetOpen"
      :sender-name="prefill.senderName"
      :sender-tel="prefill.senderTel"
      :sender-addr="prefill.senderAddr"
      :farm-address="farmAddress"
      :test-id-prefix="TEST_PREFIX"
      @close="closeSenderSheet"
      @save="onSenderSave"
    />
  </div>
</template>

<style scoped>
.page {
  min-height: 100dvh;
  background: var(--ods-color-bg-muted);
  padding-bottom: calc(140px + env(safe-area-inset-bottom));
}
.ctx {
  margin: 0;
  font: var(--ods-font-form-help);
  color: var(--ods-color-text-secondary);
}
.title {
  margin: var(--ods-space-8) 0 0;
  font: var(--ods-font-title-3);
}
.spec {
  margin: 0 0 var(--ods-space-8);
  font: var(--ods-font-form-value);
  font-weight: 700;
}
.meta,
.hint {
  margin: var(--ods-space-8) 0 0;
  font: var(--ods-font-form-help);
  color: var(--ods-color-text-secondary);
}
.err {
  margin: 0;
  color: var(--ods-color-danger);
  font: var(--ods-font-form-help);
}
.ok {
  margin: 0;
  font: var(--ods-font-form-value);
  font-weight: 700;
}
.remain {
  margin: var(--ods-space-8) 0;
  padding-left: 1.2em;
  font: var(--ods-font-form-help);
}
.footer-actions {
  position: sticky;
  bottom: calc(56px + env(safe-area-inset-bottom));
  padding: var(--ods-space-12) var(--ods-space-16);
  background: var(--ods-color-bg-muted);
}
.sender-bar,
.line__dest {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ods-space-8);
  box-sizing: border-box;
  min-height: 28px;
  margin: var(--ods-space-8) 0 0;
  padding: 0 var(--ods-space-8);
  border-radius: var(--ods-radius-button);
  min-width: 0;
  font: var(--ods-font-caption);
  font-weight: 600;
}
.sender-bar {
  background: var(--ods-color-bg-muted);
  color: var(--ods-color-text-secondary);
}
.sender-bar--ok {
  background: var(--ods-color-primary-subtle, #f0f7f4);
  color: var(--ods-color-primary);
}
.sender-bar--warn {
  background: var(--ods-color-caution-soft);
  color: var(--ods-color-gray-900);
}
.sender-bar__txt,
.line__dest-status {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sender-bar__act,
.line__dest-btn {
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
.sender-bar__act:focus-visible,
.line__dest-btn:focus-visible {
  outline: 2px solid var(--ods-color-primary);
  outline-offset: 2px;
}
.line__dest--ok {
  background: var(--ods-color-primary-subtle, #f0f7f4);
}
.line__dest--ok .line__dest-status {
  color: var(--ods-color-primary);
}
.line__dest--warn {
  background: var(--ods-color-caution-soft);
}
.line__dest--warn .line__dest-status {
  color: var(--ods-color-caution);
}
.line__dest--danger {
  background: var(--ods-color-danger-soft);
}
.line__dest--danger .line__dest-status {
  color: var(--ods-color-danger);
}
</style>
