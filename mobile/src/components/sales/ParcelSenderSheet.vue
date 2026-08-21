<script setup lang="ts">
import { ref, watch } from 'vue'

import OdsButton from '@/components/ods/OdsButton.vue'
import OdsFormField from '@/components/ods/OdsFormField.vue'
import OdsInput from '@/components/ods/OdsInput.vue'
import OdsSelect from '@/components/ods/OdsSelect.vue'
import {
  MSG_NEED_SENDER,
  MSG_NEED_SENDER_ADDR,
  formatPhoneKr,
} from '@/views/orders/ordersConstants'

const LABEL_SENDER = '보내는 사람'
const LABEL_SENDER_TEL = '전화번호'
const LABEL_SENDER_SHEET = '보내는 사람 설정'
const LABEL_SENDER_HINT = '판매 전체 공통 적용'
const LABEL_SENDER_APPLY = '전체 적용'
const LABEL_SENDER_ADDR = '주소'
const LABEL_SENDER_ADDR_ORCHARD = '과수원 주소'
const LABEL_SENDER_ADDR_CUSTOM = '직접 입력'
const SENDER_ADDR_ORCHARD = 'orchard'
const SENDER_ADDR_CUSTOM = 'custom'
const SENDER_ADDR_OPTIONS = [
  { value: SENDER_ADDR_ORCHARD, label: LABEL_SENDER_ADDR_ORCHARD },
  { value: SENDER_ADDR_CUSTOM, label: LABEL_SENDER_ADDR_CUSTOM },
] as const
const DEFAULT_TEST_PREFIX = 'sales-preview'

const props = withDefaults(
  defineProps<{
    open: boolean
    senderName: string
    senderTel: string
    senderAddr: string
    farmAddress?: string
    testIdPrefix?: string
  }>(),
  {
    farmAddress: '',
    testIdPrefix: DEFAULT_TEST_PREFIX,
  },
)

const emit = defineEmits<{
  close: []
  save: [{ name: string; tel: string; addr: string }]
}>()

const draftName = ref('')
const draftTel = ref('')
const draftAddr = ref('')
const addrMode = ref<typeof SENDER_ADDR_ORCHARD | typeof SENDER_ADDR_CUSTOM>(SENDER_ADDR_ORCHARD)
const sheetErr = ref('')

function tidOf(suffix: string): string {
  return `${props.testIdPrefix || DEFAULT_TEST_PREFIX}-${suffix}`
}

/** 저장값이 과수원 주소와 같으면 과수원 모드, 그 외 직접 입력 */
function resetFromProps() {
  draftName.value = String(props.senderName || '')
  draftTel.value = String(props.senderTel || '')
  const farmAddr = String(props.farmAddress || '').trim()
  const saved = String(props.senderAddr || '').trim()
  if (saved && farmAddr && saved === farmAddr) {
    addrMode.value = SENDER_ADDR_ORCHARD
    draftAddr.value = farmAddr
  } else if (saved) {
    addrMode.value = SENDER_ADDR_CUSTOM
    draftAddr.value = saved
  } else if (farmAddr) {
    addrMode.value = SENDER_ADDR_ORCHARD
    draftAddr.value = farmAddr
  } else {
    addrMode.value = SENDER_ADDR_CUSTOM
    draftAddr.value = ''
  }
  sheetErr.value = ''
}

watch(
  () => props.open,
  (isOpen) => {
    if (isOpen) resetFromProps()
  },
  { immediate: true },
)

function closeSheet() {
  sheetErr.value = ''
  emit('close')
}

function onTelInput(raw: string) {
  draftTel.value = formatPhoneKr(raw)
}

function onAddrMode(raw: string) {
  const mode = String(raw) === SENDER_ADDR_CUSTOM ? SENDER_ADDR_CUSTOM : SENDER_ADDR_ORCHARD
  addrMode.value = mode
  if (mode !== SENDER_ADDR_ORCHARD) return
  const farmAddr = String(props.farmAddress || '').trim()
  if (!farmAddr) {
    addrMode.value = SENDER_ADDR_CUSTOM
    sheetErr.value = MSG_NEED_SENDER_ADDR
    return
  }
  draftAddr.value = farmAddr
  sheetErr.value = ''
}

function onAddrInput(raw: string) {
  draftAddr.value = String(raw || '')
  if (sheetErr.value) sheetErr.value = ''
}

