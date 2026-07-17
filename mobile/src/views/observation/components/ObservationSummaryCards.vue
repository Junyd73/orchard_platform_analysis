<script setup lang="ts">
import OdsCard from '@/components/ods/OdsCard.vue'
import type { ObservationSummary } from '@/types/observation'

defineProps<{
  summary: ObservationSummary | null
  loading?: boolean
}>()
</script>

<template>
  <section class="summary" aria-label="오늘 요약">
    <p v-if="loading" class="summary__hint">요약 불러오는 중…</p>
    <div class="summary__grid">
      <OdsCard>
        <p class="label">오늘 관찰</p>
        <p class="value">{{ summary?.today_count ?? '—' }}</p>
      </OdsCard>
      <OdsCard>
        <p class="label">위험</p>
        <p class="value value--danger">{{ summary?.danger_count ?? '—' }}</p>
      </OdsCard>
      <OdsCard>
        <p class="label">과실 관찰</p>
        <p class="value">{{ summary?.fruit_count ?? '—' }}</p>
      </OdsCard>
      <OdsCard>
        <p class="label">AI 대기</p>
        <p class="value value--ai">{{ summary?.ai_pending_count ?? '—' }}</p>
      </OdsCard>
    </div>
  </section>
</template>

<style scoped>
.summary__hint {
  margin: 0 0 var(--ods-space-8);
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
.value--danger {
  color: var(--ods-color-danger);
}
.value--ai {
  color: var(--ods-color-ai);
}
</style>
