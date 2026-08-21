<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'

import { fetchCommonCodes } from '@/api/commonCodes'
import { createCustomer, createOrder, fetchCustomers, fetchOrder, updateOrder } from '@/api/orders'
import { ApiClientError } from '@/api/client'
import iconChevronDown from '@/assets/ods/common/icon-chevron-down.svg'
import iconChevronRight from '@/assets/ods/scr004/icon-chevron-right.svg'
import OdsAppBar from '@/components/ods/OdsAppBar.vue'
import OdsBottomNav from '@/components/ods/OdsBottomNav.vue'
import OdsButton from '@/components/ods/OdsButton.vue'
import OdsCard from '@/components/ods/OdsCard.vue'
import OdsFormField from '@/components/ods/OdsFormField.vue'
import OdsInput from '@/components/ods/OdsInput.vue'
import OdsSelect from '@/components/ods/OdsSelect.vue'
import {
  CODE_PARENT_DELIVERY,
  CODE_PARENT_GRADE,
  CODE_PARENT_SIZE,
  CODE_PARENT_SPEC,
  DELIVERY_TP_VISIT,
  LABEL_ADD_DEST,
  LABEL_ADD_LINE,
  LABEL_ALLOC,
  LABEL_AMT,
  LABEL_BASIC_INFO,
  LABEL_CANCEL_EDIT,
  LABEL_COLLAPSE_DEST,
  LABEL_COLLAPSE_LINE,
  LABEL_COLLAPSE_SHIP,
  LABEL_CUSTOMER,
  LABEL_CUSTOMER_ADDR1,
  LABEL_CUSTOMER_ADDR2,
  LABEL_CUSTOMER_CANCEL,
  LABEL_CUSTOMER_MOBILE,
  LABEL_CUSTOMER_NAME,
  LABEL_CUSTOMER_SAVE,
  LABEL_DELIVERY_INFO,
  LABEL_DELIVERY_TP,
  LABEL_DEST,
  LABEL_DEST_COUNT_SUFFIX,
  LABEL_DEST_QTY,
  LABEL_DLVRY_MSG,
  LABEL_EDIT_ORDER,
  LABEL_EXPAND_DEST,
  LABEL_EXPAND_LINE,
  LABEL_EXPAND_SHIP,
  LABEL_GRADE,
  LABEL_LINE,
  LABEL_NEW_CUSTOMER,
  LABEL_NEW_CUSTOMER_A11Y,
  LABEL_NEW_CUSTOMER_PLUS,
  LABEL_NEW_ORDER,
  LABEL_ORDER_DT,
  LABEL_OVER,
  LABEL_PREPAY,
  LABEL_QTY,
  LABEL_REMOVE_LINE,
  LABEL_RCV_ADDR,
  LABEL_RCV_NAME,
  LABEL_RCV_TEL,
  LABEL_RMK,
  LABEL_SAVE_ORDER,
  LABEL_SIZE,
  LABEL_TOTAL_LINES,
  LABEL_TOTAL_QTY,
  LABEL_UNASSIGNED,
  LABEL_UNIT_PRICE,
  LABEL_VARIETY,
  LABEL_WEIGHT,
  MSG_CUSTOMER_REQUIRED,
  MSG_CUSTOMER_SAVE_FAIL,
  MSG_SAVE_FAIL,
  formatOrderAmt,
  isOrderEditLocked,
  isParcelDelivery,
  isPearVariety,
  isVarietyCode,
  PEAR_ITEM_CD,
  isWeightKgName,
  isWeightPackName,
  joinDot,
  orderEditLockMessage,
  ORDER_STATUS_CONFIRMED,
  ORDER_STATUS_PREP,
  parseWeightFromCodeNm,
  pickDefaultWeightCd,
} from '@/views/orders/ordersConstants'
import {
  buildOrderPayload,
  destQtySum,
  emptyDest,
  emptyLine,
  findSaveIssue as findFormSaveIssue,
  linesFromDetail,
  num,
  type EditDest,
  type EditLine,
} from '@/views/orders/orderFormModel'
import { todayBizIso } from '@/shared/bizDate'
import { useAppStore } from '@/composables/stores/app'
import type { CommonCodeItem } from '@/types/commonCode'
import type { CustomerListItem, OrderCreatePayload } from '@/types/order'

const router = useRouter()
const route = useRoute()
const { farmCd } = storeToRefs(useAppStore())

const isEdit = computed(() => route.name === 'order-edit')
const orderNo = computed(() => String(route.params.orderNo || ''))
const pageTitle = computed(() => (isEdit.value ? LABEL_EDIT_ORDER : LABEL_NEW_ORDER))
const statusCd = ref('')
const lockProducts = computed(
  () =>
    isEdit.value &&
    (statusCd.value === ORDER_STATUS_CONFIRMED || statusCd.value === ORDER_STATUS_PREP),
)
const lockHeaderCore = computed(
  () =>
    isEdit.value &&
    (statusCd.value === ORDER_STATUS_CONFIRMED || statusCd.value === ORDER_STATUS_PREP),
)
const lockCustomer = computed(() => isEdit.value && statusCd.value === ORDER_STATUS_PREP)
const lockRmk = computed(() => isEdit.value && statusCd.value === ORDER_STATUS_PREP)
const lockDeliveryTp = computed(() => isEdit.value && statusCd.value === ORDER_STATUS_PREP)
const lockDestStructure = computed(() => isEdit.value && statusCd.value === ORDER_STATUS_PREP)
const editLocked = computed(() => isEdit.value && isOrderEditLocked(statusCd.value))

