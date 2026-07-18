<script setup lang="ts">
import { computed, ref } from 'vue'

import iconExpense from '@/assets/ods/work-log/icon-expense.svg'
import iconLabor from '@/assets/ods/work-log/icon-labor.svg'
import iconWork from '@/assets/ods/work-log/icon-work.svg'
import {
  formatWon,
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
  return '오늘 하루도 수고 많으셨습니다'
})

const chips = computed(() => [
  {
    key: 'work',
    label: '오늘 작업',
    value: String(props.todayWorkCount ?? 0),
    icon: iconWork,
  },
  {
    key: 'labor',
    label: '투입 인력',
    value: String(props.todayResourceCount ?? 0),
    icon: iconLabor,
  },
  {
    key: 'expense',
    label: '오늘 경비',
    value: formatWon(props.todayExpenseSum ?? 0),
    icon: iconExpense,
  },
])

function onImgError() {
  imgFailed.value = true
}
</script>

<template>
  <header
    v-if="mode !== 'daily'"
    class="hero-photo"
    :class="{ 'hero-photo--fallback': imgFailed }"
  >
    <img
      v-if="!imgFailed"
      class="hero-photo__bg"
      :src="heroSrc"
      alt=""
      @error="onImgError"
    />
    <div class="hero-photo__overlay" aria-hidden="true" />
    <div class="hero-photo__body">
      <p class="hero-photo__date">{{ todayPretty }}</p>
      <p class="hero-photo__msg">{{ greeting }}</p>
      <div class="hero-photo__chips" aria-label="오늘 요약">
        <div v-for="c in chips" :key="c.key" class="chip">
          <span class="chip__icon-wrap">
            <img class="chip__icon" :src="c.icon" alt="" />
          </span>
          <span class="chip__label">{{ c.label }}</span>
          <span class="chip__value">{{ c.value }}</span>
        </div>
      </div>
    </div>
  </header>

  <header v-else class="hero">
    <p class="hero__date">{{ todayPretty }}</p>
    <h1 class="hero__title">영농일지</h1>
    <p class="hero__msg">{{ greeting }}</p>
    <div class="hero__strip" role="status">
      <span class="hero__strip-label">작업일</span>
      <span class="hero__strip-value">{{ contextLabel || '—' }}</span>
    </div>
  </header>
</template>

<style scoped>
.hero-photo {
  position: relative;
  margin-inline: calc(-1 * var(--ods-page-padding-x));
  overflow: hidden;
  border-radius: 0 0 var(--ods-radius-card) var(--ods-radius-card);
  min-height: 220px;
  color: var(--ods-color-white);
  background: var(--ods-color-primary);
}
.hero-photo--fallback {
  background: var(--ods-color-primary);
}
.hero-photo__bg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.hero-photo__overlay {
  position: absolute;
  inset: 0;
  /* SCR-010 Hero 한정 ODS 예외: 반투명 녹색 오버레이 */
  background: color-mix(in srgb, var(--ods-color-primary) 55%, transparent);
}
.hero-photo__body {
  position: relative;
  z-index: 1;
  padding: var(--ods-space-16) var(--ods-page-padding-x) var(--ods-space-16);
}
.hero-photo__date {
  margin: 0;
  font: var(--ods-font-caption);
  opacity: 0.95;
}
.hero-photo__msg {
  margin: var(--ods-space-8) 0 0;
  font: var(--ods-font-title-1);
  font-weight: 700;
  color: var(--ods-color-white);
  line-height: 1.35;
}
.hero-photo__chips {
  margin-top: var(--ods-space-16);
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--ods-space-12);
}
.chip {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--ods-space-4);
  padding: var(--ods-space-12) var(--ods-space-8);
  border-radius: var(--ods-radius-card);
  background: rgba(255, 255, 255, 0.18);
  border: 1px solid rgba(255, 255, 255, 0.28);
  text-align: center;
}
.chip__icon-wrap {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.92);
}
.chip__icon {
  width: 22px;
  height: 22px;
}
.chip__label {
  font: var(--ods-font-caption);
  opacity: 0.95;
}
.chip__value {
  font: var(--ods-font-body-1);
  font-weight: 700;
}

.hero {
  padding: var(--ods-space-8) 0 var(--ods-space-16);
}
.hero__date {
  margin: 0;
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
}
.hero__title {
  margin: var(--ods-space-8) 0 0;
  font: var(--ods-font-title-1);
  color: var(--ods-color-text);
}
.hero__msg {
  margin: var(--ods-space-8) 0 0;
  font: var(--ods-font-body-1);
  color: var(--ods-color-text-secondary);
}
.hero__strip {
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
.hero__strip-label {
  flex-shrink: 0;
  font: var(--ods-font-body-2);
  color: var(--ods-color-text-secondary);
}
.hero__strip-value {
  min-width: 0;
  font: var(--ods-font-body-1);
  font-weight: 700;
  color: var(--ods-color-text);
  text-align: right;
}
</style>
