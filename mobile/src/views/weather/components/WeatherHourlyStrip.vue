<script setup lang="ts">
import {
  LABEL_WEATHER_HOURLY,
  LABEL_WEATHER_SUNRISE,
  LABEL_WEATHER_SUNSET,
  WEATHER_ICON_KEY,
} from '@/views/weather/weatherConstants'
import {
  formatHourLabel,
  formatMm,
  formatPct,
  formatTempC,
  formatWindMs,
  weatherIconByKey,
} from '@/views/weather/weatherFormat'
import type { WeatherHourlyItemDto } from '@/types/weather'

defineProps<{
  items: WeatherHourlyItemDto[]
}>()

function sunLabel(marker?: string | null): string {
  if (marker === WEATHER_ICON_KEY.SUNRISE) return LABEL_WEATHER_SUNRISE
  if (marker === WEATHER_ICON_KEY.SUNSET) return LABEL_WEATHER_SUNSET
  return ''
}
</script>

<template>
  <section class="hour" aria-label="시간별 예보">
    <h2 class="hour__title">{{ LABEL_WEATHER_HOURLY }}</h2>
    <div v-if="items.length" class="hour__wrap">
      <div class="hour__axis" aria-hidden="true">
        <span class="axis-time" />
        <span class="axis-ico" />
        <span>기온</span>
        <span>강수확률</span>
        <span>강수량</span>
        <span>습도</span>
        <span>바람</span>
      </div>
      <div class="hour__scroll" role="list">
        <article
          v-for="(row, idx) in items"
          :key="`${row.at}-${row.kind}-${idx}`"
          class="hour__cell"
          :class="{ 'hour__cell--sun': row.kind === 'sun' }"
          role="listitem"
        >
          <p class="hour__time">{{ formatHourLabel(row.at) }}</p>
          <template v-if="row.kind === 'sun'">
            <img
              class="hour__ico"
              :src="weatherIconByKey(row.marker)"
              alt=""
              aria-hidden="true"
            />
            <p class="hour__sun">{{ sunLabel(row.marker) }}</p>
            <p class="hour__pad" />
            <p class="hour__pad" />
            <p class="hour__pad" />
            <p class="hour__pad" />
          </template>
          <template v-else>
            <img
              class="hour__ico"
              :src="weatherIconByKey(row.icon, row.weather_cd)"
              alt=""
              aria-hidden="true"
            />
            <p class="hour__temp">{{ formatTempC(row.temp_c) }}</p>
            <p class="hour__pop">{{ formatPct(row.precip_prob_pct) }}</p>
            <p class="hour__mm">{{ formatMm(row.precip_mm) }}</p>
            <p class="hour__hum">{{ formatPct(row.humidity_pct) }}</p>
            <p class="hour__wind">{{ formatWindMs(row.wind_ms) }}</p>
          </template>
        </article>
      </div>
    </div>
    <p v-else class="hour__empty">시간별 예보가 없습니다.</p>
  </section>
</template>

<style scoped>
.hour {
  padding: var(--ods-space-12);
  border-radius: var(--ods-radius-card);
  background: var(--ods-color-white);
  border: 1px solid var(--ods-color-border);
  box-shadow: var(--ods-shadow-card);
}
.hour__title {
  margin: 0 0 10px;
  font: 700 15px/1.3 var(--ods-font-family);
  color: var(--ods-color-text);
}
.hour__wrap {
  display: flex;
  gap: 4px;
  min-width: 0;
}
.hour__axis {
  flex: 0 0 56px;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  padding: 6px 0;
  font: 11px/1.25 var(--ods-font-family);
  color: var(--ods-color-text-secondary);
}
.hour__axis .axis-time,
.hour__axis .axis-ico {
  height: 16px;
}
.hour__axis .axis-ico {
  height: 32px;
}
.hour__axis span {
  min-height: 16px;
  display: flex;
  align-items: center;
}
.hour__scroll {
  display: flex;
  gap: 2px;
  overflow-x: auto;
  flex: 1 1 auto;
  min-width: 0;
  padding-bottom: 4px;
  -webkit-overflow-scrolling: touch;
}
.hour__cell {
  flex: 0 0 56px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 6px 2px;
  border-radius: 8px;
  text-align: center;
}
.hour__cell--sun {
  background: color-mix(in srgb, var(--ods-color-caution) 18%, transparent);
}
.hour__time {
  margin: 0;
  min-height: 16px;
  font: 600 12px/1.2 var(--ods-font-family);
  color: var(--ods-color-text-secondary);
}
.hour__ico {
  width: 28px;
  height: 28px;
  margin: 2px 0;
}
.hour__temp,
.hour__pop,
.hour__mm,
.hour__hum,
.hour__wind,
.hour__sun,
.hour__pad {
  margin: 0;
  min-height: 16px;
  font: 12px/1.25 var(--ods-font-family);
  color: var(--ods-color-text);
}
.hour__pop {
  color: var(--ods-color-primary);
}
.hour__sun {
  font-weight: 600;
  color: var(--ods-color-caution);
}
.hour__empty {
  margin: 0;
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
}
</style>
