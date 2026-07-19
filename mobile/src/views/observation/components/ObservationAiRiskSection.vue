<script setup lang="ts">
import { computed } from 'vue'

import iconWarn from '@/assets/ods/scr004/icon-kpi-warn.svg'
import thumbSkeleton from '@/assets/ods/scr004/thumb-ai-risk-skeleton.jpg'
import {
  AI_RISK_SKELETON_ITEM,
  LABEL_AI_RISK,
  LABEL_AI_RISK_BADGE,
  MSG_AI_RISK_EMPTY,
  MSG_AI_RISK_LOADING,
  type AiRiskCardItem,
} from '@/views/observation/observationHomeCopy'

const props = withDefaults(
  defineProps<{
    item?: AiRiskCardItem | null
    loading?: boolean
    /** API 전: 시안 뼈대 샘플 표시 */
    showSkeleton?: boolean
  }>(),
  {
    item: null,
    loading: false,
    showSkeleton: true,
  },
)

const emit = defineEmits<{
  open: []
}>()

const card = computed((): AiRiskCardItem | null => {
  if (props.item) return props.item
  if (props.showSkeleton && !props.loading) {
    return {
      ...AI_RISK_SKELETON_ITEM,
      thumbUrl: AI_RISK_SKELETON_ITEM.thumbUrl || thumbSkeleton,
    }
  }
  return null
})

const metaLabel = computed(() => {
  const c = card.value
  if (!c) return ''
  return `${c.foundCount}건 발견 · ${c.timeLabel}`
})
</script>

<template>
  <section class="ai-risk" :aria-label="LABEL_AI_RISK">
    <p v-if="loading" class="ai-risk__hint" role="status">
      {{ MSG_AI_RISK_LOADING }}
    </p>

    <button
      v-else-if="card"
      type="button"
      class="ai-risk__card"
      @click="emit('open')"
    >
      <div class="ai-risk__main">
        <p class="ai-risk__label">
          <img class="ai-risk__ico" :src="iconWarn" alt="" >
          {{ LABEL_AI_RISK }}
        </p>
        <p class="ai-risk__name">
          <span class="ai-risk__name-text">{{ card.pestName }}</span>
          <span class="ai-risk__badge">{{ LABEL_AI_RISK_BADGE }}</span>
        </p>
        <p class="ai-risk__meta">{{ metaLabel }}</p>
      </div>

      <div class="ai-risk__aside" aria-hidden="true">
        <div class="ai-risk__thumb">
          <img
            v-if="card.thumbUrl"
            class="ai-risk__img"
            :src="card.thumbUrl"
            alt=""
          >
          <span v-else class="ai-risk__ph">병해충</span>
        </div>
        <span class="ai-risk__chev">›</span>
      </div>
    </button>

    <div v-else class="ai-risk__card ai-risk__card--empty" role="status">
      <div class="ai-risk__main">
        <p class="ai-risk__label">
          <img class="ai-risk__ico" :src="iconWarn" alt="" >
          {{ LABEL_AI_RISK }}
        </p>
        <p class="ai-risk__empty">{{ MSG_AI_RISK_EMPTY }}</p>
      </div>
    </div>
  </section>
</template>

<style scoped>
.ai-risk {
  margin: 0;
}
.ai-risk__hint {
  margin: 0;
  padding: var(--ods-space-16);
  border-radius: 16px;
  background: color-mix(in srgb, var(--ods-color-danger) 8%, white);
  border: 1px solid color-mix(in srgb, var(--ods-color-danger) 18%, white);
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
}
.ai-risk__card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ods-space-12);
  width: 100%;
  margin: 0;
  padding: 14px 12px 14px 16px;
  border: 1px solid color-mix(in srgb, var(--ods-color-danger) 20%, white);
  border-radius: 16px;
  background: color-mix(in srgb, var(--ods-color-danger) 7%, white);
  box-shadow: var(--ods-shadow-card);
  text-align: left;
  cursor: pointer;
}
.ai-risk__card--empty {
  cursor: default;
}
.ai-risk__main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.ai-risk__label {
  margin: 0;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  font-weight: 700;
  line-height: 1.2;
  color: var(--ods-color-danger);
}
.ai-risk__ico {
  width: 14px;
  height: 14px;
  display: block;
  flex: 0 0 auto;
}
.ai-risk__name {
  margin: 0;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
}
.ai-risk__name-text {
  font-size: 17px;
  font-weight: 800;
  line-height: 1.25;
  letter-spacing: -0.03em;
  color: var(--ods-color-text);
}
.ai-risk__badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 7px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 800;
  line-height: 1.2;
  color: var(--ods-color-danger);
  background: color-mix(in srgb, var(--ods-color-danger) 14%, white);
}
.ai-risk__meta {
  margin: 0;
  font-size: 12px;
  font-weight: 500;
  line-height: 1.3;
  color: var(--ods-color-text-secondary);
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
  background: color-mix(in srgb, var(--ods-color-danger) 10%, white);
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
