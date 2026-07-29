<script setup lang="ts">
/**
 * ODS 폼 가독성 레퍼런스 (SCR-002).
 * @see docs/ODS/MOBILE_FORM_READABILITY.md — 라벨15 / 값14 / 컨트롤·하단버튼 48
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'

import { fetchCommonCodes } from '@/api/commonCodes'
import { fetchFarmSites } from '@/api/farms'
import { fetchObservationTrack } from '@/api/observationFruit'
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
  OBS_FOLLOW_UP_ROOT_TITLE_LABEL,
  OBS_SEVERITY_NORMAL_CD,
  OBS_SEVERITY_PARENT_CD,
  OBS_TARGET_FRUIT_CD,
  OBS_TARGET_PEST_CD,
} from '@/composables/constants/app'
import { formatDateKo, todayLocalIso } from '@/shared/formatDateKo'
import { clearObsDraft, writeObsDraft } from '@/composables/obsDraft'
import { useAppStore } from '@/composables/stores/app'
import type { CommonCodeItem } from '@/types/commonCode'
import type { FarmSiteSummary } from '@/types/farm'

const route = useRoute()
const router = useRouter()
const store = useAppStore()
const { farmCd, farm } = storeToRefs(store)

const sites = ref<FarmSiteSummary[]>([])
const severityCodes = ref<CommonCodeItem[]>([])
const obsId = ref('')
const obsDt = ref(todayLocalIso())
/** 신규 진입 시 미선택('') — 병해충/과실 필수 선택 */
const targetTypeCd = ref('')
const siteId = ref('')
const severityCd = ref(OBS_SEVERITY_NORMAL_CD)
const obsTitle = ref('')
const obsContent = ref('')
/** 후속 관찰: 직전 obs_id */
const parentObsId = ref('')
const zoneNm = ref('')
const rowNo = ref('')
const treeNo = ref('')
const branchNo = ref('')
const sampleNo = ref('')

const loading = ref(true)
const saving = ref(false)
const errorMessage = ref('')
/** DRAFT | COMPLETED — 취소/안내 문구용 */
const obsStatus = ref('')
const datePicker = ref<HTMLInputElement | null>(null)

const farmLabel = computed(() => farm.value?.farm_nm || farmCd.value)
const obsDtLabel = computed(() => formatDateKo(obsDt.value))
const todayMax = computed(() => todayLocalIso())
const OBS_DT_FUTURE_MSG = '관찰일자는 오늘까지만 허용됩니다.'
const fromDetail = computed(() => String(route.query.from || '') === 'detail')
const isEditCompleted = computed(
  () => fromDetail.value || obsStatus.value === 'COMPLETED',
)
/** 추적 관찰(신규·수정): 부모 연결 건 — 일자·내용만 편집 */
const isFollowUpObs = computed(() => Boolean(String(parentObsId.value || '').trim()))
/** 카드 타이틀용 1차(최초) 관찰명 */
const followUpRootTitle = computed(() => {
  const raw = String(obsTitle.value || '').trim()
  if (!raw) return ''
  return stripTrackSuffix(raw)
})
const followUpCardTitle = computed(() => {
  const name = followUpRootTitle.value
  if (!name) return ''
  return `${OBS_FOLLOW_UP_ROOT_TITLE_LABEL} : ${name}`
})
const canSubmit = computed(() => {
  if (saving.value) return false
  if (!obsDt.value || !obsContent.value.trim()) return false
  if (isFollowUpObs.value) {
    return Boolean(siteId.value && targetTypeCd.value && obsTitle.value.trim())
  }
  if (!siteId.value || !targetTypeCd.value || !severityCd.value) return false
  return Boolean(obsTitle.value.trim())
})

const targetOptions = [
  { value: OBS_TARGET_PEST_CD, label: '병해충' },
  { value: OBS_TARGET_FRUIT_CD, label: '과실' },
]

function resetBlankForm() {
  obsId.value = ''
  obsDt.value = todayLocalIso()
  targetTypeCd.value = ''
  siteId.value = sites.value.length === 1 ? sites.value[0].site_id : ''
  severityCd.value = OBS_SEVERITY_NORMAL_CD
  obsTitle.value = ''
  obsContent.value = ''
  parentObsId.value = ''
  zoneNm.value = ''
  rowNo.value = ''
  treeNo.value = ''
  branchNo.value = ''
  sampleNo.value = ''
  obsStatus.value = ''
  errorMessage.value = ''
  clearObsDraft(farmCd.value)
}

function resolveInitialObsId(): string {
  // 신규(+ 관찰하기)은 빈 폼. 복원은 ?obs_id= 가 있을 때만 (뒤로가기·사진 단계 복귀)
  return String(route.query.obs_id || '').trim()
}

function resolveParentObsId(): string {
  return String(route.query.parent_obs_id || '').trim()
}

