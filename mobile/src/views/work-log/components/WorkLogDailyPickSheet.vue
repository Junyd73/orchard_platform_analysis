<script setup lang="ts">
defineProps<{
  open: boolean
  title: string
  options: ReadonlyArray<{ value: string; label: string }>
}>()

const emit = defineEmits<{
  close: []
  select: [value: string, label: string]
}>()
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="sheet" role="dialog" :aria-label="title">
      <button type="button" class="sheet__backdrop" aria-label="닫기" @click="emit('close')" />
      <div class="sheet__panel">
        <header class="sheet__head">
          <h3 class="sheet__title">{{ title }}</h3>
          <button type="button" class="sheet__x" @click="emit('close')">닫기</button>
        </header>
        <ul class="sheet__list">
          <li v-for="opt in options" :key="opt.value">
            <button
              type="button"
              class="sheet__item"
              @click="emit('select', opt.value, opt.label)"
            >
              {{ opt.label }}
            </button>
          </li>
        </ul>
        <p v-if="options.length === 0" class="sheet__empty">선택 가능한 항목이 없습니다.</p>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.sheet {
  position: fixed;
  inset: 0;
  z-index: 80;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
}
.sheet__backdrop {
  position: absolute;
  inset: 0;
  margin: 0;
  padding: 0;
  border: none;
  background: color-mix(in srgb, var(--ods-color-gray-900) 40%, transparent);
  cursor: pointer;
}
.sheet__panel {
  position: relative;
  max-height: min(56dvh, 420px);
  display: flex;
  flex-direction: column;
  border-radius: var(--ods-radius-card) var(--ods-radius-card) 0 0;
  background: var(--ods-color-white);
  box-shadow: var(--ods-shadow-card);
  padding-bottom: env(safe-area-inset-bottom);
}
.sheet__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--ods-space-12) var(--ods-space-16);
  border-bottom: 1px solid var(--ods-color-border);
}
.sheet__title {
  margin: 0;
  font: var(--ods-font-headline);
  color: var(--ods-color-text);
}
.sheet__x {
  margin: 0;
  padding: var(--ods-space-4) var(--ods-space-8);
  border: none;
  background: transparent;
  font: var(--ods-font-form-help);
  font-weight: 700;
  color: var(--ods-color-primary);
  cursor: pointer;
}
.sheet__list {
  list-style: none;
  margin: 0;
  padding: var(--ods-space-8) 0;
  overflow-y: auto;
}
.sheet__item {
  width: 100%;
  margin: 0;
  padding: var(--ods-space-12) var(--ods-space-16);
  border: none;
  background: transparent;
  text-align: left;
  font: var(--ods-font-body-1);
  color: var(--ods-color-text);
  cursor: pointer;
}
.sheet__item:active {
  background: var(--ods-color-bg-muted);
}
.sheet__empty {
  margin: 0;
  padding: var(--ods-space-20);
  text-align: center;
  font: var(--ods-font-form-help);
  color: var(--ods-color-text-secondary);
}
</style>
