<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import {
  fetchWorkLogPesticideItems,
  type WorkLogPesticideItemOption,
  type WorkLogStockItemKind,
} from '@/api/workLogs'
import iconEdit from '@/assets/ods/scr004/icon-edit.svg'
import iconPlus from '@/assets/ods/work-log/icon-plus.svg'
import iconTrash from '@/assets/ods/scr004/icon-trash.svg'
import WorkLogDailyPickSheet from '@/views/work-log/components/WorkLogDailyPickSheet.vue'
import {
  loadRecentPurposes,
  MSG_STOCK_LINK,
  PLACEHOLDER_PURPOSE,
} from '@/views/pesticide/pesticideConstants'
import {
  availablePesticideQty,
  createEmptyPesticideRow,
  MSG_FERTILIZER_EMPTY,
  MSG_FERTILIZER_HINT,
  MSG_FERTILIZER_NOT_TARGET,
  MSG_FERTILIZER_REMOVE_CONFIRM,
  MSG_PESTICIDE_EMPTY,
  MSG_PESTICIDE_HINT,
  MSG_PESTICIDE_NOT_TARGET,
  MSG_PESTICIDE_REMOVE_CONFIRM,
  msgPesticideStockShort,
  PLACEHOLDER_SELECT,
  type DailyShellPesticideRow,
} from '@/views/work-log/workLogConstants'

const listed = defineModel<DailyShellPesticideRow[]>({ default: () => [] })

const props = withDefaults(
  defineProps<{
    farmCd: string
    /** pesticide | fertilizer — 품목 필터·문구 */
    mode?: WorkLogStockItemKind
    /**
     * 방제/약제살포 또는 비료작업일 때만 빈문구·추가 노출.
     * null=미지정 → isPesticideWork 폴백 (Boolean 미전달 시 false 캐스팅 회피)
     */
    isTargetWork?: boolean | null
    /** @deprecated isTargetWork 사용 */
    isPesticideWork?: boolean
    stockAppliedYn?: string
    readOnly?: boolean
    editingReplace?: boolean
    /** 재고 보기 링크 (홈 간략등록 모달 등에서는 숨김) */
    showStockLink?: boolean
  }>(),
  {
    mode: 'pesticide',
    isTargetWork: null,
    // Boolean prop 미전달 시 Vue가 false로 캐스팅하므로 기본 true
    isPesticideWork: true,
    showStockLink: true,
  },
)

const emit = defineEmits<{
  pending: [message?: string]
  cancelUse: []
  editBegin: []
}>()

const router = useRouter()

const isFertMode = computed(() => props.mode === 'fertilizer')
const itemLabel = computed(() => (isFertMode.value ? '비료' : '농약'))
const hintText = computed(() =>
  isFertMode.value ? MSG_FERTILIZER_HINT : MSG_PESTICIDE_HINT,
)
const emptyText = computed(() =>
  isFertMode.value ? MSG_FERTILIZER_EMPTY : MSG_PESTICIDE_EMPTY,
)
const notTargetText = computed(() =>
  isFertMode.value ? MSG_FERTILIZER_NOT_TARGET : MSG_PESTICIDE_NOT_TARGET,
)
const removeConfirmText = computed(() =>
  isFertMode.value
    ? MSG_FERTILIZER_REMOVE_CONFIRM
    : MSG_PESTICIDE_REMOVE_CONFIRM,
)

const isPestTarget = computed(() => {
  if (props.isTargetWork != null) return props.isTargetWork !== false
  return props.isPesticideWork !== false
})

const canEditLines = computed(
  () =>
    isPestTarget.value &&
    !props.readOnly &&
    (props.stockAppliedYn !== 'Y' || !!props.editingReplace),
)

const draft = ref<DailyShellPesticideRow | null>(null)
/** 수정 중인 목록 행 id (null이면 신규 추가) */
const editingId = ref<string | null>(null)
const items = ref<WorkLogPesticideItemOption[]>([])
const pickOpen = ref(false)
let seq = 0

const isEditing = computed(() => editingId.value != null)

/** 확정(재고 차감) 건을 화면에서 수정 중이면 목록 수량을 가용 재고에 환원 */
const stockCommitted = computed(
  () => props.stockAppliedYn === 'Y' || !!props.editingReplace,
)

const itemOptions = computed(() =>
  items.value.map((it) => ({
    value: String(it.item_id),
    label: it.spec_nm
      ? `${it.item_nm} (${it.spec_nm}) · 재고 ${it.qty_piece}`
      : `${it.item_nm} · 재고 ${it.qty_piece}`,
  })),
)

