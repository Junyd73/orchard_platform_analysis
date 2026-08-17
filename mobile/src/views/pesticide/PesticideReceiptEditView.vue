<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'

import {
  createPesticideReceipt,
  deletePesticideReceipt,
  fetchPesticideInfoDetail,
  fetchPesticideInfoList,
  fetchPesticideReceiptDetail,
  fetchPesticideStockList,
  fetchPesticideSuppliers,
  updatePesticideReceipt,
} from '@/api/pesticide'
import { ApiClientError } from '@/api/client'
import OdsAppBar from '@/components/ods/OdsAppBar.vue'
import OdsBottomNav from '@/components/ods/OdsBottomNav.vue'
import OdsButton from '@/components/ods/OdsButton.vue'
import OdsCard from '@/components/ods/OdsCard.vue'
import OdsInput from '@/components/ods/OdsInput.vue'
import OdsSkeleton from '@/components/ods/OdsSkeleton.vue'
import {
  LABEL_RECEIPT_APPLIED_BANNER,
  LABEL_RECEIPT_DETAIL_TITLE,
  LABEL_RECEIPT_DICT_APPLY,
  LABEL_RECEIPT_DICT_CLEAR,
  LABEL_RECEIPT_DICT_EMPTY,
  LABEL_RECEIPT_DICT_LINKED,
  LABEL_RECEIPT_DICT_LOAD_FAIL,
  LABEL_RECEIPT_DICT_PICK,
  LABEL_RECEIPT_DICT_SEARCH,
  LABEL_RECEIPT_ITEM_ADD,
  LABEL_RECEIPT_ITEM_NM,
  LABEL_RECEIPT_ITEM_REMOVE,
  LABEL_RECEIPT_ITEMS,
  LABEL_RECEIPT_LINK_STOCK,
  LABEL_RECEIPT_LINK_STOCK_EMPTY,
  LABEL_RECEIPT_NEW_TITLE,
  LABEL_RECEIPT_SAVE,
  LABEL_RECEIPT_SPEC_LABEL,
  LABEL_RECEIPT_SUPPLIER,
  LABEL_RECEIPT_SUPPLIER_DIRECT,
  LABEL_RECEIPT_SUPPLIER_NM,
  MSG_RECEIPT_LINE_REQUIRED,
  MSG_RECEIPT_SAVE_FAIL,
} from '@/views/pesticide/pesticideConstants'
import { todayIso } from '@/views/work-log/workLogConstants'
import { useAppStore } from '@/composables/stores/app'
import type {
  PesticideInfoSummary,
  PesticideReceiptLine,
  PesticideStockItem,
  PesticideSupplier,
} from '@/types/pesticide'

type EditLine = {
  item_nm: string
  spec_nm: string
  qty: number
  unit_price: number | null
  supply_amt: number | null
  tax_amt: number | null
  link_item_id: number | null
  info_id: number | null
  info_label: string
}

const route = useRoute()
const router = useRouter()
const { farmCd } = storeToRefs(useAppStore())

const isNew = computed(() => route.name === 'pesticide-receipt-new')
const receiptId = computed(() => Number(route.params.receiptId || 0))
const pageTitle = computed(() =>
  isNew.value ? LABEL_RECEIPT_NEW_TITLE : LABEL_RECEIPT_DETAIL_TITLE,
)

const loading = ref(true)
const saving = ref(false)
const errorMsg = ref('')
const saveErrorMsg = ref('')
const toastMsg = ref('')

const receiptDt = ref(todayIso())
const supplierId = ref<number | null>(null)
const supplierNmText = ref('')
const recipientNm = ref('')
const rmk = ref('')
const appliedYn = ref('N')
const lines = ref<EditLine[]>([emptyLine()])
const suppliers = ref<PesticideSupplier[]>([])
const stockItems = ref<PesticideStockItem[]>([])

const dictOpen = ref(false)
const dictLineIdx = ref(0)
const dictKeyword = ref('')
const dictLoading = ref(false)
const dictErrorMsg = ref('')
const dictSelected = ref<PesticideInfoSummary | null>(null)
const dictItems = ref<PesticideInfoSummary[]>([])
let dictTimer: number | undefined

const isApplied = computed(() => appliedYn.value === 'Y')
/** 공급자 마스터 선택 시 공급자명 잠금 */
const supplierNmLocked = computed(() => supplierId.value != null)

