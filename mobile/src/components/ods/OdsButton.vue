<script setup lang="ts">
withDefaults(
  defineProps<{
    variant?: 'primary' | 'secondary' | 'ai' | 'danger'
    type?: 'button' | 'submit' | 'reset'
    disabled?: boolean
    block?: boolean
  }>(),
  {
    variant: 'primary',
    type: 'button',
    disabled: false,
    block: true,
  },
)
</script>

<template>
  <button
    class="ods-btn"
    :class="[`ods-btn--${variant}`, { 'ods-btn--block': block }]"
    :type="type"
    :disabled="disabled"
  >
    <slot />
  </button>
</template>

<style scoped>
.ods-btn {
  min-height: var(--ods-control-height);
  padding: 0 var(--ods-space-16);
  border: none;
  border-radius: var(--ods-radius-button);
  font: var(--ods-font-headline);
  cursor: pointer;
}
.ods-btn--block {
  width: 100%;
}
.ods-btn--primary {
  background: var(--ods-color-primary);
  color: var(--ods-color-white);
}
.ods-btn--secondary {
  background: var(--ods-color-gray-100);
  color: var(--ods-color-gray-900);
  border: 1px solid var(--ods-color-border);
}
.ods-btn--ai {
  background: var(--ods-color-ai);
  color: var(--ods-color-white);
}
.ods-btn--danger {
  background: var(--ods-color-danger);
  color: var(--ods-color-white);
}
.ods-btn:disabled {
  background: var(--ods-color-gray-300);
  color: var(--ods-color-gray-500);
  cursor: not-allowed;
}
</style>
