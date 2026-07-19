<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'

import iconClipboard from '@/assets/ods/work-log/icon-clipboard.svg'
import iconPlus from '@/assets/ods/work-log/icon-plus.svg'
import {
  MSG_TIMELINE_EMPTY,
  type DailyTimelineItem,
} from '@/views/work-log/workLogConstants'

/** 더보기(···) 전용 폭 — 작업 박스와 겹치지 않음 */
const MORE_GUTTER_PX = 28

const props = defineProps<{
  items: readonly DailyTimelineItem[]
  selectedId: string | null
}>()

const emit = defineEmits<{
  select: [id: string]
  add: []
}>()

const isEmpty = computed(() => props.items.length === 0)

const scrollEl = ref<HTMLElement | null>(null)
const canScrollMore = ref(false)

function updateOverflow() {
  const el = scrollEl.value
  if (!el) {
    canScrollMore.value = false
    return
  }
  canScrollMore.value = el.scrollWidth - el.scrollLeft - el.clientWidth > 8
}

watch(
  () => props.selectedId,
  async (id) => {
    if (!id) return
    await nextTick()
    const btn = scrollEl.value?.querySelector<HTMLElement>(`[data-tl-id="${id}"]`)
    btn?.scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' })
    updateOverflow()
  },
)

watch(
  () => props.items.length,
  async () => {
    await nextTick()
    updateOverflow()
  },
)

onMounted(() => {
  updateOverflow()
  scrollEl.value?.addEventListener('scroll', updateOverflow, { passive: true })
  window.addEventListener('resize', updateOverflow)
})

onUnmounted(() => {
  scrollEl.value?.removeEventListener('scroll', updateOverflow)
  window.removeEventListener('resize', updateOverflow)
})

const showMoreHint = computed(
  () => props.items.length >= 4 || canScrollMore.value,
)
</script>

<template>
  <section class="tl" aria-label="작업 타임라인">
    <div class="tl__head">
      <h2 class="tl__title">작업 타임라인</h2>
      <button
        v-if="!isEmpty"
        type="button"
        class="tl__add"
        @click="emit('add')"
      >
        <img :src="iconPlus" alt="" />
        작업 추가
      </button>
    </div>

    <div v-if="isEmpty" class="tl__empty">
      <img class="tl__empty-ico" :src="iconClipboard" alt="" />
      <p class="tl__empty-msg">{{ MSG_TIMELINE_EMPTY }}</p>
    </div>

    <div
      v-else
      class="tl__wrap"
      :class="{ 'tl__wrap--more': showMoreHint }"
      :style="showMoreHint ? { '--tl-more-gutter': `${MORE_GUTTER_PX}px` } : undefined"
    >
      <div ref="scrollEl" class="tl__rail" role="list" @scroll="updateOverflow">
        <div class="tl__track">
          <div class="tl__axis" aria-hidden="true" />

          <button
            v-for="it in items"
            :key="it.id"
            type="button"
            role="listitem"
            class="tl__node"
            :class="[`tl__node--${it.tone}`, { 'tl__node--on': selectedId === it.id }]"
            :data-tl-id="it.id"
            :aria-pressed="selectedId === it.id"
            @click="emit('select', it.id)"
          >
            <span class="tl__chip">
              <img class="tl__ico" :src="it.icon" alt="" />
              <span class="tl__name">{{ it.title }}</span>
              <span class="tl__time">{{ it.time }}</span>
            </span>
            <span class="tl__dot" aria-hidden="true" />
          </button>
        </div>
      </div>

      <div
        v-if="showMoreHint"
        class="tl__more"
        aria-hidden="true"
        title="옆으로 밀어 더 보기"
      >
        <span class="tl__more-dot" />
        <span class="tl__more-dot" />
        <span class="tl__more-dot" />
      </div>
    </div>
  </section>
</template>

<style scoped>
.tl {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-12);
  padding: var(--ods-space-12) var(--ods-space-16);
  border-radius: var(--ods-radius-card);
  background: var(--ods-color-white);
  border: 1px solid var(--ods-color-border);
  box-shadow: var(--ods-shadow-card);
}

.tl__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.tl__title {
  margin: 0;
  font: var(--ods-font-headline);
  font-size: 16px;
  color: var(--ods-color-text);
}

.tl__add {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  margin: 0;
  padding: var(--ods-space-4);
  border: none;
  background: transparent;
  font: var(--ods-font-body-2);
  font-weight: 700;
  color: var(--ods-color-primary);
  cursor: pointer;
}

.tl__add img {
  width: 13px;
  height: 13px;
}

.tl__empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--ods-space-12);
  padding: var(--ods-space-20) var(--ods-space-12);
  text-align: center;
}

.tl__empty-ico {
  width: 56px;
  height: 56px;
}

