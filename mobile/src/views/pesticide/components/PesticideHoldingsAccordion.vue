<script setup lang="ts">
import { computed, ref } from 'vue'

import {
  COL_INGREDIENT,
  COL_ITEM_NM,
  COL_PEST_TARGET,
  COL_STOCK,
  formatStockQty,
  HOLDINGS_CATEGORIES,
  holdingsCategoryKeyOf,
  isStockQtyWarn,
  MSG_HOLDINGS_EMPTY,
  PLACEHOLDER_DASH,
  SECTION_HOLDINGS,
  type HoldingsCategoryKey,
} from '@/views/pesticide/pesticideConstants'
import type { PesticideStockItem } from '@/types/pesticide'

type HoldingRow = {
  item_id: number
  item_nm: string
  pest_target_nm: string
  ingredient_nm: string
  qty_piece: number
}

const props = defineProps<{
  items: PesticideStockItem[]
  loading?: boolean
}>()

const emit = defineEmits<{
  select: [itemId: number]
}>()

const openMap = ref<Record<HoldingsCategoryKey, boolean>>(
  Object.fromEntries(
    HOLDINGS_CATEGORIES.map((c) => [c.key, c.defaultOpen]),
  ) as Record<HoldingsCategoryKey, boolean>,
)

function displayOrDash(raw: string | null | undefined): string {
  const s = String(raw || '').trim()
  return s || PLACEHOLDER_DASH
}

const grouped = computed(() => {
  const map: Record<HoldingsCategoryKey, HoldingRow[]> = {
    insect: [],
    fungus: [],
    nutrient: [],
    other: [],
  }
  for (const it of props.items) {
    if (it.qty_piece <= 0) continue
    const key = holdingsCategoryKeyOf(it.pest_category_nm)
    map[key].push({
      item_id: it.item_id,
      item_nm: it.item_nm,
      pest_target_nm: displayOrDash(it.pest_target_nm),
      ingredient_nm: displayOrDash(it.ingredient_nm),
      qty_piece: it.qty_piece,
    })
  }
  for (const cat of HOLDINGS_CATEGORIES) {
    map[cat.key].sort(compareHoldingRows)
  }
  return map
})

/** 품목명 가나다순 */
function compareHoldingRows(a: HoldingRow, b: HoldingRow): number {
  return a.item_nm.localeCompare(b.item_nm, 'ko')
}

const counts = computed(() => {
  const out: Record<HoldingsCategoryKey, number> = {
    insect: 0,
    fungus: 0,
    nutrient: 0,
    other: 0,
  }
  for (const cat of HOLDINGS_CATEGORIES) {
    out[cat.key] = grouped.value[cat.key].length
  }
  return out
})

function toggle(key: HoldingsCategoryKey) {
  openMap.value = { ...openMap.value, [key]: !openMap.value[key] }
}
</script>

