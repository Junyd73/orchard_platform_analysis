<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'

import {
  deletePesticideItem,
  fetchPesticideStockList,
  issuePesticideStockOut,
  updatePesticideItem,
} from '@/api/pesticide'
import { ApiClientError } from '@/api/client'
import OdsAppBar from '@/components/ods/OdsAppBar.vue'
import OdsBottomNav from '@/components/ods/OdsBottomNav.vue'
import OdsButton from '@/components/ods/OdsButton.vue'
import OdsCard from '@/components/ods/OdsCard.vue'
import OdsInput from '@/components/ods/OdsInput.vue'
import OdsSkeleton from '@/components/ods/OdsSkeleton.vue'
import {
  HOLDINGS_CATEGORIES,
  holdingsCategoryKeyOf,
  isStockQtyWarn,
  LABEL_STOCK_OUT,
  LABEL_STOCK_OUT_BUYER,
  LABEL_STOCK_OUT_QTY,
  LABEL_STOCK_OUT_RMK,
  MSG_STOCK_OUT_CONFIRM,
  PLACEHOLDER_SEARCH,
  type HoldingsCategoryKey,
} from '@/views/pesticide/pesticideConstants'
import { useAppStore } from '@/composables/stores/app'
import type { PesticideStockItem } from '@/types/pesticide'

const router = useRouter()
const route = useRoute()
const { farmCd } = storeToRefs(useAppStore())

const loading = ref(true)
const errorMsg = ref('')
const toastMsg = ref('')
const items = ref<PesticideStockItem[]>([])
const keyword = ref('')
const editing = ref<PesticideStockItem | null>(null)
/** 품목수정 | 출고(판매) */
const modalMode = ref<'edit' | 'out'>('edit')
const form = ref({
  item_nm: '',
  spec_nm: '',
  pest_category_nm: '',
  qty_piece: 0,
  warn_piece_below: null as number | null,
  rmk: '',
})
const outForm = ref({
  qty: 1,
  buyer_nm: '',
  rmk: '',
})
const savingOut = ref(false)

const openMap = ref<Record<HoldingsCategoryKey, boolean>>(
  Object.fromEntries(
    HOLDINGS_CATEGORIES.map((c) => [c.key, c.defaultOpen]),
  ) as Record<HoldingsCategoryKey, boolean>,
)

/** 스마트방제 CTA: 해당 병해충 대상만 */
const pestFilter = computed(() => String(route.query.pest_nm || '').trim())

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

const filtered = computed(() => {
  let rows = items.value
  const pest = pestFilter.value
  if (pest) {
    rows = rows.filter((it) => matchesPestTarget(it.pest_target_nm, pest))
  }
  const q = keyword.value.trim().toLowerCase()
  if (!q) return rows
  return rows.filter((it) => {
    const blob =
      `${it.item_nm} ${it.spec_nm || ''} ${it.ingredient_nm || ''} ${it.pest_target_nm || ''}`.toLowerCase()
    return blob.includes(q)
  })
})

/** 살충제 → 살균제 → 영양제 → 기타제 그룹 (빈 그룹도 표시) */
const groupedList = computed(() => {
  const map: Record<HoldingsCategoryKey, PesticideStockItem[]> = {
    insect: [],
    fungus: [],
    nutrient: [],
    other: [],
  }
  for (const it of filtered.value) {
    map[holdingsCategoryKeyOf(it.pest_category_nm)].push(it)
  }
  for (const cat of HOLDINGS_CATEGORIES) {
    map[cat.key].sort((a, b) => a.item_nm.localeCompare(b.item_nm, 'ko'))
  }
  return HOLDINGS_CATEGORIES.map((cat) => ({
    key: cat.key,
    label: cat.label,
    tone: cat.tone,
    items: map[cat.key],
  }))
})

const hasAnyItem = computed(() =>
  groupedList.value.some((g) => g.items.length > 0),
)

const pageTitle = computed(() =>
  pestFilter.value ? `${pestFilter.value} 농약재고` : '재고 관리',
)

