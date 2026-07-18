<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'

import { fetchFarmSites } from '@/api/farms'
import {
  createObservationBasic,
  fetchObservationDetail,
  updateObservationBasic,
} from '@/api/observations'
import { ApiClientError } from '@/api/client'
import OdsAppBar from '@/components/ods/OdsAppBar.vue'
import OdsBottomNav from '@/components/ods/OdsBottomNav.vue'
import OdsButton from '@/components/ods/OdsButton.vue'
import OdsFormField from '@/components/ods/OdsFormField.vue'
import OdsInput from '@/components/ods/OdsInput.vue'
import OdsSegmented from '@/components/ods/OdsSegmented.vue'
import OdsSelect from '@/components/ods/OdsSelect.vue'
import {
  OBS_TARGET_FRUIT_CD,
  OBS_TARGET_PEST_CD,
} from '@/composables/constants/app'
import { formatDateKo } from '@/shared/formatDateKo'
import { clearObsDraft, writeObsDraft } from '@/composables/obsDraft'
import { useAppStore } from '@/composables/stores/app'
import type { FarmSiteSummary } from '@/types/farm'

const route = useRoute()
const router = useRouter()
const store = useAppStore()
const { farmCd, farm } = storeToRefs(store)

const sites = ref<FarmSiteSummary[]>([])
const obsId = ref('')
const obsDt = ref(new Date().toISOString().slice(0, 10))
/** 신규 진입 시 미선택('') — 병해충/과실 필수 선택 */
const targetTypeCd = ref('')
const siteId = ref('')
const obsTitle = ref('')
const obsContent = ref('')

const loading = ref(true)
const saving = ref(false)
const errorMessage = ref('')
/** DRAFT | COMPLETED — 취소/안내 문구용 */
const obsStatus = ref('')
const datePicker = ref<HTMLInputElement | null>(null)

const farmLabel = computed(() => farm.value?.farm_nm || farmCd.value)
const obsDtLabel = computed(() => formatDateKo(obsDt.value))
const fromDetail = computed(() => String(route.query.from || '') === 'detail')
const isEditCompleted = computed(
  () => fromDetail.value || obsStatus.value === 'COMPLETED',
)
const canSubmit = computed(() => {
  if (saving.value) return false
  if (!obsDt.value || !siteId.value || !targetTypeCd.value) return false
  return Boolean(obsTitle.value.trim() && obsContent.value.trim())
})

const targetOptions = [
  { value: OBS_TARGET_PEST_CD, label: '병해충' },
  { value: OBS_TARGET_FRUIT_CD, label: '과실' },
]

function resetBlankForm() {
  obsId.value = ''
  obsDt.value = new Date().toISOString().slice(0, 10)
  targetTypeCd.value = ''
  siteId.value = sites.value.length === 1 ? sites.value[0].site_id : ''
  obsTitle.value = ''
  obsContent.value = ''
  obsStatus.value = ''
  errorMessage.value = ''
  clearObsDraft(farmCd.value)
}

function resolveInitialObsId(): string {
  // 신규(+ 관찰하기)은 빈 폼. 복원은 ?obs_id= 가 있을 때만 (뒤로가기·사진 단계 복귀)
  return String(route.query.obs_id || '').trim()
}

async function loadSites() {
  try {
    sites.value = await fetchFarmSites(farmCd.value, true)
  } catch {
    sites.value = []
  }
}

async function restoreIfNeeded() {
  const id = resolveInitialObsId()
  if (!id) {
    resetBlankForm()
    return
  }
  try {
    const detail = await fetchObservationDetail(farmCd.value, id)
    obsId.value = detail.obs_id
    obsDt.value = detail.obs_dt
    targetTypeCd.value =
      detail.target_type_cd === OBS_TARGET_FRUIT_CD
        ? OBS_TARGET_FRUIT_CD
        : detail.target_type_cd === OBS_TARGET_PEST_CD
          ? OBS_TARGET_PEST_CD
          : ''
    siteId.value = detail.site_id || ''
    obsTitle.value = detail.obs_title || ''
    obsContent.value = detail.obs_content || ''
    obsStatus.value = String(detail.observation_status || 'DRAFT').toUpperCase()
    writeObsDraft(farmCd.value, detail.obs_id)
  } catch {
    resetBlankForm()
    await router.replace({ name: 'observation-new' })
  }
}

function goList() {
  void router.push({ name: 'observation' })
}

function goDetail() {
  if (!obsId.value) {
    goList()
    return
  }
  void router.push({
    name: 'observation-detail',
    params: { obsId: obsId.value },
  })
}

async function onCancel() {
  if (isEditCompleted.value && obsId.value) {
    goDetail()
    return
  }
  goList()
}