const saving = ref(false)
const errorMsg = ref('')
const orderDt = ref(todayBizIso())
const custmId = ref('')
const prePay = ref('0')
const rmk = ref('')
const lines = ref<EditLine[]>([emptyLine()])
const expandedProductIndex = ref<number | null>(0)
const expandedShipIndex = ref<number | null>(null)
const expandedDest = ref<{ line: number; dest: number } | null>(null)
const customers = ref<CustomerListItem[]>([])
const varieties = ref<CommonCodeItem[]>([])
const grades = ref<CommonCodeItem[]>([])
const specs = ref<CommonCodeItem[]>([])
const pearSizes = ref<CommonCodeItem[]>([])
const deliveries = ref<CommonCodeItem[]>([])

const weightKgCodes = computed(() => specs.value.filter((c) => isWeightKgName(c.code_nm)))
const weightPackCodes = computed(() => specs.value.filter((c) => isWeightPackName(c.code_nm)))

const harvestYear = computed(() => Number(todayBizIso().slice(0, 4)))
const totalQty = computed(() => lines.value.reduce((sum, line) => sum + num(line.qty), 0))
const totalAmt = computed(() => lines.value.reduce((sum, line) => sum + lineAmt(line), 0))

const customerModalOpen = ref(false)
const customerSaving = ref(false)
const customerError = ref('')
const newCustNm = ref('')
const newCustMobile = ref('')
const newCustAddr1 = ref('')
const newCustAddr2 = ref('')
const newCustRmk = ref('')

function lineAmt(line: EditLine): number {
  return num(line.qty) * num(line.unit_price)
}

function codeNmOf(codes: CommonCodeItem[], cd: string): string {
  return codes.find((c) => c.code_cd === cd)?.code_nm || ''
}

function lineSpecText(line: EditLine): string {
  return joinDot([
    codeNmOf(varieties.value, line.variety_cd),
    codeNmOf(weightCodesFor(line), line.weight_cd),
    codeNmOf(grades.value, line.grade_cd),
    codeNmOf(sizeCodesFor(line), line.size_cd),
  ])
}

function lineQtyAmtText(line: EditLine): string {
  return joinDot([
    `${LABEL_QTY} ${formatOrderAmt(num(line.qty))}`,
    `${formatOrderAmt(lineAmt(line))}원`,
  ])
}

function shipSummaryText(line: EditLine): string {
  const tpNm = codeNmOf(deliveries.value, line.delivery_tp_cd)
  if (!isParcelDelivery(line.delivery_tp_cd)) {
    const d = line.dests[0]
    return joinDot([tpNm, d?.rcv_name || '', d?.rcv_addr || ''])
  }
  return joinDot([
    tpNm,
    `${LABEL_DEST} ${line.dests.length}${LABEL_DEST_COUNT_SUFFIX}`,
    `${formatOrderAmt(destQtySum(line))}/${formatOrderAmt(num(line.qty))}`,
  ])
}

function destSummarySub(dest: EditDest): string {
  return joinDot([dest.rcv_tel, dest.rcv_addr])
}

function destSummaryMain(dest: EditDest): string {
  return joinDot([dest.rcv_name || LABEL_DEST, formatOrderAmt(num(dest.qty))])
}

function allocStatusText(line: EditLine): string {
  const sum = destQtySum(line)
  const qty = num(line.qty)
  const remain = qty - sum
  const head = `${LABEL_ALLOC} ${formatOrderAmt(sum)} / ${formatOrderAmt(qty)}`
  if (remain > 0) return `${head} · ${LABEL_UNASSIGNED} ${formatOrderAmt(remain)}`
  if (remain < 0) return `${head} · ${formatOrderAmt(-remain)} ${LABEL_OVER}`
  return head
}

function canAddDest(line: EditLine): boolean {
  return (
    !lockDestStructure.value &&
    isParcelDelivery(line.delivery_tp_cd) &&
    destQtySum(line) < num(line.qty)
  )
}

function isDestOpen(lineIdx: number, destIdx: number): boolean {
  return expandedDest.value?.line === lineIdx && expandedDest.value.dest === destIdx
}

function toggleDest(lineIdx: number, destIdx: number) {
  if (isDestOpen(lineIdx, destIdx)) {
    expandedDest.value = null
    return
  }
  expandedDest.value = { line: lineIdx, dest: destIdx }
}

function setLineQty(line: EditLine, raw: string) {
  line.qty = raw
  if (!isParcelDelivery(line.delivery_tp_cd) && line.dests[0]) {
    line.dests[0].qty = raw
  }
}

function setDeliveryTp(line: EditLine, tp: string) {
  if (lockDeliveryTp.value) return
  const wasParcel = isParcelDelivery(line.delivery_tp_cd)
  const nowParcel = isParcelDelivery(tp)
  line.delivery_tp_cd = tp
  if (nowParcel && !wasParcel) {
    const first = line.dests[0] || emptyDest()
    first.qty = '1'
    line.dests = [first]
    return
  }
  if (!nowParcel) {
    const first = line.dests[0] || emptyDest()
    first.qty = line.qty
    line.dests = [first]
    expandedDest.value = null
  }
}

function addDest(lineIdx: number) {
  if (lockDestStructure.value) return
  const line = lines.value[lineIdx]
  if (!canAddDest(line)) return
  line.dests.push(emptyDest())
  expandedProductIndex.value = lineIdx
  expandedShipIndex.value = lineIdx
  expandedDest.value = { line: lineIdx, dest: line.dests.length - 1 }
}

