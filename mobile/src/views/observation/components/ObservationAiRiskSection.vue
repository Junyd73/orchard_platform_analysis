<script setup lang="ts">
import { computed } from 'vue'

import iconWarn from '@/assets/ods/common/icon-kpi-warn.svg'
import {
  LABEL_AI_RISK,
  MSG_AI_RISK_EMPTY,
  MSG_AI_RISK_LOADING,
  type AiRiskCardItem,
} from '@/views/observation/observationHomeCopy'

const props = withDefaults(
  defineProps<{
    items?: AiRiskCardItem[] | null
    loading?: boolean
  }>(),
  {
    items: null,
    loading: false,
  },
)

const emit = defineEmits<{
  open: [obsId: string]
}>()

const cards = computed(() => props.items ?? [])
const isEmpty = computed(() => !props.loading && cards.value.length === 0)
</script>

<template>
  <section class="ai-risk" :aria-label="LABEL_AI_RISK">
    <header class="ai-risk__head">
      <h2 class="ai-risk__title">
        <img class="ai-risk__ico" :src="iconWarn" alt="" aria-hidden="true">
        {{ LABEL_AI_RISK }}
      </h2>
      <p v-if="!loading && cards.length" class="ai-risk__count">
        {{ cards.length }}건
      </p>
    </header>

    <p v-if="loading" class="ai-risk__hint" role="status">
      {{ MSG_AI_RISK_LOADING }}
    </p>

    <div
      v-else-if="!isEmpty"
      class="ai-risk__track"
      role="list"
    >
      <button
        v-for="c in cards"
        :key="c.id"
        type="button"
        class="ai-risk__card"
        role="listitem"
        :aria-label="`${c.pestName}, ${c.severityLabel}, ${c.timeLabel}`"
        @click="emit('open', c.id)"
      >
        <div class="ai-risk__main">
          <p class="ai-risk__name">{{ c.pestName }}</p>
          <p class="ai-risk__meta">
            <span class="ai-risk__sev">{{ c.severityLabel }}</span>
            <span class="ai-risk__date">{{ c.timeLabel }}</span>
          </p>
        </div>

        <div class="ai-risk__aside" aria-hidden="true">
          <div class="ai-risk__thumb">
            <img
              v-if="c.thumbUrl"
              class="ai-risk__img"
              :src="c.thumbUrl"
              alt=""
            >
            <span v-else class="ai-risk__ph">병해충</span>
          </div>
          <span class="ai-risk__chev">›</span>
        </div>
      </button>
    </div>

    <div v-else class="ai-risk__card ai-risk__card--empty" role="status">
      <div class="ai-risk__main">
        <p class="ai-risk__empty">{{ MSG_AI_RISK_EMPTY }}</p>
      </div>
    </div>
  </section>
</template>

<style scoped>
.ai-risk {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-10);
  margin: 0;
}
.ai-risk__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ods-space-8);
  padding: 0 2px;
}
.ai-risk__title {
  margin: 0;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font: var(--ods-font-headline);
  font-size: 15px;
  font-weight: 800;
  letter-spacing: -0.02em;
  color: var(--ods-color-danger);
}
.ai-risk__ico {
  width: 14px;
  height: 14px;
  display: block;
  flex: 0 0 auto;
}
.ai-risk__count {
  margin: 0;
  font: var(--ods-font-caption);
  font-weight: 700;
  color: var(--ods-color-text-secondary);
}
.ai-risk__hint {
  margin: 0;
  padding: var(--ods-space-16);
  border-radius: 16px;
  background: color-mix(in srgb, var(--ods-color-danger) 4%, transparent);
  border: 1px solid color-mix(in srgb, var(--ods-color-danger) 10%, transparent);
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
}
.ai-risk__track {
  display: flex;
  gap: 10px;
  overflow-x: auto;
  padding: 2px 2px 4px;
  scroll-snap-type: x mandatory;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
}
.ai-risk__track::-webkit-scrollbar {
  display: none;
}
.ai-risk__card {
  flex: 0 0 auto;
  width: min(292px, calc(100vw - 48px));
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ods-space-12);
  margin: 0;
  padding: 14px 12px 14px 16px;
  border: 1px solid color-mix(in srgb, var(--ods-color-danger) 12%, transparent);
  border-radius: 16px;
  background: color-mix(in srgb, var(--ods-color-danger) 3.5%, transparent);
  box-shadow: none;
  text-align: left;
  cursor: pointer;
  scroll-snap-align: start;
}
.ai-risk__card--empty {
  width: 100%;
  cursor: default;
  flex: none;
}
.ai-risk__main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.ai-risk__name {
  margin: 0;
  font-size: 16px;
  font-weight: 800;
  line-height: 1.25;
  letter-spacing: -0.03em;
  color: var(--ods-color-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ai-risk__meta {
  margin: 0;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  line-height: 1.3;
}
.ai-risk__sev {
  display: inline-flex;
  align-items: center;
  padding: 2px 7px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 800;
  color: var(--ods-color-danger);
  background: color-mix(in srgb, var(--ods-color-danger) 8%, transparent);
}
.ai-risk__date {
  color: var(--ods-color-text-secondary);
  font-weight: 500;
}
.ai-risk__empty {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
  color: var(--ods-color-text-secondary);
}
.ai-risk__aside {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  gap: 8px;
}
.ai-risk__thumb {
  width: 56px;
  height: 56px;
  border-radius: 12px;
  overflow: hidden;
  background: color-mix(in srgb, var(--ods-color-danger) 6%, transparent);
  display: grid;
  place-items: center;
  flex: 0 0 auto;
}
.ai-risk__img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.ai-risk__ph {
  font-size: 10px;
  font-weight: 700;
  color: color-mix(in srgb, var(--ods-color-danger) 55%, white);
}
.ai-risk__chev {
  width: 32px;
  height: 32px;
  border-radius: 999px;
  display: grid;
  place-items: center;
  font-size: 18px;
  font-weight: 700;
  line-height: 1;
  color: var(--ods-color-danger);
  background: var(--ods-color-white);
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
}
</style>
