<script setup lang="ts">
</script>

<template>
  <div class="shell">
    <main class="content">
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
}
</style>