function removeDest(lineIdx: number, destIdx: number) {
  if (lockDestStructure.value) return
  const line = lines.value[lineIdx]
  line.dests.splice(destIdx, 1)
  const cur = expandedDest.value
  if (!cur || cur.line !== lineIdx) return
  if (cur.dest === destIdx) expandedDest.value = null
  else if (cur.dest > destIdx) expandedDest.value = { line: lineIdx, dest: cur.dest - 1 }
}

function visitDest(line: EditLine): EditDest {
  if (!line.dests.length) line.dests.push(emptyDest())
  return line.dests[0]
}

function lineDeliveries(line: EditLine): OrderCreatePayload['lines'][number]['deliveries'] {
  const tp = line.delivery_tp_cd || DELIVERY_TP_VISIT
  if (isParcelDelivery(tp)) {
    return line.dests.map((d) => ({
      delivery_tp_cd: tp,
      qty: num(d.qty),
      planned_dt: orderDt.value,
      rcv_name: d.rcv_name,
      rcv_tel: d.rcv_tel,
      rcv_addr: d.rcv_addr,
      dlvry_msg: d.dlvry_msg,
    }))
  }
  const d = visitDest(line)
  return [
    {
      delivery_tp_cd: tp,
      qty: num(line.qty),
      planned_dt: orderDt.value,
      rcv_name: d.rcv_name,
      rcv_tel: d.rcv_tel,
      rcv_addr: d.rcv_addr,
      dlvry_msg: d.dlvry_msg,
    },
  ]
}

function isLineOpen(idx: number): boolean {
  return expandedProductIndex.value === idx
}

function isShipOpen(idx: number): boolean {
  return expandedShipIndex.value === idx
}

function toggleProduct(idx: number) {
  if (expandedProductIndex.value === idx) {
    expandedProductIndex.value = null
    if (expandedShipIndex.value === idx) expandedShipIndex.value = null
    if (expandedDest.value?.line === idx) expandedDest.value = null
    return
  }
  expandedProductIndex.value = idx
  expandedShipIndex.value = null
  expandedDest.value = null
}

function toggleShip(idx: number) {
  expandedShipIndex.value = expandedShipIndex.value === idx ? null : idx
}

function findSaveIssue() {
  return findFormSaveIssue(lines.value, lineWeightValue)
}

function weightCodesFor(line: EditLine): CommonCodeItem[] {
  return isPearVariety(line.variety_cd) ? weightKgCodes.value : weightPackCodes.value
}

function sizeCodesFor(line: EditLine): CommonCodeItem[] {
  return isPearVariety(line.variety_cd) ? pearSizes.value : weightPackCodes.value
}

function lineWeightValue(line: EditLine): number {
  const row = weightCodesFor(line).find((c) => c.code_cd === line.weight_cd)
  return parseWeightFromCodeNm(row?.code_nm || '')
}

function applyLineDefaults(line: EditLine) {
  if (!line.variety_cd || !isVarietyCode(line.variety_cd)) {
    line.variety_cd = varieties.value[0]?.code_cd || ''
  }
  if (!line.grade_cd && grades.value[0]) {
    line.grade_cd = grades.value[0].code_cd
  }
  const weights = weightCodesFor(line)
  if (!line.weight_cd || !weights.some((c) => c.code_cd === line.weight_cd)) {
    line.weight_cd = pickDefaultWeightCd(weights)
  }
  const sizes = sizeCodesFor(line)
  if (!line.size_cd || !sizes.some((c) => c.code_cd === line.size_cd)) {
    line.size_cd = sizes[0]?.code_cd || ''
  }
  if (!line.delivery_tp_cd && deliveries.value[0]) {
    line.delivery_tp_cd = deliveries.value[0].code_cd
  }
  if (!line.dests.length) {
    line.dests.push(emptyDest())
  }
  if (!isParcelDelivery(line.delivery_tp_cd) && line.dests[0]) {
    line.dests[0].qty = line.qty
  }
}

function setVariety(line: EditLine, varietyCd: string) {
  line.variety_cd = varietyCd
  applyLineDefaults(line)
}

async function loadMasters() {
  errorMsg.value = ''
  try {
    const [cust, pearKids, grade, spec, size, dlv] = await Promise.all([
      fetchCustomers(farmCd.value),
      fetchCommonCodes(farmCd.value, PEAR_ITEM_CD),
      fetchCommonCodes(farmCd.value, CODE_PARENT_GRADE),
      fetchCommonCodes(farmCd.value, CODE_PARENT_SPEC),
      fetchCommonCodes(farmCd.value, CODE_PARENT_SIZE),
      fetchCommonCodes(farmCd.value, CODE_PARENT_DELIVERY),
    ])
    customers.value = cust
    // FR01 직계는 중분류(배/배즙/원물). 품종은 FR010100 하위 소분류만.
    varieties.value = pearKids.filter((c) => isVarietyCode(c.code_cd))
    grades.value = grade
    specs.value = spec
    pearSizes.value = size
    deliveries.value = dlv
    if (!isEdit.value) {
      lines.value.forEach(applyLineDefaults)
    }
  } catch (err) {
    errorMsg.value = err instanceof ApiClientError ? err.message : MSG_SAVE_FAIL
  }
}

