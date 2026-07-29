<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'

import {
  fetchPesticideInfoDetail,
  fetchPesticideInfoList,
} from '@/api/pesticide'
import { ApiClientError } from '@/api/client'
import OdsAppBar from '@/components/ods/OdsAppBar.vue'
import OdsBadge from '@/components/ods/OdsBadge.vue'
import OdsBottomNav from '@/components/ods/OdsBottomNav.vue'
import OdsInput from '@/components/ods/OdsInput.vue'
import OdsSkeleton from '@/components/ods/OdsSkeleton.vue'
import {
  MSG_PESTICIDE_DICT_DETAIL_FAIL,
  MSG_PESTICIDE_DICT_EMPTY,
  MSG_PESTICIDE_DICT_LOAD_FAIL,
  MSG_PESTICIDE_DICT_SEARCH,
  MSG_PESTICIDE_DICT_TITLE,
  PLACEHOLDER_DASH,
} from '@/views/pesticide/pesticideConstants'
import {
  formatDilutionWithPerLiter,
  resolveDilutionUnitFromSpec,
} from '@/views/observation/scr004DetailUi'
import { useAppStore } from '@/composables/stores/app'
import type { PesticideInfoDetail, PesticideInfoSummary } from '@/types/pesticide'

const { farmCd } = storeToRefs(useAppStore())

const keyword = ref('')
const loading = ref(false)
const errorMsg = ref('')
const items = ref<PesticideInfoSummary[]>([])
const detail = ref<PesticideInfoDetail | null>(null)
const detailOpen = ref(false)
const detailLoading = ref(false)

let timer: number | undefined

async function load() {
  const farm = farmCd.value
  if (!farm) return
  loading.value = true
  errorMsg.value = ''
  try {
    const res = await fetchPesticideInfoList(farm, {
      keyword: keyword.value,
      limit: 80,
    })
    items.value = res.items
  } catch (err) {
    errorMsg.value =
      err instanceof ApiClientError ? err.message : MSG_PESTICIDE_DICT_LOAD_FAIL
    items.value = []
  } finally {
    loading.value = false
  }
}

function onKeywordInput() {
  window.clearTimeout(timer)
  timer = window.setTimeout(() => {
    void load()
  }, 280)
}

async function openDetail(infoId: number) {
  const farm = farmCd.value
  if (!farm) return
  detailOpen.value = true
  detailLoading.value = true
  detail.value = null
  try {
    detail.value = await fetchPesticideInfoDetail(farm, infoId)
  } catch (err) {
    errorMsg.value =
      err instanceof ApiClientError
        ? err.message
        : MSG_PESTICIDE_DICT_DETAIL_FAIL
    detailOpen.value = false
  } finally {
    detailLoading.value = false
  }
}

function closeDetail() {
  detailOpen.value = false
}

function dash(v: string | null | undefined) {
  return String(v || '').trim() || PLACEHOLDER_DASH
}

function listSub(it: PesticideInfoSummary) {
  const ing = dash(it.ingredient_nm)
  const cat = String(it.category_nm || '').trim()
  return cat ? `${ing} · ${cat}` : ing
}

const pestTargets = computed(() => {
  const raw = String(detail.value?.pest_target_nm || '')
  return raw
    .split(/[,，]/)
    .map((s) => s.trim())
    .filter(Boolean)
})

