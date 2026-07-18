<script setup lang="ts">
import OdsAppBar from '@/components/ods/OdsAppBar.vue'
</script>

<template>
  <div class="shell">
    <main class="content">
      <OdsAppBar />
      <slot />
    </main>
  </div>
</template>

<style scoped>
.shell {
  min-height: 100dvh;
  background: var(--ods-color-bg-muted);
}
.content {
  max-width: 480px;
  margin: 0 auto;
  padding: var(--ods-space-16) var(--ods-page-padding-x) var(--ods-space-32);
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-16);
}
</style>
