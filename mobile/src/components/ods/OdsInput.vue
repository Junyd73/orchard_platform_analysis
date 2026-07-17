<script setup lang="ts">
import { useAttrs } from 'vue'

/**
 * ODS Input
 * - variant=default: SCR-001 등 기존 화면 (변경 최소화)
 * - variant=form: 모바일 폼 가독성 (라벨 16px SemiBold+, 입력 17px)
 */
withDefaults(
  defineProps<{
    modelValue?: string
    label?: string
    type?: string
    placeholder?: string
    disabled?: boolean
    variant?: 'default' | 'form'
    /** form 전용: 라벨 옆 * (OdsFormField 미사용 시) */
    required?: boolean
    /** form 전용: (선택) */
    optional?: boolean
    /** form 전용: 라벨 없이 컨트롤만 (OdsFormField 슬롯용) */
    bare?: boolean
  }>(),
  {
    modelValue: '',
    label: '',
    type: 'text',
    placeholder: '',
    disabled: false,
    variant: 'default',
    required: false,
    optional: false,
    bare: false,
  },
)

defineEmits<{
  'update:modelValue': [value: string]
}>()

defineOptions({ inheritAttrs: false })

const attrs = useAttrs()
</script>

<template>
  <label
    v-if="!bare"
    class="ods-field"
    :class="{ 'ods-field--form': variant === 'form' }"
  >
    <span v-if="label" class="ods-field__label">
      <span class="ods-field__label-text">{{ label }}</span>
      <span v-if="required" class="ods-field__req" aria-hidden="true">*</span>
      <span v-else-if="optional" class="ods-field__opt">(선택)</span>
    </span>
    <input
      class="ods-input"
      :class="{ 'ods-input--form': variant === 'form' }"
      v-bind="attrs"
      :type="type || 'text'"
      :value="modelValue"
      :placeholder="placeholder"
      :disabled="disabled"
      :aria-required="required || undefined"
      @input="$emit('update:modelValue', ($event.target as HTMLInputElement).value)"
    >
  </label>
  <input
    v-else
    class="ods-input"
    :class="{ 'ods-input--form': variant === 'form' }"
    v-bind="attrs"
    :type="type || 'text'"
    :value="modelValue"
    :placeholder="placeholder"
    :disabled="disabled"
    :aria-required="required || undefined"
    @input="$emit('update:modelValue', ($event.target as HTMLInputElement).value)"
  >
</template>

<style scoped>
.ods-field {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-4);
  min-width: 0;
}
.ods-field--form {
  gap: var(--ods-form-label-gap);
}
.ods-field__label {
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
}
.ods-field--form .ods-field__label {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 4px;
  font: var(--ods-font-form-label);
  color: var(--ods-color-text-label);
}
.ods-field__req {
  color: var(--ods-color-danger);
  font-weight: 700;
}
.ods-field__opt {
  font: var(--ods-font-form-help);
  font-weight: 500;
  color: var(--ods-color-text-secondary);
}
.ods-input {
  height: var(--ods-control-height);
  min-height: var(--ods-control-height);
  width: 100%;
  box-sizing: border-box;
  padding: 0 var(--ods-space-16);
  border: 1px solid var(--ods-color-border);
  border-radius: var(--ods-radius-button);
  font: var(--ods-font-body-1);
  color: var(--ods-color-text);
  background: var(--ods-color-white);
}
.ods-input--form {
  font: var(--ods-font-form-value);
}
.ods-input--form::placeholder {
  font: var(--ods-font-form-placeholder);
  color: var(--ods-color-gray-500);
}
.ods-input:disabled {
  background: var(--ods-color-gray-100);
  color: var(--ods-color-gray-500);
}
</style>
