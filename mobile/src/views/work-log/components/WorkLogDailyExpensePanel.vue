<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import {
  fetchWorkLogAccountCodes,
  type WorkLogAccountCodeOption,
} from '@/api/workLogs'
import iconEdit from '@/assets/ods/scr004/icon-edit.svg'
import iconPlus from '@/assets/ods/work-log/icon-plus.svg'
import iconTrash from '@/assets/ods/scr004/icon-trash.svg'
import WorkLogDailyPickSheet from '@/views/work-log/components/WorkLogDailyPickSheet.vue'
import {
  createEmptyExpenseRow,
  EXPENSE_ACCT_LEVEL,
  EXPENSE_ACCT_PREFIX,
  MSG_EXPENSE_EMPTY,
  MSG_EXPENSE_REMOVE_CONFIRM,
  MSG_EXPENSE_REMOVE_PAID_CONFIRM,
  PAY_METHOD_ACCT_LEVEL,
  PAY_METHOD_ACCT_PREFIX,
  PLACEHOLDER_SELECT,
  type DailyShellExpenseRow,
} from '@/views/work-log/workLogConstants'

const listed = defineModel<DailyShellExpenseRow[]>({ default: () => [] })
const props = defineProps<{ workDt?: string; farmCd: string }>()
const emit = defineEmits<{
  pending: []
  /** DB에 저장된 경비(exp_id) 삭제 — 통합 저장 시 removed_exp_ids */
  removeSaved: [expId: number]
}>()

const draft = ref<DailyShellExpenseRow | null>(null)
const editingId = ref<string | null>(null)
const expenseAccts = ref<WorkLogAccountCodeOption[]>([])
const payMethods = ref<WorkLogAccountCodeOption[]>([])
type PickKind = 'expense' | 'payMethod' | 'paid' | null
const pickKind = ref<PickKind>(null)
let seq = 0

const isEditing = computed(() => editingId.value != null)

const paidOptions = [
  { value: 'Y', label: '지불' },
  { value: 'N', label: '미지불' },
]

const pickTitle = computed(() => {
  if (pickKind.value === 'expense') return '지출내용'
  if (pickKind.value === 'payMethod') return '지불방식'
  if (pickKind.value === 'paid') return '지불여부'
  return ''
})

const pickOptions = computed(() => {
  if (pickKind.value === 'expense') {
    return expenseAccts.value.map((a) => ({
      value: a.acct_cd,
      label: a.acct_nm,
    }))
  }
  if (pickKind.value === 'payMethod') {
    return payMethods.value.map((a) => ({
      value: a.acct_cd,
      label: a.acct_nm,
    }))
  }
  if (pickKind.value === 'paid') return paidOptions
  return []
})

onMounted(async () => {
  try {
    const [ex, pay] = await Promise.all([
      fetchWorkLogAccountCodes(
        props.farmCd,
        EXPENSE_ACCT_PREFIX,
        EXPENSE_ACCT_LEVEL,
      ),
      fetchWorkLogAccountCodes(
        props.farmCd,
        PAY_METHOD_ACCT_PREFIX,
        PAY_METHOD_ACCT_LEVEL,
      ),
    ])
    expenseAccts.value = ex || []
    payMethods.value = pay || []
  } catch {
    emit('pending')
  }
})

function clearDraft() {
  draft.value = null
  editingId.value = null
  pickKind.value = null
}

function onAdd() {
  if (draft.value) {
    clearDraft()
    return
  }
  seq += 1
  editingId.value = null
  draft.value = createEmptyExpenseRow(`exp-draft-${seq}`, props.workDt || '')
}

function onEditRow(row: DailyShellExpenseRow) {
  editingId.value = row.id
  draft.value = { ...row }
  pickKind.value = null
}

function paidLabel(yn: string): string {
  return yn === 'Y' ? '지불' : '미지불'
}

function openPick(kind: Exclude<PickKind, null>) {
  if (!draft.value) return
  pickKind.value = kind
}