/** `{기본제목} N차` / 구형 `N차추적` 접미 제거 */
function stripTrackSuffix(title: string): string {
  const raw = String(title || '').trim()
  const stripped = raw
    .replace(/\s*\d+차추적\s*$/u, '')
    .replace(/\s*\d+차\s*$/u, '')
    .trim()
  return stripped || raw || '과실 관찰'
}

/** 1차=최초, 추적은 2차부터. 다음 차수 = 현재 건수 + 1 */
async function buildFollowUpTitle(parentId: string, fallbackTitle: string): Promise<string> {
  const base = stripTrackSuffix(fallbackTitle)
  try {
    const track = await fetchObservationTrack(farmCd.value, parentId)
    const count = Math.max(1, Number(track.track_count || track.items?.length || 1))
    const nextRound = count + 1
    const rootTitle = stripTrackSuffix(track.items?.[0]?.obs_title || base)
    return `${rootTitle} ${nextRound}차`
  } catch {
    return `${base} 2차`
  }
}

async function loadSites() {
  try {
    sites.value = await fetchFarmSites(farmCd.value, true)
  } catch {
    sites.value = []
  }
}

async function loadSeverityCodes() {
  try {
    severityCodes.value = await fetchCommonCodes(
      farmCd.value,
      OBS_SEVERITY_PARENT_CD,
    )
  } catch {
    severityCodes.value = []
  }
  if (
    severityCd.value &&
    severityCodes.value.length &&
    !severityCodes.value.some((c) => c.code_cd === severityCd.value)
  ) {
    severityCd.value = OBS_SEVERITY_NORMAL_CD
  }
}

async function restoreIfNeeded() {
  const id = resolveInitialObsId()
  const parentId = resolveParentObsId()
  if (!id && parentId) {
    try {
      const parent = await fetchObservationDetail(farmCd.value, parentId)
      parentObsId.value = parent.obs_id
      obsDt.value = todayLocalIso()
      targetTypeCd.value =
        parent.target_type_cd === OBS_TARGET_FRUIT_CD
          ? OBS_TARGET_FRUIT_CD
          : parent.target_type_cd === OBS_TARGET_PEST_CD
            ? OBS_TARGET_PEST_CD
            : OBS_TARGET_FRUIT_CD
      siteId.value = parent.site_id || ''
      severityCd.value = parent.severity_cd || OBS_SEVERITY_NORMAL_CD
      zoneNm.value = parent.zone_nm || ''
      rowNo.value = parent.row_no || ''
      treeNo.value = parent.tree_no || ''
      branchNo.value = parent.branch_no || ''
      sampleNo.value = parent.sample_no || ''
      obsTitle.value = await buildFollowUpTitle(
        parent.obs_id,
        parent.obs_title || '과실 관찰',
      )
      obsContent.value = '추적 관찰'
      obsStatus.value = ''
      obsId.value = ''
      clearObsDraft(farmCd.value)
    } catch {
      resetBlankForm()
      errorMessage.value = '추적 관찰의 원본을 불러오지 못했습니다.'
    }
    return
  }
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
    severityCd.value = detail.severity_cd || OBS_SEVERITY_NORMAL_CD
    zoneNm.value = detail.zone_nm || ''
    rowNo.value = detail.row_no || ''
    treeNo.value = detail.tree_no || ''
    branchNo.value = detail.branch_no || ''
    sampleNo.value = detail.sample_no || ''
    obsTitle.value = detail.obs_title || ''
    obsContent.value = detail.obs_content || ''
    parentObsId.value = detail.parent_obs_id || ''
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
  const next = (ev.target as HTMLInputElement).value
  if (next && next > todayLocalIso()) {
    obsDt.value = todayLocalIso()
    errorMessage.value = OBS_DT_FUTURE_MSG
    return
  }
  obsDt.value = next
  if (errorMessage.value === OBS_DT_FUTURE_MSG) errorMessage.value = ''
}

async function onNext() {
  if (!isFollowUpObs.value && !targetTypeCd.value) {
    errorMessage.value = '관찰 대상을 선택해 주세요.'
    return
  }
  if (!canSubmit.value) {
    errorMessage.value = isFollowUpObs.value
      ? '필수 항목을 확인해 주세요. (관찰일자·관찰 내용)'
      : '필수 항목을 확인해 주세요. (관찰일자·대상·필지·위험도·제목·관찰 내용)'
    return
  }
  if (!severityCd.value) {
    errorMessage.value = '위험도를 선택해 주세요.'
    return
  }
  if (obsDt.value > todayLocalIso()) {
    errorMessage.value = OBS_DT_FUTURE_MSG
    return
  }
  saving.value = true
  errorMessage.value = ''
  const payload = {
    obs_dt: obsDt.value,
    target_type_cd: targetTypeCd.value,
    site_id: siteId.value,
    severity_cd: severityCd.value,
    obs_title: obsTitle.value.trim() || null,
    obs_content: obsContent.value.trim() || null,
    parent_obs_id: parentObsId.value || null,
    zone_nm: zoneNm.value.trim() || null,
    row_no: rowNo.value.trim() || null,
    tree_no: treeNo.value.trim() || null,
    branch_no: branchNo.value.trim() || null,
    sample_no: sampleNo.value.trim() || null,
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
  await loadSeverityCodes()
  await restoreIfNeeded()
  if (!obsId.value && !siteId.value && sites.value.length === 1) {
    siteId.value = sites.value[0].site_id
  }
  loading.value = false
})

