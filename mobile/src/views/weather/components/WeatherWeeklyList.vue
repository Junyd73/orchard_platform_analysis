<script setup lang="ts">
import { computed, ref } from 'vue'

import {
  BTN_WEATHER_WEEKLY_LESS,
  BTN_WEATHER_WEEKLY_MORE,
  LABEL_WEATHER_AM,
  LABEL_WEATHER_PM,
  LABEL_WEATHER_WEEKLY,
  LABEL_WEATHER_WEEKLY_NOTE,
  WEATHER_WEEKLY_COLLAPSED_DAYS,
} from '@/views/weather/weatherConstants'
import {
  formatPct,
  formatTempC,
  weatherIconByKey,
  weeklyDateLabel,
} from '@/views/weather/weatherFormat'
import type { WeatherWeeklyItemDto } from '@/types/weather'

const props = defineProps<{
  items: WeatherWeeklyItemDto[]
}>()

const expanded = ref(false)

const visible = computed(() => {
  if (expanded.value) return props.items
  return props.items.slice(0, WEATHER_WEEKLY_COLLAPSED_DAYS)
})

const canToggle = computed(
  () => props.items.length > WEATHER_WEEKLY_COLLAPSED_DAYS,
)
</script>

<template>
  <section class="week" aria-label="주간예보">
    <h2 class="week__title">{{ LABEL_WEATHER_WEEKLY }}</h2>
    <ul class="week__list">
      <li v-for="row in visible" :key="row.date" class="week__row">
        <div class="week__day">
          <span class="week__date">{{ weeklyDateLabel(row.date, row.weekday) }}</span>
          <img
            class="week__ico"
            :src="weatherIconByKey(row.icon)"
            alt=""
            aria-hidden="true"
          />
        </div>
        <div class="week__ampm" :aria-label="LABEL_WEATHER_AM">
          <span class="lbl">{{ LABEL_WEATHER_AM }}</span>
          <span class="pop">{{ formatPct(row.am.precip_prob_pct) }}</span>
        </div>
        <div class="week__ampm" :aria-label="LABEL_WEATHER_PM">
          <span class="lbl">{{ LABEL_WEATHER_PM }}</span>
          <span class="pop">{{ formatPct(row.pm.precip_prob_pct) }}</span>
        </div>
        <div class="week__temps">
          <span class="min">{{ formatTempC(row.temp_min) }}</span>
          <span class="max">{{ formatTempC(row.temp_max) }}</span>
        </div>
      </li>
    </ul>
    <button
      v-if="canToggle"
      type="button"
      class="week__more"
      @click="expanded = !expanded"
    >
      {{ expanded ? BTN_WEATHER_WEEKLY_LESS : BTN_WEATHER_WEEKLY_MORE }}
    </button>
    <p class="week__note">{{ LABEL_WEATHER_WEEKLY_NOTE }}</p>
  </section>
</template>

<style scoped>
.week {
  padding: var(--ods-space-12);
  border-radius: var(--ods-radius-card);
  background: var(--ods-color-white);
  border: 1px solid var(--ods-color-border);
  box-shadow: var(--ods-shadow-card);
}
.week__title {
  margin: 0 0 10px;
  font: 700 15px/1.3 var(--ods-font-family);
  color: var(--ods-color-text);
}
.week__list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.week__row {
  display: grid;
  grid-template-columns: minmax(72px, 1.1fr) 1fr 1fr auto;
  align-items: center;
  gap: 6px;
  padding: 10px 2px;
  border-bottom: 1px solid var(--ods-color-border);
}
.week__row:last-child {
  border-bottom: none;
}
.week__day {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}
.week__date {
  font: 600 13px/1.2 var(--ods-font-family);
  color: var(--ods-color-text);
  white-space: nowrap;
}
.week__ico {
  width: 22px;
  height: 22px;
  flex-shrink: 0;
}
.week__ampm {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}
.week__ampm .lbl {
  font: 11px/1.2 var(--ods-font-family);
  color: var(--ods-color-text-secondary);
}
.week__ampm .pop {
  font: 600 13px/1.2 var(--ods-font-family);
  color: var(--ods-color-primary);
}
.week__temps {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
  min-width: 36px;
  font: 600 13px/1.2 var(--ods-font-family);
}
.week__temps .min {
  color: var(--ods-color-primary);
}
.week__temps .max {
  color: var(--ods-color-danger);
}
.week__more {
  margin-top: 8px;
  width: 100%;
  padding: 10px;
  border: 1px solid var(--ods-color-border);
  border-radius: 8px;
  background: var(--ods-color-bg-muted);
  font: 600 13px/1.2 var(--ods-font-family);
  color: var(--ods-color-text);
  cursor: pointer;
}
.week__note {
  margin: 10px 0 0;
  font: 11px/1.4 var(--ods-font-family);
  color: var(--ods-color-text-secondary);
}
</style>
