<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { ApiClientError } from '@/api/client'
import {
  confirmObservationAiCandidate,
  fetchObservationAiAnalysis,
  fetchObservationPsis,
  fetchObservationSmartSprayGuide,
  requestObservationAiAnalysis,
  requestObservationPsis,
} from '@/api/observationAi'
import { fetchObservationPhotos } from '@/api/observationPhotos'
import OdsButton from '@/components/ods/OdsButton.vue'
import {
  categoryLabel,
  formatConfidence,
  matchTypeLabel,
  messageForAiErrorCode,
  urgencyLabel,
} from '@/shared/aiErrorMessages'
import { OBS_AI_PHOTO_MAX_COUNT } from '@/composables/constants/app'
import {
  aiHint,
  aiLabel,
  guideUiPhaseFromStatus,
  type GuideUiPhase,
} from '@/views/observation/scr004DetailUi'
import type {
  ObservationAiAnalysisResponse,
  ObservationAiCandidate,
  ObservationPsisResponse,
  ObservationSmartSprayGuideResponse,
} from '@/types/observation'

export type AiPanelPhase =
  | 'idle'
  | 'loading'
  | 'analyzing'
  | 'success'
  | 'error'

export type ConfirmPhase = 'idle' | 'confirming' | 'confirmed' | 'error'
export type PsisPhase = 'not_ready' | 'loading' | 'success' | 'empty' | 'error'

const props = withDefaults(
  defineProps<{
    farmCd: string
    obsId: string
    photoIds?: string[]
    /** PSIS 조회용 작물명 (PC cb_crop 대응) */
    cropName?: string
  }>(),
  { cropName: '배' },
)

const emit = defineEmits<{
  updated: [result: ObservationAiAnalysisResponse]
  confirmed: [
    payload: {
      analysis_id: string
      candidate_seq: number
      confirmed_name: string
      ai_status: string
    },
  ]
  psisUpdated: [result: ObservationPsisResponse | null]
  guideUpdated: [
    payload: {
      phase: GuideUiPhase
      guide: ObservationSmartSprayGuideResponse | null
    },
  ]
}>()

const phase = ref<AiPanelPhase>('idle')
const confirmPhase = ref<ConfirmPhase>('idle')
const psisPhase = ref<PsisPhase>('not_ready')
const analysis = ref<ObservationAiAnalysisResponse | null>(null)
const psis = ref<ObservationPsisResponse | null>(null)
const errorMessage = ref('')
const confirmError = ref('')
const psisError = ref('')
const statusMessage = ref('')
const localPhotoIds = ref<string[]>([])
const consentChecked = ref(false)
const selectedSeq = ref<number | null>(null)
const cropInput = ref(props.cropName || '배')
const lastPsisKey = ref('')

/** radio value는 문자열로 올 수 있어 숫자로 정규화 */
function onSelectCandidate(raw: number | string) {
  const n = Number(raw)
  selectedSeq.value = Number.isFinite(n) ? n : null
}

let reqSeq = 0
let confirmSeq = 0
let psisSeq = 0
let guideSeq = 0
let loadAbort: AbortController | null = null
let analyzeAbort: AbortController | null = null
let confirmAbort: AbortController | null = null
let psisAbort: AbortController | null = null
let guideAbort: AbortController | null = null
let alive = true

const effectivePhotoIds = computed(() => {
  if (props.photoIds && props.photoIds.length) return props.photoIds
  return localPhotoIds.value
})

const canAnalyze = computed(
  () =>
    Boolean(props.farmCd && props.obsId) &&
    effectivePhotoIds.value.length > 0 &&
    consentChecked.value &&
    phase.value !== 'analyzing' &&
    phase.value !== 'loading' &&
    confirmPhase.value !== 'confirming' &&
    psisPhase.value !== 'loading',
)

const candidates = computed(() => analysis.value?.candidates ?? [])

const selectedCandidate = computed(() =>
  candidates.value.find((c) => c.candidate_seq === selectedSeq.value) || null,
)

const canConfirm = computed(
  () =>
    Boolean(analysis.value?.analysis_id) &&
    selectedSeq.value != null &&
    phase.value !== 'analyzing' &&
    confirmPhase.value !== 'confirming' &&
    candidates.value.length > 0,
)

const confirmedName = computed(() => {
  const c = candidates.value.find((x) => String(x.selected_yn || '') === 'Y')
  if (!c) return ''
  return String(c.confirmed_name || c.name_ko || '').trim()
})

