<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'

import { confirmShipment } from '@/api/shipments'
import { fetchCustomers } from '@/api/orders'
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
  formatOrderAmt,
  formatOrderLineSpec,
} from '@/views/orders/ordersConstants'
import {
  LABEL_CONFIRM_SHIP,
  LABEL_MODE,
  LABEL_MODE_DIRECT,
  LABEL_MODE_STOCK,
  LABEL_ORDER,
  LABEL_REMAINING,
  LABEL_SHIP_LINE,
  LABEL_SHIP_PAGE,
  HINT_SHIP_ORDER,
  HINT_SHIP_PRODUCTION,
  HINT_SHIP_STOCK,
  MSG_CONFIRM_OK,
  MSG_NO_PREFILL,
  MSG_STOCK_MODE_NEED_ALLOC,
  MSG_STOCK_MODE_PARTIAL_ALLOC,
  SHIP_MODE_DIRECT,
  SHIP_MODE_STOCK,
  buildShipConfirmRequest,
  canUseStockMode,
  findShipQtyIssue,
  findStockModeIssue,
  mapShipApiError,
  orderStatusLabel,
  type ShipDraftLine,
} from '@/views/sales/shipConfirmModel'
import { todayBizIso } from '@/shared/bizDate'
import { useAppStore } from '@/composables/stores/app'
import { useSalesPrefillStore } from '@/composables/stores/salesPrefill'
import type { CustomerListItem } from '@/types/order'
import type { ShipConfirmResponse, ShipMode } from '@/types/shipment'

const router = useRouter()
const { farmCd } = storeToRefs(useAppStore())
const prefill = useSalesPrefillStore()

const busy = ref(false)
const errorMsg = ref('')
const done = ref<ShipConfirmResponse | null>(null)
const customers = ref<CustomerListItem[]>([])
const lines = ref<ShipDraftLine[]>([])
const shipMode = ref<ShipMode>(SHIP_MODE_DIRECT)
const custmId = ref('')

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

function specText(ln: ShipDraftLine): string {
  return formatOrderLineSpec(ln)
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
  busy.value = true
  errorMsg.value = ''
  try {
    const payload = buildShipConfirmRequest({
      shipMode: shipMode.value,
      salesDt: todayBizIso(),
      orderNo: prefill.orderNo,
      custmId: custmId.value.trim() || prefill.custmId,
      lines: lines.value,
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
</style>
