<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import iconCalendar from '@/assets/ods/work-log/icon-calendar.svg'
import OdsEmptyState from '@/components/ods/OdsEmptyState.vue'
import {
  buildCalendarLines,
  CALENDAR_KIND_COLOR,
  CALENDAR_KIND_ICON,
  daysInMonth,
  firstWeekdaySun0,
  isFutureDate,
  isRestDay,
  monthLabel,
  pad2,
  shiftMonth,
  todayIso,
  WEEKDAY_LABELS,
  WORK_FILTER_OPTIONS,
  type CalendarScheduleHint,
  type WorkFilterKey,
} from '@/views/work-log/workLogConstants'
import type { WorkLogDayCell } from '@/types/workLog'

const SWIPE_THRESHOLD_PX = 48

const props = defineProps<{
  year: number
  month: number
  days: Record<string, WorkLogDayCell>
  /** work_dt → 예정 일정 힌트 */
  schedulesByDt?: Record<string, CalendarScheduleHint[]>
  filters: Record<WorkFilterKey, boolean>
  selectedDt?: string | null
  loading?: boolean
  showEmpty?: boolean
}>()

const emit = defineEmits<{
  select: [workDt: string]
  blocked: [message: string]
  'toggle-filter': [key: WorkFilterKey]
  'go-today': []
  'prev-month': []
  'next-month': []
  'prev-year': []
  'next-year': []
}>()

const today = todayIso()
const title = computed(() => monthLabel(props.year, props.month))
const slideDir = ref<'left' | 'right' | 'up' | 'down' | 'none'>('none')
const monthKey = computed(() => `${props.year}-${props.month}`)
const selectedIso = computed(() => props.selectedDt || today)

watch(
  () => monthKey.value,
  (next, prev) => {
    if (!prev) {
      slideDir.value = 'none'
      return
    }
    const [ny, nm] = next.split('-').map(Number)
    const [py, pm] = prev.split('-').map(Number)
    if (ny !== py) {
      slideDir.value = ny > py ? 'up' : 'down'
      return
    }
    slideDir.value = nm > pm ? 'left' : 'right'
  },
)

type CalCell = {
  key: string
  day: number
  iso: string
  inMonth: boolean
  future: boolean
  isToday: boolean
  isSelected: boolean
  isRest: boolean
  cell: WorkLogDayCell | null
  hasSchedule: boolean
  lines: ReturnType<typeof buildCalendarLines>['lines']
  extra: number
}

const cells = computed((): CalCell[] => {
  const total = daysInMonth(props.year, props.month)
  const start = firstWeekdaySun0(props.year, props.month)
  const out: CalCell[] = []
  const selected = selectedIso.value

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
      isSelected: false,
      isRest: isRestDay(iso),
      cell: null,
      hasSchedule: false,
      lines: [],
      extra: 0,
    })
  }

  for (let d = 1; d <= total; d += 1) {
    const iso = `${props.year}-${pad2(props.month)}-${pad2(d)}`
    const cell = props.days[iso] || null
    const sched = props.schedulesByDt?.[iso] || []
    const built = buildCalendarLines(cell, props.filters, sched)
    out.push({
      key: iso,
      day: d,
      iso,
      inMonth: true,
      future: isFutureDate(iso, today),
      isToday: iso === today,
      isSelected: iso === selected,
      isRest: isRestDay(iso),
      cell,
      hasSchedule: sched.length > 0,
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
      isSelected: false,
      isRest: isRestDay(iso),
      cell: null,
      hasSchedule: false,
      lines: [],
      extra: 0,
    })
    n += 1
  }
  return out
})

const hasAnyWork = computed(() =>
  Object.values(props.days).some((d) => d.has_work || Number(d.work_count || 0) > 0) ||
  Object.values(props.schedulesByDt || {}).some((arr) => arr.length > 0),
)

const swipe = ref<{ x: number; y: number; active: boolean } | null>(null)
const didSwipe = ref(false)

function onPointerDown(e: PointerEvent) {
  if (e.pointerType === 'mouse' && e.button !== 0) return
  didSwipe.value = false
  swipe.value = { x: e.clientX, y: e.clientY, active: true }
  // 마우스는 capture 금지 — capture 시 셀 click이 부모로 잡혀 일간 진입이 안 됨
  if (e.pointerType === 'mouse') return
  const el = e.currentTarget as HTMLElement | null
  try {
    el?.setPointerCapture?.(e.pointerId)
  } catch {
    // capture 미지원 환경은 무시
  }
}

