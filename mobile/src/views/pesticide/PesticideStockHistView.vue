<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { storeToRefs } from 'pinia'

import { fetchPesticideStockHist } from '@/api/pesticide'
import { ApiClientError } from '@/api/client'
import OdsAppBar from '@/components/ods/OdsAppBar.vue'
import OdsBadge from '@/components/ods/OdsBadge.vue'
import OdsBottomNav from '@/components/ods/OdsBottomNav.vue'
import OdsCard from '@/components/ods/OdsCard.vue'
import OdsSkeleton from '@/components/ods/OdsSkeleton.vue'
import {
  HIST_TYPE_LABEL,
  LABEL_STOCK_HIST_TITLE,
} from '@/views/pesticide/pesticideConstants'
import { useAppStore } from '@/composables/stores/app'
import type { PesticideStockHistRow } from '@/types/pesticide'

const route = useRoute()
const { farmCd } = storeToRefs(useAppStore())

const itemId = computed(() => Number(route.params.itemId))
const loading = ref(true)
const errorMsg = ref('')
const itemNm = ref('')
const rows = ref<PesticideStockHistRow[]>([])

function typeLabel(row: PesticideStockHistRow): string {
  return HIST_TYPE_LABEL[row.trans_type] || row.trans_type
}

function metaText(row: PesticideStockHistRow): string {
  const parts: string[] = []
  if (row.trans_dt) parts.push(row.trans_dt)
  if (row.trans_type === 'IN' && row.receipt_dt) {
    parts.push(`입고일 ${row.receipt_dt}`)
  }
  if (row.supplier_nm) parts.push(row.supplier_nm)
  if (row.rmk) parts.push(row.rmk)
  return parts.join(' · ')
}

async function load() {
  const farm = farmCd.value
  const id = itemId.value
  if (!farm || !id) return
  loading.value = true
  errorMsg.value = ''
  try {
    const res = await fetchPesticideStockHist(farm, id)
    itemNm.value = res.item_nm
    rows.value = res.rows
  } catch (err) {
    errorMsg.value =
      err instanceof ApiClientError ? err.message : '이력을 불러오지 못했습니다.'
    rows.value = []
  } finally {
    loading.value = false
  }
}

watch([farmCd, itemId], () => {
  void load()
})

onMounted(() => {
  void load()
})
</script>

<template>
  <div class="page">
    <main class="content ods-page-content">
      <OdsAppBar show-back back-fallback="pesticide-stock" />
      <p class="eyebrow">{{ LABEL_STOCK_HIST_TITLE }}</p>
      <h1 class="item-nm">{{ itemNm || `품목 #${itemId}` }}</h1>
      <p v-if="errorMsg" class="error" role="alert">{{ errorMsg }}</p>
      <OdsSkeleton v-else-if="loading" height="120px" />
      <OdsCard v-else-if="!rows.length">
        <p class="hint">변동 이력이 없습니다.</p>
      </OdsCard>
      <ul v-else class="list">
        <li v-for="r in rows" :key="r.hist_id" class="list__row">
          <div class="list__main">
            <p class="list__type">
              <OdsBadge
                :tone="r.qty_delta < 0 ? 'danger' : 'ok'"
              >
                {{ typeLabel(r) }}
              </OdsBadge>
              <span class="delta" :class="{ 'delta--neg': r.qty_delta < 0 }">
                {{ r.qty_delta > 0 ? `+${r.qty_delta}` : r.qty_delta }}
              </span>
            </p>
            <p class="list__meta">{{ metaText(r) }}</p>
          </div>
          <p class="list__after">
            <span class="list__after-lbl">잔량</span>
            <strong>{{ r.qty_after != null ? r.qty_after : '—' }}</strong>
          </p>
        </li>
      </ul>
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
.eyebrow {
  margin: 0 0 var(--ods-space-4);
  font: var(--ods-font-card-section);
  font-weight: 700;
  color: var(--ods-color-text-secondary);
}
.item-nm {
  margin: 0 0 var(--ods-space-16);
  font: var(--ods-font-title-1);
  font-weight: 800;
  line-height: 1.25;
  color: var(--ods-color-text);
  letter-spacing: -0.02em;
}
.list {
  margin: 0;
  padding: 0;
  list-style: none;
  border-radius: var(--ods-radius-card);
  background: var(--ods-color-white);
  border: 1px solid var(--ods-color-border);
  box-shadow: var(--ods-shadow-card);
  overflow: hidden;
}
.list__row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: var(--ods-space-12);
  padding: var(--ods-space-12) var(--ods-space-16);
  border-bottom: 1px solid var(--ods-color-border);
}
.list__row:last-child {
  border-bottom: none;
}
.list__main {
  min-width: 0;
  flex: 1;
}
.list__type {
  margin: 0;
  font: var(--ods-font-form-value);
  font-weight: 800;
  display: flex;
  gap: var(--ods-space-8);
  align-items: center;
}
.delta {
  color: var(--ods-color-primary);
  font-variant-numeric: tabular-nums;
}
.delta--neg {
  color: var(--ods-color-danger);
}
.list__meta {
  margin: var(--ods-space-4) 0 0;
  font: var(--ods-font-card-section);
  color: var(--ods-color-text-secondary);
  line-height: 1.4;
}
.list__after {
  margin: 0;
  flex-shrink: 0;
  text-align: right;
  font-variant-numeric: tabular-nums;
}
.list__after-lbl {
  display: block;
  font: var(--ods-font-card-meta);
  font-weight: 700;
  color: var(--ods-color-text-secondary);
}
.list__after strong {
  font: var(--ods-font-headline);
  font-weight: 800;
  color: var(--ods-color-text);
}
.hint,
.error {
  margin: 0;
  padding: var(--ods-space-16);
  text-align: center;
  font: var(--ods-font-form-help);
}
.error {
  color: var(--ods-color-danger);
}
</style>
