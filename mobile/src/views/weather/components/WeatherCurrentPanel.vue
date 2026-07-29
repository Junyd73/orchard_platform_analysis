<script setup lang="ts">
import wxHumidity from '@/assets/ods/work-log/wx-humidity.svg'
import wxPrecip from '@/assets/ods/work-log/wx-precip.svg'
import wxWind from '@/assets/ods/work-log/wx-wind.svg'
import {
  LABEL_WEATHER_HUMIDITY,
  LABEL_WEATHER_PRECIP_PROB,
  LABEL_WEATHER_TOMORROW_AM,
  LABEL_WEATHER_WIND,
} from '@/views/weather/weatherConstants'
import {
  formatPct,
  formatTempC,
  formatTempDiff,
  formatWindMs,
  weatherIconByKey,
} from '@/views/weather/weatherFormat'
import type {
  WeatherCurrentDto,
  WeatherPeriodHalfDto,
} from '@/types/weather'

defineProps<{
  current: WeatherCurrentDto
  location: string
  tomorrowAm?: WeatherPeriodHalfDto | null
}>()
</script>

<template>
  <section class="cur" aria-label="현재 날씨">
    <p v-if="location" class="cur__loc">{{ location }}</p>
    <div class="cur__main">
      <img
        class="cur__ico"
        :src="weatherIconByKey(null, current.weather_cd)"
        alt=""
        aria-hidden="true"
      />
      <div class="cur__temps">
        <p class="cur__now">{{ formatTempC(current.temp_c) }}</p>
        <p class="cur__sky">{{ current.weather_nm }}</p>
        <p v-if="formatTempDiff(current.temp_diff_from_yesterday)" class="cur__diff">
          {{ formatTempDiff(current.temp_diff_from_yesterday) }}
        </p>
        <p class="cur__range">
          <span class="min">{{ formatTempC(current.temp_min) }}</span>
          <span aria-hidden="true"> / </span>
          <span class="max">{{ formatTempC(current.temp_max) }}</span>
        </p>
      </div>
    </div>

    <p v-if="tomorrowAm" class="cur__tmr">
      {{ LABEL_WEATHER_TOMORROW_AM }}
      강수 {{ formatPct(tomorrowAm.precip_prob_pct) }}
    </p>

    <ul class="cur__meta">
      <li>
        <img :src="wxHumidity" alt="" aria-hidden="true" />
        <span>{{ LABEL_WEATHER_HUMIDITY }} {{ formatPct(current.humidity_pct) }}</span>
      </li>
      <li>
        <img :src="wxWind" alt="" aria-hidden="true" />
        <span>{{ LABEL_WEATHER_WIND }} {{ formatWindMs(current.wind_ms) }}</span>
      </li>
      <li>
        <img :src="wxPrecip" alt="" aria-hidden="true" />
        <span
          >{{ LABEL_WEATHER_PRECIP_PROB }}
          {{ formatPct(current.precip_prob_pct) }}</span
        >
      </li>
    </ul>
  </section>
</template>

<style scoped>
.cur {
  padding: var(--ods-space-16) var(--ods-space-12);
  border-radius: var(--ods-radius-card);
  background: var(--ods-color-white);
  border: 1px solid var(--ods-color-border);
  box-shadow: var(--ods-shadow-card);
}
.cur__loc {
  margin: 0 0 8px;
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
}
.cur__main {
  display: flex;
  align-items: center;
  gap: 12px;
}
.cur__ico {
  width: 56px;
  height: 56px;
  flex-shrink: 0;
}
.cur__now {
  margin: 0;
  font: 700 36px/1.05 var(--ods-font-family);
  color: var(--ods-color-text);
}
.cur__sky {
  margin: 4px 0 0;
  font: var(--ods-font-body);
}
.cur__diff {
  margin: 2px 0 0;
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
}
.cur__range {
  margin: 4px 0 0;
  font: var(--ods-font-caption);
}
.cur__range .min {
  color: var(--ods-color-primary);
}
.cur__range .max {
  color: var(--ods-color-danger);
}
.cur__tmr {
  margin: 12px 0 0;
  padding: 8px 10px;
  border-radius: var(--ods-radius-sm, 8px);
  background: var(--ods-color-bg-muted);
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
}
.cur__meta {
  margin: 14px 0 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-wrap: wrap;
  gap: 8px 14px;
}
.cur__meta li {
  display: flex;
  align-items: center;
  gap: 4px;
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
}
.cur__meta img {
  width: 14px;
  height: 14px;
}
</style>