function commit() {
  const name = String(draftName.value || '').trim()
  const tel = formatPhoneKr(draftTel.value).trim()
  const addr = String(draftAddr.value || '').trim()
  if (!name || !tel || !addr) {
    sheetErr.value = MSG_NEED_SENDER
    return
  }
  sheetErr.value = ''
  emit('save', { name, tel, addr })
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="dest-overlay"
      role="dialog"
      aria-modal="true"
      :aria-label="LABEL_SENDER_SHEET"
      :data-testid="tidOf('sender-sheet')"
      @click.self="closeSheet"
    >
      <div class="dest-sheet dest-sheet--sender">
        <header class="dest-sheet__head">
          <div class="dest-sheet__head-main">
            <div class="dest-sheet__title-row">
              <h3 class="dest-sheet__title">{{ LABEL_SENDER_SHEET }}</h3>
              <button
                type="button"
                class="dest-sheet__x"
                aria-label="닫기"
                :data-testid="tidOf('sender-close')"
                @click="closeSheet"
              >
                ✕
              </button>
            </div>
            <p class="dest-sheet__sender-hint">{{ LABEL_SENDER_HINT }}</p>
          </div>
        </header>

        <div class="dest-sheet__body">
          <OdsFormField :label="LABEL_SENDER">
            <OdsInput
              :model-value="draftName"
              variant="form"
              bare
              :data-testid="tidOf('sender-name')"
              :aria-label="LABEL_SENDER"
              @update:model-value="draftName = String($event)"
            />
          </OdsFormField>
          <OdsFormField :label="LABEL_SENDER_TEL">
            <OdsInput
              :model-value="draftTel"
              variant="form"
              bare
              inputmode="tel"
              :data-testid="tidOf('sender-tel')"
              :aria-label="LABEL_SENDER_TEL"
              @update:model-value="onTelInput(String($event))"
            />
          </OdsFormField>
          <OdsFormField :label="LABEL_SENDER_ADDR">
            <div class="sender-addr-row" :data-testid="tidOf('sender-addr-row')">
              <OdsSelect
                :model-value="addrMode"
                variant="form"
                class="sender-addr-row__mode"
                :data-testid="tidOf('sender-addr-mode')"
                :aria-label="LABEL_SENDER_ADDR"
                @update:model-value="onAddrMode(String($event))"
              >
                <option v-for="opt in SENDER_ADDR_OPTIONS" :key="opt.value" :value="opt.value">
                  {{ opt.label }}
                </option>
              </OdsSelect>
              <OdsInput
                :model-value="draftAddr"
                variant="form"
                bare
                class="sender-addr-row__input"
                :data-testid="tidOf('sender-addr')"
                :aria-label="LABEL_SENDER_ADDR"
                :placeholder="
                  addrMode === SENDER_ADDR_ORCHARD
                    ? LABEL_SENDER_ADDR_ORCHARD
                    : LABEL_SENDER_ADDR_CUSTOM
                "
                @update:model-value="onAddrInput(String($event))"
              />
            </div>
          </OdsFormField>
          <p v-if="sheetErr" class="dest-sheet__err" role="alert" :data-testid="tidOf('sender-err')">
            {{ sheetErr }}
          </p>
        </div>

        <footer class="dest-sheet__foot">
          <OdsButton
            type="button"
            class="dest-sheet__cta"
            :data-testid="tidOf('sender-apply')"
            @click.stop="commit"
          >
            {{ LABEL_SENDER_APPLY }}
          </OdsButton>
        </footer>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.dest-overlay {
  position: fixed;
  inset: 0;
  z-index: 200;
  background: rgba(0, 0, 0, 0.35);
  display: flex;
  align-items: flex-end;
  justify-content: center;
}
.dest-sheet {
  width: min(100%, var(--ods-page-content-max, 480px));
  max-height: min(88vh, 720px);
  background: var(--ods-color-bg, #fdfbf7);
  border-radius: 16px 16px 0 0;
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
  overflow: hidden;
}
.dest-sheet__head {
  padding: var(--ods-space-12) var(--ods-space-16);
  border-bottom: 1px solid var(--ods-color-border);
}
.dest-sheet__head-main {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-8);
  min-width: 0;
  width: 100%;
}
.dest-sheet__title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ods-space-8);
  min-width: 0;
}
.dest-sheet__title {
  margin: 0;
  font: var(--ods-font-title-3);
  font-weight: 700;
}
.dest-sheet__x {
  border: none;
  background: transparent;
  font-size: 18px;
  cursor: pointer;
  color: var(--ods-color-text-secondary);
  flex-shrink: 0;
  line-height: 1;
  padding: var(--ods-space-4);
}
.dest-sheet__sender-hint {
  margin: var(--ods-space-4) 0 0;
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
}
.dest-sheet__body {
  overflow-y: auto;
  padding: var(--ods-space-12) var(--ods-space-16);
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-8);
  min-width: 0;
}
.sender-addr-row {
  display: grid;
  grid-template-columns: minmax(5.5rem, 6.75rem) minmax(0, 1fr);
  gap: var(--ods-space-4);
  align-items: center;
  min-width: 0;
}
.sender-addr-row__mode {
  width: 100%;
  min-width: 0;
  height: 36px;
  min-height: 36px;
  max-height: 36px;
  font: var(--ods-font-caption);
  font-weight: 600;
  padding-inline: var(--ods-space-4);
  box-sizing: border-box;
}
.sender-addr-row__input {
  min-width: 0;
  width: 100%;
}
.dest-sheet--sender .sender-addr-row :deep(input.ods-input),
.dest-sheet--sender .sender-addr-row :deep(.sender-addr-row__input.ods-input) {
  height: 36px;
  min-height: 36px;
  padding: 0 var(--ods-space-8);
  box-sizing: border-box;
}
.dest-sheet__err {
  margin: 0;
  color: var(--ods-color-danger, #b00020);
  font: var(--ods-font-footnote, 12px);
}
.dest-sheet__cta {
  width: 100%;
  min-height: 44px;
}
.dest-sheet__foot {
  padding: var(--ods-space-12) var(--ods-space-16)
    calc(var(--ods-space-12) + env(safe-area-inset-bottom, 0px));
  border-top: 1px solid var(--ods-color-border);
}
</style>
