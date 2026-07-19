<script setup lang="ts">
withDefaults(
  defineProps<{
    title?: string
    description?: string
    /** 캘린더 등: 시선을 덜 뺏는 컴팩트 빈 상태 */
    compact?: boolean
  }>(),
  {
    title: '표시할 내용이 없습니다',
    description: '',
    compact: false,
  },
)
</script>

<template>
  <div
    class="ods-empty"
    :class="{ 'ods-empty--compact': compact }"
    role="status"
  >
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
.ods-empty--compact {
  padding: var(--ods-space-12) var(--ods-space-12);
  box-shadow: none;
  border: 1px solid var(--ods-color-gray-100);
  background: var(--ods-color-bg-muted);
}
.ods-empty__title {
  margin: 0;
  font: var(--ods-font-headline);
  color: var(--ods-color-text);
}
.ods-empty--compact .ods-empty__title {
  font: var(--ods-font-caption);
  font-weight: 600;
  color: var(--ods-color-text-secondary);
}
.ods-empty__desc {
  margin: var(--ods-space-8) 0 0;
  font: var(--ods-font-body-2);
  color: var(--ods-color-text-secondary);
}
.ods-empty--compact .ods-empty__desc {
  margin-top: var(--ods-space-4);
  font-size: 10px;
  line-height: 1.35;
}
.ods-empty__actions {
  margin-top: var(--ods-space-16);
  display: flex;
  justify-content: center;
  gap: var(--ods-space-8);
}
.ods-empty--compact .ods-empty__actions {
  margin-top: var(--ods-space-8);
}
</style>
