<script setup lang="ts">
/**
 * 월간 기상 — 일간(WorkLogDailyWeatherStrip)과 동일 스타일.
 * 캘린더 셀 weather fallback만 추가로 받습니다.
 */
import WorkLogDailyWeatherStrip from '@/views/work-log/components/WorkLogDailyWeatherStrip.vue'
import type { WorkLogMasterDto } from '@/types/workLog'

defineProps<{
  master: WorkLogMasterDto | null
  weatherNmFallback?: string | null
  weatherCdFallback?: string | null
  loading?: boolean
}>()
</script>

<template>
  <div class="anim-fade">
    <WorkLogDailyWeatherStrip
      :master="master"
      :weather-nm-fallback="weatherNmFallback"
      :weather-cd-fallback="weatherCdFallback"
      :loading="loading"
    />
  </div>
</template>

<style scoped>
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
@media (prefers-reduced-motion: reduce) {
  .anim-fade {
    animation: none;
  }
}
</style>
