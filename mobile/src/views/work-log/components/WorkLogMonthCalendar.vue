<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import iconCalendar from '@/assets/ods/work-log/icon-calendar.svg'
import OdsButton from '@/components/ods/OdsButton.vue'
import OdsEmptyState from '@/components/ods/OdsEmptyState.vue'
import {
  buildCalendarLines,
  CALENDAR_KIND_COLOR,
  CALENDAR_KIND_ICON,
  daysInMonth,
  firstWeekdayMon0,
  isFutureDate,
  monthLabel,
  pad2,
  shiftMonth,
  todayIso,
  WEEKDAY_LABELS_MON,
  WORK_FILTER_OPTIONS,
  type WorkFilterKey,
} from '@/views/work-log/workLogConstants'
import type { WorkLogDayCell } from '@/types/workLog'

const props = defineProps<{
  year: number
  month: number
  days: Record<string, WorkLogDayCell>
  filters: Record<WorkFilterKey, boolean>
  canGoNext?: boolean
  loading?: boolean
  showEmpty?: boolean
}>()

const emit = defineEmits<{
  select: [workDt: string]
  blocked: [message: string]
  'open-filter': []
  'go-today': []
  'prev-month': []
  'next-month': []
}>()

const today = todayIso()
const title = computed(() => monthLabel(props.year, props.month))
const slideDir = ref<'left' | 'right' | 'none'>('none')
const monthKey = computed(() => `${props.year}-${props.month}`)

watch(
  () => monthKey.value,
  (next, prev) => {
    if (!prev) {
      slideDir.value = 'none'
      return
    }
    slideDir.value = next > prev ? 'left' : 'right'
  },
)

type CalCell = {
  key: string
  day: number
  iso: string
  inMonth: boolean
  future: boolean
  isToday: boolean
  isSunday: boolean
  cell: WorkLogDayCell | null
  lines: ReturnType<typeof buildCalendarLines>['lines']
  extra: number
}

const cells = computed((): CalCell[] => {
  const total = daysInMonth(props.year, props.month)
  const start = firstWeekdayMon0(props.year, props.month)
  const out: CalCell[] = []

  const prev = shiftMonth(props.year, props.month, -1)
  const prevTotal = daysInMonth(prev.year, prev.month)
  for (let i = start - 1; i >= 0; i -= 1) {
    const d = prevTotal - i
    const iso = `${prev.year}-${pad2(prev.month)}-${pad2(d)}`
    out.push({
      key: `p-${iso}`,
      day: d,
      iso,
      inMonth: false,
      future: isFutureDate(iso, today),
      isToday: false,
      isSunday: new Date(`${iso}T12:00:00`).getDay() === 0,
      cell: null,
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
      inMonth: true,
      future: isFutureDate(iso, today),
      isToday: iso === today,
      isSunday: new Date(`${iso}T12:00:00`).getDay() === 0,
      cell,
      lines: built.lines,
      extra: built.extra,
    })
  }

  const next = shiftMonth(props.year, props.month, 1)
  let n = 1
  while (out.length % 7 !== 0) {
    const iso = `${next.year}-${pad2(next.month)}-${pad2(n)}`
    out.push({
      key: `n-${iso}`,
      day: n,
      iso,
      inMonth: false,
      future: isFutureDate(iso, today),
      isToday: false,
      isSunday: new Date(`${iso}T12:00:00`).getDay() === 0,
      cell: null,
      lines: [],
      extra: 0,
    })
    n += 1
  }
  return out
})

const hasAnyWork = computed(() =>
  Object.values(props.days).some((d) => d.has_work || Number(d.work_count || 0) > 0),
)

function onTap(c: CalCell) {
  if (!c.inMonth) {
    if (c.iso < `${props.year}-${pad2(props.month)}-01`) emit('prev-month')
    else emit('next-month')
    return
  }
  if (c.future) {
    emit('blocked', '영농일지는 오늘까지만 작성할 수 있습니다.')
    return
  }
  emit('select', c.iso)
}
</script>

