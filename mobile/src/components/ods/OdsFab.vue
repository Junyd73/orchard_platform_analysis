<script setup lang="ts">
withDefaults(
  defineProps<{
    label?: string
    ariaLabel: string
  }>(),
  {
    label: '',
  },
)

const emit = defineEmits<{
  click: []
}>()
</script>

<template>
  <button
    type="button"
    class="ods-fab"
    :aria-label="ariaLabel"
    @click="emit('click')"
  >
    <span class="ods-fab__icon">
      <slot />
    </span>
    <span v-if="label" class="ods-fab__label">{{ label }}</span>
  </button>
</template>

<style scoped>
.ods-fab {
  position: fixed;
  right: max(var(--ods-space-16), env(safe-area-inset-right));
  bottom: calc(64px + var(--ods-space-24) + env(safe-area-inset-bottom));
  z-index: 40;
  width: var(--ods-fab-size);
  height: var(--ods-fab-size);
  border: none;
  border-radius: var(--ods-radius-badge);
  background: var(--ods-color-primary);
  color: var(--ods-color-white);
  box-shadow: var(--ods-shadow-fab);
  cursor: pointer;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0;
  padding: 0;
  overflow: hidden;
  transition:
    transform var(--ods-motion-fast) var(--ods-motion-ease),
    box-shadow var(--ods-motion-fast) var(--ods-motion-ease);
}
.ods-fab::after {
  content: '';
  position: absolute;
  inset: 0;
  background: radial-gradient(
    circle at center,
    rgba(255, 255, 255, 0.35) 0%,
    transparent 60%
  );
  opacity: 0;
  transform: scale(0.4);
  transition:
    opacity var(--ods-motion-fast) var(--ods-motion-ease),
    transform var(--ods-motion-base) var(--ods-motion-ease);
  pointer-events: none;
}
.ods-fab:active {
  transform: scale(0.94);
  box-shadow: var(--ods-shadow-card);
}
.ods-fab:active::after {
  opacity: 1;
  transform: scale(1.6);
}
.ods-fab__icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: var(--ods-space-24);
  height: var(--ods-space-24);
}
.ods-fab__icon :deep(img) {
  width: 22px;
  height: 22px;
  filter: brightness(0) invert(1);
}
.ods-fab__label {
  font: var(--ods-font-caption);
  font-weight: 700;
  line-height: 1.1;
  margin-top: 1px;
}
@media (prefers-reduced-motion: reduce) {
  .ods-fab,
  .ods-fab::after {
    transition: none;
  }
}
</style>
