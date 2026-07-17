<script setup lang="ts">
/**
 * 모바일 폼 필드 래퍼 (라벨·필수/선택·도움말).
 * ODS PDF 원본이 아닌 Project A 현장 가독성 적용 규칙 사용.
 */
withDefaults(
  defineProps<{
    label: string
    required?: boolean
    optional?: boolean
    hint?: string
    as?: 'label' | 'fieldset'
  }>(),
  {
    required: false,
    optional: false,
    hint: '',
    as: 'label',
  },
)
</script>

<template>
  <component :is="as === 'fieldset' ? 'fieldset' : 'label'" class="ods-form-field">
    <component :is="as === 'fieldset' ? 'legend' : 'span'" class="ods-form-field__label">
      <span class="ods-form-field__label-text">{{ label }}</span>
      <span v-if="required" class="ods-form-field__req" aria-hidden="true">*</span>
      <span v-else-if="optional" class="ods-form-field__opt">(선택)</span>
    </component>
    <div class="ods-form-field__control">
      <slot />
    </div>
    <p v-if="hint" class="ods-form-field__hint">{{ hint }}</p>
  </component>
</template>

<style scoped>
.ods-form-field {
  display: flex;
  flex-direction: column;
  gap: var(--ods-form-label-gap);
  margin: 0;
  padding: 0;
  border: none;
  min-width: 0;
}
.ods-form-field__label {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 4px;
  padding: 0;
  font: var(--ods-font-form-label);
  color: var(--ods-color-text-label);
}
.ods-form-field__label-text {
  font: inherit;
  color: inherit;
}
.ods-form-field__req {
  color: var(--ods-color-danger);
  font-weight: 700;
}
.ods-form-field__opt {
  font: var(--ods-font-form-help);
  font-weight: 500;
  color: var(--ods-color-text-secondary);
}
.ods-form-field__control {
  min-width: 0;
}
.ods-form-field__hint {
  margin: 0;
  font: var(--ods-font-form-help);
  color: var(--ods-color-text-secondary);
}
</style>