const dilutionDisplay = computed(() => {
  const d = detail.value
  if (!d) return PLACEHOLDER_DASH
  const unit = resolveDilutionUnitFromSpec(
    d.spec_nm,
    d.category_nm,
    d.pesticide_nm,
    d.brand_nm,
    d.usage_note,
    d.ingredient_nm,
  )
  return formatDilutionWithPerLiter(d.dilution_guide, unit)
})

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
          <h1 class="head__title">{{ MSG_PESTICIDE_DICT_TITLE }}</h1>
        </header>

        <OdsInput
          v-model="keyword"
          bare
          type="search"
          :placeholder="MSG_PESTICIDE_DICT_SEARCH"
          @input="onKeywordInput"
        />

        <p v-if="errorMsg" class="error" role="alert">{{ errorMsg }}</p>
        <OdsSkeleton v-else-if="loading" height="120px" />
        <ul v-else class="list">
          <li
            v-for="it in items"
            :key="it.info_id"
            class="list__row"
            @click="openDetail(it.info_id)"
          >
            <div class="list__top">
              <p class="list__nm">{{ it.pesticide_nm }}</p>
              <OdsBadge v-if="it.category_nm" tone="ok">{{ it.category_nm }}</OdsBadge>
            </div>
            <p class="list__sub">{{ listSub(it) }}</p>
          </li>
          <li v-if="!items.length" class="hint">{{ MSG_PESTICIDE_DICT_EMPTY }}</li>
        </ul>
      </div>
    </main>

    <div
      v-if="detailOpen"
      class="modal"
      role="dialog"
      aria-modal="true"
      :aria-label="detail?.pesticide_nm || '상세'"
      @click.self="closeDetail"
    >
      <div class="modal__card">
        <header class="modal__head">
          <div class="modal__titles">
            <h2>{{ detail?.pesticide_nm || '상세' }}</h2>
            <OdsBadge v-if="detail?.category_nm" tone="ok">
              {{ detail.category_nm }}
            </OdsBadge>
          </div>
          <button type="button" class="modal__close" @click="closeDetail">
            닫기
          </button>
        </header>

        <OdsSkeleton v-if="detailLoading" height="80px" />
        <div v-else-if="detail" class="sections">
          <section class="sec">
            <h3 class="sec__title">기본 정보</h3>
            <dl class="dl">
              <div class="dl__row dl__row--inline">
                <dt>성분명</dt>
                <dd>{{ dash(detail.ingredient_nm) }}</dd>
              </div>
              <div class="dl__row dl__row--inline">
                <dt>구분</dt>
                <dd>{{ dash(detail.category_nm) }}</dd>
              </div>
              <div class="dl__row dl__row--inline">
                <dt>제조사</dt>
                <dd>{{ dash(detail.maker_nm) }}</dd>
              </div>
              <div class="dl__row">
                <dt>대상병해충</dt>
                <dd>
                  <ul v-if="pestTargets.length" class="pest-list">
                    <li v-for="p in pestTargets" :key="p">{{ p }}</li>
                  </ul>
                  <template v-else>{{ PLACEHOLDER_DASH }}</template>
                </dd>
              </div>
            </dl>
          </section>

          <section class="sec">
            <h3 class="sec__title">사용 정보</h3>
            <dl class="dl">
              <div class="dl__row">
                <dt>희석</dt>
                <dd>{{ dilutionDisplay }}</dd>
              </div>
              <div class="dl__row">
                <dt>용법</dt>
                <dd>{{ dash(detail.usage_note) }}</dd>
              </div>
              <div class="dl__row">
                <dt>주의</dt>
                <dd>{{ dash(detail.caution_note) }}</dd>
              </div>
            </dl>
          </section>

          <section class="sec">
            <h3 class="sec__title">재고</h3>
            <dl class="dl">
              <div class="dl__row dl__row--inline">
                <dt>재고합</dt>
                <dd>{{ detail.stock_qty }}개</dd>
              </div>
            </dl>
          </section>
        </div>
      </div>
    </div>
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
.list__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ods-space-8);
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
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
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

.modal {
  position: fixed;
  inset: 0;
  z-index: 80;
  display: flex;
  align-items: flex-end;
  justify-content: center;
  padding: var(--ods-space-12);
  background: color-mix(in srgb, var(--ods-color-gray-900) 45%, transparent);
}
.modal__card {
  width: min(520px, 100%);
  max-height: 80dvh;
  overflow: auto;
  padding: var(--ods-card-padding);
  border: 1px solid var(--ods-color-border);
  border-radius: var(--ods-radius-card) var(--ods-radius-card)
    var(--ods-radius-button) var(--ods-radius-button);
  background: var(--ods-color-white);
  box-shadow: var(--ods-shadow-card);
}
.modal__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--ods-space-8);
  margin-bottom: var(--ods-form-field-gap);
  padding-bottom: var(--ods-space-12);
  border-bottom: 1px solid var(--ods-color-border);
}
.modal__titles {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--ods-space-8);
  min-width: 0;
}
.modal__head h2 {
  margin: 0;
  font: var(--ods-font-title-2);
  font-weight: 800;
  color: var(--ods-color-text);
}
.modal__close {
  flex-shrink: 0;
  min-height: var(--ods-control-height);
  margin: 0;
  padding: 0 var(--ods-space-8);
  border: 0;
  background: transparent;
  font: var(--ods-font-form-label);
  color: var(--ods-color-primary);
  cursor: pointer;
}

.sections {
  display: flex;
  flex-direction: column;
  gap: var(--ods-form-field-gap);
}
.sec__title {
  margin: 0 0 var(--ods-form-label-gap);
  font: var(--ods-font-form-label);
  color: var(--ods-color-text);
}
.dl {
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: var(--ods-form-field-gap);
}
.dl__row {
  display: flex;
  flex-direction: column;
  gap: var(--ods-form-label-gap);
}
.dl__row--inline {
  display: grid;
  grid-template-columns: 88px 1fr;
  gap: var(--ods-space-8);
  align-items: start;
}
.dl__row dt {
  margin: 0;
  font: var(--ods-font-card-section);
  color: var(--ods-color-text-secondary);
}
.dl__row dd {
  margin: 0;
  font: var(--ods-font-form-value);
  color: var(--ods-color-text);
  word-break: keep-all;
  line-height: 1.45;
}
.dl__row--inline dt {
  font: var(--ods-font-form-help);
  font-weight: 600;
}
.dl__row--inline dd {
  font: var(--ods-font-form-help);
  font-weight: 600;
}
.pest-list {
  margin: 0;
  padding: 0 0 0 var(--ods-space-16);
  list-style: disc;
}
.pest-list li {
  margin: 0;
  padding: 0;
  line-height: 1.45;
}
.pest-list li + li {
  margin-top: var(--ods-space-4);
}
</style>
