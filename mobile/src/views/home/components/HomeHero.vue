<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'

import iconCalendar from '@/assets/ods/work-log/icon-calendar.svg'
import iconLabor from '@/assets/ods/work-log/icon-labor.svg'
import iconPest from '@/assets/ods/common/icon-kpi-pest.svg'
import iconWarn from '@/assets/ods/common/icon-kpi-warn.svg'
import {
  HOME_HERO_IMAGE_BY_SEASON,
  HOME_HERO_SEASON_FADE_MS,
  HOME_HERO_SEASON_LABEL,
  HOME_HERO_SEASON_ORDER,
  HOME_HERO_SEASON_PREVIEW,
  HOME_HERO_SEASON_PREVIEW_MS,
  homeHeroImageForMonth,
  heroGreetingForHour,
  LABEL_KPI_LABOR,
  LABEL_KPI_PEST,
  LABEL_KPI_SPRAY,
  LABEL_KPI_TODAY_WORK,
  type HeroSeason,
} from '@/views/home/homeConstants'
import { todayIso, WEEKDAY_LABELS } from '@/views/work-log/workLogConstants'

const props = defineProps<{
  farmName?: string
  todayWork?: number
  laborCount?: number
  pestCaution?: number
  sprayPlan?: number
}>()

const imgFailed = ref(false)
const previewIndex = ref(0)
let previewTimer = 0

const previewSeason = computed<HeroSeason>(
  () => HOME_HERO_SEASON_ORDER[previewIndex.value] ?? 'spring',
)

const todayPretty = computed(() => {
  const iso = todayIso()
  const [, m, d] = iso.split('-')
  const week = WEEKDAY_LABELS[new Date(`${iso}T12:00:00`).getDay()]
  return `${Number(m)}월 ${Number(d)}일 (${week})`
})

const heroSrc = computed(() => {
  if (HOME_HERO_SEASON_PREVIEW) {
    return HOME_HERO_IMAGE_BY_SEASON[previewSeason.value]
  }
  return homeHeroImageForMonth(Number(todayIso().slice(5, 7)))
})

/** 이중 레이어 크로스페이드 */
const layerA = ref(heroSrc.value)
const layerB = ref(heroSrc.value)
const useLayerB = ref(false)

function preloadImage(src: string): Promise<void> {
  return new Promise((resolve) => {
    const img = new Image()
    img.onload = () => resolve()
    img.onerror = () => resolve()
    img.src = src
  })
}

watch(heroSrc, async (next) => {
  imgFailed.value = false
  await preloadImage(next)
  if (useLayerB.value) {
    layerA.value = next
    requestAnimationFrame(() => {
      useLayerB.value = false
    })
  } else {
    layerB.value = next
    requestAnimationFrame(() => {
      useLayerB.value = true
    })
  }
})

onMounted(() => {
  if (!HOME_HERO_SEASON_PREVIEW) return
  previewTimer = window.setInterval(() => {
    previewIndex.value =
      (previewIndex.value + 1) % HOME_HERO_SEASON_ORDER.length
  }, HOME_HERO_SEASON_PREVIEW_MS)
})

onUnmounted(() => {
  if (previewTimer) window.clearInterval(previewTimer)
})

const greeting = computed(() => heroGreetingForHour(new Date().getHours()))

const subcopy = computed(() => {
  const name = (props.farmName || '').trim()
  return name
    ? `${name}의 성공적인 하루를 응원합니다.`
    : '성공적인 하루를 응원합니다.'
})

const kpiCards = computed(() => [
  {
    key: 'work',
    icon: iconCalendar,
    label: LABEL_KPI_TODAY_WORK,
    value: `${props.todayWork ?? 0}건`,
  },
  {
    key: 'labor',
    icon: iconLabor,
    label: LABEL_KPI_LABOR,
    value: `${props.laborCount ?? 0}명`,
  },
  {
    key: 'pest',
    icon: iconPest,
    label: LABEL_KPI_PEST,
    value: `${props.pestCaution ?? 0}건`,
  },
  {
    key: 'spray',
    icon: iconWarn,
    label: LABEL_KPI_SPRAY,
    value: `${props.sprayPlan ?? 0}건`,
  },
])

function onImgError() {
  imgFailed.value = true
}
</script>

