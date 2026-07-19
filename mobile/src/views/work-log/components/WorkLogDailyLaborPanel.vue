<script setup lang="ts">
import { ref } from 'vue'

import iconPlus from '@/assets/ods/work-log/icon-plus.svg'
import {
  createEmptyLaborRow,
  MSG_LABOR_EMPTY,
  PLACEHOLDER_SELECT,
  type DailyShellLaborRow,
} from '@/views/work-log/workLogConstants'

const listed = defineModel<DailyShellLaborRow[]>({ default: () => [] })

const emit = defineEmits<{
  pending: []
}>()

const draft = ref<DailyShellLaborRow | null>(null)
let seq = 0

function onAdd() {
  if (draft.value) {
    draft.value = null
    return
  }
  seq += 1
  draft.value = createEmptyLaborRow(`labor-draft-${seq}`)
}

function onSelectField() {
  emit('pending')
}

function paidLabel(yn: string): string {
  return yn === 'Y' ? '지급' : '미지급'
}

function togglePaid() {
  if (!draft.value) return
  draft.value.paidYn = draft.value.paidYn === 'Y' ? 'N' : 'Y'
}

function confirmDraft() {
  if (!draft.value) return
  const row = { ...draft.value }
  if (!row.empNm.trim() && !row.empCd.trim()) {
    emit('pending')
    return
  }
  if (!row.empCd) row.empCd = row.empNm.trim()
  if (!row.status) row.status = 'INS'
  listed.value = [...listed.value, row]
  draft.value = null
}
</script>

<template>
  <div class="panel">
    <ul v-if="listed.length > 0" class="list" aria-label="등록 인력">
      <li v-for="row in listed" :key="row.id" class="list__item">
        <p class="list__title">{{ row.empNm || '이름 미입력' }}</p>
        <p class="list__meta">
          {{ row.manHour }}시간 · 일당 {{ row.dayPay }} ·
          {{ row.payMethod || '지급방식 미선택' }} · {{ paidLabel(row.paidYn) }}
        </p>
      </li>
    </ul>
    <p v-else class="panel__empty">{{ MSG_LABOR_EMPTY }}</p>

    <button
      type="button"
      class="panel__add"
      :class="{ 'panel__add--on': !!draft }"
      :aria-expanded="!!draft"
      @click="onAdd"
    >
      <img :src="iconPlus" alt="" />
      {{ draft ? '입력 닫기' : '인력추가' }}
    </button>

    <article v-if="draft" class="row-card" aria-label="인력 입력">
      <label class="field">
        <span class="field__label">직원명</span>
        <input
          v-model="draft.empNm"
          class="field__input"
          type="text"
          :placeholder="PLACEHOLDER_SELECT"
          @focus="onSelectField"
        />
      </label>
      <div class="field-row">
        <label class="field">
          <span class="field__label">시간</span>
          <input v-model="draft.manHour" class="field__input" type="text" inputmode="decimal" />
        </label>
        <label class="field">
          <span class="field__label">일당</span>
          <input v-model="draft.dayPay" class="field__input" type="text" inputmode="numeric" />
        </label>
      </div>
      <label class="field">
        <span class="field__label">지급방식 코드</span>
        <input
          v-model="draft.payMethodCd"
          class="field__input"
          type="text"
          placeholder="예: AS010101"
        />
      </label>
      <label class="field">
        <span class="field__label">지급여부</span>
        <button type="button" class="field__select" @click="togglePaid">
          <span>{{ paidLabel(draft.paidYn) }}</span>
          <span class="field__chev">›</span>
        </button>
      </label>
      <button type="button" class="panel__confirm" @click="confirmDraft">인력 등록</button>
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
  color: #2c2822;
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
.field-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
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
