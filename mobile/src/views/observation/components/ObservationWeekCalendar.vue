<script setup lang="ts">
import { computed } from 'vue'

import {
  LABEL_OBS_CALENDAR,
  LABEL_OBS_DETAIL_LOOKUP,
  OBS_CAL_LEGEND,
  buildRangeIsos,
  emptyObsCalDay,
  monthLabelKo,
  type ObsCalDayCounts,
} from '@/views/observation/observationCalendar'
import {
  WEEKDAY_LABELS,
  isFutureDate,
  todayIso,
} from '@/views/work-log/workLogConstants'

const props = withDefaults(
  defineProps<{
    /** 7일 구간의 시작일 (기본: 오늘-6, 오늘 포함 과거 7일) */
    rangeStart: string
    selectedDt: string
    days?: Record<string, ObsCalDayCounts>
    loading?: boolean
    /** 관찰상세조회 — 조건(필터) 카드 펼침 */
    detailOpen?: boolean
  }>(),
  {
    days: () => ({}),
    loading: false,
    detailOpen: false,
  },
)

const emit = defineEmits<{
  select: [iso: string]
  'prev-range': []
  'next-range': []
  'toggle-detail': []
}>()

const today = todayIso()

const cells = computed(() => {
  return buildRangeIsos(props.rangeStart, 7).map((iso) => {
    const d = new Date(`${iso}T12:00:00`)
    const wdIdx = d.getDay()
    const counts = props.days[iso] ?? emptyObsCalDay()
    return {
      iso,
      day: d.getDate(),
      wd: WEEKDAY_LABELS[wdIdx],
      isRest: wdIdx === 0 || wdIdx === 6,
      isToday: iso === today,
      isSelected: iso === props.selectedDt,
      future: isFutureDate(iso, today),
      counts,
    }
  })
})

const monthLabel = computed(() => monthLabelKo(props.rangeStart))

function onSelect(iso: string) {
  emit('select', iso)
}
</script>

<template>
  <section class="obs-cal" :aria-label="LABEL_OBS_CALENDAR">
    <header class="obs-cal__head">
      <h2 class="obs-cal__title">{{ LABEL_OBS_CALENDAR }}</h2>
      <div class="obs-cal__nav" role="group" :aria-label="monthLabel">
        <button
          type="button"
          class="obs-cal__nav-btn"
          aria-label="이전 7일"
          @click="emit('prev-range')"
        >
          ‹
        </button>
        <span class="obs-cal__month">{{ monthLabel }}</span>
        <button
          type="button"
          class="obs-cal__nav-btn"
          aria-label="다음 7일"
          @click="emit('next-range')"
        >
          ›
        </button>
      </div>
    </header>

    <div
      class="obs-cal__week"
      role="list"
      :aria-busy="loading"
    >
      <button
        v-for="c in cells"
        :key="c.iso"
        type="button"
        role="listitem"
        class="obs-cal__cell"
        :class="{
          'obs-cal__cell--today': c.isToday && !c.isSelected,
          'obs-cal__cell--selected': c.isSelected,
          'obs-cal__cell--future': c.future,
        }"
        :aria-label="`${c.iso} ${c.wd}`"
        :aria-pressed="c.isSelected"
        @click="onSelect(c.iso)"
      >
        <span
          class="obs-cal__wd"
          :class="{ 'obs-cal__wd--rest': c.isRest }"
        >
          {{ c.wd }}
        </span>
        <span class="obs-cal__day">{{ c.day }}</span>
        <span class="obs-cal__dots" aria-hidden="true">
          <span
            v-for="leg in OBS_CAL_LEGEND"
            :key="leg.key"
            class="obs-cal__dot-row"
          >
            <i
              class="obs-cal__dot"
              :style="{ background: leg.colorVar }"
            />
            <span class="obs-cal__n">{{ c.counts[leg.key] }}</span>
          </span>
        </span>
      </button>
    </div>

    <div class="obs-cal__foot">
      <ul class="obs-cal__legend" :aria-label="`${LABEL_OBS_CALENDAR} 범례`">
        <li
          v-for="leg in OBS_CAL_LEGEND"
          :key="leg.key"
          class="obs-cal__leg"
        >
          <i
            class="obs-cal__dot obs-cal__dot--leg"
            :style="{ background: leg.colorVar }"
            aria-hidden="true"
          />
          <span>{{ leg.label }}</span>
        </li>
      </ul>
      <button
        type="button"
        class="obs-cal__detail-btn"
        :aria-expanded="detailOpen"
        :aria-controls="detailOpen ? 'obs-lookup-panel' : undefined"
        @click="emit('toggle-detail')"
      >
        {{ LABEL_OBS_DETAIL_LOOKUP }}
        <span class="obs-cal__detail-chev" aria-hidden="true">
          {{ detailOpen ? '▴' : '▾' }}
        </span>
      </button>
    </div>
  </section>
