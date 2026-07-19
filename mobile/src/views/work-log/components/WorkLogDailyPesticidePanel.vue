<script setup lang="ts">
import { computed, ref } from 'vue'

import iconPlus from '@/assets/ods/work-log/icon-plus.svg'
import {
  createEmptyPesticideRow,
  MSG_PESTICIDE_EMPTY,
  MSG_PESTICIDE_HINT,
  type DailyShellPesticideRow,
} from '@/views/work-log/workLogConstants'

const listed = defineModel<DailyShellPesticideRow[]>({ default: () => [] })

const props = defineProps<{
  stockAppliedYn?: string
  readOnly?: boolean
  /** 수정 모드(저장 시 교체) — 진입만으로 DB/재고 변경 없음 */
  editingReplace?: boolean
}>()

const emit = defineEmits<{
  pending: []
  cancelUse: []
  editBegin: []
}>()

const canEditLines = computed(
  () =>
    !props.readOnly &&
    (props.stockAppliedYn !== 'Y' || !!props.editingReplace),
)

const draft = ref<DailyShellPesticideRow | null>(null)
let seq = 0

function onAdd() {
  if (draft.value) {
    draft.value = null
    return
  }
  seq += 1
  draft.value = createEmptyPesticideRow(`pest-draft-${seq}`)
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
  listed.value = [...listed.value, row]
  draft.value = null
}
</script>

<template>
  <div class="panel">
    <p class="panel__hint">{{ MSG_PESTICIDE_HINT }}</p>
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
        농약 사용 취소
      </button>
    </div>

    <ul v-if="listed.length > 0" class="list" aria-label="등록 농약">
      <li v-for="row in listed" :key="row.id" class="list__item">
        <p class="list__title">{{ row.itemNm || `품목#${row.itemId}` }}</p>
        <p class="list__meta">
          {{ row.spec || '규격 —' }} · 수량 {{ row.useQty }}
          <template v-if="row.purpose"> · {{ row.purpose }}</template>
        </p>
      </li>
    </ul>
    <p v-else class="panel__empty">{{ MSG_PESTICIDE_EMPTY }}</p>

    <template v-if="canEditLines">
      <button
        type="button"
        class="panel__add"
        :class="{ 'panel__add--on': !!draft }"
        :aria-expanded="!!draft"
        @click="onAdd"
      >
        <img :src="iconPlus" alt="" />
        {{ draft ? '입력 닫기' : '농약추가' }}
      </button>

      <article v-if="draft" class="row-card" aria-label="농약 입력">
        <label class="field">
          <span class="field__label">품목ID</span>
          <input v-model.number="draft.itemId" class="field__input" type="number" />
        </label>
        <label class="field">
          <span class="field__label">농약명</span>
          <input v-model="draft.itemNm" class="field__input" type="text" />
        </label>
        <label class="field">
          <span class="field__label">규격</span>
          <input v-model="draft.spec" class="field__input" type="text" />
        </label>
        <label class="field">
          <span class="field__label">사용수량</span>
          <input v-model="draft.useQty" class="field__input" type="text" inputmode="numeric" />
        </label>
        <label class="field">
          <span class="field__label">용도</span>
          <input v-model="draft.purpose" class="field__input" type="text" />
        </label>
        <button type="button" class="panel__confirm" @click="confirmDraft">농약 등록</button>
      </article>
    </template>
  </div>
</template>

<style scoped>
.panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.panel__hint,
.panel__empty,
.panel__applied {
  margin: 0;
  font-size: 13px;
  color: #8a8074;
}
.panel__applied {
  color: #c62828;
  font-weight: 600;
}
.panel__add,
.panel__cancel,
.panel__edit,
.panel__confirm {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-height: 40px;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 600;
}
.panel__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.panel__edit {
  border: 1px solid #c5b8a4;
  background: #fff;
  color: #5c5346;
  padding: 0 14px;
}
.panel__add {
  border: 1px dashed #c5b8a4;
  background: #fff;
  color: #5c5348;
}
.panel__add--on {
  border-style: solid;
  background: #f7f2ea;
}
.panel__add img {
  width: 16px;
  height: 16px;
}
.panel__cancel {
  border: 1px solid #c62828;
  background: #fff;
  color: #c62828;
}
.panel__confirm {
  border: none;
  background: #2e7d4f;
  color: #fff;
}
.list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.list__item {
  padding: 10px 12px;
  border-radius: 10px;
  background: #f7f2ea;
}
.list__title {
  margin: 0 0 4px;
  font-size: 14px;
  font-weight: 600;
}
.list__meta {
  margin: 0;
  font-size: 12px;
  color: #6b6358;
}
.row-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px;
  border-radius: 12px;
  background: #fff;
  border: 1px solid #e8e0d4;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.field__label {
  font-size: 12px;
  color: #6b6358;
}
.field__input {
  min-height: 40px;
  padding: 0 12px;
  border: 1px solid #d9d0c3;
  border-radius: 8px;
  font-size: 14px;
}
</style>