const summaryText = computed(() => String(analysis.value?.summary || '').trim() || '—')

function isAbortError(err: unknown): boolean {
  return err instanceof ApiClientError && err.message.includes('취소')
}

function syncSelectionFromAnalysis(res: ObservationAiAnalysisResponse | null) {
  const list = res?.candidates || []
  const selected = list.find((c) => String(c.selected_yn || '') === 'Y')
  if (selected) {
    selectedSeq.value = selected.candidate_seq
    confirmPhase.value = 'confirmed'
    return
  }
  if (list.length === 1) {
    selectedSeq.value = list[0].candidate_seq
  } else {
    selectedSeq.value = null
  }
  confirmPhase.value = 'idle'
}

function evidenceLine(c: ObservationAiCandidate): string {
  const ev = (c.visual_evidence || []).map((x) => String(x).trim()).filter(Boolean)
  const diff = String(c.differential_reason || '').trim()
  const parts = [...ev]
  if (diff) parts.push(diff)
  return parts.length ? parts.join(' · ') : '—'
}

async function refreshPhotoIds(signal?: AbortSignal) {
  if (props.photoIds && props.photoIds.length) {
    localPhotoIds.value = [...props.photoIds]
    return
  }
  const list = await fetchObservationPhotos(props.farmCd, props.obsId, signal)
  localPhotoIds.value = list.photos.map((p) => p.photo_id)
}

async function loadLatest() {
  if (!props.farmCd || !props.obsId) return
  const seq = ++reqSeq
  loadAbort?.abort()
  loadAbort = new AbortController()
  phase.value = 'loading'
  errorMessage.value = ''
  statusMessage.value = ''
  try {
    await refreshPhotoIds(loadAbort.signal)
    const res = await fetchObservationAiAnalysis(
      props.farmCd,
      props.obsId,
      loadAbort.signal,
    )
    if (!alive || seq !== reqSeq) return
    analysis.value = res
    syncSelectionFromAnalysis(res)
    if (res.analysis_id) {
      phase.value = 'success'
      if (confirmedName.value) {
        await loadCachedPsis(seq)
      }
    } else {
      phase.value = 'idle'
      clearPsis()
    }
  } catch (err) {
    if (!alive || seq !== reqSeq || isAbortError(err)) return
    phase.value = 'error'
    errorMessage.value =
      err instanceof ApiClientError ? err.message : '분석 결과를 불러오지 못했습니다.'
  }
}

async function loadCachedPsis(parentSeq: number) {
  try {
    const cached = await fetchObservationPsis(props.farmCd, props.obsId)
    if (!alive || parentSeq !== reqSeq) return
    if (cached.success && (cached.similar_cases?.length || cached.psis_status === 'EMPTY')) {
      applyPsisResult(cached)
    }
    await loadSmartGuide()
  } catch {
    /* 캐시 조회 실패는 무시 — 확정 후 재조회 */
    if (alive && parentSeq === reqSeq) await loadSmartGuide()
  }
}

function clearGuide() {
  guideAbort?.abort()
  guideSeq += 1
  emit('guideUpdated', { phase: 'idle', guide: null })
}

function clearPsis() {
  psis.value = null
  psisPhase.value = 'not_ready'
  psisError.value = ''
  lastPsisKey.value = ''
  emit('psisUpdated', null)
  clearGuide()
}

function applyPsisResult(res: ObservationPsisResponse) {
  psis.value = res
  if (!res.success) {
    psisPhase.value = 'error'
    psisError.value = messageForAiErrorCode(res.error_code, res.error)
  } else if (!res.similar_cases?.length || res.psis_status === 'EMPTY') {
    psisPhase.value = 'empty'
    psisError.value = ''
  } else {
    psisPhase.value = 'success'
    psisError.value = ''
  }
  emit('psisUpdated', res)
}

/** PSIS 완료 후 Smart Spray Guide 조회 (기존 카드용) */
async function loadSmartGuide() {
  if (!props.farmCd || !props.obsId) return
  const seq = ++guideSeq
  const farm = props.farmCd
  const oid = props.obsId
  guideAbort?.abort()
  guideAbort = new AbortController()
  emit('guideUpdated', { phase: 'loading', guide: null })
  try {
    const res = await fetchObservationSmartSprayGuide(farm, oid, guideAbort.signal)
    if (!alive || seq !== guideSeq) return
    if (props.farmCd !== farm || props.obsId !== oid) return
    if (!res.success) {
      emit('guideUpdated', {
        phase: 'error',
        guide: res,
      })
      return
    }
    emit('guideUpdated', {
      phase: guideUiPhaseFromStatus(res.guide_status),
      guide: res,
    })
  } catch (err) {
    if (!alive || seq !== guideSeq || isAbortError(err)) return
    emit('guideUpdated', { phase: 'error', guide: null })
  }
}

