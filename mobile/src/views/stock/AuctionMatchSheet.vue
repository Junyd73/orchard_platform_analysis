<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import {
  finalizeAuctionShipment,
  getAuctionCandidates,
  getAuctionShipmentDetail,
} from '@/api/auctionShipments'
import iconFarm from '@/assets/ods/common/icon-farm.svg'
import iconChart from '@/assets/ods/pesticide/icon-menu-stats.svg'
import iconReceipt from '@/assets/ods/pesticide/icon-menu-receipt.svg'
import iconStock from '@/assets/ods/pesticide/icon-kpi-stock.svg'
import iconCalendar from '@/assets/ods/scr004/icon-calendar.svg'
import iconDoc from '@/assets/ods/scr004/icon-content.svg'
import iconInfo from '@/assets/ods/scr004/icon-meta.svg'
import OdsButton from '@/components/ods/OdsButton.vue'
import OdsInput from '@/components/ods/OdsInput.vue'
import OdsSelect from '@/components/ods/OdsSelect.vue'
import {
  allowedReasons,
  auctionMatchUserMessage,
  buildFinalizeRequest,
  candidateSpecTitle,
  compareSpecTitle,
  compareSummaryMessage,
  computeSpecDiffs,
  confirmStatusText,
  confirmStatusTone,
  defaultTradeDt,
  discrepancyReady,
  formatDiffQty,
  formatWon,
  hasSpecDiff,
  isSourceFetchError,
  isStatusConflictError,
  isStaleCandidateError,
  MSG_AUCTION_MATCH_EMPTY,
  MSG_AUCTION_MATCH_EMPTY_HINT,
  MSG_AUCTION_MATCH_OK,
  reasonLabel,
  selectionComplete,
  selectedTotals,
  sortAuctionCandidates,
  sortSpecDiffRows,
  sourceUsedLabel,
  specKey,
  sumSpecDiffTotals,
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

type MatchStep = 'fetch' | 'compare' | 'diff' | 'confirm' | 'done'

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
const sortedCandidates = computed(() => sortAuctionCandidates(candidates.value))
const sortedDiffs = computed(() => sortSpecDiffRows(diffs.value))
const mismatchDiffs = computed(() => sortedDiffs.value.filter((row) => row.diff !== 0))
const compareTotals = computed(() => sumSpecDiffTotals(diffs.value))
const compareHasDiff = computed(() => hasSpecDiff(diffs.value))
const compareMessage = computed(() => compareSummaryMessage(diffs.value))
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

function goCompare() {
  if (!canSelectNext.value) return
  submitError.value = ''
  step.value = 'compare'
}

function prepareDiffDrafts() {
  const next: Record<string, DiscrepancyDraft> = {}
  for (const row of diffs.value) {
    if (row.diff === 0) continue
    const key = specKey(row.spec)
    next[key] = drafts.value[key] ?? emptyDraft()
  }
  drafts.value = next
}

function continueFromCompare() {
  if (!canSelectNext.value) return
  submitError.value = ''
  if (compareHasDiff.value) {
    prepareDiffDrafts()
    step.value = 'diff'
    return
  }
  drafts.value = {}
  step.value = 'confirm'
}

function backFromDiff() {
  step.value = 'compare'
}

function backFromConfirm() {
  step.value = compareHasDiff.value ? 'diff' : 'compare'
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
      :class="{ 'is-busy': busy }"
      role="dialog"
      aria-modal="true"
      aria-label="경락매칭"
      data-testid="auction-match-sheet"
    >
      <button type="button" class="auc-sheet__backdrop" aria-label="닫기" :disabled="busy" @click="emit('close')" />
      <div class="auc-sheet__panel">
        <div class="auc-sheet__header">
          <div class="auc-sheet__header-main">
            <span class="auc-sheet__title-ico" aria-hidden="true">
              <img :src="iconChart" alt="" />
            </span>
            <div class="auc-sheet__header-text">
              <p class="auc-sheet__title">경락매칭</p>
              <p
                v-if="detail"
                class="auc-sheet__meta"
                data-testid="auction-match-meta"
              >
                {{ detail.ship_dt }} · {{ detail.market_name }} · {{ detail.corporation_name }}
                · 출하 {{ detail.total_shipped_qty }}박스
              </p>
            </div>
          </div>
          <button type="button" class="auc-sheet__close" aria-label="닫기" :disabled="busy" @click="emit('close')">
            ✕
          </button>
        </div>

        <p v-if="detailLoading" class="auc-sheet__hint">출하 정보를 불러오는 중…</p>
        <p v-else-if="detailError" class="auc-sheet__err" data-testid="auction-match-detail-error">
          {{ detailError }}
        </p>

        <template v-if="detail">
          <template v-if="step !== 'done' && inTransit">
            <div class="auc-sheet__trade-row">
              <label class="auc-sheet__lbl" for="auc-trade-dt">경락일자</label>
              <OdsInput
                id="auc-trade-dt"
                class="auc-sheet__trade-input"
                :model-value="tradeDt"
                type="date"
                variant="form"
                data-testid="auction-match-trade-dt"
                :disabled="busy"
                @update:model-value="onTradeDtChange"
              />
              <OdsButton
                type="button"
                variant="secondary-filled"
                :block="false"
                :busy="fetchBusy"
                :disabled="busy"
                class="auc-sheet__fetch-btn"
                data-testid="auction-match-fetch"
                @click="fetchCandidates"
              >
                경락가 가져오기
              </OdsButton>
            </div>
            <div
              v-if="sourceUsed"
              class="auc-sheet__source-head"
              data-testid="auction-match-source"
            >
              <img class="auc-sheet__source-ico" :src="iconDoc" alt="" aria-hidden="true" />
              <span class="auc-sheet__source-label">{{ sourceUsedLabel(sourceUsed) }}</span>
            </div>
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
            <div
              v-if="sortedCandidates.length"
              class="auc-sheet__cand-frame"
              data-testid="auction-match-candidates"
            >
              <table class="auc-sheet__compare-table auc-sheet__cand-table">
                <colgroup>
                  <col class="auc-sheet__compare-col--no" />
                  <col class="auc-sheet__compare-col--spec" />
                  <col class="auc-sheet__cand-col--qty" />
                  <col class="auc-sheet__cand-col--price" />
                  <col class="auc-sheet__cand-col--amt" />
                </colgroup>
                <thead>
                  <tr>
                    <th scope="col">No.</th>
                    <th scope="col">규격</th>
                    <th scope="col">수량</th>
                    <th scope="col">단가</th>
                    <th scope="col">금액</th>
                  </tr>
                </thead>
                <tbody>
                  <template v-for="(item, idx) in sortedCandidates" :key="item.source_key">
                    <tr
                      class="auc-sheet__cand-row"
                      :class="{ 'auc-sheet__cand-row--on': selectedKeys.includes(item.source_key) }"
                      :data-testid="`auction-cand-${item.source_key}`"
                      :aria-selected="selectedKeys.includes(item.source_key)"
                      tabindex="0"
                      @click="toggleCandidate(item)"
                      @keydown.enter.prevent="toggleCandidate(item)"
                      @keydown.space.prevent="toggleCandidate(item)"
                    >
                      <td class="auc-sheet__compare-no">{{ idx + 1 }}</td>
                      <td class="auc-sheet__compare-spec">
                        {{ candidateSpecTitle(item) }}
                        <span
                          v-if="item.requires_grade_input"
                          class="auc-sheet__cand-grade-hint"
                        > · 등급선택</span>
                      </td>
                      <td class="auc-sheet__compare-num">{{ item.qty }}박스</td>
                      <td class="auc-sheet__compare-num">{{ formatWon(item.unit_price) }}</td>
                      <td class="auc-sheet__compare-num">{{ formatWon(item.amount) }}</td>
                    </tr>
                    <tr
                      v-if="item.requires_grade_input && selectedKeys.includes(item.source_key)"
                      class="auc-sheet__cand-grade-row"
                    >
                      <td colspan="5">
                        <OdsSelect
                          :model-value="gradeByKey[item.source_key] || ''"
                          variant="form"
                          :data-testid="`auction-cand-grade-${item.source_key}`"
                          :disabled="busy"
                          @click.stop
                          @update:model-value="(v: string) => setGrade(item.source_key, v)"
                        >
                          <option value="">등급 선택</option>
                          <option v-for="g in grades" :key="g.grade_cd" :value="g.grade_cd">
                            {{ g.grade_name }}
                          </option>
                        </OdsSelect>
                      </td>
                    </tr>
                  </template>
                </tbody>
              </table>
            </div>
            <p v-if="selectedRows.length" class="auc-sheet__summary" data-testid="auction-match-summary">
              선택 {{ totals.count }}건 · {{ totals.qty }}박스 · {{ formatWon(totals.amount) }}
            </p>
            <OdsButton
              v-if="selectedRows.length"
              type="button"
              :disabled="!canSelectNext || busy"
              data-testid="auction-match-next-diff"
              @click="goCompare"
            >
              수량 확인
            </OdsButton>
          </template>

          <template v-if="step === 'compare'">
            <section class="auc-sheet__compare" aria-label="수량 비교" data-testid="auction-match-compare">
              <div class="auc-sheet__compare-summary">
                <p class="auc-sheet__compare-totals" data-testid="auction-match-compare-totals">
                  보낸수량
                  <strong>{{ compareTotals.totalShipped }}박스</strong>
                  <span class="auc-sheet__compare-sep" aria-hidden="true">|</span>
                  경락수량
                  <strong>{{ compareTotals.totalMatched }}박스</strong>
                </p>
                <p
                  class="auc-sheet__compare-msg"
                  :class="{ 'auc-sheet__compare-msg--warn': compareHasDiff }"
                  data-testid="auction-match-compare-msg"
                >
                  <span
                    v-if="compareHasDiff"
                    class="auc-sheet__compare-warn-mark"
                    aria-hidden="true"
                  >!</span>
                  {{ compareMessage }}
                </p>
              </div>
              <div class="auc-sheet__compare-frame">
                <table class="auc-sheet__compare-table">
                  <colgroup>
                    <col class="auc-sheet__compare-col--no" />
                    <col class="auc-sheet__compare-col--spec" />
                    <col class="auc-sheet__compare-col--qty" />
                    <col class="auc-sheet__compare-col--qty" />
                    <col class="auc-sheet__compare-col--diff" />
                  </colgroup>
                  <thead>
                    <tr>
                      <th scope="col">No.</th>
                      <th scope="col">규격</th>
                      <th scope="col">보낸수량</th>
                      <th scope="col">경락수량</th>
                      <th scope="col">차이</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr
                      v-for="(row, idx) in sortedDiffs"
                      :key="specKey(row.spec)"
                      :data-testid="`auction-compare-row-${specKey(row.spec)}`"
                    >
                      <td class="auc-sheet__compare-no">{{ idx + 1 }}</td>
                      <td class="auc-sheet__compare-spec">{{ compareSpecTitle(row.spec) }}</td>
                      <td class="auc-sheet__compare-num">{{ row.shipped }}박스</td>
                      <td class="auc-sheet__compare-num">{{ row.matched }}박스</td>
                      <td
                        class="auc-sheet__compare-num"
                        :class="{
                          'auc-sheet__compare-diff--neg': row.diff < 0,
                          'auc-sheet__compare-diff--pos': row.diff > 0,
                        }"
                      >
                        {{ formatDiffQty(row.diff) }}
                      </td>
                    </tr>
                  </tbody>
                  <tfoot>
                    <tr data-testid="auction-match-compare-total-row">
                      <td class="auc-sheet__compare-total-label" colspan="2">합계</td>
                      <td class="auc-sheet__compare-num">{{ compareTotals.totalShipped }}박스</td>
                      <td class="auc-sheet__compare-num">{{ compareTotals.totalMatched }}박스</td>
                      <td class="auc-sheet__compare-num">{{ formatDiffQty(compareTotals.totalDiff) }}</td>
                    </tr>
                  </tfoot>
                </table>
              </div>
            </section>
            <div class="auc-sheet__compare-footer">
              <p class="auc-sheet__compare-guide">
                <img class="auc-sheet__compare-guide-ico" :src="iconInfo" alt="" aria-hidden="true" />
                규격별 수량을 확인한 후 다음 단계로 진행하세요.
              </p>
              <div class="auc-sheet__actions">
                <OdsButton
                  type="button"
                  variant="secondary"
                  :block="false"
                  :disabled="busy"
                  data-testid="auction-match-compare-back"
                  @click="step = 'fetch'"
                >
                  이전
                </OdsButton>
                <OdsButton
                  type="button"
                  :block="false"
                  :disabled="busy"
                  data-testid="auction-match-compare-continue"
                  @click="continueFromCompare"
                >
                  확인하고 계속
                </OdsButton>
              </div>
            </div>
          </template>

          <template v-if="step === 'diff'">
            <ul class="auc-sheet__diff-list" data-testid="auction-match-diffs">
              <li v-for="row in mismatchDiffs" :key="specKey(row.spec)" class="auc-sheet__diff">
                <div class="auc-sheet__diff-top">
                  <div class="auc-sheet__diff-info">
                    <p class="auc-sheet__diff-title">{{ compareSpecTitle(row.spec) }}</p>
                    <p class="auc-sheet__cand-meta">
                      보낸 {{ row.shipped }} · 경락 {{ row.matched }} · 차이 {{ formatDiffQty(row.diff) }}
                    </p>
                  </div>
                  <OdsSelect
                    class="auc-sheet__diff-reason"
                    :model-value="drafts[specKey(row.spec)]?.reason || ''"
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
                </div>
                <OdsInput
                  v-if="drafts[specKey(row.spec)]?.reason === 'OTHER' || drafts[specKey(row.spec)]?.reason === 'QTY_ERROR'"
                  class="auc-sheet__diff-remark"
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
              </li>
            </ul>
            <div class="auc-sheet__actions">
              <OdsButton
                type="button"
                variant="secondary"
                :block="false"
                :disabled="busy"
                data-testid="auction-match-diff-back"
                @click="backFromDiff"
              >
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
            <section class="auc-sheet__confirm" aria-label="최종 확인" data-testid="auction-match-confirm">
              <div class="auc-sheet__confirm-summary">
                <div class="auc-sheet__confirm-stat">
                  <img class="auc-sheet__confirm-stat-ico" :src="iconCalendar" alt="" aria-hidden="true" />
                  <div class="auc-sheet__confirm-stat-body">
                    <span class="auc-sheet__confirm-stat-lbl">경락일자</span>
                    <strong class="auc-sheet__confirm-stat-val auc-sheet__confirm-stat-val--accent">{{ tradeDt }}</strong>
                  </div>
                </div>
                <div class="auc-sheet__confirm-stat">
                  <img class="auc-sheet__confirm-stat-ico" :src="iconFarm" alt="" aria-hidden="true" />
                  <div class="auc-sheet__confirm-stat-body">
                    <span class="auc-sheet__confirm-stat-lbl">시장 · 중도매인</span>
                    <strong class="auc-sheet__confirm-stat-val">
                      {{ detail.market_name }} · {{ detail.corporation_name }}
                    </strong>
                  </div>
                </div>
                <div class="auc-sheet__confirm-stat">
                  <img class="auc-sheet__confirm-stat-ico" :src="iconStock" alt="" aria-hidden="true" />
                  <div class="auc-sheet__confirm-stat-body">
                    <span class="auc-sheet__confirm-stat-lbl">선택규격 / 출하수량</span>
                    <strong class="auc-sheet__confirm-stat-val auc-sheet__confirm-stat-val--accent">
                      {{ totals.count }}건 · {{ totals.qty }}박스
                    </strong>
                  </div>
                </div>
              </div>

              <div class="auc-sheet__confirm-revenue" data-testid="auction-match-confirm-revenue">
                <img class="auc-sheet__confirm-revenue-ico" :src="iconReceipt" alt="" aria-hidden="true" />
                <p class="auc-sheet__confirm-revenue-text">
                  예상 매출
                  <strong>{{ formatWon(totals.amount) }}</strong>
                </p>
              </div>

              <div class="auc-sheet__compare-frame auc-sheet__confirm-frame">
                <table class="auc-sheet__compare-table auc-sheet__confirm-table">
                  <colgroup>
                    <col class="auc-sheet__compare-col--no" />
                    <col class="auc-sheet__compare-col--spec" />
                    <col class="auc-sheet__confirm-col--status" />
                  </colgroup>
                  <thead>
                    <tr>
                      <th scope="col">No.</th>
                      <th scope="col">규격</th>
                      <th scope="col">상태 / 비고</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr
                      v-for="(row, idx) in sortedDiffs"
                      :key="specKey(row.spec)"
                      :data-testid="`auction-confirm-row-${specKey(row.spec)}`"
                    >
                      <td class="auc-sheet__compare-no">{{ idx + 1 }}</td>
                      <td class="auc-sheet__compare-spec">{{ compareSpecTitle(row.spec) }}</td>
                      <td
                        class="auc-sheet__confirm-status"
                        :class="`auc-sheet__confirm-status--${confirmStatusTone(row.diff)}`"
                      >
                        {{ confirmStatusText(row, drafts) }}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>

              <p
                class="auc-sheet__confirm-guide"
                data-testid="auction-match-confirm-msg"
              >
                <img class="auc-sheet__compare-guide-ico" :src="iconInfo" alt="" aria-hidden="true" />
                {{ compareMessage }}
              </p>
            </section>
            <div class="auc-sheet__actions auc-sheet__actions--end">
              <OdsButton
                type="button"
                variant="secondary"
                :block="false"
                :disabled="busy"
                data-testid="auction-match-confirm-back"
                @click="backFromConfirm"
              >
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
  max-height: min(92vh, 720px);
  overflow: auto;
  background: var(--ods-color-white);
  border-radius: var(--ods-radius-card) var(--ods-radius-card) 0 0;
  padding: var(--ods-space-16) var(--ods-space-16)
    calc(var(--ods-space-20) + env(safe-area-inset-bottom));
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-16);
}
.auc-sheet__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--ods-space-8);
}
.auc-sheet__header-main {
  display: flex;
  align-items: flex-start;
  gap: var(--ods-space-8);
  min-width: 0;
}
.auc-sheet__title-ico {
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--ods-radius-button);
  background: color-mix(in srgb, var(--ods-color-primary) 12%, var(--ods-color-white));
  color: var(--ods-color-primary);
}
.auc-sheet__title-ico img {
  width: var(--ods-icon-lg);
  height: var(--ods-icon-lg);
}
.auc-sheet__header-text {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-4);
}
.auc-sheet__title {
  margin: 0;
  font: var(--ods-font-title-2);
  color: var(--ods-color-text);
}
.auc-sheet__close {
  flex-shrink: 0;
  padding: var(--ods-space-4);
  background: transparent;
  border: none;
  font-size: 16px;
  color: var(--ods-color-text-secondary);
  cursor: pointer;
}
.auc-sheet__trade-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--ods-space-8);
}
.auc-sheet__lbl {
  margin: 0;
  flex-shrink: 0;
  font: var(--ods-font-card-emphasis);
  color: var(--ods-color-text);
}
.auc-sheet__trade-input {
  flex: 1 1 8.5rem;
  min-width: 0;
}
.auc-sheet__fetch-btn {
  flex: 0 0 auto;
  min-height: var(--ods-button-height-in-card);
  padding-inline: var(--ods-space-12);
  font: var(--ods-font-card-emphasis);
}
.auc-sheet :deep(.auc-sheet__fetch-btn.ods-btn--secondary-filled) {
  background: color-mix(in srgb, var(--ods-color-secondary) 22%, var(--ods-color-white));
  color: var(--ods-color-primary);
  border: 1px solid color-mix(in srgb, var(--ods-color-primary) 28%, transparent);
}
.auc-sheet__source-head {
  display: flex;
  align-items: center;
  gap: var(--ods-space-8);
}
.auc-sheet__source-ico {
  width: var(--ods-icon-lg);
  height: var(--ods-icon-lg);
  flex-shrink: 0;
}
.auc-sheet__source-label {
  font: var(--ods-font-headline);
  color: var(--ods-color-text);
}
.auc-sheet__meta,
.auc-sheet__hint,
.auc-sheet__summary,
.auc-sheet__ok {
  margin: 0;
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
}
.auc-sheet__err {
  margin: 0;
  font: var(--ods-font-caption);
  color: var(--ods-color-danger);
}
.auc-sheet__retry {
  align-self: flex-start;
  padding: 0;
  border: none;
  background: transparent;
  color: var(--ods-color-primary);
  font: var(--ods-font-caption);
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
.auc-sheet__diff-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-8);
}
.auc-sheet__cand-frame {
  min-width: 0;
  margin-inline: calc(var(--ods-space-8) * -1);
  width: calc(100% + var(--ods-space-16));
  border: 1px solid var(--ods-color-border);
  border-radius: var(--ods-radius-button);
  overflow: hidden;
  background: var(--ods-color-white);
}
.auc-sheet__cand-col--qty {
  width: 3.4rem;
}
.auc-sheet__cand-col--price {
  width: 4.25rem;
}
.auc-sheet__cand-col--amt {
  width: 4.75rem;
}
.auc-sheet__cand-row {
  cursor: pointer;
}
.auc-sheet__cand-row:hover td {
  background: color-mix(in srgb, var(--ods-color-primary) 4%, var(--ods-color-white));
}
.auc-sheet__cand-row--on td {
  background: color-mix(in srgb, var(--ods-color-primary) 10%, var(--ods-color-white));
}
.auc-sheet__cand-row--on td:first-child {
  box-shadow: inset 3px 0 0 var(--ods-color-primary);
}
.auc-sheet.is-busy .auc-sheet__cand-row {
  cursor: wait;
  pointer-events: none;
}
.auc-sheet__cand-grade-hint {
  color: var(--ods-color-caution);
  font-weight: 600;
}
.auc-sheet__cand-grade-row td {
  padding: var(--ods-space-8);
  background: color-mix(in srgb, var(--ods-color-primary) 6%, var(--ods-color-white));
  border-bottom: 1px solid var(--ods-color-border);
}
.auc-sheet__diff-title {
  margin: 0;
  font: var(--ods-font-body-2);
  font-weight: 700;
}
.auc-sheet__cand-meta {
  margin: 0;
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
}
.auc-sheet__diff {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-6);
  padding: var(--ods-space-8);
  border-radius: var(--ods-radius-card);
  background: var(--ods-color-surface-muted, #faf8f4);
}
.auc-sheet__diff-top {
  display: flex;
  align-items: center;
  gap: var(--ods-space-8);
  min-width: 0;
}
.auc-sheet__diff-info {
  flex: 1 1 auto;
  min-width: 0;
}
.auc-sheet__diff :deep(.auc-sheet__diff-reason) {
  flex: 0 0 auto;
  width: auto;
  min-width: 5.75rem;
  max-width: 7.25rem;
  height: var(--ods-select-height);
  min-height: var(--ods-select-height);
  max-height: var(--ods-select-height);
  padding: 0 var(--ods-space-8);
  font: var(--ods-font-caption);
  line-height: 1.2;
}
.auc-sheet__compare {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-12);
  min-width: 0;
  margin-inline: calc(var(--ods-space-8) * -1);
  width: calc(100% + var(--ods-space-16));
}
.auc-sheet__compare-summary {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--ods-space-8);
  padding: var(--ods-space-12);
  border-radius: var(--ods-radius-button);
  background: color-mix(in srgb, var(--ods-color-primary) 8%, var(--ods-color-white));
}
.auc-sheet__compare-totals {
  margin: 0;
  font: var(--ods-font-caption);
  color: var(--ods-color-text);
}
.auc-sheet__compare-totals strong {
  font: var(--ods-font-card-emphasis);
  color: var(--ods-color-primary);
}
.auc-sheet__compare-sep {
  margin: 0 var(--ods-space-4);
  color: var(--ods-color-text-secondary);
}
.auc-sheet__compare-msg {
  margin: 0;
  display: inline-flex;
  align-items: flex-start;
  gap: var(--ods-space-4);
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
}
.auc-sheet__compare-msg--warn {
  color: var(--ods-color-caution);
}
.auc-sheet__compare-warn-mark {
  flex-shrink: 0;
  width: 14px;
  height: 14px;
  margin-top: 1px;
  border-radius: var(--ods-radius-badge);
  background: var(--ods-color-caution);
  color: var(--ods-color-white);
  font: 700 10px/14px var(--ods-font-family);
  text-align: center;
}
.auc-sheet__compare-frame {
  width: 100%;
  min-width: 0;
  border: 1px solid var(--ods-color-border);
  border-radius: var(--ods-radius-button);
  overflow: hidden;
  background: var(--ods-color-white);
}
.auc-sheet__compare-table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
  font: var(--ods-font-caption);
}
.auc-sheet__compare-col--no {
  width: 1.75rem;
}
.auc-sheet__compare-col--spec {
  width: auto;
}
.auc-sheet__compare-col--qty {
  width: 3.4rem;
}
.auc-sheet__compare-col--diff {
  width: 1.85rem;
}
.auc-sheet__compare-table th,
.auc-sheet__compare-table td {
  box-sizing: border-box;
  padding: var(--ods-space-8) var(--ods-space-4);
  border-bottom: 1px solid var(--ods-color-border);
  vertical-align: middle;
  line-height: 1.3;
}
.auc-sheet__compare-table thead th {
  background: var(--ods-color-bg-muted);
  color: var(--ods-color-text-secondary);
  font: var(--ods-font-card-emphasis);
  text-align: right;
  white-space: nowrap;
}
.auc-sheet__compare-table thead th:nth-child(1),
.auc-sheet__compare-table thead th:nth-child(2) {
  text-align: left;
}
.auc-sheet__compare-no {
  font: var(--ods-font-caption);
  font-variant-numeric: tabular-nums;
  text-align: center;
  color: var(--ods-color-text-secondary);
}
.auc-sheet__compare-spec {
  font: var(--ods-font-caption);
  font-weight: 500;
  letter-spacing: -0.02em;
  color: var(--ods-color-text);
  text-align: left;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: clip;
}
.auc-sheet__compare-num {
  font: var(--ods-font-caption);
  font-variant-numeric: tabular-nums;
  text-align: right;
  white-space: nowrap;
  color: var(--ods-color-text);
}
.auc-sheet__compare-diff--neg {
  color: var(--ods-color-danger);
  font-weight: 600;
}
.auc-sheet__compare-diff--pos {
  color: var(--ods-color-ai);
  font-weight: 600;
}
.auc-sheet__compare-table tfoot td {
  background: color-mix(in srgb, var(--ods-color-primary) 10%, var(--ods-color-white));
  font: var(--ods-font-card-emphasis);
  border-bottom: none;
}
.auc-sheet__compare-total-label {
  text-align: left;
  padding-left: var(--ods-space-8);
}
.auc-sheet__compare-footer {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-12);
  padding-top: var(--ods-space-4);
}
.auc-sheet__compare-guide {
  margin: 0;
  display: flex;
  align-items: flex-start;
  gap: var(--ods-space-4);
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
}
.auc-sheet__compare-guide-ico {
  width: var(--ods-icon-sm);
  height: var(--ods-icon-sm);
  flex-shrink: 0;
  margin-top: 1px;
  opacity: 0.75;
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
.auc-sheet__actions--end {
  justify-content: flex-end;
  padding-bottom: var(--ods-space-8);
}
.auc-sheet__confirm {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-12);
  min-width: 0;
  margin-inline: calc(var(--ods-space-8) * -1);
  width: calc(100% + var(--ods-space-16));
}
.auc-sheet__confirm-summary {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--ods-space-8);
  padding: var(--ods-space-12);
  border-radius: var(--ods-radius-button);
  background: color-mix(in srgb, var(--ods-color-primary) 8%, var(--ods-color-white));
}
.auc-sheet__confirm-stat {
  display: flex;
  align-items: flex-start;
  gap: var(--ods-space-4);
  min-width: 0;
}
.auc-sheet__confirm-stat + .auc-sheet__confirm-stat {
  padding-left: var(--ods-space-8);
  border-left: 1px solid color-mix(in srgb, var(--ods-color-primary) 18%, transparent);
}
.auc-sheet__confirm-stat-ico {
  width: var(--ods-icon-sm);
  height: var(--ods-icon-sm);
  flex-shrink: 0;
  margin-top: 2px;
  opacity: 0.85;
}
.auc-sheet__confirm-stat-body {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.auc-sheet__confirm-stat-lbl {
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
}
.auc-sheet__confirm-stat-val {
  margin: 0;
  font: var(--ods-font-caption);
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--ods-color-text);
  word-break: keep-all;
  overflow-wrap: anywhere;
}
.auc-sheet__confirm-stat-val--accent {
  color: var(--ods-color-primary);
  font-variant-numeric: tabular-nums;
}
.auc-sheet__confirm-revenue {
  display: flex;
  align-items: center;
  gap: var(--ods-space-8);
  padding: var(--ods-space-12);
  border-radius: var(--ods-radius-button);
  background: color-mix(in srgb, var(--ods-color-primary) 10%, var(--ods-color-white));
}
.auc-sheet__confirm-revenue-ico {
  width: var(--ods-icon-md, var(--ods-icon-sm));
  height: var(--ods-icon-md, var(--ods-icon-sm));
  flex-shrink: 0;
}
.auc-sheet__confirm-revenue-text {
  margin: 0;
  font: var(--ods-font-body-2);
  color: var(--ods-color-text);
}
.auc-sheet__confirm-revenue-text strong {
  margin-left: var(--ods-space-4);
  font: var(--ods-font-headline);
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  color: var(--ods-color-primary);
}
.auc-sheet__confirm-col--status {
  width: 7.25rem;
}
.auc-sheet__confirm-table thead th:nth-child(3) {
  text-align: left;
}
.auc-sheet__confirm-status {
  font: var(--ods-font-caption);
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.02em;
  text-align: left;
  white-space: nowrap;
}
.auc-sheet__confirm-status--ok {
  color: var(--ods-color-primary);
}
.auc-sheet__confirm-status--neg {
  color: var(--ods-color-danger);
}
.auc-sheet__confirm-status--pos {
  color: var(--ods-color-ai);
}
.auc-sheet__confirm-guide {
  margin: 0;
  display: flex;
  align-items: flex-start;
  gap: var(--ods-space-4);
  padding: var(--ods-space-8) var(--ods-space-12);
  border-radius: var(--ods-radius-button);
  background: color-mix(in srgb, var(--ods-color-primary) 8%, var(--ods-color-white));
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
}
@media (max-width: 360px) {
  .auc-sheet__confirm-summary {
    grid-template-columns: 1fr;
  }
  .auc-sheet__confirm-stat + .auc-sheet__confirm-stat {
    padding-left: 0;
    border-left: none;
    padding-top: var(--ods-space-8);
    border-top: 1px solid color-mix(in srgb, var(--ods-color-primary) 18%, transparent);
  }
}
.auc-sheet__done {
  margin: 0;
  font: var(--ods-font-headline);
  font-weight: 700;
}
</style>
