<script setup lang="ts">
/**
 * ODS 폼 가독성 레퍼런스 (열매 측정).
 * @see docs/ODS/MOBILE_FORM_READABILITY.md — ObservationNewView 와 동일 토큰
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'

import { fetchCommonCodes } from '@/api/commonCodes'
import { ApiClientError } from '@/api/client'
import {
  fetchFruitMeasurement,
  fetchObservationTrack,
  saveFruitMeasurement,
} from '@/api/observationFruit'
import { completeObservation, fetchObservationDetail } from '@/api/observations'
import OdsAppBar from '@/components/ods/OdsAppBar.vue'
import OdsBottomNav from '@/components/ods/OdsBottomNav.vue'
import OdsButton from '@/components/ods/OdsButton.vue'
import OdsCard from '@/components/ods/OdsCard.vue'
import FruitMeasureForm from '@/views/observation/components/FruitMeasureForm.vue'
import {
  OBS_CALYX_PARENT_CD,
  OBS_FRUIT_COLOR_PARENT_CD,
  OBS_FRUIT_SHAPE_PARENT_CD,
  OBS_STALK_PARENT_CD,
  OBS_TARGET_FRUIT_CD,
} from '@/composables/constants/app'
import {
  emptyFruitMeasureForm,
  formFromMeasurement,
  measurementFromForm,
  type FruitMeasureFormModel,
} from '@/shared/fruitMeasureForm'
import { clearObsDraft } from '@/composables/obsDraft'
import { useAppStore } from '@/composables/stores/app'
import type { CommonCodeItem } from '@/types/commonCode'
import type { ObservationTrackItem } from '@/types/observation'

const route = useRoute()
const router = useRouter()
const store = useAppStore()
const { farmCd, farm } = storeToRefs(store)

const obsId = computed(() => String(route.params.obsId || '').trim())
const fromWizard = computed(() => String(route.query.from || '') === 'new')

const ready = ref(false)
const loading = ref(false)
const saving = ref(false)
const errorMessage = ref('')
const statusMessage = ref('')
const obsStatus = ref('')
const targetTypeCd = ref('')
/** 추적(2차+) 완료 후 1차 상세로 복귀용 */
const rootObsId = ref('')
const parentObsId = ref('')

const form = ref<FruitMeasureFormModel>(emptyFruitMeasureForm())
const shapeOptions = ref<CommonCodeItem[]>([])
const colorOptions = ref<CommonCodeItem[]>([])
const stalkOptions = ref<CommonCodeItem[]>([])
const calyxOptions = ref<CommonCodeItem[]>([])

const isDraft = computed(() => obsStatus.value === 'DRAFT')
const isFruitObs = computed(
  () => String(targetTypeCd.value || '').trim() === OBS_TARGET_FRUIT_CD,
)
const showFinish = computed(() => Boolean(obsId.value) && (isDraft.value || fromWizard.value))
const finishLabel = computed(() => (isDraft.value ? '최종 완료' : '수정 완료'))

let loadAbort: AbortController | null = null

async function loadCodes(signal?: AbortSignal) {
  const [shape, color, stalk, calyx] = await Promise.all([
    fetchCommonCodes(farmCd.value, OBS_FRUIT_SHAPE_PARENT_CD, { signal }),
    fetchCommonCodes(farmCd.value, OBS_FRUIT_COLOR_PARENT_CD, { signal }),
    fetchCommonCodes(farmCd.value, OBS_STALK_PARENT_CD, { signal }),
    fetchCommonCodes(farmCd.value, OBS_CALYX_PARENT_CD, { signal }),
  ])
  shapeOptions.value = shape
  colorOptions.value = color
  stalkOptions.value = stalk
  calyxOptions.value = calyx
}

function prefillFromTrack(items: ObservationTrackItem[]): void {
  const prev =
    items.filter((x) => !x.is_current).at(-1) ||
    (items.length >= 2 ? items[items.length - 2] : null)
  if (!prev) return
  form.value = formFromMeasurement({
    width_mm: prev.width_mm,
    height_mm: prev.height_mm,
    circumference_mm: prev.circumference_mm,
    estimated_weight_g: prev.estimated_weight_g,
    shape_cd: prev.shape_cd,
    skin_color_cd: prev.skin_color_cd,
    fruit_rmk: '',
  })
}