function openDatePicker() {
  const el = datePicker.value
  if (!el || saving.value) return
  if (typeof el.showPicker === 'function') {
    try {
      el.showPicker()
      return
    } catch {
      /* fall through */
    }
  }
  el.focus()
  el.click()
}

function onObsDtInput(ev: Event) {
  obsDt.value = (ev.target as HTMLInputElement).value
}

async function onNext() {
  if (!targetTypeCd.value) {
    errorMessage.value = '관찰 대상을 선택해 주세요.'
    return
  }
  if (!canSubmit.value) {
    errorMessage.value =
      '필수 항목을 확인해 주세요. (관찰일자·대상·필지·제목·관찰 내용)'
    return
  }
  saving.value = true
  errorMessage.value = ''
  const payload = {
    obs_dt: obsDt.value,
    target_type_cd: targetTypeCd.value,
    site_id: siteId.value,
    obs_title: obsTitle.value.trim() || null,
    obs_content: obsContent.value.trim() || null,
  }
  try {
    const res = obsId.value
      ? await updateObservationBasic(farmCd.value, obsId.value, payload)
      : await createObservationBasic(farmCd.value, payload)
    obsId.value = res.obs_id
    writeObsDraft(farmCd.value, res.obs_id)
    await router.replace({
      name: 'observation-new',
      query: {
        obs_id: res.obs_id,
        ...(fromDetail.value || obsStatus.value === 'COMPLETED'
          ? { from: 'detail' }
          : {}),
      },
    })
    await router.push({
      name: 'observation-photos',
      params: { obsId: res.obs_id },
      query: { from: 'new' },
    })
  } catch (err) {
    errorMessage.value =
      err instanceof ApiClientError ? err.message : '저장에 실패했습니다. 다시 시도해 주세요.'
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  loading.value = true
  if (!farm.value) {
    await store.refreshAll()
  }
  await loadSites()
  await restoreIfNeeded()
  if (!obsId.value && !siteId.value && sites.value.length === 1) {
    siteId.value = sites.value[0].site_id
  }
  loading.value = false
})

// 동일 화면에서 ?obs_id 제거 시(신규 재진입)만 폼 초기화. 저장 후 obs_id 부여는 무시.
watch(
  () => String(route.query.obs_id || ''),
  async (id, prev) => {
    if (id === prev) return
    if (id) return
    loading.value = true
    resetBlankForm()
    if (!siteId.value && sites.value.length === 1) {
      siteId.value = sites.value[0].site_id
    }
    loading.value = false
  },
)
</script>

