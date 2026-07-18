<script setup lang="ts">
import { computed } from 'vue'

import OdsButton from '@/components/ods/OdsButton.vue'
import { weatherIconSrc } from '@/views/work-log/workLogConstants'
import type { WorkLogMasterDto } from '@/types/workLog'

const props = defineProps<{
  master: WorkLogMasterDto | null
  weatherNmFallback?: string | null
  weatherCdFallback?: string | null
  loading?: boolean
}>()

const emit = defineEmits<{
  forecast: []
}>()

const weatherCd = computed(
  () => props.master?.weather_cd || props.weatherCdFallback || null,
)
const weatherNm = computed(() => {
  const fromMaster = String(props.master?.weather_nm || '').trim()
  if (fromMaster && fromMaster !== '-') return fromMaster
  const fb = String(props.weatherNmFallback || '').trim()
  if (fb && fb !== '-') return fb
  return ''
})

const iconSrc = computed(() => weatherIconSrc(weatherCd.value, weatherNm.value))

const tempMax = computed(() => {
  if (props.loading) return '…'
  const v = props.master?.temp_max
  return v != null ? `${v}℃` : '—'
})

const tempMin = computed(() => {
  if (props.loading) return '…'
  const v = props.master?.temp_min
  return v != null ? `${v}℃` : '—'
})

function part(value: string | number | null | undefined, unit: string): string {
  if (value == null || value === '') return '—'
  return `${value}${unit}`
}
</script>

<template>
  <section class="wx anim-fade" aria-label="오늘의 기상">
    <div class="wx__left">
      <div class="wx__top">
        <img class="wx__icon" :src="iconSrc" alt="" />
        <p class="wx__temp">
          <span class="wx__temp-max">{{ tempMax }}</span>
          <span class="wx__temp-sep"> / </span>
          <span class="wx__temp-min">{{ tempMin }}</span>
        </p>
      </div>
      <p class="wx__meta">
        <template v-if="loading">불러오는 중…</template>
        <template v-else>
          <span>{{ weatherNm || '날씨 미입력' }}</span>
          <span class="wx__pipe" aria-hidden="true" />
          <span>강수 {{ part(master?.precip, 'mm') }}</span>
          <span class="wx__pipe" aria-hidden="true" />
          <span>습도 {{ part(master?.humidity, '%') }}</span>
          <span class="wx__pipe" aria-hidden="true" />
          <span>바람 {{ part(master?.wind_max, 'm/s') }}</span>
        </template>
      </p>
    </div>
    <OdsButton
      variant="secondary-filled"
      type="button"
      :block="false"
      class="wx__btn"
      @click="emit('forecast')"
    >
      시간별 예보 &gt;
    </OdsButton>
  </section>
</template>

<style scoped>
.wx {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ods-space-12);
  min-height: 112px;
  padding: var(--ods-space-16);
  border-radius: var(--ods-radius-card-lg);
  background: var(--ods-color-white);
  box-shadow: var(--ods-shadow-elevated);
}
.wx__left {
  flex: 1;
  min-width: 0;
}
.wx__top {
  display: flex;
  align-items: center;
  gap: var(--ods-space-12);
}
.wx__icon {
  width: 44px;
  height: 44px;
  flex-shrink: 0;
}
.wx__temp {
  margin: 0;
  line-height: 1.1;
  letter-spacing: -0.03em;
}
.wx__temp-max {
  font-size: 40px;
  font-weight: 800;
  color: var(--ods-color-text);
}
.wx__temp-sep,
.wx__temp-min {
  font-size: 22px;
  font-weight: 700;
  color: var(--ods-color-gray-500);
}
.wx__meta {
  margin: var(--ods-space-8) 0 0;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
  line-height: 1.4;
}
.wx__meta > span {
  white-space: nowrap;
}
.wx__pipe {
  display: inline-block;
  width: 1px;
  height: 10px;
  margin: 0 var(--ods-space-8);
  background: var(--ods-color-border);
  vertical-align: middle;
}
.wx__btn {
  flex-shrink: 0;
  min-height: 40px !important;
  padding: 0 var(--ods-space-12) !important;
  border-radius: var(--ods-radius-badge) !important;
  font: var(--ods-font-caption) !important;
  font-weight: 700 !important;
}
.anim-fade {
  animation: wl-fade var(--ods-motion-base) var(--ods-motion-ease) both;
}
@keyframes wl-fade {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}
@media (max-width: 359px) {
  .wx__temp-max {
    font-size: 32px;
  }
  .wx__temp-sep,
  .wx__temp-min {
    font-size: 18px;
  }
}
@media (prefers-reduced-motion: reduce) {
  .anim-fade {
    animation: none;
  }
}
</style>
