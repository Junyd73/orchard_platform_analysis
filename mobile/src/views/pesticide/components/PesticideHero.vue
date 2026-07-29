<script setup lang="ts">
import { computed, ref } from 'vue'

import heroPesticide from '@/assets/images/pesticide/hero-pesticide.png'
import iconKpiCalendar from '@/assets/ods/pesticide/icon-kpi-calendar.svg'
import iconKpiLow from '@/assets/ods/pesticide/icon-kpi-low.svg'
import iconKpiStock from '@/assets/ods/pesticide/icon-kpi-stock.svg'
import {
  HERO_GREETING_HIGHLIGHT,
  HERO_GREETING_LINE1,
  HERO_GREETING_LINE2_PREFIX,
  LABEL_KPI_LAST_SPRAY,
  LABEL_KPI_LOW,
  LABEL_KPI_NEXT_SPRAY,
  LABEL_KPI_TOTAL,
  PLACEHOLDER_DASH,
} from '@/views/pesticide/pesticideConstants'
import { todayIso, WEEKDAY_LABELS } from '@/views/work-log/workLogConstants'

const props = defineProps<{
  totalCount?: number
  lowCount?: number
  lastSprayDt?: string | null
  nextSprayDt?: string | null
  loading?: boolean
}>()

const imgFailed = ref(false)

const todayPretty = computed(() => {
  const iso = todayIso()
  const [, m, d] = iso.split('-')
  const week = WEEKDAY_LABELS[new Date(`${iso}T12:00:00`).getDay()]
  return `${Number(m)}월 ${Number(d)}일 (${week})`
})

function fmtSpecies(n: number | undefined): string {
  if (props.loading) return '…'
  return `${n ?? 0}종`
}

/** KPI 밀집용: YYYY-MM-DD → MM-DD */
function fmtDateShort(raw: string | null | undefined): string {
  if (props.loading) return '…'
  const s = String(raw || '').trim()
  if (!s) return PLACEHOLDER_DASH
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s)
  return m ? `${m[2]}-${m[3]}` : s
}

const nextDday = computed(() => {
  const s = String(props.nextSprayDt || '').trim()
  if (!/^\d{4}-\d{2}-\d{2}$/.test(s)) return null
  const today = new Date(`${todayIso()}T12:00:00`)
  const target = new Date(`${s}T12:00:00`)
  return Math.round((target.getTime() - today.getTime()) / 86_400_000)
})

const nextDdayLabel = computed(() => {
  const d = nextDday.value
  if (d == null) return ''
  if (d === 0) return 'D-Day'
  if (d > 0) return `D-${d}`
  return `D+${Math.abs(d)}`
})

function onImgError() {
  imgFailed.value = true
}
</script>

<template>
  <header
    class="hero anim-fade-up"
    :class="{ 'hero--fallback': imgFailed }"
    aria-label="농약 관리 소개"
  >
    <img
      v-if="!imgFailed"
      class="hero__bg"
      :src="heroPesticide"
      alt=""
      @error="onImgError"
    />
    <div class="hero__overlay" aria-hidden="true" />
    <div class="hero__body">
      <p class="hero__date">{{ todayPretty }}</p>
      <p class="hero__msg">
        {{ HERO_GREETING_LINE1 }}
        <br />
        {{ HERO_GREETING_LINE2_PREFIX }}<em class="hero__em">{{ HERO_GREETING_HIGHLIGHT }}</em>
      </p>

      <div class="hero__kpi" aria-label="농약 요약">
        <div class="kpi">
          <span class="kpi__ico-wrap" aria-hidden="true">
            <img class="kpi__ico" :src="iconKpiStock" alt="" />
          </span>
          <div class="kpi__texts">
            <p class="kpi__label">{{ LABEL_KPI_TOTAL }}</p>
            <p class="kpi__value">{{ fmtSpecies(totalCount) }}</p>
          </div>
        </div>
        <span class="kpi__div" aria-hidden="true" />
        <div class="kpi">
          <span class="kpi__ico-wrap" aria-hidden="true">
            <img class="kpi__ico" :src="iconKpiLow" alt="" />
          </span>
          <div class="kpi__texts">
            <p class="kpi__label">{{ LABEL_KPI_LOW }}</p>
            <p class="kpi__value">{{ fmtSpecies(lowCount) }}</p>
          </div>
        </div>
        <span class="kpi__div" aria-hidden="true" />
        <div class="kpi">
          <span class="kpi__ico-wrap" aria-hidden="true">
            <img class="kpi__ico" :src="iconKpiCalendar" alt="" />
          </span>
          <div class="kpi__texts">
            <p class="kpi__label">{{ LABEL_KPI_LAST_SPRAY }}</p>
            <p class="kpi__value kpi__value--date">{{ fmtDateShort(lastSprayDt) }}</p>
          </div>
        </div>
        <span class="kpi__div" aria-hidden="true" />
        <div class="kpi">
          <span class="kpi__ico-wrap" aria-hidden="true">
            <img class="kpi__ico" :src="iconKpiCalendar" alt="" />
          </span>
          <div class="kpi__texts">
            <p class="kpi__label">{{ LABEL_KPI_NEXT_SPRAY }}</p>
            <p class="kpi__value kpi__value--date">
              <span>{{ fmtDateShort(nextSprayDt) }}</span>
              <span v-if="nextDdayLabel" class="kpi__dday">{{ nextDdayLabel }}</span>
            </p>
          </div>
        </div>
      </div>
    </div>
  </header>
