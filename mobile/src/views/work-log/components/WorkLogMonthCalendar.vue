<script setup lang="ts">
import { computed } from 'vue'

import iconExpense from '@/assets/ods/work-log/icon-expense.svg'
import iconLabor from '@/assets/ods/work-log/icon-labor.svg'
import iconWork from '@/assets/ods/work-log/icon-work.svg'
import OdsCard from '@/components/ods/OdsCard.vue'
import {
  buildCalendarLines,
  daysInMonth,
  firstWeekdaySun0,
  isFutureDate,
  pad2,
  todayIso,
  WEEKDAY_LABELS,
  type WorkFilterKey,
} from '@/views/work-log/workLogConstants'
import type { WorkLogDayCell } from '@/types/workLog'

const props = defineProps<{
  year: number
  month: number
  days: Record<string, WorkLogDayCell>
  filters: Record<WorkFilterKey, boolean>
}>()

const emit = defineEmits<{
  select: [workDt: string]
  blocked: [message: string]
}>()

const today = todayIso()

const iconByKind: Record<string, string> = {
  work: iconWork,
  labor: iconLabor,
  expense: iconExpense,
  weather: iconWork,
  other: iconWork,
}

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
    lines: ReturnType<typeof buildCalendarLines>['lines']
    extra: number
  }> = []
  for (let i = 0; i < start; i += 1) {
    out.push({
      key: `e-${i}`,
      day: null,
      iso: null,
      cell: null,
      future: false,
      isToday: false,
      lines: [],
      extra: 0,
    })
  }
  for (let d = 1; d <= total; d += 1) {
    const iso = `${props.year}-${pad2(props.month)}-${pad2(d)}`
    const cell = props.days[iso] || null
    const built = buildCalendarLines(cell, props.filters)
    out.push({
      key: iso,
      day: d,
      iso,
      cell,
      future: isFutureDate(iso, today),
      isToday: iso === today,
      lines: built.lines,
      extra: built.extra,
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
  <OdsCard>
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
            </div>
            <p v-for="(line, idx) in c.lines" :key="`${c.iso}-${idx}`" class="cal__work">
              <img
                v-if="iconByKind[line.kind]"
                class="cal__line-ico"
                :src="iconByKind[line.kind]"
                alt=""
              />
              {{ line.text }}
            </p>
            <p v-if="c.extra > 0" class="cal__more">+{{ c.extra }}</p>
          </template>
        </button>
      </div>
      <div class="cal__legend" aria-label="범례">
        <span class="cal__leg">
          <img class="cal__leg-ico" :src="iconWork" alt="" />작업
        </span>
        <span class="cal__leg">
          <img class="cal__leg-ico" :src="iconLabor" alt="" />인력
        </span>
        <span class="cal__leg">
          <img class="cal__leg-ico" :src="iconExpense" alt="" />경비
        </span>
        <span class="cal__leg"><i class="cal__leg-dot" />이슈</span>
        <span class="cal__leg">
          <i class="cal__leg-swatch cal__leg-swatch--progress" />진행중
        </span>
      </div>
    </section>
  </OdsCard>
</template>

<style scoped>
.cal {
  margin: 0;
}
.cal__head,
.cal__grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: var(--ods-space-4);
}
.cal__wd {
  text-align: center;
  font: var(--ods-font-caption);
  font-weight: 700;
  color: var(--ods-color-text-secondary);
  padding: 6px 0;
}
.cal__cell {
  min-height: 84px;
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
  box-shadow: inset 0 0 0 1px
    color-mix(in srgb, var(--ods-color-primary) 35%, transparent);
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
.cal__work,
.cal__more {
  margin: 2px 0 0;
  font-size: 10px;
  line-height: 1.25;
  color: var(--ods-color-text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  display: flex;
  align-items: center;
  gap: 2px;
}
.cal__line-ico {
  width: 10px;
  height: 10px;
  flex-shrink: 0;
}
.cal__more {
  color: var(--ods-color-primary);
  font-weight: 600;
}
.cal__legend {
  display: flex;
  flex-wrap: wrap;
  gap: var(--ods-space-12);
  margin-top: var(--ods-space-16);
  padding-top: var(--ods-space-12);
  border-top: 1px solid var(--ods-color-border);
}
.cal__leg {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
}
.cal__leg-ico {
  width: 14px;
  height: 14px;
}
.cal__leg-swatch {
  display: inline-block;
  width: 12px;
  height: 12px;
  border-radius: 3px;
}
.cal__leg-swatch--progress {
  background: color-mix(in srgb, var(--ods-color-accent) 55%, white);
  border: 1px solid var(--ods-color-caution, #c9a227);
}
.cal__leg-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--ods-color-danger);
}
</style>
