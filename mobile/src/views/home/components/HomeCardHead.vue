<script setup lang="ts">
defineProps<{
  title: string
  icon: string
  detailLabel?: string
}>()

const emit = defineEmits<{
  detail: []
}>()
</script>

<template>
  <div class="head">
    <div class="head__left">
      <img class="head__ico" :src="icon" alt="" aria-hidden="true" />
      <h2 class="head__title">{{ title }}</h2>
    </div>
    <button
      v-if="detailLabel"
      type="button"
      class="head__detail"
      @click="emit('detail')"
    >
      {{ detailLabel }}
      <span class="head__chev" aria-hidden="true">›</span>
    </button>
  </div>
</template>

<style scoped>
.head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
}
.head__left {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}
.head__ico {
  width: var(--ods-icon-xl);
  height: var(--ods-icon-xl);
  flex-shrink: 0;
}
.head__title {
  margin: 0;
  font: var(--ods-font-headline);
  font-size: 15px;
  color: var(--ods-color-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.head__detail {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  gap: 1px;
  margin: 0;
  padding: 0;
  border: 0;
  background: transparent;
  font: 600 12px/1.2 var(--ods-font-family);
  color: var(--ods-color-primary);
  cursor: pointer;
}
.head__chev {
  font-size: 14px;
  line-height: 1;
  font-weight: 700;
}
</style>
