<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'

const props = defineProps<{
  open: boolean
  /** 1차 관찰 삭제 시 함께 삭제될 2차 이상 건수 (0이면 일반 경고만) */
  relatedTrackCount?: number
}>()

const emit = defineEmits<{
  cancel: []
  confirm: []
}>()

const cancelBtn = ref<HTMLButtonElement | null>(null)

const relatedCount = computed(() => Math.max(0, Number(props.relatedTrackCount || 0)))
const hasCascade = computed(() => relatedCount.value > 0)

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
        <p
          v-if="hasCascade"
          class="dlg__cascade"
          role="alert"
        >
          이 관찰은 1차 기록입니다. 연관된 2차 이상 추적 관찰
          {{ relatedCount }}건도 모두 함께 삭제됩니다.
        </p>
        <p class="dlg__body">삭제를 진행하면 아래 정보가 모두 삭제됩니다.</p>
        <ul class="dlg__list">
          <li>관찰 기본정보</li>
          <li>관찰 내용</li>
          <li>등록한 사진 및 썸네일</li>
          <li>AI 분석 결과</li>
          <li>스마트 방제 가이드 결과</li>
          <li>첨부 데이터</li>
          <li v-if="hasCascade">2차 이상 추적 관찰 전체 (측정·사진 포함)</li>
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
  background: color-mix(in srgb, var(--ods-color-gray-900) 50%, transparent);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--ods-space-16);
}
.dlg__panel {
  width: 100%;
  max-width: min(400px, var(--ods-page-content-max, 480px));
  background: var(--ods-color-white);
  border-radius: var(--ods-radius-card);
  padding: var(--ods-card-padding, var(--ods-space-16));
  box-shadow: var(--ods-shadow-card);
  display: flex;
  flex-direction: column;
  gap: 0;
}
.dlg__title {
  margin: 0;
  font: var(--ods-font-form-label);
  color: var(--ods-color-text);
}
.dlg__lead,
.dlg__body,
.dlg__ask {
  margin: var(--ods-form-label-gap, var(--ods-space-8)) 0 0;
  font: var(--ods-font-form-help);
  color: var(--ods-color-text);
}
.dlg__cascade {
  margin: var(--ods-form-label-gap, var(--ods-space-8)) 0 0;
  padding: var(--ods-space-8);
  border-radius: var(--ods-radius-button);
  background: var(--ods-color-danger-soft);
  font: var(--ods-font-form-help);
  font-weight: 700;
  color: var(--ods-color-danger);
}
.dlg__list {
  margin: var(--ods-form-label-gap, var(--ods-space-8)) 0 0;
  padding-left: 1.2em;
  font: var(--ods-font-form-help);
  color: var(--ods-color-text-secondary);
}
.dlg__warn {
  margin: var(--ods-space-12) 0 0;
  font: var(--ods-font-form-help);
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
  min-height: var(--ods-button-height);
  border-radius: var(--ods-radius-button);
  font: var(--ods-font-form-value);
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
