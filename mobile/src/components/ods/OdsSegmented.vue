<script setup lang="ts">
/**
 * ODS Segmented Control (compact) — 보조 선택 컨트롤.
 * 주 액션(OdsButton)과 시각 위계를 구분한다.
 */
export type OdsSegmentOption = {
  value: string
  label: string
}

withDefaults(
  defineProps<{
    modelValue: string
    options: OdsSegmentOption[]
    disabled?: boolean
    ariaLabel?: string
  }>(),
  {
    disabled: false,
    ariaLabel: undefined,
  },
)

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

function select(value: string) {
  emit('update:modelValue', value)
}
</script>

<template>
  <div
    class="ods-segmented"
    role="group"
    :aria-label="ariaLabel"
  >
    <button
      v-for="opt in options"
      :key="opt.value"
      type="button"
      class="ods-segmented__btn"
      :class="{ 'is-selected': modelValue === opt.value }"
      :aria-pressed="modelValue === opt.value"
      :disabled="disabled"
      @click="select(opt.value)"
    >
      <span class="ods-segmented__face">{{ opt.label }}</span>
    </button>
  </div>
</template>

<style scoped>
.ods-segmented {
  display: inline-grid;
  grid-auto-flow: column;
  grid-auto-columns: 1fr;
  gap: var(--ods-space-8);
  width: min(100%, 220px);
  max-width: 100%;
  min-height: var(--ods-touch-min);
  align-items: center;
}

.ods-segmented__btn {
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: var(--ods-touch-min);
  min-width: var(--ods-touch-min);
  padding: 0;
  border: none;
  background: transparent;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}

.ods-segmented__face {
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  /* 시각 높이 36~40px */
  height: 38px;
  width: 100%;
  padding: 0 var(--ods-space-12);
  border: 1px solid var(--ods-color-border);
  border-radius: var(--ods-radius-badge);
  background: var(--ods-color-white);
  font: var(--ods-font-body-2);
  font-weight: 600;
  color: var(--ods-color-text-secondary);
  white-space: nowrap;
}

.ods-segmented__btn.is-selected .ods-segmented__face {
  background: var(--ods-color-primary);
  border-color: var(--ods-color-primary);
  color: var(--ods-color-white);
}

.ods-segmented__btn:focus-visible {
  outline: none;
}

.ods-segmented__btn:focus-visible .ods-segmented__face {
  outline: 2px solid var(--ods-color-primary);
  outline-offset: 2px;
}

.ods-segmented__btn:active:not(:disabled) .ods-segmented__face {
  filter: brightness(0.96);
}

.ods-segmented__btn:disabled {
  cursor: not-allowed;
  opacity: 0.48;
}

@media (max-width: 320px) {
  .ods-segmented {
    width: 100%;
  }
}
</style>
