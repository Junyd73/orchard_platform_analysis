<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import {
  finalizeAuctionShipment,
  getAuctionCandidates,
  getAuctionShipmentDetail,
} from '@/api/auctionShipments'
import OdsButton from '@/components/ods/OdsButton.vue'
import OdsInput from '@/components/ods/OdsInput.vue'
import OdsSelect from '@/components/ods/OdsSelect.vue'
import {
  allowedReasons,
  auctionMatchUserMessage,
  buildFinalizeRequest,
  computeSpecDiffs,
  defaultTradeDt,
  discrepancyReady,
  formatWon,
  isSourceFetchError,
  isStatusConflictError,
  isStaleCandidateError,
  MSG_AUCTION_MATCH_EMPTY,
  MSG_AUCTION_MATCH_EMPTY_HINT,
  MSG_AUCTION_MATCH_OK,
  reasonLabel,
  selectionComplete,
  selectedTotals,
  sourceUsedLabel,
  specKey,
  specTitle,
  uniqueSpecGrades,
  type DiscrepancyDraft,
} from '@/views/stock/auctionMatchModel'
import {
  AUCTION_STATUS_COMPLETED,
  AUCTION_STATUS_IN_TRANSIT,
} from '@/views/stock/auctionShipModel'
import type {
  AuctionCandidate,
  AuctionDiscrepancyReason,
  AuctionFinalizeResponse,
  AuctionShipmentDetail,
} from '@/types/auctionShipment'

const props = defineProps<{
  open: boolean
  farmCd: string
  shipmentId: string
}>()

const emit = defineEmits<{
  close: []
  success: []
  statusConflict: []
}>()

type MatchStep = 'fetch' | 'diff' | 'confirm' | 'done'

const detail = ref<AuctionShipmentDetail | null>(null)
const detailError = ref('')
const detailLoading = ref(false)
const tradeDt = ref('')
const sourceUsed = ref('')
const candidates = ref<AuctionCandidate[]>([])
const fetched = ref(false)
const fetchBusy = ref(false)
const fetchError = ref('')
const sourceError = ref('')
const selectedKeys = ref<string[]>([])
const gradeByKey = ref<Record<string, string>>({})
const drafts = ref<Record<string, DiscrepancyDraft>>({})
const step = ref<MatchStep>('fetch')
const submitBusy = ref(false)
const submitError = ref('')
const result = ref<AuctionFinalizeResponse | null>(null)
let fetchSeq = 0

const selectedRows = computed(() =>
  selectedKeys.value
    .map((key) => {
      const candidate = candidates.value.find((item) => item.source_key === key)
      if (!candidate) return null
      return { candidate, userGradeCd: gradeByKey.value[key] || null }
    })
    .filter((row): row is { candidate: AuctionCandidate; userGradeCd: string | null } => row != null),
)

const totals = computed(() => selectedTotals(selectedRows.value.map((row) => row.candidate)))
const diffs = computed(() => computeSpecDiffs(detail.value?.specs ?? [], selectedRows.value))
const grades = computed(() => uniqueSpecGrades(detail.value?.specs ?? []))
const discCheck = computed(() => discrepancyReady(diffs.value, drafts.value))
const canSelectNext = computed(() => selectionComplete(selectedRows.value))
const inTransit = computed(() => detail.value?.status === AUCTION_STATUS_IN_TRANSIT)
const busy = computed(() => detailLoading.value || fetchBusy.value || submitBusy.value)

function emptyDraft(): DiscrepancyDraft {
  return { reason: '', remark: '', returnConfirmed: false }
}

function resetLocal(keepDate = false) {
  sourceUsed.value = ''
  candidates.value = []
  fetched.value = false
  fetchError.value = ''
  sourceError.value = ''
  selectedKeys.value = []
  gradeByKey.value = {}
  drafts.value = {}
  submitError.value = ''
  result.value = null
  if (!keepDate) tradeDt.value = ''
  if (detail.value?.status === AUCTION_STATUS_COMPLETED) {
    step.value = 'done'
  } else {
    step.value = 'fetch'
  }
}

