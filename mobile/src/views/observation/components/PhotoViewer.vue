<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'

import { resolveMediaUrl } from '@/utils/mediaUrl'

export type PhotoViewerItem = {
  original_url?: string | null
  thumb_url?: string | null
  display_nm?: string | null
}

const props = defineProps<{
  open: boolean
  photos: PhotoViewerItem[]
  index: number
}>()

const emit = defineEmits<{
  close: []
  'update:index': [value: number]
}>()

const imgLoading = ref(false)
const imgError = ref(false)
const touchStartX = ref<number | null>(null)
const historyPushed = ref(false)
let ignoreNextPop = false

const safeIndex = computed(() => {
  if (!props.photos.length) return 0
  return Math.min(Math.max(0, props.index), props.photos.length - 1)
})

const current = computed(() => props.photos[safeIndex.value] ?? null)

const imageSrc = computed(() => {
  if (!props.open) return ''
  const p = current.value
  if (!p) return ''
  return resolveMediaUrl(p.original_url || p.thumb_url)
})

const counter = computed(() => {
  if (!props.photos.length) return '0 / 0'
  return `${safeIndex.value + 1} / ${props.photos.length}`
})

const canPrev = computed(() => safeIndex.value > 0)
const canNext = computed(() => safeIndex.value < props.photos.length - 1)

function lockBody(lock: boolean) {
  document.body.style.overflow = lock ? 'hidden' : ''
}

function closeViewer() {
  emit('close')
}

function goPrev() {
  if (!canPrev.value) return
  emit('update:index', safeIndex.value - 1)
}

function goNext() {
  if (!canNext.value) return
  emit('update:index', safeIndex.value + 1)
}

function onKeydown(ev: KeyboardEvent) {
  if (!props.open) return
  if (ev.key === 'Escape') {
    ev.preventDefault()
    closeViewer()
  } else if (ev.key === 'ArrowLeft') {
    ev.preventDefault()
    goPrev()
  } else if (ev.key === 'ArrowRight') {
    ev.preventDefault()
    goNext()
  }
}

function onPopState() {
  if (ignoreNextPop) {
    ignoreNextPop = false
    return
  }
  historyPushed.value = false
  if (props.open) emit('close')
}

function onTouchStart(ev: TouchEvent) {
  touchStartX.value = ev.changedTouches[0]?.clientX ?? null
}

function onTouchEnd(ev: TouchEvent) {
  const start = touchStartX.value
  touchStartX.value = null
  if (start == null) return
  const end = ev.changedTouches[0]?.clientX ?? start
  const dx = end - start
  if (Math.abs(dx) < 48) return
  if (dx > 0) goPrev()
  else goNext()
}

function onImgLoad() {
  imgLoading.value = false
  imgError.value = false
}

function onImgError() {
  imgLoading.value = false
  imgError.value = true
}

watch(
  () => [props.open, props.index, imageSrc.value] as const,
  ([open]) => {
    if (open) {
      imgLoading.value = true
      imgError.value = false
    }
  },
)

watch(
  () => props.open,
  (open) => {
    lockBody(open)
    if (open) {
      if (!historyPushed.value) {
        history.pushState({ photoViewer: true }, '')
        historyPushed.value = true
      }
      return
    }
    if (historyPushed.value) {
      historyPushed.value = false
      if (history.state && (history.state as { photoViewer?: boolean }).photoViewer) {
        ignoreNextPop = true
        history.back()
      }
    }
  },
)

