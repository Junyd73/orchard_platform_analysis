<script setup lang="ts">
import {
  MSG_SUMMARY_EMPTY,
  type DailyShellSummaryCard,
} from '@/views/work-log/workLogConstants'

defineProps<{
  cards: readonly DailyShellSummaryCard[]
  empty?: boolean
}>()
</script>

<template>
  <section class="sum" aria-label="오늘 작업 요약">
    <h2 class="sum__title">오늘 작업 요약</h2>
    <p v-if="empty" class="sum__empty">{{ MSG_SUMMARY_EMPTY }}</p>
    <div v-else class="sum__grid">
      <article
        v-for="c in cards"
        :key="c.key"
        class="sum__card"
        :class="`sum__card--${c.tone}`"
      >
        <div class="sum__top">
          <img class="sum__ico" :src="c.icon" alt="" />
          <p class="sum__label">{{ c.label }}</p>
        </div>
        <dl class="sum__lines">
          <div v-for="(line, i) in c.lines" :key="i" class="sum__line">
            <dt>{{ line.label }}</dt>
            <dd>{{ line.value }}</dd>
          </div>
        </dl>
      </article>
    </div>
  </section>
</template>

<style scoped>
.sum {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-12);
}
.sum__title {
  margin: 0;
  font: var(--ods-font-headline);
  color: var(--ods-color-text);
}
.sum__empty {
  margin: 0;
  padding: var(--ods-space-16);
  border-radius: var(--ods-radius-card);
  background: var(--ods-color-white);
  border: 1px solid var(--ods-color-border);
  box-shadow: var(--ods-shadow-card);
  font: var(--ods-font-form-help);
  color: var(--ods-color-text-secondary);
  text-align: center;
}
.sum__grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--ods-space-12);
}
.sum__card {
  padding: var(--ods-space-12);
  border-radius: var(--ods-radius-card);
  border: 1px solid transparent;
  box-shadow: var(--ods-shadow-card);
  min-width: 0;
}
.sum__card--labor {
  background: color-mix(in srgb, var(--ods-color-ai) 12%, var(--ods-color-white));
  border-color: color-mix(in srgb, var(--ods-color-ai) 28%, transparent);
}
.sum__card--expense {
  background: color-mix(in srgb, var(--ods-color-accent) 18%, var(--ods-color-white));
  border-color: color-mix(in srgb, var(--ods-color-accent) 40%, transparent);
}
.sum__card--pesticide {
  background: color-mix(in srgb, var(--ods-color-primary) 10%, var(--ods-color-white));
  border-color: color-mix(in srgb, var(--ods-color-primary) 28%, transparent);
}
.sum__card--fertilizer {
  background: color-mix(in srgb, var(--ods-color-secondary) 14%, var(--ods-color-white));
  border-color: color-mix(in srgb, var(--ods-color-secondary) 32%, transparent);
}
.sum__top {
  display: flex;
  align-items: center;
  gap: var(--ods-space-8);
  margin-bottom: var(--ods-space-8);
}
.sum__ico {
  width: var(--ods-icon-xl);
  height: var(--ods-icon-xl);
}
.sum__label {
  margin: 0;
  font: var(--ods-font-card-section);
  color: var(--ods-color-text-secondary);
}
.sum__lines {
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-4);
}
.sum__line {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--ods-space-8);
}
.sum__line dt {
  margin: 0;
  font: var(--ods-font-card-help);
  color: var(--ods-color-text-secondary);
  flex-shrink: 0;
}
.sum__line dd {
  margin: 0;
  font: var(--ods-font-form-help);
  font-weight: 700;
  color: var(--ods-color-text);
  text-align: right;
  min-width: 0;
  word-break: keep-all;
}
</style>
