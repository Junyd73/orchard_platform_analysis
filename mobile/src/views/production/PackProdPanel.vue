<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'

import {
  confirmProduction,
  fetchHarvestRecords,
  fetchRawStock,
  type HarvestRecord,
  type ProductionPrefillLine,
  type RawStockItem,
} from '@/api/production'
import { fetchCommonCodes } from '@/api/commonCodes'
import { ApiClientError } from '@/api/client'
import OdsButton from '@/components/ods/OdsButton.vue'
import OdsCard from '@/components/ods/OdsCard.vue'
import OdsFormField from '@/components/ods/OdsFormField.vue'
import OdsInput from '@/components/ods/OdsInput.vue'
import OdsSelect from '@/components/ods/OdsSelect.vue'
import {
  CODE_PARENT_GRADE,
  CODE_PARENT_SIZE,
  CODE_PARENT_VARIETY,
  CODE_PARENT_WEIGHT,
  DEFAULT_WH_CD,
  INPUT_HARVEST,
  INPUT_RAW_STOCK,
  INPUT_SOURCE_PACK_OPTIONS,
  INPUT_SOURCE_PROCESS_OPTIONS,
  LABEL_ADD_WEIGHT,
  LABEL_CONFIRM,
  LABEL_GO_SALES,
  LABEL_HARVEST_RECORD,
  LABEL_INPUT_SOURCE,
  LABEL_JUICE_BOXES,
  LABEL_JUICE_KIND,
  LABEL_PROD_TYPE,
  LABEL_PRODUCTION,
  LABEL_RAW_STOCK,
  LABEL_SAVE_STOCK,
  MSG_ADD_SIZE,
  MSG_ADD_WEIGHT,
  MSG_CONFIRM_FAIL,
  MSG_CONFIRM_OK,
  MSG_DELETE_SIZE_CONFIRM,
  MSG_DELETE_WEIGHT_CONFIRM,
  MSG_ENTER_JUICE,
  MSG_HARVEST_EMPTY,
  MSG_HARVEST_LOAD_FAIL,
  MSG_RAW_LOAD_FAIL,
  MSG_SELECT_RAW,
  MSG_MIXED_YEAR,
  MSG_MIXED_VARIETY,
  JUICE_KIND_OPTIONS,
  ITEM_JUICE_PLAIN,
  PROD_TYPE_OPTIONS,
  PROD_TYPE_PACK,
  PROD_TYPE_PROCESS,
} from '@/views/production/productionConstants'
import { attachPrefillDisplayNames } from '@/views/production/prefillDisplay'
import {
  buildHarvestConsumptions,
  canSelectHarvestRow,
  formatHarvestRowLabel,
  harvestAnchor,
  harvestSelectionSummary,
  isHarvestSelectable,
  mapProductionHarvestError,
  validateHarvestSelections,
} from '@/views/production/harvestSelection'
import { todayIso } from '@/views/work-log/workLogConstants'
import { useAppStore } from '@/composables/stores/app'
import { useSalesPrefillStore } from '@/composables/stores/salesPrefill'

// ── 타입 ─────────────────────────────────────────────────────────────
interface CodeOption { value: string; label: string }

/** 중량 카드 내 과수탭 한 개 */
interface SizeTab {
  sizeCd: string
  /** grade_cd → 박스 수 문자열 */
  gradeQty: Record<string, string>
}

/** 포장중량 카드 */
interface WeightCard {
  weightCd: string   // SZ01 계열 code_cd
  weight: number     // kg 숫자 (parseWeightFromCodeNm)
  sizes: SizeTab[]
  activeSize: string // 현재 선택된 size_cd
}

// ── emit ─────────────────────────────────────────────────────────────
const emit = defineEmits<{
  toast: [message: string]
  goSales: []
}>()

const { farmCd } = storeToRefs(useAppStore())
const salesPrefill = useSalesPrefillStore()

// ── 상태 ─────────────────────────────────────────────────────────────
const prodType    = ref(PROD_TYPE_PACK)
const inputSource = ref(INPUT_HARVEST)
const varietyCd   = ref('')

// 원료 rows
const harvestRows      = ref<HarvestRecord[]>([])
const harvestUseQtyMap = ref<Record<string, string>>({})
const rawRows           = ref<RawStockItem[]>([])
const selectedRawKey    = ref('')
// 원물 key → 사용수량 (각 행 독립 관리)
const rawUseQtyMap      = ref<Record<string, string>>({})

// 마스터 코드
const varietyOptions = ref<CodeOption[]>([])
const weightOptions  = ref<CodeOption[]>([])
const sizeOptions    = ref<CodeOption[]>([])
const gradeOptions   = ref<CodeOption[]>([])

// PACK N:N:N 카드
const weightCards = ref<WeightCard[]>([])

// PROCESS 단순
const juiceQty = ref('')
const juiceItemCd = ref(ITEM_JUICE_PLAIN)

// UI 상태
const loading       = ref(false)
const confirming    = ref(false)
const postConfirm   = ref(false)
const lastPrefill   = ref<ProductionPrefillLine[]>([])
const errorMsg      = ref('')
const harvestLoadError = ref('')
const rawLoadError     = ref('')

// ── computed ─────────────────────────────────────────────────────────
const isHarvest = computed(() => inputSource.value === INPUT_HARVEST)
const isPack    = computed(() => prodType.value === PROD_TYPE_PACK)