async function hydrateOrder() {
  if (!isEdit.value || !orderNo.value) return
  const detail = await fetchOrder(farmCd.value, orderNo.value)
  statusCd.value = detail.status_cd
  if (isOrderEditLocked(detail.status_cd)) {
    errorMsg.value = orderEditLockMessage(detail.status_cd)
    return
  }
  orderDt.value = detail.order_dt
  custmId.value = detail.custm_id
  prePay.value = String(detail.pre_pay_amt ?? 0)
  rmk.value = detail.rmk || ''
  lines.value = linesFromDetail(detail, (line) =>
    isPearVariety(line.variety_cd) ? weightKgCodes.value : weightPackCodes.value,
  )
  lines.value.forEach(applyLineDefaults)
  expandedProductIndex.value = 0
  expandedShipIndex.value = null
  expandedDest.value = null
}

function addLine() {
  if (lockProducts.value) return
  const next = emptyLine()
  applyLineDefaults(next)
  lines.value.push(next)
  expandedProductIndex.value = lines.value.length - 1
  expandedShipIndex.value = null
  expandedDest.value = null
}

function removeLine(idx: number) {
  if (lockProducts.value) return
  if (lines.value.length <= 1) return
  lines.value.splice(idx, 1)
  expandedProductIndex.value = Math.min(idx, lines.value.length - 1)
  expandedShipIndex.value = null
  expandedDest.value = null
}

function openCustomerModal() {
  customerError.value = ''
  newCustNm.value = ''
  newCustMobile.value = ''
  newCustAddr1.value = ''
  newCustAddr2.value = ''
  newCustRmk.value = ''
  customerModalOpen.value = true
}

function closeCustomerModal() {
  customerModalOpen.value = false
  customerError.value = ''
}

async function saveNewCustomer() {
  customerError.value = ''
  customerSaving.value = true
  try {
    const created = await createCustomer(farmCd.value, {
      custm_nm: newCustNm.value,
      mobile: newCustMobile.value,
      addr1: newCustAddr1.value,
      addr2: newCustAddr2.value,
      rmk: newCustRmk.value,
    })
    try {
      customers.value = await fetchCustomers(farmCd.value)
    } catch {
      customers.value = [...customers.value, created]
    }
    custmId.value = created.custm_id
    closeCustomerModal()
  } catch (err) {
    customerError.value =
      err instanceof ApiClientError ? err.message : MSG_CUSTOMER_SAVE_FAIL
  } finally {
    customerSaving.value = false
  }
}

async function onSave() {
  errorMsg.value = ''
  if (editLocked.value) {
    errorMsg.value = orderEditLockMessage(statusCd.value)
    return
  }
  if (!custmId.value) {
    errorMsg.value = MSG_CUSTOMER_REQUIRED
    return
  }
  const issue = findSaveIssue()
  if (issue) {
    errorMsg.value = issue.message
    expandedProductIndex.value = issue.lineIdx
    expandedShipIndex.value = issue.ship ? issue.lineIdx : expandedShipIndex.value
    expandedDest.value =
      issue.destIdx === null ? null : { line: issue.lineIdx, dest: issue.destIdx }
    return
  }
  const payload = buildOrderPayload({
    custmId: custmId.value,
    orderDt: orderDt.value,
    prePay: num(prePay.value),
    rmk: rmk.value,
    harvestYear: harvestYear.value,
    lines: lines.value,
    lineWeightValue,
    lineDeliveries,
  })
  saving.value = true
  try {
    const saved = isEdit.value
      ? await updateOrder(farmCd.value, orderNo.value, payload)
      : await createOrder(farmCd.value, payload)
    await router.replace({ name: 'order-detail', params: { orderNo: saved.order_no } })
  } catch (err) {
    errorMsg.value = err instanceof ApiClientError ? err.message : MSG_SAVE_FAIL
  } finally {
    saving.value = false
  }
}

function goBack() {
  if (isEdit.value && orderNo.value) {
    void router.replace({ name: 'order-detail', params: { orderNo: orderNo.value } })
    return
  }
  void router.replace({ name: 'orders' })
}

async function bootForm() {
  await loadMasters()
  if (isEdit.value) {
    try {
      await hydrateOrder()
    } catch (err) {
      errorMsg.value = err instanceof ApiClientError ? err.message : MSG_SAVE_FAIL
    }
  }
}

onMounted(() => {
  void bootForm()
})

watch(
  () => [route.name, route.params.orderNo],
  () => {
    void bootForm()
  },
)
</script>

