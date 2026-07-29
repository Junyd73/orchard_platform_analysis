<script setup lang="ts">
import { computed } from 'vue'

import iconBriefing from '@/assets/ods/home/icon-title-briefing.svg'
import iconClipboard from '@/assets/ods/work-log/icon-clipboard.svg'
import iconPest from '@/assets/ods/common/icon-kpi-pest.svg'
import iconWarn from '@/assets/ods/common/icon-kpi-warn.svg'
import iconWork from '@/assets/ods/work-log/icon-work.svg'
import wxRain from '@/assets/ods/work-log/wx-rain.svg'
import HomeCardHead from '@/views/home/components/HomeCardHead.vue'
import {
  HOME_BRIEFING_KIND,
  HOME_BRIEFING_KIND_LABEL,
  HOME_BRIEFING_KIND_ORDER,
  LABEL_HOME_BRIEFING,
  MSG_HOME_BRIEFING_EMPTY,
} from '@/views/home/homeConstants'
import type { HomeBriefingItem } from '@/views/home/homeMock'

const props = defineProps<{
  items: HomeBriefingItem[]
}>()

const ICON_BY_KIND: Record<string, string> = {
  [HOME_BRIEFING_KIND.WEATHER]: wxRain,
  [HOME_BRIEFING_KIND.PEST]: iconPest,
  [HOME_BRIEFING_KIND.IN_PROGRESS]: iconWarn,
  [HOME_BRIEFING_KIND.TODAY_SCHEDULE]: iconWork,
  [HOME_BRIEFING_KIND.OBSERVATION]: iconClipboard,
}

const visible = computed(() => {
  const map = new Map(props.items.map((it) => [it.kind, it]))
  return HOME_BRIEFING_KIND_ORDER.map((k) => map.get(k)).filter(
    (it): it is HomeBriefingItem => Boolean(it),
  )
})
</script>

<template>
  <section class="card" aria-label="오늘 브리핑">
    <HomeCardHead :title="LABEL_HOME_BRIEFING" :icon="iconBriefing" />
    <ul v-if="visible.length" class="list">
      <li v-for="it in visible" :key="it.kind" class="row">
        <img
          class="row__ico"
          :src="ICON_BY_KIND[it.kind]"
          alt=""
          aria-hidden="true"
        />
        <p class="row__text">
          <span class="row__kind">{{ HOME_BRIEFING_KIND_LABEL[it.kind] }}</span>
          <span class="row__title">{{ it.title }}</span>
        </p>
      </li>
    </ul>
    <p v-else class="empty">{{ MSG_HOME_BRIEFING_EMPTY }}</p>
  </section>
</template>

<style scoped>
.card {
  padding: var(--ods-space-12);
  border-radius: var(--ods-radius-card);
  background: var(--ods-color-white);
  border: 1px solid var(--ods-color-border);
  box-shadow: var(--ods-shadow-card);
  box-sizing: border-box;
}
.list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.row {
  display: flex;
  gap: 8px;
  align-items: center;
  min-height: 28px;
}
.row__ico {
  width: var(--ods-icon-md);
  height: var(--ods-icon-md);
  flex-shrink: 0;
}
.row__text {
  margin: 0;
  min-width: 0;
  display: flex;
  align-items: baseline;
  gap: 6px;
  font: var(--ods-font-body-2);
  color: var(--ods-color-text);
  overflow: hidden;
}
.row__kind {
  flex-shrink: 0;
  font: 600 11px/1.2 var(--ods-font-family);
  color: var(--ods-color-primary);
}
.row__title {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.empty {
  margin: 0;
  font: var(--ods-font-body-2);
  color: var(--ods-color-text-secondary);
}
</style>
