<script setup lang="ts">
import {
  LABEL_HOME_RECENT,
  MSG_HOME_RECENT_EMPTY,
} from '@/views/home/homeConstants'
import type { HomeRecentItem } from '@/views/home/homeMock'

defineProps<{
  items: HomeRecentItem[]
}>()
</script>

<template>
  <section class="wrap" aria-label="최근 활동">
    <div class="head">
      <h2 class="title">{{ LABEL_HOME_RECENT }}</h2>
    </div>
    <ul v-if="items.length" class="list">
      <li v-for="it in items" :key="it.id" class="row">
        <div class="row__main">
          <p class="row__title">{{ it.title }}</p>
          <p class="row__detail">{{ it.detail }}</p>
        </div>
        <div class="row__side">
          <span v-if="it.badge" class="badge">{{ it.badge }}</span>
          <time class="row__time">{{ it.timeLabel }}</time>
        </div>
      </li>
    </ul>
    <p v-else class="empty">{{ MSG_HOME_RECENT_EMPTY }}</p>
  </section>
</template>

<style scoped>
.wrap {
  padding: var(--ods-space-12);
  border-radius: var(--ods-radius-card);
  background: var(--ods-color-white);
  border: 1px solid var(--ods-color-border);
  box-shadow: var(--ods-shadow-card);
}
.head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: var(--ods-space-12);
}
.title {
  margin: 0;
  font: var(--ods-font-headline);
  color: var(--ods-color-text);
}
.list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 0;
}
.row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  padding: 10px 0;
  border-top: 1px solid var(--ods-color-gray-100);
}
.row:first-child {
  border-top: 0;
  padding-top: 0;
}
.row__main {
  min-width: 0;
}
.row__title {
  margin: 0;
  font: var(--ods-font-body-1);
  color: var(--ods-color-text);
}
.row__detail {
  margin: 2px 0 0;
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
}
.row__side {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
  flex-shrink: 0;
}
.badge {
  padding: 2px 6px;
  border-radius: 6px;
  background: color-mix(in srgb, var(--ods-color-ai) 14%, #fff);
  color: var(--ods-color-ai);
  font: 600 10px/1.2 var(--ods-font-family);
}
.row__time {
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
}
.empty {
  margin: 0;
  font: var(--ods-font-body-2);
  color: var(--ods-color-text-secondary);
}
</style>
