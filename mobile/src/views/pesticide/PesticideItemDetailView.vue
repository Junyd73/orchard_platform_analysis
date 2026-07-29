<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'

import {
  fetchPesticideItemUsage,
  fetchPesticideStockDetail,
} from '@/api/pesticide'
import { ApiClientError } from '@/api/client'
import OdsAppBar from '@/components/ods/OdsAppBar.vue'
import OdsBadge from '@/components/ods/OdsBadge.vue'
import OdsBottomNav from '@/components/ods/OdsBottomNav.vue'
import OdsButton from '@/components/ods/OdsButton.vue'
import OdsEmptyState from '@/components/ods/OdsEmptyState.vue'
import OdsSkeleton from '@/components/ods/OdsSkeleton.vue'
import PesticideUsageRow from '@/views/pesticide/components/PesticideUsageRow.vue'
import {
  formatQtyPiece,
  formatThreshold,
  LABEL_LOW,
  LABEL_STOCK_SECTION,
  LABEL_USAGE_SECTION,
  LABEL_THRESHOLD,
  MSG_USAGE_EMPTY,
} from '@/views/pesticide/pesticideConstants'
import { useAppStore } from '@/composables/stores/app'
import type {
  PesticideStockItemDetail,
  PesticideUsageRow as UsageRow,
} from '@/types/pesticide'

const route = useRoute()
const router = useRouter()
const store = useAppStore()
const { farmCd } = storeToRefs(store)

const loading = ref(true)
const loadingMore = ref(false)
const errorMsg = ref('')
const item = ref<PesticideStockItemDetail | null>(null)
const usageRows = ref<UsageRow[]>([])
const usageTotal = ref(0)

const itemId = computed(() => Number(route.params.itemId))

const hasMore = computed(
  () => usageRows.value.length < usageTotal.value,
)

async function loadDetail() {
  const farm = farmCd.value
  const id = itemId.value
  if (!farm || !Number.isFinite(id) || id <= 0) return
  loading.value = true
  errorMsg.value = ''
  try {
    const res = await fetchPesticideStockDetail(farm, id)
    item.value = res.item
    const usagePage = await fetchPesticideItemUsage(farm, id, { limit: 20 })
    usageRows.value = usagePage.rows
    usageTotal.value = usagePage.total
  } catch (err) {
    errorMsg.value =
      err instanceof ApiClientError ? err.message : '품목 정보를 불러오지 못했습니다.'
    item.value = null
    usageRows.value = []
  } finally {
    loading.value = false
  }
}

async function loadMore() {
  const farm = farmCd.value
  const id = itemId.value
  if (!farm || loadingMore.value || !hasMore.value) return
  loadingMore.value = true
  try {
    const res = await fetchPesticideItemUsage(farm, id, {
      offset: usageRows.value.length,
      limit: 20,
    })
    usageRows.value = [...usageRows.value, ...res.rows]
    usageTotal.value = res.total
  } catch {
    /* ignore append failure */
  } finally {
    loadingMore.value = false
  }
}

function openWorkLog(workDt: string) {
  void router.push({ name: 'work-log-daily', params: { workDt } })
}

watch([farmCd, itemId], () => {
  void loadDetail()
})

onMounted(() => {
  void loadDetail()
})
</script>

