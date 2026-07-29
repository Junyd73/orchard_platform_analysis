<script setup lang="ts">
import { useRouter } from 'vue-router'

import iconObservation from '@/assets/ods/home/icon-quick-observation.svg'
import iconOrder from '@/assets/ods/home/icon-quick-order.svg'
import iconPesticide from '@/assets/ods/home/icon-quick-pesticide.svg'
import iconWorklog from '@/assets/ods/home/icon-quick-worklog.svg'
import {
  HOME_DAILY_NEW_QUERY,
  HOME_QUICK_ACTIONS,
  LABEL_HOME_QUICK,
  MSG_HOME_ORDER_SOON,
  type HomeQuickActionKey,
} from '@/views/home/homeConstants'
import { todayIso } from '@/views/work-log/workLogConstants'

const emit = defineEmits<{
  soon: [message: string]
  pesticide: []
}>()

const router = useRouter()

const ICONS: Record<HomeQuickActionKey, string> = {
  observation: iconObservation,
  work_log: iconWorklog,
  pesticide: iconPesticide,
  order: iconOrder,
}

function onSelect(key: HomeQuickActionKey, ready: boolean, to: string) {
  if (!ready) {
    emit('soon', MSG_HOME_ORDER_SOON)
    return
  }
  if (key === 'work_log') {
    void router.push({
      name: 'work-log-daily',
      params: { workDt: todayIso() },
      query: { new: HOME_DAILY_NEW_QUERY },
    })
    return
  }
  if (key === 'pesticide') {
    emit('pesticide')
    return
  }
  if (to) void router.push(to)
}
</script>

<template>
  <section class="wrap" aria-label="빠른 실행">
    <h2 class="title">{{ LABEL_HOME_QUICK }}</h2>
    <nav class="grid" aria-label="빠른 실행 메뉴">
      <button
        v-for="a in HOME_QUICK_ACTIONS"
        :key="a.key"
        type="button"
        class="item"
        :class="{ 'item--soon': !a.ready }"
        @click="onSelect(a.key, a.ready, a.to)"
      >
        <img class="item__ico" :src="ICONS[a.key]" alt="" aria-hidden="true" />
        <span class="item__text">
          <span class="item__label">{{ a.label }}</span>
          <span class="item__sub">{{ a.sub }}</span>
        </span>
      </button>
    </nav>
  </section>
</template>

<style scoped>
.wrap {
  padding: 0;
  border: 0;
  border-radius: 0;
  background: transparent;
  box-shadow: none;
}
.title {
  margin: 0 0 10px;
  font: var(--ods-font-headline);
  color: var(--ods-color-text);
}
.grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 6px;
  margin: 0;
  padding: 0;
}
.item {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 6px;
  min-width: 0;
  margin: 0;
  padding: 10px 5px;
  border: 1px solid var(--ods-color-border);
  border-radius: 12px;
  background: var(--ods-color-white);
  cursor: pointer;
  text-align: left;
  appearance: none;
  -webkit-appearance: none;
}
.item:active {
  background: color-mix(in srgb, var(--ods-color-primary) 8%, #fff);
}
.item--soon {
  opacity: 0.72;
}
.item__ico {
  width: 20px;
  height: 20px;
  flex-shrink: 0;
}
.item__text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.item__label {
  font: 700 10px/1.2 var(--ods-font-family);
  color: var(--ods-color-text);
  word-break: keep-all;
  white-space: nowrap;
  letter-spacing: -0.03em;
}
.item__sub {
  font: 400 9px/1.25 var(--ods-font-family);
  color: var(--ods-color-text-secondary);
  word-break: keep-all;
  white-space: nowrap;
}

@media (max-width: 389px) {
  .grid {
    grid-template-columns: 1fr 1fr;
    gap: 8px;
  }
  .item {
    padding: 12px 10px;
    gap: 8px;
  }
  .item__ico {
    width: 26px;
    height: 26px;
  }
  .item__label {
    font-size: 12px;
    letter-spacing: -0.02em;
  }
  .item__sub {
    font-size: 10px;
  }
}
</style>