const prodTypeOptions = PROD_TYPE_OPTIONS.map(o => ({ value: o.value, label: o.label }))
const juiceKindOptions = JUICE_KIND_OPTIONS.map(o => ({ value: o.value, label: o.label }))
const inputOptions = computed(() =>
  (prodType.value === PROD_TYPE_PROCESS
    ? INPUT_SOURCE_PROCESS_OPTIONS
    : INPUT_SOURCE_PACK_OPTIONS
  ).map(o => ({ value: o.value, label: o.label })),
)

/** 이미 추가된 weightCd 목록 */
const usedWeightCds = computed(() => new Set(weightCards.value.map(c => c.weightCd)))
/** 추가 가능한 중량 목록 */
const availableWeightOptions = computed(() =>
  weightOptions.value.filter(w => !usedWeightCds.value.has(w.value)),
)

/** 각 중량 카드의 총 박스 */
function cardTotal(card: WeightCard): number {
  return card.sizes.reduce((sum, s) => sum + sizeTotal(s), 0)
}
/** 각 과수탭의 총 박스 */
function sizeTotal(tab: SizeTab): number {
  return Object.values(tab.gradeQty).reduce((sum, v) => sum + (Number(v) || 0), 0)
}

/** 전체 생산결과 line 수 (qty > 0) */
const totalPositiveLines = computed(() =>
  weightCards.value.reduce((sum, card) =>
    sum + card.sizes.reduce((s2, tab) =>
      s2 + Object.values(tab.gradeQty).filter(v => Number(v) > 0).length, 0), 0),
)

const harvestSelections = computed(() => {
  const out: Record<string, number> = {}
  for (const [wid, raw] of Object.entries(harvestUseQtyMap.value)) {
    const qty = Number(raw)
    if (Number.isInteger(qty) && qty >= 1) out[wid] = qty
  }
  return out
})
const harvestAnchorRow = computed(() =>
  harvestAnchor(harvestRows.value, harvestSelections.value),
)
const harvestSummaryText = computed(() =>
  harvestSelectionSummary(harvestSelections.value),
)

// ── 유틸 ─────────────────────────────────────────────────────────────
function rawKey(r: RawStockItem): string {
  return `${r.wh_cd}|${r.variety_cd}|${r.size_cd}|${r.weight}|${r.harvest_year}|${r.storage_dt}`
}

function rawUseQtyOf(row: RawStockItem): number {
  const n = Number(rawUseQtyMap.value[rawKey(row)] ?? '')
  return Number.isInteger(n) ? n : 0
}

/** qty>=1인 원물 행만 Core raw_consumptions로 전달 (PC WorkCart와 동일, N건). */
function buildRawConsumptions() {
  return rawRows.value
    .filter((r) => rawUseQtyOf(r) >= 1)
    .map((r) => ({
      wh_cd: r.wh_cd,
      variety_cd: r.variety_cd,
      size_cd: r.size_cd,
      weight: r.weight,
      harvest_year: r.harvest_year,
      storage_dt: r.storage_dt,
      qty: rawUseQtyOf(r),
    }))
}

function parseWeightFromLabel(label: string): number {
  const m = label.replace(',', '.').match(/(\d+(?:\.\d+)?)/)
  return m ? parseFloat(m[1]) : 0
}

// ── 마스터 로드 ──────────────────────────────────────────────────────
async function loadMasters() {
  const farm = farmCd.value
  const [vars, weights, sizes, grades] = await Promise.all([
    fetchCommonCodes(farm, CODE_PARENT_VARIETY),
    fetchCommonCodes(farm, CODE_PARENT_WEIGHT),
    fetchCommonCodes(farm, CODE_PARENT_SIZE),
    fetchCommonCodes(farm, CODE_PARENT_GRADE),
  ])
  varietyOptions.value = vars
    .filter(c => String(c.code_cd).length === 8 && !String(c.code_cd).endsWith('00'))
    .map(c => ({ value: c.code_cd, label: c.code_nm || c.code_cd }))
  weightOptions.value = weights.map(c => ({ value: c.code_cd, label: c.code_nm || c.code_cd }))
  sizeOptions.value   = sizes.map(c => ({ value: c.code_cd, label: c.code_nm || c.code_cd }))
  gradeOptions.value  = grades.map(c => ({ value: c.code_cd, label: c.code_nm || c.code_cd }))
}

// ── 원료 로드 ────────────────────────────────────────────────────────
async function loadSources() {
  loading.value = true
  errorMsg.value = ''
  harvestLoadError.value = ''
  rawLoadError.value = ''
  try {
    const farm  = farmCd.value
    const today = todayIso()
    if (isHarvest.value) {
      harvestRows.value = await fetchHarvestRecords(farm, {
        from_date: today.slice(0, 8) + '01',
        to_date: today,
      })
    } else {
      rawRows.value = await fetchRawStock(farm)
    }
  } catch {
    if (isHarvest.value) {
      harvestRows.value = []
      harvestLoadError.value = MSG_HARVEST_LOAD_FAIL
    } else {
      rawRows.value = []
      rawLoadError.value = MSG_RAW_LOAD_FAIL
    }
  } finally {
    loading.value = false
  }
}

// ── 원료 선택 ────────────────────────────────────────────────────────
function isHarvestSelected(workId: string): boolean {
  return Object.prototype.hasOwnProperty.call(harvestUseQtyMap.value, workId)
}

function harvestUseQtyOf(row: HarvestRecord): number {
  const n = Number(harvestUseQtyMap.value[row.work_id] ?? '')
  return Number.isInteger(n) ? n : 0
}