function onPickSelect(value: string, label: string) {
  if (!draft.value || !pickKind.value) return
  if (pickKind.value === 'expense') {
    draft.value.acctCd = value
    draft.value.expenseNm = label
  } else if (pickKind.value === 'payMethod') {
    draft.value.payMethodCd = value
    draft.value.payMethod = label
  } else if (pickKind.value === 'paid') {
    draft.value.paidYn = value
  }
  pickKind.value = null
}

function confirmDraft() {
  if (!draft.value) return
  const row = { ...draft.value }
  if (!row.acctCd.trim()) {
    emit('pending')
    return
  }
  if (!row.payMethodCd.trim()) {
    emit('pending')
    return
  }
  if (editingId.value) {
    if (row.expId != null && Number(row.expId) > 0) {
      row.status = 'MOD'
    } else if (!row.status || row.status === 'ORG') {
      row.status = 'INS'
    }
    listed.value = listed.value.map((r) =>
      r.id === editingId.value ? { ...row, id: r.id } : r,
    )
  } else {
    if (!row.status) row.status = 'INS'
    listed.value = [...listed.value, row]
  }
  clearDraft()
}

function onRemoveRow(row: DailyShellExpenseRow) {
  const paid = String(row.paidYn || 'N').toUpperCase() === 'Y'
  const hasSaved = row.expId != null && Number(row.expId) > 0
  const msg =
    hasSaved && paid
      ? MSG_EXPENSE_REMOVE_PAID_CONFIRM
      : MSG_EXPENSE_REMOVE_CONFIRM
  if (!window.confirm(msg)) return
  if (editingId.value === row.id) clearDraft()
  if (hasSaved) emit('removeSaved', Number(row.expId))
  listed.value = listed.value.filter((r) => r.id !== row.id)
}
</script>

<template>
  <div class="panel">
    <ul v-if="listed.length > 0" class="list" aria-label="등록 경비">
      <li
        v-for="row in listed"
        :key="row.id"
        class="list__item"
        :class="{ 'list__item--on': editingId === row.id }"
      >
        <button
          type="button"
          class="list__body"
          :aria-label="`${row.expenseNm || '경비'} 수정`"
          @click="onEditRow(row)"
        >
          <p class="list__title">
            {{ row.expenseNm || row.acctCd || '지출내용 미입력' }}
          </p>
          <p class="list__meta">
            {{ row.occurDt || '일자 미입력' }} · {{ row.detail || '상세 없음' }} ·
            {{ row.amount }}원 · {{ row.payMethod || '지불방식 미선택' }} ·
            {{ paidLabel(row.paidYn) }}
          </p>
        </button>
        <button
          type="button"
          class="list__edit"
          :aria-label="`${row.expenseNm || '경비'} 수정`"
          @click="onEditRow(row)"
        >
          <img :src="iconEdit" alt="" />
        </button>
        <button
          type="button"
          class="list__del"
          :aria-label="`${row.expenseNm || '경비'} 삭제`"
          @click="onRemoveRow(row)"
        >
          <img :src="iconTrash" alt="" />
        </button>
      </li>
    </ul>
    <p v-else class="panel__empty">{{ MSG_EXPENSE_EMPTY }}</p>

    <button
      type="button"
      class="panel__add"
      :class="{ 'panel__add--on': !!draft && !isEditing }"
      :aria-expanded="!!draft"
      @click="onAdd"
    >
      <img :src="iconPlus" alt="" />
      {{ draft && !isEditing ? '입력 닫기' : '경비추가' }}
    </button>

    <article
      v-if="draft"
      class="row-card"
      :aria-label="isEditing ? '경비 수정' : '경비 입력'"
    >
      <p v-if="isEditing" class="row-card__badge">수정 중</p>
      <label class="field">
        <span class="field__label">발생일자</span>
        <input v-model="draft.occurDt" class="field__input" type="date" />
      </label>
      <label class="field">
        <span class="field__label">지출내용</span>
        <button
          type="button"
          class="field__select"
          @click="openPick('expense')"
        >
          <span>{{ draft.expenseNm || PLACEHOLDER_SELECT }}</span>
          <span class="field__chev">›</span>
        </button>
      </label>
      <label class="field">
        <span class="field__label">상세내역</span>
        <input
          v-model="draft.detail"
          class="field__input"
          type="text"
          maxlength="15"
        />
      </label>
      <label class="field">
        <span class="field__label">사용금액</span>
        <input
          v-model="draft.amount"
          class="field__input"
          type="text"
          inputmode="numeric"
        />
      </label>
      <label class="field">
        <span class="field__label">지불방식</span>
        <button
          type="button"
          class="field__select"
          @click="openPick('payMethod')"
        >
          <span>{{ draft.payMethod || PLACEHOLDER_SELECT }}</span>
          <span class="field__chev">›</span>
        </button>
      </label>
      <label class="field">
        <span class="field__label">지불여부</span>
        <button type="button" class="field__select" @click="openPick('paid')">
          <span>{{ paidLabel(draft.paidYn) }}</span>
          <span class="field__chev">›</span>
        </button>
      </label>
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
          {{ isEditing ? '경비 수정' : '경비 등록' }}
        </button>
      </div>
    </article>

    <WorkLogDailyPickSheet
      :open="pickKind != null"
      :title="pickTitle"
      :options="pickOptions"
      @close="pickKind = null"
      @select="onPickSelect"
    />
  </div>