async function loadDetail() {
  if (!props.farmCd || !props.shipmentId) return
  detailLoading.value = true
  detailError.value = ''
  try {
    const data = await getAuctionShipmentDetail(props.farmCd, props.shipmentId)
    detail.value = data
    tradeDt.value = defaultTradeDt(data.ship_dt)
    if (data.status === AUCTION_STATUS_COMPLETED) {
      step.value = 'done'
    }
  } catch (err) {
    detail.value = null
    detailError.value = auctionMatchUserMessage(err)
  } finally {
    detailLoading.value = false
  }
}

async function fetchCandidates() {
  if (!props.farmCd || !props.shipmentId || !inTransit.value) return
  if (!/^\d{4}-\d{2}-\d{2}$/.test(tradeDt.value)) {
    fetchError.value = '경락일자를 확인해 주세요.'
    return
  }
  const seq = ++fetchSeq
  fetchBusy.value = true
  fetchError.value = ''
  sourceError.value = ''
  selectedKeys.value = []
  gradeByKey.value = {}
  drafts.value = {}
  step.value = 'fetch'
  try {
    const page = await getAuctionCandidates(props.farmCd, props.shipmentId, tradeDt.value)
    if (seq !== fetchSeq) return
    candidates.value = page.items ?? []
    sourceUsed.value = page.source_used || ''
    fetched.value = true
  } catch (err) {
    if (seq !== fetchSeq) return
    candidates.value = []
    fetched.value = false
    if (isSourceFetchError(err)) {
      sourceError.value = auctionMatchUserMessage(err)
    } else {
      fetchError.value = auctionMatchUserMessage(err)
    }
  } finally {
    if (seq === fetchSeq) fetchBusy.value = false
  }
}

function onTradeDtChange(value: string) {
  if (value === tradeDt.value) return
  tradeDt.value = value
  selectedKeys.value = []
  gradeByKey.value = {}
  drafts.value = {}
  candidates.value = []
  fetched.value = false
  sourceUsed.value = ''
  fetchError.value = ''
  sourceError.value = ''
  submitError.value = ''
  step.value = 'fetch'
  if (inTransit.value) void fetchCandidates()
}

function toggleCandidate(item: AuctionCandidate) {
  if (busy.value || !inTransit.value) return
  const key = item.source_key
  if (selectedKeys.value.includes(key)) {
    selectedKeys.value = selectedKeys.value.filter((k) => k !== key)
    const next = { ...gradeByKey.value }
    delete next[key]
    gradeByKey.value = next
    return
  }
  selectedKeys.value = [...selectedKeys.value, key]
  if (item.requires_grade_input && grades.value.length === 1) {
    gradeByKey.value = { ...gradeByKey.value, [key]: grades.value[0].grade_cd }
  }
}

function setGrade(key: string, gradeCd: string) {
  gradeByKey.value = { ...gradeByKey.value, [key]: gradeCd }
}

function ensureDraft(key: string): DiscrepancyDraft {
  if (!drafts.value[key]) {
    drafts.value = { ...drafts.value, [key]: emptyDraft() }
  }
  return drafts.value[key]
}

function patchDraft(key: string, patch: Partial<DiscrepancyDraft>) {
  drafts.value = { ...drafts.value, [key]: { ...ensureDraft(key), ...patch } }
}

function setReason(key: string, reason: string) {
  patchDraft(key, {
    reason: reason as AuctionDiscrepancyReason | '',
    returnConfirmed: reason === 'RETURN' ? ensureDraft(key).returnConfirmed : false,
  })
}

function setRemark(key: string, remark: string) {
  patchDraft(key, { remark })
}

function setReturnConfirmed(key: string, confirmed: boolean) {
  patchDraft(key, { returnConfirmed: confirmed })
}

