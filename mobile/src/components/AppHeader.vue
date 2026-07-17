<script setup lang="ts">
defineProps<{
  title?: string
  subtitle?: string
}>()
</script>

<template>
  <header class="app-header">
    <p class="eyebrow">{{ title || 'Orchard Platform' }}</p>
    <h1>{{ subtitle || '삼육농원 모바일 관리' }}</h1>
  </header>
</template>

<style scoped>
.app-header {
  padding: 8px 4px 16px;
}
.eyebrow {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
  color: #2d5a27;
  letter-spacing: 0.02em;
}
h1 {
  margin: 4px 0 0;
  font-size: 22px;
  line-height: 1.3;
  color: #1a202c;
  font-weight: 700;
}
</style>