<template>
  <div class="page">
    <main class="content ods-page-content">
      <OdsAppBar
        :show-back="true"
        :back-mode="isEdit ? 'emit' : 'history'"
        back-fallback="orders"
        @back="goBack"
      />
      <h1 class="title">{{ pageTitle }}</h1>
      <p v-if="errorMsg" class="err" role="alert">{{ errorMsg }}</p>
      <OdsCard :title="LABEL_BASIC_INFO">
        <div class="form-grid">
          <OdsFormField :label="LABEL_ORDER_DT" required>
            <div class="date-iso">
              <span class="date-iso__value">{{ orderDt }}</span>
              <input
                v-model="orderDt"
                class="date-iso__native"
                type="date"
                :aria-label="LABEL_ORDER_DT"
                :disabled="lockHeaderCore"
              />
            </div>
          </OdsFormField>
          <OdsFormField :label="LABEL_CUSTOMER" required as="fieldset">
            <div class="customer-row">
              <OdsSelect v-model="custmId" variant="form" required :disabled="lockCustomer">
                <option value="">고객 선택</option>
                <option v-for="c in customers" :key="c.custm_id" :value="c.custm_id">
                  {{ c.custm_nm }}{{ c.mobile ? ` (${c.mobile})` : '' }}
                </option>
              </OdsSelect>
              <button
                type="button"
                class="link-btn"
                :disabled="lockCustomer"
                :aria-label="LABEL_NEW_CUSTOMER_A11Y"
                :title="LABEL_NEW_CUSTOMER_A11Y"
                @click="openCustomerModal"
              >
                {{ LABEL_NEW_CUSTOMER_PLUS }}
              </button>
            </div>
          </OdsFormField>
          <OdsFormField :label="LABEL_PREPAY" optional>
            <OdsInput v-model="prePay" type="number" variant="form" bare :disabled="lockHeaderCore" />
          </OdsFormField>
          <OdsFormField :label="LABEL_RMK" optional>
            <OdsInput v-model="rmk" variant="form" bare :disabled="lockRmk" />
          </OdsFormField>
        </div>
      </OdsCard>
      <div
        v-for="(line, idx) in lines"
        :key="idx"
        class="line-card"
        :class="{ 'line-card--open': isLineOpen(idx) }"
      >
        <OdsCard>
          <button
            v-if="!isLineOpen(idx)"
            type="button"
            class="line-summary"
            :aria-expanded="false"
            :aria-label="LABEL_EXPAND_LINE"
            @click="toggleProduct(idx)"
          >
            <span class="line-summary__top">
              <span class="line-summary__title">{{ LABEL_LINE }} {{ idx + 1 }}</span>
              <img :src="iconChevronRight" alt="" class="chev" />
            </span>
            <span class="line-summary__spec">{{ lineSpecText(line) }}</span>
            <span class="line-summary__meta">{{ lineQtyAmtText(line) }}</span>
            <span class="line-summary__meta">{{ shipSummaryText(line) }}</span>
          </button>
          <template v-else>
            <div class="line-head">
              <h2 class="line-head__title">{{ LABEL_LINE }} {{ idx + 1 }}</h2>
              <div class="line-head__actions">
                <button
                  v-if="lines.length > 1 && !lockProducts"
                  type="button"
                  class="line-head__del"
                  @click="removeLine(idx)"
                >
                  {{ LABEL_REMOVE_LINE }}
                </button>
                <button
                  type="button"
                  class="line-head__chev"
                  :aria-expanded="true"
                  :aria-label="LABEL_COLLAPSE_LINE"
                  @click="toggleProduct(idx)"
                >
                  <img :src="iconChevronDown" alt="" class="chev" />
                </button>
              </div>
            </div>
            <div class="spec-grid">
              <OdsFormField :label="LABEL_VARIETY" required>
                <OdsSelect
                  :model-value="line.variety_cd"
                  variant="form"
                  :disabled="lockProducts"
                  @update:model-value="(v) => setVariety(line, v)"
                >
                  <option value="">품종 선택</option>
                  <option v-for="v in varieties" :key="v.code_cd" :value="v.code_cd">
                    {{ v.code_nm }}
                  </option>
                </OdsSelect>
              </OdsFormField>
              <OdsFormField :label="LABEL_WEIGHT" required>
                <OdsSelect v-model="line.weight_cd" variant="form" :disabled="lockProducts">
                  <option value="">중량 선택</option>
                  <option v-for="w in weightCodesFor(line)" :key="w.code_cd" :value="w.code_cd">
                    {{ w.code_nm }}
                  </option>
                </OdsSelect>
              </OdsFormField>
              <OdsFormField :label="LABEL_GRADE" required>
                <OdsSelect v-model="line.grade_cd" variant="form" :disabled="lockProducts">
                  <option value="">등급 선택</option>
                  <option v-for="g in grades" :key="g.code_cd" :value="g.code_cd">
                    {{ g.code_nm }}
                  </option>
                </OdsSelect>
              </OdsFormField>
              <OdsFormField :label="LABEL_SIZE" required>
                <OdsSelect v-model="line.size_cd" variant="form" :disabled="lockProducts">
                  <option value="">크기 선택</option>
                  <option v-for="s in sizeCodesFor(line)" :key="s.code_cd" :value="s.code_cd">
                    {{ s.code_nm }}
                  </option>
                </OdsSelect>
              </OdsFormField>
            </div>
            <div class="price-grid">
              <OdsFormField :label="LABEL_QTY" required>
                <OdsInput
                  :model-value="line.qty"
                  type="number"
                  variant="form"
                  bare
                  :disabled="lockProducts"
                  @update:model-value="(v) => setLineQty(line, v)"
                />
              </OdsFormField>
              <OdsFormField :label="LABEL_UNIT_PRICE" required>
                <OdsInput
                  v-model="line.unit_price"
                  type="number"
                  variant="form"
                  bare
                  :disabled="lockProducts"
                />
              </OdsFormField>
            </div>
            <div class="amt-row">
              <span class="amt-row__label">{{ LABEL_AMT }}</span>
              <strong class="amt-row__value">{{ formatOrderAmt(lineAmt(line)) }}원</strong>
            </div>
            <section class="ship-section">
              <button
                type="button"
                class="ship-head"
                :aria-expanded="isShipOpen(idx)"
                :aria-label="isShipOpen(idx) ? LABEL_COLLAPSE_SHIP : LABEL_EXPAND_SHIP"
                @click="toggleShip(idx)"
              >
                <span class="ship-head__title">{{ LABEL_DELIVERY_INFO }}</span>
                <span class="ship-head__right">
                  <span v-if="!isShipOpen(idx)" class="ship-head__sum">{{ shipSummaryText(line) }}</span>
                  <img
                    :src="isShipOpen(idx) ? iconChevronDown : iconChevronRight"
                    alt=""
                    class="chev"
                  />
                </span>
              </button>
              <div v-if="isShipOpen(idx)" class="ship-body">
                <div class="form-grid">
                  <OdsFormField class="form-span-2" :label="LABEL_DELIVERY_TP" required>
                    <OdsSelect
                      :model-value="line.delivery_tp_cd"
                      variant="form"
                      :disabled="lockDeliveryTp"
                      @update:model-value="(v) => setDeliveryTp(line, v)"
                    >
                      <option v-for="d in deliveries" :key="d.code_cd" :value="d.code_cd">
                        {{ d.code_nm }}
                      </option>
                    </OdsSelect>
                  </OdsFormField>
                </div>
                <template v-if="isParcelDelivery(line.delivery_tp_cd)">
                  <p class="alloc">{{ allocStatusText(line) }}</p>
                  <div
                    v-for="(dest, dIdx) in line.dests"
                    :key="dIdx"
                    class="dest-card"
                    :class="{ 'dest-card--open': isDestOpen(idx, dIdx) }"
                  >
                    <button
                      v-if="!isDestOpen(idx, dIdx)"
                      type="button"
                      class="dest-summary"
                      :aria-expanded="false"
                      :aria-label="LABEL_EXPAND_DEST"
                      @click="toggleDest(idx, dIdx)"
                    >
                      <span class="dest-summary__top">
                        <span class="dest-summary__title">
                          {{ LABEL_DEST }} {{ dIdx + 1 }}
                        </span>
                        <img :src="iconChevronRight" alt="" class="chev" />
                      </span>
                      <span class="dest-summary__main">{{ destSummaryMain(dest) }}</span>
                      <span class="dest-summary__sub">{{ destSummarySub(dest) }}</span>
                    </button>
                    <template v-else>
                      <div class="dest-head">
                        <h4 class="dest-head__title">{{ LABEL_DEST }} {{ dIdx + 1 }}</h4>
                        <div class="dest-head__actions">
                          <button
                            v-if="!lockDestStructure"
                            type="button"
                            class="line-head__del"
                            @click="removeDest(idx, dIdx)"
                          >
                            {{ LABEL_REMOVE_LINE }}
                          </button>
                          <button
                            type="button"
                            class="line-head__chev"
                            :aria-expanded="true"
                            :aria-label="LABEL_COLLAPSE_DEST"
                            @click="toggleDest(idx, dIdx)"
                          >
                            <img :src="iconChevronDown" alt="" class="chev" />
                          </button>
                        </div>
                      </div>
                      <div class="form-grid">
                        <OdsFormField :label="LABEL_DEST_QTY" required>
                          <OdsInput
                            v-model="dest.qty"
                            type="number"
                            variant="form"
                            bare
                            :disabled="lockDestStructure"
                          />
                        </OdsFormField>
                        <OdsFormField :label="LABEL_RCV_NAME" required>
                          <OdsInput v-model="dest.rcv_name" variant="form" bare />
                        </OdsFormField>
                        <OdsFormField class="form-span-2" :label="LABEL_RCV_TEL" required>
                          <OdsInput v-model="dest.rcv_tel" variant="form" bare />
                        </OdsFormField>
                        <OdsFormField class="form-span-2" :label="LABEL_RCV_ADDR" required>
                          <OdsInput v-model="dest.rcv_addr" variant="form" bare />
                        </OdsFormField>
                        <OdsFormField class="form-span-2" :label="LABEL_DLVRY_MSG" optional>
                          <OdsInput v-model="dest.dlvry_msg" variant="form" bare />
                        </OdsFormField>
                      </div>
                    </template>
                  </div>
                  <OdsButton
                    v-if="!lockDestStructure"
                    class="add-dest-btn"
                    variant="secondary"
                    type="button"
                    :disabled="!canAddDest(line)"
                    @click="addDest(idx)"
                  >
                    {{ LABEL_ADD_DEST }}
                  </OdsButton>
                </template>
                <div v-else class="form-grid">
                  <OdsFormField :label="LABEL_RCV_NAME" optional>
                    <OdsInput v-model="visitDest(line).rcv_name" variant="form" bare />
                  </OdsFormField>
                  <OdsFormField :label="LABEL_RCV_TEL" optional>
                    <OdsInput v-model="visitDest(line).rcv_tel" variant="form" bare />
                  </OdsFormField>
                  <OdsFormField class="form-span-2" :label="LABEL_RCV_ADDR" optional>
                    <OdsInput v-model="visitDest(line).rcv_addr" variant="form" bare />
                  </OdsFormField>
                </div>
              </div>
            </section>
          </template>
        </OdsCard>
      </div>
      <OdsButton
        v-if="!lockProducts"
        class="add-line-btn"
        variant="secondary"
        type="button"
        @click="addLine"
      >
        {{ LABEL_ADD_LINE }}
      </OdsButton>
      <div class="save-block">
        <p class="order-sum">
          {{ LABEL_TOTAL_LINES }} {{ lines.length }}{{ LABEL_LINE }}
          · {{ LABEL_TOTAL_QTY }} {{ formatOrderAmt(totalQty) }}
          · {{ formatOrderAmt(totalAmt) }}원
        </p>
        <OdsButton
          variant="primary"
          type="button"
          :busy="saving"
          :disabled="editLocked"
          @click="onSave"
        >
          {{ LABEL_SAVE_ORDER }}
        </OdsButton>
        <OdsButton
          v-if="isEdit"
          class="cancel-btn"
          variant="secondary"
          type="button"
          :disabled="saving"
          @click="goBack"
        >
          {{ LABEL_CANCEL_EDIT }}
        </OdsButton>
      </div>
    </main>
    <OdsBottomNav />
    <div
      v-if="customerModalOpen"
      class="modal"
      role="dialog"
      aria-modal="true"
      :aria-label="LABEL_NEW_CUSTOMER"
    >
      <div class="modal__card">
        <div class="modal__head">
          <h2>{{ LABEL_NEW_CUSTOMER }}</h2>
          <button type="button" class="modal__close" @click="closeCustomerModal">
            {{ LABEL_CUSTOMER_CANCEL }}
          </button>
        </div>
        <p v-if="customerError" class="modal__error" role="alert">{{ customerError }}</p>
        <div class="form-grid">
          <OdsFormField :label="LABEL_CUSTOMER_NAME" required>
            <OdsInput v-model="newCustNm" variant="form" bare />
          </OdsFormField>
          <OdsFormField :label="LABEL_CUSTOMER_MOBILE" required>
            <OdsInput v-model="newCustMobile" variant="form" bare />
          </OdsFormField>
          <OdsFormField class="form-span-2" :label="LABEL_CUSTOMER_ADDR1" optional>
            <OdsInput v-model="newCustAddr1" variant="form" bare />
          </OdsFormField>
          <OdsFormField class="form-span-2" :label="LABEL_CUSTOMER_ADDR2" optional>
            <OdsInput v-model="newCustAddr2" variant="form" bare />
          </OdsFormField>
          <OdsFormField class="form-span-2" :label="LABEL_RMK" optional>
            <OdsInput v-model="newCustRmk" variant="form" bare />
          </OdsFormField>
        </div>
        <OdsButton
          variant="primary"
          type="button"
          :busy="customerSaving"
          @click="saveNewCustomer"
        >
          {{ LABEL_CUSTOMER_SAVE }}
        </OdsButton>
      </div>
    </div>
  </div>
