<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { ApiClientError } from '@/api/client'
import { fetchCommonCodes } from '@/api/commonCodes'
import {
  confirmObservationAiCandidate,
  fetchObservationAiAnalysis,
  fetchObservationSmartSprayGuide,
  requestObservationAiAnalysis,
} from '@/api/observationAi'
import { fetchObservationPhotos } from '@/api/observationPhotos'
import OdsButton from '@/components/ods/OdsButton.vue'
import OdsFormField from '@/components/ods/OdsFormField.vue'
import OdsSelect from '@/components/ods/OdsSelect.vue'
import {
  categoryLabel,
  formatConfidence,
  messageForAiErrorCode,
  urgencyLabel,
} from '@/shared/aiErrorMessages'
import {
  OBS_AI_DURATION_NOTICE,
  OBS_AI_PHOTO_MAX_COUNT,
  OBS_SEVERITY_NORMAL_CD,
  OBS_SEVERITY_PARENT_CD,
} from '@/composables/constants/app'
import { suggestSeverityFromUrgency } from '@/views/observation/severityFromUrgency'
import {
  aiHint,
  aiLabel,
  guideUiPhaseFromStatus,
  type GuideUiPhase,
} from '@/views/observation/scr004DetailUi'
import type { CommonCodeItem } from '@/types/commonCode'
import type {
  ObservationAiAnalysisResponse,
  ObservationAiCandidate,
  ObservationSmartSprayGuideResponse,
} from '@/types/observation'

export type AiPanelPhase =
  | 'idle'
  | 'loading'
  | 'analyzing'
  | 'success'
  | 'error'

export type ConfirmPhase = 'idle' | 'confirming' | 'confirmed' | 'error'

const props = withDefaults(
  defineProps<{
    farmCd: string
    obsId: string
    photoIds?: string[]
    /** AI 분석 crop_hint 기본값 (PC cb_crop 대응) */
    cropName?: string
    /** master 위험도 — 확정 복원 시 urgency 제안보다 우선 */
    masterSeverityCd?: string | null
  }>(),
  { cropName: '배', masterSeverityCd: null },
)

const emit = defineEmits<{
  updated: [result: ObservationAiAnalysisResponse]
  confirmed: [
    payload: {
      analysis_id: string
      candidate_seq: number
      confirmed_name: string
      ai_status: string
      severity_cd: string
    },
  ]
  guideUpdated: [
    payload: {
      phase: GuideUiPhase
      guide: ObservationSmartSprayGuideResponse | null
    },
  ]
}>()

const phase = ref<AiPanelPhase>('idle')
const confirmPhase = ref<ConfirmPhase>('idle')
const analysis = ref<ObservationAiAnalysisResponse | null>(null)
const errorMessage = ref('')
const confirmError = ref('')
const statusMessage = ref('')
const localPhotoIds = ref<string[]>([])
const consentChecked = ref(false)
const selectedSeq = ref<number | null>(null)
const severityCodes = ref<CommonCodeItem[]>([])
const severityCd = ref(OBS_SEVERITY_NORMAL_CD)
const cropInput = ref(props.cropName || '배')
/** 분석 중 경과 초 (버튼·상태 표시용) */
const analyzeElapsedSec = ref(0)

function resolveSeveritySuggestion(
  urgency: string | null | undefined,
  preferMaster: boolean,
): string {
  if (preferMaster) {
    const master = String(props.masterSeverityCd || '').trim()
    if (master) return master
  }
  return suggestSeverityFromUrgency(urgency)
}

/** radio value는 문자열로 올 수 있어 숫자로 정규화 */
function onSelectCandidate(raw: number | string) {
  const n = Number(raw)
  selectedSeq.value = Number.isFinite(n) ? n : null
  const cand = candidates.value.find((c) => c.candidate_seq === selectedSeq.value)
  // 후보 변경 시 AI 긴급도 제안으로 갱신 (사용자가 확정 전 수정 가능)
  severityCd.value = suggestSeverityFromUrgency(cand?.urgency)
}

async function loadSeverityCodes() {
  try {
    severityCodes.value = await fetchCommonCodes(
      props.farmCd,
      OBS_SEVERITY_PARENT_CD,
    )
  } catch {
    severityCodes.value = []
  }
}

let reqSeq = 0
let confirmSeq = 0
let guideSeq = 0
let loadAbort: AbortController | null = null
let analyzeAbort: AbortController | null = null
let confirmAbort: AbortController | null = null
let guideAbort: AbortController | null = null
let analyzeTickTimer: ReturnType<typeof setInterval> | null = null
let alive = true