function emptyLine(): EditLine {
  return {
    item_nm: '',
    spec_nm: '',
    qty: 0,
    unit_price: null,
    supply_amt: null,
    tax_amt: null,
    link_item_id: null,
    info_id: null,
    info_label: '',
  }
}

function showToast(msg: string) {
  toastMsg.value = msg
  window.setTimeout(() => {
    if (toastMsg.value === msg) toastMsg.value = ''
  }, 2200)
}

function addLine() {
  lines.value.push(emptyLine())
}

function removeLine(idx: number) {
  if (lines.value.length <= 1) return
  lines.value.splice(idx, 1)
}

function onSupplierChange() {
  if (supplierId.value == null) return
  const found = suppliers.value.find((s) => s.supplier_id === supplierId.value)
  if (found) {
    supplierNmText.value = found.supplier_nm
  }
}

/** 마스터 연결 시 표시명을 마스터와 맞춤 */
function syncLinkedNamesFromMasters() {
  onSupplierChange()
  for (const ln of lines.value) {
    if (ln.link_item_id == null) continue
    const found = stockItems.value.find((x) => x.item_id === ln.link_item_id)
    if (found) {
      ln.item_nm = found.item_nm
    }
  }
}

function onPickItem(idx: number, itemIdRaw: string) {
  const id = Number(itemIdRaw)
  const found = stockItems.value.find((x) => x.item_id === id)
  if (!found) {
    lines.value[idx].link_item_id = null
    return
  }
  lines.value[idx].link_item_id = found.item_id
  lines.value[idx].item_nm = found.item_nm
  lines.value[idx].spec_nm = found.spec_nm || ''
  if (found.info_id) {
    lines.value[idx].info_id = found.info_id
    lines.value[idx].info_label =
      found.info_pesticide_nm || found.item_nm || LABEL_RECEIPT_DICT_LINKED
  }
  saveErrorMsg.value = ''
}

function clearInfoLink(idx: number) {
  lines.value[idx].info_id = null
  lines.value[idx].info_label = ''
  saveErrorMsg.value = ''
}

function openDictPicker(idx: number) {
  dictLineIdx.value = idx
  dictKeyword.value = lines.value[idx].item_nm || ''
  dictItems.value = []
  dictErrorMsg.value = ''
  dictSelected.value = null
  dictOpen.value = true
  void searchDict()
}

function closeDictPicker() {
  dictOpen.value = false
  dictSelected.value = null
  dictErrorMsg.value = ''
  window.clearTimeout(dictTimer)
}

function selectDictItem(info: PesticideInfoSummary) {
  dictSelected.value = info
}

function applyDictPick() {
  if (!dictSelected.value) return
  void pickDict(dictSelected.value)
}

function onDictKeywordInput() {
  window.clearTimeout(dictTimer)
  dictTimer = window.setTimeout(() => {
    void searchDict()
  }, 280)
}

async function searchDict() {
  const farm = farmCd.value
  if (!farm) return
  dictLoading.value = true
  dictErrorMsg.value = ''
  try {
    const res = await fetchPesticideInfoList(farm, {
      keyword: dictKeyword.value,
      limit: 40,
    })
    dictItems.value = res.items
    if (
      dictSelected.value &&
      !res.items.some((it) => it.info_id === dictSelected.value?.info_id)
    ) {
      dictSelected.value = null
    }
  } catch (err) {
    dictItems.value = []
    dictSelected.value = null
    dictErrorMsg.value =
      err instanceof ApiClientError ? err.message : LABEL_RECEIPT_DICT_LOAD_FAIL
  } finally {
    dictLoading.value = false
  }
}

function isCapacitySpec(value: string | null | undefined): boolean {
  const v = String(value || '').trim()
  if (!v) return false
  if (/^\d+\s*[x×]\s*\d+/i.test(v)) return true
  return /\d\s*(?:ml|㎖|mL|L|ℓ|l|g|kg|mg|cc)\b/i.test(v)
}

