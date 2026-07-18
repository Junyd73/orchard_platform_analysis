<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'

import { fetchWorkLogDaily, fetchWorkLogMonthly } from '@/api/workLogs'
import { ApiClientError } from '@/api/client'
import OdsAppBar from '@/components/ods/OdsAppBar.vue'
import OdsBottomNav from '@/components/ods/OdsBottomNav.vue'
import OdsButton from '@/components/ods/OdsButton.vue'
import WorkLogFilterSheet from '@/views/work-log/components/WorkLogFilterSheet.vue'
import WorkLogHero from '@/views/work-log/components/WorkLogHero.vue'
import WorkLogMonthCalendar from '@/views/work-log/components/WorkLogMonthCalendar.vue'
import WorkLogMonthChart from '@/views/work-log/components/WorkLogMonthChart.vue'
import WorkLogMonthSummary from '@/views/work-log/components/WorkLogMonthSummary.vue'
import WorkLogWeatherCard from '@/views/work-log/components/WorkLogWeatherCard.vue'
import {
  defaultWorkFilters,
  isFutureDate,
  monthLabel,
  MSG_DETAIL_PENDING,
  MSG_HOURLY_FORECAST_PENDING,
  todayIso,
  type WorkFilterKey,
} from '@/views/work-log/workLogConstants'
import { useAppStore } from '@/composables/stores/app'
import type {
  WorkLogDayCell,
  WorkLogMasterDto,
  WorkLogMonthSummary as SummaryDto,
} from '@/types/workLog'

const store = useAppStore()
const router = useRouter()
const route = useRoute()
const { farmCd, farm } = storeToRefs(store)

const now = new Date()
const year = ref(now.getFullYear())
const month = ref(now.getMonth() + 1)
const loading = ref(true)
const weatherLoading = ref(false)
const errorMessage = ref('')
const toastMessage = ref('')
const summary = ref<SummaryDto | null>(null)
const days = ref<Record<string, WorkLogDayCell>>({})
const todayMaster = ref<WorkLogMasterDto | null>(null)
const filterOpen = ref(false)
const filters = ref(defaultWorkFilters())

const title = computed(() => monthLabel(year.value, month.value))
const today = todayIso()

const todayCell = computed(() => days.value[today] || null)

const todayWorkCount = computed(() => Number(todayCell.value?.work_count || 0))
const todayResourceCount = computed(() => Number(todayCell.value?.resource_count || 0))
const todayExpenseSum = computed(() => {
  const c = todayCell.value
  if (!c) return 0
  return Number(c.expense_sum || 0) + Number(c.labor_sum || 0)
})

const canGoNext = computed(() => {
  const t = new Date()
  const cy = t.getFullYear()
  const cm = t.getMonth() + 1
  return year.value < cy || (year.value === cy && month.value < cm)
})

async function loadMonth() {
  loading.value = true
  errorMessage.value = ''
  try {
    const res = await fetchWorkLogMonthly(farmCd.value, year.value, month.value)
    summary.value = res.summary
    days.value = res.days || {}
  } catch (err) {
    summary.value = null
    days.value = {}
    errorMessage.value =
      err instanceof ApiClientError ? err.message : '월간 영농일지를 불러오지 못했습니다.'
  } finally {
    loading.value = false
  }
}

async function loadTodayWeather() {
  const t = new Date()
  const viewingCurrent =
    year.value === t.getFullYear() && month.value === t.getMonth() + 1
  if (!viewingCurrent) {
    todayMaster.value = null
    return
  }
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

function goPrev() {
  if (month.value === 1) {
    year.value -= 1
    month.value = 12
  } else {
    month.value -= 1
  }
}

function goNext() {
  if (!canGoNext.value) return
  if (month.value === 12) {
    year.value += 1
    month.value = 1
  } else {
    month.value += 1
  }
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
  // 기존 날씨 상세 라우트 없음 → 토스트만
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
  void loadTodayWeather()
})

onMounted(async () => {
  if (!farm.value) {
    await store.refreshAll()
  }
  await Promise.all([loadMonth(), loadTodayWeather()])
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

      <WorkLogHero
        mode="monthly"
        :farm-name="farm?.farm_nm || undefined"
        :today-work-count="todayWorkCount"
        :today-resource-count="todayResourceCount"
        :today-expense-sum="todayExpenseSum"
      />

      <WorkLogWeatherCard
        :master="todayMaster"
        :loading="weatherLoading"
        @forecast="onForecast"
      />

      <div class="month-head">
        <div class="month-head__row">
          <button type="button" class="month-head__nav" aria-label="이전 달" @click="goPrev">
            ‹
          </button>
          <h2 class="month-head__title">{{ title }}</h2>
          <button
            type="button"
            class="month-head__nav"
            aria-label="다음 달"
            :disabled="!canGoNext"
            @click="goNext"
          >
            ›
          </button>
        </div>
        <div class="month-head__actions">
          <OdsButton
            variant="secondary"
            type="button"
            :block="false"
            class="month-head__btn"
            @click="filterOpen = true"
          >
            작업필터 ▼
          </OdsButton>
          <OdsButton
            variant="primary"
            type="button"
            :block="false"
            class="month-head__btn"
            @click="goTodayMonth"
          >
            오늘
          </OdsButton>
        </div>
      </div>

      <p v-if="errorMessage" class="error" role="alert">{{ errorMessage }}</p>
      <p v-else-if="loading" class="status status--loading" role="status">
        캘린더 불러오는 중…
      </p>

      <WorkLogMonthCalendar
        v-if="!errorMessage"
        :year="year"
        :month="month"
        :days="days"
        :filters="filters"
        @select="onSelectDay"
        @blocked="onBlocked"
      />

      <WorkLogMonthSummary
        :year="year"
        :month="month"
        :summary="summary"
        :loading="loading"
        @detail="onSummaryDetail"
      />

      <WorkLogMonthChart
        v-if="!errorMessage"
        :year="year"
        :month="month"
        :days="days"
      />
    </main>

    <button type="button" class="fab" aria-label="오늘 영농일지 등록" @click="onFabRegister">
      + 등록
    </button>

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
.month-head {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-12);
}
.month-head__row {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--ods-space-12);
}
.month-head__title {
  margin: 0;
  min-width: 8em;
  text-align: center;
  font: var(--ods-font-headline);
  color: var(--ods-color-text);
}
.month-head__nav {
  width: 44px;
  height: 44px;
  border: 1px solid var(--ods-color-border);
  border-radius: var(--ods-radius-button);
  background: var(--ods-color-white);
  font-size: 22px;
  line-height: 1;
  cursor: pointer;
  color: var(--ods-color-text);
}
.month-head__nav:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.month-head__actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--ods-space-8);
}
.month-head__btn {
  width: 100%;
}
.status {
  margin: 0;
  font: var(--ods-font-body-2);
  color: var(--ods-color-text-secondary);
}
.status--loading {
  color: var(--ods-color-ai);
  font-weight: 600;
}
.error {
  margin: 0;
  font: var(--ods-font-body-2);
  color: var(--ods-color-danger);
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
.toast {
  position: fixed;
  left: 50%;
  bottom: calc(120px + env(safe-area-inset-bottom));
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
