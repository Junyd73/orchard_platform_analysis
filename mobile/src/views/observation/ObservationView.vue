<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'

import { fetchFarmSites } from '@/api/farms'
import {
  cancelObservationDraft,
  fetchObservationDrafts,
  fetchObservationSummary,
  fetchObservations,
} from '@/api/observations'
import { ApiClientError } from '@/api/client'
import OdsAppBar from '@/components/ods/OdsAppBar.vue'
import OdsBottomNav from '@/components/ods/OdsBottomNav.vue'
import ObservationDraftsPanel from '@/views/observation/components/ObservationDraftsPanel.vue'
import ObservationFilters from '@/views/observation/components/ObservationFilters.vue'
import ObservationHero from '@/views/observation/components/ObservationHero.vue'
import ObservationListCard from '@/views/observation/components/ObservationListCard.vue'
import ObservationSummaryCards from '@/views/observation/components/ObservationSummaryCards.vue'
import { clearObsDraft } from '@/composables/obsDraft'
import { useAppStore } from '@/composables/stores/app'
import type { FarmSiteSummary } from '@/types/farm'
import type {
  ObservationDraftItem,
  ObservationListItem,
  ObservationSummary,
} from '@/types/observation'

const store = useAppStore()
const router = useRouter()
const route = useRoute()
const { farmCd, farm } = storeToRefs(store)

const loading = ref(true)
const summaryLoading = ref(true)
const draftBusy = ref(false)
const errorMessage = ref('')
const toastMessage = ref('')
const summary = ref<ObservationSummary | null>(null)
const items = ref<ObservationListItem[]>([])
const drafts = ref<ObservationDraftItem[]>([])
const sites = ref<FarmSiteSummary[]>([])
const listAnchor = ref<HTMLElement | null>(null)
const showFabChoice = ref(false)

const siteId = ref('')
const keyword = ref('')
const sort = ref<'obs_dt_desc' | 'obs_dt_asc'>('obs_dt_desc')

const appliedKeyword = ref('')
const appliedSiteId = ref('')

const hasFilter = computed(
  () => Boolean(appliedKeyword.value.trim()) || Boolean(appliedSiteId.value),
)

const resultStatus = computed(() => {
  if (loading.value) {
    return hasFilter.value || keyword.value.trim() || siteId.value
      ? '검색 중…'
      : '목록 불러오는 중…'
  }
  if (errorMessage.value) return ''
  if (hasFilter.value && items.value.length === 0) {
    const parts: string[] = []
    if (appliedKeyword.value) parts.push(`「${appliedKeyword.value}」`)
    if (appliedSiteId.value) {
      const site = sites.value.find((s) => s.site_id === appliedSiteId.value)
      parts.push(site?.site_nm || appliedSiteId.value)
    }
    return `${parts.join(' · ')} 검색 결과가 없습니다.`
  }
  if (!items.value.length) return '표시할 관찰이 없습니다.'
  if (hasFilter.value) {
    const kw = appliedKeyword.value ? `「${appliedKeyword.value}」 ` : ''
    return `${kw}검색 결과 ${items.value.length}건`
  }
  return `최근 관찰 ${items.value.length}건`
})

async function loadSites() {
  try {
    sites.value = await fetchFarmSites(farmCd.value, true)
  } catch {
    sites.value = []
  }
}

async function loadSummary() {
  summaryLoading.value = true
  try {
    summary.value = await fetchObservationSummary(farmCd.value)
  } catch (err) {
    summary.value = null
    if (!errorMessage.value) {
      errorMessage.value =
        err instanceof ApiClientError ? err.message : '요약을 불러오지 못했습니다.'
    }
  } finally {
    summaryLoading.value = false
  }
}

async function loadDrafts() {
  try {
    drafts.value = await fetchObservationDrafts(farmCd.value)
  } catch {
    drafts.value = []
  }
}

