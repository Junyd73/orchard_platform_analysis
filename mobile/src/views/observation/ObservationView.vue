<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'

import { fetchFarmSites } from '@/api/farms'
import {
  fetchObservationDrafts,
  fetchObservations,
} from '@/api/observations'
import { ApiClientError } from '@/api/client'
import iconCamera from '@/assets/ods/scr004/icon-camera.svg'
import OdsAppBar from '@/components/ods/OdsAppBar.vue'
import OdsBottomNav from '@/components/ods/OdsBottomNav.vue'
import ObservationAiRiskSection from '@/views/observation/components/ObservationAiRiskSection.vue'
import ObservationFilters from '@/views/observation/components/ObservationFilters.vue'
import ObservationHero from '@/views/observation/components/ObservationHero.vue'
import type { ObservationHeroKpiKey } from '@/views/observation/components/ObservationHero.vue'
import ObservationListCard from '@/views/observation/components/ObservationListCard.vue'
import ObservationRecentAiSection from '@/views/observation/components/ObservationRecentAiSection.vue'
import ObservationWeekCalendar from '@/views/observation/components/ObservationWeekCalendar.vue'
import {
  aggregateObsCalendar,
  formatObsListRangeLabel,
  pastRangeStart,
  rangeFromStart,
  shiftIsoDays,
  type ObsCalDayCounts,
} from '@/views/observation/observationCalendar'
import {
  HOME_WEEK_LIMIT,
  homeWeekRange,
  isDefaultHomeWeekRange,
  LABEL_HOME_WEEK_LIST,
  mapHomeRecentAiItems,
  mapHomeRiskItems,
  summarizeHomeWeek,
} from '@/views/observation/observationHomeWeek'
import { todayIso } from '@/views/work-log/workLogConstants'
import { clearObsDraft } from '@/composables/obsDraft'
import { useAppStore } from '@/composables/stores/app'
import type { FarmSiteSummary } from '@/types/farm'
import type {
  ObservationDraftItem,
  ObservationListItem,
  ObservationSummary,
} from '@/types/observation'

const MSG_LIST_EMPTY = '표시할 관찰이 없습니다. 새 관찰을 등록해 보세요.'
const MSG_LIST_EMPTY_FILTER = '조건에 맞는 관찰이 없습니다.'
const MSG_FAB_NEW = '+ 새 관찰'

const store = useAppStore()
const router = useRouter()
const route = useRoute()
const { farmCd, farm } = storeToRefs(store)

const loading = ref(true)
const homeWeekLoading = ref(true)
const errorMessage = ref('')
const toastMessage = ref('')
const homeWeekSummary = ref<ObservationSummary | null>(null)
const homeWeekItems = ref<ObservationListItem[]>([])
const items = ref<ObservationListItem[]>([])
const drafts = ref<ObservationDraftItem[]>([])
const sites = ref<FarmSiteSummary[]>([])
const listAnchor = ref<HTMLElement | null>(null)
const showFabChoice = ref(false)

const calRangeStart = ref(pastRangeStart(todayIso()))
const calSelectedDt = ref(todayIso())
const calDays = ref<Record<string, ObsCalDayCounts>>({})
const calLoading = ref(false)
/** 관찰상세조회 — 조건(필터) 카드만 토글, 기본 감춤. 목록은 항상 표시 */
const filterOpen = ref(false)

const siteId = ref('')
const keyword = ref('')
const sort = ref<'obs_dt_desc' | 'obs_dt_asc'>('obs_dt_desc')
/** 기본·「최근」= 오늘 포함 과거 7일 */
const dateFrom = ref(pastRangeStart(todayIso()))
const dateTo = ref(todayIso())

const appliedKeyword = ref('')
const appliedSiteId = ref('')
const appliedDateFrom = ref(dateFrom.value)
const appliedDateTo = ref(dateTo.value)

const hasExtraFilter = computed(
  () =>
    Boolean(appliedKeyword.value.trim()) || Boolean(appliedSiteId.value),
)

const riskItems = computed(() =>
  mapHomeRiskItems(homeWeekItems.value, todayIso()),
)
const recentAiItems = computed(() =>
  mapHomeRecentAiItems(homeWeekItems.value, todayIso()),
)

