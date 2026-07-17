<script setup lang="ts">
withDefaults(
  defineProps<{
    modelValue?: string
    disabled?: boolean
    variant?: 'default' | 'form'
    required?: boolean
  }>(),
  {
    modelValue: '',
    variant: 'default',
    disabled: false,
    required: false,
  },
)

defineEmits<{
  'update:modelValue': [value: string]
}>()
</script>

<template>
  <select
    class="ods-select"
    :class="{ 'ods-select--form': variant === 'form' }"
    :value="modelValue"
    :disabled="disabled"
    :required="required"
    :aria-required="required || undefined"
    @change="$emit('update:modelValue', ($event.target as HTMLSelectElement).value)"
  >
    <slot />
  </select>
</template>

<style scoped>
.ods-select {
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
.ods-select--form {
  font: var(--ods-font-form-value);
}
.ods-select:disabled {
  background: var(--ods-color-gray-100);
  color: var(--ods-color-gray-500);
}
</style>
