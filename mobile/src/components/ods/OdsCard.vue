<script setup lang="ts">
defineProps<{
  title?: string
}>()
</script>

<template>
  <section class="ods-card">
    <h2 v-if="title" class="ods-card__title">{{ title }}</h2>
    <slot />
  </section>
</template>

<style scoped>
.ods-card {
  background: var(--ods-color-white);
  border: 1px solid var(--ods-color-border);
  border-radius: var(--ods-radius-card);
  padding: var(--ods-card-padding);
  box-shadow: var(--ods-shadow-card);
}
.ods-card__title {
  margin: 0 0 var(--ods-space-12);
  font: var(--ods-font-form-label);
  color: var(--ods-color-text);
}
/* 카드 안 버튼 = 하단 Floating(48)과 구분 */
.ods-card :deep(.ods-btn) {
  min-height: var(--ods-button-height-in-card);
}
</style>
