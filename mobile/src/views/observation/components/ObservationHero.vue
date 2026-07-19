<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import iconCalendar from '@/assets/ods/scr004/icon-kpi-calendar.svg'
import iconFruit from '@/assets/ods/scr004/icon-kpi-fruit.svg'
import iconRobot from '@/assets/ods/scr004/icon-kpi-robot.svg'
import iconWarn from '@/assets/ods/scr004/icon-kpi-warn.svg'
import { OBSERVATION_HERO_ITEMS } from '@/views/observation/observationHeroCatalog'
import { selectDailyObservationHero } from '@/views/observation/selectDailyObservationHero'
import { todayIso, WEEKDAY_LABELS } from '@/views/work-log/workLogConstants'
import type { ObservationSummary } from '@/types/observation'

const props = defineProps<{
  farmName?: string
  summary?: ObservationSummary | null
  loading?: boolean
  /** 테스트·미리보기용 YYYY-MM-DD (기본: 오늘) */
  dateIso?: string
}>()

const emit = defineEmits<{
  select: [key: 'today' | 'danger' | 'ai' | 'fruit']
}>()

const imgFailed = ref(false)

const effectiveDate = computed(() => {
  const d = String(props.dateIso || '').trim()
  return /^\d{4}-\d{2}-\d{2}$/.test(d) ? d : todayIso()
})

const dailyHero = computed(() =>
  selectDailyObservationHero(OBSERVATION_HERO_ITEMS, effectiveDate.value),
)

watch(
  () => dailyHero.value.id,
  () => {
    imgFailed.value = false
  },
)

const todayPretty = computed(() => {
  const iso = effectiveDate.value
  const [, m, d] = iso.split('-')
  const week = WEEKDAY_LABELS[new Date(`${iso}T12:00:00`).getDay()]
  return `${Number(m)}월 ${Number(d)}일 (${week})`
})

const titleLines = computed(() =>
  dailyHero.value.title.split('\n').map((s) => s.trim()).filter(Boolean),
)

type KpiKey = 'today' | 'danger' | 'ai' | 'fruit'
type KpiTone = 'today' | 'danger' | 'ai' | 'fruit'

/** STEP 1: 승인 시안 KPI 4칸 유지 (5칸은 후속) */
const cards = computed(() => {
  const s = props.summary
  const loading = props.loading
  const fmt = (n: number | null | undefined) => {
    if (loading) return '…'
    if (n == null) return '—'
    return `${n}건`
  }
  return [
    {
      key: 'today' as KpiKey,
      label: '오늘 관찰',
      icon: iconCalendar,
      value: fmt(s?.today_count),
      tone: 'today' as KpiTone,
      chevron: false,
    },
    {
      key: 'danger' as KpiKey,
      label: '위험 관찰',
      icon: iconWarn,
      value: fmt(s?.danger_count),
      tone: 'danger' as KpiTone,
      chevron: true,
    },
    {
      key: 'ai' as KpiKey,
      label: 'AI 대기',
      icon: iconRobot,
      value: fmt(s?.ai_pending_count),
      tone: 'ai' as KpiTone,
      chevron: true,
    },
    {
      key: 'fruit' as KpiKey,
      label: '과실 관찰',
      icon: iconFruit,
      value: fmt(s?.fruit_count),
      tone: 'fruit' as KpiTone,
      chevron: true,
    },
  ]
})

function onImgError() {
  imgFailed.value = true
}
</script>

