<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'

import { fetchPesticideYearlyStats } from '@/api/pesticide'
import { ApiClientError } from '@/api/client'
import OdsAppBar from '@/components/ods/OdsAppBar.vue'
import OdsBadge from '@/components/ods/OdsBadge.vue'
import OdsBottomNav from '@/components/ods/OdsBottomNav.vue'
import OdsCard from '@/components/ods/OdsCard.vue'
import OdsSegmented, {
  type OdsSegmentOption,
} from '@/components/ods/OdsSegmented.vue'
import OdsSkeleton from '@/components/ods/OdsSkeleton.vue'
import {
  HOLDINGS_CATEGORIES,
  holdingsCategoryKeyOf,
  type HoldingsCategoryKey,
} from '@/views/pesticide/pesticideConstants'
import { useAppStore } from '@/composables/stores/app'
import type { PesticideYearlyStatsItem } from '@/types/pesticide'

const { farmCd } = storeToRefs(useAppStore())

const year = ref(new Date().getFullYear())
const loading = ref(true)
const errorMsg = ref('')
const items = ref<PesticideYearlyStatsItem[]>([])
/** 기본: 일자별 */
const tab = ref('day')

const tabOptions: OdsSegmentOption[] = [
  { value: 'day', label: '일자별' },
  { value: 'item', label: '농약별' },
]

const openMap = ref<Record<HoldingsCategoryKey, boolean>>(
  Object.fromEntries(
    HOLDINGS_CATEGORIES.map((c) => [c.key, c.defaultOpen]),
  ) as Record<HoldingsCategoryKey, boolean>,
)

const yearOptions = computed(() => {
  const y = new Date().getFullYear()
  return [y, y - 1, y - 2, y - 3]
})

const dayRows = computed(() => {
  const map = new Map<string, { qty: number; names: string[] }>()
  for (const it of items.value) {
    for (const [d, q] of Object.entries(it.daily || {})) {
      const prev = map.get(d) || { qty: 0, names: [] }
      prev.qty += q
      if (q > 0) prev.names.push(`${it.item_nm} ${q}`)
      map.set(d, prev)
    }
  }
  return [...map.entries()]
    .map(([use_dt, v]) => ({
      use_dt,
      qty: v.qty,
      detail: v.names.join(' , '),
    }))
    .sort((a, b) => b.use_dt.localeCompare(a.use_dt))
})

const itemGroups = computed(() => {
  const map: Record<HoldingsCategoryKey, PesticideYearlyStatsItem[]> = {
    insect: [],
    fungus: [],
    nutrient: [],
    other: [],
  }
  for (const it of items.value) {
    map[holdingsCategoryKeyOf(it.pest_category_nm)].push(it)
  }
  for (const cat of HOLDINGS_CATEGORIES) {
    map[cat.key].sort(
      (a, b) =>
        b.total_qty - a.total_qty || a.item_nm.localeCompare(b.item_nm, 'ko'),
    )
  }
  return map
})

const groupCounts = computed(() => {
  const out: Record<HoldingsCategoryKey, number> = {
    insect: 0,
    fungus: 0,
    nutrient: 0,
    other: 0,
  }
  for (const cat of HOLDINGS_CATEGORIES) {
    out[cat.key] = itemGroups.value[cat.key].length
  }
  return out
})

function toggle(key: HoldingsCategoryKey) {
  openMap.value = { ...openMap.value, [key]: !openMap.value[key] }
}

async function load() {
  const farm = farmCd.value
  if (!farm) return
  loading.value = true
  errorMsg.value = ''
  try {
    const res = await fetchPesticideYearlyStats(farm, year.value)
    items.value = res.items
  } catch (err) {
    errorMsg.value =
      err instanceof ApiClientError ? err.message : '통계를 불러오지 못했습니다.'
    items.value = []
  } finally {
    loading.value = false
  }
}

watch([farmCd, year], () => {
  void load()
})

onMounted(() => {
  void load()
})
</script>