function stopAnalyzeTick() {
  if (analyzeTickTimer != null) {
    clearInterval(analyzeTickTimer)
    analyzeTickTimer = null
  }
  analyzeElapsedSec.value = 0
}

function startAnalyzeTick() {
  stopAnalyzeTick()
  analyzeElapsedSec.value = 0
  analyzeTickTimer = setInterval(() => {
    analyzeElapsedSec.value += 1
  }, 1000)
}

const analyzeBusyLabel = computed(() => {
  const sec = analyzeElapsedSec.value
  if (sec <= 0) return '사진 분석 중…'
  return `사진 분석 중… ${sec}초`
})

const effectivePhotoIds = computed(() => {
  // 서버에서 갱신한 localPhotoIds 를 우선 (재분석 직전 동기화)
  if (localPhotoIds.value.length) return localPhotoIds.value
  if (props.photoIds && props.photoIds.length) return props.photoIds
  return []
})

const canAnalyze = computed(
  () =>
    Boolean(props.farmCd && props.obsId) &&
    effectivePhotoIds.value.length > 0 &&
    consentChecked.value &&
    phase.value !== 'analyzing' &&
    phase.value !== 'loading' &&
    confirmPhase.value !== 'confirming',
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
    candidates.value.length > 0 &&
    Boolean(severityCd.value),
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
    // 이미 확정된 건: master 위험도 유지 (urgency로 덮어쓰지 않음)
    severityCd.value = resolveSeveritySuggestion(selected.urgency, true)
    confirmPhase.value = 'confirmed'
    return
  }
  if (list.length === 1) {
    selectedSeq.value = list[0].candidate_seq
    severityCd.value = suggestSeverityFromUrgency(list[0].urgency)
  } else {
    selectedSeq.value = null
    severityCd.value = OBS_SEVERITY_NORMAL_CD
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
  // 재분석 시 항상 서버 목록을 기준으로 맞춤 (부모 prop 지연·불일치 방지)
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
        await loadSmartGuide()
      }
    } else {
      phase.value = 'idle'
      clearGuide()
    }
  } catch (err) {
    if (!alive || seq !== reqSeq || isAbortError(err)) return
    phase.value = 'error'
    errorMessage.value =
      err instanceof ApiClientError ? err.message : '분석 결과를 불러오지 못했습니다.'
  }
}

