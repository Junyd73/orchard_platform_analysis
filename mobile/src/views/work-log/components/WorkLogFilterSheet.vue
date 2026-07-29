<script setup lang="ts">
import {
  WORK_FILTER_OPTIONS,
  type WorkFilterKey,
} from '@/views/work-log/workLogConstants'

defineProps<{
  open: boolean
  filters: Record<WorkFilterKey, boolean>
}>()

const emit = defineEmits<{
  close: []
  toggle: [key: WorkFilterKey]
  reset: []
}>()
</script>

<template>
  <div
    v-if="open"
    class="sheet"
    role="dialog"
    aria-modal="true"
    aria-label="작업필터"
  >
    <button type="button" class="sheet__backdrop" aria-label="닫기" @click="emit('close')" />
    <div class="sheet__panel">
      <p class="sheet__title">작업필터</p>
      <p class="sheet__desc">여러 항목을 선택할 수 있습니다. (기본: 전체)</p>
      <ul class="sheet__list">
        <li v-for="opt in WORK_FILTER_OPTIONS" :key="opt.key">
          <label class="sheet__row">
            <input
              type="checkbox"
              :checked="filters[opt.key]"
              @change="emit('toggle', opt.key)"
            />
            <span>{{ opt.label }}</span>
          </label>
        </li>
      </ul>
      <div class="sheet__actions">
        <button type="button" class="sheet__btn" @click="emit('reset')">전체 선택</button>
        <button type="button" class="sheet__btn sheet__btn--primary" @click="emit('close')">
          적용
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.sheet {
  position: fixed;
  inset: 0;
  z-index: 60;
  display: flex;
  align-items: flex-end;
  justify-content: center;
}
.sheet__backdrop {
  position: absolute;
  inset: 0;
  border: none;
  background: color-mix(in srgb, black 45%, transparent);
  cursor: pointer;
}
.sheet__panel {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: var(--ods-page-content-max);
  background: var(--ods-color-white);
  border-radius: var(--ods-radius-card) var(--ods-radius-card) 0 0;
  padding: var(--ods-space-16) var(--ods-space-16)
    calc(var(--ods-space-16) + env(safe-area-inset-bottom));
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-8);
}
.sheet__title {
  margin: 0;
  font: var(--ods-font-headline);
  font-weight: 700;
}
.sheet__desc {
  margin: 0;
  font: var(--ods-font-form-help);
  color: var(--ods-color-text-secondary);
}
.sheet__list {
  list-style: none;
  margin: var(--ods-space-8) 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-4);
}
.sheet__row {
  display: flex;
  align-items: center;
  gap: var(--ods-space-12);
  min-height: var(--ods-control-height);
  font: var(--ods-font-body-1);
  cursor: pointer;
}
.sheet__row input {
  width: 20px;
  height: 20px;
  accent-color: var(--ods-color-primary);
}
.sheet__actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--ods-space-8);
  margin-top: var(--ods-space-8);
}
.sheet__btn {
  min-height: var(--ods-control-height);
  border: 1px solid var(--ods-color-border);
  border-radius: var(--ods-radius-button);
  background: var(--ods-color-gray-100);
  font: var(--ods-font-headline);
  cursor: pointer;
}
.sheet__btn--primary {
  background: var(--ods-color-primary);
  border-color: var(--ods-color-primary);
  color: var(--ods-color-white);
}
</style>
