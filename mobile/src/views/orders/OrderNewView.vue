<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'

import { fetchCommonCodes } from '@/api/commonCodes'
import { createCustomer, createOrder, fetchCustomers, fetchOrder, updateOrder } from '@/api/orders'
import { fetchWorkLogAccountCodes, type WorkLogAccountCodeOption } from '@/api/workLogs'
import { ApiClientError } from '@/api/client'
import iconChevronDown from '@/assets/ods/common/icon-chevron-down.svg'
import iconChevronRight from '@/assets/ods/scr004/icon-chevron-right.svg'
import ParcelDestinationSheet from '@/components/sales/ParcelDestinationSheet.vue'
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
  CODE_PARENT_SALES_TYPE,
  CODE_PARENT_SEASON,
  CODE_PARENT_SIZE,
  CODE_PARENT_SPEC,
  DEFAULT_SALES_TYPE_CD,
  DEFAULT_SEASON_TYPE_CD,
  DELIVERY_TP_VISIT,
  LABEL_ADD_LINE,
  LABEL_AMT,
  LABEL_BASIC_INFO,
  LABEL_CANCEL_EDIT,
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
  LABEL_EDIT_ORDER,
  LABEL_EXPAND_LINE,
  LABEL_EXPAND_SHIP,
  LABEL_GRADE,
  LABEL_LINE,
  LABEL_NEW_CUSTOMER,
  LABEL_NEW_CUSTOMER_A11Y,
  LABEL_NEW_CUSTOMER_PLUS,
  LABEL_NEW_ORDER,
  LABEL_ORDER_DT,
  LABEL_PREPAY,
  LABEL_PREPAY_METHOD,
  LABEL_QTY,
  LABEL_REMOVE_LINE,
  LABEL_RCV_ADDR,
  LABEL_RCV_NAME,
  LABEL_RCV_TEL,
  LABEL_RMK,
  LABEL_SALES_TYPE,
  LABEL_SAVE_ORDER,
  LABEL_SEASON_TYPE,
  LABEL_SIZE,
  LABEL_TOTAL_LINES,
  LABEL_TOTAL_QTY,
  LABEL_UNIT_PRICE,
  LABEL_VARIETY,
  LABEL_WEIGHT,
  MSG_CUSTOMER_REQUIRED,
  MSG_CUSTOMER_SAVE_FAIL,
  MSG_PARCEL_DEST_NONE,
  MSG_PREPAY_METHOD_REQUIRED,
  MSG_SAVE_FAIL,
  formatOrderAmt,
  isOrderEditLocked,
  isParcelDelivery,
  isPearVariety,
  isVarietyCode,
  PEAR_ITEM_CD,
  PREPAY_METHOD_ACCT_LEVEL,
  PREPAY_METHOD_ACCT_PREFIX,
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
  effectiveDests,
  findSaveIssue as findFormSaveIssue,
  isBlankDestDraft,
  linesFromDetail,
  num,
  type EditDest,
  type EditLine,
} from '@/views/orders/orderFormModel'
import {
  deliveryQtyTone,
  emptyDeliveryDraft,
  orderParcelStatusText,
  type ShipDeliveryDraft,
} from '@/views/sales/shipDeliveryModel'
import { todayBizIso } from '@/shared/bizDate'
import { useAppStore } from '@/composables/stores/app'
import type { CommonCodeItem } from '@/types/commonCode'
import type { CustomerListItem, OrderCreatePayload } from '@/types/order'