function onPointerUp(e: PointerEvent) {
  const s = swipe.value
  swipe.value = null
  const el = e.currentTarget as HTMLElement | null
  try {
    if (el?.hasPointerCapture?.(e.pointerId)) {
      el.releasePointerCapture(e.pointerId)
    }
  } catch {
    // ignore
  }
  if (!s?.active) return
  const dx = e.clientX - s.x
  const dy = e.clientY - s.y
  const absX = Math.abs(dx)
  const absY = Math.abs(dy)
  // 탭(미세 이동): 스와이프 아님 · 셀 click에 위임
  if (absX < SWIPE_THRESHOLD_PX && absY < SWIPE_THRESHOLD_PX) return
  didSwipe.value = true
  if (absX >= absY) {
    if (dx < 0) emit('next-month')
    else emit('prev-month')
    return
  }
  if (dy < 0) emit('next-year')
  else emit('prev-year')
}

function onPointerCancel(e: PointerEvent) {
  swipe.value = null
  const el = e.currentTarget as HTMLElement | null
  try {
    if (el?.hasPointerCapture?.(e.pointerId)) {
      el.releasePointerCapture(e.pointerId)
    }
  } catch {
    // ignore
  }
}

function onTap(c: CalCell) {
  if (didSwipe.value) {
    didSwipe.value = false
    return
  }
  if (!c.inMonth) {
    if (c.iso < `${props.year}-${pad2(props.month)}-01`) emit('prev-month')
    else emit('next-month')
    return
  }
  if (c.future) {
    // 미래일도 일정 확인·등록을 위해 일간 진입 허용 (실적 저장은 일간에서 차단)
    emit('select', c.iso)
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
        <h2 class="cal-card__title">{{ title }}</h2>
      </div>
      <button
        type="button"
        class="cal-card__chip cal-card__chip--today"
        @click="emit('go-today')"
      >
        오늘
      </button>
    </div>

    <div
      class="cal-gesture"
      @pointerdown="onPointerDown"
      @pointerup="onPointerUp"
      @pointercancel="onPointerCancel"
    >
      <div
        :key="monthKey"
        class="cal-slide"
        :class="{
          'cal-slide--left': slideDir === 'left',
          'cal-slide--right': slideDir === 'right',
          'cal-slide--up': slideDir === 'up',
          'cal-slide--down': slideDir === 'down',
        }"
      >
        <div class="cal__head">
          <span
            v-for="(w, i) in WEEKDAY_LABELS"
            :key="w"
            class="cal__wd"
            :class="{ 'cal__wd--rest': i === 0 || i === 6 }"
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
              'cal__cell--today': c.isToday && !c.isSelected,
              'cal__cell--selected': c.inMonth && c.isSelected,
              'cal__cell--work':
                c.inMonth &&
                (c.cell?.has_work || c.hasSchedule) &&
                !c.isSelected &&
                !c.isToday,
            }"
            @click="onTap(c)"
          >
            <span
              class="cal__day"
              :class="{
                'cal__day--rest': c.isRest && c.inMonth,
                'cal__day--today': c.isToday,
              }"
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
    </div>

    <OdsEmptyState
      v-if="showEmpty && !loading && !hasAnyWork"
      class="cal-empty"
      compact
      title="이 달의 작업·예정이 없습니다"
      description="날짜를 눌러 영농일지 또는 일정을 등록해 보세요."
    />

    <div class="cal__legend" aria-label="작업 필터">
      <button
        v-for="opt in WORK_FILTER_OPTIONS"
        :key="opt.key"
        type="button"
        class="cal__leg"
        :class="{ 'cal__leg--on': filters[opt.key] }"
        :aria-pressed="filters[opt.key]"
        @click="emit('toggle-filter', opt.key)"
      >
        <img class="cal__leg-ico" :src="CALENDAR_KIND_ICON[opt.key]" alt="" />
        <span
          class="cal__leg-text"
          :style="{ color: CALENDAR_KIND_COLOR[opt.key] }"
        >
          {{ opt.label }}
        </span>
      </button>
    </div>
  </section>
</template>

