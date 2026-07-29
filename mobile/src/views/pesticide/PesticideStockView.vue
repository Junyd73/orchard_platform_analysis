<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'

import {
  fetchPesticideRecentUsage,
  fetchPesticideStockList,
} from '@/api/pesticide'
import { ApiClientError } from '@/api/client'
import OdsAppBar from '@/components/ods/OdsAppBar.vue'
import OdsBottomNav from '@/components/ods/OdsBottomNav.vue'
import OdsButton from '@/components/ods/OdsButton.vue'
import OdsSkeleton from '@/components/ods/OdsSkeleton.vue'
import PesticideHero from '@/views/pesticide/components/PesticideHero.vue'
import PesticideHoldingsAccordion from '@/views/pesticide/components/PesticideHoldingsAccordion.vue'
import PesticideQuickMenu from '@/views/pesticide/components/PesticideQuickMenu.vue'
import PesticideRecentUsage from '@/views/pesticide/components/PesticideRecentUsage.vue'
import PesticideStockOverview from '@/views/pesticide/components/PesticideStockOverview.vue'
import {
  COL_INGREDIENT,
  COL_PEST_TARGET,
  buildCategoryShares,
  formatStockQty,
  isStockQtyWarn,
  MSG_COMING_SOON,
  PLACEHOLDER_DASH,
  RECENT_USAGE_DAYS,
  RECENT_USAGE_MAX_DAYS,
  type PesticideQuickActionKey,
} from '@/views/pesticide/pesticideConstants'
import { useAppStore } from '@/composables/stores/app'
import type {
  PesticideRecentUsageDay,
  PesticideStockItem,
} from '@/types/pesticide'

const router = useRouter()
const route = useRoute()
const store = useAppStore()
const { farmCd } = storeToRefs(store)

const loading = ref(true)
const errorMsg = ref('')
const toastMsg = ref('')
const items = ref<PesticideStockItem[]>([])
const lastSprayDt = ref<string | null>(null)
const recentDays = ref<PesticideRecentUsageDay[]>([])

const holdingsSection = ref<HTMLElement | null>(null)

/** 스마트방제 등에서 넘긴 병해충 필터 */
const pestFilter = computed(() => String(route.query.pest_nm || '').trim())

/** 표준명(응애) ↔ 세부명(점박이응애) 양방향 포함 매칭 */
function matchesPestTarget(
  target: string | null | undefined,
  pest: string,
): boolean {
  const needle = pest.replace(/\s+/g, '')
  if (!needle) return true
  const hay = String(target || '').replace(/\s+/g, '')
  if (!hay) return false
  if (hay.includes(needle) || needle.includes(hay)) return true
  return hay.split(/[,，/·]/).some((part) => {
    const p = part.trim()
    return Boolean(p && (p.includes(needle) || needle.includes(p)))
  })
}

const filteredItems = computed(() => {
  const pest = pestFilter.value
  if (!pest) return items.value
  return items.value.filter((it) => matchesPestTarget(it.pest_target_nm, pest))
})

/** 재고 있는 품목만 (목록·KPI·도넛 공통) — 품목명 가나다순 */
const stockedItems = computed(() =>
  filteredItems.value
    .filter((it) => (it.qty_piece || 0) > 0)
    .slice()
    .sort((a, b) => a.item_nm.localeCompare(b.item_nm, 'ko')),
)

const totalCount = computed(() => stockedItems.value.length)

const lowCount = computed(
  () => stockedItems.value.filter((it) => isStockQtyWarn(it.qty_piece)).length,
)

const totalPiece = computed(() =>
  stockedItems.value.reduce((sum, it) => sum + Math.max(0, it.qty_piece || 0), 0),
)

const categoryShares = computed(() => buildCategoryShares(stockedItems.value))