<template>
  <div class="page">
    <main class="content ods-page-content">
      <OdsAppBar show-back back-fallback="pesticide" />
      <header class="head">
        <h1 class="head__title">사용 통계</h1>
        <label class="year">
          <span class="sr">연도</span>
          <select v-model.number="year">
            <option v-for="y in yearOptions" :key="y" :value="y">
              {{ y }}년
            </option>
          </select>
        </label>
      </header>

      <p v-if="errorMsg" class="error" role="alert">{{ errorMsg }}</p>
      <OdsSkeleton v-else-if="loading" height="160px" />
      <template v-else>
        <OdsCard class="tabs-card">
          <OdsSegmented
            v-model="tab"
            :options="tabOptions"
            aria-label="통계 구분"
          />
        </OdsCard>

        <OdsCard v-if="tab === 'day'" class="panel-card">
          <p v-if="!dayRows.length" class="hint">
            해당 연도 사용 내역이 없습니다.
          </p>
          <ul v-else class="list">
            <li
              v-for="row in dayRows"
              :key="row.use_dt"
              class="list__row list__row--col"
            >
              <div class="list__dayhead">
                <span>{{ row.use_dt }}</span>
                <OdsBadge tone="ok">{{ row.qty }}개</OdsBadge>
              </div>
              <p class="list__sub">{{ row.detail }}</p>
            </li>
          </ul>
        </OdsCard>

        <div v-else class="acc">
          <OdsCard v-if="!items.length">
            <p class="hint">해당 연도 사용 내역이 없습니다.</p>
          </OdsCard>
          <template v-else>
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
                <span>{{ cat.label }}</span>
                <span class="acc__meta">
                  <OdsBadge tone="neutral">{{ groupCounts[cat.key] }}종</OdsBadge>
                  <span class="acc__chev" aria-hidden="true">{{
                    openMap[cat.key] ? '▾' : '▸'
                  }}</span>
                </span>
              </button>
              <ul v-if="openMap[cat.key]" class="list">
                <li v-if="!itemGroups[cat.key].length" class="hint hint--sm">
                  사용 내역 없음
                </li>
                <li
                  v-for="it in itemGroups[cat.key]"
                  :key="it.item_id"
                  class="list__row"
                >
                  <div>
                    <p class="list__nm">{{ it.item_nm }}</p>
                    <p v-if="it.spec_nm" class="list__sub">{{ it.spec_nm }}</p>
                  </div>
                  <p class="list__qty">{{ it.total_qty }}개</p>
                </li>
              </ul>
            </div>
          </template>
        </div>
      </template>
    </main>
    <OdsBottomNav />
  </div>
</template>

<style scoped>
.page {
  min-height: 100dvh;
  background: var(--ods-color-bg-muted);
  padding-bottom: calc(var(--ods-thumb-sm) + env(safe-area-inset-bottom));
}
.head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ods-space-12);
  margin-bottom: var(--ods-space-12);
}
.head__title {
  margin: 0;
  font: var(--ods-font-title-2);
  font-weight: 800;
}
.year select {
  min-height: var(--ods-control-height);
  border-radius: var(--ods-radius-button);
  border: 1px solid var(--ods-color-border);
  padding: 0 var(--ods-space-12);
  background: var(--ods-color-white);
  font: var(--ods-font-form-value);
  font-weight: 700;
}
.tabs-card :deep(.ods-segmented) {
  width: 100%;
  max-width: none;
}
.panel-card {
  padding: 0;
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
  width: 100%;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--ods-space-12);
  min-height: var(--ods-button-height);
  padding: 0 var(--ods-space-16);
  border: none;
  background: var(--ods-color-bg-muted);
  font: var(--ods-font-form-value);
  font-weight: 800;
  color: var(--ods-color-text);
  cursor: pointer;
  text-align: left;
}
.acc__meta {
  display: inline-flex;
  align-items: center;
  gap: var(--ods-space-8);
  font: var(--ods-font-card-section);
  font-weight: 700;
  color: var(--ods-color-text-secondary);
}
.acc__chev {
  font: var(--ods-font-card-section);
}
.list {
  margin: 0;
  padding: 0;
  list-style: none;
}
.list__row {
  display: flex;
  justify-content: space-between;
  gap: var(--ods-space-12);
  padding: var(--ods-space-12) var(--ods-space-16);
  border-bottom: 1px solid var(--ods-color-border);
}
.list__row--col {
  flex-direction: column;
}
.list__row:last-child {
  border-bottom: none;
}
.list__nm {
  margin: 0;
  font: var(--ods-font-form-value);
  font-weight: 700;
}
.list__sub {
  margin: var(--ods-space-4) 0 0;
  font: var(--ods-font-card-section);
  color: var(--ods-color-text-secondary);
  line-height: 1.4;
}
.list__qty {
  margin: 0;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
}
.list__dayhead {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font: var(--ods-font-form-help);
  font-weight: 700;
}
.hint,
.error {
  margin: 0;
  padding: var(--ods-space-16);
  text-align: center;
  font: var(--ods-font-form-help);
}
.hint--sm {
  padding: var(--ods-space-12) var(--ods-space-16);
  color: var(--ods-color-text-secondary);
}
.error {
  color: var(--ods-color-danger);
}
.sr {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
}
</style>
