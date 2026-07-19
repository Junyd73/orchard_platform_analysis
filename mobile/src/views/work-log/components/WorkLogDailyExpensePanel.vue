<script setup lang="ts">
import { ref } from 'vue'

import iconPlus from '@/assets/ods/work-log/icon-plus.svg'
import {
  createEmptyExpenseRow,
  MSG_EXPENSE_EMPTY,
  type DailyShellExpenseRow,
} from '@/views/work-log/workLogConstants'

const listed = defineModel<DailyShellExpenseRow[]>({ default: () => [] })
const props = defineProps<{ workDt?: string }>()

const emit = defineEmits<{
  pending: []
}>()

const draft = ref<DailyShellExpenseRow | null>(null)
let seq = 0

function onAdd() {
  if (draft.value) {
    draft.value = null
    return
  }
  seq += 1
  draft.value = createEmptyExpenseRow(`exp-draft-${seq}`, props.workDt || '')
}

function paidLabel(yn: string): string {
  return yn === 'Y' ? '지불' : '미지불'
}

function togglePaid() {
  if (!draft.value) return
  draft.value.paidYn = draft.value.paidYn === 'Y' ? 'N' : 'Y'
}

function confirmDraft() {
  if (!draft.value) return
  const row = { ...draft.value }
  if (!row.acctCd.trim()) {
    emit('pending')
    return
  }
  if (!row.status) row.status = 'INS'
  listed.value = [...listed.value, row]
  draft.value = null
}
</script>

<template>
  <div class="panel">
    <ul v-if="listed.length > 0" class="list" aria-label="등록 경비">
      <li v-for="row in listed" :key="row.id" class="list__item">
        <p class="list__title">{{ row.expenseNm || row.acctCd || '지출내용 미입력' }}</p>
        <p class="list__meta">
          {{ row.occurDt || '일자 미입력' }} · {{ row.detail || '상세 없음' }} ·
          {{ row.amount }}원 · {{ paidLabel(row.paidYn) }}
        </p>
      </li>
    </ul>
    <p v-else class="panel__empty">{{ MSG_EXPENSE_EMPTY }}</p>

    <button
      type="button"
      class="panel__add"
      :class="{ 'panel__add--on': !!draft }"
      :aria-expanded="!!draft"
      @click="onAdd"
    >
      <img :src="iconPlus" alt="" />
      {{ draft ? '입력 닫기' : '경비추가' }}
    </button>

    <article v-if="draft" class="row-card" aria-label="경비 입력">
      <label class="field">
        <span class="field__label">발생일자</span>
        <input v-model="draft.occurDt" class="field__input" type="date" />
      </label>
      <label class="field">
        <span class="field__label">계정코드</span>
        <input
          v-model="draft.acctCd"
          class="field__input"
          type="text"
          placeholder="예: EX020201"
        />
      </label>
      <label class="field">
        <span class="field__label">지출내용명</span>
        <input v-model="draft.expenseNm" class="field__input" type="text" />
      </label>
      <label class="field">
        <span class="field__label">상세내역</span>
        <input v-model="draft.detail" class="field__input" type="text" maxlength="15" />
      </label>
      <label class="field">
        <span class="field__label">사용금액</span>
        <input v-model="draft.amount" class="field__input" type="text" inputmode="numeric" />
      </label>
      <label class="field">
        <span class="field__label">지불방식 코드</span>
        <input
          v-model="draft.payMethodCd"
          class="field__input"
          type="text"
          placeholder="예: AS010101"
        />
      </label>
      <label class="field">
        <span class="field__label">지불여부</span>
        <button type="button" class="field__select" @click="togglePaid">
          <span>{{ paidLabel(draft.paidYn) }}</span>
          <span class="field__chev">›</span>
        </button>
      </label>
      <button type="button" class="panel__confirm" @click="confirmDraft">경비 등록</button>
    </article>
  </div>
</template>

<style scoped>
.panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
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
.field__input,
.field__select {
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
}
.field__chev {
  color: #a39a8c;
}
</style>