async function pickDict(info: PesticideInfoSummary) {
  const idx = dictLineIdx.value
  const ln = lines.value[idx]
  ln.info_id = info.info_id
  ln.info_label = info.pesticide_nm
  ln.item_nm = info.pesticide_nm
  ln.link_item_id = null

  let capacitySpec = ''
  const farm = farmCd.value
  if (farm) {
    try {
      const detail = await fetchPesticideInfoDetail(farm, info.info_id)
      if (isCapacitySpec(detail.spec_nm)) {
        capacitySpec = String(detail.spec_nm).trim()
      }
    } catch {
      /* 사전 상세는 선택적 — 용량 없으면 비움 */
    }
  }
  if (
    !capacitySpec &&
    isCapacitySpec(ln.spec_nm) &&
    ln.spec_nm !== info.pesticide_nm &&
    ln.spec_nm !== info.brand_nm
  ) {
    capacitySpec = ln.spec_nm.trim()
  }
  ln.spec_nm = capacitySpec

  saveErrorMsg.value = ''
  closeDictPicker()
}

function recalcLine(idx: number) {
  const ln = lines.value[idx]
  if (ln.unit_price == null || !ln.qty) {
    ln.supply_amt = null
    ln.tax_amt = null
    return
  }
  const supply = Math.round(ln.qty * ln.unit_price)
  ln.supply_amt = supply
  ln.tax_amt = Math.round(supply * 0.1)
}

function toBodyLines(): PesticideReceiptLine[] {
  return lines.value
    .filter((ln) => ln.item_nm.trim() && ln.qty > 0)
    .map((ln, i) => ({
      line_no: i + 1,
      item_nm: ln.item_nm.trim(),
      spec_nm: ln.spec_nm || null,
      qty: Math.trunc(ln.qty),
      unit_price: ln.unit_price,
      supply_amt: ln.supply_amt,
      tax_amt: ln.tax_amt,
      link_item_id: ln.link_item_id,
      info_id: ln.info_id,
    }))
}

async function loadMasters() {
  const farm = farmCd.value
  if (!farm) return
  const [sup, stock] = await Promise.all([
    fetchPesticideSuppliers(farm),
    fetchPesticideStockList(farm, { sort: 'name' }),
  ])
  suppliers.value = sup.items
  stockItems.value = stock.items
}

async function loadDetail() {
  const farm = farmCd.value
  if (!farm || isNew.value) {
    loading.value = false
    return
  }
  loading.value = true
  errorMsg.value = ''
  try {
    const d = await fetchPesticideReceiptDetail(farm, receiptId.value)
    receiptDt.value = d.receipt_dt
    supplierId.value = d.supplier_id
    supplierNmText.value = d.supplier_nm_text || ''
    recipientNm.value = d.recipient_nm || ''
    rmk.value = d.rmk || ''
    appliedYn.value = d.stock_applied_yn || 'N'
    lines.value = (d.lines.length ? d.lines : [{} as PesticideReceiptLine]).map(
      (ln) => ({
        item_nm: ln.item_nm || '',
        spec_nm: ln.spec_nm || '',
        qty: ln.qty || 0,
        unit_price: ln.unit_price ?? null,
        supply_amt: ln.supply_amt ?? null,
        tax_amt: ln.tax_amt ?? null,
        link_item_id: ln.link_item_id ?? null,
        info_id: ln.info_id ?? null,
        info_label: ln.info_id
          ? LABEL_RECEIPT_DICT_LINKED
          : '',
      }),
    )
  } catch (err) {
    errorMsg.value =
      err instanceof ApiClientError ? err.message : '입고를 불러오지 못했습니다.'
  } finally {
    syncLinkedNamesFromMasters()
    loading.value = false
  }
}

async function save() {
  const farm = farmCd.value
  if (!farm || saving.value) return
  const bodyLines = toBodyLines()
  saveErrorMsg.value = ''
  if (!bodyLines.length) {
    saveErrorMsg.value = MSG_RECEIPT_LINE_REQUIRED
    return
  }
  saving.value = true
  try {
    const body = {
      receipt_dt: receiptDt.value,
      supplier_id: supplierId.value,
      supplier_nm_text: supplierNmText.value,
      recipient_nm: recipientNm.value,
      rmk: rmk.value,
      lines: bodyLines,
    }
    if (isNew.value) {
      const res = await createPesticideReceipt(farm, body)
      showToast(res.message)
      await router.replace({
        name: 'pesticide-receipt-detail',
        params: { receiptId: String(res.receipt_id) },
      })
    } else {
      const res = await updatePesticideReceipt(farm, receiptId.value, body)
      showToast(res.message)
      await loadDetail()
      await loadMasters()
    }
  } catch (err) {
    saveErrorMsg.value =
      err instanceof ApiClientError ? err.message : MSG_RECEIPT_SAVE_FAIL
  } finally {
    saving.value = false
  }
}

