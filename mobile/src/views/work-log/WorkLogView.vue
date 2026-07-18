<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'

import { fetchWorkLogDaily, fetchWorkLogMonthly } from '@/api/workLogs'
import { ApiClientError } from '@/api/client'
import OdsAppBar from '@/components/ods/OdsAppBar.vue'
import OdsBottomNav from '@/components/ods/OdsBottomNav.vue'
import OdsFab from '@/components/ods/OdsFab.vue'
import OdsSkeleton from '@/components/ods/OdsSkeleton.vue'
import WorkLogFilterSheet from '@/views/work-log/components/WorkLogFilterSheet.vue'
import WorkLogHero from '@/views/work-log/components/WorkLogHero.vue'
import WorkLogMonthCalendar from '@/views/work-log/components/WorkLogMonthCalendar.vue'
import WorkLogMonthChart from '@/views/work-log/components/WorkLogMonthChart.vue'
import WorkLogMonthSummary from '@/views/work-log/components/WorkLogMonthSummary.vue'
import WorkLogWeatherCard from '@/views/work-log/components/WorkLogWeatherCard.vue'
import {
  defaultWorkFilters,
  isFutureDate,
  MSG_DETAIL_PENDING,
  MSG_HOURLY_FORECAST_PENDING,
  MSG_LOAD_MONTH_FAILED,
  shiftMonth,
  todayIso,
  type WorkFilterKey,
} from '@/views/work-log/workLogConstants'
import { useAppStore } from '@/composables/stores/app'
import type {
  WorkLogDayCell,
  WorkLogMasterDto,
  WorkLogMonthSummary as SummaryDto,
} from '@/types/workLog'

import iconPlus from '@/assets/ods/work-log/icon-plus.svg'

const store = useAppStore()
const router = useRouter()
const route = useRoute()
const { farmCd, farm } = storeToRefs(store)

const now = new Date()
const year = ref(now.getFullYear())
const month = ref(now.getMonth() + 1)
const loading = ref(true)
const weatherLoading = ref(false)
const bootstrapping = ref(true)
const toastMessage = ref('')
const loadFailed = ref(false)
const summary = ref<SummaryDto | null>(null)
const days = ref<Record<string, WorkLogDayCell>>({})
const todayMaster = ref<WorkLogMasterDto | null>(null)
const filterOpen = ref(false)
const filters = ref(defaultWorkFilters())

const today = todayIso()

const todayCell = computed(() => days.value[today] || null)
const todayWorkCount = computed(() => Number(todayCell.value?.work_count || 0))
const todayResourceCount = computed(() => Number(todayCell.value?.resource_count || 0))
const todayExpenseSum = computed(() => {
  const c = todayCell.value
  if (!c) return 0
  return Number(c.expense_sum || 0) + Number(c.labor_sum || 0)
})
const todayInProgressCount = computed((): number | null => null)
const todayPlannedCount = computed((): number | null => null)

const canGoNext = computed(() => {
  const t = new Date()
  const cy = t.getFullYear()
  const cm = t.getMonth() + 1
  return year.value < cy || (year.value === cy && month.value < cm)
})

const showMonthSkeleton = computed(() => bootstrapping.value)
const showWeatherSkeleton = computed(
  () => bootstrapping.value || (weatherLoading.value && !todayMaster.value),
)

async function loadMonth() {
  loading.value = true
  loadFailed.value = false
  try {
    const res = await fetchWorkLogMonthly(farmCd.value, year.value, month.value)
    summary.value = res.summary
    days.value = res.days || {}
  } catch (err) {
    summary.value = null
    days.value = {}
    loadFailed.value = true
    const msg =
      err instanceof ApiClientError ? err.message : MSG_LOAD_MONTH_FAILED
    showToast(sanitizeError(msg))
  } finally {
    loading.value = false
  }
}

async function loadTodayWeather() {
  weatherLoading.value = true
  try {
    const daily = await fetchWorkLogDaily(farmCd.value, today)
    todayMaster.value = daily.master
  } catch {
    todayMaster.value = null
  } finally {
    weatherLoading.value = false
  }
}

function sanitizeError(msg: string): string {
  const m = String(msg || '').trim()
  if (!m) return MSG_LOAD_MONTH_FAILED
  if (/not\s*found/i.test(m) || m === 'Farm not found') {
    return MSG_LOAD_MONTH_FAILED
  }
  return m
}

function goPrev() {
  const next = shiftMonth(year.value, month.value, -1)
  year.value = next.year
  month.value = next.month
}

function goNext() {
  if (!canGoNext.value) return
  const next = shiftMonth(year.value, month.value, 1)
  year.value = next.year
  month.value = next.month
}

function goTodayMonth() {
  const t = new Date()
  year.value = t.getFullYear()
  month.value = t.getMonth() + 1
}