function onToggleHarvest(row: HarvestRecord) {
  if (!isHarvestSelectable(row)) return
  const check = canSelectHarvestRow(row, harvestAnchorRow.value)
  if (!check.ok) {
    if (check.message) errorMsg.value = check.message
    return
  }
  errorMsg.value = ''
  if (isHarvestSelected(row.work_id)) {
    const next = { ...harvestUseQtyMap.value }
    delete next[row.work_id]
    harvestUseQtyMap.value = next
    if (!Object.keys(next).length) varietyCd.value = ''
    return
  }
  harvestUseQtyMap.value = { ...harvestUseQtyMap.value, [row.work_id]: '1' }
  if (row.variety_cd) varietyCd.value = row.variety_cd
}

function setHarvestUseQty(workId: string, value: string) {
  harvestUseQtyMap.value = { ...harvestUseQtyMap.value, [workId]: value }
}

function onSelectRaw(key: string) {
  selectedRawKey.value = key
  const row = rawRows.value.find(r => rawKey(r) === key)
  if (row?.variety_cd) varietyCd.value = row.variety_cd
}

// ── 중량 카드 관리 ───────────────────────────────────────────────────
function addWeightCard(wCd: string) {
  if (usedWeightCds.value.has(wCd)) return
  const opt = weightOptions.value.find(w => w.value === wCd)
  const kg  = opt ? parseWeightFromLabel(opt.label) : 0
  const firstSize = sizeOptions.value[0]?.value ?? ''
  weightCards.value.push({
    weightCd:   wCd,
    weight:     kg,
    sizes:      firstSize ? [{ sizeCd: firstSize, gradeQty: {} }] : [],
    activeSize: firstSize,
  })
}

function removeWeightCard(idx: number) {
  const card = weightCards.value[idx]
  if (!card) return
  const hasData = cardTotal(card) > 0
  if (hasData && !window.confirm(MSG_DELETE_WEIGHT_CONFIRM)) return
  weightCards.value.splice(idx, 1)
}

// ── 과수 탭 관리 ─────────────────────────────────────────────────────
function usedSizeCds(card: WeightCard): Set<string> {
  return new Set(card.sizes.map(s => s.sizeCd))
}
function availableSizes(card: WeightCard): CodeOption[] {
  const used = usedSizeCds(card)
  return sizeOptions.value.filter(s => !used.has(s.value))
}

function addSizeTab(card: WeightCard, sizeCd: string) {
  if (usedSizeCds(card).has(sizeCd)) return
  card.sizes.push({ sizeCd, gradeQty: {} })
  card.activeSize = sizeCd
}

function removeSizeTab(card: WeightCard, sizeCd: string) {
  const tab = card.sizes.find(s => s.sizeCd === sizeCd)
  if (!tab) return
  const hasData = sizeTotal(tab) > 0
  if (hasData && !window.confirm(MSG_DELETE_SIZE_CONFIRM)) return
  const idx = card.sizes.findIndex(s => s.sizeCd === sizeCd)
  card.sizes.splice(idx, 1)
  if (card.activeSize === sizeCd) {
    card.activeSize = card.sizes[0]?.sizeCd ?? ''
  }
}

function sizeLabel(sizeCd: string): string {
  return sizeOptions.value.find(s => s.value === sizeCd)?.label ?? sizeCd
}

function getGradeQty(tab: SizeTab, gradeCd: string): string {
  return tab.gradeQty[gradeCd] ?? ''
}
function setGradeQty(tab: SizeTab, gradeCd: string, v: string) {
  tab.gradeQty = { ...tab.gradeQty, [gradeCd]: v }
}

// ── 중량 선택 모달 대신 inline select ────────────────────────────────
const addWeightCd = ref('')
watch(addWeightCd, (v) => {
  if (v) {
    addWeightCard(v)
    addWeightCd.value = ''
  }
})

const addSizeCdFor = ref<Record<number, string>>({})
watch(addSizeCdFor, (map) => {
  for (const [idxStr, sizeCd] of Object.entries(map)) {
    if (!sizeCd) continue
    const card = weightCards.value[Number(idxStr)]
    if (card) addSizeTab(card, sizeCd)
    addSizeCdFor.value = { ...addSizeCdFor.value, [idxStr]: '' }
  }
}, { deep: true })

// ── 리셋 ─────────────────────────────────────────────────────────────
function resetPostConfirm() {
  postConfirm.value     = false
  lastPrefill.value     = []
  weightCards.value     = []
  juiceQty.value        = ''
  juiceItemCd.value     = ITEM_JUICE_PLAIN
  rawUseQtyMap.value    = {}
  harvestUseQtyMap.value = {}
  selectedRawKey.value  = ''
  errorMsg.value        = ''
}

// ── validation ────────────────────────────────────────────────────────
function validate(): string {
  if (isHarvest.value) {
    const msgHarvest = validateHarvestSelections(harvestRows.value, harvestSelections.value)
    if (msgHarvest) return msgHarvest
  }
  if (!isHarvest.value) {
    const used = buildRawConsumptions()
    if (used.length === 0) return MSG_SELECT_RAW
    if (new Set(used.map((r) => r.harvest_year)).size > 1) return MSG_MIXED_YEAR
    if (new Set(used.map((r) => r.variety_cd)).size > 1) return MSG_MIXED_VARIETY
    for (const row of rawRows.value) {
      const rawStr = String(rawUseQtyMap.value[rawKey(row)] ?? '').trim()
      if (rawStr === '') continue
      const useQty = Number(rawStr)
      if (!Number.isInteger(useQty) || useQty < 0)
        return '사용수량은 0 이상 정수여야 합니다.'
      if (useQty === 0) continue
      if (useQty > (row.available_qty ?? Infinity))
        return `사용수량(${useQty}통)이 잔여(${row.available_qty}통)를 초과합니다.`
    }
  }
  if (isPack.value) {
    if (weightCards.value.length === 0) return MSG_ADD_WEIGHT
    for (const card of weightCards.value) {
      if (card.sizes.length === 0) return MSG_ADD_SIZE
    }
    if (totalPositiveLines.value === 0) return MSG_ENTER_JUICE.replace('배즙', '생산')
  } else {
    if (Number(juiceQty.value) < 1) return MSG_ENTER_JUICE
  }
  return ''
}

