<script setup lang="ts">
import { computed } from 'vue'

import {
  LABEL_RECENT_AI,
  LABEL_RECENT_AI_ALL,
  MSG_RECENT_AI_EMPTY,
  MSG_RECENT_AI_LOADING,
  type RecentAiCardItem,
} from '@/views/observation/observationHomeCopy'

const props = withDefaults(
  defineProps<{
    items?: RecentAiCardItem[] | null
    loading?: boolean
  }>(),
  {
    items: null,
    loading: false,
  },
)

const emit = defineEmits<{
  openAll: []
  select: [id: string]
}>()

const cards = computed((): RecentAiCardItem[] => props.items ?? [])

const isEmpty = computed(() => !props.loading && cards.value.length === 0)
</script>

<template>
  <div class="recent-ai" :aria-label="LABEL_RECENT_AI">
    <header class="recent-ai__head">
      <h3 class="recent-ai__title">{{ LABEL_RECENT_AI }}</h3>
      <button
        type="button"
        class="recent-ai__all"
        @click="emit('openAll')"
      >
        {{ LABEL_RECENT_AI_ALL }}
      </button>
    </header>

    <div
      v-if="loading || isEmpty"
      class="recent-ai__panel"
      role="status"
    >
      <p class="recent-ai__hint">
        {{ loading ? MSG_RECENT_AI_LOADING : MSG_RECENT_AI_EMPTY }}
      </p>
    </div>

    <div
      v-else
      class="recent-ai__panel"
    >
      <div class="recent-ai__track" role="list">
        <button
          v-for="c in cards"
          :key="c.id"
          type="button"
          class="ai-card"
          role="listitem"
          @click="emit('select', c.id)"
        >
          <div class="ai-card__thumb" aria-hidden="true">
            <img
              v-if="c.thumbUrl"
              class="ai-card__img"
              :src="c.thumbUrl"
              alt=""
            >
            <span v-else class="ai-card__ph">AI</span>
          </div>
          <div class="ai-card__body">
            <div class="ai-card__row">
              <p class="ai-card__name">{{ c.title }}</p>
              <p v-if="c.confidencePct != null" class="ai-card__conf">
                {{ c.confidencePct }}%
              </p>
            </div>
            <p class="ai-card__target">{{ c.targetLabel }}</p>
            <p class="ai-card__time">{{ c.timeLabel }}</p>
          </div>
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.recent-ai {
  display: flex;
  flex-direction: column;
  gap: var(--ods-form-label-gap, var(--ods-space-8));
}
.recent-ai__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ods-space-8);
  padding: 0;
}
.recent-ai__title {
  margin: 0;
  font: var(--ods-font-card-section);
  color: var(--ods-color-text);
}
.recent-ai__all {
  margin: 0;
  padding: 0;
  border: none;
  background: transparent;
  font: var(--ods-font-card-emphasis);
  color: var(--ods-color-primary);
  cursor: pointer;
}
.recent-ai__panel {
  margin: 0;
  padding: var(--ods-space-12);
  border-radius: var(--ods-radius-card);
  background: var(--ods-color-white);
  border: 1px solid var(--ods-color-gray-100);
  box-shadow: var(--ods-shadow-card);
}
.recent-ai__hint {
  margin: 0;
  font: var(--ods-font-form-help);
  font-weight: 600;
  color: var(--ods-color-text-secondary);
}
.recent-ai__track {
  display: flex;
  gap: var(--ods-space-8);
  overflow-x: auto;
  margin: 0 calc(-1 * var(--ods-space-4));
  padding: 0 var(--ods-space-4);
  scroll-snap-type: x mandatory;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
}
.recent-ai__track::-webkit-scrollbar {
  display: none;
}
.ai-card {
  flex: 0 0 auto;
  width: 158px;
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: var(--ods-space-8);
  margin: 0;
  padding: var(--ods-space-8);
  border: 1px solid var(--ods-color-gray-100);
  border-radius: var(--ods-radius-button);
  background: var(--ods-color-white);
  box-shadow: none;
  text-align: left;
  cursor: pointer;
  scroll-snap-align: start;
}
.ai-card__thumb {
  flex: 0 0 auto;
  width: var(--ods-touch-min);
  height: var(--ods-touch-min);
  border-radius: var(--ods-radius-button);
  overflow: hidden;
  background: color-mix(in srgb, var(--ods-color-primary) 8%, white);
  display: grid;
  place-items: center;
}
.ai-card__img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.ai-card__ph {
  font: var(--ods-font-card-meta);
  font-weight: 800;
  color: color-mix(in srgb, var(--ods-color-primary) 55%, white);
}
.ai-card__body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-4);
}
.ai-card__row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--ods-space-4);
  min-width: 0;
}
.ai-card__name {
  margin: 0;
  min-width: 0;
  font: var(--ods-font-card-body);
  color: var(--ods-color-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.ai-card__conf {
  margin: 0;
  flex: 0 0 auto;
  font: var(--ods-font-card-emphasis);
  color: var(--ods-color-primary);
  font-variant-numeric: tabular-nums;
}
.ai-card__target,
.ai-card__time {
  margin: 0;
  font: var(--ods-font-card-help);
  color: var(--ods-color-text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
