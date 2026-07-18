<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'

import { completeObservation, fetchObservationDetail } from '@/api/observations'
import { ApiClientError } from '@/api/client'
import OdsAppBar from '@/components/ods/OdsAppBar.vue'
import OdsBottomNav from '@/components/ods/OdsBottomNav.vue'
import OdsButton from '@/components/ods/OdsButton.vue'
import OdsCard from '@/components/ods/OdsCard.vue'
import AiAnalysisPanel from '@/views/observation/components/AiAnalysisPanel.vue'
import PhotoPanel from '@/views/observation/components/PhotoPanel.vue'
import { OBS_TARGET_FRUIT_CD } from '@/composables/constants/app'
import { clearObsDraft } from '@/composables/obsDraft'
import { useAppStore } from '@/composables/stores/app'
import type { ObservationAiAnalysisResponse, ObservationPhotoItem } from '@/types/observation'

const route = useRoute()
const router = useRouter()
const store = useAppStore()
const { farmCd, farm } = storeToRefs(store)

const obsId = computed(() => String(route.params.obsId || '').trim())
/** 기본정보 → 사진 마법사 진입 (신규 DRAFT 또는 상세 수정) */
const fromWizard = computed(() => String(route.query.from || '') === 'new')
const ready = ref(false)
const finishing = ref(false)
const errorMessage = ref('')
const statusMessage = ref('')
const obsStatus = ref('')
const targetTypeCd = ref('')
const photoIds = ref<string[]>([])
const aiStatus = ref('')

const isDraft = computed(() => obsStatus.value === 'DRAFT')
const isFruitObs = computed(
  () => String(targetTypeCd.value || '').trim() === OBS_TARGET_FRUIT_CD,
)
/** 신규 등록: 최종 완료 / 이미 완료된 건 수정: 수정 완료 */
const showFinish = computed(() => Boolean(obsId.value) && (isDraft.value || fromWizard.value))
const finishLabel = computed(() => {
  if (isFruitObs.value && fromWizard.value) return '다음 (열매측정)'
  return isDraft.value ? '최종 완료' : '수정 완료'
})
const backToBasic = computed(() => fromWizard.value && Boolean(obsId.value))

async function loadStatus() {
  if (!obsId.value) {
    obsStatus.value = ''
    targetTypeCd.value = ''
    return
  }
  try {
    const d = await fetchObservationDetail(farmCd.value, obsId.value)
    obsStatus.value = String(d.observation_status || 'DRAFT').toUpperCase()
    targetTypeCd.value = String(d.target_type_cd || '').trim()
  } catch {
    obsStatus.value = ''
    targetTypeCd.value = ''
  }
}

onMounted(async () => {
  if (!farm.value) {
    await store.refreshAll()
  }
  await loadStatus()
  ready.value = true
})

watch(obsId, () => {
  void loadStatus()
})

function goDetail() {
  if (!obsId.value) {
    void router.push({ name: 'observation' })
    return
  }
  void router.push({
    name: 'observation-detail',
    params: { obsId: obsId.value },
  })
}

function goBack() {
  if (backToBasic.value) {
    void router.push({
      name: 'observation-new',
      query: { obs_id: obsId.value },
    })
    return
  }
  if (obsStatus.value === 'COMPLETED' && obsId.value) {
    goDetail()
    return
  }
  void router.push({ name: 'observation' })
}

async function onFinish() {
  if (!obsId.value || finishing.value || !showFinish.value) return

  // 과실 등록 마법사: 사진 다음 → 열매측정
  if (isFruitObs.value && fromWizard.value) {
    void router.push({
      name: 'observation-fruit',
      params: { obsId: obsId.value },
      query: { from: 'new' },
    })
    return
  }

  // 이미 COMPLETED 건 수정 흐름: API complete 없이 상세로 복귀
  if (!isDraft.value) {
    clearObsDraft(farmCd.value)
    goDetail()
    return
  }

  finishing.value = true
  errorMessage.value = ''
  statusMessage.value = '완료 처리 중…'
  try {
    await completeObservation(farmCd.value, obsId.value)
    clearObsDraft(farmCd.value)
    obsStatus.value = 'COMPLETED'
    statusMessage.value = '관찰이 완료되었습니다.'
    void router.push({ name: 'observation' })
  } catch (err) {
    statusMessage.value = ''
    errorMessage.value =
      err instanceof ApiClientError ? err.message : '완료 처리에 실패했습니다.'
  } finally {
    finishing.value = false
  }
}

function onPhotosChanged(photos: ObservationPhotoItem[]) {
  photoIds.value = photos.map((p) => p.photo_id)
}

function onAiUpdated(res: ObservationAiAnalysisResponse) {
  aiStatus.value = res.ai_status || ''
}
</script>

<template>
  <div class="page">
    <main class="content">
      <OdsAppBar show-back @back="goBack" />

      <header class="top">
        <h1 class="title">관찰 사진</h1>
        <p class="sub">{{ obsId || '—' }}</p>
      </header>

      <nav v-if="fromWizard" class="steps" aria-label="등록 단계">
        <template v-if="isFruitObs">
          <span class="step">1. 기본정보</span>
          <span class="step step--active">2. 사진</span>
          <span class="step">3. 열매</span>
          <span class="step">4. 완료</span>
        </template>
        <template v-else>
          <span class="step">1. 기본정보</span>
          <span class="step step--active">2. 사진</span>
          <span class="step">3. 완료</span>
        </template>
      </nav>

      <p v-if="!obsId" class="error" role="alert">관찰 번호가 없습니다.</p>
      <template v-else-if="ready">
        <PhotoPanel
          :farm-cd="farmCd"
          :obs-id="obsId"
          variant="scr004"
          @changed="onPhotosChanged"
        />
        <OdsCard v-if="!isFruitObs" class="ai-card" aria-label="AI 분석">
          <h2 class="ai-title">AI 분석</h2>
          <AiAnalysisPanel
            :farm-cd="farmCd"
            :obs-id="obsId"
            :photo-ids="photoIds"
            crop-name="배"
            @updated="onAiUpdated"
          />
        </OdsCard>
      </template>

      <p v-if="statusMessage" class="status" role="status">{{ statusMessage }}</p>
      <p v-if="errorMessage" class="error" role="alert">{{ errorMessage }}</p>
    </main>

    <div v-if="obsId" class="footer-actions">
      <OdsButton
        variant="secondary"
        type="button"
        :block="false"
        class="footer-btn"
        @click="goBack"
      >
        {{ backToBasic ? '기본정보 수정' : obsStatus === 'COMPLETED' ? '상세' : '목록' }}
      </OdsButton>
      <OdsButton
        v-if="showFinish"
        variant="primary"
        :disabled="finishing"
        :block="false"
        class="footer-btn"
        @click="onFinish"
      >
        {{ finishing ? '처리 중…' : finishLabel }}
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
.sub {
  margin: var(--ods-space-4) 0 0;
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
  word-break: break-all;
}
.steps {
  display: flex;
  gap: var(--ods-space-8);
  margin: 0 0 var(--ods-space-16);
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
.error {
  color: var(--ods-color-danger);
  font: var(--ods-font-body-2);
}
.status {
  margin: var(--ods-space-12) 0 0;
  font: var(--ods-font-body-2);
  color: var(--ods-color-primary);
  font-weight: 600;
}
.ai-card {
  margin-top: var(--ods-space-16);
}
.ai-title {
  margin: 0 0 var(--ods-space-8);
  font: var(--ods-font-title-3, var(--ods-font-body-1));
  font-weight: 700;
  color: var(--ods-color-text);
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
