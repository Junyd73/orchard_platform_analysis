<script setup lang="ts">
import { computed } from 'vue'

import OdsCard from '@/components/ods/OdsCard.vue'
import {
  currentTempLabel,
  weatherIconSrc,
} from '@/views/work-log/workLogConstants'
import type { WorkLogMasterDto } from '@/types/workLog'

const props = defineProps<{
  master: WorkLogMasterDto | null
  loading?: boolean
}>()

const emit = defineEmits<{
  forecast: []
}>()

const iconSrc = computed(() =>
  weatherIconSrc(props.master?.weather_cd, props.master?.weather_nm),
)

const currentTemp = computed(() =>
  props.loading
    ? '…'
    : currentTempLabel(props.master?.temp_min, props.master?.temp_max),
)

function rangeLine(master: WorkLogMasterDto | null): string {
  if (!master) return '최고/최저 —'
  const max = master.temp_max
  const min = master.temp_min
  if (max == null && min == null) return '최고/최저 —'
  return `최고 ${max != null ? `${max}℃` : '—'} · 최저 ${min != null ? `${min}℃` : '—'}`
}
</script>

<template>
  <OdsCard>
    <section class="wx" aria-label="기상">
      <img class="wx__illust" :src="iconSrc" alt="" />
      <div class="wx__main">
        <div class="wx__top">
          <p class="wx__temp">{{ currentTemp }}</p>
          <button type="button" class="wx__link" @click="emit('forecast')">
            시간별 예보 &gt;
          </button>
        </div>
        <p class="wx__meta">
          <template v-if="loading">불러오는 중…</template>
          <template v-else-if="master">
            {{ master.weather_nm || '날씨 미입력' }}
            · {{ rangeLine(master) }}
            · 강수 {{ master.precip != null ? `${master.precip}mm` : '—' }}
            · 습도 {{ master.humidity != null ? `${master.humidity}%` : '—' }}
            · 풍속 {{ master.wind_max != null ? `${master.wind_max}m/s` : '—' }}
          </template>
          <template v-else>오늘 기상 기록이 없습니다. 일간에서 입력할 수 있습니다.</template>
        </p>
      </div>
    </section>
  </OdsCard>
</template>

<style scoped>
.wx {
  display: flex;
  align-items: flex-start;
  gap: var(--ods-space-12);
}
.wx__illust {
  width: 56px;
  height: 56px;
  flex-shrink: 0;
}
.wx__main {
  flex: 1;
  min-width: 0;
}
.wx__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ods-space-8);
}
.wx__temp {
  margin: 0;
  font: var(--ods-font-title-2);
  color: var(--ods-color-text);
}
.wx__link {
  flex-shrink: 0;
  border: none;
  background: transparent;
  padding: 0;
  min-height: var(--ods-touch-min);
  font: var(--ods-font-body-2);
  font-weight: 700;
  color: var(--ods-color-primary);
  cursor: pointer;
}
.wx__meta {
  margin: var(--ods-space-8) 0 0;
  font: var(--ods-font-body-2);
  color: var(--ods-color-text-secondary);
}
</style>