onMounted(() => {
  window.addEventListener('keydown', onKeydown)
  window.addEventListener('popstate', onPopState)
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
  window.removeEventListener('popstate', onPopState)
  lockBody(false)
})
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="viewer"
      role="dialog"
      aria-modal="true"
      aria-label="사진 확대 보기"
      @touchstart.passive="onTouchStart"
      @touchend.passive="onTouchEnd"
    >
      <header class="viewer__bar">
        <p class="viewer__counter">{{ counter }}</p>
        <button type="button" class="viewer__close" aria-label="닫기" @click="closeViewer">
          닫기
        </button>
      </header>

      <div class="viewer__stage">
        <button
          type="button"
          class="viewer__nav viewer__nav--prev"
          :disabled="!canPrev"
          aria-label="이전 사진"
          @click="goPrev"
        >
          ‹
        </button>

        <div class="viewer__frame">
          <p v-if="imgLoading && !imgError" class="viewer__status">불러오는 중…</p>
          <div v-if="imgError" class="viewer__fail" role="alert">
            <p>사진을 불러오지 못했습니다.</p>
            <button type="button" class="viewer__fail-btn" @click="closeViewer">닫기</button>
          </div>
          <img
            v-show="!imgError"
            class="viewer__img"
            :src="imageSrc"
            :alt="current?.display_nm || '관찰 사진'"
            @load="onImgLoad"
            @error="onImgError"
          >
        </div>

        <button
          type="button"
          class="viewer__nav viewer__nav--next"
          :disabled="!canNext"
          aria-label="다음 사진"
          @click="goNext"
        >
          ›
        </button>
      </div>

      <p class="viewer__caption" :title="current?.display_nm || ''">
        {{ current?.display_nm || '' }}
      </p>
    </div>
  </Teleport>
</template>

<style scoped>
.viewer {
  position: fixed;
  inset: 0;
  z-index: 200;
  display: flex;
  flex-direction: column;
  background: color-mix(in srgb, var(--ods-color-gray-900) 96%, transparent);
  padding: env(safe-area-inset-top) env(safe-area-inset-right) env(safe-area-inset-bottom)
    env(safe-area-inset-left);
}
.viewer__bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ods-space-12);
  min-height: var(--ods-button-height);
  padding: var(--ods-space-8) var(--ods-page-padding-x, var(--ods-space-16));
  flex: 0 0 auto;
}
.viewer__counter {
  margin: 0;
  color: var(--ods-color-white);
  font: var(--ods-font-form-value);
  font-weight: 700;
}
.viewer__close {
  min-height: var(--ods-touch-min);
  min-width: 64px;
  border: none;
  border-radius: var(--ods-radius-button);
  background: color-mix(in srgb, var(--ods-color-white) 14%, transparent);
  color: var(--ods-color-white);
  font: var(--ods-font-form-value);
  font-weight: 700;
  cursor: pointer;
}
.viewer__stage {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: var(--ods-touch-min) 1fr var(--ods-touch-min);
  align-items: center;
  gap: var(--ods-space-4);
  padding: 0 var(--ods-space-8);
}
.viewer__frame {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}
.viewer__img {
  max-width: 100%;
  max-height: 100%;
  width: auto;
  height: auto;
  object-fit: contain;
  display: block;
}
.viewer__status,
.viewer__fail {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--ods-space-12);
  color: var(--ods-color-white);
  font: var(--ods-font-form-value);
  text-align: center;
  padding: var(--ods-space-16);
}
.viewer__fail-btn {
  min-height: var(--ods-touch-min);
  padding: 0 var(--ods-space-16);
  border: none;
  border-radius: var(--ods-radius-button);
  background: var(--ods-color-primary);
  color: var(--ods-color-white);
  font: var(--ods-font-form-value);
  font-weight: 700;
  cursor: pointer;
}
.viewer__nav {
  width: var(--ods-touch-min);
  height: var(--ods-touch-min);
  border: none;
  border-radius: var(--ods-radius-badge);
  background: color-mix(in srgb, var(--ods-color-white) 12%, transparent);
  color: var(--ods-color-white);
  font: var(--ods-font-title-1);
  line-height: 1;
  cursor: pointer;
}
.viewer__nav:disabled {
  opacity: 0.25;
  cursor: not-allowed;
}
.viewer__caption {
  margin: 0;
  padding: var(--ods-space-8) var(--ods-page-padding-x, var(--ods-space-16)) var(--ods-space-16);
  color: color-mix(in srgb, var(--ods-color-white) 85%, transparent);
  font: var(--ods-font-card-help);
  text-align: center;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  flex: 0 0 auto;
}
</style>