const resultStatus = computed(() => {
  if (loading.value) {
    return hasExtraFilter.value || keyword.value.trim() || siteId.value
      ? '검색 중…'
      : '목록 불러오는 중…'
  }
  if (errorMessage.value) return ''
  const from = appliedDateFrom.value || pastRangeStart(todayIso())
  const to = appliedDateTo.value || todayIso()
  const weekTitle = isDefaultHomeWeekRange(from, to, todayIso())
    ? LABEL_HOME_WEEK_LIST
    : formatObsListRangeLabel(from, to)
  if (!items.value.length) {
    return hasExtraFilter.value ? MSG_LIST_EMPTY_FILTER : MSG_LIST_EMPTY
  }
  if (hasExtraFilter.value && appliedKeyword.value) {
    return `「${appliedKeyword.value}」 ${weekTitle}`
  }
  return weekTitle
})

async function loadSites() {
  try {
    sites.value = await fetchFarmSites(farmCd.value, true)
  } catch {
    sites.value = []
  }
}

async function loadHomeWeek() {
  homeWeekLoading.value = true
  try {
    const { from, to } = homeWeekRange(todayIso())
    const rows = await fetchObservations(farmCd.value, {
      date_from: from,
      date_to: to,
      sort: 'obs_dt_desc',
      limit: HOME_WEEK_LIMIT,
    })
    homeWeekItems.value = rows
    homeWeekSummary.value = summarizeHomeWeek(rows, todayIso())
    if (calRangeStart.value === from) {
      calDays.value = aggregateObsCalendar(rows)
    }
  } catch (err) {
    homeWeekItems.value = []
    homeWeekSummary.value = null
    if (!errorMessage.value) {
      errorMessage.value =
        err instanceof ApiClientError
          ? err.message
          : '최근 7일 요약을 불러오지 못했습니다.'
    }
  } finally {
    homeWeekLoading.value = false
  }
}

async function loadDrafts() {
  try {
    drafts.value = await fetchObservationDrafts(farmCd.value)
  } catch {
    drafts.value = []
  }
}

async function loadCalendar() {
  const { from, to } = rangeFromStart(calRangeStart.value)
  const home = homeWeekRange(todayIso())
  if (from === home.from && to === home.to && homeWeekItems.value.length) {
    calDays.value = aggregateObsCalendar(homeWeekItems.value)
    return
  }
  calLoading.value = true
  try {
    const rows = await fetchObservations(farmCd.value, {
      date_from: from,
      date_to: to,
      sort: 'obs_dt_desc',
      limit: HOME_WEEK_LIMIT,
    })
    calDays.value = aggregateObsCalendar(rows)
  } catch {
    calDays.value = {}
  } finally {
    calLoading.value = false
  }
}

async function loadList(opts?: { scrollToList?: boolean }) {
  loading.value = true
  errorMessage.value = ''
  const kw = keyword.value.trim()
  const sid = siteId.value
  const today = todayIso()
  const from = dateFrom.value.trim() || pastRangeStart(today)
  const to = dateTo.value.trim() || today
  try {
    items.value = await fetchObservations(farmCd.value, {
      site_id: sid || undefined,
      keyword: kw || undefined,
      date_from: from,
      date_to: to,
      sort: sort.value,
      limit: 50,
    })
    appliedKeyword.value = kw
    appliedSiteId.value = sid
    appliedDateFrom.value = from
    appliedDateTo.value = to
    if (opts?.scrollToList) {
      await nextTick()
      listAnchor.value?.scrollIntoView?.({ behavior: 'smooth', block: 'start' })
    }
  } catch (err) {
    items.value = []
    errorMessage.value =
      err instanceof ApiClientError ? err.message : '관찰 목록을 불러오지 못했습니다.'
  } finally {
    loading.value = false
  }
}

async function refreshAll() {
  await Promise.all([loadHomeWeek(), loadList(), loadDrafts()])
  await loadCalendar()
}

function onCalSelect(iso: string) {
  calSelectedDt.value = iso
  dateFrom.value = iso
  dateTo.value = iso
  void loadList({ scrollToList: true })
}

function onCalPrevRange() {
  calRangeStart.value = shiftIsoDays(calRangeStart.value, -7)
  void loadCalendar()
}

function onCalNextRange() {
  const next = shiftIsoDays(calRangeStart.value, 7)
  const maxStart = pastRangeStart(todayIso())
  calRangeStart.value = next > maxStart ? maxStart : next
  void loadCalendar()
}