async function runAnalyze() {
  if (!canAnalyze.value) {
    if (!effectivePhotoIds.value.length) {
      errorMessage.value = '업로드된 사진이 없습니다. 사진을 먼저 등록해 주세요.'
      phase.value = 'error'
    }
    return
  }
  const seq = ++reqSeq
  const farm = props.farmCd
  const oid = props.obsId
  analyzeAbort?.abort()
  analyzeAbort = new AbortController()
  phase.value = 'analyzing'
  errorMessage.value = ''
  confirmError.value = ''
  statusMessage.value = 'AI 분석 중…'
  clearPsis()
  selectedSeq.value = null
  confirmPhase.value = 'idle'
  try {
    const ids = effectivePhotoIds.value.slice(0, OBS_AI_PHOTO_MAX_COUNT)
    const res = await requestObservationAiAnalysis(
      farm,
      oid,
      {
        consent: true,
        photo_ids: ids,
        crop_hint: cropInput.value.trim() || '',
      },
      { signal: analyzeAbort.signal },
    )
    if (!alive || seq !== reqSeq) return
    if (props.farmCd !== farm || props.obsId !== oid) return

    analysis.value = res
    syncSelectionFromAnalysis(res)
    if (!res.success) {
      phase.value = 'error'
      errorMessage.value = messageForAiErrorCode(res.error_code, res.error)
      statusMessage.value = ''
      return
    }
    phase.value = 'success'
    statusMessage.value = '분석이 완료되었습니다.'
    emit('updated', res)
  } catch (err) {
    if (!alive || seq !== reqSeq || isAbortError(err)) return
    if (props.farmCd !== farm || props.obsId !== oid) return
    phase.value = 'error'
    statusMessage.value = ''
    if (err instanceof ApiClientError) {
      errorMessage.value = messageForAiErrorCode(err.errorCode, err.message)
    } else {
      errorMessage.value = 'AI 분석에 실패했습니다.'
    }
  }
}

async function runConfirm() {
  if (!canConfirm.value || !analysis.value?.analysis_id || selectedSeq.value == null) {
    confirmError.value = '확정할 후보를 선택해 주세요.'
    confirmPhase.value = 'error'
    return
  }
  const cand = selectedCandidate.value
  if (!cand) {
    confirmError.value = '확정할 후보를 선택해 주세요.'
    confirmPhase.value = 'error'
    return
  }

  const already =
    String(cand.selected_yn || '') === 'Y' &&
    String(analysis.value.ai_status || '').toUpperCase() === 'CONFIRMED'
  if (already) {
    confirmPhase.value = 'confirmed'
    statusMessage.value = '이미 확정된 후보입니다.'
    await runPsisSearch(false)
    return
  }

  const seq = ++confirmSeq
  const farm = props.farmCd
  const oid = props.obsId
  const aid = analysis.value.analysis_id
  const candSeq = selectedSeq.value
  confirmAbort?.abort()
  confirmAbort = new AbortController()
  confirmPhase.value = 'confirming'
  confirmError.value = ''
  statusMessage.value = '후보 확정 중…'
  clearPsis()

  try {
    const res = await confirmObservationAiCandidate(
      farm,
      oid,
      {
        analysis_id: aid,
        candidate_seq: candSeq,
        confirmed_name: cand.name_ko || null,
      },
      { signal: confirmAbort.signal },
    )
    if (!alive || seq !== confirmSeq) return
    if (props.farmCd !== farm || props.obsId !== oid) return

    if (!res.success) {
      confirmPhase.value = 'error'
      confirmError.value = messageForAiErrorCode(res.error_code, res.error)
      statusMessage.value = ''
      return
    }

    confirmPhase.value = 'confirmed'
    statusMessage.value = `'${res.confirmed_name || cand.name_ko}' 확정되었습니다.`
    emit('confirmed', {
      analysis_id: String(res.analysis_id || aid),
      candidate_seq: Number(res.candidate_seq || candSeq),
      confirmed_name: String(res.confirmed_name || cand.name_ko || ''),
      ai_status: String(res.ai_status || 'CONFIRMED'),
    })

    const refreshed = await fetchObservationAiAnalysis(farm, oid, confirmAbort.signal)
    if (!alive || seq !== confirmSeq) return
    analysis.value = refreshed
    syncSelectionFromAnalysis(refreshed)
    emit('updated', refreshed)

    await runPsisSearch(false)
  } catch (err) {
    if (!alive || seq !== confirmSeq || isAbortError(err)) return
    confirmPhase.value = 'error'
    statusMessage.value = ''
    if (err instanceof ApiClientError) {
      confirmError.value = messageForAiErrorCode(err.errorCode, err.message)
    } else {
      confirmError.value = '후보 확정에 실패했습니다.'
    }
  }
}