async function remove() {
  const farm = farmCd.value
  if (!farm || isNew.value) return
  const tip = isApplied.value
    ? '재고에 반영된 입고입니다. 삭제하면 반영 수량이 되돌아갑니다. 계속할까요?'
    : '이 입고를 삭제할까요?'
  if (!window.confirm(tip)) return
  try {
    await deletePesticideReceipt(farm, receiptId.value)
    showToast('삭제되었습니다.')
    await router.replace({ name: 'pesticide-receipts' })
  } catch (err) {
    showToast(err instanceof ApiClientError ? err.message : '삭제 실패')
  }
}

watch(
  lines,
  () => {
    if (saveErrorMsg.value) saveErrorMsg.value = ''
  },
  { deep: true },
)

watch(
  () => [farmCd.value, route.fullPath],
  async () => {
    loading.value = true
    try {
      await loadMasters()
      await loadDetail()
      syncLinkedNamesFromMasters()
    } finally {
      loading.value = false
    }
  },
)

onMounted(async () => {
  if (!String(receiptId.value || '').trim()) {
    receiptDt.value = todayIso()
  }
  await loadMasters()
  await loadDetail()
  syncLinkedNamesFromMasters()
})
</script>

<template>
  <div class="page">
    <main class="content ods-page-content">
      <OdsAppBar show-back back-fallback="pesticide-receipts" />

      <div class="stack">
        <header class="head">
          <h1 class="head__title">{{ pageTitle }}</h1>
        </header>

        <OdsCard v-if="isApplied" role="status">
          {{ LABEL_RECEIPT_APPLIED_BANNER }}
        </OdsCard>

        <p v-if="errorMsg" class="error" role="alert">{{ errorMsg }}</p>
        <OdsSkeleton v-else-if="loading" height="160px" />

        <form v-else class="form" @submit.prevent="save">
          <section class="card">
            <label class="field">
              <span>입고일</span>
              <input v-model="receiptDt" type="date" required />
            </label>
            <label class="field">
              <span>{{ LABEL_RECEIPT_SUPPLIER }}</span>
              <select v-model="supplierId" @change="onSupplierChange">
                <option :value="null">{{ LABEL_RECEIPT_SUPPLIER_DIRECT }}</option>
                <option
                  v-for="s in suppliers"
                  :key="s.supplier_id"
                  :value="s.supplier_id"
                >
                  {{ s.supplier_nm }}
                </option>
              </select>
            </label>
            <OdsInput
              v-model="supplierNmText"
              :label="LABEL_RECEIPT_SUPPLIER_NM"
              :disabled="supplierNmLocked"
            />
            <OdsInput v-model="recipientNm" label="인수자" />
            <OdsInput v-model="rmk" label="비고" />
          </section>

          <div class="lines-head">
            <h2 class="lines-head__title">{{ LABEL_RECEIPT_ITEMS }}</h2>
            <OdsButton
              type="button"
              variant="secondary"
              :block="false"
              @click="addLine"
            >
              {{ LABEL_RECEIPT_ITEM_ADD }}
            </OdsButton>
          </div>

          <section
            v-for="(ln, idx) in lines"
            :key="idx"
            class="card line"
          >
            <div class="link-row">
              <label class="field field--grow">
                <span>{{ LABEL_RECEIPT_LINK_STOCK }}</span>
                <select
                  :value="ln.link_item_id ?? ''"
                  @change="
                    onPickItem(idx, ($event.target as HTMLSelectElement).value)
                  "
                >
                  <option value="">{{ LABEL_RECEIPT_LINK_STOCK_EMPTY }}</option>
                  <option
                    v-for="it in stockItems"
                    :key="it.item_id"
                    :value="String(it.item_id)"
                  >
                    {{ it.item_nm }}
                  </option>
                </select>
              </label>
              <OdsButton
                type="button"
                class="link-row__dict"
                variant="secondary-filled"
                :block="false"
                @click="openDictPicker(idx)"
              >
                {{ LABEL_RECEIPT_DICT_PICK }}
              </OdsButton>
            </div>
            <p v-if="ln.info_id" class="dict-row__badge">
              {{ ln.info_label || LABEL_RECEIPT_DICT_LINKED }}
              <button
                type="button"
                class="dict-row__clear"
                @click="clearInfoLink(idx)"
              >
                {{ LABEL_RECEIPT_DICT_CLEAR }}
              </button>
            </p>

            <OdsInput
              v-model="ln.item_nm"
              :label="LABEL_RECEIPT_ITEM_NM"
              :disabled="ln.link_item_id != null"
            />
            <OdsInput v-model="ln.spec_nm" :label="LABEL_RECEIPT_SPEC_LABEL" />
            <div class="amt-grid">
              <label class="field">
                <span>수량</span>
                <input
                  v-model.number="ln.qty"
                  type="number"
                  min="0"
                  inputmode="numeric"
                  @change="recalcLine(idx)"
                />
              </label>
              <label class="field">
                <span>단가</span>
                <input
                  v-model.number="ln.unit_price"
                  type="number"
                  min="0"
                  inputmode="decimal"
                  @change="recalcLine(idx)"
                />
              </label>
              <label class="field">
                <span>공급가</span>
                <input
                  v-model.number="ln.supply_amt"
                  type="number"
                  inputmode="decimal"
                />
              </label>
              <label class="field">
                <span>세액</span>
                <input
                  v-model.number="ln.tax_amt"
                  type="number"
                  inputmode="decimal"
                />
              </label>
            </div>
            <OdsButton
              v-if="lines.length > 1"
              type="button"
              variant="danger"
              :block="false"
              @click="removeLine(idx)"
            >
              {{ LABEL_RECEIPT_ITEM_REMOVE }}
            </OdsButton>
          </section>

          <p v-if="saveErrorMsg" class="save-error" role="alert">
            {{ saveErrorMsg }}
          </p>

          <div class="actions" aria-label="저장·삭제">
            <OdsButton
              v-if="!isNew"
              type="button"
              class="actions__btn"
              variant="danger"
              :block="false"
              @click="remove"
            >
              삭제
            </OdsButton>
            <OdsButton
              type="submit"
              class="actions__btn"
              :block="false"
              :busy="saving"
            >
              {{ saving ? '저장 중…' : LABEL_RECEIPT_SAVE }}
            </OdsButton>
          </div>
        </form>
      </div>
    </main>

    <Teleport to="body">
      <div
        v-if="dictOpen"
        class="modal"
        role="dialog"
        aria-modal="true"
        :aria-label="LABEL_RECEIPT_DICT_PICK"
        @click.self="closeDictPicker"
      >
        <div class="modal__card">
          <div class="modal__head">
            <h2>{{ LABEL_RECEIPT_DICT_PICK }}</h2>
            <button type="button" class="modal__close" @click="closeDictPicker">
              닫기
            </button>
          </div>
          <OdsInput
            v-model="dictKeyword"
            bare
            type="search"
            :placeholder="LABEL_RECEIPT_DICT_SEARCH"
            @input="onDictKeywordInput"
          />
          <p v-if="dictErrorMsg" class="modal__error" role="alert">
            {{ dictErrorMsg }}
          </p>
          <OdsSkeleton v-if="dictLoading" height="80px" />
          <ul v-else class="dict-list">
            <li
              v-for="it in dictItems"
              :key="it.info_id"
              class="dict-list__row"
              :class="{ 'is-selected': dictSelected?.info_id === it.info_id }"
              @click="selectDictItem(it)"
            >
              <p class="dict-list__nm">{{ it.pesticide_nm }}</p>
              <p class="dict-list__sub">
                {{ [it.brand_nm, it.ingredient_nm, it.category_nm].filter(Boolean).join(' · ') }}
              </p>
            </li>
            <li v-if="!dictItems.length && !dictErrorMsg" class="hint">
              {{ LABEL_RECEIPT_DICT_EMPTY }}
            </li>
          </ul>
          <OdsButton
            type="button"
            :disabled="!dictSelected"
            @click="applyDictPick"
          >
            {{ LABEL_RECEIPT_DICT_APPLY }}
          </OdsButton>
        </div>
      </div>
    </Teleport>

    <p v-if="toastMsg" class="toast" role="status">{{ toastMsg }}</p>
    <OdsBottomNav />
  </div>
