<script setup lang="ts">
import iconChevronRight from '@/assets/ods/scr004/icon-chevron-right.svg'
import {
  LABEL_STANDALONE_USE,
  workIdToRouteDate,
} from '@/views/pesticide/pesticideConstants'
import type { PesticideUsageRow } from '@/types/pesticide'

defineProps<{
  row: PesticideUsageRow
}>()

const emit = defineEmits<{
  openWork: [workDt: string]
}>()

function onWorkClick(workId: string | null) {
  const dt = workId ? workIdToRouteDate(workId) : ''
  if (dt) emit('openWork', dt)
}
</script>

<template>
  <article class="usage">
    <div class="usage__head">
      <time class="usage__date">{{ row.use_dt }}</time>
      <span class="usage__qty">낱개 {{ row.use_qty }}</span>
    </div>
    <p class="usage__purpose">
      목적: {{ row.purpose_nm || '—' }}
      <template v-if="row.site_nm"> · {{ row.site_nm }}</template>
    </p>
    <button
      v-if="row.work_id && workIdToRouteDate(row.work_id)"
      type="button"
      class="usage__link"
      @click="onWorkClick(row.work_id)"
    >
      작업 {{ row.work_id }}
      <img :src="iconChevronRight" alt="" aria-hidden="true" />
    </button>
    <p v-else class="usage__solo">{{ LABEL_STANDALONE_USE }}</p>
  </article>
</template>

<style scoped>
.usage {
  padding: var(--ods-space-12) var(--ods-space-16);
  border-radius: var(--ods-radius-card);
  background: var(--ods-color-white);
  box-shadow: var(--ods-shadow-card);
}
.usage__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ods-space-8);
}
.usage__date {
  font: var(--ods-font-form-value);
  font-weight: 700;
  color: var(--ods-color-text);
}
.usage__qty {
  font: var(--ods-font-form-help);
  color: var(--ods-color-text-secondary);
}
.usage__purpose {
  margin: var(--ods-space-8) 0 0;
  font: var(--ods-font-form-help);
  color: var(--ods-color-text-secondary);
}
.usage__link {
  display: inline-flex;
  align-items: center;
  gap: var(--ods-space-4);
  margin-top: var(--ods-space-8);
  padding: 0;
  border: none;
  background: transparent;
  font: var(--ods-font-form-help);
  font-weight: 700;
  color: var(--ods-color-primary);
  cursor: pointer;
  min-height: var(--ods-touch-min);
}
.usage__link img {
  width: var(--ods-icon-md);
  height: var(--ods-icon-md);
}
.usage__solo {
  margin: var(--ods-space-8) 0 0;
  font: var(--ods-font-card-help);
  color: var(--ods-color-text-secondary);
}
</style>
