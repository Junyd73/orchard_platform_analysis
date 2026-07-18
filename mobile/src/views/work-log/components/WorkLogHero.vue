<script setup lang="ts">
import { computed, ref } from 'vue'

import iconExpense from '@/assets/ods/work-log/icon-expense.svg'
import iconLabor from '@/assets/ods/work-log/icon-labor.svg'
import iconWork from '@/assets/ods/work-log/icon-work.svg'
import {
  formatWonWithUnit,
  heroImageForMonth,
  todayIso,
  WEEKDAY_LABELS,
} from '@/views/work-log/workLogConstants'

const props = defineProps<{
  farmName?: string
  mode?: 'monthly' | 'daily'
  contextLabel?: string
  todayWorkCount?: number
  todayInProgressCount?: number | null
  todayPlannedCount?: number | null
  todayResourceCount?: number
  todayExpenseSum?: number
}>()

const imgFailed = ref(false)

const todayPretty = computed(() => {
  const iso = todayIso()
  const [, m, d] = iso.split('-')
  const week = WEEKDAY_LABELS[new Date(`${iso}T12:00:00`).getDay()]
  return `${Number(m)}월 ${Number(d)}일 (${week})`
})

const todayMonth = computed(() => Number(todayIso().slice(5, 7)))
const heroSrc = computed(() => heroImageForMonth(todayMonth.value))

const greeting = computed(() => {
  if (props.mode === 'daily') {
    const name = (props.farmName || '').trim()
    return name ? `${name} · 당일 작업·이슈 기록` : '당일 작업·이슈를 기록하세요'
  }
  return '오늘 하루도\n수고 많으셨습니다!'
})

const workSub = computed(() => {
  const prog = props.todayInProgressCount
  const plan = props.todayPlannedCount
  if (prog == null && plan == null) return '—'
  const parts: string[] = []
  if (prog != null) parts.push(`진행 ${prog}건`)
  if (plan != null) parts.push(`예정 ${plan}건`)
  return parts.join(' · ') || '—'
})

const laborSub = computed(() => '—')

const expenseSub = computed(() => {
  const n = Number(props.todayExpenseSum || 0)
  if (!Number.isFinite(n) || n <= 0) return '—'
  return `지출 ${formatWonWithUnit(n)}`
})

function onImgError() {
  imgFailed.value = true
}
</script>

<template>
  <header
    v-if="mode !== 'daily'"
    class="hero anim-fade-up"
    :class="{ 'hero--fallback': imgFailed }"
  >
    <img
      v-if="!imgFailed"
      class="hero__bg"
      :src="heroSrc"
      alt=""
      @error="onImgError"
    />
    <div class="hero__overlay" aria-hidden="true" />
    <div class="hero__body">
      <p class="hero__date">{{ todayPretty }}</p>
      <p class="hero__msg">{{ greeting }}</p>
      <div class="hero__kpi" aria-label="오늘 요약">
        <div class="kpi">
          <span class="kpi__ico-wrap">
            <img class="kpi__ico" :src="iconWork" alt="" />
          </span>
          <div class="kpi__texts">
            <p class="kpi__value">{{ todayWorkCount ?? 0 }}건</p>
            <p class="kpi__sub">{{ workSub }}</p>
          </div>
        </div>
        <span class="kpi__div" aria-hidden="true" />
        <div class="kpi">
          <span class="kpi__ico-wrap">
            <img class="kpi__ico" :src="iconLabor" alt="" />
          </span>
          <div class="kpi__texts">
            <p class="kpi__value">{{ todayResourceCount ?? 0 }}명</p>
            <p class="kpi__sub">{{ laborSub }}</p>
          </div>
        </div>
        <span class="kpi__div" aria-hidden="true" />
        <div class="kpi">
          <span class="kpi__ico-wrap">
            <img class="kpi__ico" :src="iconExpense" alt="" />
          </span>
          <div class="kpi__texts">
            <p class="kpi__value kpi__value--sm">
              {{ formatWonWithUnit(todayExpenseSum) }}
            </p>
            <p class="kpi__sub">{{ expenseSub }}</p>
          </div>
        </div>
      </div>
    </div>
  </header>

  <header v-else class="daily">
    <p class="daily__date">{{ todayPretty }}</p>
    <h1 class="daily__title">영농일지</h1>
    <p class="daily__msg">{{ greeting }}</p>
    <div class="daily__strip" role="status">
      <span class="daily__strip-label">작업일</span>
      <span class="daily__strip-value">{{ contextLabel || '—' }}</span>
    </div>
  </header>