const categoryOptions = HOLDINGS_CATEGORIES.map((c) => c.label).concat(['전착제', ''])

function toggle(key: HoldingsCategoryKey) {
  openMap.value = { ...openMap.value, [key]: !openMap.value[key] }
}

function expandGroupsWithItems() {
  const next = { ...openMap.value }
  for (const g of groupedList.value) {
    next[g.key] = g.items.length > 0
  }
  openMap.value = next
}

/** 검색·병해충 필터 시 결과 있는 그룹만 자동 펼침 */
watch([keyword, pestFilter], () => {
  if (keyword.value.trim() || pestFilter.value) {
    expandGroupsWithItems()
  }
})

function showToast(msg: string) {
  toastMsg.value = msg
  window.setTimeout(() => {
    if (toastMsg.value === msg) toastMsg.value = ''
  }, 2200)
}

async function load() {
  const farm = farmCd.value
  if (!farm) return
  loading.value = true
  errorMsg.value = ''
  try {
    const res = await fetchPesticideStockList(farm, { sort: 'name' })
    items.value = res.items
    if (pestFilter.value) expandGroupsWithItems()
  } catch (err) {
    errorMsg.value =
      err instanceof ApiClientError ? err.message : '재고를 불러오지 못했습니다.'
    items.value = []
  } finally {
    loading.value = false
  }
}

function closeModal() {
  editing.value = null
  modalMode.value = 'edit'
}

function openEdit(it: PesticideStockItem) {
  editing.value = it
  modalMode.value = 'edit'
  form.value = {
    item_nm: it.item_nm,
    spec_nm: it.spec_nm || '',
    pest_category_nm: it.pest_category_nm || '',
    qty_piece: it.qty_piece,
    warn_piece_below: it.warn_piece_below,
    rmk: '',
  }
}

function openOut() {
  const it = editing.value
  if (!it) return
  modalMode.value = 'out'
  outForm.value = {
    qty: Math.min(1, Math.max(0, it.qty_piece)) || 1,
    buyer_nm: '',
    rmk: '',
  }
}

async function saveEdit() {
  const farm = farmCd.value
  const it = editing.value
  if (!farm || !it) return
  try {
    await updatePesticideItem(farm, it.item_id, {
      item_nm: form.value.item_nm,
      spec_nm: form.value.spec_nm,
      pest_category_nm: form.value.pest_category_nm,
      qty_piece: form.value.qty_piece,
      warn_piece_below: form.value.warn_piece_below,
      rmk: form.value.rmk,
      info_id: it.info_id,
    })
    showToast('저장되었습니다.')
    closeModal()
    await load()
  } catch (err) {
    showToast(err instanceof ApiClientError ? err.message : '저장 실패')
  }
}

async function submitOut() {
  const farm = farmCd.value
  const it = editing.value
  if (!farm || !it || savingOut.value) return
  const qty = Math.trunc(Number(outForm.value.qty) || 0)
  if (qty <= 0) {
    showToast('출고 수량을 입력해 주세요.')
    return
  }
  if (qty > it.qty_piece) {
    showToast(`재고가 부족합니다. (현재 ${it.qty_piece})`)
    return
  }
  if (!outForm.value.buyer_nm.trim() && !outForm.value.rmk.trim()) {
    showToast('구매처 또는 비고를 입력해 주세요.')
    return
  }
  if (!window.confirm(MSG_STOCK_OUT_CONFIRM)) return
  savingOut.value = true
  try {
    const res = await issuePesticideStockOut(farm, it.item_id, {
      qty,
      buyer_nm: outForm.value.buyer_nm.trim(),
      rmk: outForm.value.rmk.trim(),
    })
    showToast(res.message || '출고되었습니다.')
    closeModal()
    await load()
  } catch (err) {
    showToast(err instanceof ApiClientError ? err.message : '출고 실패')
  } finally {
    savingOut.value = false
  }
}

