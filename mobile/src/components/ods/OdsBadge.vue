<script setup lang="ts">
withDefaults(
  defineProps<{
    tone?: 'neutral' | 'ok' | 'caution' | 'danger' | 'ai'
  }>(),
  { tone: 'neutral' },
)
</script>

<template>
  <span class="ods-badge" :class="`ods-badge--${tone}`">
    <slot />
  </span>
</template>

<style scoped>
.ods-badge {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 0 var(--ods-space-8);
  border-radius: var(--ods-radius-badge);
  font: var(--ods-font-caption);
  font-weight: 600;
}
.ods-badge--neutral {
  background: var(--ods-color-gray-100);
  color: var(--ods-color-gray-700);
}
.ods-badge--ok {
  background: #e8f5e9;
  color: var(--ods-color-primary);
}
.ods-badge--caution {
  background: #fff3e0;
  color: #e65100;
}
.ods-badge--danger {
  background: #fdecea;
  color: var(--ods-color-danger);
}
.ods-badge--ai {
  background: #e8eef6;
  color: var(--ods-color-ai);
}
</style>