async function loadList() {
  loading.value = true
  errorMessage.value = ''
  const kw = keyword.value.trim()
  const sid = siteId.value
  try {
    items.value = await fetchObservations(farmCd.value, {
      site_id: sid || undefined,
      keyword: kw || undefined,
      sort: sort.value,
      limit: 50,
    })
    appliedKeyword.value = kw
    appliedSiteId.value = sid
    await nextTick()
    listAnchor.value?.scrollIntoView?.({ behavior: 'smooth', block: 'start' })
  } catch (err) {
    items.value = []
    errorMessage.value =
      err instanceof ApiClientError ? err.message : '관찰 목록을 불러오지 못했습니다.'
  } finally {
    loading.value = false
  }
}

async function refreshAll() {
  await Promise.all([loadSummary(), loadList(), loadDrafts()])
}

function goNewBlank() {
  clearObsDraft(farmCd.value)
  showFabChoice.value = false
  void router.push({ name: 'observation-new' })
}

function goResume(obsId: string) {
  showFabChoice.value = false
  void router.push({
    name: 'observation-new',
    query: { obs_id: obsId },
  })
}

function onFabClick() {
  if (drafts.value.length > 0) {
    showFabChoice.value = true
    return
  }
  goNewBlank()
}

function onResumeDraft(obsId: string) {
  goResume(obsId)
}

async function onCancelDraft(obsId: string) {
  const ok = window.confirm(
    '작성 중인 기본정보와 사진이 삭제됩니다.\n계속하시겠습니까?',
  )
  if (!ok) return
  draftBusy.value = true
  try {
    await cancelObservationDraft(farmCd.value, obsId)
    clearObsDraft(farmCd.value)
    await refreshAll()
  } catch (err) {
    errorMessage.value =
      err instanceof ApiClientError ? err.message : '작성 취소에 실패했습니다.'
  } finally {
    draftBusy.value = false
  }
}

onMounted(async () => {
  if (!farm.value) {
    await store.refreshAll()
  }
  await loadSites()
  await refreshAll()
  const toast = String(route.query.toast || '').trim()
  if (toast) {
    toastMessage.value = toast
    void router.replace({ name: 'observation' })
    window.setTimeout(() => {
      toastMessage.value = ''
    }, 3200)
  }
})
</script>

<template>
  <div class="page">
    <OdsAppBar />
    <main class="content">
      <ObservationHero :farm-name="farm?.farm_nm || undefined" />

      <ObservationSummaryCards :summary="summary" :loading="summaryLoading" />

      <ObservationDraftsPanel
        :drafts="drafts"
        :busy="draftBusy"
        @resume="onResumeDraft"
        @cancel="onCancelDraft"
      />

      <h2 class="section-title">최근 생육관찰</h2>

      <ObservationFilters
        v-model:site-id="siteId"
        v-model:keyword="keyword"
        v-model:sort="sort"
        :sites="sites"
        :searching="loading"
        @apply="loadList"
      />

      <div ref="listAnchor" class="list-anchor">
        <p v-if="errorMessage" class="error" role="alert">{{ errorMessage }}</p>
        <p v-else class="status" :class="{ 'status--loading': loading }" role="status">
          {{ resultStatus }}
        </p>

        <div v-if="!errorMessage && items.length" class="list" :aria-busy="loading">
          <ObservationListCard v-for="row in items" :key="row.obs_id" :item="row" />
        </div>
      </div>
    </main>

    <button type="button" class="fab" aria-label="관찰하기" @click="onFabClick">
      + 관찰하기
    </button>

    <p v-if="toastMessage" class="toast" role="status">{{ toastMessage }}</p>

    <div
      v-if="showFabChoice"
      class="sheet"
      role="dialog"
      aria-modal="true"
      aria-label="작성 중 관찰 선택"
    >
      <div class="sheet__panel">
        <p class="sheet__title">작성 중인 관찰이 있습니다</p>
        <p class="sheet__desc">
          이어서 작성하거나 새 관찰을 시작할 수 있습니다. 기존 초안은 자동으로 이어쓰거나 삭제하지 않습니다.
        </p>
        <button
          type="button"
          class="sheet__btn sheet__btn--primary"
          @click="goResume(drafts[0].obs_id)"
        >
          ① 이어쓰기
        </button>
        <button type="button" class="sheet__btn" @click="goNewBlank">② 새 관찰</button>
        <button type="button" class="sheet__btn sheet__btn--ghost" @click="showFabChoice = false">
          닫기
        </button>
      </div>
    </div>

    <OdsBottomNav />
  </div>