.tl__empty-msg {
  margin: 0;
  max-width: 280px;
  font: var(--ods-font-body-2);
  color: var(--ods-color-text-secondary);
  line-height: 1.55;
  white-space: pre-line;
}

.tl__wrap {
  --tl-more-gutter: 0px;
  display: flex;
  align-items: flex-start;
  gap: 0;
  min-width: 0;
}

.tl__rail {
  flex: 1 1 auto;
  min-width: 0;
  overflow-x: auto;
  overflow-y: hidden;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
}

.tl__wrap--more .tl__rail {
  -webkit-mask-image: linear-gradient(
    to right,
    #000 0%,
    #000 calc(100% - 24px),
    transparent 100%
  );
  mask-image: linear-gradient(
    to right,
    #000 0%,
    #000 calc(100% - 24px),
    transparent 100%
  );
}

.tl__rail::-webkit-scrollbar {
  display: none;
}

.tl__track {
  position: relative;
  display: flex;
  align-items: flex-start;
  gap: 12px;
  min-width: max-content;
  padding: 0;
}

.tl__axis {
  position: absolute;
  left: 0;
  right: 0;
  /* 도트 center = bottom 3px + 5px */
  bottom: 7px;
  height: 2px;
  border-radius: 1px;
  background: #d0d0d0;
  pointer-events: none;
  z-index: 0;
}

.tl__node {
  position: relative;
  z-index: 1;
  flex: 0 0 80px;
  width: 80px;
  display: block;
  margin: 0;
  /* 칩(76) + 도트 영역(16) */
  padding: 0 0 16px;
  border: none;
  background: transparent;
  cursor: pointer;
}

.tl__chip {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: space-between;
  gap: 2px;
  width: 80px;
  height: 76px;
  padding: 8px 5px 6px;
  border-radius: 14px;
  box-sizing: border-box;
  overflow: hidden;
  transition:
    background 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease;
}

.tl__node--mint .tl__chip {
  background: color-mix(in srgb, #81c784 14%, #ffffff);
}
.tl__node--forest .tl__chip {
  background: color-mix(in srgb, var(--ods-color-primary) 7%, #ffffff);
}
.tl__node--gold .tl__chip {
  background: color-mix(in srgb, #ffca28 16%, #ffffff);
}
.tl__node--violet .tl__chip {
  background: color-mix(in srgb, #9575cd 11%, #ffffff);
}

.tl__node--on .tl__chip {
  background: var(--ods-color-primary);
  box-shadow: 0 4px 12px color-mix(in srgb, var(--ods-color-primary) 32%, transparent);
}

.tl__node--on .tl__name,
.tl__node--on .tl__time {
  color: #fff;
}

.tl__node--on .tl__ico {
  filter: brightness(0) invert(1);
}

.tl__ico {
  flex: 0 0 auto;
  width: 20px;
  height: 20px;
}

.tl__name {
  flex: 1 1 auto;
  width: 100%;
  min-height: 0;
  margin: 0;
  font-size: 11px;
  font-weight: 700;
  line-height: 1.25;
  color: var(--ods-color-text);
  text-align: center;
  overflow: hidden;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  word-break: break-all;
}

.tl__time {
  flex: 0 0 auto;
  width: 100%;
  margin: 0;
  font-size: 11px;
  font-weight: 600;
  line-height: 1.2;
  color: var(--ods-color-text-secondary);
  text-align: center;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.tl__dot {
  position: absolute;
  left: 50%;
  bottom: 3px;
  z-index: 1;
  width: 10px;
  height: 10px;
  margin: 0;
  border-radius: 50%;
  box-sizing: border-box;
  background: var(--ods-color-primary);
  border: 2px solid var(--ods-color-primary);
  transform: translateX(-50%);
}

.tl__node--gold .tl__dot {
  background: #f9a825;
  border-color: #f9a825;
}
.tl__node--violet .tl__dot {
  background: #7e57c2;
  border-color: #7e57c2;
}

/* 선택 시에도 크기 고정 — 링만 강조 */
.tl__node--on .tl__dot {
  width: 10px;
  height: 10px;
  background: #fff;
  border: 2.5px solid var(--ods-color-primary);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--ods-color-primary) 35%, transparent);
}

.tl__more {
  flex: 0 0 var(--tl-more-gutter, 28px);
  width: var(--tl-more-gutter, 28px);
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: center;
  gap: 4px;
  height: 76px;
  box-sizing: border-box;
  user-select: none;
  pointer-events: none;
}

.tl__more-dot {
  display: block;
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: #616161;
}

.tl__more-dot:nth-child(1) {
  opacity: 0.4;
}
.tl__more-dot:nth-child(2) {
  opacity: 0.22;
}
.tl__more-dot:nth-child(3) {
  opacity: 0.1;
}
</style>
