<script setup lang="ts">
import { computed } from 'vue'

import iconCalendar from '@/assets/ods/work-log/icon-calendar.svg'
import {
  formatDailyDateLabel,
  todayIso,
} from '@/views/work-log/workLogConstants'

const props = defineProps<{
  workDt: string
}>()

const emit = defineEmits<{
  'go-today': []
}>()

const label = computed(() => formatDailyDateLabel(props.workDt))
const isToday = computed(() => props.workDt === todayIso())
</script>

<template>
  <section class="date-bar" aria-label="작업 일자">
    <div class="date-bar__title-wrap">
      <img class="date-bar__cal-ico" :src="iconCalendar" alt="" />
      <h2 class="date-bar__title">{{ label }}</h2>
    </div>
    <button
      v-if="!isToday"
      type="button"
      class="date-bar__chip"
      @click="emit('go-today')"
    >
      오늘
    </button>
  </section>
</template>

<style scoped>
/* 월간 WorkLogMonthCalendar `.cal-card__head` 와 동일 패턴 */
.date-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ods-space-8);
}
.date-bar__title-wrap {
  display: flex;
  align-items: center;
  gap: var(--ods-space-8);
  min-width: 0;
}
.date-bar__cal-ico {
  width: var(--ods-icon-lg);
  height: var(--ods-icon-lg);
  color: var(--ods-color-primary);
}
.date-bar__title {
  margin: 0;
  font: var(--ods-font-headline);
  font-weight: 800;
  color: var(--ods-color-text);
  white-space: nowrap;
}
.date-bar__chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: var(--ods-hit-sm);
  padding: 0 var(--ods-space-12);
  border: 1px solid var(--ods-color-border);
  border-radius: var(--ods-radius-badge);
  font: var(--ods-font-card-help);
  font-weight: 600;
  line-height: 1;
  color: var(--ods-color-text);
  cursor: pointer;
  white-space: nowrap;
  background: var(--ods-color-white);
}
</style>