async function runPsisSearch(forceRefresh: boolean) {
  const disease =
    confirmedName.value ||
    String(selectedCandidate.value?.name_ko || '').trim()
  const crop = cropInput.value.trim()
  if (!disease) {
    psisPhase.value = 'error'
    psisError.value = '확정된 병해충명이 없습니다.'
    return
  }
  if (!crop) {
    psisPhase.value = 'error'
    psisError.value = '작물명을 입력해 주세요.'
    return
  }

  const key = `${props.farmCd}|${props.obsId}|${crop}|${disease}|${forceRefresh ? '1' : '0'}`
  if (!forceRefresh && key === lastPsisKey.value && psisPhase.value === 'success') {
    await loadSmartGuide()
    return
  }

  const seq = ++psisSeq
  const farm = props.farmCd
  const oid = props.obsId
  psisAbort?.abort()
  psisAbort = new AbortController()
  psisPhase.value = 'loading'
  psisError.value = ''

  try {
    const res = await requestObservationPsis(
      farm,
      oid,
      {
        analysis_id: analysis.value?.analysis_id,
        candidate_seq: selectedSeq.value,
        crop_name: crop,
        disease_name: disease,
        force_refresh: forceRefresh,
        allow_similar: false,
      },
      { signal: psisAbort.signal },
    )
    if (!alive || seq !== psisSeq) return
    if (props.farmCd !== farm || props.obsId !== oid) return
    lastPsisKey.value = `${farm}|${oid}|${crop}|${disease}|0`
    applyPsisResult(res)
    await loadSmartGuide()
  } catch (err) {
    if (!alive || seq !== psisSeq || isAbortError(err)) return
    psisPhase.value = 'error'
    if (err instanceof ApiClientError) {
      psisError.value = messageForAiErrorCode(err.errorCode, err.message)
    } else {
      psisError.value = '공식 농약정보 조회에 실패했습니다.'
    }
    emit('psisUpdated', null)
    // PSIS 실패여도 가이드는 DB 기준으로 조회 시도
    await loadSmartGuide()
  }
}

function resetForObsChange() {
  reqSeq += 1
  confirmSeq += 1
  psisSeq += 1
  guideSeq += 1
  loadAbort?.abort()
  analyzeAbort?.abort()
  confirmAbort?.abort()
  psisAbort?.abort()
  guideAbort?.abort()
  analysis.value = null
  errorMessage.value = ''
  confirmError.value = ''
  statusMessage.value = ''
  localPhotoIds.value = []
  consentChecked.value = false
  selectedSeq.value = null
  confirmPhase.value = 'idle'
  cropInput.value = props.cropName || '배'
  clearPsis()
  phase.value = 'idle'
}

watch(
  () => [props.farmCd, props.obsId] as const,
  () => {
    resetForObsChange()
    void loadLatest()
  },
)

watch(
  () => (props.photoIds && props.photoIds.length ? props.photoIds.join('|') : ''),
  (key) => {
    if (!key || !props.photoIds?.length) return
    localPhotoIds.value = [...props.photoIds]
  },
)

watch(
  () => props.cropName,
  (v) => {
    if (v && v.trim()) cropInput.value = v.trim()
  },
)

onMounted(() => {
  alive = true
  void loadLatest()
})

onBeforeUnmount(() => {
  alive = false
  reqSeq += 1
  confirmSeq += 1
  psisSeq += 1
  guideSeq += 1
  loadAbort?.abort()
  analyzeAbort?.abort()
  confirmAbort?.abort()
  psisAbort?.abort()
  guideAbort?.abort()
})

defineExpose({
  reload: loadLatest,
  analyze: runAnalyze,
  confirm: runConfirm,
  searchPsis: runPsisSearch,
  loadGuide: loadSmartGuide,
  phase,
  confirmPhase,
  psisPhase,
  psis,
  selectedSeq,
})
</script>

