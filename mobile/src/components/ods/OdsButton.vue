<script setup lang="ts">
withDefaults(
  defineProps<{
    variant?: 'primary' | 'secondary' | 'secondary-filled' | 'ai' | 'danger'
    type?: 'button' | 'submit' | 'reset'
    disabled?: boolean
    /** 처리 중: 클릭 차단하되 variant 색 유지 */
    busy?: boolean
    block?: boolean
    /** 외부 form 연결 (floating submit 등) */
    form?: string
  }>(),
  {
    variant: 'primary',
    type: 'button',
    disabled: false,
    busy: false,
    block: true,
  },
)
</script>

<template>
  <button
    class="ods-btn"
    :class="[
      `ods-btn--${variant}`,
      {
        'ods-btn--block': block,
        'ods-btn--busy': busy,
      },
    ]"
    :type="type"
    :disabled="disabled || busy"
    :aria-busy="busy || undefined"
    :form="form"
  >
    <slot />
  </button>
</template>

<style scoped>
.ods-btn {
  min-height: var(--ods-button-height, var(--ods-control-height));
  padding: 0 var(--ods-space-16);
  border: none;
  border-radius: var(--ods-radius-button);
  font: var(--ods-font-headline);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
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
.ods-btn--secondary-filled {
  background: var(--ods-color-secondary-soft);
  color: var(--ods-color-primary);
  border: none;
}
.ods-btn--ai {
  background: var(--ods-color-ai);
  color: var(--ods-color-white);
}
.ods-btn--danger {
  background: var(--ods-color-danger);
  color: var(--ods-color-white);
}
.ods-btn:disabled:not(.ods-btn--busy) {
  background: var(--ods-color-gray-300);
  color: var(--ods-color-gray-500);
  cursor: not-allowed;
}
.ods-btn--busy {
  cursor: wait;
  animation: ods-btn-pulse 1.6s ease-in-out infinite;
}
.ods-btn--ai.ods-btn--busy:disabled {
  background: var(--ods-color-ai);
  color: var(--ods-color-white);
}
.ods-btn--primary.ods-btn--busy:disabled {
  background: var(--ods-color-primary);
  color: var(--ods-color-white);
}
@keyframes ods-btn-pulse {
  0%,
  100% {
    filter: brightness(1);
  }
  50% {
    filter: brightness(1.1);
  }
}
</style>
