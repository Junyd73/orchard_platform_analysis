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
  <div class="ai-risk" :aria-label="LABEL_AI_RISK">
    <header class="ai-risk__head">
      <h3 class="ai-risk__title">
        <img class="ai-risk__ico" :src="iconWarn" alt="" aria-hidden="true">
        {{ LABEL_AI_RISK }}
      </h3>
      <p v-if="!loading && cards.length" class="ai-risk__count">
        {{ cards.length }}건
      </p>
    </header>

    <div
      v-if="loading || isEmpty"
      class="ai-risk__panel ai-risk__panel--empty"
      role="status"
    >
      <p class="ai-risk__hint">
        {{ loading ? MSG_AI_RISK_LOADING : MSG_AI_RISK_EMPTY }}
      </p>
    </div>

    <div
      v-else
      class="ai-risk__panel"
    >
      <div class="ai-risk__track" role="list">
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
    </div>
  </div>
</template>

<style scoped>
.ai-risk {
  display: flex;
  flex-direction: column;
  gap: var(--ods-form-label-gap, var(--ods-space-8));
  margin: 0;
}
.ai-risk__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ods-space-8);
  padding: 0;
}
.ai-risk__title {
  margin: 0;
  display: inline-flex;
  align-items: center;
  gap: var(--ods-space-4);
  font: var(--ods-font-card-section);
  color: var(--ods-color-danger);
}
.ai-risk__ico {
  width: var(--ods-icon-sm);
  height: var(--ods-icon-sm);
  display: block;
  flex: 0 0 auto;
}
.ai-risk__count {
  margin: 0;
  font: var(--ods-font-card-emphasis);
  color: var(--ods-color-text-secondary);
}
.ai-risk__panel {
  margin: 0;
  padding: var(--ods-space-12);
  border-radius: var(--ods-radius-card);
  background: var(--ods-color-white);
  border: 1px solid var(--ods-color-gray-100);
  box-shadow: var(--ods-shadow-card);
}
.ai-risk__panel--empty {
  background: color-mix(in srgb, var(--ods-color-danger) 4%, transparent);
  border-color: color-mix(in srgb, var(--ods-color-danger) 10%, transparent);
  box-shadow: none;
}
.ai-risk__hint {
  margin: 0;
  font: var(--ods-font-form-help);
  font-weight: 600;
  color: var(--ods-color-text-secondary);
}
.ai-risk__track {
  display: flex;
  gap: var(--ods-space-8);
  overflow-x: auto;
  margin: 0 calc(-1 * var(--ods-space-4));
  padding: 0 var(--ods-space-4);
  scroll-snap-type: x mandatory;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
}
.ai-risk__track::-webkit-scrollbar {
  display: none;
}
.ai-risk__card {
  flex: 0 0 auto;
  width: min(268px, calc(100vw - 4 * var(--ods-space-16)));
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ods-space-12);
  margin: 0;
  padding: var(--ods-space-12) var(--ods-space-12) var(--ods-space-12) var(--ods-space-16);
  border: 1px solid color-mix(in srgb, var(--ods-color-danger) 12%, transparent);
  border-radius: var(--ods-radius-card);
  background: color-mix(in srgb, var(--ods-color-danger) 3.5%, transparent);
  box-shadow: none;
  text-align: left;
  cursor: pointer;
  scroll-snap-align: start;
}
.ai-risk__main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-4);
}
.ai-risk__name {
  margin: 0;
  font: var(--ods-font-form-label);
  color: var(--ods-color-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ai-risk__meta {
  margin: 0;
  display: inline-flex;
  align-items: center;
  gap: var(--ods-space-4);
  font: var(--ods-font-card-meta);
}
.ai-risk__sev {
  display: inline-flex;
  align-items: center;
  padding: var(--ods-space-4) var(--ods-space-8);
  border-radius: var(--ods-radius-button);
  font: var(--ods-font-card-emphasis);
  color: var(--ods-color-danger);
  background: color-mix(in srgb, var(--ods-color-danger) 8%, transparent);
}
.ai-risk__date {
  color: var(--ods-color-text-secondary);
  font-weight: 500;
}
.ai-risk__aside {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  gap: var(--ods-space-8);
}
.ai-risk__thumb {
  width: var(--ods-thumb-sm);
  height: var(--ods-thumb-sm);
  border-radius: var(--ods-radius-button);
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
  font: var(--ods-font-card-meta);
  font-weight: 700;
  color: color-mix(in srgb, var(--ods-color-danger) 55%, white);
}
.ai-risk__chev {
  width: var(--ods-hit-sm);
  height: var(--ods-hit-sm);
  border-radius: var(--ods-radius-badge);
  display: grid;
  place-items: center;
  font: var(--ods-font-title-2);
  font-weight: 700;
  line-height: 1;
  color: var(--ods-color-danger);
  background: var(--ods-color-white);
  box-shadow: var(--ods-shadow-card);
}
</style>