</template>

<style scoped>
.hero {
  position: relative;
  height: 300px;
  border-radius: var(--ods-radius-card-lg);
  overflow: hidden;
  color: var(--ods-color-white);
  background: var(--ods-color-primary);
  box-shadow: var(--ods-shadow-elevated);
}
.hero--fallback {
  background: var(--ods-color-primary);
}
.hero__bg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: 78% center;
  /* 선명도: blur 없음, contrast 소폭 상향 */
  filter: contrast(1.08) saturate(1.06);
}
.hero__overlay {
  position: absolute;
  inset: 0;
  /* 좌 65% → 우 25% 감쇠 */
  background: linear-gradient(
    95deg,
    color-mix(in srgb, var(--ods-color-primary) 88%, #0d3b12) 0%,
    color-mix(in srgb, var(--ods-color-primary) 65%, transparent) 48%,
    color-mix(in srgb, var(--ods-color-primary) 25%, transparent) 100%
  );
}
.hero__body {
  position: relative;
  z-index: 1;
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: var(--ods-space-24);
  box-sizing: border-box;
}
.hero__date {
  margin: 0;
  font: var(--ods-font-caption);
  font-weight: 600;
  opacity: 0.95;
}
.hero__msg {
  margin: var(--ods-space-12) 0 0;
  font-size: 24px;
  font-weight: 800;
  line-height: 1.28;
  letter-spacing: -0.03em;
  white-space: pre-line;
  color: var(--ods-color-white);
  max-width: 12em;
}
.hero__kpi {
  margin-top: auto;
  padding-top: var(--ods-space-24);
  display: grid;
  grid-template-columns: 1fr auto 1fr auto 1fr;
  align-items: center;
}
.kpi {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--ods-space-8);
  min-width: 0;
  text-align: center;
}
.kpi__ico-wrap {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 52px;
  height: 52px;
  border-radius: var(--ods-radius-badge);
  background: rgba(255, 255, 255, 0.28);
}
.kpi__ico {
  width: 26px;
  height: 26px;
  filter: brightness(0) invert(1);
}
.kpi__texts {
  min-width: 0;
  width: 100%;
}
.kpi__value {
  margin: 0;
  font-size: 18px;
  font-weight: 800;
  line-height: 1.2;
  color: var(--ods-color-white);
}
.kpi__value--sm {
  font-size: 13px;
  letter-spacing: -0.02em;
}
.kpi__sub {
  margin: var(--ods-space-4) 0 0;
  font-size: 10px;
  line-height: 1.25;
  opacity: 0.86;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.kpi__div {
  width: 1px;
  height: 48px;
  background: rgba(255, 255, 255, 0.22);
}

.anim-fade-up {
  animation: wl-fade-up var(--ods-motion-base) var(--ods-motion-ease) both;
}
@keyframes wl-fade-up {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.daily {
  padding: var(--ods-space-8) 0 var(--ods-space-16);
}
.daily__date {
  margin: 0;
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
}
.daily__title {
  margin: var(--ods-space-8) 0 0;
  font: var(--ods-font-title-1);
  color: var(--ods-color-text);
}
.daily__msg {
  margin: var(--ods-space-8) 0 0;
  font: var(--ods-font-body-1);
  color: var(--ods-color-text-secondary);
}
.daily__strip {
  margin-top: var(--ods-space-16);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ods-space-8);
  min-height: var(--ods-control-height);
  padding: 0 var(--ods-space-16);
  border-radius: var(--ods-radius-card);
  background: var(--ods-color-white);
  border: 1px solid var(--ods-color-border);
  box-shadow: var(--ods-shadow-card);
}
.daily__strip-label {
  flex-shrink: 0;
  font: var(--ods-font-body-2);
  color: var(--ods-color-text-secondary);
}
.daily__strip-value {
  min-width: 0;
  font: var(--ods-font-body-1);
  font-weight: 700;
  color: var(--ods-color-text);
  text-align: right;
}

@media (min-width: 390px) {
  .hero {
    height: 320px;
  }
  .hero__msg {
    font-size: 26px;
  }
}
@media (prefers-reduced-motion: reduce) {
  .anim-fade-up {
    animation: none;
  }
}
</style>
