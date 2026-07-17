<script setup lang="ts">
defineProps<{
  title: string
  description: string
  to: string
}>()
</script>

<template>
  <RouterLink class="menu-card" :to="to">
    <strong>{{ title }}</strong>
    <span>{{ description }}</span>
  </RouterLink>
</template>

<style scoped>
.menu-card {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-height: 72px;
  padding: 16px;
  border-radius: 14px;
  border: 1px solid #eae7e2;
  background: #fff;
  text-decoration: none;
  color: inherit;
}
.menu-card strong {
  font-size: 17px;
  color: #2d5a27;
}
.menu-card span {
  font-size: 14px;
  color: #718096;
  line-height: 1.4;
}
.menu-card:active {
  background: #f7fafc;
}
</style>
