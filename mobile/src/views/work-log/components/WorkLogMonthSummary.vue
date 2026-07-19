<script setup lang="ts">
import iconExpense from '@/assets/ods/work-log/icon-expense.svg'
import iconFertilizer from '@/assets/ods/work-log/icon-fertilizer.svg'
import iconLabor from '@/assets/ods/work-log/icon-labor.svg'
import iconPesticide from '@/assets/ods/work-log/icon-pesticide.svg'
import iconWork from '@/assets/ods/work-log/icon-work.svg'
import {
  formatLaborSummary,
  formatWonWithUnit,
  monthRangeLabel,
} from '@/views/work-log/workLogConstants'
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

const PLACEHOLDER = '—'
const SUB_CUMULATIVE = '누적'
const SUB_VS_PLAN = '계획 대비'
const title = () => `${props.month}월 월간 요약`
const range = () => monthRangeLabel(props.year, props.month)
</script>

<template>
  <section class="sum anim-fade" aria-label="월간 요약">
    <div class="sum__head">
      <div class="sum__titles">
        <h2 class="sum__title">{{ title() }}</h2>
        <span class="sum__range">{{ range() }}</span>
      </div>
      <button type="button" class="sum__link" @click="emit('detail')">
        자세히 보기 &gt;
      </button>
    </div>

    <p v-if="loading" class="sum__hint">요약 불러오는 중…</p>

    <div class="sum__grid">
      <article class="sum__card">
        <img class="sum__ico" :src="iconWork" alt="" />
        <p class="sum__label">작업</p>
        <p class="sum__value">
          {{ summary ? `${summary.work_count}건` : PLACEHOLDER }}
        </p>
        <p class="sum__sub">{{ SUB_CUMULATIVE }}</p>
      </article>
      <article class="sum__card">
        <img class="sum__ico" :src="iconLabor" alt="" />
        <p class="sum__label">투입 인력</p>
        <p class="sum__value sum__value--sm">
          {{
            summary
              ? formatLaborSummary(
                  summary.resource_count,
                  summary.labor_hour_sum,
                )
              : PLACEHOLDER
          }}
        </p>
        <p class="sum__sub">{{ SUB_CUMULATIVE }}</p>
      </article>
      <article class="sum__card">
        <img class="sum__ico" :src="iconExpense" alt="" />
        <p class="sum__label">경비 지출</p>
        <p class="sum__value sum__value--sm">
          {{
            summary
              ? formatWonWithUnit(summary.expense_sum + summary.labor_sum)
              : PLACEHOLDER
          }}
        </p>
        <p class="sum__sub">{{ SUB_CUMULATIVE }}</p>
      </article>
      <article class="sum__card">
        <img class="sum__ico" :src="iconPesticide" alt="" />
        <p class="sum__label">농약 사용</p>
        <p class="sum__value">
          {{ summary ? `${summary.pesticide_count ?? 0}건` : PLACEHOLDER }}
        </p>
        <p class="sum__sub">{{ SUB_CUMULATIVE }}</p>
      </article>
      <article class="sum__card">
        <img class="sum__ico" :src="iconFertilizer" alt="" />
        <p class="sum__label">비료 사용</p>
        <p class="sum__value">
          {{ summary ? `${summary.fertilizer_count ?? 0}건` : PLACEHOLDER }}
        </p>
        <p class="sum__sub">{{ SUB_CUMULATIVE }}</p>
      </article>
      <article class="sum__card">
        <img class="sum__ico" :src="iconWork" alt="" />
        <p class="sum__label">수확 진행</p>
        <p class="sum__value">{{ PLACEHOLDER }}</p>
        <p class="sum__sub">{{ SUB_VS_PLAN }}</p>
      </article>
    </div>
  </section>
</template>

<style scoped>
.sum__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--ods-space-8);
  margin-bottom: var(--ods-space-12);
}
.sum__titles {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: var(--ods-space-8);
  min-width: 0;
}
.sum__title {
  margin: 0;
  font: var(--ods-font-headline);
  font-weight: 800;
  color: var(--ods-color-text);
}
.sum__range {
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
}
.sum__link {
  flex-shrink: 0;
  border: none;
  background: transparent;
  padding: 0;
  min-height: var(--ods-touch-min);
  font: var(--ods-font-body-2);
  font-weight: 700;
  color: var(--ods-color-primary);
  cursor: pointer;
}
.sum__hint {
  margin: 0 0 var(--ods-space-8);
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
}
.sum__grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--ods-space-8);
}
.sum__card {
  min-height: 96px;
  padding: var(--ods-space-12) var(--ods-space-8) var(--ods-space-12);
  border-radius: var(--ods-radius-card);
  background: var(--ods-color-white);
  box-shadow: var(--ods-shadow-card);
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  box-sizing: border-box;
  transition: box-shadow var(--ods-motion-fast) var(--ods-motion-ease);
}
.sum__card:hover {
  box-shadow: var(--ods-shadow-elevated);
}
.sum__ico {
  width: 22px;
  height: 22px;
  margin: 0 auto var(--ods-space-4);
  display: block;
}
.sum__label {
  margin: 0;
  font-size: 10px;
  line-height: 1.25;
  color: var(--ods-color-text-secondary);
}
.sum__value {
  margin: var(--ods-space-4) 0 0;
  font-size: 17px;
  font-weight: 800;
  color: var(--ods-color-text);
  line-height: 1.2;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sum__value--sm {
  font-size: 12px;
  letter-spacing: -0.03em;
}
.sum__sub {
  margin: var(--ods-space-4) 0 0;
  font-size: 10px;
  line-height: 1.2;
  color: var(--ods-color-text-secondary);
}
.anim-fade {
  animation: wl-fade var(--ods-motion-base) var(--ods-motion-ease) both;
}
@keyframes wl-fade {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}
@media (prefers-reduced-motion: reduce) {
  .anim-fade {
    animation: none;
  }
}
</style>
