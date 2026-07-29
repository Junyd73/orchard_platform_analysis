<script setup lang="ts">
import iconWeather from '@/assets/ods/home/icon-title-weather.svg'
import wxHumidity from '@/assets/ods/work-log/wx-humidity.svg'
import wxPrecip from '@/assets/ods/work-log/wx-precip.svg'
import wxSunny from '@/assets/ods/work-log/wx-sunny.svg'
import wxWind from '@/assets/ods/work-log/wx-wind.svg'
import HomeCardHead from '@/views/home/components/HomeCardHead.vue'
import {
  BTN_HOME_DETAIL,
  LABEL_HOME_WEATHER,
} from '@/views/home/homeConstants'
import type { HomeWeatherMock } from '@/views/home/homeMock'

defineProps<{
  weather: HomeWeatherMock
}>()

const emit = defineEmits<{
  detail: []
}>()
</script>

<template>
  <section class="card" aria-label="현재 날씨">
    <HomeCardHead
      :title="LABEL_HOME_WEATHER"
      :icon="iconWeather"
      :detail-label="BTN_HOME_DETAIL"
      @detail="emit('detail')"
    />
    <p class="card__loc">{{ weather.location }}</p>
    <div class="main">
      <img class="main__ico" :src="wxSunny" alt="" aria-hidden="true" />
      <div>
        <p class="main__temp">{{ weather.tempC }}°</p>
        <p class="main__sky">{{ weather.skyLabel }}</p>
        <p class="main__range">
          {{ weather.tempMinC }}° / {{ weather.tempMaxC }}°
        </p>
      </div>
    </div>
    <ul class="meta">
      <li>
        <img :src="wxHumidity" alt="" aria-hidden="true" />
        <span>{{ weather.humidityPct }}%</span>
      </li>
      <li>
        <img :src="wxWind" alt="" aria-hidden="true" />
        <span>{{ weather.windMs }}m/s</span>
      </li>
      <li>
        <img :src="wxPrecip" alt="" aria-hidden="true" />
        <span>{{ weather.precipPct }}%</span>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.card {
  display: flex;
  flex-direction: column;
  min-height: 100%;
  min-width: 0;
  padding: var(--ods-space-12);
  border-radius: var(--ods-radius-card);
  background: var(--ods-color-white);
  border: 1px solid var(--ods-color-border);
  box-shadow: var(--ods-shadow-card);
  box-sizing: border-box;
}
.card__loc {
  margin: -2px 0 8px;
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.main {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1 1 auto;
}
.main__ico {
  width: 40px;
  height: 40px;
  flex-shrink: 0;
}
.main__temp {
  margin: 0;
  font: 700 24px/1.1 var(--ods-font-family);
  color: var(--ods-color-text);
}
.main__sky {
  margin: 1px 0 0;
  font: var(--ods-font-caption);
}
.main__range {
  margin: 1px 0 0;
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
}
.meta {
  margin: 8px 0 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-wrap: wrap;
  gap: 6px 10px;
}
.meta li {
  display: flex;
  align-items: center;
  gap: 4px;
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
}
.meta img {
  width: 12px;
  height: 12px;
}
</style>