const recentPurposes = computed(() => loadRecentPurposes(props.farmCd))

function goStock() {
  void router.push({ name: 'pesticide' })
}

function applyPurpose(purpose: string) {
  if (draft.value) draft.value.purpose = purpose
}

async function loadItems() {
  try {
    items.value =
      (await fetchWorkLogPesticideItems(
        props.farmCd,
        props.mode || 'pesticide',
      )) || []
  } catch {
    emit('pending')
  }
}

onMounted(() => {
  void loadItems()
})

watch(
  () => [props.farmCd, props.mode] as const,
  () => {
    void loadItems()
  },
)

function clearDraft() {
  draft.value = null
  editingId.value = null
  pickOpen.value = false
}

function onAdd() {
  if (draft.value) {
    clearDraft()
    return
  }
  seq += 1
  editingId.value = null
  draft.value = createEmptyPesticideRow(`${props.mode || 'pest'}-draft-${seq}`)
}

function onEditRow(row: DailyShellPesticideRow) {
  if (!canEditLines.value) return
  editingId.value = row.id
  draft.value = { ...row }
  pickOpen.value = false
}

function onRemoveRow(row: DailyShellPesticideRow) {
  if (!canEditLines.value) return
  if (!window.confirm(removeConfirmText.value)) return
  if (editingId.value === row.id) clearDraft()
  listed.value = listed.value.filter((r) => r.id !== row.id)
}

function onPickItem(value: string, _label: string) {
  if (!draft.value) return
  const it = items.value.find((x) => String(x.item_id) === value)
  if (!it) {
    pickOpen.value = false
    return
  }
  draft.value.itemId = it.item_id
  draft.value.itemNm = it.item_nm
  draft.value.spec = it.spec_nm || ''
  pickOpen.value = false
}

function confirmDraft() {
  if (!draft.value) return
  const row = { ...draft.value }
  const qty = Number(row.useQty || 0)
  const iid = Number(row.itemId || 0)
  if (!iid || qty <= 0) {
    emit('pending')
    return
  }
  const catalog = items.value.find((x) => Number(x.item_id) === iid)
  if (!catalog) {
    emit('pending', `선택한 ${itemLabel.value} 품목을 찾을 수 없습니다.`)
    return
  }
  const available = availablePesticideQty({
    stockQty: Number(catalog.qty_piece || 0),
    listed: listed.value,
    itemId: iid,
    editingId: editingId.value,
    stockCommitted: stockCommitted.value,
  })
  if (qty > available) {
    emit(
      'pending',
      msgPesticideStockShort(
        row.itemNm || catalog.item_nm,
        available,
        qty,
        itemLabel.value,
      ),
    )
    return
  }
  if (editingId.value) {
    listed.value = listed.value.map((r) =>
      r.id === editingId.value ? { ...row, id: r.id } : r,
    )
  } else {
    listed.value = [...listed.value, row]
  }
  clearDraft()
}
</script>