function goDiff() {
  if (!canSelectNext.value) return
  submitError.value = ''
  const next: Record<string, DiscrepancyDraft> = {}
  for (const row of diffs.value) {
    if (row.diff === 0) continue
    const key = specKey(row.spec)
    next[key] = drafts.value[key] ?? emptyDraft()
  }
  drafts.value = next
  step.value = 'diff'
}

function goConfirm() {
  if (!discCheck.value.ok) {
    submitError.value = discCheck.value.message || ''
    return
  }
  submitError.value = ''
  step.value = 'confirm'
}

async function submitFinalize() {
  if (!detail.value || submitBusy.value || !canSelectNext.value || !discCheck.value.ok) return
  submitBusy.value = true
  submitError.value = ''
  try {
    const payload = buildFinalizeRequest({
      tradeDt: tradeDt.value,
      selected: selectedRows.value,
      diffs: diffs.value,
      drafts: drafts.value,
    })
    result.value = await finalizeAuctionShipment(props.farmCd, props.shipmentId, payload)
    detail.value = await getAuctionShipmentDetail(props.farmCd, props.shipmentId)
    selectedKeys.value = []
    gradeByKey.value = {}
    drafts.value = {}
    candidates.value = []
    fetched.value = false
    step.value = 'done'
    emit('success')
  } catch (err) {
    submitError.value = auctionMatchUserMessage(err)
    if (isStaleCandidateError(err)) {
      selectedKeys.value = []
      gradeByKey.value = {}
      drafts.value = {}
      candidates.value = []
      fetched.value = false
      sourceUsed.value = ''
      step.value = 'fetch'
      return
    }
    if (isStatusConflictError(err)) {
      emit('statusConflict')
    }
  } finally {
    submitBusy.value = false
  }
}