</template>

<style scoped>
.panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
  max-width: 100%;
}
.panel__empty {
  margin: 0;
  font-size: 13px;
  color: #8a8074;
}
.panel__add {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-height: 40px;
  border: 1px dashed #c5b8a4;
  border-radius: 10px;
  background: #fff;
  color: #5c5348;
  font-size: 14px;
  font-weight: 600;
}
.panel__add--on {
  border-style: solid;
  background: #f7f2ea;
}
.panel__add img {
  width: 16px;
  height: 16px;
}
.panel__confirm {
  min-height: 40px;
  border: none;
  border-radius: 10px;
  background: #2e7d4f;
  color: #fff;
  font-size: 14px;
  font-weight: 600;
}
.list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
}
.list__item {
  display: flex;
  align-items: flex-start;
  gap: 4px;
  padding: 10px 8px 10px 12px;
  border-radius: 10px;
  background: #f7f2ea;
  min-width: 0;
  border: 1.5px solid transparent;
}
.list__item--on {
  border-color: #2e7d4f;
  background: #eef6f1;
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
.list__title {
  margin: 0 0 4px;
  font-size: 14px;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.list__meta {
  margin: 0;
  font-size: 12px;
  color: #6b6358;
  overflow-wrap: anywhere;
  word-break: break-word;
}
.list__edit,
.list__del {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  margin: 0;
  padding: 0;
  border: none;
  border-radius: 8px;
  background: transparent;
  cursor: pointer;
}
.list__edit img,
.list__del img {
  width: 18px;
  height: 18px;
  opacity: 0.7;
}
.row-card__badge {
  margin: 0;
  font-size: 12px;
  font-weight: 700;
  color: #2e7d4f;
}
.row-card__actions {
  display: flex;
  gap: 8px;
}
.panel__cancel-edit {
  flex: 0 0 auto;
  min-height: 40px;
  padding: 0 14px;
  border: 1px solid #c5b8a4;
  border-radius: 10px;
  background: #fff;
  color: #5c5348;
  font-size: 14px;
  font-weight: 600;
}
.row-card__actions .panel__confirm {
  flex: 1;
}
.row-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px;
  border-radius: 12px;
  background: #fff;
  border: 1px solid #e8e0d4;
  min-width: 0;
  max-width: 100%;
  box-sizing: border-box;
  overflow: hidden;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}
.field__label {
  font-size: 12px;
  color: #6b6358;
}
.field__input,
.field__select {
  box-sizing: border-box;
  width: 100%;
  max-width: 100%;
  min-height: 40px;
  padding: 0 12px;
  border: 1px solid #d9d0c3;
  border-radius: 8px;
  background: #fff;
  font-size: 14px;
  text-align: left;
}
.field__select {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.field__select span:first-child {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}
.field__chev {
  flex-shrink: 0;
  color: #a39a8c;
}
</style>