<template>
  <div class="page">
    <main class="content">
      <OdsAppBar show-back @back="onCancel" />

      <header class="top">
        <h1 class="title">{{ isEditCompleted && obsId ? '관찰 수정' : '관찰기록' }}</h1>
      </header>

      <nav class="steps" aria-label="등록 단계">
        <span class="step step--active">1. 기본정보</span>
        <span class="step">2. 사진</span>
        <span class="step step--muted">3. 완료</span>
      </nav>

      <p v-if="loading" class="status" role="status">불러오는 중…</p>

      <form
        v-else
        id="obs-basic-form"
        class="form"
        @submit.prevent="onNext"
      >
        <OdsInput
          label="농장"
          :model-value="farmLabel"
          variant="form"
          disabled
        />

        <OdsFormField label="관찰일자" required>
          <div class="date-field">
            <button
              type="button"
              class="date-field__display"
              :disabled="saving"
              :aria-label="`관찰일자 ${obsDtLabel}`"
              @click="openDatePicker"
            >
              {{ obsDtLabel }}
            </button>
            <input
              ref="datePicker"
              class="date-field__native"
              type="date"
              :value="obsDt"
              :disabled="saving"
              required
              tabindex="-1"
              aria-hidden="true"
              @input="onObsDtInput"
            >
          </div>
        </OdsFormField>

        <OdsFormField
          class="field-target"
          label="관찰 대상"
          required
          as="fieldset"
        >
          <OdsSegmented
            v-model="targetTypeCd"
            :options="targetOptions"
            :disabled="saving"
            aria-label="관찰 대상"
          />
        </OdsFormField>

        <OdsFormField label="필지" required>
          <OdsSelect v-model="siteId" variant="form" required>
            <option value="" disabled>필지 선택</option>
            <option v-for="s in sites" :key="s.site_id" :value="s.site_id">
              {{ s.site_nm || s.site_id }}
            </option>
          </OdsSelect>
        </OdsFormField>

        <OdsInput
          v-model="obsTitle"
          label="제목"
          variant="form"
          required
          placeholder="예: 잎 반점 관찰"
        />

        <OdsFormField
          label="관찰 내용"
          required
          hint="현장에서 본 증상·상황을 적어 주세요. AI 분석을 위한 데이터 수집 단계이며, 장기적으로 AI 추천 정확도 향상에도 도움이 됩니다."
        >
          <textarea
            v-model="obsContent"
            class="textarea"
            rows="4"
            placeholder="현장에서 본 증상을 적어 주세요"
            required
          />
        </OdsFormField>

        <p v-if="obsId" class="hint" role="status">
          <template v-if="isEditCompleted">
            수정 중 · {{ obsId }} (저장 후 사진 단계에서 「수정 완료」를 눌러 주세요)
          </template>
          <template v-else>
            임시 저장됨 · {{ obsId }} (다시 저장해도 같은 번호를 사용합니다)
          </template>
        </p>
        <p v-if="errorMessage" class="error" role="alert">{{ errorMessage }}</p>
      </form>
    </main>

    <div v-if="!loading" class="footer-actions">
      <OdsButton
        variant="secondary"
        type="button"
        :disabled="saving"
        :block="false"
        class="footer-btn"
        @click="onCancel"
      >
        취소
      </OdsButton>
      <OdsButton
        variant="primary"
        type="submit"
        form="obs-basic-form"
        :disabled="!canSubmit"
        :block="false"
        class="footer-btn"
      >
        {{ saving ? '저장 중…' : '다음 · 사진' }}
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
  max-width: 480px;
  margin: 0 auto;
  padding: var(--ods-space-16) var(--ods-page-padding-x) var(--ods-space-24);
}
.top {
  margin-top: var(--ods-space-8);
}
.title {
  margin: 0;
  font: var(--ods-font-title-1);
  color: var(--ods-color-text);
}
.steps {
  display: flex;
  gap: var(--ods-space-8);
  margin: var(--ods-space-16) 0;
  flex-wrap: wrap;
}
.step {
  font: var(--ods-font-caption);
  font-weight: 700;
  color: var(--ods-color-gray-500);
  padding: var(--ods-space-4) var(--ods-space-8);
  border-radius: var(--ods-radius-badge);
  background: var(--ods-color-white);
  border: 1px solid var(--ods-color-border);
}
.step--active {
  /* 진행 Step: 저채도 Amber (주 액션 Green과 분리) */
  color: var(--ods-color-gray-900);
  background: color-mix(in srgb, var(--ods-color-accent) 70%, white);
  border-color: color-mix(in srgb, var(--ods-color-caution) 40%, var(--ods-color-accent));
}
.step--muted {
  opacity: 0.55;
}
.form {
  display: flex;
  flex-direction: column;
  gap: var(--ods-form-field-gap);
  padding: var(--ods-space-16);
  background: var(--ods-color-white);
  border: 1px solid var(--ods-color-border);
  border-radius: var(--ods-radius-card);
  box-shadow: var(--ods-shadow-card);
}
/* 관찰 대상: 라벨·칩을 한 묶음으로 (필드 간 section gap은 form gap 유지) */
:deep(.field-target) {
  gap: var(--ods-space-4);
}
.date-field {
  position: relative;
  min-width: 0;
}
.date-field__display {
  box-sizing: border-box;
  display: flex;
  align-items: center;
  width: 100%;
  min-height: var(--ods-control-height);
  padding: 0 var(--ods-space-16);
  border: 1px solid var(--ods-color-border);
  border-radius: var(--ods-radius-button);
  background: var(--ods-color-white);
  font: var(--ods-font-form-value);
  color: var(--ods-color-text);
  text-align: left;
  cursor: pointer;
}
.date-field__display:disabled {
  background: var(--ods-color-gray-100);
  color: var(--ods-color-gray-500);
  cursor: not-allowed;
}
.date-field__native {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  opacity: 0;
  pointer-events: none;
  border: 0;
}
.textarea {
  width: 100%;
  box-sizing: border-box;
  min-height: 108px;
  padding: var(--ods-space-12) var(--ods-space-16);
  border: 1px solid var(--ods-color-border);
  border-radius: var(--ods-radius-button);
  font: var(--ods-font-form-value);
  color: var(--ods-color-text);
  background: var(--ods-color-white);
  resize: vertical;
}
.textarea::placeholder {
  font: var(--ods-font-form-placeholder);
  color: var(--ods-color-gray-500);
}
.hint {
  margin: 0;
  font: var(--ods-font-form-help);
  color: var(--ods-color-ai);
}
.error {
  margin: 0;
  font: var(--ods-font-form-help);
  font-weight: 600;
  color: var(--ods-color-danger);
}
.status {
  font: var(--ods-font-form-help);
  color: var(--ods-color-text-secondary);
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
  min-height: 48px;
}
</style>
