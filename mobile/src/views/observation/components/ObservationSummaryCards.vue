<script setup lang="ts">
import iconAi from '@/assets/ods/scr004/icon-ai.svg'
import iconCalendar from '@/assets/ods/scr004/icon-calendar.svg'
import iconLeaf from '@/assets/ods/scr004/icon-leaf.svg'
import iconMeta from '@/assets/ods/scr004/icon-meta.svg'
import type { ObservationSummary } from '@/types/observation'

const props = defineProps<{
  summary: ObservationSummary | null
  loading?: boolean
}>()

const emit = defineEmits<{
  select: [key: 'today' | 'danger' | 'ai' | 'fruit']
}>()

type KpiKey = 'today' | 'danger' | 'ai' | 'fruit'

const cards: {
  key: KpiKey
  label: string
  icon: string
  tone?: 'danger' | 'ai'
  count: () => string
}[] = [
  {
    key: 'today',
    label: '오늘 관찰',
    icon: iconCalendar,
    count: () => formatCount(props.summary?.today_count),
  },
  {
    key: 'danger',
    label: '위험 관찰',
    icon: iconMeta,
    tone: 'danger',
    count: () => formatCount(props.summary?.danger_count),
  },
  {
    key: 'ai',
    label: 'AI 대기',
    icon: iconAi,
    tone: 'ai',
    count: () => formatCount(props.summary?.ai_pending_count),
  },
  {
    key: 'fruit',
    label: '과실 관찰',
    icon: iconLeaf,
    count: () => formatCount(props.summary?.fruit_count),
  },
]

function formatCount(n: number | null | undefined): string {
  if (props.loading) return '…'
  if (n == null) return '—'
  return `${n}건`
}
</script>

<template>
  <section class="kpi" aria-label="오늘 요약">
    <p v-if="loading" class="kpi__hint">요약 불러오는 중…</p>
    <p v-else-if="!summary" class="kpi__hint">
      요약 정보를 아직 불러오지 못했습니다.
    </p>
    <div class="kpi__row">
      <button
        v-for="c in cards"
        :key="c.key"
        type="button"
        class="kpi__card"
        @click="emit('select', c.key)"
      >
        <img class="kpi__ico" :src="c.icon" alt="" />
        <span class="kpi__label">{{ c.label }}</span>
        <span
          class="kpi__value"
          :class="{
            'kpi__value--danger': c.tone === 'danger',
            'kpi__value--ai': c.tone === 'ai',
          }"
        >
          {{ c.count() }}
        </span>
      </button>
    </div>
  </section>
</template>

<style scoped>
.kpi {
  margin-top: calc(-1 * var(--ods-space-24));
  position: relative;
  z-index: 2;
}
.kpi__hint {
  margin: 0 0 var(--ods-space-8);
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
  text-align: center;
}
.kpi__row {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--ods-space-8);
}
.kpi__card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  margin: 0;
  padding: var(--ods-space-8) 4px;
  border: 1px solid var(--ods-color-border);
  border-radius: var(--ods-radius-card);
  background: var(--ods-color-white);
  box-shadow: var(--ods-shadow-card);
  cursor: pointer;
  min-width: 0;
}
.kpi__ico {
  width: 18px;
  height: 18px;
}
.kpi__label {
  font: var(--ods-font-caption);
  font-size: 10px;
  font-weight: 600;
  color: var(--ods-color-text-secondary);
  white-space: nowrap;
}
.kpi__value {
  font: var(--ods-font-body-2);
  font-weight: 800;
  color: var(--ods-color-text);
  line-height: 1.2;
}
.kpi__value--danger {
  color: var(--ods-color-danger);
}
.kpi__value--ai {
  color: var(--ods-color-ai);
}
</style>