async function loadAll() {
  if (!obsId.value) {
    obsStatus.value = ''
    targetTypeCd.value = ''
    rootObsId.value = ''
    parentObsId.value = ''
    return
  }
  loadAbort?.abort()
  loadAbort = new AbortController()
  const signal = loadAbort.signal
  loading.value = true
  errorMessage.value = ''
  try {
    const detail = await fetchObservationDetail(farmCd.value, obsId.value)
    obsStatus.value = String(detail.observation_status || 'DRAFT').toUpperCase()
    targetTypeCd.value = String(detail.target_type_cd || '').trim()
    parentObsId.value = String(detail.parent_obs_id || '').trim()
    rootObsId.value =
      String(detail.root_obs_id || '').trim() ||
      parentObsId.value ||
      obsId.value

    if (String(detail.target_type_cd || '').trim() !== OBS_TARGET_FRUIT_CD) {
      errorMessage.value = '과실 관찰이 아닙니다. 사진 단계로 이동합니다.'
      void router.replace({
        name: 'observation-photos',
        params: { obsId: obsId.value },
        query: fromWizard.value ? { from: 'new' } : {},
      })
      return
    }

    await loadCodes(signal)
    const [meas, track] = await Promise.all([
      fetchFruitMeasurement(farmCd.value, obsId.value, signal),
      fetchObservationTrack(farmCd.value, obsId.value, signal),
    ])
    if (meas.measurement) {
      form.value = formFromMeasurement(meas.measurement)
    } else {
      form.value = emptyFruitMeasureForm()
      prefillFromTrack(track.items || [])
    }
  } catch (err) {
    if (err instanceof ApiClientError && err.message.includes('취소')) return
    errorMessage.value =
      err instanceof ApiClientError ? err.message : '열매 측정 정보를 불러오지 못했습니다.'
  } finally {
    loading.value = false
  }
}

function goPhotos() {
  if (!obsId.value) {
    void router.push({ name: 'observation' })
    return
  }
  void router.push({
    name: 'observation-photos',
    params: { obsId: obsId.value },
    query: fromWizard.value ? { from: 'new' } : {},
  })
}

function goDetail(targetObsId?: string) {
  const id = String(targetObsId || obsId.value || '').trim()
  if (!id) {
    void router.push({ name: 'observation' })
    return
  }
  void router.push({
    name: 'observation-detail',
    params: { obsId: id },
  })
}

/** 추적(2차+) 완료 시 1차 상세로 — 추적관찰 버튼이 보이는 화면 */
function goAfterComplete() {
  if (parentObsId.value) {
    goDetail(rootObsId.value || parentObsId.value)
    return
  }
  void router.push({ name: 'observation' })
}

function goBack() {
  if (fromWizard.value) {
    goPhotos()
    return
  }
  if (obsStatus.value === 'COMPLETED' && obsId.value) {
    goDetail()
    return
  }
  void router.push({ name: 'observation' })
}

async function onFinish() {
  if (!obsId.value || saving.value || !showFinish.value || !isFruitObs.value) return
  saving.value = true
  errorMessage.value = ''
  statusMessage.value = '저장 중…'
  try {
    await saveFruitMeasurement(farmCd.value, obsId.value, measurementFromForm(form.value))
    if (!isDraft.value) {
      clearObsDraft(farmCd.value)
      statusMessage.value = '측정값이 저장되었습니다.'
      goDetail()
      return
    }
    statusMessage.value = '완료 처리 중…'
    await completeObservation(farmCd.value, obsId.value)
    clearObsDraft(farmCd.value)
    obsStatus.value = 'COMPLETED'
    statusMessage.value = '관찰이 완료되었습니다.'
    goAfterComplete()
  } catch (err) {
    statusMessage.value = ''
    errorMessage.value =
      err instanceof ApiClientError ? err.message : '저장에 실패했습니다.'
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  if (!farm.value) {
    await store.refreshAll()
  }
  await loadAll()
  ready.value = true
})

watch(obsId, () => {
  void loadAll()
})
</script>