function onToggleFilter() {
  filterOpen.value = !filterOpen.value
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

function goDetail(obsId: string) {
  const id = String(obsId || '').trim()
  if (!id) return
  void router.push({
    name: 'observation-detail',
    params: { obsId: id },
  })
}

function onFabClick() {
  if (drafts.value.length > 0) {
    showFabChoice.value = true
    return
  }
  goNewBlank()
}

function onQuickRange(days: number) {
  const today = todayIso()
  dateTo.value = today
  dateFrom.value = shiftIsoDays(today, -(days - 1))
  void loadList({ scrollToList: true })
}

async function onKpiSelect(_key: ObservationHeroKpiKey) {
  const { from, to } = homeWeekRange(todayIso())
  dateFrom.value = from
  dateTo.value = to
  await loadList({ scrollToList: true })
}

function onOpenRecentAiAll() {
  void onKpiSelect('ai')
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
    <main class="content ods-page-content">
      <OdsAppBar />

      <ObservationHero
        :farm-name="farm?.farm_nm || undefined"
        :summary="homeWeekSummary"
        :loading="homeWeekLoading"
        @select="onKpiSelect"
      />

      <ObservationAiRiskSection
        :items="riskItems"
        :loading="homeWeekLoading"
        @open="goDetail"
      />

      <ObservationRecentAiSection
        :items="recentAiItems"
        :loading="homeWeekLoading"
        @open-all="onOpenRecentAiAll"
        @select="goDetail"
      />

      <ObservationWeekCalendar
        :range-start="calRangeStart"
        :selected-dt="calSelectedDt"
        :days="calDays"
        :loading="calLoading"
        :detail-open="filterOpen"
        @select="onCalSelect"
        @prev-range="onCalPrevRange"
        @next-range="onCalNextRange"
        @toggle-detail="onToggleFilter"
      />

      <div
        v-show="filterOpen"
        id="obs-lookup-panel"
        class="lookup-filters"
      >
        <ObservationFilters
          v-model:site-id="siteId"
          v-model:keyword="keyword"
          v-model:sort="sort"
          v-model:date-from="dateFrom"
          v-model:date-to="dateTo"
          :sites="sites"
          :searching="loading"
          @apply="() => loadList({ scrollToList: true })"
          @quick-range="onQuickRange"
        />
      </div>

      <section class="lookup" aria-label="관찰내역">
        <div ref="listAnchor" class="list-anchor">
          <p v-if="errorMessage" class="error" role="alert">{{ errorMessage }}</p>
          <p
            v-else
            class="status"
            :class="{ 'status--loading': loading }"
            role="status"
          >
            {{ resultStatus }}
          </p>

          <div
            v-if="!errorMessage && items.length"
            class="list"
            :aria-busy="loading"
          >
            <ObservationListCard
              v-for="row in items"
              :key="row.obs_id"
              :item="row"
            />
          </div>
        </div>
      </section>
    </main>

    <button
      type="button"
      class="fab"
      :aria-label="MSG_FAB_NEW"
      @click="onFabClick"
    >
      <img class="fab__ico" :src="iconCamera" alt="" >
      {{ MSG_FAB_NEW }}
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
          이어서 작성하거나 새 관찰을 시작할 수 있습니다. 기존 초안은 자동으로
          이어쓰거나 삭제하지 않습니다.
        </p>
        <button
          type="button"
          class="sheet__btn sheet__btn--primary"
          @click="goResume(drafts[0].obs_id)"
        >
          ① 이어쓰기
        </button>
        <button type="button" class="sheet__btn" @click="goNewBlank">
          ② 새 관찰
        </button>
        <button
          type="button"
          class="sheet__btn sheet__btn--ghost"
          @click="showFabChoice = false"
        >
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
  /* padding/max-width/gap -> .ods-page-content (AppBar SSOT) */
}
.lookup {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-12);
}
.lookup-filters {
  min-width: 0;
  /* sticky AppBar 아래로 맞춰 scrollIntoView 가림 방지 */
  scroll-margin-top: calc(
    env(safe-area-inset-top, 0px) + 56px + var(--ods-space-8)
  );
}
.list-anchor {
  margin-top: 0;
  scroll-margin-top: calc(
    env(safe-area-inset-top, 0px) + 56px + var(--ods-space-8)
  );
}
.status {
  margin: 0 0 var(--ods-space-12);
  font: var(--ods-font-headline);
  font-size: 15px;
  font-weight: 800;
  line-height: 1.35;
  letter-spacing: -0.02em;
  color: var(--ods-color-text);
}
.status--loading {
  font: var(--ods-font-body-2);
  font-weight: 600;
  letter-spacing: 0;
  color: var(--ods-color-ai);
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
  min-height: 52px;
  padding: 0 18px;
  border: none;
  border-radius: 999px;
  background: var(--ods-color-primary);
  color: var(--ods-color-white);
  font: var(--ods-font-body-1);
  font-weight: 700;
  box-shadow: var(--ods-shadow-card);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
.fab__ico {
  width: 18px;
  height: 18px;
  filter: brightness(0) invert(1);
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