<template>
  <div class="panel">
    <template v-if="!isPestTarget">
      <p class="panel__empty">{{ notTargetText }}</p>
    </template>
    <template v-else>
      <div class="panel__top">
        <p class="panel__hint">{{ hintText }}</p>
        <button
          v-if="showStockLink"
          type="button"
          class="panel__stock"
          @click="goStock"
        >
          {{ MSG_STOCK_LINK }}
        </button>
      </div>
      <p v-if="stockAppliedYn === 'Y' && !editingReplace" class="panel__applied">
        재고 확정됨 — 「수정」은 저장 시에만 반영됩니다. 「사용 취소」는 즉시 복원합니다.
      </p>
      <p v-else-if="editingReplace" class="panel__applied">
        수정 모드 — 저장 시 기존 사용 취소·복원 후 신규 확정됩니다.
      </p>
      <div v-if="stockAppliedYn === 'Y'" class="panel__actions">
        <button
          v-if="!editingReplace"
          type="button"
          class="panel__edit"
          @click="emit('editBegin')"
        >
          수정
        </button>
        <button
          type="button"
          class="panel__cancel"
          @click="emit('cancelUse')"
        >
          {{ itemLabel }} 사용 취소
        </button>
      </div>

      <ul v-if="listed.length > 0" class="list" :aria-label="`등록 ${itemLabel}`">
        <li
          v-for="row in listed"
          :key="row.id"
          class="list__item"
          :class="{ 'list__item--on': editingId === row.id }"
        >
          <button
            type="button"
            class="list__body"
            :aria-label="`${row.itemNm || itemLabel} 수정`"
            :disabled="!canEditLines"
            @click="onEditRow(row)"
          >
            <p class="list__title">{{ row.itemNm || `품목#${row.itemId}` }}</p>
            <p class="list__meta">
              {{ row.spec || '규격 —' }} · 수량 {{ row.useQty }}
              <template v-if="row.purpose"> · {{ row.purpose }}</template>
            </p>
          </button>
          <template v-if="canEditLines">
            <button
              type="button"
              class="list__edit"
              :aria-label="`${row.itemNm || itemLabel} 수정`"
              @click="onEditRow(row)"
            >
              <img :src="iconEdit" alt="" />
            </button>
            <button
              type="button"
              class="list__del"
              :aria-label="`${row.itemNm || itemLabel} 삭제`"
              @click="onRemoveRow(row)"
            >
              <img :src="iconTrash" alt="" />
            </button>
          </template>
        </li>
      </ul>
      <p v-else class="panel__empty">{{ emptyText }}</p>

      <template v-if="canEditLines">
        <button
          type="button"
          class="panel__add"
          :class="{ 'panel__add--on': !!draft && !isEditing }"
          :aria-expanded="!!draft"
          @click="onAdd"
        >
          <img :src="iconPlus" alt="" />
          {{ draft && !isEditing ? '입력 닫기' : `${itemLabel}추가` }}
        </button>

        <article
          v-if="draft"
          class="row-card"
          :aria-label="isEditing ? `${itemLabel} 수정` : `${itemLabel} 입력`"
        >
          <p v-if="isEditing" class="row-card__badge">수정 중</p>
          <label class="field">
            <span class="field__label">{{ itemLabel }}명</span>
            <button type="button" class="field__select" @click="pickOpen = true">
              <span>{{ draft.itemNm || PLACEHOLDER_SELECT }}</span>
              <span class="field__chev">›</span>
            </button>
          </label>
          <label class="field">
            <span class="field__label">규격</span>
            <input
              class="field__input field__input--ro"
              type="text"
              :value="draft.spec || '—'"
              readonly
              tabindex="-1"
            />
          </label>
          <label class="field">
            <span class="field__label">사용수량</span>
            <input
              v-model="draft.useQty"
              class="field__input"
              type="text"
              inputmode="numeric"
            />
          </label>
          <label class="field">
            <span class="field__label">용도</span>
            <input
              v-model="draft.purpose"
              class="field__input"
              type="text"
              :placeholder="PLACEHOLDER_PURPOSE"
            />
          </label>
          <div v-if="recentPurposes.length" class="purpose-chips">
            <button
              v-for="p in recentPurposes"
              :key="p"
              type="button"
              class="purpose-chips__btn"
              @click="applyPurpose(p)"
            >
              {{ p }}
            </button>
          </div>
          <div class="row-card__actions">
            <button
              v-if="isEditing"
              type="button"
              class="panel__cancel-edit"
              @click="clearDraft"
            >
              취소
            </button>
            <button type="button" class="panel__confirm" @click="confirmDraft">
              {{ isEditing ? `${itemLabel} 수정` : `${itemLabel} 등록` }}
            </button>
          </div>
        </article>
      </template>

      <WorkLogDailyPickSheet
        :open="pickOpen"
        :title="`${itemLabel} 품목`"
        :options="itemOptions"
        @close="pickOpen = false"
        @select="onPickItem"
      />
    </template>
  </div>
</template>