</template>

<style scoped>
.page {
  min-height: 100dvh;
  background: var(--ods-color-bg-muted);
  padding-bottom: calc(var(--ods-thumb-sm) + env(safe-area-inset-bottom));
}

.stack {
  display: flex;
  flex-direction: column;
  gap: var(--ods-page-content-gap);
}

.head {
  margin: 0;
}
.head__title {
  margin: 0;
  font: var(--ods-font-title-2);
  font-weight: 800;
  color: var(--ods-color-text);
}

.form {
  display: flex;
  flex-direction: column;
  gap: var(--ods-page-content-gap);
}

.card {
  margin: 0;
  padding: var(--ods-card-padding);
  border-radius: var(--ods-radius-card);
  border: 1px solid var(--ods-color-border);
  background: var(--ods-color-white);
  box-shadow: var(--ods-shadow-card);
  display: flex;
  flex-direction: column;
  gap: var(--ods-form-field-gap);
}

.field {
  display: flex;
  flex-direction: column;
  gap: var(--ods-form-label-gap);
  font: var(--ods-font-form-label);
  color: var(--ods-color-text);
}
.field input,
.field select {
  box-sizing: border-box;
  width: 100%;
  min-width: 0;
  height: var(--ods-control-height);
  min-height: var(--ods-control-height);
  border-radius: var(--ods-radius-button);
  border: 1px solid var(--ods-color-border);
  padding: 0 var(--ods-space-12);
  background: var(--ods-color-white);
  font: var(--ods-font-form-value);
  color: var(--ods-color-text);
}