// ── lines 빌드 ────────────────────────────────────────────────────────
function buildLines() {
  if (!isPack.value) return []
  const lines: { grade_cd: string; size_cd: string; qty: number; weight: number }[] = []
  for (const card of weightCards.value) {
    for (const tab of card.sizes) {
      for (const [gradeCd, qStr] of Object.entries(tab.gradeQty)) {
        const q = Number(qStr)
        if (q > 0) {
          lines.push({ grade_cd: gradeCd, size_cd: tab.sizeCd, qty: q, weight: card.weight })
        }
      }
    }
  }
  return lines
}

// ── 생산확정 ─────────────────────────────────────────────────────────
async function onConfirm() {
  const msg = validate()
  if (msg) { errorMsg.value = msg; return }
  confirming.value = true
  errorMsg.value   = ''
  try {
    const consumptions = isHarvest.value ? [] : buildRawConsumptions()
    const harvestConsumptions = isHarvest.value
      ? buildHarvestConsumptions(harvestRows.value, harvestSelections.value)
      : []
    const firstRaw = consumptions[0]
    const firstHarvest = harvestRows.value.find(
      (r) => r.work_id === Object.keys(harvestSelections.value)[0],
    )
    const res = await confirmProduction(farmCd.value, {
      prod_type:   prodType.value,
      input_source: inputSource.value,
      variety_cd:  firstRaw?.variety_cd || firstHarvest?.variety_cd || varietyCd.value,
      wh_cd:       firstRaw?.wh_cd || DEFAULT_WH_CD,
      pack_weight: 0,           // 각 line에 weight 포함
      lines:       buildLines(),
      work_ids:    [],
      juice_qty:   isPack.value ? 0 : Number(juiceQty.value),
      juice_item_cd: isPack.value ? undefined : juiceItemCd.value,
      raw_consumptions: consumptions,
      harvest_consumptions: harvestConsumptions,
    })
    lastPrefill.value = res.prefill_lines || []
    postConfirm.value = true
    emit('toast', MSG_CONFIRM_OK)
  } catch (err) {
    const code = err instanceof ApiClientError ? err.errorCode : undefined
    errorMsg.value = mapProductionHarvestError(
      code,
      err instanceof ApiClientError ? err.message : MSG_CONFIRM_FAIL,
    )
    if (code === 'HARVEST_EXCEED' && isHarvest.value) {
      harvestUseQtyMap.value = {}
      void loadSources()
    }
  } finally {
    confirming.value = false
  }
}

function onSaveStock() {
  resetPostConfirm()
  void loadSources()
  emit('toast', '재고에 저장되었습니다.')
}

function onGoSales() {
  if (lastPrefill.value.length) {
    salesPrefill.setFromProduction(
      attachPrefillDisplayNames(lastPrefill.value, {
        variety: varietyOptions.value,
        grade: gradeOptions.value,
        size: sizeOptions.value,
        item: juiceKindOptions,
      }),
    )
  }
  resetPostConfirm()
  emit('goSales')
}

// ── watch ─────────────────────────────────────────────────────────────
watch(prodType, () => {
  inputSource.value = prodType.value === PROD_TYPE_PROCESS ? INPUT_RAW_STOCK : INPUT_HARVEST
  resetPostConfirm()
  void loadSources()
})
watch(inputSource, () => {
  resetPostConfirm()
  void loadSources()
})

onMounted(async () => {
  await loadMasters()
  await loadSources()
})
</script>