<style scoped>
.panel {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-12);
  min-width: 0;
  max-width: 100%;
}
.panel__top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--ods-space-8);
}
.panel__stock {
  flex-shrink: 0;
  border: none;
  background: transparent;
  padding: 0;
  min-height: var(--ods-hit-sm);
  font: var(--ods-font-form-help);
  font-weight: 700;
  color: var(--ods-color-primary);
  cursor: pointer;
}
.purpose-chips {
  display: flex;
  flex-wrap: wrap;
  gap: var(--ods-space-8);
}
.purpose-chips__btn {
  border: 1px solid var(--ods-color-border);
  border-radius: var(--ods-radius-badge);
  background: var(--ods-color-white);
  padding: var(--ods-space-4) var(--ods-space-8);
  font: var(--ods-font-card-section);
  color: var(--ods-color-text);
  cursor: pointer;
}
.panel__hint,
.panel__empty,
.panel__applied {
  margin: 0;
  font: var(--ods-font-form-help);
  color: var(--ods-color-text-secondary);
  overflow-wrap: anywhere;
}
.panel__applied {
  color: var(--ods-color-danger);
  font-weight: 600;
}
.panel__add,
.panel__cancel,
.panel__edit,
.panel__confirm,
.panel__cancel-edit {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--ods-space-8);
  min-height: var(--ods-button-height-in-card);
  border-radius: var(--ods-radius-button);
  font: var(--ods-font-form-value);
  font-weight: 600;
}
.panel__actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--ods-space-8);
}
.panel__edit {
  border: 1px solid var(--ods-color-border);
  background: var(--ods-color-white);
  color: var(--ods-color-text);
  padding: 0 var(--ods-space-12);
}
.panel__add {
  border: 1px dashed var(--ods-color-border);
  background: var(--ods-color-white);
  color: var(--ods-color-text);
}
.panel__add--on {
  border-style: solid;
  background: var(--ods-color-gray-100);
}
.panel__add img {
  width: var(--ods-icon-md);
  height: var(--ods-icon-md);
}
.panel__cancel {
  border: 1px solid var(--ods-color-danger);
  background: var(--ods-color-white);
  color: var(--ods-color-danger);
}
.panel__cancel-edit {
  flex: 1;
  border: 1px solid var(--ods-color-border);
  background: var(--ods-color-white);
  color: var(--ods-color-text);
}
.panel__confirm {
  flex: 1;
  border: none;
  background: var(--ods-color-primary);
  color: var(--ods-color-white);
}
.list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-8);
  min-width: 0;
}
.list__item {
  display: flex;
  align-items: flex-start;
  gap: var(--ods-space-4);
  padding: var(--ods-space-8) var(--ods-space-8) var(--ods-space-8) var(--ods-space-12);
  border-radius: var(--ods-radius-button);
  background: var(--ods-color-gray-100);
  min-width: 0;
  border: 2px solid transparent;
}
.list__item--on {
  border-color: var(--ods-color-primary);
  background: color-mix(in srgb, var(--ods-color-primary) 8%, white);
}
.list__body {
  flex: 1;
  min-width: 0;
  margin: 0;
  padding: 0;
  border: none;
  background: transparent;
  text-align: left;
  cursor: pointer;
}
.list__body:disabled {
  cursor: default;
}
.list__title {
  margin: 0 0 var(--ods-space-4);
  font: var(--ods-font-form-value);
  font-weight: 600;
  color: var(--ods-color-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.list__meta {
  margin: 0;
  font: var(--ods-font-card-section);
  color: var(--ods-color-text-secondary);
  overflow-wrap: anywhere;
  word-break: break-word;
}
.list__edit,
.list__del {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: var(--ods-button-height-in-card);
  height: var(--ods-button-height-in-card);
  margin: 0;
  padding: 0;
  border: none;
  border-radius: var(--ods-radius-button);
  background: transparent;
  cursor: pointer;
}
.list__edit img,
.list__del img {
  width: var(--ods-icon-lg);
  height: var(--ods-icon-lg);
  opacity: 0.7;
}
.row-card {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-12);
  padding: var(--ods-space-12);
  border-radius: var(--ods-radius-button);
  background: var(--ods-color-white);
  border: 1px solid var(--ods-color-border);
  min-width: 0;
  max-width: 100%;
  box-sizing: border-box;
  overflow: hidden;
}
.row-card__badge {
  margin: 0;
  font: var(--ods-font-card-section);
  font-weight: 700;
  color: var(--ods-color-primary);
}
.row-card__actions {
  display: flex;
  gap: var(--ods-space-8);
}
.field {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-4);
  min-width: 0;
}
.field__label {
  font: var(--ods-font-form-label);
  color: var(--ods-color-text-label, var(--ods-color-text));
}
.field__input,
.field__select {
  box-sizing: border-box;
  width: 100%;
  max-width: 100%;
  height: var(--ods-control-height);
  min-height: var(--ods-control-height);
  padding: 0 var(--ods-space-12);
  border: 1px solid var(--ods-color-border);
  border-radius: var(--ods-radius-button);
  background: var(--ods-color-white);
  font: var(--ods-font-form-value);
  color: var(--ods-color-text);
  text-align: left;
}
.field__input--ro {
  background: var(--ods-color-gray-100);
  color: var(--ods-color-text-secondary);
}
.field__select {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ods-space-8);
}
.field__select span:first-child {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}
.field__chev {
  flex-shrink: 0;
  color: var(--ods-color-gray-500);
}
</style>