// 동일 화면에서 ?obs_id / parent_obs_id 변경 시 폼 갱신
watch(
  () =>
    [
      String(route.query.obs_id || ''),
      String(route.query.parent_obs_id || ''),
    ].join('|'),
  async (key, prev) => {
    if (key === prev) return
    loading.value = true
    await restoreIfNeeded()
    if (!obsId.value && !siteId.value && sites.value.length === 1) {
      siteId.value = sites.value[0].site_id
    }
    loading.value = false
  },
)
</script>

<template>
  <div class="page">
    <main class="content ods-page-content">
      <OdsAppBar show-back back-mode="emit" @back="onCancel" />

      <nav class="steps" aria-label="등록 단계">
        <template v-if="targetTypeCd === OBS_TARGET_FRUIT_CD">
          <span class="step step--active">1. 기본정보</span>
          <span class="step">2. 사진</span>
          <span class="step">3. 열매</span>
          <span class="step step--muted">4. 완료</span>
        </template>
        <template v-else>
          <span class="step step--active">1. 기본정보</span>
          <span class="step">2. 사진</span>
          <span class="step step--muted">3. 완료</span>
        </template>
      </nav>

      <p v-if="loading" class="status" role="status">불러오는 중…</p>

      <form
        v-else
        id="obs-basic-form"
        class="form"
        @submit.prevent="onNext"
      >
        <h2 v-if="isFollowUpObs && followUpCardTitle" class="form-card-title">
          {{ followUpCardTitle }}
        </h2>

        <div class="form__fields">
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
              :max="todayMax"
              :disabled="saving"
              required
              tabindex="-1"
              aria-hidden="true"
              @input="onObsDtInput"
            >
          </div>
        </OdsFormField>

        <template v-if="!isFollowUpObs">
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

          <div class="field-row">
            <OdsFormField label="필지" required class="field-row__item">
              <OdsSelect v-model="siteId" variant="form" required>
                <option value="" disabled>필지 선택</option>
                <option v-for="s in sites" :key="s.site_id" :value="s.site_id">
                  {{ s.site_nm || s.site_id }}
                </option>
              </OdsSelect>
            </OdsFormField>

            <OdsFormField label="위험도" required class="field-row__item">
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
          </div>

          <OdsInput
            v-model="obsTitle"
            label="제목"
            variant="form"
            required
            placeholder="예: 잎 반점 관찰"
          />
        </template>

        <OdsFormField
          label="관찰 내용"
          required
          :hint="
            isFollowUpObs
              ? '이번 추적에서 본 변화를 적어 주세요.'
              : '현장에서 본 증상·상황을 적어 주세요. AI 분석을 위한 데이터 수집 단계이며, 장기적으로 AI 추천 정확도 향상에도 도움이 됩니다.'
          "
        >
          <textarea
            v-model="obsContent"
            class="textarea"
            rows="4"
            :placeholder="isFollowUpObs ? '추적 관찰 내용을 적어 주세요' : '현장에서 본 증상을 적어 주세요'"
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
        </div>
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
  /* AppBar↔다음 블록: ODS 공통 (--ods-appbar-content-gap: 0 + page gap 16) */
  --ods-page-content-gap: var(--ods-space-16);
}
.form-card-title {
  margin: 0 0 var(--ods-space-8);
  font: var(--ods-font-form-label);
  color: var(--ods-color-primary);
  word-break: break-word;
}
.form__fields {
  display: flex;
  flex-direction: column;
  gap: var(--ods-form-field-gap);
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
  padding: var(--ods-card-padding, var(--ods-space-16));
  background: var(--ods-color-white);
  border: 1px solid var(--ods-color-border);
  border-radius: var(--ods-radius-card);
  box-shadow: var(--ods-shadow-card);
}
/* 관찰 대상: 라벨·칩을 한 묶음으로 (필드 간 section gap은 form gap 유지) */
:deep(.field-target) {
  gap: var(--ods-space-4);
}
/* 1행 2열 — 필지 | 위험도 */
.field-row {
  display: flex;
  align-items: stretch;
  gap: var(--ods-space-8);
  min-width: 0;
}
.field-row__item {
  flex: 1 1 0;
  min-width: 0;
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
  height: var(--ods-control-height);
  min-height: var(--ods-control-height);
  max-height: var(--ods-control-height);
  padding: 0 var(--ods-space-16);
  border: 1px solid var(--ods-color-border);
  border-radius: var(--ods-radius-button);
  background: var(--ods-color-white);
  font: var(--ods-font-form-value);
  line-height: 1.2;
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
  max-width: var(--ods-page-content-max, 480px);
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