const LABEL_DEST_SETUP = '설정 ›'
const LABEL_DEST_EDIT = '편집 ›'
const LABEL_UNIT_BOX = '박스'

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
const salesTypeCd = ref(DEFAULT_SALES_TYPE_CD)
const seasonTypeCd = ref(DEFAULT_SEASON_TYPE_CD)
const prePay = ref('0')
const prePayMethodCd = ref('')
/** hydrate 시점의 저장된 결제수단. 레거시 NULL 보완 판정용. */
const originalPrePayMethodCd = ref('')
const payMethodOptions = ref<WorkLogAccountCodeOption[]>([])
const rmk = ref('')
const lines = ref<EditLine[]>([emptyLine()])
const expandedProductIndex = ref<number | null>(0)
const expandedShipIndex = ref<number | null>(null)
const destSheetLineIdx = ref<number | null>(null)
const destSheetOpenFormIndex = ref<number | null>(null)
const customers = ref<CustomerListItem[]>([])
const salesTypes = ref<CommonCodeItem[]>([])
const seasonTypes = ref<CommonCodeItem[]>([])
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
const showPrePayMethod = computed(() => num(prePay.value) > 0)
/** 확정/부분출고 + 선입금>0 + 저장 method 없음 → 결제수단만 1회 보완 가능 */
const legacyMissingPrePayMethod = computed(
  () =>
    isEdit.value &&
    num(prePay.value) > 0 &&
    !originalPrePayMethodCd.value &&
    (statusCd.value === ORDER_STATUS_CONFIRMED || statusCd.value === ORDER_STATUS_PREP),
)
/** 결제수단 잠금: 헤더 잠금이어도 레거시 보완이면 예외로 열림 */
const lockPrePayMethod = computed(
  () => editLocked.value || (lockHeaderCore.value && !legacyMissingPrePayMethod.value),
)

watch(prePay, (raw) => {
  if (num(raw) <= 0) {
    prePayMethodCd.value = ''
  }
})

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
  const assigned = destQtySum(line)
  if (assigned <= 1e-9) {
    return joinDot([tpNm, MSG_PARCEL_DEST_NONE])
  }
  return joinDot([
    tpNm,
    `${LABEL_DEST} ${effectiveDests(line).length}${LABEL_DEST_COUNT_SUFFIX}`,
    `${formatOrderAmt(assigned)}/${formatOrderAmt(num(line.qty))}`,
  ])
}

function parcelStatusText(line: EditLine): string {
  return orderParcelStatusText(num(line.qty), destQtySum(line), LABEL_UNIT_BOX)
}

function parcelStatusTone(line: EditLine): 'ok' | 'warn' | 'danger' {
  return deliveryQtyTone(num(line.qty), destQtySum(line))
}

function parcelDestBtnLabel(line: EditLine): string {
  return destQtySum(line) <= 1e-9 ? LABEL_DEST_SETUP : LABEL_DEST_EDIT
}

function editDestToDraft(dest: EditDest): ShipDeliveryDraft {
  return emptyDeliveryDraft({
    qty: Math.max(1, Math.floor(num(dest.qty))),
    rcv_name: dest.rcv_name,
    rcv_tel: dest.rcv_tel,
    rcv_addr: dest.rcv_addr,
    dlvry_msg: dest.dlvry_msg,
    ship_fee: 0,
  })
}

function draftToEditDest(d: ShipDeliveryDraft): EditDest {
  return {
    qty: String(Math.max(1, Math.floor(Number(d.qty) || 0))),
    rcv_name: String(d.rcv_name || '').trim(),
    rcv_tel: String(d.rcv_tel || '').trim(),
    rcv_addr: String(d.rcv_addr || '').trim(),
    dlvry_msg: String(d.dlvry_msg || '').trim(),
  }
}

function parcelInitialDests(line: EditLine): ShipDeliveryDraft[] {
  return effectiveDests(line).map(editDestToDraft)
}

const destSheetLine = computed(() =>
  destSheetLineIdx.value != null ? lines.value[destSheetLineIdx.value] ?? null : null,
)

const destSheetProductSummary = computed(() =>
  destSheetLine.value ? lineSpecText(destSheetLine.value) : '',
)

const destSheetOrderQty = computed(() =>
  destSheetLine.value ? Math.max(0, Math.floor(num(destSheetLine.value.qty))) : 0,
)

const destSheetInitialDests = computed(() =>
  destSheetLine.value ? parcelInitialDests(destSheetLine.value) : [],
)

const destSheetCustomerDefaults = computed(() => {
  const c = customers.value.find((x) => x.custm_id === custmId.value)
  return {
    rcv_name: c?.custm_nm || '',
    rcv_tel: c?.mobile || '',
  }
})