<template>
  <div class="page">
    <main class="content ods-page-content">
      <OdsAppBar show-back back-mode="emit" @back="goBack" />

      <nav v-if="fromWizard" class="steps" aria-label="등록 단계">
        <span class="step">1. 기본정보</span>
        <span class="step">2. 사진</span>
        <span class="step step--active">3. 열매</span>
        <span class="step">4. 완료</span>
      </nav>

      <p v-if="!obsId" class="error" role="alert">관찰 번호가 없습니다.</p>
      <p v-else-if="loading || !ready" class="status" role="status">불러오는 중…</p>
      <OdsCard v-else-if="isFruitObs" class="card" aria-label="열매 측정 입력">
        <p class="hint">PC 관찰일지와 동일한 항목입니다. 필요한 값만 입력하세요.</p>
        <FruitMeasureForm
          v-model="form"
          :shape-options="shapeOptions"
          :color-options="colorOptions"
          :stalk-options="stalkOptions"
          :calyx-options="calyxOptions"
          :disabled="saving"
        />
      </OdsCard>

      <p v-if="statusMessage" class="status" role="status">{{ statusMessage }}</p>
      <p v-if="errorMessage" class="error" role="alert">{{ errorMessage }}</p>
    </main>

    <div v-if="obsId && isFruitObs" class="footer-actions">
      <OdsButton
        variant="secondary"
        type="button"
        :block="false"
        class="footer-btn"
        :disabled="saving"
        @click="goBack"
      >
        {{ fromWizard ? '사진으로' : obsStatus === 'COMPLETED' ? '상세' : '목록' }}
      </OdsButton>
      <OdsButton
        v-if="showFinish"
        variant="primary"
        :disabled="saving || loading"
        :block="false"
        class="footer-btn"
        @click="onFinish"
      >
        {{ saving ? '처리 중…' : finishLabel }}
      </OdsButton>
    </div>

    <OdsBottomNav />
  </div>
</template>

<style scoped>
.page {
  min-height: 100dvh;
  background: var(--ods-color-bg-muted);
  padding-bottom: calc(148px + env(safe-area-inset-bottom, 0px));
}
.content {
  /* padding/max-width -> .ods-page-content (AppBar SSOT) */
}
.steps {
  display: flex;
  gap: var(--ods-space-8);
  margin: 0;
  flex-wrap: wrap;
}
.step {
  font: var(--ods-font-card-emphasis);
  font-weight: 700;
  color: var(--ods-color-gray-500);
  padding: var(--ods-space-4) var(--ods-space-8);
  border-radius: var(--ods-radius-badge);
  background: var(--ods-color-white);
  border: 1px solid var(--ods-color-border);
}
.step--active {
  color: var(--ods-color-gray-900);
  background: color-mix(in srgb, var(--ods-color-accent) 70%, white);
  border-color: color-mix(in srgb, var(--ods-color-caution) 40%, var(--ods-color-accent));
}
.card {
  margin-top: var(--ods-space-8);
}
.hint {
  margin: 0 0 var(--ods-space-16);
  font: var(--ods-font-form-help);
  color: var(--ods-color-text-secondary);
}
.error {
  color: var(--ods-color-danger);
  font: var(--ods-font-form-help);
  font-weight: 600;
}
.status {
  margin: var(--ods-space-12) 0 0;
  font: var(--ods-font-form-help);
  color: var(--ods-color-primary);
  font-weight: 600;
}
.footer-actions {
  position: fixed;
  left: 0;
  right: 0;
  bottom: calc(64px + env(safe-area-inset-bottom, 0px));
  z-index: 30;
  display: flex;
  gap: var(--ods-space-8);
  max-width: 480px;
  margin: 0 auto;
  padding: var(--ods-space-8) var(--ods-page-padding-x)
    calc(var(--ods-space-8) + env(safe-area-inset-bottom, 0px));
  background: color-mix(in srgb, var(--ods-color-bg-muted) 92%, transparent);
  backdrop-filter: blur(8px);
}
.footer-btn {
  flex: 1;
}
.footer-actions :deep(.ods-btn) {
  min-height: var(--ods-button-height, 48px);
}
</style>
