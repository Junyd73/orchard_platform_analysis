<script setup lang="ts">
import { ref, watch } from 'vue'

import { reopenAuctionShipment } from '@/api/auctionShipments'
import OdsButton from '@/components/ods/OdsButton.vue'
import OdsInput from '@/components/ods/OdsInput.vue'
import {
  auctionReopenUserMessage,
  isReopenNotFoundError,
  isReopenStatusConflictError,
  MSG_AUCTION_REOPEN_CONFIRM,
} from '@/views/stock/auctionMatchModel'

const props = defineProps<{
  open: boolean
  farmCd: string
  shipmentId: string
}>()

const emit = defineEmits<{
  close: []
  success: []
  settled: []
  statusConflict: []
  notFound: []
}>()

const remark = ref('')
const submitBusy = ref(false)
const submitError = ref('')

function resetForm() {
  remark.value = ''
  submitError.value = ''
  submitBusy.value = false
}

watch(
  () => [props.open, props.shipmentId] as const,
  ([isOpen]) => {
    if (!isOpen) {
      resetForm()
    }
  },
)

function closeIfIdle() {
  if (submitBusy.value) return
  emit('close')
}

async function submitReopen() {
  if (submitBusy.value || !props.farmCd || !props.shipmentId) return
  submitBusy.value = true
  submitError.value = ''
  try {
    await reopenAuctionShipment(props.farmCd, props.shipmentId, {
      remark: remark.value,
    })
    emit('success')
  } catch (err) {
    submitError.value = auctionReopenUserMessage(err)
    emit('settled')
    if (isReopenNotFoundError(err)) {
      emit('notFound')
      emit('close')
    } else if (isReopenStatusConflictError(err)) {
      emit('statusConflict')
      emit('close')
    }
  } finally {
    submitBusy.value = false
  }
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="auc-sheet"
      role="dialog"
      aria-modal="true"
      aria-labelledby="auction-reopen-title"
      data-testid="auction-reopen-sheet"
    >
      <button
        type="button"
        class="auc-sheet__backdrop"
        aria-label="닫기"
        :disabled="submitBusy"
        @click="closeIfIdle"
      />
      <div class="auc-sheet__panel">
        <p id="auction-reopen-title" class="auc-sheet__title">경락매칭 정정</p>
        <p class="auc-sheet__lead" data-testid="auction-reopen-confirm-text">
          {{ MSG_AUCTION_REOPEN_CONFIRM }}
        </p>
        <div class="auc-sheet__field">
          <label class="auc-sheet__lbl" for="auction-reopen-remark">정정 메모 (선택)</label>
          <OdsInput
            id="auction-reopen-remark"
            :model-value="remark"
            variant="form"
            :disabled="submitBusy"
            data-testid="auction-reopen-remark"
            @update:model-value="remark = String($event || '')"
          />
        </div>
        <p v-if="submitError" class="auc-sheet__err" role="alert" data-testid="auction-reopen-error">
          {{ submitError }}
        </p>
        <div class="auc-sheet__actions">
          <OdsButton
            type="button"
            variant="secondary"
            :block="false"
            :disabled="submitBusy"
            data-testid="auction-reopen-cancel"
            @click="closeIfIdle"
          >
            취소
          </OdsButton>
          <OdsButton
            type="button"
            :block="false"
            :disabled="submitBusy"
            :busy="submitBusy"
            data-testid="auction-reopen-submit"
            @click="submitReopen"
          >
            확인
          </OdsButton>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.auc-sheet {
  position: fixed;
  inset: 0;
  z-index: 60;
  display: flex;
  align-items: flex-end;
  justify-content: center;
}
.auc-sheet__backdrop {
  position: absolute;
  inset: 0;
  border: none;
  background: color-mix(in srgb, black 45%, transparent);
  cursor: pointer;
}
.auc-sheet__panel {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: var(--ods-page-content-max);
  background: var(--ods-color-white);
  border-radius: var(--ods-radius-card) var(--ods-radius-card) 0 0;
  padding: var(--ods-space-16);
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-12);
}
.auc-sheet__title {
  margin: 0;
  font: var(--ods-font-headline);
  font-weight: 700;
}
.auc-sheet__lead {
  margin: 0;
  font: var(--ods-font-body-2);
  color: var(--ods-color-text);
  line-height: 1.5;
  white-space: pre-wrap;
}
.auc-sheet__field {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-6);
}
.auc-sheet__lbl {
  font: var(--ods-font-form-label, var(--ods-font-body-2));
  font-weight: 700;
}
.auc-sheet__err {
  margin: 0;
  font: var(--ods-font-footnote);
  color: var(--ods-color-danger);
}
.auc-sheet__actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--ods-space-8);
}
</style>
