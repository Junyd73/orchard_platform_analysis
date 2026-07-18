<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'

import { fetchWorkLogMonthly } from '@/api/workLogs'
import { ApiClientError } from '@/api/client'
import OdsAppBar from '@/components/ods/OdsAppBar.vue'
import OdsBottomNav from '@/components/ods/OdsBottomNav.vue'
import OdsButton from '@/components/ods/OdsButton.vue'
import WorkLogHero from '@/views/work-log/components/WorkLogHero.vue'
import WorkLogMonthCalendar from '@/views/work-log/components/WorkLogMonthCalendar.vue'
import WorkLogMonthSummary from '@/views/work-log/components/WorkLogMonthSummary.vue'
import {
  isFutureDate,
  monthLabel,
} from '@/views/work-log/workLogConstants'
import { useAppStore } from '@/composables/stores/app'
import type { WorkLogMonthSummary as SummaryDto, WorkLogDayCell } from '@/types/workLog'

const store = useAppStore()
const router = useRouter()
const route = useRoute()
const { farmCd, farm } = storeToRefs(store)

const now = new Date()
const year = ref(now.getFullYear())
const month = ref(now.getMonth() + 1)
const loading = ref(true)
const errorMessage = ref('')
const toastMessage = ref('')
const summary = ref<SummaryDto | null>(null)
const days = ref<Record<string, WorkLogDayCell>>({})

const title = computed(() => monthLabel(year.value, month.value))

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

function goToday() {
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
  await loadMonth()
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
        :context-label="title"
      />

      <nav class="month-nav" aria-label="연월 이동">
        <OdsButton
          variant="secondary"
          type="button"
          :block="false"
          class="month-nav__side"
          @click="goPrev"
        >
          이전
        </OdsButton>
        <OdsButton
          variant="secondary"
          type="button"
          :block="false"
          class="month-nav__center"
          @click="goToday"
        >
          오늘로
        </OdsButton>
        <OdsButton
          variant="secondary"
          type="button"
          :block="false"
          class="month-nav__side"
          :disabled="!canGoNext"
          @click="goNext"
        >
          다음
        </OdsButton>
      </nav>

      <WorkLogMonthSummary :summary="summary" :loading="loading" />

      <h2 class="section-title">월간 캘린더</h2>
      <p class="section-hint">날짜를 누르면 일간 영농일지로 이동합니다.</p>

      <p v-if="errorMessage" class="error" role="alert">{{ errorMessage }}</p>
      <p v-else-if="loading" class="status status--loading" role="status">
        캘린더 불러오는 중…
      </p>

      <WorkLogMonthCalendar
        v-if="!errorMessage"
        :year="year"
        :month="month"
        :days="days"
        @select="onSelectDay"
        @blocked="onBlocked"
      />
    </main>

    <p v-if="toastMessage" class="toast" role="status">{{ toastMessage }}</p>
    <OdsBottomNav />
  </div>
</template>

<style scoped>
.page {
  min-height: 100dvh;
  background: var(--ods-color-bg-muted);
  padding-bottom: calc(88px + env(safe-area-inset-bottom));
}
.content {
  max-width: 480px;
  margin: 0 auto;
  padding: var(--ods-space-12) var(--ods-page-padding-x) var(--ods-space-16);
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-16);
}
.month-nav {
  display: grid;
  grid-template-columns: 1fr 1.2fr 1fr;
  gap: var(--ods-space-8);
}
.month-nav__side,
.month-nav__center {
  width: 100%;
}
.section-title {
  margin: var(--ods-space-8) 0 0;
  font: var(--ods-font-headline);
  color: var(--ods-color-text);
}
.section-hint {
  margin: calc(-1 * var(--ods-space-8)) 0 0;
  font: var(--ods-font-body-2);
  color: var(--ods-color-text-secondary);
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
