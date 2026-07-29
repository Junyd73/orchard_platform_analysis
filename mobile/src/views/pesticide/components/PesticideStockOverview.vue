<script setup lang="ts">
import { computed } from 'vue'

import iconSec from '@/assets/ods/pesticide/icon-sec-chart.svg'
import OdsSectionTitle from '@/components/ods/OdsSectionTitle.vue'
import {
  MSG_VIEW_ALL,
  SECTION_STOCK_STATUS,
  type DemoCategoryShare,
} from '@/views/pesticide/pesticideConstants'

const props = defineProps<{
  totalPiece?: number
  shares?: readonly DemoCategoryShare[]
  loading?: boolean
}>()

const emit = defineEmits<{
  viewAll: []
}>()

const displayTotal = computed(() => Math.max(0, props.totalPiece ?? 0))

const legendRows = computed(() => props.shares ?? [])

const donutStyle = computed(() => {
  const rows = legendRows.value
  if (!rows.length) {
    return { background: 'var(--ods-color-border)' }
  }
  let acc = 0
  const stops: string[] = []
  for (const row of rows) {
    const start = acc
    acc += row.pct
    stops.push(`${row.tone} ${start}% ${acc}%`)
  }
  if (acc < 100) {
    stops.push(`var(--ods-color-border) ${acc}% 100%`)
  }
  return { background: `conic-gradient(${stops.join(', ')})` }
})
</script>

<template>
  <section class="sec" :aria-label="SECTION_STOCK_STATUS">
    <div class="sec__head">
      <OdsSectionTitle :title="SECTION_STOCK_STATUS" :icon="iconSec" />
      <button type="button" class="sec__link" @click="emit('viewAll')">
        {{ MSG_VIEW_ALL }} &gt;
      </button>
    </div>

    <div class="panel">
      <div class="donut" aria-hidden="true">
        <div class="donut__ring" :style="donutStyle" />
        <div class="donut__center">
          <p class="donut__label">총 재고</p>
          <p class="donut__value">
            {{ loading ? '…' : `${displayTotal}개` }}
          </p>
        </div>
      </div>

      <ul v-if="legendRows.length" class="legend">
        <li v-for="row in legendRows" :key="row.key" class="legend__row">
          <span class="legend__dot" :style="{ background: row.tone }" />
          <span class="legend__nm">{{ row.label }}</span>
          <span class="legend__val"
            >{{ row.kinds }}종 {{ row.qty }}개 ({{ row.pct }}%)</span
          >
        </li>
      </ul>
      <p v-else class="legend-empty">{{ loading ? '불러오는 중…' : '재고가 없습니다.' }}</p>
    </div>
  </section>
</template>

<style scoped>
.sec__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ods-space-8);
  margin-bottom: var(--ods-space-12);
}
.sec__link {
  border: none;
  background: transparent;
  padding: 0;
  min-height: var(--ods-hit-sm);
  font: var(--ods-font-form-help);
  font-weight: 700;
  color: var(--ods-color-primary);
  cursor: pointer;
}
.panel {
  display: grid;
  grid-template-columns: var(--ods-thumb-lg) 1fr;
  gap: var(--ods-card-block-gap);
  align-items: center;
  padding: var(--ods-card-padding);
  border-radius: var(--ods-radius-card);
  background: var(--ods-color-white);
  border: 1px solid var(--ods-color-border);
  box-shadow: var(--ods-shadow-card);
}
.donut {
  position: relative;
  width: var(--ods-thumb-lg);
  height: var(--ods-thumb-lg);
  margin: 0 auto;
}
.donut__ring {
  width: 100%;
  height: 100%;
  border-radius: 50%;
  mask: radial-gradient(farthest-side, transparent 58%, #000 59%);
  -webkit-mask: radial-gradient(farthest-side, transparent 58%, #000 59%);
}
.donut__center {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}
.donut__label {
  margin: 0;
  font: var(--ods-font-card-help);
  color: var(--ods-color-text-secondary);
}
.donut__value {
  margin: var(--ods-space-4) 0 0;
  font: var(--ods-font-form-value);
  font-weight: 800;
  color: var(--ods-color-text);
}
.legend {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-12);
}
.legend-empty {
  margin: 0;
  font: var(--ods-font-card-section);
  color: var(--ods-color-text-secondary);
  text-align: center;
}
.legend__row {
  display: grid;
  grid-template-columns: var(--ods-dot-md) 1fr auto;
  align-items: center;
  gap: var(--ods-space-8);
  font: var(--ods-font-card-section);
}
.legend__dot {
  width: var(--ods-dot-md);
  height: var(--ods-dot-md);
  border-radius: 50%;
}
.legend__nm {
  color: var(--ods-color-text-secondary);
}
.legend__val {
  font-weight: 700;
  color: var(--ods-color-text);
  font-variant-numeric: tabular-nums;
}
</style>
