<script setup lang="ts">
withDefaults(
  defineProps<{
    /** 섹션 제목 문구 */
    title: string
    /** ODS 아이콘 URL (assets/ods/.../*.svg) */
    icon: string
    /** 시맨틱 레벨. 페이지 섹션은 2, 카드 안 소제목은 3 */
    level?: 2 | 3
  }>(),
  {
    level: 2,
  },
)
</script>

<template>
  <div class="ods-sec-title">
    <img class="ods-sec-title__ico" :src="icon" alt="" aria-hidden="true">
    <component :is="level === 3 ? 'h3' : 'h2'" class="ods-sec-title__text">
      {{ title }}
    </component>
  </div>
</template>

<style scoped>
.ods-sec-title {
  display: inline-flex;
  align-items: center;
  gap: var(--ods-section-title-gap, var(--ods-space-8));
  margin: 0;
  min-width: 0;
}
.ods-sec-title__ico {
  width: var(--ods-section-title-icon, var(--ods-icon-lg));
  height: var(--ods-section-title-icon, var(--ods-icon-lg));
  flex: 0 0 auto;
  display: block;
}
.ods-sec-title__text {
  margin: 0;
  min-width: 0;
  font: var(--ods-font-form-label);
  color: var(--ods-color-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
