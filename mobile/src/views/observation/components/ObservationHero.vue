<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import iconFruit from '@/assets/ods/common/icon-kpi-fruit.svg'
import iconPest from '@/assets/ods/common/icon-kpi-pest.svg'
import iconRobot from '@/assets/ods/common/icon-kpi-robot.svg'
import iconWarn from '@/assets/ods/common/icon-kpi-warn.svg'
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

export type ObservationHeroKpiKey = 'pest' | 'fruit' | 'ai' | 'danger'

const emit = defineEmits<{
  select: [key: ObservationHeroKpiKey]
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

type KpiTone = ObservationHeroKpiKey

/** KPI 4칸: 병해충 → 과실 → AI → 위험 */
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
      key: 'pest' as const,
      label: '병해충 관찰',
      icon: iconPest,
      value: fmt(s?.pest_count),
      tone: 'pest' as KpiTone,
      chevron: true,
    },
    {
      key: 'fruit' as const,
      label: '과실 관찰',
      icon: iconFruit,
      value: fmt(s?.fruit_count),
      tone: 'fruit' as KpiTone,
      chevron: true,
    },
    {
      key: 'ai' as const,
      label: 'AI 분석',
      icon: iconRobot,
      value: fmt(s?.ai_pending_count),
      tone: 'ai' as KpiTone,
      chevron: true,
    },
    {
      key: 'danger' as const,
      label: '위험 분석',
      icon: iconWarn,
      value: fmt(s?.danger_count),
      tone: 'danger' as KpiTone,
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

      <div class="hero__kpi" aria-label="최근 7일 요약">
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
/* SCR-010 월간 Hero와 동일 높이(180/188) · KPI4 플랫 행 */
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
  /* 시안: 우측 인물·과실, 좌측 카피 여백 */
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
  /* KPI 4칸 라벨 확보: 좌우 패딩 축소 */
  padding: var(--ods-space-24) var(--ods-space-8) var(--ods-space-8);
  box-sizing: border-box;
}
.hero__date {
  margin: 0;
  display: inline-block;
  width: fit-content;
  max-width: 100%;
  padding: var(--ods-space-4) var(--ods-space-8);
  border-radius: var(--ods-radius-badge);
  font: var(--ods-font-form-help);
  font-weight: 700;
  color: var(--ods-color-white);
  background: color-mix(in srgb, var(--ods-color-gray-900) 38%, transparent);
  text-shadow: 0 1px 2px color-mix(in srgb, var(--ods-color-gray-900) 45%, transparent);
}
.hero__msg {
  margin: var(--ods-space-8) 0 0;
  font: var(--ods-font-title-2);
  color: var(--ods-color-white);
  text-shadow:
    0 1px 2px color-mix(in srgb, var(--ods-color-gray-900) 55%, transparent),
    0 2px 10px color-mix(in srgb, var(--ods-color-gray-900) 35%, transparent);
}
.hero__hint {
  margin: var(--ods-space-4) 0 0;
  font: var(--ods-font-card-help);
  color: color-mix(in srgb, var(--ods-color-white) 85%, transparent);
}
.hero__kpi {
  margin-top: auto;
  padding-top: var(--ods-space-8);
  margin-left: -2px;
  margin-right: -2px;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  align-items: stretch;
}
.kpi {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: var(--ods-space-4);
  margin: 0;
  min-width: 0;
  padding: var(--ods-space-4);
  border: none;
  border-radius: 0;
  background: transparent;
  cursor: pointer;
  text-align: left;
  color: var(--ods-color-white);
}
.kpi + .kpi {
  border-left: 1px solid color-mix(in srgb, var(--ods-color-white) 35%, transparent);
  padding-left: var(--ods-space-4);
}
.kpi__ico-wrap {
  flex: 0 0 auto;
  display: grid;
  place-items: center;
  width: var(--ods-icon-2xl);
  height: var(--ods-icon-2xl);
  border-radius: var(--ods-radius-button);
  background: color-mix(in srgb, var(--ods-color-white) 96%, transparent);
}
.kpi__ico {
  width: var(--ods-icon-sm);
  height: var(--ods-icon-sm);
  display: block;
}
.kpi__text {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-4);
  min-width: 0;
  flex: 1;
}
.kpi__label {
  font: var(--ods-font-card-meta);
  font-weight: 600;
  color: color-mix(in srgb, var(--ods-color-white) 88%, transparent);
  white-space: nowrap;
  overflow: visible;
}
.kpi__value {
  font: var(--ods-font-card-body);
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
  .hero {
    height: 188px;
  }
  .hero__msg {
    font: var(--ods-font-title-2);
  }
  .kpi__value {
    font: var(--ods-font-form-value);
    font-weight: 800;
  }
}
@media (prefers-reduced-motion: reduce) {
  .anim-fade-up {
    animation: none;
  }
}
</style>