<template>
  <section class="cal-card" aria-label="월간 캘린더">
    <div class="cal-card__head">
      <div class="cal-card__title-wrap">
        <img class="cal-card__cal-ico" :src="iconCalendar" alt="" />
        <button
          type="button"
          class="cal-card__title-btn"
          :aria-label="`${title} · 이전 달`"
          @click="emit('prev-month')"
        >
          ‹
        </button>
        <h2 class="cal-card__title">{{ title }}</h2>
        <button
          type="button"
          class="cal-card__title-btn"
          :aria-label="`${title} · 다음 달`"
          :disabled="canGoNext === false"
          @click="emit('next-month')"
        >
          ›
        </button>
      </div>
      <div class="cal-card__actions">
        <OdsButton
          variant="secondary"
          type="button"
          :block="false"
          class="cal-card__chip"
          @click="emit('open-filter')"
        >
          작업 필터⌄
        </OdsButton>
        <OdsButton
          variant="primary"
          type="button"
          :block="false"
          class="cal-card__chip"
          @click="emit('go-today')"
        >
          오늘
        </OdsButton>
      </div>
    </div>

    <div
      :key="monthKey"
      class="cal-slide"
      :class="{
        'cal-slide--left': slideDir === 'left',
        'cal-slide--right': slideDir === 'right',
      }"
    >
      <div class="cal__head">
        <span
          v-for="(w, i) in WEEKDAY_LABELS_MON"
          :key="w"
          class="cal__wd"
          :class="{ 'cal__wd--sun': i === 6 }"
        >
          {{ w }}
        </span>
      </div>

      <div class="cal__grid">
        <button
          v-for="c in cells"
          :key="c.key"
          type="button"
          class="cal__cell"
          :class="{
            'cal__cell--out': !c.inMonth,
            'cal__cell--future': c.inMonth && c.future,
            'cal__cell--today': c.isToday,
            'cal__cell--work': c.inMonth && c.cell?.has_work && !c.isToday,
          }"
          @click="onTap(c)"
        >
          <span
            class="cal__day"
            :class="{ 'cal__day--sun': c.isSunday && c.inMonth }"
          >
            {{ c.day }}
          </span>
          <template v-if="c.inMonth">
            <div class="cal__events">
              <p
                v-for="(line, idx) in c.lines"
                :key="`${c.iso}-${idx}`"
                class="cal__line"
              >
                <img
                  class="cal__line-ico"
                  :src="CALENDAR_KIND_ICON[line.kind]"
                  alt=""
                />
                <span
                  class="cal__line-text"
                  :style="{ color: CALENDAR_KIND_COLOR[line.kind] }"
                >
                  {{ line.text }}
                </span>
              </p>
              <p v-if="c.extra > 0" class="cal__more">+{{ c.extra }}</p>
            </div>
          </template>
        </button>
      </div>
    </div>

    <OdsEmptyState
      v-if="showEmpty && !loading && !hasAnyWork"
      class="cal-empty"
      title="이 달의 작업 기록이 없습니다"
      description="날짜를 눌러 영농일지를 등록해 보세요."
    />

    <div class="cal__legend" aria-label="범례">
      <span v-for="opt in WORK_FILTER_OPTIONS" :key="opt.key" class="cal__leg">
        <img class="cal__leg-ico" :src="CALENDAR_KIND_ICON[opt.key]" alt="" />
        <span class="cal__leg-text" :style="{ color: CALENDAR_KIND_COLOR[opt.key] }">
          {{ opt.label }}
        </span>
      </span>
    </div>
  </section>
</template>

