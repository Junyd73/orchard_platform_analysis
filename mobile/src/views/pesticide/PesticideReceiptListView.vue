<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'

import { fetchPesticideReceipts } from '@/api/pesticide'
import { ApiClientError } from '@/api/client'
import OdsAppBar from '@/components/ods/OdsAppBar.vue'
import OdsBadge from '@/components/ods/OdsBadge.vue'
import OdsBottomNav from '@/components/ods/OdsBottomNav.vue'
import OdsButton from '@/components/ods/OdsButton.vue'
import OdsSkeleton from '@/components/ods/OdsSkeleton.vue'
import {
  LABEL_RECEIPT_APPLIED,
  LABEL_RECEIPT_EMPTY,
  LABEL_RECEIPT_ITEM_COUNT,
  LABEL_RECEIPT_NEW_BTN,
  LABEL_RECEIPT_PENDING,
  LABEL_RECEIPT_SUPPLIER_FALLBACK,
  LABEL_RECEIPT_TITLE,
} from '@/views/pesticide/pesticideConstants'
import { useAppStore } from '@/composables/stores/app'
import type { PesticideReceiptSummary } from '@/types/pesticide'

const router = useRouter()
const { farmCd } = storeToRefs(useAppStore())

const loading = ref(true)
const errorMsg = ref('')
const items = ref<PesticideReceiptSummary[]>([])

async function load() {
  const farm = farmCd.value
  if (!farm) return
  loading.value = true
  errorMsg.value = ''
  try {
    const res = await fetchPesticideReceipts(farm)
    items.value = res.items
  } catch (err) {
    errorMsg.value =
      err instanceof ApiClientError ? err.message : '입고 목록을 불러오지 못했습니다.'
    items.value = []
  } finally {
    loading.value = false
  }
}

watch(farmCd, () => {
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

      <div class="stack">
        <header class="head">
          <h1 class="head__title">{{ LABEL_RECEIPT_TITLE }}</h1>
          <OdsButton
            :block="false"
            @click="router.push({ name: 'pesticide-receipt-new' })"
          >
            {{ LABEL_RECEIPT_NEW_BTN }}
          </OdsButton>
        </header>

        <p v-if="errorMsg" class="error" role="alert">{{ errorMsg }}</p>
        <OdsSkeleton v-else-if="loading" height="120px" />
        <ul v-else class="list">
          <li
            v-for="it in items"
            :key="it.receipt_id"
            class="list__row"
            @click="
              router.push({
                name: 'pesticide-receipt-detail',
                params: { receiptId: String(it.receipt_id) },
              })
            "
          >
            <div class="list__main">
              <p class="list__nm">{{ it.receipt_dt }}</p>
              <p class="list__sub">
                {{ it.supplier_nm || LABEL_RECEIPT_SUPPLIER_FALLBACK }} ·
                {{ it.line_count }}{{ LABEL_RECEIPT_ITEM_COUNT }} ·
                {{ it.total_qty }}개
              </p>
            </div>
            <OdsBadge :tone="it.stock_applied_yn === 'Y' ? 'ok' : 'neutral'">
              {{
                it.stock_applied_yn === 'Y'
                  ? LABEL_RECEIPT_APPLIED
                  : LABEL_RECEIPT_PENDING
              }}
            </OdsBadge>
          </li>
          <li v-if="!items.length" class="hint">{{ LABEL_RECEIPT_EMPTY }}</li>
        </ul>
      </div>
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

.stack {
  display: flex;
  flex-direction: column;
  gap: var(--ods-page-content-gap);
}

.head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--ods-space-12);
  margin: 0;
}
.head__title {
  margin: 0;
  font: var(--ods-font-title-2);
  font-weight: 800;
  color: var(--ods-color-text);
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
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--ods-space-12);
  padding: var(--ods-space-12) var(--ods-card-padding);
  border-bottom: 1px solid var(--ods-color-border);
  cursor: pointer;
}
.list__row:last-child {
  border-bottom: none;
}
.list__row:active {
  background: var(--ods-color-bg-muted);
}
.list__main {
  min-width: 0;
  flex: 1 1 auto;
}
.list__nm {
  margin: 0;
  font: var(--ods-font-form-value);
  font-weight: 700;
  color: var(--ods-color-text);
}
.list__sub {
  margin: var(--ods-space-4) 0 0;
  font: var(--ods-font-card-section);
  color: var(--ods-color-text-secondary);
}

.hint,
.error {
  margin: 0;
  padding: var(--ods-card-padding);
  text-align: center;
  font: var(--ods-font-form-help);
  color: var(--ods-color-text-secondary);
}
.error {
  color: var(--ods-color-danger);
}
</style>