function onSelectDay(workDt: string) {
  if (isFutureDate(workDt)) {
    showToast('영농일지는 오늘까지만 작성할 수 있습니다.')
    return
  }
  void router.push({ name: 'work-log-daily', params: { workDt } })
}

function onBlocked(msg: string) {
  showToast(msg)
}

function onFabRegister() {
  void router.push({ name: 'work-log-daily', params: { workDt: today } })
}

function onForecast() {
  showToast(MSG_HOURLY_FORECAST_PENDING)
}

function onSummaryDetail() {
  showToast(MSG_DETAIL_PENDING)
}

function onToggleFilter(key: WorkFilterKey) {
  filters.value = { ...filters.value, [key]: !filters.value[key] }
}

function onResetFilters() {
  filters.value = defaultWorkFilters()
}

function showToast(msg: string) {
  toastMessage.value = msg
  window.setTimeout(() => {
    if (toastMessage.value === msg) toastMessage.value = ''
  }, 2800)
}

watch([year, month], () => {
  void loadMonth()
})

onMounted(async () => {
  if (!farm.value) {
    await store.refreshAll()
  }
  await Promise.all([loadMonth(), loadTodayWeather()])
  bootstrapping.value = false
  const toast = String(route.query.toast || '').trim()
  if (toast) {
    showToast(toast)
    void router.replace({ name: 'work-log' })
  }
})
</script>

<template>
  <div class="page">
    <main class="content">
      <OdsAppBar />

      <div class="hero-stack">
        <OdsSkeleton v-if="showMonthSkeleton" variant="hero" />
        <WorkLogHero
          v-else
          mode="monthly"
          :farm-name="farm?.farm_nm || undefined"
          :today-work-count="todayWorkCount"
          :today-in-progress-count="todayInProgressCount"
          :today-planned-count="todayPlannedCount"
          :today-resource-count="todayResourceCount"
          :today-expense-sum="todayExpenseSum"
        />

        <div class="hero-stack__weather">
          <OdsSkeleton v-if="showWeatherSkeleton" variant="card" height="112px" />
          <WorkLogWeatherCard
            v-else
            :master="todayMaster"
            :weather-nm-fallback="todayCell?.weather_nm"
            :weather-cd-fallback="todayCell?.weather_cd"
            :loading="weatherLoading"
            @forecast="onForecast"
          />
        </div>
      </div>

      <template v-if="showMonthSkeleton">
        <OdsSkeleton variant="card" height="360px" />
        <OdsSkeleton variant="kpi" />
        <OdsSkeleton variant="card" height="140px" />
      </template>

      <template v-else>
        <WorkLogMonthCalendar
          :year="year"
          :month="month"
          :days="days"
          :filters="filters"
          :can-go-next="canGoNext"
          :loading="loading"
          :show-empty="loadFailed || Object.keys(days).length === 0"
          @select="onSelectDay"
          @blocked="onBlocked"
          @open-filter="filterOpen = true"
          @go-today="goTodayMonth"
          @prev-month="goPrev"
          @next-month="goNext"
        />

        <WorkLogMonthSummary
          :year="year"
          :month="month"
          :summary="summary"
          :loading="loading"
          @detail="onSummaryDetail"
        />

        <WorkLogMonthChart :year="year" :month="month" :days="days" />
      </template>
    </main>

    <OdsFab label="등록" aria-label="오늘 영농일지 등록" @click="onFabRegister">
      <img :src="iconPlus" alt="" />
    </OdsFab>

    <WorkLogFilterSheet
      :open="filterOpen"
      :filters="filters"
      @close="filterOpen = false"
      @toggle="onToggleFilter"
      @reset="onResetFilters"
    />

    <p v-if="toastMessage" class="toast" role="status">{{ toastMessage }}</p>
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
  padding: var(--ods-space-12) var(--ods-page-padding-x) var(--ods-space-24);
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-16);
}
.hero-stack {
  position: relative;
  padding-bottom: var(--ods-space-40);
}
.hero-stack__weather {
  position: relative;
  z-index: 2;
  margin-top: calc(var(--ods-space-40) * -1);
}
.toast {
  position: fixed;
  left: 50%;
  bottom: calc(150px + env(safe-area-inset-bottom));
  transform: translateX(-50%);
  z-index: 70;
  max-width: min(420px, calc(100vw - 32px));
  margin: 0;
  padding: var(--ods-space-12) var(--ods-space-16);
  border-radius: var(--ods-radius-button);
  background: color-mix(in srgb, var(--ods-color-gray-900) 92%, transparent);
  color: var(--ods-color-white);
  font: var(--ods-font-body-2);
  font-weight: 600;
  text-align: center;
  box-shadow: var(--ods-shadow-card);
}
</style>
