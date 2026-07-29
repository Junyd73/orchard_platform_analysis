<script setup lang="ts">
import iconFruit from '@/assets/ods/common/icon-kpi-fruit.svg'
import iconPest from '@/assets/ods/common/icon-kpi-pest.svg'
import iconRobot from '@/assets/ods/common/icon-kpi-robot.svg'
import iconWarn from '@/assets/ods/common/icon-kpi-warn.svg'
import type { ObservationHeroKpiKey } from '@/views/observation/components/ObservationHero.vue'
import type { ObservationSummary } from '@/types/observation'

const props = defineProps<{
  summary: ObservationSummary | null
  loading?: boolean
}>()

const emit = defineEmits<{
  select: [key: ObservationHeroKpiKey]
}>()

const cards: {
  key: ObservationHeroKpiKey
  label: string
  icon: string
  tone?: 'danger' | 'ai'
  count: () => string
}[] = [
  {
    key: 'pest',
    label: '병해충 관찰',
    icon: iconPest,
    count: () => formatCount(props.summary?.pest_count),
  },
  {
    key: 'fruit',
    label: '과실 관찰',
    icon: iconFruit,
    count: () => formatCount(props.summary?.fruit_count),
  },
  {
    key: 'ai',
    label: 'AI 분석',
    icon: iconRobot,
    tone: 'ai',
    count: () => formatCount(props.summary?.ai_pending_count),
  },
  {
    key: 'danger',
    label: '위험 분석',
    icon: iconWarn,
    tone: 'danger',
    count: () => formatCount(props.summary?.danger_count),
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
  font: var(--ods-font-card-help);
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
  gap: var(--ods-space-4);
  margin: 0;
  padding: var(--ods-space-8) var(--ods-space-4);
  border: 1px solid var(--ods-color-border);
  border-radius: var(--ods-radius-card);
  background: var(--ods-color-white);
  box-shadow: var(--ods-shadow-card);
  cursor: pointer;
  min-width: 0;
}
.kpi__ico {
  width: var(--ods-icon-lg);
  height: var(--ods-icon-lg);
}
.kpi__label {
  font: var(--ods-font-card-meta);
  font-weight: 600;
  color: var(--ods-color-text-secondary);
  white-space: nowrap;
}
.kpi__value {
  font: var(--ods-font-card-body);
  color: var(--ods-color-text);
}
.kpi__value--danger {
  color: var(--ods-color-danger);
}
.kpi__value--ai {
  color: var(--ods-color-ai);
}
</style>
