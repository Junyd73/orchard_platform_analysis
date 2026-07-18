<script setup lang="ts">
import iconExpense from '@/assets/ods/work-log/icon-expense.svg'
import iconLabor from '@/assets/ods/work-log/icon-labor.svg'
import iconWork from '@/assets/ods/work-log/icon-work.svg'
import OdsCard from '@/components/ods/OdsCard.vue'
import { formatWon, monthLabel } from '@/views/work-log/workLogConstants'
import type { WorkLogMonthSummary } from '@/types/workLog'

const props = defineProps<{
  year: number
  month: number
  summary: WorkLogMonthSummary | null
  loading?: boolean
}>()

const emit = defineEmits<{
  detail: []
}>()

const title = () => `${monthLabel(props.year, props.month)} 요약`

/** 농약·비료·수확: 이번 단계 플레이스홀더 (임의 수치 금지) */
const PLACEHOLDER = '—'
</script>

<template>
  <section class="summary" aria-label="월간 요약">
    <div class="summary__head">
      <h2 class="summary__title">{{ title() }}</h2>
      <button type="button" class="summary__link" @click="emit('detail')">
        자세히 보기 &gt;
      </button>
    </div>
    <p v-if="loading" class="summary__hint">요약 불러오는 중…</p>
    <div class="summary__grid">
      <OdsCard>
        <div class="kpi">
          <img class="kpi__ico" :src="iconWork" alt="" />
          <p class="label">작업</p>
          <p class="value">{{ summary?.work_count ?? '—' }}</p>
        </div>
      </OdsCard>
      <OdsCard>
        <div class="kpi">
          <img class="kpi__ico" :src="iconLabor" alt="" />
          <p class="label">투입인력</p>
          <p class="value">{{ summary?.resource_count ?? '—' }}</p>
        </div>
      </OdsCard>
      <OdsCard>
        <div class="kpi">
          <img class="kpi__ico" :src="iconExpense" alt="" />
          <p class="label">경비</p>
          <p class="value value--sm">
            {{ summary ? formatWon(summary.expense_sum) : '—' }}
          </p>
        </div>
      </OdsCard>
      <OdsCard>
        <div class="kpi">
          <p class="label">농약</p>
          <p class="value">{{ PLACEHOLDER }}</p>
        </div>
      </OdsCard>
      <OdsCard>
        <div class="kpi">
          <p class="label">비료</p>
          <p class="value">{{ PLACEHOLDER }}</p>
        </div>
      </OdsCard>
      <OdsCard>
        <div class="kpi">
          <p class="label">수확진행률</p>
          <p class="value">{{ PLACEHOLDER }}</p>
        </div>
      </OdsCard>
    </div>
  </section>
</template>

<style scoped>
.summary__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ods-space-8);
  margin-bottom: var(--ods-space-8);
}
.summary__title {
  margin: 0;
  font: var(--ods-font-headline);
  color: var(--ods-color-text);
}
.summary__link {
  border: none;
  background: transparent;
  min-height: var(--ods-touch-min);
  font: var(--ods-font-body-2);
  font-weight: 700;
  color: var(--ods-color-primary);
  cursor: pointer;
}
.summary__hint {
  margin: 0 0 var(--ods-space-8);
  font: var(--ods-font-caption);
  color: var(--ods-color-gray-500);
}
.summary__grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--ods-space-12);
}
.kpi {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--ods-space-4);
}
.kpi__ico {
  width: 22px;
  height: 22px;
}
.label {
  margin: 0;
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
  text-align: center;
}
.value {
  margin: 0;
  font: var(--ods-font-title-2);
  color: var(--ods-color-text);
  text-align: center;
}
.value--sm {
  font: var(--ods-font-headline);
  font-weight: 700;
}
</style>
