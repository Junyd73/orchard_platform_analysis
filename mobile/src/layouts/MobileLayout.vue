<script setup lang="ts">
import OdsAppBar from '@/components/ods/OdsAppBar.vue'
import OdsBottomNav from '@/components/ods/OdsBottomNav.vue'
</script>

<template>
  <div class="page">
    <main class="content ods-page-content">
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
  /* padding/max-width/gap -> .ods-page-content (AppBar SSOT) */
}
.body {
  display: flex;
  flex-direction: column;
  gap: var(--ods-page-content-gap);
  min-width: 0;
}
</style>
