<script setup lang="ts">
import { computed, ref } from 'vue'

import iconPlus from '@/assets/ods/work-log/icon-plus.svg'
import {
  MSG_WORK_PHOTO_EMPTY,
  MSG_WORK_PHOTO_LIMIT,
  WORK_PHOTO_MAX_COUNT,
} from '@/views/work-log/workLogConstants'

const emit = defineEmits<{
  pending: []
}>()

/** Shell: 업로드 전 슬롯 수 (실제 파일 없음) */
const photoCount = ref(0)

const canAdd = computed(() => photoCount.value < WORK_PHOTO_MAX_COUNT)
const slots = computed(() =>
  Array.from({ length: photoCount.value }, (_, i) => i + 1),
)

function onAdd() {
  if (!canAdd.value) {
    emit('pending')
    return
  }
  photoCount.value += 1
}

function onSlotClick() {
  emit('pending')
}
</script>

<template>
  <div class="panel">
    <div class="panel__head">
      <h3 class="panel__title">작업 결과 사진</h3>
      <span class="panel__count">{{ photoCount }}/{{ WORK_PHOTO_MAX_COUNT }}</span>
    </div>
    <p class="panel__hint">{{ MSG_WORK_PHOTO_LIMIT }}</p>

    <p v-if="photoCount === 0" class="panel__empty">{{ MSG_WORK_PHOTO_EMPTY }}</p>

    <div class="grid" aria-label="작업 사진">
      <button
        v-for="n in slots"
        :key="n"
        type="button"
        class="grid__slot"
        @click="onSlotClick"
      >
        <span class="grid__label">사진 {{ n }}</span>
      </button>
      <button
        v-if="canAdd"
        type="button"
        class="grid__slot grid__slot--add"
        @click="onAdd"
      >
        <img :src="iconPlus" alt="" />
        <span>추가</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.panel {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-12);
}
.panel__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.panel__title {
  margin: 0;
  font: var(--ods-font-body-2);
  font-weight: 700;
  color: var(--ods-color-text);
}
.panel__count {
  font: var(--ods-font-caption);
  font-weight: 700;
  color: var(--ods-color-primary);
}
.panel__hint {
  margin: 0;
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
}
.panel__empty {
  margin: 0;
  padding: var(--ods-space-12);
  text-align: center;
  font: var(--ods-font-body-2);
  color: var(--ods-color-text-secondary);
  background: var(--ods-color-bg-muted);
  border-radius: var(--ods-radius-button);
}
.grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--ods-space-8);
}
.grid__slot {
  aspect-ratio: 1;
  margin: 0;
  padding: 0;
  border: 1px dashed var(--ods-color-border);
  border-radius: 10px;
  background: var(--ods-color-bg-muted);
  display: grid;
  place-items: center;
  gap: 4px;
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
  cursor: pointer;
}
.grid__slot--add {
  border-style: solid;
  border-color: var(--ods-color-primary);
  color: var(--ods-color-primary);
  font-weight: 700;
}
.grid__slot--add img {
  width: 16px;
  height: 16px;
}
.grid__label {
  font-weight: 700;
}
</style>