<template>
  <div class="pack-prod">

    <!-- Level 2: 생산구분 + 원료 1행 -->
    <OdsCard class="pack-prod__section pack-prod__section--compact">
      <div class="pack-prod__row2">
        <OdsFormField :label="LABEL_PROD_TYPE">
          <OdsSelect v-model="prodType">
            <option v-for="o in prodTypeOptions" :key="o.value" :value="o.value">{{ o.label }}</option>
          </OdsSelect>
        </OdsFormField>
        <OdsFormField :label="LABEL_INPUT_SOURCE">
          <OdsSelect v-model="inputSource">
            <option v-for="o in inputOptions" :key="o.value" :value="o.value">{{ o.label }}</option>
          </OdsSelect>
        </OdsFormField>
      </div>
    </OdsCard>

    <!-- Level 2: 원료 선택 카드 -->
    <OdsCard class="pack-prod__section pack-prod__section--compact">
      <template v-if="isHarvest">
        <p class="pack-prod__card-label">{{ LABEL_HARVEST_RECORD }}</p>
        <div v-if="loading" class="pack-prod__hint">불러오는 중…</div>
        <div v-else-if="harvestLoadError" class="pack-prod__error" role="alert">
          {{ harvestLoadError }}
        </div>
        <div v-else-if="!harvestRows.length" class="pack-prod__hint">
          {{ MSG_HARVEST_EMPTY }}
        </div>
        <!-- 수확기록: 복수 선택 + 행별 사용량 -->
        <div
          v-for="row in harvestRows"
          :key="row.work_id"
          class="pack-prod__harvest-row"
          :class="{
            'pack-prod__harvest-row--on': isHarvestSelected(row.work_id),
            'pack-prod__harvest-row--disabled': !isHarvestSelectable(row),
          }"
        >
          <button
            type="button"
            class="pack-prod__harvest-label"
            :disabled="!isHarvestSelectable(row) && !isHarvestSelected(row.work_id)"
            @click="onToggleHarvest(row)"
          >
            <span class="pack-prod__harvest-identity">{{ formatHarvestRowLabel(row) }}</span>
          </button>
          <template v-if="isHarvestSelected(row.work_id)">
            <span class="pack-prod__harvest-use-label">이번 사용</span>
            <input
              :value="harvestUseQtyMap[row.work_id] ?? ''"
              type="number"
              inputmode="numeric"
              min="1"
              :max="row.remaining_container_qty"
              placeholder="1"
              class="pack-prod__harvest-use-input"
              :aria-label="`${row.variety_nm || row.variety_cd} 이번 사용 상자`"
              @click.stop
              @input="(e) => setHarvestUseQty(row.work_id, (e.target as HTMLInputElement).value)"
            />
            <span class="pack-prod__harvest-use-unit">상자</span>
          </template>
          <template v-else-if="harvestUseQtyOf(row) >= 1">
            <span class="pack-prod__harvest-use-badge">
              사용 {{ harvestUseQtyMap[row.work_id] }}상자
            </span>
          </template>
        </div>
        <p v-if="harvestSummaryText" class="pack-prod__harvest-summary">{{ harvestSummaryText }}</p>
      </template>

      <template v-else>
        <p class="pack-prod__card-label">{{ LABEL_RAW_STOCK }}</p>
        <div v-if="loading" class="pack-prod__hint">불러오는 중…</div>
        <div v-else-if="rawLoadError" class="pack-prod__error" role="alert">
          {{ rawLoadError }}
        </div>
        <div v-else-if="!rawRows.length" class="pack-prod__hint">
          사용 가능한 원물 재고가 없습니다.
        </div>
        <!-- 원물 선택 행: identity · 잔여 · 사용수량 한 행 -->
        <div
          v-for="row in rawRows"
          :key="rawKey(row)"
          class="pack-prod__raw-row"
          :class="{ 'pack-prod__raw-row--on': selectedRawKey === rawKey(row) }"
        >
          <!-- 좌: 선택 버튼 영역 -->
          <button
            type="button"
            class="pack-prod__raw-label"
            @click="onSelectRaw(rawKey(row))"
          >
            <span class="pack-prod__raw-identity">
              {{ row.variety_nm || row.variety_cd }}<template v-if="row.size_nm"> · {{ row.size_nm }}</template> · {{ row.storage_dt }}
            </span>
            <span class="pack-prod__raw-avail">잔여 {{ row.available_qty }}통</span>
          </button>
          <!-- 우: 사용수량 (선택 행=편집 input / 비선택이지만 수량 있으면 읽기 뱃지) -->
          <template v-if="selectedRawKey === rawKey(row)">
            <span class="pack-prod__raw-use-label">사용</span>
            <input
              :value="rawUseQtyMap[rawKey(row)] ?? ''"
              type="number"
              inputmode="numeric"
              min="0"
              :max="row.available_qty"
              placeholder="0"
              class="pack-prod__raw-use-input"
              :aria-label="`${row.variety_nm || row.variety_cd} 사용 통수`"
              @click.stop
              @input="(e) => { rawUseQtyMap[rawKey(row)] = (e.target as HTMLInputElement).value }"
            />
            <span class="pack-prod__raw-use-unit">통</span>
          </template>
          <!-- 비선택 + 실제 사용(1통 이상)만 뱃지 -->
          <template v-else-if="rawUseQtyOf(row) >= 1">
            <span class="pack-prod__raw-use-badge">
              사용 {{ rawUseQtyMap[rawKey(row)] }}통
            </span>
          </template>
          <template v-else>
            <span class="pack-prod__raw-use-ph" aria-hidden="true"></span>
          </template>
        </div>
      </template>
    </OdsCard>

    <!-- Level 2: 생산결과 (PACK N:N:N) -->
    <template v-if="isPack">
      <!-- section 제목 + 포장중량 추가 버튼 (화면에 1개만) -->
      <div class="pack-prod__result-head">
        <span class="pack-prod__section-title">{{ LABEL_PRODUCTION }}</span>
        <select
          v-if="availableWeightOptions.length"
          class="pack-prod__add-weight-select"
          :value="''"
          aria-label="포장중량 추가"
          @change="(e) => { const v = (e.target as HTMLSelectElement).value; if (v) addWeightCard(v); (e.target as HTMLSelectElement).value = '' }"
        >
          <option value="" disabled>{{ LABEL_ADD_WEIGHT }}</option>
          <option v-for="w in availableWeightOptions" :key="w.value" :value="w.value">
            {{ w.label }}
          </option>
        </select>
      </div>

      <!-- Level 3: 포장중량 카드 loop -->
      <OdsCard
        v-for="(card, cIdx) in weightCards"
        :key="card.weightCd"
        class="pack-prod__weight-card"
      >
        <!-- 카드 헤더: 중량명 + 총량(보조) + 삭제(neutral) -->
        <div class="pack-prod__card-head">
          <span class="pack-prod__weight-nm">
            {{ weightOptions.find(w => w.value === card.weightCd)?.label ?? card.weightCd }}
          </span>
          <span class="pack-prod__card-total">
            총 {{ cardTotal(card) }}박스
          </span>
          <button
            type="button"
            class="pack-prod__del-btn"
            :aria-label="`${weightOptions.find(w => w.value === card.weightCd)?.label ?? card.weightCd} 삭제`"
            @click="removeWeightCard(cIdx)"
          >
            <span aria-hidden="true">✕</span>
          </button>
        </div>

        <!-- Level 4: 과수 탭 (상단 4탭보다 작은 크기) -->
        <div class="pack-prod__size-tabs" role="tablist">
          <button
            v-for="tab in card.sizes"
            :key="tab.sizeCd"
            type="button"
            role="tab"
            class="pack-prod__size-tab"
            :class="{ 'pack-prod__size-tab--on': card.activeSize === tab.sizeCd }"
            :aria-selected="card.activeSize === tab.sizeCd"
            @click="card.activeSize = tab.sizeCd"
          >
            {{ sizeLabel(tab.sizeCd) }}<template v-if="sizeTotal(tab) > 0">&thinsp;<span class="pack-prod__size-cnt">{{ sizeTotal(tab) }}</span></template>
          </button>

          <!-- 과수 추가: compact + 버튼 스타일 -->
          <select
            v-if="availableSizes(card).length"
            class="pack-prod__add-size-select"
            :value="''"
            :aria-label="`${weightOptions.find(w => w.value === card.weightCd)?.label ?? card.weightCd} 과수 추가`"
            @change="(e) => { const v = (e.target as HTMLSelectElement).value; if (v) addSizeTab(card, v); (e.target as HTMLSelectElement).value = '' }"
          >
            <option value="" disabled>+</option>
            <option v-for="s in availableSizes(card)" :key="s.value" :value="s.value">
              {{ s.label }}
            </option>
          </select>
        </div>

        <!-- Level 5: 현재 선택 과수의 등급별 입력 ("○○ 생산량" 중복 제목 없음) -->
        <template v-for="tab in card.sizes" :key="tab.sizeCd">
          <div v-show="card.activeSize === tab.sizeCd" class="pack-prod__grade-area">
            <div
              v-for="g in gradeOptions"
              :key="g.value"
              class="pack-prod__grade-row"
            >
              <span class="pack-prod__grade-nm">{{ g.label }}</span>
              <OdsInput
                :model-value="getGradeQty(tab, g.value)"
                :aria-label="`${sizeLabel(tab.sizeCd)} ${g.label}`"
                inputmode="numeric"
                type="number"
                min="0"
                placeholder="0"
                class="pack-prod__grade-input"
                @update:model-value="setGradeQty(tab, g.value, $event)"
              />
              <span class="pack-prod__unit">박스</span>
            </div>

            <!-- 과수 삭제: neutral, 탭이 2개 이상일 때만 -->
            <button
              v-if="card.sizes.length > 1"
              type="button"
              class="pack-prod__del-size-btn"
              @click="removeSizeTab(card, tab.sizeCd)"
            >{{ sizeLabel(tab.sizeCd) }} 삭제</button>
          </div>
        </template>
      </OdsCard>
    </template>

    <!-- 생산결과 (PROCESS) -->
    <OdsCard v-else class="pack-prod__section pack-prod__section--compact">
      <p class="pack-prod__card-label">{{ LABEL_JUICE_KIND }}</p>
      <div class="pack-prod__choice-row" role="group" :aria-label="LABEL_JUICE_KIND">
        <button
          v-for="o in juiceKindOptions"
          :key="o.value"
          type="button"
          class="pack-prod__pick pack-prod__choice"
          :class="{ 'pack-prod__pick--on': juiceItemCd === o.value }"
          @click="juiceItemCd = o.value"
        >{{ o.label }}</button>
      </div>
      <OdsFormField :label="LABEL_JUICE_BOXES">
        <OdsInput v-model="juiceQty" inputmode="numeric" type="number" min="1" />
      </OdsFormField>
    </OdsCard>

    <p v-if="errorMsg" class="pack-prod__error" role="alert">{{ errorMsg }}</p>

    <div class="pack-prod__actions">
      <template v-if="!postConfirm">
        <OdsButton :busy="confirming" @click="onConfirm">{{ LABEL_CONFIRM }}</OdsButton>
      </template>
      <template v-else>
        <OdsButton variant="secondary" @click="onSaveStock">{{ LABEL_SAVE_STOCK }}</OdsButton>
        <OdsButton @click="onGoSales">{{ LABEL_GO_SALES }}</OdsButton>
      </template>
    </div>
  </div>