<template>
  <div class="ai-panel" aria-label="AI 분석">
    <p class="lead">{{ aiLabel(analysis?.ai_status || 'NONE') }}</p>
    <p class="hint">{{ aiHint(analysis?.ai_status || 'NONE') }}</p>

    <p v-if="phase === 'analyzing' || statusMessage" class="status" role="status">
      {{ statusMessage || 'AI 분석 중…' }}
    </p>
    <p v-if="errorMessage" class="error" role="alert">{{ errorMessage }}</p>
    <p v-if="confirmError" class="error" role="alert">{{ confirmError }}</p>

    <label class="consent">
      <input
        v-model="consentChecked"
        type="checkbox"
        :disabled="phase === 'analyzing' || confirmPhase === 'confirming'"
      >
      외부 AI 분석에 사진을 전송하는 데 동의합니다.
    </label>

    <label class="crop-field">
      <span class="crop-field__lbl">작물명</span>
      <input
        v-model="cropInput"
        type="text"
        class="crop-field__input"
        placeholder="예: 배"
        :disabled="confirmPhase === 'confirming' || psisPhase === 'loading'"
      >
    </label>

    <div class="actions">
      <OdsButton
        variant="ai"
        :disabled="!canAnalyze"
        :block="false"
        class="analyze-btn"
        @click="runAnalyze"
      >
        {{
          phase === 'analyzing'
            ? '분석 중…'
            : analysis?.analysis_id
              ? '재분석'
              : 'AI 분석'
        }}
      </OdsButton>
      <p v-if="!effectivePhotoIds.length" class="warn">
        사진 업로드 후 분석을 실행할 수 있습니다.
      </p>
      <p v-else-if="!consentChecked" class="warn">
        동의 후 AI 분석을 실행할 수 있습니다.
      </p>
    </div>

    <template v-if="analysis?.analysis_id && phase !== 'analyzing'">
      <p class="summary">{{ summaryText }}</p>

      <fieldset class="cand-set" :disabled="confirmPhase === 'confirming'">
        <legend class="cand-set__legend">병해충 후보</legend>
        <p v-if="!candidates.length" class="warn">표시할 후보가 없습니다.</p>
        <label
          v-for="c in candidates"
          :key="c.candidate_seq"
          class="cand"
          :class="{
            'cand--active': selectedSeq === c.candidate_seq,
            'cand--confirmed': String(c.selected_yn || '') === 'Y',
          }"
        >
          <input
            type="radio"
            name="ai-candidate"
            :value="c.candidate_seq"
            :checked="selectedSeq === c.candidate_seq"
            @change="onSelectCandidate(c.candidate_seq)"
          >
          <div class="cand__body">
            <p class="cand__title">
              {{ c.name_ko || '—' }}
              <span v-if="String(c.selected_yn || '') === 'Y'" class="cand__badge">확정</span>
            </p>
            <p class="cand__meta">
              {{ categoryLabel(c.category) }} · 신뢰도 {{ formatConfidence(c.confidence) }}
              · 긴급도 {{ urgencyLabel(c.urgency) }}
            </p>
            <p class="cand__ev">{{ evidenceLine(c) }}</p>
          </div>
        </label>
      </fieldset>

      <div class="actions">
        <OdsButton
          variant="primary"
          :disabled="!canConfirm"
          :block="false"
          @click="runConfirm"
        >
          {{
            confirmPhase === 'confirming'
              ? '확정 중…'
              : confirmPhase === 'confirmed'
                ? '후보 재확정'
                : '후보 확정'
          }}
        </OdsButton>
      </div>
    </template>

    <section v-if="confirmPhase === 'confirmed' || psisPhase !== 'not_ready'" class="psis" aria-label="공식 농약정보">
      <h3 class="psis__title">공식 농약정보</h3>
      <p v-if="psisPhase === 'loading'" class="status" role="status">공식 등록정보 조회 중…</p>
      <p v-if="psisError" class="error" role="alert">{{ psisError }}</p>
      <p v-if="psisPhase === 'empty'" class="warn">
        확정 병해충에 대한 등록정보가 없습니다.
      </p>
      <template v-if="psisPhase === 'success' && psis">
        <p class="psis__meta">
          조회: {{ psis.query_candidate || '—' }}
          · 작물 {{ psis.crop_name || cropInput }}
          · {{ psis.similar_cases.length }}건
          <span v-if="psis.from_cache"> (캐시)</span>
        </p>
        <ul class="psis__list">
          <li v-for="item in psis.similar_cases" :key="item.snapshot_id || item.rank" class="psis__item">
            <p class="psis__name">
              {{ item.rank }}. {{ item.pesticide_name || item.brand_name || '—' }}
              <span class="psis__sim">{{ matchTypeLabel(item.similarity) }}</span>
            </p>
            <p class="psis__line">성분: {{ item.active_ingredient || '—' }}</p>
            <p class="psis__line">용도: {{ item.purpose_name || '—' }}</p>
            <p class="psis__line">희석: {{ item.dilution || '—' }}</p>
            <p class="psis__line">사용법: {{ item.usage_method || '—' }}</p>
            <p class="psis__line">
              안전사용: {{ item.preharvest_interval || '—' }}
              · 횟수 {{ item.max_use_count || '—' }}
            </p>
          </li>
        </ul>
      </template>
      <OdsButton
        v-if="confirmPhase === 'confirmed' && psisPhase !== 'loading'"
        variant="secondary"
        :block="false"
        class="psis__retry"
        @click="runPsisSearch(true)"
      >
        방제정보 다시 조회
      </OdsButton>
    </section>
  </div>