async function load() {
  const farm = farmCd.value
  if (!farm) return
  loading.value = true
  errorMsg.value = ''
  try {
    const [stockRes, usageRes] = await Promise.all([
      // 전체 재고 조회 후 클라이언트에서 병해충 대상 매칭(세부명 포함)
      fetchPesticideStockList(farm, { sort: 'name' }),
      fetchPesticideRecentUsage(farm, {
        days: RECENT_USAGE_DAYS,
        max_days: RECENT_USAGE_MAX_DAYS,
      }),
    ])
    items.value = stockRes.items
    lastSprayDt.value =
      usageRes.last_spray_dt || stockRes.summary.last_spray_dt || null
    recentDays.value = usageRes.days || []
  } catch (err) {
    errorMsg.value =
      err instanceof ApiClientError ? err.message : '재고를 불러오지 못했습니다.'
    items.value = []
    lastSprayDt.value = null
    recentDays.value = []
  } finally {
    loading.value = false
  }
}

function showToast(msg: string) {
  toastMsg.value = msg
  window.setTimeout(() => {
    if (toastMsg.value === msg) toastMsg.value = ''
  }, 2200)
}

function openItem(itemId: number) {
  void router.push({
    name: 'pesticide-detail',
    params: { itemId: String(itemId) },
  })
}

function displayOrDash(raw: string | null | undefined): string {
  const s = String(raw || '').trim()
  return s || PLACEHOLDER_DASH
}