</template>

<style scoped>
.obs-cal {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-12);
  margin: 0;
  padding: var(--ods-space-16);
  border-radius: var(--ods-radius-card);
  background: var(--ods-color-white);
  border: 1px solid var(--ods-color-gray-100);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}
.obs-cal__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ods-space-8);
}
.obs-cal__title {
  margin: 0;
  font: var(--ods-font-headline);
  font-size: 15px;
  font-weight: 800;
  color: var(--ods-color-text);
  letter-spacing: -0.02em;
}
.obs-cal__nav {
  display: inline-flex;
  align-items: center;
  gap: 2px;
}
.obs-cal__nav-btn {
  width: 32px;
  height: 32px;
  margin: 0;
  padding: 0;
  border: none;
  border-radius: 8px;
  background: transparent;
  font-size: 20px;
  font-weight: 600;
  line-height: 1;
  color: var(--ods-color-text-secondary);
  cursor: pointer;
}
.obs-cal__nav-btn:active {
  background: var(--ods-color-gray-100);
}
.obs-cal__month {
  min-width: 6.5em;
  text-align: center;
  font: var(--ods-font-body-1);
  font-weight: 700;
  color: var(--ods-color-text);
}
.obs-cal__week {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: 4px;
}
.obs-cal__cell {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  margin: 0;
  padding: 8px 2px 6px;
  border: 1.5px solid transparent;
  border-radius: 12px;
  background: transparent;
  cursor: pointer;
  min-width: 0;
}
.obs-cal__cell--today {
  background: color-mix(in srgb, var(--ods-color-primary) 6%, transparent);
}
.obs-cal__cell--selected {
  border-color: var(--ods-color-primary);
  background: color-mix(in srgb, var(--ods-color-primary) 8%, white);
}
.obs-cal__cell--future {
  opacity: 0.55;
}
.obs-cal__wd {
  display: block;
  width: 100%;
  text-align: center;
  font-size: 11px;
  font-weight: 600;
  line-height: 1.2;
  color: var(--ods-color-text-secondary);
}
.obs-cal__wd--rest {
  color: var(--ods-color-danger);
}
.obs-cal__day {
  display: block;
  width: 100%;
  text-align: center;
  font-size: 15px;
  font-weight: 800;
  line-height: 1.2;
  letter-spacing: -0.02em;
  color: var(--ods-color-text);
}
.obs-cal__dots {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  width: 100%;
  box-sizing: border-box;
}
.obs-cal__dot-row {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 3px;
  min-width: 0;
}
.obs-cal__dot {
  width: 5px;
  height: 5px;
  border-radius: 999px;
  flex: 0 0 auto;
  display: block;
}
.obs-cal__dot--leg {
  width: 6px;
  height: 6px;
}
.obs-cal__n {
  font-size: 10px;
  font-weight: 700;
  line-height: 1;
  color: var(--ods-color-text-secondary);
  font-variant-numeric: tabular-nums;
}
.obs-cal__foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ods-space-8);
  min-width: 0;
}
.obs-cal__legend {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px 10px;
  margin: 0;
  padding: 0;
  list-style: none;
  min-width: 0;
  flex: 1 1 auto;
}
.obs-cal__leg {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font: var(--ods-font-caption);
  font-weight: 600;
  color: var(--ods-color-text-secondary);
}
.obs-cal__detail-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin: 0;
  padding: 4px 0;
  border: none;
  background: transparent;
  font: var(--ods-font-caption);
  font-size: 12px;
  font-weight: 700;
  color: var(--ods-color-primary);
  cursor: pointer;
  flex: 0 0 auto;
  white-space: nowrap;
}
.obs-cal__detail-btn:active {
  opacity: 0.7;
}
.obs-cal__detail-chev {
  font-size: 10px;
  line-height: 1;
}
</style>