.lines-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--ods-space-8);
  margin: 0;
}
.lines-head__title {
  margin: 0;
  font: var(--ods-font-form-label);
  font-weight: 700;
  color: var(--ods-color-text);
}

.dict-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--ods-space-8);
}
.link-row {
  display: flex;
  align-items: flex-end;
  gap: var(--ods-space-8);
}
.link-row .field--grow {
  flex: 1;
  min-width: 0;
}
.link-row__dict {
  flex-shrink: 0;
  margin-bottom: 0;
}
.dict-row__badge {
  margin: 0;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--ods-space-8);
  font: var(--ods-font-card-help);
  font-weight: 700;
  color: var(--ods-color-text);
}
.dict-row__clear {
  border: none;
  background: transparent;
  color: var(--ods-color-danger);
  font: var(--ods-font-card-help);
  font-weight: 700;
  cursor: pointer;
  padding: 0;
}

.amt-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: var(--ods-space-8);
}
.amt-grid .field {
  min-width: 0;
}

.actions {
  display: flex;
  flex-direction: row;
  align-items: stretch;
  gap: var(--ods-space-8);
}
.actions__btn {
  flex: 1;
  min-width: 0;
}
.actions :deep(.ods-btn) {
  width: 100%;
}

.hint,
.error {
  margin: 0;
  padding: var(--ods-card-padding);
  text-align: center;
  font: var(--ods-font-form-help);
  color: var(--ods-color-text-secondary);
}
.error {
  color: var(--ods-color-danger);
}
.save-error {
  margin: 0;
  padding: var(--ods-space-12) var(--ods-card-padding);
  border-radius: var(--ods-radius-card);
  border: 1px solid color-mix(in srgb, var(--ods-color-danger) 35%, transparent);
  background: color-mix(in srgb, var(--ods-color-danger) 8%, white);
  font: var(--ods-font-form-help);
  font-weight: 600;
  color: var(--ods-color-danger);
  line-height: 1.45;
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

.dict-list {
  list-style: none;
  margin: 0;
  padding: 0;
  border: 1px solid var(--ods-color-border);
  border-radius: var(--ods-radius-card);
  overflow: hidden;
}
.dict-list__row {
  padding: var(--ods-space-12) var(--ods-card-padding);
  border-bottom: 1px solid var(--ods-color-border);
  cursor: pointer;
}
.dict-list__row:last-child {
  border-bottom: none;
}
.dict-list__row:active {
  background: var(--ods-color-bg-muted);
}
.dict-list__row.is-selected {
  background: color-mix(in srgb, var(--ods-color-primary) 10%, white);
}
.dict-list__nm {
  margin: 0;
  font: var(--ods-font-form-value);
  font-weight: 700;
  color: var(--ods-color-text);
}
.dict-list__sub {
  margin: var(--ods-space-4) 0 0;
  font: var(--ods-font-card-section);
  color: var(--ods-color-text-secondary);
}

.toast {
  position: fixed;
  left: 50%;
  bottom: calc(var(--ods-thumb-sm) + var(--ods-space-16) + env(safe-area-inset-bottom));
  transform: translateX(-50%);
  z-index: 60;
  margin: 0;
  padding: var(--ods-space-8) var(--ods-space-16);
  border-radius: var(--ods-radius-badge);
  background: var(--ods-color-gray-900);
  color: var(--ods-color-white);
  font: var(--ods-font-card-section);
}
</style>
