<script setup lang="ts">
import OdsCard from '@/components/ods/OdsCard.vue'
import { formatWon } from '@/views/work-log/workLogConstants'
import type { WorkLogMonthSummary } from '@/types/workLog'

defineProps<{
  summary: WorkLogMonthSummary | null
  loading?: boolean
}>()
</script>

<template>
  <section class="summary" aria-label="월간 요약">
    <p v-if="loading" class="summary__hint">요약 불러오는 중…</p>
    <div class="summary__grid">
      <OdsCard>
        <p class="label">작업일</p>
        <p class="value">{{ summary?.work_day_count ?? '—' }}</p>
      </OdsCard>
      <OdsCard>
        <p class="label">작업 건수</p>
        <p class="value">{{ summary?.work_count ?? '—' }}</p>
      </OdsCard>
      <OdsCard>
        <p class="label">인력 건수</p>
        <p class="value">{{ summary?.resource_count ?? '—' }}</p>
      </OdsCard>
      <OdsCard>
        <p class="label">인건비</p>
        <p class="value">{{ summary ? formatWon(summary.labor_sum) : '—' }}</p>
      </OdsCard>
    </div>
    <OdsCard>
      <p class="label">경비·자재</p>
      <p class="value">{{ summary ? formatWon(summary.expense_sum) : '—' }}</p>
    </OdsCard>
  </section>
</template>

<style scoped>
.summary {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-12);
}
.summary__hint {
  margin: 0;
  font: var(--ods-font-caption);
  color: var(--ods-color-gray-500);
}
.summary__grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--ods-space-12);
}
.label {
  margin: 0;
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
}
.value {
  margin: var(--ods-space-8) 0 0;
  font: var(--ods-font-title-2);
  color: var(--ods-color-text);
}
</style>