<template>
  <section class="sec" :aria-label="SECTION_HOLDINGS">
    <p v-if="loading" class="hint">불러오는 중…</p>

    <div v-else class="acc">
      <div
        v-for="cat in HOLDINGS_CATEGORIES"
        :key="cat.key"
        class="acc__panel"
      >
        <button
          type="button"
          class="acc__head"
          :aria-expanded="openMap[cat.key]"
          @click="toggle(cat.key)"
        >
          <span class="acc__title">
            {{ cat.label }}
            <span class="acc__count">{{ counts[cat.key] }}</span>
          </span>
          <span class="acc__chev" :class="{ 'acc__chev--open': openMap[cat.key] }"
            >›</span
          >
        </button>

        <div v-show="openMap[cat.key]" class="acc__body">
          <p v-if="!grouped[cat.key].length" class="acc__empty">
            {{ MSG_HOLDINGS_EMPTY }}
          </p>
          <div v-else class="tbl-wrap">
            <table class="tbl">
              <thead>
                <tr>
                  <th scope="col">{{ COL_ITEM_NM }}</th>
                  <th scope="col">{{ COL_PEST_TARGET }}</th>
                  <th scope="col">{{ COL_INGREDIENT }}</th>
                  <th scope="col" class="tbl__qty-h">{{ COL_STOCK }}</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="row in grouped[cat.key]"
                  :key="row.item_id"
                  class="tbl__row"
                  @click="emit('select', row.item_id)"
                >
                  <td>
                    <span
                      class="tbl__nm"
                      :class="{ 'tbl__nm--warn': isStockQtyWarn(row.qty_piece) }"
                    >{{ row.item_nm }}</span>
                  </td>
                  <td>{{ row.pest_target_nm }}</td>
                  <td>{{ row.ingredient_nm }}</td>
                  <td class="tbl__qty">
                    {{ formatStockQty(row.qty_piece) }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.hint {
  margin: 0;
  font: var(--ods-font-card-section);
  color: var(--ods-color-text-secondary);
  text-align: center;
}
.acc {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-8);
}
.acc__panel {
  border-radius: var(--ods-radius-card);
  background: var(--ods-color-white);
  border: 1px solid var(--ods-color-border);
  box-shadow: var(--ods-shadow-card);
  overflow: hidden;
}
.acc__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  min-height: var(--ods-button-height);
  padding: 0 var(--ods-space-16);
  border: none;
  background: var(--ods-color-bg-muted);
  cursor: pointer;
  text-align: left;
}
.acc__title {
  display: inline-flex;
  align-items: center;
  gap: var(--ods-space-8);
  font: var(--ods-font-form-value);
  font-weight: 800;
  color: var(--ods-color-text);
}
.acc__count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: var(--ods-icon-xl);
  height: var(--ods-space-20);
  padding: 0 var(--ods-space-8);
  border-radius: var(--ods-radius-badge);
  font: var(--ods-font-card-meta);
  font-weight: 700;
  color: var(--ods-color-primary);
  background: color-mix(in srgb, var(--ods-color-primary) 12%, var(--ods-color-white));
}
.acc__chev {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: var(--ods-icon-2xl);
  height: var(--ods-icon-2xl);
  font: var(--ods-font-title-2);
  font-weight: 700;
  color: var(--ods-color-gray-500);
  transform: rotate(90deg);
  transition: transform 0.15s ease;
}
.acc__chev--open {
  transform: rotate(-90deg);
}
.acc__body {
  border-top: 1px solid var(--ods-color-border);
}
.acc__empty {
  margin: 0;
  padding: var(--ods-space-16);
  font: var(--ods-font-card-section);
  color: var(--ods-color-text-secondary);
  text-align: center;
}
.tbl-wrap {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}
.tbl {
  width: 100%;
  min-width: 320px;
  border-collapse: collapse;
  font: var(--ods-font-card-meta);
}
.tbl th {
  padding: var(--ods-space-8);
  text-align: left;
  font: var(--ods-font-card-section);
  font-weight: 700;
  color: var(--ods-color-text);
  background: var(--ods-color-gray-100);
  border-bottom: 1px solid var(--ods-color-border);
  white-space: nowrap;
}
.tbl__qty-h {
  text-align: right;
}
.tbl td {
  padding: var(--ods-space-8);
  border-bottom: 1px solid var(--ods-color-border);
  color: var(--ods-color-text);
  vertical-align: top;
  word-break: keep-all;
}
.tbl tr:last-child td {
  border-bottom: none;
}
.tbl__row {
  cursor: pointer;
}
.tbl__row:active {
  background: var(--ods-color-bg-muted);
}
.tbl__nm {
  font: var(--ods-font-card-emphasis);
  font-weight: 700;
  color: var(--ods-color-text);
}
.tbl__nm--warn {
  color: var(--ods-color-danger);
}
.tbl__qty {
  text-align: right;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
</style>