<template>
  <header
    class="hero anim-fade-up"
    :class="{ 'hero--fallback': imgFailed }"
    :style="{ '--home-hero-fade-ms': `${HOME_HERO_SEASON_FADE_MS}ms` }"
    aria-label="홈 소개"
  >
    <div class="hero__bg-stack" aria-hidden="true">
      <img
        class="hero__bg"
        :class="{ 'hero__bg--on': !useLayerB }"
        :src="layerA"
        alt=""
        @error="onImgError"
      />
      <img
        class="hero__bg"
        :class="{ 'hero__bg--on': useLayerB }"
        :src="layerB"
        alt=""
        @error="onImgError"
      />
    </div>
    <div class="hero__overlay" aria-hidden="true" />
    <div class="hero__body">
      <div class="hero__top">
        <p class="hero__date">{{ todayPretty }}</p>
        <Transition name="season-fade" mode="out-in">
          <p
            v-if="HOME_HERO_SEASON_PREVIEW"
            :key="previewSeason"
            class="hero__season"
            aria-live="polite"
          >
            {{ HOME_HERO_SEASON_LABEL[previewSeason] }}
          </p>
        </Transition>
      </div>
      <p class="hero__msg">{{ greeting }}</p>
      <p class="hero__sub">{{ subcopy }}</p>
      <div class="hero__kpi" aria-label="오늘 요약">
        <div v-for="c in kpiCards" :key="c.key" class="kpi">
          <span class="kpi__ico-wrap" aria-hidden="true">
            <img class="kpi__ico" :src="c.icon" alt="" />
          </span>
          <span class="kpi__text">
            <span class="kpi__label">{{ c.label }}</span>
            <span class="kpi__value">{{ c.value }}</span>
          </span>
        </div>
      </div>
    </div>
  </header>
</template>

<style scoped>
/* 생육관찰 Hero와 동일: 높이 180/188 · KPI 아이콘+2줄 플랫 행 */
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
  object-position: center;
  opacity: 0;
  transition: opacity var(--home-hero-fade-ms, 1200ms) ease-in-out;
  will-change: opacity;
}
.hero__bg--on {
  opacity: 1;
}
.hero__bg-stack {
  position: absolute;
  inset: 0;
}
.season-fade-enter-active,
.season-fade-leave-active {
  transition: opacity calc(var(--home-hero-fade-ms, 1200ms) * 0.55) ease;
}
.season-fade-enter-from,
.season-fade-leave-to {
  opacity: 0;
}
.hero__overlay {
  position: absolute;
  inset: 0;
  background:
    linear-gradient(
      180deg,
      transparent 0%,
      transparent 46%,
      color-mix(in srgb, var(--ods-color-primary) 28%, transparent) 68%,
      color-mix(in srgb, black 40%, var(--ods-color-primary)) 100%
    ),
    linear-gradient(
      100deg,
      color-mix(in srgb, var(--ods-color-primary) 30%, transparent) 0%,
      color-mix(in srgb, var(--ods-color-primary) 10%, transparent) 38%,
      transparent 62%
    );
}
.hero__body {
  position: relative;
  z-index: 1;
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: var(--ods-space-24) 8px 10px 10px;
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
  color: var(--ods-color-white);
  background: color-mix(in srgb, black 28%, transparent);
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.45);
}
.hero__top {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.hero__season {
  margin: 0;
  padding: 3px 8px;
  border-radius: var(--ods-radius-badge);
  font-size: 12px;
  font-weight: 700;
  line-height: 1.25;
  color: var(--ods-color-white);
  background: color-mix(in srgb, var(--ods-color-accent) 55%, black 20%);
}
.hero__msg {
  margin: var(--ods-space-8) 0 0;
  font-size: 18px;
  font-weight: 800;
  line-height: 1.28;
  letter-spacing: -0.03em;
  white-space: pre-line;
  max-width: 14em;
  text-shadow:
    0 1px 2px rgba(0, 0, 0, 0.55),
    0 2px 10px rgba(0, 0, 0, 0.35);
}
.hero__sub {
  margin: 4px 0 0;
  font: var(--ods-font-caption);
  line-height: 1.35;
  max-width: 20em;
  color: rgba(255, 255, 255, 0.9);
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.4);
}
.hero__kpi {
  margin-top: auto;
  padding-top: var(--ods-space-8);
  margin-left: -2px;
  margin-right: -2px;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  align-items: stretch;
  background: transparent;
}
.kpi {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 4px;
  margin: 0;
  min-width: 0;
  padding: 2px 2px;
  color: var(--ods-color-white);
}
.kpi + .kpi {
  border-left: 1px solid rgba(255, 255, 255, 0.35);
  padding-left: 4px;
}
.kpi__ico-wrap {
  flex: 0 0 auto;
  display: grid;
  place-items: center;
  width: var(--ods-icon-2xl);
  height: var(--ods-icon-2xl);
  border-radius: 7px;
  background: rgba(255, 255, 255, 0.92);
}
.kpi__ico {
  width: var(--ods-icon-sm);
  height: var(--ods-icon-sm);
  display: block;
}
.kpi__text {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
  flex: 1;
}
.kpi__label {
  font-size: 10px;
  font-weight: 600;
  line-height: 1.2;
  letter-spacing: -0.04em;
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
@media (min-width: 390px) {
  .hero {
    height: 188px;
  }
  .hero__msg {
    font-size: 19px;
  }
  .kpi__value {
    font-size: 14px;
  }
}
</style>