<template>
  <header
    class="hero anim-fade-up"
    :class="{ 'hero--fallback': imgFailed }"
    aria-label="생육관찰 소개"
  >
    <img
      v-if="!imgFailed"
      class="hero__bg"
      :src="dailyHero.image"
      :alt="dailyHero.alt"
      @error="onImgError"
    >
    <!-- 장식 그라데이션 · AI 스캔 포인트는 STEP2+ -->
    <div class="hero__overlay" aria-hidden="true" />
    <div class="hero__body">
      <p class="hero__date">{{ todayPretty }}</p>
      <p class="hero__msg">
        <template v-for="(line, i) in titleLines" :key="i">
          <br v-if="i > 0">{{ line }}
        </template>
      </p>

      <p v-if="loading" class="hero__hint">요약 불러오는 중…</p>
      <p v-else-if="!summary" class="hero__hint">
        요약 정보를 아직 불러오지 못했습니다.
      </p>

      <div class="hero__kpi" aria-label="오늘 요약">
        <button
          v-for="c in cards"
          :key="c.key"
          type="button"
          class="kpi"
          :class="`kpi--${c.tone}`"
          @click="emit('select', c.key)"
        >
          <span class="kpi__ico-wrap" aria-hidden="true">
            <img class="kpi__ico" :src="c.icon" alt="" >
          </span>
          <span class="kpi__text">
            <span class="kpi__label">{{ c.label }}</span>
            <span class="kpi__value">
              {{ c.value }}<span v-if="c.chevron" class="kpi__chev">›</span>
            </span>
          </span>
        </button>
      </div>
    </div>
  </header>
</template>

<style scoped>
/* 시안 A: 히어로 하단 플랫 KPI(구분선) · 승인 레이아웃 유지 */
.hero {
  position: relative;
  min-height: 160px;
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
  object-position: 72% center;
  filter: contrast(1.04) saturate(1.02);
}
.hero__overlay {
  position: absolute;
  inset: 0;
  background:
    linear-gradient(
      180deg,
      transparent 0%,
      transparent 28%,
      color-mix(in srgb, var(--ods-color-primary) 22%, transparent) 52%,
      color-mix(in srgb, black 48%, var(--ods-color-primary)) 100%
    ),
    linear-gradient(
      100deg,
      color-mix(in srgb, var(--ods-color-primary) 42%, transparent) 0%,
      color-mix(in srgb, var(--ods-color-primary) 16%, transparent) 40%,
      transparent 64%
    );
}
.hero__body {
  position: relative;
  z-index: 1;
  min-height: 160px;
  display: flex;
  flex-direction: column;
  padding: var(--ods-space-16) var(--ods-space-12) 10px var(--ods-space-16);
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
  color: var(--ods-color-white);
  text-shadow:
    0 1px 2px rgba(0, 0, 0, 0.55),
    0 2px 10px rgba(0, 0, 0, 0.35);
}
.hero__hint {
  margin: var(--ods-space-8) 0 0;
  font: var(--ods-font-caption);
  color: rgba(255, 255, 255, 0.85);
}
.hero__kpi {
  margin-top: auto;
  padding-top: var(--ods-space-10);
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  align-items: stretch;
}
.kpi {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 6px;
  margin: 0;
  min-width: 0;
  padding: 2px 6px;
  border: none;
  border-radius: 0;
  background: transparent;
  cursor: pointer;
  text-align: left;
  color: var(--ods-color-white);
}
.kpi + .kpi {
  border-left: 1px solid rgba(255, 255, 255, 0.35);
}
.kpi__ico-wrap {
  flex: 0 0 auto;
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.96);
}
.kpi__ico {
  width: 16px;
  height: 16px;
  display: block;
}
.kpi__text {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
}
.kpi__label {
  font-size: 10px;
  font-weight: 600;
  line-height: 1.2;
  color: rgba(255, 255, 255, 0.88);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.kpi__value {
  font-size: 13px;
  font-weight: 800;
  line-height: 1.15;
  letter-spacing: -0.02em;
  color: var(--ods-color-white);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.kpi__chev {
  margin-left: 1px;
  font-weight: 700;
  opacity: 0.75;
}
.anim-fade-up {
  animation: obs-hero-fade var(--ods-motion-base) var(--ods-motion-ease) both;
}
@keyframes obs-hero-fade {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
@media (min-width: 390px) {
  .hero,
  .hero__body {
    min-height: 168px;
  }
  .hero__msg {
    font-size: 19px;
  }
  .kpi__value {
    font-size: 14px;
  }
}
@media (prefers-reduced-motion: reduce) {
  .anim-fade-up {
    animation: none;
  }
}
</style>
