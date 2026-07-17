<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'

const props = defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  cancel: []
  confirm: []
}>()

const cancelBtn = ref<HTMLButtonElement | null>(null)

watch(
  () => props.open,
  async (open) => {
    if (!open) return
    await nextTick()
    cancelBtn.value?.focus()
  },
)
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="dlg"
      role="dialog"
      aria-modal="true"
      aria-labelledby="obs-del-title"
      @keydown.esc.prevent="emit('cancel')"
    >
      <div class="dlg__panel">
        <h2 id="obs-del-title" class="dlg__title">관찰 기록 삭제</h2>
        <p class="dlg__lead">선택한 관찰 기록을 삭제하시겠습니까?</p>
        <p class="dlg__body">삭제를 진행하면 아래 정보가 모두 삭제됩니다.</p>
        <ul class="dlg__list">
          <li>관찰 기본정보</li>
          <li>관찰 내용</li>
          <li>등록한 사진 및 썸네일</li>
          <li>AI 분석 결과</li>
          <li>스마트 방제 가이드 결과</li>
          <li>첨부 데이터</li>
        </ul>
        <p class="dlg__warn">삭제된 데이터는 복구할 수 없습니다.</p>
        <p class="dlg__ask">계속하시겠습니까?</p>
        <div class="dlg__actions">
          <button
            ref="cancelBtn"
            type="button"
            class="dlg__btn dlg__btn--cancel"
            @click="emit('cancel')"
          >
            취소
          </button>
          <button
            type="button"
            class="dlg__btn dlg__btn--danger"
            @click="emit('confirm')"
          >
            삭제
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.dlg {
  position: fixed;
  inset: 0;
  z-index: 80;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--ods-space-16);
}
.dlg__panel {
  width: 100%;
  max-width: 400px;
  background: var(--ods-color-white);
  border-radius: var(--ods-radius-card);
  padding: var(--ods-space-16);
  box-shadow: var(--ods-shadow-card);
}
.dlg__title {
  margin: 0;
  font: var(--ods-font-headline);
  color: var(--ods-color-text);
}
.dlg__lead,
.dlg__body,
.dlg__ask {
  margin: var(--ods-space-8) 0 0;
  font: var(--ods-font-body-2);
  color: var(--ods-color-text);
}
.dlg__list {
  margin: var(--ods-space-8) 0 0;
  padding-left: 1.2em;
  font: var(--ods-font-body-2);
  color: var(--ods-color-text-secondary);
}
.dlg__warn {
  margin: var(--ods-space-12) 0 0;
  font: var(--ods-font-body-2);
  font-weight: 700;
  color: var(--ods-color-danger);
}
.dlg__actions {
  display: flex;
  gap: var(--ods-space-8);
  margin-top: var(--ods-space-16);
}
.dlg__btn {
  flex: 1;
  min-height: 48px;
  border-radius: var(--ods-radius-button);
  font: var(--ods-font-body-1);
  font-weight: 700;
  cursor: pointer;
  border: 1px solid var(--ods-color-border);
  background: var(--ods-color-white);
}
.dlg__btn--cancel {
  color: var(--ods-color-text);
}
.dlg__btn--danger {
  background: var(--ods-color-danger);
  border-color: var(--ods-color-danger);
  color: var(--ods-color-white);
}
</style>
