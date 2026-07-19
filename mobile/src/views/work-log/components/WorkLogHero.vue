<script setup lang="ts">
import { computed, ref } from 'vue'

import iconCalendar from '@/assets/ods/work-log/icon-calendar.svg'
import iconExpense from '@/assets/ods/work-log/icon-expense.svg'
import iconLabor from '@/assets/ods/work-log/icon-labor.svg'
import {
  formatHeroWonWithUnit,
  formatLaborSummary,
  formatWonWithUnit,
  heroGreetingForHour,
  heroImageForMonth,
  todayIso,
  WEEKDAY_LABELS,
} from '@/views/work-log/workLogConstants'

const props = defineProps<{
  farmName?: string
  mode?: 'monthly' | 'daily'
  contextLabel?: string
  todayWorkCount?: number
  todayResourceCount?: number
  todayLaborHourSum?: number
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
  return heroGreetingForHour(new Date().getHours())
})

const expenseDisplay = computed(() => formatHeroWonWithUnit(props.todayExpenseSum))
const expenseFull = computed(() => formatWonWithUnit(props.todayExpenseSum))
/** 7자리 이상(백만원대~)이면 열·폰트 압축 */
const expenseLong = computed(() => {
  const n = Math.round(Number(props.todayExpenseSum || 0))
  return Number.isFinite(n) && n >= 1_000_000
})
const expenseVeryLong = computed(() => {
  const n = Math.round(Number(props.todayExpenseSum || 0))
  return Number.isFinite(n) && n >= 10_000_000
})
/** 작업·인력·경비 숫자 동일 크기 (금액 기준) */
const valueSizeClass = computed(() => {
  if (expenseVeryLong.value) return 'kpi__value--xs'
  if (expenseLong.value) return 'kpi__value--compact'
  return ''
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
      <div
        class="hero__kpi"
        :class="{
          'hero__kpi--expense-long': expenseLong,
          'hero__kpi--expense-xl': expenseVeryLong,
        }"
        aria-label="오늘 요약"
      >
        <div class="kpi">
          <span class="kpi__ico-wrap">
            <img class="kpi__ico" :src="iconCalendar" alt="" />
          </span>
          <div class="kpi__texts">
            <p class="kpi__label">오늘 작업</p>
            <p class="kpi__value" :class="valueSizeClass">
              {{ todayWorkCount ?? 0 }}건
            </p>
          </div>
        </div>
        <span class="kpi__div" aria-hidden="true" />
        <div class="kpi">
          <span class="kpi__ico-wrap">
            <img class="kpi__ico" :src="iconLabor" alt="" />
          </span>
          <div class="kpi__texts">
            <p class="kpi__label">투입 인력</p>
            <p class="kpi__value" :class="valueSizeClass">
              {{
                formatLaborSummary(
                  todayResourceCount ?? 0,
                  todayLaborHourSum ?? 0,
                )
              }}
            </p>
          </div>
        </div>
        <span class="kpi__div" aria-hidden="true" />
        <div class="kpi kpi--expense">
          <span class="kpi__ico-wrap">
            <img class="kpi__ico" :src="iconExpense" alt="" />
          </span>
          <div class="kpi__texts">
            <p class="kpi__label">오늘 경비</p>
            <p class="kpi__value" :class="valueSizeClass" :title="expenseFull">
              {{ expenseDisplay }}
            </p>
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
/*
  시안4: 흰 페이지 위 녹색 Hero 카드
  (AppBar/페이지 배경은 흰색 — Green Layer 사용 안 함)
*/
.hero {
  position: relative;
  height: 180px;
  border-radius: var(--ods-radius-card-lg);
  overflow: hidden;
  color: var(--ods-color-white);
  background: var(--ods-color-primary);
  box-shadow: var(--ods-shadow-card);
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
  /* 시안: 우측 과실·잎이 보이도록 */
  object-position: 72% center;
  filter: contrast(1.04) saturate(1.02);
}
.hero__overlay {
  position: absolute;
  inset: 0;
  /*
    시안1: 상단은 밝은 과수원 유지,
    하단 KPI만 반투명 진녹 밴드
  */
  background:
    linear-gradient(
      180deg,
      transparent 0%,
      transparent 46%,
      color-mix(in srgb, var(--ods-color-primary) 35%, transparent) 68%,
      color-mix(in srgb, black 48%, var(--ods-color-primary)) 100%
    ),
    linear-gradient(
      100deg,
      color-mix(in srgb, var(--ods-color-primary) 38%, transparent) 0%,
      color-mix(in srgb, var(--ods-color-primary) 14%, transparent) 38%,
      transparent 62%
    );
}
.hero__body {
  position: relative;
  z-index: 1;
  height: 100%;
  display: flex;
  flex-direction: column;
  /* 상단을 더 내려 하늘·가장자리와 분리 */
  padding: var(--ods-space-24) var(--ods-space-12) var(--ods-space-12) var(--ods-space-16);
  box-sizing: border-box;
}
.hero__date {
  margin: 0;
  display: inline-block;
  width: fit-content;
  max-width: 100%;
  padding: 3px 8px;
  border-radius: var(--ods-radius-badge);
  font-size: 13px;
  font-weight: 700;
  line-height: 1.25;
  letter-spacing: -0.01em;
  color: var(--ods-color-white);
  background: color-mix(in srgb, black 38%, transparent);
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.45);
}
.hero__msg {
  margin: var(--ods-space-8) 0 0;
  font-size: 18px;
  font-weight: 800;
  line-height: 1.3;
  letter-spacing: -0.03em;
  white-space: pre-line;
  color: var(--ods-color-white);
  max-width: 15em;
  text-shadow:
    0 1px 2px rgba(0, 0, 0, 0.55),
    0 2px 10px rgba(0, 0, 0, 0.35);
}
.hero__kpi {
  margin-top: auto;
  padding-top: var(--ods-space-8);
  flex-shrink: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr) auto minmax(0, 1.3fr);
  align-items: center;
  gap: 0;
  column-gap: var(--ods-space-4);
}
/* 백만원 이상: 경비 열만 소폭 확대 (작업·인력 라벨 한 줄 유지) */
.hero__kpi--expense-long {
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr) auto minmax(0, 1.45fr);
}
.hero__kpi--expense-xl {
  grid-template-columns: minmax(0, 0.95fr) auto minmax(0, 0.95fr) auto minmax(0, 1.55fr);
}
/* 시안: [아이콘] 라벨 / 숫자 — 가로 배치 */
.kpi {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: flex-start;
  gap: var(--ods-space-4);
  min-width: 0;
  padding: 0;
}
.kpi--expense {
  min-width: 0;
}
.kpi__ico-wrap {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: color-mix(in srgb, var(--ods-color-primary) 70%, black);
  border: 1px solid rgba(255, 255, 255, 0.22);
}
.kpi__ico {
  width: 16px;
  height: 16px;
  filter: brightness(0) invert(1);
}
.kpi__texts {
  min-width: 0;
  flex: 1 1 auto;
  text-align: left;
}
.kpi__label {
  margin: 0;
  font-size: 10px;
  font-weight: 500;
  line-height: 1.2;
  opacity: 0.9;
  white-space: nowrap;
}
.kpi__value {
  margin: 2px 0 0;
  font-size: 16px;
  font-weight: 800;
  line-height: 1.15;
  letter-spacing: -0.02em;
  font-variant-numeric: tabular-nums;
  color: var(--ods-color-white);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.kpi__value--compact {
  font-size: 13px;
  letter-spacing: -0.04em;
}
.kpi__value--xs {
  font-size: 11px;
  letter-spacing: -0.05em;
}
.kpi__div {
  width: 1px;
  height: 36px;
  align-self: center;
  background: rgba(255, 255, 255, 0.28);
}

.anim-fade-up {
  animation: wl-fade-up var(--ods-motion-base) var(--ods-motion-ease) both;
}
@keyframes wl-fade-up {
  from {
    opacity: 0;
    transform: translateY(8px);
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
    height: 188px;
  }
  .hero__msg {
    font-size: 19px;
  }
  .kpi__value {
    font-size: 17px;
  }
  .kpi__value--compact {
    font-size: 14px;
  }
  .kpi__value--xs {
    font-size: 12px;
  }
  .kpi__ico-wrap {
    width: 34px;
    height: 34px;
  }
}
@media (prefers-reduced-motion: reduce) {
  .anim-fade-up {
    animation: none;
  }
}
</style>
