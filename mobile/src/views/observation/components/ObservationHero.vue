<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  farmName?: string
}>()

const todayLabel = computed(() => {
  const d = new Date()
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  const week = ['일', '월', '화', '수', '목', '금', '토'][d.getDay()]
  return `${y}. ${m}. ${day} (${week})`
})

const greeting = computed(() => {
  const name = (props.farmName || '').trim()
  return name ? `${name}의 오늘` : '오늘도 과수원의 변화를 기록하세요'
})
</script>

<template>
  <header class="hero">
    <p class="hero__date">{{ todayLabel }}</p>
    <h1 class="hero__title">생육관찰</h1>
    <p class="hero__msg">{{ greeting }}</p>
    <div class="hero__weather" role="status">
      <span class="hero__weather-label">오늘 날씨</span>
      <span class="hero__weather-value">준비 중</span>
    </div>
  </header>
</template>

<style scoped>
.hero {
  padding: var(--ods-space-8) 0 var(--ods-space-16);
}
.hero__date {
  margin: 0;
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
}
.hero__title {
  margin: var(--ods-space-8) 0 0;
  font: var(--ods-font-title-1);
  color: var(--ods-color-text);
}
.hero__msg {
  margin: var(--ods-space-8) 0 0;
  font: var(--ods-font-body-1);
  color: var(--ods-color-text-secondary);
}
.hero__weather {
  margin-top: var(--ods-space-16);
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: var(--ods-control-height);
  padding: 0 var(--ods-space-16);
  border-radius: var(--ods-radius-card);
  background: var(--ods-color-white);
  border: 1px solid var(--ods-color-border);
}
.hero__weather-label {
  font: var(--ods-font-body-2);
  color: var(--ods-color-text-secondary);
}
.hero__weather-value {
  font: var(--ods-font-body-1);
  color: var(--ods-color-gray-500);
}
</style>