</template>

<style scoped>
.page {
  min-height: 100dvh;
  background: var(--ods-color-bg-muted);
  padding-bottom: calc(140px + env(safe-area-inset-bottom));
}
.content {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-12);
}
.content :deep(.ods-card__title) {
  margin-bottom: var(--ods-space-8);
}
.content :deep(.ods-form-field) {
  gap: var(--ods-space-4);
}
.title {
  margin: 0;
  font: var(--ods-font-title-2);
  font-weight: 800;
  color: var(--ods-color-text);
}
.err {
  margin: 0;
  color: var(--ods-color-danger);
  font: var(--ods-font-form-help);
}
.form-grid,
.spec-grid,
.price-grid {
  display: grid;
  gap: var(--ods-space-8);
  min-width: 0;
}
.form-grid,
.price-grid {
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
}
.price-grid {
  margin-top: var(--ods-space-8);
}
.spec-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}
@media (max-width: 339px) {
  .spec-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
.form-grid :deep(.ods-form-field),
.spec-grid :deep(.ods-form-field),
.price-grid :deep(.ods-form-field) {
  min-width: 0;
}
.spec-grid :deep(.ods-form-field__label) {
  font: var(--ods-font-card-section);
}
.spec-grid :deep(.ods-select) {
  padding-left: var(--ods-space-8);
  padding-right: var(--ods-space-8);
}
.form-span-2 {
  grid-column: 1 / -1;
}
.line-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ods-space-8);
  margin: 0 0 var(--ods-space-8);
}
.line-head__title {
  margin: 0;
  font: var(--ods-font-form-label);
  color: var(--ods-color-text);
}
.line-head__actions {
  display: flex;
  align-items: center;
  gap: var(--ods-space-4);
  flex: 0 0 auto;
}
.line-head__del {
  border: none;
  background: transparent;
  color: var(--ods-color-danger);
  font: var(--ods-font-form-help);
  font-weight: 700;
  cursor: pointer;
  min-height: var(--ods-control-height);
  padding: 0 var(--ods-space-8);
}
.line-head__chev {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  margin: 0;
  padding: 0;
  border: 0;
  background: transparent;
  cursor: pointer;
  width: var(--ods-control-height);
  height: var(--ods-control-height);
}
.line-card:not(.line-card--open) :deep(.ods-card) {
  padding: var(--ods-space-12);
}
.line-summary {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-4);
  width: 100%;
  margin: 0;
  padding: 0;
  border: 0;
  background: transparent;
  text-align: left;
  cursor: pointer;
  color: inherit;
}
.line-summary__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ods-space-8);
}
.line-summary__title {
  font: var(--ods-font-form-label);
  color: var(--ods-color-text);
}
.line-summary__spec,
.line-summary__meta {
  display: block;
  font: var(--ods-font-card-meta);
  color: var(--ods-color-text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.line-summary__spec {
  font: var(--ods-font-card-body);
  color: var(--ods-color-text);
}
.chev {
  width: var(--ods-icon-md);
  height: var(--ods-icon-md);
  flex: 0 0 auto;
}
.amt-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--ods-space-8);
  margin: 0;
  padding: var(--ods-space-8) 0 0;
}
.amt-row__label {
  font: var(--ods-font-form-label);
  color: var(--ods-color-text-label);
}
.amt-row__value {
  font: var(--ods-font-headline);
  color: var(--ods-color-text);
}
.ship-section {
  margin-top: var(--ods-space-12);
  padding-top: var(--ods-space-12);
  border-top: 1px solid var(--ods-color-border);
}
.ship-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ods-space-8);
  width: 100%;
  margin: 0;
  padding: 0;
  border: 0;
  background: transparent;
  cursor: pointer;
  min-height: var(--ods-control-height);
  color: inherit;
  text-align: left;
}
.ship-head__title {
  font: var(--ods-font-card-section);
  color: var(--ods-color-text);
  flex: 0 0 auto;
}
.ship-head__right {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: var(--ods-space-8);
  min-width: 0;
  flex: 1 1 auto;
}
.ship-head__sum {
  font: var(--ods-font-card-meta);
  color: var(--ods-color-text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ship-section .form-grid {
  margin-top: var(--ods-space-8);
}
.ship-body {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-8);
  margin-top: var(--ods-space-8);
}
.ship-body > .form-grid {
  margin-top: 0;
}
.alloc {
  margin: 0;
  font: var(--ods-font-card-section);
  color: var(--ods-color-text);
}
.dest-card {
  border: 1px solid var(--ods-color-border);
  border-radius: var(--ods-radius-button);
  padding: var(--ods-space-8);
  background: var(--ods-color-white);
}
.dest-card--open {
  background: var(--ods-color-gray-100);
}
.dest-summary {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-4);
  width: 100%;
  margin: 0;
  padding: 0;
  border: 0;
  background: transparent;
  text-align: left;
  cursor: pointer;
  color: inherit;
}
.dest-summary__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ods-space-8);
}
.dest-summary__title,
.dest-head__title {
  margin: 0;
  font: var(--ods-font-card-section);
  color: var(--ods-color-text);
}
.dest-summary__main,
.dest-summary__sub {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font: var(--ods-font-card-meta);
  color: var(--ods-color-text-secondary);
}
.dest-summary__main {
  font: var(--ods-font-card-body);
  color: var(--ods-color-text);
}
.dest-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ods-space-8);
  margin: 0 0 var(--ods-space-8);
}
.dest-head__actions {
  display: flex;
  align-items: center;
  gap: var(--ods-space-4);
}
.content :deep(.add-dest-btn.ods-btn) {
  min-height: var(--ods-button-height-in-card);
  height: var(--ods-button-height-in-card);
  font: var(--ods-font-body-2);
  font-weight: 600;
}
.content :deep(.add-line-btn.ods-btn) {
  min-height: var(--ods-button-height-in-card);
  height: var(--ods-button-height-in-card);
  font: var(--ods-font-body-2);
  font-weight: 600;
}
.save-block {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-8);
}
.order-sum {
  margin: 0;
  font: var(--ods-font-form-help);
  color: var(--ods-color-text-secondary);
}
.date-iso {
  position: relative;
  height: var(--ods-control-height);
  min-height: var(--ods-control-height);
  box-sizing: border-box;
  display: flex;
  align-items: center;
  padding: 0 var(--ods-space-16);
  border: 1px solid var(--ods-color-border);
  border-radius: var(--ods-radius-button);
  background: var(--ods-color-white);
}
.date-iso__value {
  font: var(--ods-font-form-value);
  color: var(--ods-color-text);
  pointer-events: none;
}
.date-iso__native {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  margin: 0;
  padding: 0;
  border: 0;
  opacity: 0;
  cursor: pointer;
}
.customer-row {
  display: flex;
  flex-wrap: nowrap;
  align-items: center;
  gap: var(--ods-space-8);
  min-width: 0;
}
.customer-row :deep(.ods-select) {
  flex: 1 1 auto;
  min-width: 0;
}
.link-btn {
  box-sizing: border-box;
  flex: 0 0 var(--ods-control-height);
  width: var(--ods-control-height);
  height: var(--ods-control-height);
  min-width: var(--ods-control-height);
  min-height: var(--ods-control-height);
  margin: 0;
  padding: 0;
  border: 1px solid var(--ods-color-border);
  border-radius: var(--ods-radius-button);
  background: var(--ods-color-gray-100);
  color: var(--ods-color-gray-900);
  font: var(--ods-font-form-label);
  line-height: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}
