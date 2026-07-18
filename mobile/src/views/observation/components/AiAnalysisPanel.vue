<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { ApiClientError } from '@/api/client'
import {
  fetchObservationAiAnalysis,
  requestObservationAiAnalysis,
} from '@/api/observationAi'
import { fetchObservationPhotos } from '@/api/observationPhotos'
import OdsButton from '@/components/ods/OdsButton.vue'
import {
  formatConfidence,
  messageForAiErrorCode,
} from '@/shared/aiErrorMessages'
import { OBS_AI_PHOTO_MAX_COUNT } from '@/composables/constants/app'
import { aiHint, aiLabel } from '@/views/observation/scr004DetailUi'
import type { ObservationAiAnalysisResponse } from '@/types/observation'

export type AiPanelPhase =
  | 'idle'
  | 'loading'
  | 'analyzing'
  | 'success'
  | 'error'

const props = defineProps<{
  farmCd: string
  obsId: string
  /** 부모가 이미 알고 있는 photo_id (없으면 목록에서 조회) */
  photoIds?: string[]
}>()

const emit = defineEmits<{
  updated: [result: ObservationAiAnalysisResponse]
}>()

const phase = ref<AiPanelPhase>('idle')
const analysis = ref<ObservationAiAnalysisResponse | null>(null)
const errorMessage = ref('')
const statusMessage = ref('')
const localPhotoIds = ref<string[]>([])
const consentChecked = ref(true)

let reqSeq = 0
let loadAbort: AbortController | null = null
let analyzeAbort: AbortController | null = null
let alive = true

const effectivePhotoIds = computed(() => {
  if (props.photoIds && props.photoIds.length) return props.photoIds
  return localPhotoIds.value
})

const canAnalyze = computed(
  () =>
    Boolean(props.farmCd && props.obsId) &&
    effectivePhotoIds.value.length > 0 &&
    phase.value !== 'analyzing' &&
    phase.value !== 'loading',
)

const candidates = computed(() => analysis.value?.candidates ?? [])
const topName = computed(() => {
  const c = candidates.value[0]
  return (c?.name_ko || '').trim() || '—'
})
const topConfidence = computed(() =>
  formatConfidence(candidates.value[0]?.confidence ?? analysis.value?.confidence),
)
const summaryText = computed(() => {
  const s = String(analysis.value?.summary || '').trim()
  return s || '—'
})
const evidenceText = computed(() => {
  const c = candidates.value[0]
  const ev = c?.visual_evidence || []
  const diff = String(c?.differential_reason || '').trim()
  const parts = [...ev.map((x) => String(x).trim()).filter(Boolean)]
  if (diff) parts.push(diff)
  return parts.length ? parts.join(' · ') : '—'
})
const needMorePhotos = computed(() => {
  const a = analysis.value
  if (!a) return false
  if (a.analysis_possible === false) return true
  if (a.review_required) return true
  const q = String(a.image_quality || '').toUpperCase()
  return q === 'POOR' || q === 'BAD'
})

function isAbortError(err: unknown): boolean {
  return err instanceof ApiClientError && err.message.includes('취소')
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
    if (res.analysis_id) {
      phase.value = 'success'
      statusMessage.value = ''
    } else {
      phase.value = 'idle'
    }
  } catch (err) {
    if (!alive || seq !== reqSeq || isAbortError(err)) return
    phase.value = 'error'
    errorMessage.value =
      err instanceof ApiClientError ? err.message : '분석 결과를 불러오지 못했습니다.'
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
  if (!consentChecked.value) {
    errorMessage.value = '외부 AI 전송에 동의해 주세요.'
    phase.value = 'error'
    return
  }

  const seq = ++reqSeq
  const farm = props.farmCd
  const oid = props.obsId
  analyzeAbort?.abort()
  analyzeAbort = new AbortController()
  phase.value = 'analyzing'
  errorMessage.value = ''
  statusMessage.value = 'AI 분석 중…'
  try {
    const ids = effectivePhotoIds.value.slice(0, OBS_AI_PHOTO_MAX_COUNT)
    const res = await requestObservationAiAnalysis(
      farm,
      oid,
      { consent: true, photo_ids: ids, crop_hint: '' },
      { signal: analyzeAbort.signal },
    )
    if (!alive || seq !== reqSeq) return
    if (props.farmCd !== farm || props.obsId !== oid) return

    analysis.value = res
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

function resetForObsChange() {
  reqSeq += 1
  loadAbort?.abort()
  analyzeAbort?.abort()
  analysis.value = null
  errorMessage.value = ''
  statusMessage.value = ''
  localPhotoIds.value = []
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

onMounted(() => {
  alive = true
  void loadLatest()
})

onBeforeUnmount(() => {
  alive = false
  reqSeq += 1
  loadAbort?.abort()
  analyzeAbort?.abort()
})

defineExpose({
  reload: loadLatest,
  analyze: runAnalyze,
  phase,
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

    <label class="consent">
      <input v-model="consentChecked" type="checkbox" :disabled="phase === 'analyzing'">
      외부 AI 분석에 사진을 전송하는 데 동의합니다.
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
    </div>

    <dl v-if="analysis?.analysis_id && phase !== 'analyzing'" class="result">
      <div class="row">
        <dt>분석 상태</dt>
        <dd>{{ analysis.ai_status || '—' }}</dd>
      </div>
      <div class="row">
        <dt>후보</dt>
        <dd>{{ topName }}</dd>
      </div>
      <div class="row">
        <dt>신뢰도</dt>
        <dd>{{ topConfidence }}</dd>
      </div>
      <div class="row">
        <dt>요약</dt>
        <dd>{{ summaryText }}</dd>
      </div>
      <div class="row">
        <dt>근거</dt>
        <dd>{{ evidenceText }}</dd>
      </div>
      <div v-if="needMorePhotos" class="row">
        <dt>안내</dt>
        <dd>추가 촬영이 필요할 수 있습니다.</dd>
      </div>
      <div v-if="candidates.length > 1" class="row row--list">
        <dt>후보 목록</dt>
        <dd>
          <ul>
            <li v-for="c in candidates" :key="c.candidate_seq">
              {{ c.candidate_seq }}. {{ c.name_ko || '—' }}
              ({{ formatConfidence(c.confidence) }})
            </li>
          </ul>
        </dd>
      </div>
    </dl>
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
.hint {
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
.consent {
  display: flex;
  align-items: flex-start;
  gap: var(--ods-space-8);
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
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
.result {
  margin: var(--ods-space-8) 0 0;
  padding: 0;
}
.row {
  display: grid;
  grid-template-columns: 72px 1fr;
  gap: var(--ods-space-8);
  margin: 0 0 var(--ods-space-8);
  font: var(--ods-font-body-2);
}
.row dt {
  margin: 0;
  color: var(--ods-color-text-secondary);
  font-weight: 600;
}
.row dd {
  margin: 0;
  color: var(--ods-color-text);
  word-break: break-word;
}
.row--list ul {
  margin: 0;
  padding-left: 1.1rem;
}
</style>
