<script setup lang="ts">
import { computed } from 'vue'

import thumb1 from '@/assets/ods/scr004/thumb-recent-ai-1.jpg'
import thumb2 from '@/assets/ods/scr004/thumb-recent-ai-2.jpg'
import thumb3 from '@/assets/ods/scr004/thumb-recent-ai-3.jpg'
import OdsEmptyState from '@/components/ods/OdsEmptyState.vue'
import {
  LABEL_RECENT_AI,
  LABEL_RECENT_AI_ALL,
  MSG_RECENT_AI_EMPTY,
  MSG_RECENT_AI_LOADING,
  RECENT_AI_SKELETON_ITEMS,
  type RecentAiCardItem,
} from '@/views/observation/observationHomeCopy'

const SKELETON_THUMBS = [thumb1, thumb2, thumb3] as const

const props = withDefaults(
  defineProps<{
    items?: RecentAiCardItem[] | null
    loading?: boolean
    /** API 전: 시안 뼈대 샘플 표시 */
    showSkeleton?: boolean
  }>(),
  {
    items: null,
    loading: false,
    showSkeleton: true,
  },
)

const emit = defineEmits<{
  openAll: []
  select: [id: string]
}>()

const cards = computed((): RecentAiCardItem[] => {
  if (props.items && props.items.length > 0) return props.items
  if (props.showSkeleton && !props.loading) {
    return RECENT_AI_SKELETON_ITEMS.map((item, i) => ({
      ...item,
      thumbUrl: item.thumbUrl || SKELETON_THUMBS[i] || SKELETON_THUMBS[0],
    }))
  }
  return []
})

const isEmpty = computed(() => !props.loading && cards.value.length === 0)
</script>

<template>
  <section class="recent-ai" :aria-label="LABEL_RECENT_AI">
    <header class="recent-ai__head">
      <h2 class="recent-ai__title">{{ LABEL_RECENT_AI }}</h2>
      <button
        type="button"
        class="recent-ai__all"
        @click="emit('openAll')"
      >
        {{ LABEL_RECENT_AI_ALL }}
      </button>
    </header>

    <p v-if="loading" class="recent-ai__hint" role="status">
      {{ MSG_RECENT_AI_LOADING }}
    </p>

    <OdsEmptyState
      v-else-if="isEmpty"
      compact
      :title="MSG_RECENT_AI_EMPTY"
    />

    <div
      v-else
      class="recent-ai__track"
      role="list"
    >
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
            <p class="ai-card__conf">{{ c.confidencePct }}%</p>
          </div>
          <p class="ai-card__target">{{ c.targetLabel }}</p>
          <p class="ai-card__time">{{ c.timeLabel }}</p>
        </div>
      </button>
    </div>
  </section>
</template>

<style scoped>
.recent-ai {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-10);
}
.recent-ai__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ods-space-8);
  padding: 0 2px;
}
.recent-ai__title {
  margin: 0;
  font: var(--ods-font-headline);
  font-size: 15px;
  font-weight: 800;
  color: var(--ods-color-text);
  letter-spacing: -0.02em;
}
.recent-ai__all {
  margin: 0;
  padding: 0;
  border: none;
  background: transparent;
  font: var(--ods-font-caption);
  font-weight: 700;
  color: var(--ods-color-primary);
  cursor: pointer;
}
.recent-ai__hint {
  margin: 0;
  padding: var(--ods-space-12);
  border-radius: var(--ods-radius-card);
  background: var(--ods-color-white);
  border: 1px solid var(--ods-color-gray-100);
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
}
.recent-ai__track {
  display: flex;
  gap: 10px;
  overflow-x: auto;
  padding: 2px 2px 4px;
  scroll-snap-type: x mandatory;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
}
.recent-ai__track::-webkit-scrollbar {
  display: none;
}
/* 시안: 썸네일 좌 · 텍스트 우 가로 카드 */
.ai-card {
  flex: 0 0 auto;
  width: 158px;
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 8px;
  margin: 0;
  padding: 8px;
  border: 1px solid var(--ods-color-gray-100);
  border-radius: 12px;
  background: var(--ods-color-white);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  text-align: left;
  cursor: pointer;
  scroll-snap-align: start;
}
.ai-card__thumb {
  flex: 0 0 auto;
  width: 44px;
  height: 44px;
  border-radius: 10px;
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
  font-size: 10px;
  font-weight: 800;
  color: color-mix(in srgb, var(--ods-color-primary) 55%, white);
}
.ai-card__body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.ai-card__row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 4px;
  min-width: 0;
}
.ai-card__name {
  margin: 0;
  min-width: 0;
  font-size: 13px;
  font-weight: 800;
  line-height: 1.25;
  letter-spacing: -0.02em;
  color: var(--ods-color-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.ai-card__conf {
  margin: 0;
  flex: 0 0 auto;
  font-size: 12px;
  font-weight: 800;
  line-height: 1.2;
  color: var(--ods-color-primary);
  font-variant-numeric: tabular-nums;
}
.ai-card__target,
.ai-card__time {
  margin: 0;
  font-size: 10px;
  font-weight: 500;
  line-height: 1.3;
  color: var(--ods-color-text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
