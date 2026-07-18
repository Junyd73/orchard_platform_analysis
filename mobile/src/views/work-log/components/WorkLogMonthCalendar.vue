<script setup lang="ts">
import { computed } from 'vue'

import {
  daysInMonth,
  firstWeekdaySun0,
  isFutureDate,
  pad2,
  todayIso,
  weatherIconForCd,
  WEEKDAY_LABELS,
} from '@/views/work-log/workLogConstants'
import type { WorkLogDayCell } from '@/types/workLog'

const props = defineProps<{
  year: number
  month: number
  days: Record<string, WorkLogDayCell>
}>()

const emit = defineEmits<{
  select: [workDt: string]
  blocked: [message: string]
}>()

const today = todayIso()

const cells = computed(() => {
  const total = daysInMonth(props.year, props.month)
  const start = firstWeekdaySun0(props.year, props.month)
  const out: Array<{
    key: string
    day: number | null
    iso: string | null
    cell: WorkLogDayCell | null
    future: boolean
    isToday: boolean
  }> = []
  for (let i = 0; i < start; i += 1) {
    out.push({ key: `e-${i}`, day: null, iso: null, cell: null, future: false, isToday: false })
  }
  for (let d = 1; d <= total; d += 1) {
    const iso = `${props.year}-${pad2(props.month)}-${pad2(d)}`
    const cell = props.days[iso] || null
    out.push({
      key: iso,
      day: d,
      iso,
      cell,
      future: isFutureDate(iso, today),
      isToday: iso === today,
    })
  }
  return out
})

function onTap(iso: string | null, future: boolean) {
  if (!iso) return
  if (future) {
    emit('blocked', '영농일지는 오늘까지만 작성할 수 있습니다.')
    return
  }
  emit('select', iso)
}
</script>

<template>
  <section class="cal" aria-label="월간 캘린더">
    <div class="cal__head">
      <span v-for="w in WEEKDAY_LABELS" :key="w" class="cal__wd">{{ w }}</span>
    </div>
    <div class="cal__grid">
      <button
        v-for="c in cells"
        :key="c.key"
        type="button"
        class="cal__cell"
        :class="{
          'cal__cell--empty': !c.day,
          'cal__cell--future': c.future,
          'cal__cell--today': c.isToday,
          'cal__cell--progress': c.cell?.has_in_progress,
          'cal__cell--work': c.cell?.has_work && !c.cell?.has_in_progress,
        }"
        :disabled="!c.day"
        :aria-label="c.iso || undefined"
        @click="onTap(c.iso, c.future)"
      >
        <template v-if="c.day">
          <div class="cal__dayrow">
            <span class="cal__day">{{ c.day }}</span>
            <span v-if="c.cell?.has_issue" class="cal__dot" title="이슈" />
            <span class="cal__wx">{{
              weatherIconForCd(c.cell?.weather_cd, c.cell?.weather_nm)
            }}</span>
          </div>
          <p
            v-for="(nm, idx) in (c.cell?.work_names || []).slice(0, 2)"
            :key="`${c.iso}-${idx}`"
            class="cal__work"
          >
            {{ nm }}
          </p>
          <p v-if="(c.cell?.extra_work_count || 0) > 0" class="cal__more">
            외 {{ c.cell?.extra_work_count }}건
          </p>
        </template>
      </button>
    </div>
  </section>
</template>

<style scoped>
.cal {
  background: var(--ods-color-white);
  border: 1px solid var(--ods-color-border);
  border-radius: var(--ods-radius-card);
  padding: var(--ods-space-12);
  box-shadow: var(--ods-shadow-card);
}
.cal__head,
.cal__grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 4px;
}
.cal__wd {
  text-align: center;
  font: var(--ods-font-caption);
  font-weight: 700;
  color: var(--ods-color-text-secondary);
  padding: 6px 0;
}
.cal__cell {
  min-height: 78px;
  margin: 0;
  padding: 5px;
  border: 1px solid transparent;
  border-radius: var(--ods-radius-button);
  background: transparent;
  text-align: left;
  vertical-align: top;
  cursor: pointer;
  color: var(--ods-color-text);
}
.cal__cell--empty {
  cursor: default;
  visibility: hidden;
}
.cal__cell--future {
  opacity: 0.38;
  cursor: not-allowed;
}
.cal__cell--today {
  border-color: var(--ods-color-primary);
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--ods-color-primary) 35%, transparent);
}
.cal__cell--work {
  background: color-mix(in srgb, var(--ods-color-primary) 8%, white);
}
.cal__cell--progress {
  background: color-mix(in srgb, var(--ods-color-accent) 55%, white);
}
.cal__dayrow {
  display: flex;
  align-items: center;
  gap: 3px;
  min-height: 18px;
}
.cal__day {
  font: var(--ods-font-caption);
  font-weight: 700;
}
.cal__dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--ods-color-danger);
}
.cal__wx {
  margin-left: auto;
  font-size: 11px;
  line-height: 1;
}
.cal__work,
.cal__more {
  margin: 2px 0 0;
  font-size: 10px;
  line-height: 1.25;
  color: var(--ods-color-text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.cal__more {
  color: var(--ods-color-primary);
  font-weight: 600;
}
</style>