</template>

<style scoped>
.page {
  min-height: 100dvh;
  background: var(--ods-color-bg-muted);
  padding-bottom: calc(140px + env(safe-area-inset-bottom));
}
.content {
  max-width: 480px;
  margin: 0 auto;
  padding: var(--ods-space-16) var(--ods-page-padding-x) var(--ods-space-24);
}
.section-title {
  margin: var(--ods-space-16) 0 var(--ods-space-8);
  font: var(--ods-font-headline);
  color: var(--ods-color-text);
}
.list-anchor {
  margin-top: var(--ods-space-8);
}
.status {
  margin: 0 0 var(--ods-space-8);
  font: var(--ods-font-body-2);
  color: var(--ods-color-text-secondary);
}
.status--loading {
  color: var(--ods-color-ai);
  font-weight: 600;
}
.error {
  margin: 0 0 var(--ods-space-8);
  font: var(--ods-font-body-2);
  color: var(--ods-color-danger);
}
.list {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-12);
}
.fab {
  position: fixed;
  right: max(16px, env(safe-area-inset-right));
  bottom: calc(72px + env(safe-area-inset-bottom));
  z-index: 40;
  min-height: 48px;
  padding: 0 18px;
  border: none;
  border-radius: 999px;
  background: var(--ods-color-primary);
  color: var(--ods-color-white);
  font: var(--ods-font-body-1);
  font-weight: 700;
  box-shadow: var(--ods-shadow-card);
  cursor: pointer;
}
.sheet {
  position: fixed;
  inset: 0;
  z-index: 60;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: flex-end;
  justify-content: center;
}
.sheet__panel {
  width: 100%;
  max-width: 480px;
  background: var(--ods-color-white);
  border-radius: 16px 16px 0 0;
  padding: var(--ods-space-16) var(--ods-space-16)
    calc(var(--ods-space-16) + env(safe-area-inset-bottom));
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-8);
}
.sheet__title {
  margin: 0;
  font: var(--ods-font-headline);
  font-weight: 700;
}
.sheet__desc {
  margin: 0 0 var(--ods-space-8);
  font: var(--ods-font-body-2);
  color: var(--ods-color-text-secondary);
}
.sheet__btn {
  min-height: 48px;
  border: 1px solid var(--ods-color-border);
  border-radius: var(--ods-radius-button);
  background: var(--ods-color-white);
  font: var(--ods-font-body-1);
  font-weight: 700;
  cursor: pointer;
}
.sheet__btn--primary {
  background: var(--ods-color-primary);
  border-color: var(--ods-color-primary);
  color: var(--ods-color-white);
}
.sheet__btn--ghost {
  border: none;
  color: var(--ods-color-text-secondary);
}
.toast {
  position: fixed;
  left: 50%;
  bottom: calc(88px + env(safe-area-inset-bottom));
  transform: translateX(-50%);
  z-index: 70;
  max-width: min(420px, calc(100vw - 32px));
  margin: 0;
  padding: 12px 16px;
  border-radius: 10px;
  background: rgba(33, 33, 33, 0.92);
  color: var(--ods-color-white);
  font: var(--ods-font-body-2);
  font-weight: 600;
  text-align: center;
  box-shadow: var(--ods-shadow-card);
}
</style>