watch(
  () => [props.open, props.farmCd, props.shipmentId] as const,
  ([isOpen]) => {
    if (!isOpen || !props.farmCd || !props.shipmentId) {
      detail.value = null
      resetLocal()
      return
    }
    resetLocal()
    void (async () => {
      await loadDetail()
      if (detail.value?.status === AUCTION_STATUS_IN_TRANSIT) {
        await fetchCandidates()
      }
    })()
  },
  { immediate: true },
)
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="auc-sheet"
      role="dialog"
      aria-modal="true"
      aria-label="경락매칭"
      data-testid="auction-match-sheet"
    >
      <button type="button" class="auc-sheet__backdrop" aria-label="닫기" :disabled="busy" @click="emit('close')" />
      <div class="auc-sheet__panel">
        <div class="auc-sheet__header">
          <p class="auc-sheet__title">경락매칭</p>
          <button type="button" class="auc-sheet__close" aria-label="닫기" :disabled="busy" @click="emit('close')">
            ✕
          </button>
        </div>

        <p v-if="detailLoading" class="auc-sheet__hint">출하 정보를 불러오는 중…</p>
        <p v-else-if="detailError" class="auc-sheet__err" data-testid="auction-match-detail-error">
          {{ detailError }}
        </p>

        <template v-if="detail">
          <p class="auc-sheet__meta" data-testid="auction-match-meta">
            {{ detail.ship_dt }} · {{ detail.market_name }} · {{ detail.corporation_name }}
            · 출하 {{ detail.total_shipped_qty }}박스
          </p>

          <template v-if="step !== 'done' && inTransit">
            <div class="auc-sheet__field">
              <label class="auc-sheet__lbl" for="auc-trade-dt">경락일자</label>
              <OdsInput
                id="auc-trade-dt"
                :model-value="tradeDt"
                type="date"
                variant="form"
                data-testid="auction-match-trade-dt"
                :disabled="busy"
                @update:model-value="onTradeDtChange"
              />
            </div>
            <OdsButton
              type="button"
              variant="secondary"
              :busy="fetchBusy"
              :disabled="busy"
              data-testid="auction-match-fetch"
              @click="fetchCandidates"
            >
              경락가 가져오기
            </OdsButton>
            <p v-if="sourceUsed" class="auc-sheet__hint" data-testid="auction-match-source">
              {{ sourceUsedLabel(sourceUsed) }}
            </p>
            <p v-if="sourceError" class="auc-sheet__err" data-testid="auction-match-source-error">
              {{ sourceError }}
            </p>
            <button
              v-if="sourceError"
              type="button"
              class="auc-sheet__retry"
              data-testid="auction-match-retry"
              :disabled="busy"
              @click="fetchCandidates"
            >
              다시 시도
            </button>
            <p v-if="fetchError" class="auc-sheet__err">{{ fetchError }}</p>
          </template>

          <template v-if="step === 'fetch' && inTransit">
            <p
              v-if="fetched && !candidates.length && !sourceError"
              class="auc-sheet__empty"
              data-testid="auction-match-empty"
            >
              {{ MSG_AUCTION_MATCH_EMPTY }}
              <span class="auc-sheet__hint">{{ MSG_AUCTION_MATCH_EMPTY_HINT }}</span>
            </p>
            <ul v-if="candidates.length" class="auc-sheet__cand-list" data-testid="auction-match-candidates">
              <li
                v-for="item in candidates"
                :key="item.source_key"
                class="auc-sheet__cand"
                :class="{ 'auc-sheet__cand--on': selectedKeys.includes(item.source_key) }"
              >
                <button
                  type="button"
                  class="auc-sheet__cand-btn"
                  :data-testid="`auction-cand-${item.source_key}`"
                  :disabled="busy"
                  @click="toggleCandidate(item)"
                >
                  <span class="auc-sheet__cand-name">
                    {{ item.variety_name || '경락' }}
                    · {{ item.qty }}박스
                    · {{ formatWon(item.unit_price) }}
                  </span>
                  <span class="auc-sheet__cand-meta">
                    <template v-if="item.requires_grade_input">등급 선택 필요</template>
                    <template v-else>{{ item.grade_name || '등급' }}</template>
                    <template v-if="item.size_name"> · {{ item.size_name }}</template>
                    <template v-if="item.spec_kg"> · {{ item.spec_kg }}kg</template>
                    <template v-if="item.amount"> · {{ formatWon(item.amount) }}</template>
                    <template v-if="item.auction_time"> · {{ item.auction_time }}</template>
                  </span>
                </button>
                <OdsSelect
                  v-if="item.requires_grade_input && selectedKeys.includes(item.source_key)"
                  :model-value="gradeByKey[item.source_key] || ''"
                  variant="form"
                  :data-testid="`auction-cand-grade-${item.source_key}`"
                  :disabled="busy"
                  @update:model-value="(v: string) => setGrade(item.source_key, v)"
                >
                  <option value="">등급 선택</option>
                  <option v-for="g in grades" :key="g.grade_cd" :value="g.grade_cd">
                    {{ g.grade_name }}
                  </option>
                </OdsSelect>
              </li>
            </ul>
            <p v-if="selectedRows.length" class="auc-sheet__summary" data-testid="auction-match-summary">
              선택 {{ totals.count }}건 · {{ totals.qty }}박스 · {{ formatWon(totals.amount) }}
            </p>
            <OdsButton
              v-if="selectedRows.length"
              type="button"
              :disabled="!canSelectNext || busy"
              data-testid="auction-match-next-diff"
              @click="goDiff"
            >
              수량 확인
            </OdsButton>
          </template>

          <template v-if="step === 'diff'">
            <ul class="auc-sheet__diff-list" data-testid="auction-match-diffs">
              <li v-for="row in diffs" :key="specKey(row.spec)" class="auc-sheet__diff">
                <p class="auc-sheet__diff-title">{{ specTitle(row.spec) }}</p>
                <p class="auc-sheet__cand-meta">
                  출하 {{ row.shipped }} · 경락 {{ row.matched }} ·
                  <template v-if="row.diff === 0">정상</template>
                  <template v-else>차이 {{ row.diff > 0 ? '+' : '' }}{{ row.diff }}</template>
                </p>
                <template v-if="row.diff !== 0">
                  <OdsSelect
                    :model-value="drafts[specKey(row.spec)]?.reason || ''"
                    variant="form"
                    :data-testid="`auction-diff-reason-${specKey(row.spec)}`"
                    :disabled="busy"
                    @update:model-value="(v: string) => setReason(specKey(row.spec), v)"
                  >
                    <option value="">처리 유형</option>
                    <option
                      v-for="reason in allowedReasons(row.diff)"
                      :key="reason"
                      :value="reason"
                    >
                      {{ reasonLabel(reason) }}
                    </option>
                  </OdsSelect>
                  <OdsInput
                    v-if="drafts[specKey(row.spec)]?.reason === 'OTHER' || drafts[specKey(row.spec)]?.reason === 'QTY_ERROR'"
                    :model-value="drafts[specKey(row.spec)]?.remark || ''"
                    variant="form"
                    :placeholder="drafts[specKey(row.spec)]?.reason === 'OTHER' ? '비고 (필수)' : '비고 (선택)'"
                    :data-testid="`auction-diff-remark-${specKey(row.spec)}`"
                    @update:model-value="(v: string) => setRemark(specKey(row.spec), v)"
                  />
                  <label
                    v-if="drafts[specKey(row.spec)]?.reason === 'RETURN'"
                    class="auc-sheet__check"
                    data-testid="auction-return-confirm"
                  >
                    <input
                      type="checkbox"
                      :checked="Boolean(drafts[specKey(row.spec)]?.returnConfirmed)"
                      :disabled="busy"
                      @change="(e) => setReturnConfirmed(
                        specKey(row.spec),
                        (e.target as HTMLInputElement).checked,
                      )"
                    />
                    반품 {{ Math.abs(row.diff) }}박스를 재고에 다시 반영합니다.
                  </label>
                </template>
              </li>
            </ul>
            <div class="auc-sheet__actions">
              <OdsButton type="button" variant="secondary" :block="false" :disabled="busy" @click="step = 'fetch'">
                이전
              </OdsButton>
              <OdsButton
                type="button"
                :block="false"
                :disabled="!discCheck.ok || busy"
                data-testid="auction-match-next-confirm"
                @click="goConfirm"
              >
                최종 확인
              </OdsButton>
            </div>
          </template>

          <template v-if="step === 'confirm'">
            <ul class="auc-sheet__confirm" data-testid="auction-match-confirm">
              <li>경락일자 {{ tradeDt }}</li>
              <li>{{ detail.market_name }} · {{ detail.corporation_name }}</li>
              <li>선택 {{ totals.count }}건 · {{ totals.qty }}박스</li>
              <li>예상 매출 {{ formatWon(totals.amount) }}</li>
              <li v-for="row in diffs" :key="specKey(row.spec)">
                {{ specTitle(row.spec) }}
                <template v-if="row.diff === 0">정상</template>
                <template v-else>
                  차이 {{ row.diff > 0 ? '+' : '' }}{{ row.diff }}
                  · {{ reasonLabel((drafts[specKey(row.spec)]?.reason || 'QTY_ERROR') as AuctionDiscrepancyReason) }}
                </template>
              </li>
            </ul>
            <div class="auc-sheet__actions">
              <OdsButton type="button" variant="secondary" :block="false" :disabled="busy" @click="step = 'diff'">
                이전
              </OdsButton>
              <OdsButton
                type="button"
                :block="false"
                :busy="submitBusy"
                :disabled="busy"
                data-testid="auction-match-submit"
                @click="submitFinalize"
              >
                경락매칭 완료
              </OdsButton>
            </div>
          </template>

          <template v-if="step === 'done'">
            <p class="auc-sheet__done" data-testid="auction-match-done">판매완료</p>
            <p class="auc-sheet__hint">
              경락일자 {{ result?.match_trade_dt || detail.match_trade_dt || tradeDt }}
            </p>
            <p class="auc-sheet__hint">
              판매수량 {{ result?.total_sales_qty ?? detail.total_shipped_qty }}박스
              · 매출 {{ formatWon(result?.gross_sales_amount ?? detail.gross_sales_amount ?? 0) }}
            </p>
            <OdsButton type="button" data-testid="auction-match-done-close" @click="emit('close')">
              확인
            </OdsButton>
          </template>
        </template>

        <p v-if="submitError" class="auc-sheet__err" data-testid="auction-match-error">{{ submitError }}</p>
        <p v-if="step === 'done' && !result" class="auc-sheet__ok">{{ MSG_AUCTION_MATCH_OK }}</p>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.auc-sheet {
  position: fixed;
  inset: 0;
  z-index: 60;
  display: flex;
  align-items: flex-end;
  justify-content: center;
}
.auc-sheet__backdrop {
  position: absolute;
  inset: 0;
  border: none;
  background: color-mix(in srgb, black 45%, transparent);
  cursor: pointer;
}
.auc-sheet__panel {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: var(--ods-page-content-max);
  max-height: min(88vh, 640px);
  overflow: auto;
  background: var(--ods-color-white);
  border-radius: var(--ods-radius-card) var(--ods-radius-card) 0 0;
  padding: var(--ods-space-16) var(--ods-space-16)
    calc(var(--ods-space-16) + env(safe-area-inset-bottom));
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-12);
}
.auc-sheet__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ods-space-8);
}
.auc-sheet__title {
  margin: 0;
  font: var(--ods-font-headline);
  font-weight: 700;
}
.auc-sheet__close {
  padding: var(--ods-space-4);
  background: transparent;
  border: none;
  font-size: 16px;
  color: var(--ods-color-text-secondary);
  cursor: pointer;
}
.auc-sheet__field {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-4);
}
.auc-sheet__lbl {
  margin: 0;
  font: var(--ods-font-form-label, var(--ods-font-body-2));
  font-weight: 700;
}
.auc-sheet__meta,
.auc-sheet__hint,
.auc-sheet__summary,
.auc-sheet__ok {
  margin: 0;
  font: var(--ods-font-footnote);
  color: var(--ods-color-text-secondary);
}
.auc-sheet__err {
  margin: 0;
  font: var(--ods-font-footnote);
  color: var(--ods-color-danger);
}
.auc-sheet__retry {
  align-self: flex-start;
  padding: 0;
  border: none;
  background: transparent;
  color: var(--ods-color-primary);
  font: var(--ods-font-footnote);
  cursor: pointer;
  text-decoration: underline;
}
.auc-sheet__empty {
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-4);
  font: var(--ods-font-body-2);
}
.auc-sheet__cand-list,
.auc-sheet__diff-list,
.auc-sheet__confirm {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-8);
}
.auc-sheet__cand {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-6);
  padding: var(--ods-space-8);
  border-radius: var(--ods-radius-card);
  background: var(--ods-color-surface-muted, #faf8f4);
}
.auc-sheet__cand--on {
  outline: 2px solid var(--ods-color-primary);
}
.auc-sheet__cand-btn {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--ods-space-2);
  width: 100%;
  padding: 0;
  border: none;
  background: transparent;
  text-align: left;
  cursor: pointer;
}
.auc-sheet__cand-name,
.auc-sheet__diff-title {
  margin: 0;
  font: var(--ods-font-body-2);
  font-weight: 700;
}
.auc-sheet__cand-meta {
  margin: 0;
  font: var(--ods-font-footnote);
  color: var(--ods-color-text-secondary);
}
.auc-sheet__diff {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-6);
}
.auc-sheet__check {
  display: flex;
  align-items: flex-start;
  gap: var(--ods-space-8);
  font: var(--ods-font-footnote);
}
.auc-sheet__actions {
  display: flex;
  gap: var(--ods-space-8);
}
.auc-sheet__done {
  margin: 0;
  font: var(--ods-font-headline);
  font-weight: 700;
}
</style>
