<script setup lang="ts">
import { computed, ref } from 'vue'

import { daysInMonth, pad2 } from '@/views/work-log/workLogConstants'
import type { WorkLogDayCell } from '@/types/workLog'

const props = defineProps<{
  year: number
  month: number
  days: Record<string, WorkLogDayCell>
}>()

const AXIS = [1, 7, 14, 21, 28] as const
const tip = ref('')

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
  return counts.map((c, i) => ({
    day: i + 1,
    count: c,
    pct: Math.round((c / max) * 100),
  }))
})

const isEmpty = computed(() => bars.value.every((b) => b.count === 0))

const axisLabels = computed(() => {
  const last = daysInMonth(props.year, props.month)
  const labels = [...AXIS]
  if (!labels.includes(last as (typeof AXIS)[number])) labels.push(last)
  return labels
})

function showTip(day: number, count: number) {
  if (isEmpty.value) return
  tip.value = `${day}일 · ${count}건`
}
function clearTip() {
  tip.value = ''
}
</script>

<template>
  <section class="chart" aria-label="작업 일자 분포">
    <h2 class="chart__title">작업 일자 분포</h2>
    <div class="chart__card" :class="{ 'chart__card--empty': isEmpty }">
      <p v-if="tip" class="chart__tip" role="status">{{ tip }}</p>
      <div class="chart__plot">
        <div class="chart__grid" aria-hidden="true">
          <span /><span /><span /><span />
        </div>
        <div
          class="chart__bars"
          role="img"
          :aria-label="`${year}년 ${month}월 일별 작업 건수`"
        >
          <button
            v-for="b in bars"
            :key="b.day"
            type="button"
            class="chart__bar"
            :class="{ 'chart__bar--empty': b.count === 0 }"
            :style="{
              height: isEmpty
                ? '10px'
                : `${Math.max(b.count === 0 ? 6 : 10, (b.pct / 100) * 72)}px`,
            }"
            :title="isEmpty ? undefined : `${b.day}일 · ${b.count}건`"
            :tabindex="isEmpty ? -1 : 0"
            @mouseenter="showTip(b.day, b.count)"
            @mouseleave="clearTip"
            @focus="showTip(b.day, b.count)"
            @blur="clearTip"
          />
        </div>
      </div>
      <div class="chart__axis">
        <span v-for="d in axisLabels" :key="d">{{ d }}일</span>
      </div>
    </div>
  </section>
</template>

<style scoped>
.chart__title {
  margin: 0 0 var(--ods-space-12);
  font: var(--ods-font-headline);
  font-weight: 800;
  color: var(--ods-color-text);
}
.chart__card {
  position: relative;
  padding: var(--ods-space-16);
  border-radius: var(--ods-radius-card-lg);
  background: var(--ods-color-white);
  box-shadow: var(--ods-shadow-card);
}
.chart__card--empty .chart__bar--empty {
  background: color-mix(in srgb, var(--ods-color-primary) 12%, var(--ods-color-gray-100));
  opacity: 0.85;
}
.chart__tip {
  position: absolute;
  top: var(--ods-space-8);
  right: var(--ods-space-16);
  margin: 0;
  padding: var(--ods-space-4) var(--ods-space-8);
  border-radius: var(--ods-radius-button);
  background: var(--ods-color-gray-900);
  color: var(--ods-color-white);
  font: var(--ods-font-caption);
  font-weight: 600;
}
.chart__plot {
  position: relative;
  height: 80px;
}
.chart__grid {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  pointer-events: none;
}
.chart__grid span {
  display: block;
  height: 1px;
  background: var(--ods-color-gray-100);
}
.chart__bars {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: flex-end;
  gap: 3px;
  height: 80px;
}
.chart__bar {
  flex: 1;
  min-width: 0;
  margin: 0;
  padding: 0;
  border: none;
  border-radius: 2px 2px 0 0;
  background: var(--ods-color-primary);
  cursor: pointer;
}
.chart__bar--empty {
  background: var(--ods-color-gray-100);
}
.chart__card--empty .chart__bar {
  cursor: default;
  pointer-events: none;
}
.chart__bar:hover,
.chart__bar:focus-visible {
  filter: brightness(1.08);
  outline: none;
}
.chart__axis {
  display: flex;
  justify-content: space-between;
  margin-top: var(--ods-space-8);
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
}
</style>
