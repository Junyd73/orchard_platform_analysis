<script setup lang="ts">
withDefaults(
  defineProps<{
    title?: string
    description?: string
  }>(),
  {
    title: '표시할 내용이 없습니다',
    description: '',
  },
)
</script>

<template>
  <div class="ods-empty" role="status">
    <p class="ods-empty__title">{{ title }}</p>
    <p v-if="description" class="ods-empty__desc">{{ description }}</p>
    <div v-if="$slots.default" class="ods-empty__actions">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.ods-empty {
  padding: var(--ods-space-24) var(--ods-space-16);
  text-align: center;
  border-radius: var(--ods-radius-card);
  background: var(--ods-color-white);
  box-shadow: var(--ods-shadow-card);
}
.ods-empty__title {
  margin: 0;
  font: var(--ods-font-headline);
  color: var(--ods-color-text);
}
.ods-empty__desc {
  margin: var(--ods-space-8) 0 0;
  font: var(--ods-font-body-2);
  color: var(--ods-color-text-secondary);
}
.ods-empty__actions {
  margin-top: var(--ods-space-16);
  display: flex;
  justify-content: center;
  gap: var(--ods-space-8);
}
</style>
