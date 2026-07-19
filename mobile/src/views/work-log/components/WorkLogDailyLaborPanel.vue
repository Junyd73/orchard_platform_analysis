<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import {
  fetchWorkLogAccountCodes,
  fetchWorkLogPartners,
  type WorkLogAccountCodeOption,
  type WorkLogPartnerOption,
} from '@/api/workLogs'
import iconEdit from '@/assets/ods/scr004/icon-edit.svg'
import iconPlus from '@/assets/ods/work-log/icon-plus.svg'
import iconTrash from '@/assets/ods/scr004/icon-trash.svg'
import WorkLogDailyPickSheet from '@/views/work-log/components/WorkLogDailyPickSheet.vue'
import {
  createEmptyLaborRow,
  MSG_LABOR_EMPTY,
  MSG_LABOR_REMOVE_CONFIRM,
  MSG_LABOR_REMOVE_PAID_CONFIRM,
  PAY_METHOD_ACCT_LEVEL,
  PAY_METHOD_ACCT_PREFIX,
  PLACEHOLDER_SELECT,
  type DailyShellLaborRow,
} from '@/views/work-log/workLogConstants'

const listed = defineModel<DailyShellLaborRow[]>({ default: () => [] })
const props = defineProps<{ farmCd: string }>()
const emit = defineEmits<{
  pending: []
  /** DB에 저장된 인력(res_id) 삭제 — 통합 저장 시 removed_res_ids */
  removeSaved: [resId: number]
}>()

const draft = ref<DailyShellLaborRow | null>(null)
/** 수정 중인 목록 행 id (null이면 신규 추가) */
const editingId = ref<string | null>(null)
const partners = ref<WorkLogPartnerOption[]>([])
const payMethods = ref<WorkLogAccountCodeOption[]>([])
type PickKind = 'emp' | 'payMethod' | 'paid' | null
const pickKind = ref<PickKind>(null)
let seq = 0

const isEditing = computed(() => editingId.value != null)

const paidOptions = [
  { value: 'Y', label: '지급' },
  { value: 'N', label: '미지급' },
]

const pickTitle = computed(() => {
  if (pickKind.value === 'emp') return '직원명'
  if (pickKind.value === 'payMethod') return '지급방식'
  if (pickKind.value === 'paid') return '지급여부'
  return ''
})

const pickOptions = computed(() => {
  if (pickKind.value === 'emp') {
    return partners.value.map((p) => ({
      value: String(p.pt_id),
      label: p.pt_nm,
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
    const [p, a] = await Promise.all([
      fetchWorkLogPartners(props.farmCd),
      fetchWorkLogAccountCodes(
        props.farmCd,
        PAY_METHOD_ACCT_PREFIX,
        PAY_METHOD_ACCT_LEVEL,
      ),
    ])
    partners.value = p || []
    payMethods.value = a || []
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
  draft.value = createEmptyLaborRow(`labor-draft-${seq}`)
}

function onEditRow(row: DailyShellLaborRow) {
  editingId.value = row.id
  draft.value = { ...row }
  pickKind.value = null
}

function paidLabel(yn: string): string {
  return yn === 'Y' ? '지급' : '미지급'
}

function openPick(kind: Exclude<PickKind, null>) {
  if (!draft.value) return
  pickKind.value = kind
}

function onPickSelect(value: string, label: string) {
  if (!draft.value || !pickKind.value) return
  if (pickKind.value === 'emp') {
    draft.value.empCd = value
    draft.value.empNm = label
    const partner = partners.value.find((p) => String(p.pt_id) === value)
    if (partner?.base_price != null && Number(partner.base_price) > 0) {
      draft.value.dayPay = String(Math.round(Number(partner.base_price)))
    }
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
  if (!row.empCd.trim() || !row.empNm.trim()) {
    emit('pending')
    return
  }
  if (!row.payMethodCd.trim()) {
    emit('pending')
    return
  }
  if (editingId.value) {
    // 기존 행 수정: DB 건은 MOD, 미저장 신규는 INS 유지
    if (row.resId != null && Number(row.resId) > 0) {
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

function onRemoveRow(row: DailyShellLaborRow) {
  const paid = String(row.paidYn || 'N').toUpperCase() === 'Y'
  const hasSaved = row.resId != null && Number(row.resId) > 0
  const msg =
    hasSaved && paid
      ? MSG_LABOR_REMOVE_PAID_CONFIRM
      : MSG_LABOR_REMOVE_CONFIRM
  if (!window.confirm(msg)) return
  if (editingId.value === row.id) clearDraft()
  if (hasSaved) emit('removeSaved', Number(row.resId))
  listed.value = listed.value.filter((r) => r.id !== row.id)
}
</script>

<template>
  <div class="panel">
    <ul v-if="listed.length > 0" class="list" aria-label="등록 인력">
      <li
        v-for="row in listed"
        :key="row.id"
        class="list__item"
        :class="{ 'list__item--on': editingId === row.id }"
      >
        <button
          type="button"
          class="list__body"
          :aria-label="`${row.empNm || '인력'} 수정`"
          @click="onEditRow(row)"
        >
          <p class="list__title">{{ row.empNm || '이름 미입력' }}</p>
          <p class="list__meta">
            {{ row.manHour }}시간 · 일당 {{ row.dayPay }} ·
            {{ row.payMethod || '지급방식 미선택' }} · {{ paidLabel(row.paidYn) }}
          </p>
        </button>
        <button
          type="button"
          class="list__edit"
          :aria-label="`${row.empNm || '인력'} 수정`"
          @click="onEditRow(row)"
        >
          <img :src="iconEdit" alt="" />
        </button>
        <button
          type="button"
          class="list__del"
          :aria-label="`${row.empNm || '인력'} 삭제`"
          @click="onRemoveRow(row)"
        >
          <img :src="iconTrash" alt="" />
        </button>
      </li>
    </ul>
    <p v-else class="panel__empty">{{ MSG_LABOR_EMPTY }}</p>

    <button
      type="button"
      class="panel__add"
      :class="{ 'panel__add--on': !!draft && !isEditing }"
      :aria-expanded="!!draft"
      @click="onAdd"
    >
      <img :src="iconPlus" alt="" />
      {{ draft && !isEditing ? '입력 닫기' : '인력추가' }}
    </button>

    <article
      v-if="draft"
      class="row-card"
      :aria-label="isEditing ? '인력 수정' : '인력 입력'"
    >
      <p v-if="isEditing" class="row-card__badge">수정 중</p>
      <label class="field">
        <span class="field__label">직원명</span>
        <button type="button" class="field__select" @click="openPick('emp')">
          <span>{{ draft.empNm || PLACEHOLDER_SELECT }}</span>
          <span class="field__chev">›</span>
        </button>
      </label>
      <div class="field-row">
        <label class="field">
          <span class="field__label">시간</span>
          <input
            v-model="draft.manHour"
            class="field__input"
            type="text"
            inputmode="decimal"
          />
        </label>
        <label class="field">
          <span class="field__label">일당</span>
          <input
            v-model="draft.dayPay"
            class="field__input"
            type="text"
            inputmode="numeric"
          />
        </label>
      </div>
      <label class="field">
        <span class="field__label">지급방식</span>
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
        <span class="field__label">지급여부</span>
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
          {{ isEditing ? '인력 수정' : '인력 등록' }}
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
  color: #2c2822;
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
.field-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 8px;
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
