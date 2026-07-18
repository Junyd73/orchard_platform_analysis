<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'

import { observationListThumbSrc } from '@/api/observationPhotos'
import OdsBadge from '@/components/ods/OdsBadge.vue'
import { aiLabel, aiTone } from '@/views/observation/scr004DetailUi'
import type { ObservationListItem } from '@/types/observation'

const props = defineProps<{
  item: ObservationListItem
}>()

const router = useRouter()
const thumbBroken = ref(false)

const thumbSrc = computed(() => observationListThumbSrc(props.item))
const showImage = computed(() => Boolean(thumbSrc.value) && !thumbBroken.value)

function openDetail() {
  void router.push({
    name: 'observation-detail',
    params: { obsId: props.item.obs_id },
  })
}

function openPhotos() {
  void router.push({
    name: 'observation-photos',
    params: { obsId: props.item.obs_id },
  })
}

/** 대표 썸네일 → 사진관리 (사진 있을 때만) */
function onThumbClick(ev: MouseEvent) {
  ev.stopPropagation()
  if (!props.item.has_photo) return
  openPhotos()
}

function onThumbError() {
  thumbBroken.value = true
}

function severityTone(cd: string): 'ok' | 'caution' | 'danger' | 'neutral' {
  if (cd === 'OS010400') return 'danger'
  if (cd === 'OS010300') return 'caution'
  if (cd === 'OS010100') return 'ok'
  return 'neutral'
}
</script>

<template>
  <article class="card">
    <button
      type="button"
      class="thumb"
      :class="{ 'thumb--nav': item.has_photo, 'thumb--static': !item.has_photo }"
      :aria-label="
        item.has_photo
          ? `${item.obs_title || '관찰'} 사진 관리`
          : `${item.obs_title || '관찰'} 사진 없음`
      "
      :disabled="!item.has_photo"
      @click="onThumbClick"
    >
      <img
        v-if="showImage"
        class="thumb__img"
        :src="thumbSrc"
        alt=""
        loading="lazy"
        @error="onThumbError"
      >
      <span v-else-if="item.has_photo" class="thumb__mark">사진</span>
      <span v-else class="thumb__mark thumb__mark--empty">사진 없음</span>
    </button>
    <div
      class="body"
      role="button"
      tabindex="0"
      @click="openDetail"
      @keydown.enter="openDetail"
    >
      <div class="meta">
        <OdsBadge :tone="severityTone(item.severity_cd)">{{ item.severity_nm || '상태' }}</OdsBadge>
        <OdsBadge :tone="aiTone(item.ai_status)">{{ aiLabel(item.ai_status) }}</OdsBadge>
      </div>
      <p class="type">{{ item.target_type_nm || item.obs_type_nm }}</p>
      <h3 class="title">{{ item.obs_title || '(제목 없음)' }}</h3>
      <p class="loc">{{ item.location_text }}</p>
      <p class="date">{{ item.obs_dt }}</p>
    </div>
  </article>
</template>

<style scoped>
.card {
  display: grid;
  grid-template-columns: 88px minmax(0, 1fr);
  gap: var(--ods-space-12);
  padding: var(--ods-space-12);
  background: var(--ods-color-white);
  border: 1px solid var(--ods-color-border);
  border-radius: var(--ods-radius-card);
  box-shadow: var(--ods-shadow-card);
  width: 100%;
  min-width: 0;
  box-sizing: border-box;
  overflow: hidden;
}
.thumb {
  width: 88px;
  height: 88px;
  min-height: 88px;
  border: none;
  border-radius: 12px;
  background: var(--ods-color-gray-100);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  overflow: hidden;
}
.thumb--nav {
  cursor: pointer;
}
.thumb--static {
  cursor: default;
}
.thumb:disabled {
  opacity: 1;
}
.thumb__img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.thumb__mark {
  font: var(--ods-font-caption);
  color: var(--ods-color-primary);
  font-weight: 700;
}
.thumb__mark--empty {
  color: var(--ods-color-gray-500);
  font-weight: 400;
}
.body {
  min-width: 0;
  overflow: hidden;
  text-align: left;
  cursor: pointer;
  border: none;
  background: transparent;
  padding: 0;
}
.meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--ods-space-4);
}
.type {
  margin: var(--ods-space-8) 0 0;
  font: var(--ods-font-caption);
  color: var(--ods-color-secondary);
  font-weight: 700;
}
.title {
  margin: var(--ods-space-4) 0 0;
  font: var(--ods-font-headline);
  color: var(--ods-color-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.loc,
.date {
  margin: var(--ods-space-4) 0 0;
  font: var(--ods-font-body-2);
  color: var(--ods-color-text-secondary);
}
</style>
