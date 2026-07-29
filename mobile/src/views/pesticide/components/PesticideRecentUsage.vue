<script setup lang="ts">
import { computed } from 'vue'

import iconSec from '@/assets/ods/pesticide/icon-sec-history.svg'
import OdsSectionTitle from '@/components/ods/OdsSectionTitle.vue'
import {
  COL_DATE,
  COL_USED,
  formatUsageLines,
  MSG_USAGE_EMPTY,
  MSG_VIEW_ALL,
  SECTION_RECENT_USAGE,
} from '@/views/pesticide/pesticideConstants'
import type { PesticideRecentUsageDay } from '@/types/pesticide'

const props = defineProps<{
  days?: PesticideRecentUsageDay[]
  loading?: boolean
}>()

const emit = defineEmits<{
  viewAll: []
}>()

const rows = computed(() =>
  (props.days || []).map((d) => ({
    use_dt: d.use_dt,
    text: formatUsageLines(
      d.lines.map((ln) => ({
        item_nm: ln.item_nm,
        qty: ln.use_qty,
        unit: ln.unit,
      })),
    ),
  })),
)
</script>

<template>
  <section class="sec" :aria-label="SECTION_RECENT_USAGE">
    <div class="sec__head">
      <OdsSectionTitle :title="SECTION_RECENT_USAGE" :icon="iconSec" />
      <button type="button" class="sec__link" @click="emit('viewAll')">
        {{ MSG_VIEW_ALL }} &gt;
      </button>
    </div>

    <div class="panel">
      <p v-if="loading" class="hint">불러오는 중…</p>
      <p v-else-if="!rows.length" class="hint">{{ MSG_USAGE_EMPTY }}</p>
      <table v-else class="tbl">
        <thead>
          <tr>
            <th scope="col" class="tbl__dt-h">{{ COL_DATE }}</th>
            <th scope="col">{{ COL_USED }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, i) in rows" :key="`${row.use_dt}-${i}`">
            <td class="tbl__dt">{{ row.use_dt }}</td>
            <td class="tbl__used">{{ row.text }}</td>
          </tr>
        </tbody>
      </table>
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
  border-radius: var(--ods-radius-card);
  background: var(--ods-color-white);
  border: 1px solid var(--ods-color-border);
  box-shadow: var(--ods-shadow-card);
  overflow: hidden;
}
.hint {
  margin: 0;
  padding: var(--ods-space-20) var(--ods-space-12);
  font: var(--ods-font-card-section);
  color: var(--ods-color-text-secondary);
  text-align: center;
}
.tbl {
  width: 100%;
  border-collapse: collapse;
  font: var(--ods-font-card-section);
  table-layout: fixed;
}
.tbl th {
  padding: var(--ods-space-8) var(--ods-space-12);
  text-align: left;
  font-weight: 700;
  font: var(--ods-font-card-meta);
  color: var(--ods-color-text-secondary);
  background: var(--ods-color-gray-100);
  border-bottom: 1px solid var(--ods-color-border);
}
.tbl__dt-h {
  width: var(--ods-thumb-lg);
}
.tbl td {
  padding: var(--ods-space-12);
  border-bottom: 1px solid var(--ods-color-border);
  color: var(--ods-color-text);
  vertical-align: top;
}
.tbl tr:last-child td {
  border-bottom: none;
}
.tbl__dt {
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
  color: var(--ods-color-text-secondary);
}
.tbl__used {
  font-weight: 600;
  line-height: 1.45;
  word-break: keep-all;
}
</style>
