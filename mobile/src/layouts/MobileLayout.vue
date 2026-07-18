<script setup lang="ts">
import OdsAppBar from '@/components/ods/OdsAppBar.vue'
import OdsBottomNav from '@/components/ods/OdsBottomNav.vue'
</script>

<template>
  <div class="page">
    <main class="content">
      <OdsAppBar />
      <div class="body">
        <slot />
      </div>
    </main>
    <OdsBottomNav />
  </div>
</template>

<style scoped>
.page {
  min-height: 100dvh;
  background: var(--ods-color-bg-muted);
  padding-bottom: calc(148px + env(safe-area-inset-bottom, 0px));
}
.content {
  max-width: 480px;
  margin: 0 auto;
  padding: var(--ods-space-12) var(--ods-page-padding-x) var(--ods-space-16);
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-16);
}
.body {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-16);
  min-width: 0;
}
</style>
