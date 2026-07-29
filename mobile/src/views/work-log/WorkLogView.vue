<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'

import {
  fetchWorkLogDaily,
  fetchWorkLogMonthly,
  fetchWorkLogWeather,
} from '@/api/workLogs'
import { ApiClientError } from '@/api/client'
import OdsAppBar from '@/components/ods/OdsAppBar.vue'
import OdsBottomNav from '@/components/ods/OdsBottomNav.vue'
import OdsFab from '@/components/ods/OdsFab.vue'
import OdsSkeleton from '@/components/ods/OdsSkeleton.vue'
import WorkLogHero from '@/views/work-log/components/WorkLogHero.vue'
import WorkLogMonthCalendar from '@/views/work-log/components/WorkLogMonthCalendar.vue'
import WorkLogMonthChart from '@/views/work-log/components/WorkLogMonthChart.vue'
import WorkLogMonthSummary from '@/views/work-log/components/WorkLogMonthSummary.vue'
import WorkLogWeatherCard from '@/views/work-log/components/WorkLogWeatherCard.vue'
import {
  defaultWorkFilters,
  hasWorkLogWeather,
  isFutureDate,
  MSG_DETAIL_PENDING,
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

function applyYearMonthFromQuery() {
  const qy = Number(route.query.year)
  const qm = Number(route.query.month)
  if (Number.isFinite(qy) && qy >= 2000 && qy <= 2100) year.value = qy
  if (Number.isFinite(qm) && qm >= 1 && qm <= 12) month.value = qm
}

applyYearMonthFromQuery()
const toastMessage = ref('')
const loadFailed = ref(false)
const summary = ref<SummaryDto | null>(null)
const days = ref<Record<string, WorkLogDayCell>>({})
/** 표시 월이 바뀌어도 Hero '오늘' KPI는 유지 */
const todayCellCache = ref<WorkLogDayCell | null>(null)
const todayMaster = ref<WorkLogMasterDto | null>(null)
const filters = ref(defaultWorkFilters())
const selectedDt = ref(todayIso())

const today = todayIso()

const todayCell = computed(() => days.value[today] || todayCellCache.value)
const todayWorkCount = computed(() => Number(todayCell.value?.work_count || 0))
const todayResourceCount = computed(() => Number(todayCell.value?.resource_count || 0))
const todayLaborHourSum = computed(() => Number(todayCell.value?.labor_hour_sum || 0))
const todayExpenseSum = computed(() => {
  const c = todayCell.value
  if (!c) return 0
  return Number(c.expense_sum || 0) + Number(c.labor_sum || 0)
})

const canGoNext = computed(() => {
  // 일정 등록을 위해 미래 월 허용 (오늘 기준 최대 18개월)
  const t = new Date()
  const max = new Date(t.getFullYear(), t.getMonth() + 18, 1)
  const cur = new Date(year.value, month.value - 1, 1)
  return cur < max
})

const canGoNextYear = computed(() => {
  const cy = new Date().getFullYear()
  return year.value < cy + 1
})

const showMonthSkeleton = computed(() => bootstrapping.value)
const showWeatherSkeleton = computed(
  () => bootstrapping.value || (weatherLoading.value && !todayMaster.value),
)

function rememberTodayCell(map: Record<string, WorkLogDayCell>) {
  const cell = map[today]
  if (cell) todayCellCache.value = cell
}

async function loadMonth() {
  loading.value = true
  loadFailed.value = false
  try {
    const res = await fetchWorkLogMonthly(farmCd.value, year.value, month.value)
    summary.value = res.summary
    days.value = res.days || {}
    rememberTodayCell(days.value)
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

/** 표시 월이 오늘이 아닐 때도 Hero KPI용 오늘 셀을 확보 */
async function ensureTodayCellCache() {
  if (todayCellCache.value || days.value[today]) return
  const t = new Date()
  try {
    const res = await fetchWorkLogMonthly(
      farmCd.value,
      t.getFullYear(),
      t.getMonth() + 1,
    )
    rememberTodayCell(res.days || {})
  } catch {
    // Hero는 0으로 두고 월간 조회 실패 토스트는 loadMonth에서 처리
  }
}

async function loadTodayWeather() {
  weatherLoading.value = true
  try {
    const daily = await fetchWorkLogDaily(farmCd.value, today)
    let master = daily.master
    // DB(마스터·캐시)에 없으면 PC와 동일하게 외부 API 자동 조회
    if (!hasWorkLogWeather(master) && !isFutureDate(today)) {
      try {
        const fetched = await fetchWorkLogWeather(farmCd.value, today)
        if (fetched.master) master = fetched.master
      } catch {
        // 자동 조회 실패 시 조용히 DB 결과만 유지
      }
    }
    todayMaster.value = master
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

function goPrevYear() {
  year.value -= 1
}

function goNextYear() {
  if (!canGoNextYear.value) return
  const cy = new Date().getFullYear()
  const cm = new Date().getMonth() + 1
  year.value += 1
  if (year.value === cy && month.value > cm) {
    month.value = cm
  }
}

function goTodayMonth() {
  const t = new Date()
  year.value = t.getFullYear()
  month.value = t.getMonth() + 1
  selectedDt.value = today
}

function onSelectDay(workDt: string) {
  selectedDt.value = workDt
  void router.push({ name: 'work-log-daily', params: { workDt } })
}

function onBlocked(msg: string) {
  showToast(msg)
}

function onFabRegister() {
  selectedDt.value = today
  void router.push({ name: 'work-log-daily', params: { workDt: today } })
}

function onSummaryDetail() {
  showToast(MSG_DETAIL_PENDING)
}

function onStockView() {
  void router.push({ name: 'pesticide' })
}

function onToggleFilter(key: WorkFilterKey) {
  filters.value = { ...filters.value, [key]: !filters.value[key] }
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

/** 일간→월간 복귀 시 캘린더 갱신 */
watch(
  () => route.name,
  (name) => {
    if (name === 'work-log') {
      void loadMonth()
    }
  },
)

onMounted(async () => {
  applyYearMonthFromQuery()
  if (!farm.value) {
    await store.refreshAll()
  }
  await Promise.all([loadMonth(), loadTodayWeather(), ensureTodayCellCache()])
  bootstrapping.value = false
  if (route.query.google === 'connected') {
    showToast('구글 캘린더가 연결되었습니다.')
    void router.replace({
      name: 'work-log',
      query: {
        ...(route.query.year ? { year: String(route.query.year) } : {}),
        ...(route.query.month ? { month: String(route.query.month) } : {}),
      },
    })
  }
  const toast = String(route.query.toast || '').trim()
  if (toast) {
    showToast(toast)
    void router.replace({
      name: 'work-log',
      query: {
        ...(route.query.year ? { year: String(route.query.year) } : {}),
        ...(route.query.month ? { month: String(route.query.month) } : {}),
      },
    })
  }
})
</script>

<template>
  <div class="page">
    <main class="content ods-page-content">
      <!-- ODS: AppBar는 ods-page-content 안 첫 자식 -->
      <OdsAppBar />

      <div class="top">
        <OdsSkeleton v-if="showMonthSkeleton" variant="hero" class="top__skel" />
        <WorkLogHero
          v-else
          mode="monthly"
          :farm-name="farm?.farm_nm || undefined"
          :today-work-count="todayWorkCount"
          :today-resource-count="todayResourceCount"
          :today-labor-hour-sum="todayLaborHourSum"
          :today-expense-sum="todayExpenseSum"
        />

        <div class="top__weather">
          <OdsSkeleton v-if="showWeatherSkeleton" variant="card" height="68px" />
          <WorkLogWeatherCard
            v-else
            :master="todayMaster"
            :weather-nm-fallback="todayCell?.weather_nm"
            :weather-cd-fallback="todayCell?.weather_cd"
            :loading="weatherLoading"
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
          :selected-dt="selectedDt"
          :loading="loading"
          :show-empty="
            !loading && (loadFailed || Object.keys(days).length === 0)
          "
          @select="onSelectDay"
          @blocked="onBlocked"
          @toggle-filter="onToggleFilter"
          @go-today="goTodayMonth"
          @prev-month="goPrev"
          @next-month="goNext"
          @prev-year="goPrevYear"
          @next-year="goNextYear"
        />

        <WorkLogMonthSummary
          :year="year"
          :month="month"
          :summary="summary"
          :loading="loading"
          @detail="onSummaryDetail"
          @stock="onStockView"
        />

        <WorkLogMonthChart :year="year" :month="month" :days="days" />
      </template>
    </main>

    <OdsFab label="등록" ariaLabel="오늘 영농일지 등록" @click="onFabRegister">
      <img :src="iconPlus" alt="" />
    </OdsFab>

    <p v-if="toastMessage" class="toast" role="status">{{ toastMessage }}</p>
    <OdsBottomNav />
  </div>
</template>

<style scoped>
.page {
  min-height: 100dvh;
  /* 시안4: 페이지·AppBar 영역은 흰색 바탕 */
  background: var(--ods-color-bg);
  padding-bottom: calc(140px + env(safe-area-inset-bottom));
}

.content {
  /* padding/max-width/gap -> .ods-page-content (AppBar SSOT) */
}

.top {
  position: relative;
  display: flex;
  flex-direction: column;
}
.top__skel {
  border-radius: var(--ods-radius-card-lg);
  min-height: 180px;
}
.top__weather {
  position: relative;
  z-index: 2;
  margin-top: var(--ods-space-12);
}

.toast {
  position: fixed;
  left: 50%;
  bottom: calc(150px + env(safe-area-inset-bottom));
  transform: translateX(-50%);
  z-index: 70;
  max-width: min(420px, calc(100vw - var(--ods-hit-sm)));
  margin: 0;
  padding: var(--ods-space-12) var(--ods-space-16);
  border-radius: var(--ods-radius-button);
  background: color-mix(in srgb, var(--ods-color-gray-900) 92%, transparent);
  color: var(--ods-color-white);
  font: var(--ods-font-form-help);
  font-weight: 600;
  text-align: center;
  box-shadow: var(--ods-shadow-card);
}
</style>