<style scoped>
.cal-card {
  padding: var(--ods-space-16);
  border-radius: var(--ods-radius-card-lg);
  background: var(--ods-color-white);
  box-shadow: var(--ods-shadow-card);
}
.cal-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ods-space-8);
  margin-bottom: var(--ods-space-12);
  flex-wrap: wrap;
}
.cal-card__title-wrap {
  display: flex;
  align-items: center;
  gap: var(--ods-space-4);
  min-width: 0;
}
.cal-card__cal-ico {
  width: 18px;
  height: 18px;
  color: var(--ods-color-primary);
}
.cal-card__title {
  margin: 0;
  font: var(--ods-font-headline);
  font-weight: 800;
  color: var(--ods-color-text);
  white-space: nowrap;
}
.cal-card__title-btn {
  width: 28px;
  height: 28px;
  border: none;
  background: transparent;
  color: var(--ods-color-text-secondary);
  font-size: 18px;
  line-height: 1;
  cursor: pointer;
  border-radius: var(--ods-radius-button);
}
.cal-card__title-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}
.cal-card__actions {
  display: flex;
  align-items: center;
  gap: var(--ods-space-8);
  flex-shrink: 0;
}
.cal-card__chip {
  min-height: 36px !important;
  padding: 0 var(--ods-space-12) !important;
  border-radius: var(--ods-radius-badge) !important;
  font: var(--ods-font-caption) !important;
  font-weight: 700 !important;
}
.cal-slide--left {
  animation: wl-slide-left var(--ods-motion-base) var(--ods-motion-ease) both;
}
.cal-slide--right {
  animation: wl-slide-right var(--ods-motion-base) var(--ods-motion-ease) both;
}
@keyframes wl-slide-left {
  from {
    opacity: 0.4;
    transform: translateX(12px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}
@keyframes wl-slide-right {
  from {
    opacity: 0.4;
    transform: translateX(-12px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}
.cal__head,
.cal__grid {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: var(--ods-space-4);
}
.cal__wd {
  text-align: center;
  font: var(--ods-font-caption);
  font-weight: 700;
  color: var(--ods-color-text-secondary);
  padding: var(--ods-space-4) 0 var(--ods-space-8);
}
.cal__wd--sun {
  color: var(--ods-color-danger);
}
.cal__cell {
  min-height: 80px;
  height: 80px;
  margin: 0;
  padding: var(--ods-space-4);
  border: 1px solid var(--ods-color-border);
  border-radius: var(--ods-radius-button);
  background: var(--ods-color-white);
  text-align: left;
  cursor: pointer;
  color: var(--ods-color-text);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  transition:
    background var(--ods-motion-fast) var(--ods-motion-ease),
    border-color var(--ods-motion-fast) var(--ods-motion-ease),
    box-shadow var(--ods-motion-fast) var(--ods-motion-ease);
}
.cal__cell:hover:not(.cal__cell--out):not(:disabled) {
  box-shadow: var(--ods-shadow-card);
  border-color: color-mix(in srgb, var(--ods-color-primary) 35%, var(--ods-color-border));
}
.cal__cell--out {
  background: transparent;
  border-color: transparent;
  opacity: 0.38;
}
.cal__cell--future {
  opacity: 0.45;
}
.cal__cell--today {
  border: 1.5px solid var(--ods-color-primary);
  background: var(--ods-color-primary-soft);
}
.cal__cell--work {
  background: color-mix(in srgb, var(--ods-color-primary) 4%, white);
}
.cal__day {
  font-size: 11px;
  font-weight: 700;
  line-height: 1.1;
  margin: 0 0 var(--ods-space-4);
}
.cal__day--sun {
  color: var(--ods-color-danger);
}
.cal__events {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-height: 0;
  flex: 1;
}
.cal__line {
  margin: 0;
  display: flex;
  align-items: center;
  gap: 3px;
  min-width: 0;
  font-size: 9px;
  line-height: 1.3;
}
.cal__line-ico {
  width: 9px;
  height: 9px;
  flex-shrink: 0;
}
.cal__line-text {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 600;
}
.cal__more {
  margin: 0;
  font-size: 9px;
  font-weight: 700;
  color: var(--ods-color-primary);
}
.cal-empty {
  margin-top: var(--ods-space-12);
  box-shadow: none;
  border: 1px dashed var(--ods-color-border);
}
.cal__legend {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--ods-space-8) var(--ods-space-12);
  margin-top: var(--ods-space-16);
  padding-top: var(--ods-space-12);
  border-top: 1px solid var(--ods-color-border);
  align-items: center;
}
.cal__leg {
  display: inline-flex;
  align-items: center;
  gap: var(--ods-space-4);
  min-height: 18px;
}
.cal__leg-ico {
  width: 12px;
  height: 12px;
  flex-shrink: 0;
}
.cal__leg-text {
  font: var(--ods-font-caption);
  font-weight: 600;
  line-height: 1;
}

@media (min-width: 390px) {
  .cal__cell {
    min-height: 84px;
    height: 84px;
  }
  .cal__legend {
    grid-template-columns: repeat(7, minmax(0, 1fr));
  }
}
@media (prefers-reduced-motion: reduce) {
  .cal-slide--left,
  .cal-slide--right {
    animation: none;
  }
}
</style>