<template>
  <div class="page">
    <main class="content ods-page-content">
      <OdsAppBar show-back back-fallback="pesticide" />

      <header class="hero">
        <div v-if="item" class="hero__body">
          <div class="hero__head">
            <h1 class="hero__title">{{ item.item_nm }}</h1>
            <OdsBadge v-if="item.is_low" tone="danger">{{ LABEL_LOW }}</OdsBadge>
          </div>
          <p v-if="item.spec_nm || item.info_pesticide_nm" class="hero__sub">
            <template v-if="item.spec_nm">{{ item.spec_nm }}</template>
            <template v-if="item.spec_nm && item.info_pesticide_nm"> · </template>
            <template v-if="item.info_pesticide_nm">{{ item.info_pesticide_nm }}</template>
          </p>
        </div>
        <OdsSkeleton v-else-if="loading" height="56px" />
      </header>

      <p v-if="errorMsg" class="error" role="alert">{{ errorMsg }}</p>

      <section v-if="item" class="section" :aria-label="LABEL_STOCK_SECTION">
        <h2 class="section__title">{{ LABEL_STOCK_SECTION }}</h2>
        <article class="stock-card">
          <dl class="stock-card__grid">
            <div>
              <dt>현재고</dt>
              <dd>{{ formatQtyPiece(item.qty_piece) }}</dd>
            </div>
            <div>
              <dt>{{ LABEL_THRESHOLD }}</dt>
              <dd>{{ formatThreshold(item.warn_threshold, item.warn_source) }}</dd>
            </div>
          </dl>
          <p v-if="item.rmk" class="stock-card__rmk">{{ item.rmk }}</p>
        </article>
      </section>

      <section class="section" :aria-label="LABEL_USAGE_SECTION">
        <h2 class="section__title">{{ LABEL_USAGE_SECTION }}</h2>
        <OdsSkeleton v-if="loading" height="80px" />
        <OdsEmptyState
          v-else-if="!usageRows.length"
          :title="MSG_USAGE_EMPTY"
        />
        <ul v-else class="usage-list">
          <li v-for="row in usageRows" :key="row.use_line_id">
            <PesticideUsageRow :row="row" @open-work="openWorkLog" />
          </li>
        </ul>
        <OdsButton
          v-if="hasMore && !loading"
          class="more"
          variant="secondary"
          :busy="loadingMore"
          @click="loadMore"
        >
          더 보기
        </OdsButton>
      </section>
    </main>

    <OdsBottomNav />
  </div>
</template>

<style scoped>
.page {
  min-height: 100dvh;
  background: var(--ods-color-bg);
  padding-bottom: calc(var(--ods-space-56) + env(safe-area-inset-bottom));
}
.content {
  /* padding/max-width/gap -> .ods-page-content (AppBar SSOT) */
}
.hero__body {
  margin-top: var(--ods-space-4);
}
.hero__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--ods-space-8);
}
.hero__title {
  margin: 0;
  font: var(--ods-font-title-1);
  font-weight: 800;
  color: var(--ods-color-text);
}
.hero__sub {
  margin: var(--ods-space-8) 0 0;
  font: var(--ods-font-form-help);
  color: var(--ods-color-text-secondary);
}
.section {
  margin-top: var(--ods-space-20);
}
.section__title {
  margin: 0 0 var(--ods-space-8);
  font: var(--ods-font-headline);
  font-weight: 800;
  color: var(--ods-color-text);
}
.stock-card {
  padding: var(--ods-space-16) var(--ods-space-16);
  border-radius: var(--ods-radius-card);
  border: 1px solid var(--ods-color-border);
  background: var(--ods-color-white);
  box-shadow: var(--ods-shadow-card);
}
.stock-card__grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--ods-space-12);
  margin: 0;
}
.stock-card__grid dt {
  margin: 0;
  font: var(--ods-font-card-help);
  color: var(--ods-color-text-secondary);
}
.stock-card__grid dd {
  margin: var(--ods-space-4) 0 0;
  font: var(--ods-font-form-value);
  font-weight: 700;
  color: var(--ods-color-text);
}
.stock-card__rmk {
  margin: var(--ods-space-12) 0 0;
  font: var(--ods-font-form-help);
  color: var(--ods-color-text-secondary);
}
.usage-list {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-8);
  margin: 0;
  padding: 0;
  list-style: none;
}
.more {
  width: 100%;
  margin-top: var(--ods-space-12);
}
.error {
  margin: var(--ods-space-12) 0 0;
  font: var(--ods-font-form-help);
  color: var(--ods-color-danger);
}
</style>