</template>

<style scoped>
/* SCR-010 영농일지 Hero 골격 표준 · KPI 4칸 */
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
  /* 좌측 카피 여백 · 우측 방제기·태블릿 인물 */
  object-position: 58% 42%;
  filter: contrast(1.04) saturate(1.02);
}
.hero__overlay {
  position: absolute;
  inset: 0;
  /* 영농일지와 동일: 상단 밝게 · 하단만 진녹 반투명 */
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
  padding: var(--ods-space-24) var(--ods-space-8) var(--ods-space-12) var(--ods-space-16);
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
  letter-spacing: -0.01em;
  color: var(--ods-color-white);
  background: color-mix(in srgb, black 38%, transparent);
  text-shadow: 0 1px 2px color-mix(in srgb, black 45%, transparent);
}
.hero__msg {
  margin: var(--ods-space-8) 0 0;
  font: var(--ods-font-title-2);
  font-weight: 800;
  letter-spacing: -0.03em;
  color: var(--ods-color-white);
  max-width: 15em;
  text-shadow:
    0 1px 2px color-mix(in srgb, black 55%, transparent),
    0 2px 10px color-mix(in srgb, black 35%, transparent);
}
.hero__em {
  font-style: normal;
  color: var(--ods-color-accent);
}
.hero__kpi {
  margin-top: auto;
  padding-top: var(--ods-space-8);
  flex-shrink: 0;
  display: grid;
  grid-template-columns:
    minmax(0, 1fr) auto minmax(0, 1fr) auto minmax(0, 1fr) auto minmax(0, 1fr);
  align-items: center;
  gap: 0;
  column-gap: var(--ods-space-4);
}
.kpi {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: flex-start;
  gap: var(--ods-space-4);
  min-width: 0;
  padding: 0;
}
.kpi__ico-wrap {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  width: var(--ods-hit-sm);
  height: var(--ods-hit-sm);
  border-radius: 50%;
  background: color-mix(in srgb, var(--ods-color-primary) 70%, black);
  border: 1px solid color-mix(in srgb, var(--ods-color-white) 22%, transparent);
}
.kpi__ico {
  width: var(--ods-icon-md);
  height: var(--ods-icon-md);
  filter: brightness(0) invert(1);
}
.kpi__texts {
  min-width: 0;
  flex: 1 1 auto;
  text-align: left;
}
.kpi__label {
  margin: 0;
  font: var(--ods-font-card-help);
  font-weight: 500;
  opacity: 0.9;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.kpi__value {
  margin: var(--ods-space-4) 0 0;
  font: var(--ods-font-form-help);
  font-weight: 800;
  letter-spacing: -0.02em;
  font-variant-numeric: tabular-nums;
  color: var(--ods-color-white);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.kpi__value--date {
  display: inline-flex;
  align-items: center;
  gap: var(--ods-space-4);
  letter-spacing: -0.04em;
}
.kpi__dday {
  display: inline-flex;
  align-items: center;
  padding: 0 var(--ods-space-4);
  border-radius: var(--ods-radius-badge);
  font: var(--ods-font-card-help);
  font-weight: 800;
  background: var(--ods-color-caution);
  color: var(--ods-color-white);
  line-height: 1.35;
}
.kpi__div {
  width: 1px;
  height: calc(var(--ods-hit-sm) + var(--ods-space-4));
  align-self: center;
  background: color-mix(in srgb, var(--ods-color-white) 28%, transparent);
}

.anim-fade-up {
  animation: pst-fade-up var(--ods-motion-base) var(--ods-motion-ease) both;
}
@keyframes pst-fade-up {
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
    font-weight: 800;
  }
  .kpi__value {
    font: var(--ods-font-form-value);
    font-weight: 800;
  }
  .kpi__ico-wrap {
    width: calc(var(--ods-hit-sm) + var(--ods-space-4));
    height: calc(var(--ods-hit-sm) + var(--ods-space-4));
  }
}
@media (prefers-reduced-motion: reduce) {
  .anim-fade-up {
    animation: none;
  }
}
</style>