.modal {
  position: fixed;
  inset: 0;
  z-index: 80;
  display: flex;
  align-items: flex-end;
  justify-content: center;
  padding: var(--ods-space-12);
  background: color-mix(in srgb, var(--ods-color-gray-900) 45%, transparent);
}
.modal__card {
  width: min(520px, 100%);
  max-height: 80dvh;
  overflow: auto;
  padding: var(--ods-card-padding);
  border: 1px solid var(--ods-color-border);
  border-radius: var(--ods-radius-card) var(--ods-radius-card)
    var(--ods-radius-button) var(--ods-radius-button);
  background: var(--ods-color-white);
  box-shadow: var(--ods-shadow-card);
  display: flex;
  flex-direction: column;
  gap: var(--ods-page-content-gap);
}
.modal__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ods-space-8);
}
.modal__head h2 {
  margin: 0;
  font: var(--ods-font-title-2);
  font-weight: 800;
}
.modal__close {
  border: none;
  background: transparent;
  color: var(--ods-color-primary);
  font: var(--ods-font-form-label);
  font-weight: 700;
  cursor: pointer;
  min-height: var(--ods-control-height);
}
.modal__error {
  margin: 0;
  font: var(--ods-font-form-help);
  color: var(--ods-color-danger);
  line-height: 1.45;
}
</style>