const destSheetOrdererName = computed(
  () => String(destSheetCustomerDefaults.value.rcv_name || '').trim(),
)

function openParcelDestSheet(lineIdx: number, formIndex: number | null = null) {
  destSheetOpenFormIndex.value = formIndex
  destSheetLineIdx.value = lineIdx
}

function closeParcelDestSheet() {
  destSheetLineIdx.value = null
  destSheetOpenFormIndex.value = null
}

function onParcelDestComplete(drafts: ShipDeliveryDraft[]) {
  const idx = destSheetLineIdx.value
  if (idx == null) return
  const line = lines.value[idx]
  if (!line) return
  line.dests = drafts.map(draftToEditDest)
  closeParcelDestSheet()
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
    line.dests = []
    return
  }
  if (!nowParcel) {
    const first = line.dests.find((d) => !isBlankDestDraft(d)) || line.dests[0] || emptyDest()
    first.qty = line.qty
    line.dests = [first]
  }
}

function visitDest(line: EditLine): EditDest {
  if (!line.dests.length) line.dests.push(emptyDest())
  return line.dests[0]
}

function lineDeliveries(line: EditLine): OrderCreatePayload['lines'][number]['deliveries'] {
  const tp = line.delivery_tp_cd || DELIVERY_TP_VISIT
  if (isParcelDelivery(tp)) {
    return effectiveDests(line).map((d) => ({
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
    return
  }
  expandedProductIndex.value = idx
  expandedShipIndex.value = null
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
  if (isParcelDelivery(line.delivery_tp_cd)) {
    line.dests = line.dests.filter((d) => !isBlankDestDraft(d))
    return
  }
  if (!line.dests.length) {
    line.dests.push(emptyDest())
  }
  if (line.dests[0]) {
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
    const [cust, pearKids, grade, spec, size, dlv, payMethods, salesTypeCodes, seasonCodes] =
      await Promise.all([
      fetchCustomers(farmCd.value),
      fetchCommonCodes(farmCd.value, PEAR_ITEM_CD),
      fetchCommonCodes(farmCd.value, CODE_PARENT_GRADE),
      fetchCommonCodes(farmCd.value, CODE_PARENT_SPEC),
      fetchCommonCodes(farmCd.value, CODE_PARENT_SIZE),
      fetchCommonCodes(farmCd.value, CODE_PARENT_DELIVERY),
      fetchWorkLogAccountCodes(
        farmCd.value,
        PREPAY_METHOD_ACCT_PREFIX,
        PREPAY_METHOD_ACCT_LEVEL,
      ),
      fetchCommonCodes(farmCd.value, CODE_PARENT_SALES_TYPE),
      fetchCommonCodes(farmCd.value, CODE_PARENT_SEASON),
    ])
    customers.value = cust
    // FR01 직계는 중분류(배/배즙/원물). 품종은 FR010100 하위 소분류만.
    varieties.value = pearKids.filter((c) => isVarietyCode(c.code_cd))
    grades.value = grade
    specs.value = spec
    pearSizes.value = size
    deliveries.value = dlv
    payMethodOptions.value = payMethods
    salesTypes.value = salesTypeCodes
    seasonTypes.value = seasonCodes
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
  // 레거시 blank/NULL → 강제 소매/일반 치환 금지
  salesTypeCd.value = detail.sales_type_cd || ''
  seasonTypeCd.value = detail.season_type_cd || ''
  prePay.value = String(detail.pre_pay_amt ?? 0)
  originalPrePayMethodCd.value = String(detail.pre_pay_method_cd || '')
  prePayMethodCd.value = originalPrePayMethodCd.value
  rmk.value = detail.rmk || ''
  lines.value = linesFromDetail(detail, (line) =>
    isPearVariety(line.variety_cd) ? weightKgCodes.value : weightPackCodes.value,
  )
  lines.value.forEach(applyLineDefaults)
  expandedProductIndex.value = 0
  expandedShipIndex.value = null
}

function addLine() {
  if (lockProducts.value) return
  const next = emptyLine()
  applyLineDefaults(next)
  lines.value.push(next)
  expandedProductIndex.value = lines.value.length - 1
  expandedShipIndex.value = null
}

function removeLine(idx: number) {
  if (lockProducts.value) return
  if (lines.value.length <= 1) return
  lines.value.splice(idx, 1)
  expandedProductIndex.value = Math.min(idx, lines.value.length - 1)
  expandedShipIndex.value = null
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
  if (num(prePay.value) > 0 && !prePayMethodCd.value) {
    errorMsg.value = MSG_PREPAY_METHOD_REQUIRED
    return
  }
  const issue = findSaveIssue()
  if (issue) {
    errorMsg.value = issue.message
    expandedProductIndex.value = issue.lineIdx
    expandedShipIndex.value = issue.ship ? issue.lineIdx : expandedShipIndex.value
    if (issue.destIdx !== null) {
      openParcelDestSheet(issue.lineIdx, issue.destIdx)
    }
    return
  }
  const payload = buildOrderPayload({
    custmId: custmId.value,
    orderDt: orderDt.value,
    salesTypeCd: salesTypeCd.value,
    seasonTypeCd: seasonTypeCd.value,
    prePay: num(prePay.value),
    prePayMethodCd: prePayMethodCd.value || null,
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
          <OdsFormField :label="LABEL_SALES_TYPE" required>
            <OdsSelect
              v-model="salesTypeCd"
              variant="form"
              required
              data-testid="order-sales-type"
              :disabled="lockHeaderCore"
            >
              <option value="">선택</option>
              <option v-for="c in salesTypes" :key="c.code_cd" :value="c.code_cd">
                {{ c.code_nm }}
              </option>
            </OdsSelect>
          </OdsFormField>
          <OdsFormField :label="LABEL_SEASON_TYPE" required>
            <OdsSelect
              v-model="seasonTypeCd"
              variant="form"
              required
              data-testid="order-season-type"
              :disabled="lockHeaderCore"
            >
              <option value="">선택</option>
              <option v-for="c in seasonTypes" :key="c.code_cd" :value="c.code_cd">
                {{ c.code_nm }}
              </option>
            </OdsSelect>
          </OdsFormField>
          <OdsFormField :label="LABEL_PREPAY" optional>
            <OdsInput v-model="prePay" type="number" variant="form" bare :disabled="lockHeaderCore" />
          </OdsFormField>
          <OdsFormField v-if="showPrePayMethod" :label="LABEL_PREPAY_METHOD" required>
            <OdsSelect
              v-model="prePayMethodCd"
              variant="form"
              required
              data-testid="order-prepay-method"
              :disabled="lockPrePayMethod"
            >
              <option value="">선택</option>
              <option
                v-for="opt in payMethodOptions"
                :key="opt.acct_cd"
                :value="opt.acct_cd"
              >
                {{ opt.acct_nm }}
              </option>
            </OdsSelect>
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
                  <div
                    class="line__dest"
                    :class="`line__dest--${parcelStatusTone(line)}`"
                    data-testid="order-new-delivery-status"
                  >
                    <span class="line__dest-status">{{ parcelStatusText(line) }}</span>
                    <button
                      type="button"
                      class="line__dest-btn"
                      data-testid="order-new-dest-open"
                      @click="openParcelDestSheet(idx)"
                    >
                      {{ parcelDestBtnLabel(line) }}
                    </button>
                  </div>
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
    <ParcelDestinationSheet
      :open="destSheetLineIdx != null"
      :product-summary="destSheetProductSummary"
      :order-qty="destSheetOrderQty"
      :unit-label="LABEL_UNIT_BOX"
      :initial-dests="destSheetInitialDests"
      :customer-defaults="destSheetCustomerDefaults"
      :orderer-name="destSheetOrdererName"
      :show-ship-fee="false"
      :lock-structure="lockDestStructure"
      :open-form-index="destSheetOpenFormIndex"
      test-id-prefix="order-new"
      @close="closeParcelDestSheet"
      @complete="onParcelDestComplete"
    />
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
.line__dest {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ods-space-8);
  box-sizing: border-box;
  min-height: 28px;
  margin: 0;
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