function scrollToHoldings() {
  holdingsSection.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function onQuick(key: PesticideQuickActionKey) {
  if (key === 'stock') {
    void router.push({ name: 'pesticide-stock' })
    return
  }
  if (key === 'low') {
    scrollToHoldings()
    return
  }
  if (key === 'stats') {
    void router.push({ name: 'pesticide-stats' })
    return
  }
  if (key === 'dict') {
    void router.push({ name: 'pesticide-dict' })
    return
  }
  if (key === 'pest-dict') {
    void router.push({ name: 'pesticide-pest-dict' })
    return
  }
  if (key === 'receipt') {
    void router.push({ name: 'pesticide-receipts' })
    return
  }
  showToast(MSG_COMING_SOON)
}

watch(farmCd, () => {
  void load()
})

watch(pestFilter, () => {
  void load()
})

onMounted(() => {
  void load()
})
</script>

<template>
  <div class="page">
    <main class="content ods-page-content">
      <OdsAppBar
        :show-back="Boolean(pestFilter)"
        back-fallback="pesticide-smart-spray"
      />

      <!-- 스마트방제 등: 해당 병해충 대상 농약만 리스트 -->
      <template v-if="pestFilter">
        <header class="pest-head">
          <h1 class="pest-head__title">{{ pestFilter }} 대상 농약재고</h1>
          <p class="pest-head__sub">
            적용 대상이 「{{ pestFilter }}」인 보유 농약만 표시합니다.
          </p>
        </header>

        <p v-if="errorMsg" class="error" role="alert">{{ errorMsg }}</p>
        <OdsSkeleton v-if="loading && !stockedItems.length" height="120px" />

        <ul v-else class="pest-list">
          <li
            v-for="it in stockedItems"
            :key="it.item_id"
            class="pest-list__row"
            @click="openItem(it.item_id)"
          >
            <div class="pest-list__main">
              <p class="pest-list__nm">{{ it.item_nm }}</p>
              <p class="pest-list__meta">
                {{ COL_PEST_TARGET }} ·
                {{ displayOrDash(it.pest_target_nm) }}
              </p>
              <p class="pest-list__meta">
                {{ COL_INGREDIENT }} ·
                {{ displayOrDash(it.ingredient_nm) }}
              </p>
            </div>
            <p
              class="pest-list__qty"
              :class="{ 'pest-list__qty--warn': isStockQtyWarn(it.qty_piece) }"
            >
              {{ formatStockQty(it.qty_piece) }}
            </p>
          </li>
          <li v-if="!loading && !stockedItems.length" class="pest-list__empty">
            해당 병해충 대상 농약재고가 없습니다.
          </li>
        </ul>
      </template>

      <!-- 농약 관리 메인 -->
      <template v-else>
        <OdsSkeleton
          v-if="loading && !items.length"
          variant="hero"
          height="180px"
        />
        <PesticideHero
          v-else
          :total-count="totalCount"
          :low-count="lowCount"
          :last-spray-dt="lastSprayDt"
          :next-spray-dt="null"
          :loading="loading"
        />

        <p v-if="errorMsg" class="error" role="alert">{{ errorMsg }}</p>

        <PesticideQuickMenu @select="onQuick" />

        <div class="spr-links">
          <OdsButton @click="router.push({ name: 'pesticide-smart-spray' })">
            스마트방제 안내
          </OdsButton>
          <OdsButton
            variant="secondary"
            @click="router.push({ name: 'pesticide-outbreak-settings' })"
          >
            발병여건 설정
          </OdsButton>
        </div>

        <PesticideStockOverview
          :total-piece="totalPiece"
          :shares="categoryShares"
          :loading="loading"
          @view-all="scrollToHoldings"
        />

        <div ref="holdingsSection">
          <PesticideHoldingsAccordion
            :items="filteredItems"
            :loading="loading"
            @select="openItem"
          />
        </div>

        <PesticideRecentUsage
          :days="recentDays"
          :loading="loading"
          @view-all="showToast(MSG_COMING_SOON)"
        />
      </template>
    </main>

    <p v-if="toastMsg" class="toast" role="status">{{ toastMsg }}</p>
    <OdsBottomNav />
  </div>
</template>

<style scoped>
.page {
  min-height: 100dvh;
  background: var(--ods-color-bg-muted);
  padding-bottom: calc(var(--ods-space-56) + env(safe-area-inset-bottom));
}
.error {
  margin: 0;
  font: var(--ods-font-form-help);
  color: var(--ods-color-danger);
}
.pest-head {
  margin: 0;
}
.pest-head__title {
  margin: 0;
  font: var(--ods-font-title-2);
  font-weight: 800;
  color: var(--ods-color-text);
}
.pest-head__sub {
  margin: var(--ods-section-title-gap) 0 0;
  font: var(--ods-font-form-help);
  color: var(--ods-color-text-secondary);
  line-height: 1.45;
}
.pest-list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-8);
}
.pest-list__row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--ods-space-12);
  padding: var(--ods-card-padding);
  border-radius: var(--ods-radius-card);
  border: 1px solid var(--ods-color-border);
  background: var(--ods-color-white);
  box-shadow: var(--ods-shadow-card);
}
.pest-list__row:active {
  background: var(--ods-color-gray-50);
}
.pest-list__main {
  min-width: 0;
  flex: 1;
}
.pest-list__nm {
  margin: 0;
  font: var(--ods-font-form-value);
  font-weight: 700;
  color: var(--ods-color-text);
}
.pest-list__meta {
  margin: var(--ods-space-4) 0 0;
  font: var(--ods-font-form-help);
  color: var(--ods-color-text-secondary);
  line-height: 1.4;
}
.pest-list__qty {
  flex-shrink: 0;
  margin: 0;
  font: var(--ods-font-card-help);
  font-weight: 700;
  color: var(--ods-color-primary);
}
.pest-list__qty--warn {
  color: var(--ods-color-danger);
}
.pest-list__empty {
  padding: var(--ods-card-padding);
  font: var(--ods-font-form-help);
  color: var(--ods-color-text-secondary);
  text-align: center;
}
.spr-links {
  display: flex;
  gap: var(--ods-space-8);
  margin: var(--ods-space-8) 0 var(--ods-space-4);
}
.spr-links :deep(.ods-btn) {
  flex: 1;
}
.toast {
  position: fixed;
  left: 50%;
  bottom: calc(var(--ods-space-64) + var(--ods-space-8) + env(safe-area-inset-bottom));
  transform: translateX(-50%);
  z-index: 60;
  margin: 0;
  padding: var(--ods-space-8) var(--ods-space-16);
  border-radius: var(--ods-radius-button);
  background: var(--ods-color-gray-900);
  color: var(--ods-color-white);
  font: var(--ods-font-card-help);
}
</style>
