<script setup lang="ts">
import { computed } from 'vue'

import OdsCard from '@/components/ods/OdsCard.vue'
import { daysInMonth, pad2 } from '@/views/work-log/workLogConstants'
import type { WorkLogDayCell } from '@/types/workLog'

const props = defineProps<{
  year: number
  month: number
  days: Record<string, WorkLogDayCell>
}>()

const bars = computed(() => {
  const total = daysInMonth(props.year, props.month)
  const counts: number[] = []
  let max = 1
  for (let d = 1; d <= total; d += 1) {
    const iso = `${props.year}-${pad2(props.month)}-${pad2(d)}`
    const c = Number(props.days[iso]?.work_count || 0)
    counts.push(c)
    if (c > max) max = c
  }
  return counts.map((c) => ({
    count: c,
    pct: Math.round((c / max) * 100),
  }))
})
</script>

<template>
  <section class="chart" aria-label="작업 일자 분포">
    <h2 class="chart__title">작업 일자 분포</h2>
    <OdsCard>
      <div class="chart__bars" role="img" :aria-label="`${year}년 ${month}월 일별 작업 건수`">
        <div
          v-for="(b, i) in bars"
          :key="i"
          class="chart__bar"
          :class="{ 'chart__bar--empty': b.count === 0 }"
          :style="{ height: `${Math.max(b.count === 0 ? 8 : 12, (b.pct / 100) * 64)}px` }"
          :title="`${i + 1}일 · ${b.count}건`"
        />
      </div>
      <p class="chart__hint">막대 높이 = 해당 일 작업 건수</p>
    </OdsCard>
  </section>
</template>

<style scoped>
.chart__title {
  margin: 0 0 var(--ods-space-8);
  font: var(--ods-font-headline);
  color: var(--ods-color-text);
}
.chart__bars {
  display: flex;
  align-items: flex-end;
  gap: var(--ods-space-4);
  height: 72px;
}
.chart__bar {
  flex: 1;
  min-width: 0;
  border-radius: 3px 3px 0 0;
  background: var(--ods-color-primary);
}
.chart__bar--empty {
  background: var(--ods-color-gray-100);
  opacity: 0.7;
}
.chart__hint {
  margin: var(--ods-space-8) 0 0;
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
}
</style>