<style scoped>
.cal-card {
  padding: var(--ods-space-8) var(--ods-space-4);
  border-radius: var(--ods-radius-card-lg);
  background: var(--ods-color-white);
  box-shadow: var(--ods-shadow-card);
}
.cal-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ods-space-8);
  margin-bottom: var(--ods-space-4);
}
.cal-card__title-wrap {
  display: flex;
  align-items: center;
  gap: var(--ods-space-8);
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
.cal-card__chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 32px;
  padding: 0 var(--ods-space-12);
  border: 1px solid var(--ods-color-border);
  border-radius: var(--ods-radius-badge);
  font: var(--ods-font-caption);
  font-weight: 600;
  line-height: 1;
  color: var(--ods-color-text);
  cursor: pointer;
  white-space: nowrap;
  background: var(--ods-color-white);
}
.cal-gesture {
  touch-action: none;
  user-select: none;
}
.cal-slide--left {
  animation: wl-slide-left var(--ods-motion-base) var(--ods-motion-ease) both;
}
.cal-slide--right {
  animation: wl-slide-right var(--ods-motion-base) var(--ods-motion-ease) both;
}
.cal-slide--up {
  animation: wl-slide-up var(--ods-motion-base) var(--ods-motion-ease) both;
}
.cal-slide--down {
  animation: wl-slide-down var(--ods-motion-base) var(--ods-motion-ease) both;
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
@keyframes wl-slide-up {
  from {
    opacity: 0.4;
    transform: translateY(12px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
@keyframes wl-slide-down {
  from {
    opacity: 0.4;
    transform: translateY(-12px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
.cal__head,
.cal__grid {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: 0;
}
.cal__head {
  border-bottom: 1px solid var(--ods-color-border);
}
.cal__wd {
  text-align: center;
  font: var(--ods-font-caption);
  font-weight: 700;
  color: var(--ods-color-text-secondary);
  padding: var(--ods-space-4) 0;
}
.cal__wd--rest {
  color: var(--ods-color-danger);
}
.cal__grid {
  border-top: 1px solid var(--ods-color-border);
  border-left: 1px solid var(--ods-color-border);
}
.cal__cell {
  min-height: 66px;
  height: 66px;
  margin: 0;
  padding: 3px 4px;
  border: none;
  border-right: 1px solid var(--ods-color-border);
  border-bottom: 1px solid var(--ods-color-border);
  border-radius: 0;
  background: var(--ods-color-white);
  text-align: left;
  cursor: pointer;
  color: var(--ods-color-text);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  transition: background var(--ods-motion-fast) var(--ods-motion-ease);
}
.cal__cell:hover:not(.cal__cell--out):not(:disabled) {
  background: color-mix(in srgb, var(--ods-color-primary) 6%, white);
}
.cal__cell--out {
  background: color-mix(in srgb, var(--ods-color-gray-100) 70%, white);
  opacity: 0.55;
}
.cal__cell--future {
  opacity: 0.5;
}
.cal__cell--today {
  background: color-mix(in srgb, var(--ods-color-primary) 5%, white);
}
.cal__cell--selected {
  background: var(--ods-color-primary-soft);
  box-shadow: inset 0 0 0 1.5px var(--ods-color-primary);
}
.cal__cell--work:not(.cal__cell--selected):not(.cal__cell--today) {
  background: color-mix(in srgb, var(--ods-color-primary) 4%, white);
}
.cal__day {
  font-size: 10px;
  font-weight: 700;
  line-height: 1.1;
  margin: 0 0 2px;
}
.cal__day--rest {
  color: var(--ods-color-danger);
}
.cal__day--today {
  color: var(--ods-color-primary);
}
.cal__events {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-height: 0;
  flex: 1;
}
.cal__line {
  margin: 0;
  min-width: 0;
  font-size: 11px;
  line-height: 1.35;
}
.cal__line-text {
  display: block;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 600;
}
.cal__more {
  margin: 0;
  font-size: 10px;
  font-weight: 700;
  color: var(--ods-color-primary);
}
.cal-empty {
  margin-top: var(--ods-space-8);
}
.cal__legend {
  display: flex;
  flex-wrap: nowrap;
  align-items: stretch;
  justify-content: space-between;
  gap: var(--ods-space-4);
  margin-top: var(--ods-space-8);
  padding-top: var(--ods-space-8);
  border-top: 1px solid var(--ods-color-border);
  overflow-x: auto;
  overflow-y: hidden;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
}
.cal__legend::-webkit-scrollbar {
  display: none;
}
.cal__leg {
  display: inline-flex;
  flex: 0 0 auto;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  min-width: 40px;
  margin: 0;
  padding: 6px 8px;
  border: 1px solid var(--ods-color-border);
  border-radius: var(--ods-radius-badge);
  background: var(--ods-color-bg-muted);
  cursor: pointer;
  opacity: 0.45;
  transition:
    opacity var(--ods-motion-fast) var(--ods-motion-ease),
    background var(--ods-motion-fast) var(--ods-motion-ease),
    border-color var(--ods-motion-fast) var(--ods-motion-ease);
}
.cal__leg--on {
  opacity: 1;
  background: color-mix(in srgb, var(--ods-color-primary) 8%, white);
  border-color: color-mix(in srgb, var(--ods-color-primary) 28%, var(--ods-color-border));
}
.cal__leg-ico {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
}
.cal__leg-text {
  font: var(--ods-font-caption);
  font-size: 10px;
  font-weight: 700;
  line-height: 1.2;
  white-space: nowrap;
  text-align: center;
}
@media (prefers-reduced-motion: reduce) {
  .cal-slide--left,
  .cal-slide--right,
  .cal-slide--up,
  .cal-slide--down {
    animation: none;
  }
}
</style>