function clearGuide() {
  guideAbort?.abort()
  guideSeq += 1
  emit('guideUpdated', { phase: 'idle', guide: null })
}

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
  startAnalyzeTick()
  statusMessage.value = `AI 분석 중… ${OBS_AI_DURATION_NOTICE}`
  clearGuide()
  selectedSeq.value = null
  confirmPhase.value = 'idle'
  try {
    // 재분석 직전 사진 목록을 서버와 재동기화 (부모 prop 지연·누락 방지)
    await refreshPhotoIds(analyzeAbort.signal)
    if (!alive || seq !== reqSeq) return
    if (props.farmCd !== farm || props.obsId !== oid) return

    const ids = effectivePhotoIds.value.slice(0, OBS_AI_PHOTO_MAX_COUNT)
    if (!ids.length) {
      phase.value = 'error'
      errorMessage.value = '업로드된 사진이 없습니다. 사진을 먼저 등록해 주세요.'
      statusMessage.value = ''
      stopAnalyzeTick()
      return
    }

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
      stopAnalyzeTick()
      return
    }
    phase.value = 'success'
    statusMessage.value = '분석이 완료되었습니다.'
    stopAnalyzeTick()
    emit('updated', res)
  } catch (err) {
    if (!alive || seq !== reqSeq) return
    if (isAbortError(err)) {
      stopAnalyzeTick()
      return
    }
    if (props.farmCd !== farm || props.obsId !== oid) return
    phase.value = 'error'
    statusMessage.value = ''
    stopAnalyzeTick()
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
  if (!severityCd.value) {
    confirmError.value = '위험도를 선택해 주세요.'
    confirmPhase.value = 'error'
    return
  }

  const seq = ++confirmSeq
  const farm = props.farmCd
  const oid = props.obsId
  const aid = analysis.value.analysis_id
  const candSeq = selectedSeq.value
  const chosenSeverity = severityCd.value
  confirmAbort?.abort()
  confirmAbort = new AbortController()
  confirmPhase.value = 'confirming'
  confirmError.value = ''
  statusMessage.value = '후보 확정 중…'
  clearGuide()

  try {
    const res = await confirmObservationAiCandidate(
      farm,
      oid,
      {
        analysis_id: aid,
        candidate_seq: candSeq,
        confirmed_name: cand.name_ko || null,
        severity_cd: chosenSeverity,
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
      severity_cd: chosenSeverity,
    })

    const refreshed = await fetchObservationAiAnalysis(farm, oid, confirmAbort.signal)
    if (!alive || seq !== confirmSeq) return
    analysis.value = refreshed
    syncSelectionFromAnalysis(refreshed)
    // 사용자가 확정한 위험도 유지 (urgency 제안으로 되돌리지 않음)
    severityCd.value = chosenSeverity
    emit('updated', refreshed)

    await loadSmartGuide()
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

function resetForObsChange() {
  reqSeq += 1
  confirmSeq += 1
  guideSeq += 1
  loadAbort?.abort()
  analyzeAbort?.abort()
  confirmAbort?.abort()
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
  stopAnalyzeTick()
  clearGuide()
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
  void loadSeverityCodes()
  void loadLatest()
})

watch(
  () => props.farmCd,
  () => {
    void loadSeverityCodes()
  },
)

onBeforeUnmount(() => {
  alive = false
  reqSeq += 1
  confirmSeq += 1
  guideSeq += 1
  stopAnalyzeTick()
  loadAbort?.abort()
  analyzeAbort?.abort()
  confirmAbort?.abort()
  guideAbort?.abort()
})

defineExpose({
  reload: loadLatest,
  analyze: runAnalyze,
  confirm: runConfirm,
  loadGuide: loadSmartGuide,
  phase,
  confirmPhase,
  selectedSeq,
  severityCd,
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

    <p class="duration-notice" role="note">{{ OBS_AI_DURATION_NOTICE }}</p>

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
        :disabled="confirmPhase === 'confirming'"
      >
    </label>

    <div class="actions">
      <OdsButton
        variant="ai"
        :disabled="!canAnalyze && phase !== 'analyzing'"
        :busy="phase === 'analyzing'"
        :block="false"
        class="analyze-btn"
        @click="runAnalyze"
      >
        <span
          v-if="phase === 'analyzing'"
          class="analyze-spin"
          aria-hidden="true"
        />
        {{
          phase === 'analyzing'
            ? analyzeBusyLabel
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

      <OdsFormField
        v-if="candidates.length"
        label="위험도"
        required
        hint="AI 긴급도 제안값입니다. 확정 전 확인해 주세요."
      >
        <OdsSelect v-model="severityCd" variant="form" required>
          <option
            v-for="c in severityCodes"
            :key="c.code_cd"
            :value="c.code_cd"
          >
            {{ c.code_nm || c.code_cd }}
          </option>
        </OdsSelect>
      </OdsFormField>

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
.duration-notice {
  margin: 0;
  font: var(--ods-font-body-2);
  font-weight: 700;
  color: var(--ods-color-caution, #c2410c);
}
.error {
  margin: 0;
  font: var(--ods-font-body-2);
  color: var(--ods-color-danger);
}
.consent {
  display: flex;
  align-items: flex-start;
  gap: var(--ods-space-8);
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
}
.crop-field {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: var(--ods-space-8);
}
.crop-field__lbl {
  flex-shrink: 0;
  font: var(--ods-font-body-2);
  font-weight: 700;
  color: var(--ods-color-text);
}
.crop-field__input {
  flex: 1;
  min-width: 0;
  width: auto;
  min-height: 40px;
  padding: 0 var(--ods-space-8);
  border: 1px solid var(--ods-color-border);
  border-radius: var(--ods-radius-badge, 8px);
  font: var(--ods-font-body-2);
  font-weight: 700;
  color: var(--ods-color-text);
  background: var(--ods-color-white, #fff);
}
.crop-field__input::placeholder {
  font-weight: 400;
  color: var(--ods-color-text-secondary);
}
.actions {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--ods-space-8);
}
.analyze-btn {
  min-width: 168px;
}
.analyze-spin {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.35);
  border-top-color: #fff;
  border-radius: 50%;
  animation: analyze-spin 0.75s linear infinite;
  flex-shrink: 0;
}
@keyframes analyze-spin {
  to {
    transform: rotate(360deg);
  }
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
</style>