</template>

<style scoped>
/* ── Level 1: 전체 페이지 컨테이너 ─────────────────────────────────── */
.pack-prod {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-12);
  padding-bottom: var(--ods-space-32);
}

/* ── Level 2: 카드 공통 ─────────────────────────────────────────────── */
.pack-prod__section {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-12);
}
/* 생산구분/원료·PROCESS 등 compact 카드 — padding 소폭 축소 */
.pack-prod__section--compact :deep(.ods-card__body) {
  padding: var(--ods-space-12);
}

/* 생산구분/원료 1행 2열 */
.pack-prod__row2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--ods-space-12);
}

/* 원료 카드 내 라벨 — field label 수준, 중량 카드 제목보다 약하게 */
.pack-prod__card-label {
  margin: 0 0 var(--ods-space-4);
  font: var(--ods-font-form-label, var(--ods-font-footnote));
  color: var(--ods-color-text-secondary);
}

.pack-prod__hint {
  color: var(--ods-color-text-secondary);
  font: var(--ods-font-footnote);
}

/* 수확기록/원물 선택 행 */
.pack-prod__pick {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
  min-height: 44px;
  padding: var(--ods-space-8) var(--ods-space-12);
  border: 1px solid var(--ods-color-border);
  border-radius: var(--ods-radius-card);
  background: var(--ods-color-surface);
  text-align: left;
  font: var(--ods-font-body);
  color: var(--ods-color-text);
  cursor: pointer;
}
.pack-prod__pick--on {
  border-color: var(--ods-color-primary);
  background: var(--ods-color-primary-subtle, #f0f7f4);
}
.pack-prod__choice-row {
  display: flex;
  gap: var(--ods-space-8);
}
.pack-prod__choice {
  flex: 1;
  justify-content: center;
  text-align: center;
}
.pack-prod__pick-meta {
  font: var(--ods-font-footnote);
  color: var(--ods-color-text-secondary);
  white-space: nowrap;
  margin-left: var(--ods-space-8);
}

.pack-prod__harvest-row {
  display: grid;
  grid-template-columns: 1fr auto auto auto;
  align-items: center;
  gap: var(--ods-space-6, 6px);
  min-height: 44px;
  padding: var(--ods-space-8) var(--ods-space-12);
  border: 1px solid var(--ods-color-border);
  border-radius: var(--ods-radius-card);
  background: var(--ods-color-surface);
}
.pack-prod__harvest-row--on {
  border-color: var(--ods-color-primary);
  background: var(--ods-color-primary-subtle, #f0f7f4);
}
.pack-prod__harvest-row--disabled {
  opacity: 0.55;
}
.pack-prod__harvest-label {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  padding: 0;
  border: none;
  background: transparent;
  text-align: left;
  cursor: pointer;
  min-width: 0;
}
.pack-prod__harvest-label:disabled {
  cursor: not-allowed;
}
.pack-prod__harvest-identity {
  font: var(--ods-font-body-2);
  color: var(--ods-color-text);
}
.pack-prod__harvest-use-label,
.pack-prod__harvest-use-unit {
  font: var(--ods-font-footnote);
  color: var(--ods-color-text-secondary);
  white-space: nowrap;
}
.pack-prod__harvest-use-input {
  width: 52px;
  height: 36px;
  padding: 0 var(--ods-space-4);
  border: 1px solid var(--ods-color-border);
  border-radius: var(--ods-radius-button);
  background: var(--ods-color-white);
  font: var(--ods-font-body-2);
  color: var(--ods-color-text);
  text-align: right;
}
.pack-prod__harvest-use-badge {
  grid-column: 2 / 5;
  justify-self: end;
  font: var(--ods-font-footnote);
  font-weight: 600;
  color: var(--ods-color-primary);
  white-space: nowrap;
}
.pack-prod__harvest-summary {
  margin: var(--ods-space-4) 0 0;
  font: var(--ods-font-footnote);
  color: var(--ods-color-text-secondary);
}
/* 투입 수량 (미사용, 하위 호환) */
.pack-prod__raw-qty {
  margin-top: var(--ods-space-4);
}

/* 원물 1행 레이아웃: [identity + 잔여] [사용] [N] [통] */
.pack-prod__raw-row {
  display: grid;
  grid-template-columns: 1fr auto auto auto;
  align-items: center;
  gap: var(--ods-space-6, 6px);
  min-height: 44px;
  padding: var(--ods-space-8) var(--ods-space-12);
  border: 1px solid var(--ods-color-border);
  border-radius: var(--ods-radius-card);
  background: var(--ods-color-surface);
}
.pack-prod__raw-row--on {
  border-color: var(--ods-color-primary);
  background: var(--ods-color-primary-subtle, #f0f7f4);
}
/* 좌: 선택 버튼 */
.pack-prod__raw-label {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  padding: 0;
  border: none;
  background: transparent;
  text-align: left;
  cursor: pointer;
  min-width: 0;
}
.pack-prod__raw-identity {
  font: var(--ods-font-body-2);
  color: var(--ods-color-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.pack-prod__raw-avail {
  font: var(--ods-font-footnote);
  color: var(--ods-color-text-secondary);
}
/* 우: 사용수량 */
.pack-prod__raw-use-label {
  font: var(--ods-font-footnote);
  color: var(--ods-color-text-secondary);
  white-space: nowrap;
}
.pack-prod__raw-use-input {
  width: 52px;
  height: 36px;
  padding: 0 var(--ods-space-4);
  border: 1px solid var(--ods-color-border);
  border-radius: var(--ods-radius-button);
  background: var(--ods-color-white);
  font: var(--ods-font-body-2);
  color: var(--ods-color-text);
  text-align: right;
  -moz-appearance: textfield;
}
.pack-prod__raw-use-input::-webkit-inner-spin-button,
.pack-prod__raw-use-input::-webkit-outer-spin-button {
  -webkit-appearance: none;
  margin: 0;
}
.pack-prod__raw-use-unit {
  font: var(--ods-font-footnote);
  color: var(--ods-color-text-secondary);
  white-space: nowrap;
}
.pack-prod__raw-use-ph {
  display: none;
}
/* 비선택 행의 입력된 수량 읽기 전용 뱃지 */
.pack-prod__raw-use-badge {
  grid-column: 2 / 5;   /* 사용 + input + 통 열을 하나로 합쳐서 우측 정렬 */
  justify-self: end;
  font: var(--ods-font-footnote);
  font-weight: 600;
  color: var(--ods-color-primary);
  white-space: nowrap;
}

/* ── Level 2: 생산결과 섹션 제목 + 포장중량 추가 (1행) ──────────────── */
.pack-prod__result-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ods-space-8);
  padding: 0 var(--ods-space-4);
}
.pack-prod__section-title {
  margin: 0;
  font: var(--ods-font-subheadline);
  font-weight: 700;
  color: var(--ods-color-text);
}

/* 포장중량 추가 — secondary ghost select (primary보다 낮은 우선순위) */
.pack-prod__add-weight-select {
  padding: var(--ods-space-6, 6px) var(--ods-space-12);
  border: 1px solid var(--ods-color-primary);
  border-radius: var(--ods-radius-button);
  background: transparent;
  font: var(--ods-font-body-2);
  color: var(--ods-color-primary);
  cursor: pointer;
  white-space: nowrap;
  max-width: 160px;
}

/* ── Level 3: 포장중량 카드 ─────────────────────────────────────────── */
.pack-prod__weight-card {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-8);
}

/* 카드 헤더: 중량명(bold) + 총량(secondary) + ✕(neutral, 작게) */
.pack-prod__card-head {
  display: flex;
  align-items: center;
  gap: var(--ods-space-8);
  padding-bottom: var(--ods-space-4);
  border-bottom: 1px solid var(--ods-color-border);
}
.pack-prod__weight-nm {
  font: var(--ods-font-body-1, var(--ods-font-body));
  font-weight: 700;
  color: var(--ods-color-text);
}
.pack-prod__card-total {
  flex: 1;
  text-align: right;
  font: var(--ods-font-footnote);
  color: var(--ods-color-text-secondary);
}
/* 삭제 버튼 — neutral/secondary, 빨간색 금지 (확인 시에만 danger) */
.pack-prod__del-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  padding: 0;
  border: 1px solid var(--ods-color-border);
  border-radius: var(--ods-radius-badge);
  background: transparent;
  color: var(--ods-color-text-secondary);
  font-size: 0.75rem;
  line-height: 1;
  cursor: pointer;
  flex-shrink: 0;
}
.pack-prod__del-btn:active {
  color: var(--ods-color-danger, #c53030);
  border-color: var(--ods-color-danger, #c53030);
}

/* ── Level 4: 과수 탭 (상단 4탭보다 작고 카드 내 종속감) ─────────────── */
.pack-prod__size-tabs {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--ods-space-2, 2px);
  border-bottom: 1px solid var(--ods-color-border);
  padding-bottom: 0;
}
.pack-prod__size-tab {
  padding: var(--ods-space-4) var(--ods-space-8);
  border: none;
  border-bottom: 2px solid transparent;
  background: transparent;
  /* 상단 4탭보다 작은 font */
  font-size: 0.8125rem;
  font-weight: 400;
  color: var(--ods-color-text-secondary);
  cursor: pointer;
  margin-bottom: -1px;
  white-space: nowrap;
}
.pack-prod__size-tab--on {
  color: var(--ods-color-primary);
  border-bottom-color: var(--ods-color-primary);
  font-weight: 600;
}
/* 과수 총량 숫자: 탭 텍스트보다 약하게 */
.pack-prod__size-cnt {
  font-size: 0.75rem;
  color: var(--ods-color-text-secondary);
  font-weight: 400;
}
.pack-prod__size-tab--on .pack-prod__size-cnt {
  color: var(--ods-color-primary);
}

/* 과수 추가 "+": compact, select처럼 보이지 않게 */
.pack-prod__add-size-select {
  padding: var(--ods-space-4) var(--ods-space-6, 6px);
  border: 1px dashed var(--ods-color-border);
  border-radius: var(--ods-radius-badge);
  background: transparent;
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--ods-color-text-secondary);
  cursor: pointer;
  appearance: none;
  -webkit-appearance: none;
  width: 32px;
  text-align: center;
  margin-bottom: -1px;
}

/* ── Level 5: 등급별 수량 입력 ──────────────────────────────────────── */
.pack-prod__grade-area {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-4);
  padding-top: var(--ods-space-8);
}
/* 등급 행: 라벨 | 숫자입력(고정폭) | 박스 */
.pack-prod__grade-row {
  display: grid;
  grid-template-columns: 1fr 80px 2rem;
  align-items: center;
  gap: var(--ods-space-8);
  min-height: 40px;
}
.pack-prod__grade-nm {
  font: var(--ods-font-body-2);
  color: var(--ods-color-text);
}
/* 숫자 input — 고정 폭, 우측 정렬 */
.pack-prod__grade-input :deep(input),
.pack-prod__grade-input :deep(.ods-input) {
  text-align: right;
}
.pack-prod__unit {
  font: var(--ods-font-footnote);
  color: var(--ods-color-text-secondary);
  white-space: nowrap;
}

/* 과수 삭제 — neutral 텍스트 액션 */
.pack-prod__del-size-btn {
  align-self: flex-end;
  margin-top: var(--ods-space-4);
  padding: 0;
  border: none;
  background: transparent;
  color: var(--ods-color-text-tertiary, var(--ods-color-text-secondary));
  font: var(--ods-font-footnote);
  cursor: pointer;
  text-decoration: underline;
  text-decoration-style: dotted;
}

/* ── 에러 / 액션 ─────────────────────────────────────────────────────── */
.pack-prod__error {
  margin: 0;
  color: var(--ods-color-danger, #c53030);
  font: var(--ods-font-footnote);
}

/* 생산확정/저장/판매 버튼 영역 */
.pack-prod__actions {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-8);
  padding-top: var(--ods-space-4);
}
</style>
