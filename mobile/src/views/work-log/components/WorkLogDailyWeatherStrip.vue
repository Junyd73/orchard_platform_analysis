<script setup lang="ts">
import { computed } from 'vue'

import wxHumidity from '@/assets/ods/work-log/wx-humidity.svg'
import wxPrecip from '@/assets/ods/work-log/wx-precip.svg'
import wxWind from '@/assets/ods/work-log/wx-wind.svg'
import {
  displayWeatherNm,
  weatherIconSrc,
} from '@/views/work-log/workLogConstants'
import type { WorkLogMasterDto } from '@/types/workLog'

const props = defineProps<{
  master: WorkLogMasterDto | null
  /** 월간: 캘린더 셀 기상 보완 */
  weatherNmFallback?: string | null
  weatherCdFallback?: string | null
  loading?: boolean
}>()

const weatherCd = computed(
  () => props.master?.weather_cd || props.weatherCdFallback || null,
)
const weatherNm = computed(() =>
  displayWeatherNm(
    props.master?.weather_cd || props.weatherCdFallback,
    props.master?.weather_nm || props.weatherNmFallback,
  ),
)
const iconSrc = computed(() => weatherIconSrc(weatherCd.value, weatherNm.value))

function fmtTemp(value: number | null | undefined): string {
  if (value == null) return '—'
  return `${value}°C`
}

/** 시안: 대표 기온 — 최고·최저 평균(가능 시), 없으면 한쪽 */
const currentTemp = computed(() => {
  if (props.loading) return '…'
  const max = props.master?.temp_max
  const min = props.master?.temp_min
  if (max != null && min != null) {
    return `${Math.round((max + min) / 2)}°C`
  }
  if (max != null) return `${max}°C`
  if (min != null) return `${min}°C`
  return '—'
})

const tempRange = computed(() => {
  if (props.loading) return '…'
  const min = props.master?.temp_min
  const max = props.master?.temp_max
  if (min == null && max == null) return '— / —'
  return `${fmtTemp(min)} / ${fmtTemp(max)}`
})

const humidityText = computed(() => {
  if (props.loading) return '…'
  const v = props.master?.humidity
  return v == null ? '—' : `${v}%`
})

const windText = computed(() => {
  if (props.loading) return '…'
  const v = props.master?.wind_max
  return v == null ? '—' : `${v}m/s`
})

/** API precip 값을 시안「강수확률」표시에 사용 (단위 %) */
const precipProbText = computed(() => {
  if (props.loading) return '…'
  const v = props.master?.precip
  return v == null ? '—' : `${v}%`
})
</script>

<template>
  <section class="wx" aria-label="오늘의 기상">
    <div class="wx__main">
      <img class="wx__sky" :src="iconSrc" alt="" />
      <div class="wx__temps">
        <p class="wx__now">{{ currentTemp }}</p>
        <p class="wx__range">{{ tempRange }}</p>
      </div>
    </div>

    <div class="wx__div" aria-hidden="true" />

    <div class="wx__mid">
      <div class="wx__row">
        <img class="wx__mini" :src="wxHumidity" alt="" />
        <span>습도 {{ humidityText }}</span>
      </div>
      <div class="wx__row">
        <img class="wx__mini" :src="wxWind" alt="" />
        <span>풍속 {{ windText }}</span>
      </div>
    </div>

    <div class="wx__div" aria-hidden="true" />

    <div class="wx__precip">
      <img class="wx__mini" :src="wxPrecip" alt="" />
      <div class="wx__precip-text">
        <span class="wx__precip-label">강수확률</span>
        <span class="wx__precip-val">{{ precipProbText }}</span>
      </div>
    </div>
  </section>
</template>

<style scoped>
.wx {
  display: flex;
  align-items: center;
  gap: 0;
  padding: var(--ods-space-12) var(--ods-space-12);
  border-radius: var(--ods-radius-card);
  background: var(--ods-color-white);
  box-shadow: var(--ods-shadow-card);
  border: 1px solid var(--ods-color-border);
}

.wx__main {
  flex: 1.1;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  padding-right: 10px;
}

.wx__sky {
  width: 40px;
  height: 40px;
  flex-shrink: 0;
}

.wx__temps {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.wx__now {
  margin: 0;
  font: var(--ods-font-title-2);
  font-weight: 800;
  color: var(--ods-color-text);
  line-height: 1.1;
}

.wx__range {
  margin: 0;
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
}

.wx__div {
  width: 1px;
  align-self: stretch;
  background: var(--ods-color-border);
  flex-shrink: 0;
}

.wx__mid {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 6px;
  padding: 0 10px;
}

.wx__row {
  display: flex;
  align-items: center;
  gap: 5px;
  font: var(--ods-font-caption);
  color: var(--ods-color-text);
  white-space: nowrap;
}

.wx__mini {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
}

.wx__precip {
  flex: 0.85;
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding-left: 10px;
}

.wx__precip-text {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 1px;
}

.wx__precip-label {
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
}

.wx__precip-val {
  font: var(--ods-font-body-2);
  font-weight: 800;
  color: var(--ods-color-text);
}
</style>