async function removeItem(it: PesticideStockItem) {
  const farm = farmCd.value
  if (!farm) return
  if (!window.confirm(`「${it.item_nm}」을(를) 삭제할까요?`)) return
  try {
    await deletePesticideItem(farm, it.item_id)
    showToast('삭제되었습니다.')
    closeModal()
    await load()
  } catch (err) {
    showToast(err instanceof ApiClientError ? err.message : '삭제 실패')
  }
}

function openHist(it: PesticideStockItem) {
  closeModal()
  void router.push({
    name: 'pesticide-stock-hist',
    params: { itemId: String(it.item_id) },
  })
}

watch(farmCd, () => {
  void load()
})

watch(pestFilter, () => {
  keyword.value = ''
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
        <h1 class="title">{{ pageTitle }}</h1>
        <OdsButton
          v-if="!pestFilter"
          variant="secondary"
          :block="false"
          type="button"
          class="head__cta"
          @click="router.push({ name: 'pesticide-receipts' })"
        >
          입고등록
        </OdsButton>
      </header>
      <OdsCard v-if="pestFilter" class="note-card">
        「{{ pestFilter }}」 대상 농약만 표시합니다.
      </OdsCard>
      <OdsCard v-else class="note-card">
        품목 추가는 입고등록에서 합니다. 행을 눌러 수정·이력을 봅니다.
      </OdsCard>
      <OdsInput
        v-if="!pestFilter"
        v-model="keyword"
        bare
        type="search"
        :placeholder="PLACEHOLDER_SEARCH"
      />
      <p v-if="errorMsg" class="error" role="alert">{{ errorMsg }}</p>
      <OdsSkeleton v-else-if="loading" height="160px" />
      <template v-else>
        <p v-if="!hasAnyItem" class="hint">
          {{
            pestFilter
              ? '해당 병해충 대상 농약재고가 없습니다.'
              : '품목이 없습니다.'
          }}
        </p>
        <div v-else class="acc">
          <div
            v-for="g in groupedList"
            v-show="!pestFilter || g.items.length"
            :key="g.key"
            class="acc__panel"
          >
            <button
              type="button"
              class="acc__head"
              :style="{ borderLeftColor: g.tone }"
              :aria-expanded="openMap[g.key]"
              @click="toggle(g.key)"
            >
              <span class="acc__title" :style="{ color: g.tone }">
                {{ g.label }}
                <span class="acc__count">{{ g.items.length }}</span>
              </span>
              <span
                class="acc__chev"
                :class="{ 'acc__chev--open': openMap[g.key] }"
                aria-hidden="true"
              >›</span>
            </button>
            <ul v-show="openMap[g.key]" class="list">
              <li v-if="!g.items.length" class="hint hint--sm">해당 분류 품목 없음</li>
              <li
                v-for="it in g.items"
                :key="it.item_id"
                class="list__row"
                @click="openEdit(it)"
              >
                <div>
                  <p
                    class="list__nm"
                    :class="{ 'list__nm--warn': isStockQtyWarn(it.qty_piece) }"
                  >
                    {{ it.item_nm }}
                  </p>
                  <p class="list__sub">{{ it.pest_target_nm || '—' }}</p>
                </div>
                <div class="list__right">
                  <p class="list__qty">{{ it.qty_piece }}</p>
                  <button
                    type="button"
                    class="mini"
                    @click.stop="openHist(it)"
                  >
                    이력
                  </button>
                </div>
              </li>
            </ul>
          </div>
        </div>
      </template>
    </main>

    <div
      v-if="editing"
      class="modal"
      role="dialog"
      aria-modal="true"
      @click.self="closeModal"
    >
      <div class="modal__card">
        <header class="modal__head">
          <h2>{{ modalMode === 'out' ? LABEL_STOCK_OUT : '품목 수정' }}</h2>
          <button type="button" class="link" @click="closeModal">닫기</button>
        </header>

        <template v-if="modalMode === 'out'">
          <p class="modal__stock">
            {{ editing.item_nm }} · 현재고 {{ editing.qty_piece }}
          </p>
          <label class="field">
            <span>{{ LABEL_STOCK_OUT_QTY }}</span>
            <input
              v-model.number="outForm.qty"
              type="number"
              min="1"
              :max="editing.qty_piece"
              inputmode="numeric"
            />
          </label>
          <label class="field">
            <span>{{ LABEL_STOCK_OUT_BUYER }}</span>
            <input
              v-model="outForm.buyer_nm"
              type="text"
              placeholder="예: A농가"
            />
          </label>
          <label class="field">
            <span>{{ LABEL_STOCK_OUT_RMK }}</span>
            <input
              v-model="outForm.rmk"
              type="text"
              placeholder="단가·사유 등"
            />
          </label>
          <div class="actions">
            <OdsButton type="button" :busy="savingOut" @click="submitOut">
              {{ savingOut ? '처리 중…' : '출고 반영' }}
            </OdsButton>
            <OdsButton
              type="button"
              variant="secondary"
              @click="modalMode = 'edit'"
            >
              뒤로
            </OdsButton>
          </div>
        </template>

        <template v-else>
          <label class="field"
            ><span>품목명</span
            ><input v-model="form.item_nm" type="text"
          /></label>
          <label class="field"
            ><span>규격</span
            ><input v-model="form.spec_nm" type="text"
          /></label>
          <label class="field"
            ><span>구분</span>
            <select v-model="form.pest_category_nm">
              <option v-for="c in categoryOptions" :key="c || 'empty'" :value="c">
                {{ c || '(미지정)' }}
              </option>
            </select>
          </label>
          <label class="field"
            ><span>재고(낱개)</span
            ><input v-model.number="form.qty_piece" type="number" min="0"
          /></label>
          <label class="field"
            ><span>부족경고</span
            ><input
              v-model.number="form.warn_piece_below"
              type="number"
              min="0"
              placeholder="비우면 기본값"
          /></label>
          <div class="actions">
            <OdsButton type="button" @click="saveEdit">저장</OdsButton>
            <OdsButton
              type="button"
              variant="secondary"
              :disabled="editing.qty_piece <= 0"
              @click="openOut"
            >
              {{ LABEL_STOCK_OUT }}
            </OdsButton>
            <OdsButton
              type="button"
              variant="secondary"
              @click="editing && openHist(editing)"
            >
              변동이력
            </OdsButton>
            <OdsButton
              type="button"
              variant="danger"
              @click="editing && removeItem(editing)"
            >
              삭제
            </OdsButton>
          </div>
        </template>
      </div>
    </div>

    <p v-if="toastMsg" class="toast" role="status">{{ toastMsg }}</p>
    <OdsBottomNav />
  </div>
</template>

<style scoped>
.page {
  min-height: 100dvh;
  background: var(--ods-color-bg-muted);
  padding-bottom: calc(var(--ods-space-64) + var(--ods-space-8) + env(safe-area-inset-bottom));
}
.head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--ods-space-12);
}
.head__cta {
  flex-shrink: 0;
  min-height: var(--ods-button-height-in-card);
  padding: 0 var(--ods-space-12);
  font: var(--ods-font-card-help);
}
.note-card {
  margin: var(--ods-space-8) 0;
  font: var(--ods-font-form-help);
  color: var(--ods-color-text-secondary);
  line-height: 1.45;
}
.title {
  margin: 0;
  font: var(--ods-font-title-2);
  font-weight: 800;
}
.note {
  margin: var(--ods-space-8) 0 var(--ods-space-12);
  font: var(--ods-font-card-section);
  color: var(--ods-color-text-secondary);
}
.search {
  width: 100%;
  box-sizing: border-box;
  height: var(--ods-control-height);
  min-height: var(--ods-control-height);
  margin-bottom: var(--ods-space-12);
  padding: 0 var(--ods-space-12);
  border-radius: var(--ods-radius-button);
  border: 1px solid var(--ods-color-border);
  background: var(--ods-color-white);
  font: var(--ods-font-form-value);
  color: var(--ods-color-text);
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
  padding: 0 var(--ods-space-12);
  border: none;
  border-left: 3px solid transparent;
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
  letter-spacing: -0.01em;
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
  color: inherit;
  background: color-mix(in srgb, currentColor 14%, var(--ods-color-white));
  opacity: 0.9;
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
.list {
  margin: 0;
  padding: 0;
  list-style: none;
}
.list__row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: var(--ods-space-12);
  padding: var(--ods-space-12) var(--ods-space-16);
  border-top: 1px solid var(--ods-color-border);
  cursor: pointer;
}
.list__row > div:first-child {
  min-width: 0;
  flex: 1;
}
.list__nm {
  margin: 0;
  font-weight: 800;
}
.list__nm--warn {
  color: var(--ods-color-danger);
}
.list__sub {
  margin: var(--ods-space-4) 0 0;
  font: var(--ods-font-card-section);
  color: var(--ods-color-text-secondary);
  line-height: 1.35;
  word-break: keep-all;
}
.list__right {
  flex: 0 0 auto;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: var(--ods-space-8);
  min-width: var(--ods-space-48);
}
.list__qty {
  margin: 0;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
}
.mini {
  box-sizing: border-box;
  min-width: var(--ods-space-48);
  border: 1px solid var(--ods-color-border);
  background: var(--ods-color-white);
  border-radius: var(--ods-radius-button);
  padding: var(--ods-space-4) var(--ods-space-8);
  font: var(--ods-font-card-meta);
  font-weight: 700;
  line-height: 1.2;
  white-space: nowrap;
  cursor: pointer;
}
.link {
  border: none;
  background: transparent;
  color: var(--ods-color-primary);
  font-weight: 700;
  cursor: pointer;
}
.modal {
  position: fixed;
  inset: 0;
  z-index: 80;
  background: color-mix(in srgb, var(--ods-color-gray-900) 45%, transparent);
  display: flex;
  align-items: flex-end;
  justify-content: center;
  padding: var(--ods-space-12);
}
.modal__card {
  width: min(520px, 100%);
  max-height: 85dvh;
  overflow: auto;
  background: var(--ods-color-white);
  border: 1px solid var(--ods-color-border);
  border-radius: var(--ods-radius-card);
  box-shadow: var(--ods-shadow-card);
  padding: var(--ods-space-16);
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-12);
}
.modal__head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.modal__head h2 {
  margin: 0;
  font: var(--ods-font-title-2);
}
.modal__stock {
  margin: 0;
  font: var(--ods-font-form-help);
  font-weight: 700;
  color: var(--ods-color-text);
}
.field {
  display: flex;
  flex-direction: column;
  gap: var(--ods-form-label-gap);
  font: var(--ods-font-form-label);
  color: var(--ods-color-text-label, var(--ods-color-text));
}
.field input,
.field select {
  height: var(--ods-control-height);
  min-height: var(--ods-control-height);
  border-radius: var(--ods-radius-button);
  border: 1px solid var(--ods-color-border);
  padding: 0 var(--ods-space-12);
  background: var(--ods-color-white);
  font: var(--ods-font-form-value);
  color: var(--ods-color-text);
}
.actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--ods-space-8);
}
.btn {
  min-height: var(--ods-button-height);
  padding: 0 var(--ods-space-16);
  border: none;
  border-radius: var(--ods-radius-button);
  background: var(--ods-color-primary);
  color: var(--ods-color-white);
  font: var(--ods-font-form-label);
  cursor: pointer;
}
.btn--sec {
  background: var(--ods-color-text);
}
.btn--out {
  background: var(--ods-color-ai);
}
.btn--out:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
.btn--danger {
  background: var(--ods-color-danger);
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
  border-top: 1px solid var(--ods-color-border);
}
.error {
  color: var(--ods-color-danger);
}
.toast {
  position: fixed;
  left: 50%;
  bottom: calc(var(--ods-space-64) + var(--ods-space-8) + env(safe-area-inset-bottom));
  transform: translateX(-50%);
  z-index: 90;
  margin: 0;
  padding: var(--ods-space-8) var(--ods-space-16);
  border-radius: var(--ods-radius-badge);
  background: var(--ods-color-gray-900);
  color: var(--ods-color-white);
  font: var(--ods-font-card-section);
}
</style>