</template>

<style scoped>
.ai-panel {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-8);
}
.lead {
  margin: 0;
  font: var(--ods-font-body-1);
  font-weight: 700;
  color: var(--ods-color-text);
}
.hint,
.summary {
  margin: 0;
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
}
.status {
  margin: 0;
  font: var(--ods-font-body-2);
  color: var(--ods-color-primary);
  font-weight: 600;
}
.error {
  margin: 0;
  font: var(--ods-font-body-2);
  color: var(--ods-color-danger);
}
.consent,
.crop-field {
  display: flex;
  align-items: flex-start;
  gap: var(--ods-space-8);
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
}
.crop-field {
  flex-direction: column;
  gap: var(--ods-space-4);
}
.crop-field__input {
  width: 100%;
  min-height: 40px;
  padding: 0 var(--ods-space-8);
  border: 1px solid var(--ods-color-border);
  border-radius: var(--ods-radius-badge, 8px);
  font: var(--ods-font-body-2);
}
.actions {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--ods-space-8);
}
.analyze-btn {
  min-width: 120px;
}
.warn {
  margin: 0;
  font: var(--ods-font-caption);
  color: var(--ods-color-caution, #b45309);
}
.cand-set {
  margin: 0;
  padding: 0;
  border: none;
}
.cand-set__legend {
  font: var(--ods-font-body-2);
  font-weight: 700;
  margin-bottom: var(--ods-space-8);
}
.cand {
  display: flex;
  gap: var(--ods-space-8);
  padding: var(--ods-space-8);
  margin: 0 0 var(--ods-space-8);
  border: 1px solid var(--ods-color-border);
  border-radius: 8px;
  background: var(--ods-color-white, #fff);
  cursor: pointer;
}
.cand--active {
  border-color: var(--ods-color-primary);
  background: color-mix(in srgb, var(--ods-color-primary) 8%, white);
}
.cand--confirmed {
  box-shadow: inset 3px 0 0 var(--ods-color-primary);
}
.cand__title {
  margin: 0;
  font: var(--ods-font-body-2);
  font-weight: 700;
}
.cand__badge {
  margin-left: 6px;
  font-size: 11px;
  color: var(--ods-color-primary);
}
.cand__meta,
.cand__ev {
  margin: 4px 0 0;
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
}
.psis {
  margin-top: var(--ods-space-8);
  padding-top: var(--ods-space-8);
  border-top: 1px solid var(--ods-color-border);
}
.psis__title {
  margin: 0 0 var(--ods-space-8);
  font: var(--ods-font-body-1);
  font-weight: 700;
}
.psis__meta {
  margin: 0 0 var(--ods-space-8);
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
}
.psis__list {
  margin: 0;
  padding: 0;
  list-style: none;
}
.psis__item {
  margin: 0 0 var(--ods-space-12);
  padding: var(--ods-space-8);
  border: 1px solid var(--ods-color-border);
  border-radius: 8px;
}
.psis__name {
  margin: 0 0 4px;
  font-weight: 700;
  font: var(--ods-font-body-2);
}
.psis__sim {
  margin-left: 6px;
  font-weight: 500;
  color: var(--ods-color-primary);
}
.psis__line {
  margin: 2px 0;
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
}
.psis__retry {
  margin-top: var(--ods-space-8);
}
</style>
