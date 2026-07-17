<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'

import { completeObservation, fetchObservationDetail } from '@/api/observations'
import { ApiClientError } from '@/api/client'
import OdsBottomNav from '@/components/ods/OdsBottomNav.vue'
import OdsButton from '@/components/ods/OdsButton.vue'
import PhotoPanel from '@/views/observation/components/PhotoPanel.vue'
import { clearObsDraft } from '@/composables/obsDraft'
import { useAppStore } from '@/composables/stores/app'

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

const isDraft = computed(() => obsStatus.value === 'DRAFT')
/** 신규 등록: 최종 완료 / 이미 완료된 건 수정: 수정 완료 */
const showFinish = computed(() => Boolean(obsId.value) && (isDraft.value || fromWizard.value))
const finishLabel = computed(() => (isDraft.value ? '최종 완료' : '수정 완료'))
const backToBasic = computed(() => fromWizard.value && Boolean(obsId.value))

async function loadStatus() {
  if (!obsId.value) {
    obsStatus.value = ''
    return
  }
  try {
    const d = await fetchObservationDetail(farmCd.value, obsId.value)
    obsStatus.value = String(d.observation_status || 'DRAFT').toUpperCase()
  } catch {
    obsStatus.value = ''
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
</script>

<template>
  <div class="page">
    <main class="content">
      <header class="top">
        <button type="button" class="back" @click="goBack">
          {{ backToBasic ? '← 기본정보' : obsStatus === 'COMPLETED' ? '← 상세' : '← 목록' }}
        </button>
        <h1 class="title">관찰 사진</h1>
        <p class="sub">
          {{ farm?.farm_nm || farmCd }} · {{ obsId || '—' }}
        </p>
      </header>

      <nav v-if="fromWizard" class="steps" aria-label="등록 단계">
        <span class="step">1. 기본정보</span>
        <span class="step step--active">2. 사진</span>
        <span class="step">3. 완료</span>
      </nav>

      <p v-if="!obsId" class="error" role="alert">관찰 번호가 없습니다.</p>
      <PhotoPanel v-else-if="ready" :farm-cd="farmCd" :obs-id="obsId" />

      <p v-if="statusMessage" class="status" role="status">{{ statusMessage }}</p>
      <p v-if="errorMessage" class="error" role="alert">{{ errorMessage }}</p>

      <div v-if="obsId" class="footer">
        <button type="button" class="link" @click="goBack">
          {{ backToBasic ? '기본정보 수정' : obsStatus === 'COMPLETED' ? '상세' : '목록' }}
        </button>
        <OdsButton
          v-if="showFinish"
          variant="primary"
          :disabled="finishing"
          :block="false"
          @click="onFinish"
        >
          {{ finishing ? '처리 중…' : finishLabel }}
        </OdsButton>
      </div>
    </main>
    <OdsBottomNav />
  </div>
</template>

<style scoped>
.page {
  min-height: 100dvh;
  background: var(--ods-color-bg-muted);
  padding-bottom: calc(80px + env(safe-area-inset-bottom));
}
.content {
  max-width: 480px;
  margin: 0 auto;
  padding: var(--ods-space-16) var(--ods-page-padding-x) var(--ods-space-24);
}
.top {
  margin-bottom: var(--ods-space-16);
}
.back {
  border: none;
  background: transparent;
  padding: 0;
  font: var(--ods-font-body-2);
  font-weight: 700;
  color: var(--ods-color-primary);
  cursor: pointer;
  min-height: 44px;
}
.title {
  margin: var(--ods-space-8) 0 0;
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
  color: var(--ods-color-white);
  background: var(--ods-color-primary);
  border-color: var(--ods-color-primary);
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
.footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ods-space-12);
  margin-top: var(--ods-space-16);
}
.link {
  border: none;
  background: transparent;
  padding: 0;
  min-height: 44px;
  font: var(--ods-font-body-2);
  font-weight: 700;
  color: var(--ods-color-text-secondary);
  cursor: pointer;
}
</style>
