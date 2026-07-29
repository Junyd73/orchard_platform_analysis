<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'

import { observationListThumbSrc } from '@/api/observationPhotos'
import { resolveMediaUrl } from '@/utils/mediaUrl'
import type { ObservationTrackItem } from '@/types/observation'

const props = defineProps<{
  open: boolean
  items: ObservationTrackItem[]
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
  if (!props.items.length) return 0
  return Math.min(Math.max(0, props.index), props.items.length - 1)
})

const current = computed(() => props.items[safeIndex.value] ?? null)

const counter = computed(() => {
  if (!props.items.length) return '0 / 0'
  return `${safeIndex.value + 1} / ${props.items.length}`
})

const canPrev = computed(() => safeIndex.value > 0)
const canNext = computed(() => safeIndex.value < props.items.length - 1)

function photoIdFromPath(path?: string | null): string | null {
  const raw = String(path || '').trim()
  if (!raw) return null
  const name = raw.split('/').pop() || ''
  const stem = name.replace(/\.[a-z0-9]{2,5}$/i, '')
  return stem || null
}

const imageSrc = computed(() => {
  if (!props.open) return ''
  const item = current.value
  if (!item) return ''
  const photoId = item.thumb_photo_id || photoIdFromPath(item.thumb_path)
  if (photoId) {
    return resolveMediaUrl(
      `/farms/${encodeURIComponent(item.farm_cd)}/observations/${encodeURIComponent(item.obs_id)}/photos/${encodeURIComponent(photoId)}/original`,
    )
  }
  return observationListThumbSrc({
    farm_cd: item.farm_cd,
    obs_id: item.obs_id,
    thumb_photo_id: item.thumb_photo_id,
    thumb_path: item.thumb_path,
  })
})

const hasPhoto = computed(() => Boolean(imageSrc.value))

function fmtNum(v: number | null | undefined): string {
  if (v == null || Number.isNaN(Number(v))) return '—'
  const n = Number(v)
  return Number.isInteger(n) ? String(n) : n.toFixed(1)
}

function fmtDelta(v: number | null | undefined): string {
  if (v == null || Number.isNaN(Number(v))) return ''
  const n = Number(v)
  const sign = n > 0 ? '+' : ''
  return `${sign}${fmtNum(n)}`
}

const measureLine = computed(() => {
  const item = current.value
  if (!item) return ''
  return `${fmtNum(item.width_mm)}×${fmtNum(item.height_mm)} mm · 둘레 ${fmtNum(item.circumference_mm)} · 무게 ${fmtNum(item.estimated_weight_g)} g`
})

const deltaLine = computed(() => {
  const item = current.value
  if (!item || item.delta_width_mm == null) return ''
  return `이전 대비 Δ 가로 ${fmtDelta(item.delta_width_mm)} · 둘레 ${fmtDelta(item.delta_circumference_mm)}`
})

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
      imgLoading.value = Boolean(imageSrc.value)
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
        history.pushState({ fruitTrackViewer: true }, '')
        historyPushed.value = true
      }
      return
    }
    if (historyPushed.value) {
      historyPushed.value = false
      if (history.state && (history.state as { fruitTrackViewer?: boolean }).fruitTrackViewer) {
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
      aria-label="추적 사진 보기"
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
          aria-label="이전"
          @click="goPrev"
        >
          ‹
        </button>

        <div class="viewer__frame">
          <template v-if="hasPhoto">
            <p v-if="imgLoading && !imgError" class="viewer__status">불러오는 중…</p>
            <div v-if="imgError" class="viewer__fail" role="alert">
              <p>사진을 불러오지 못했습니다.</p>
            </div>
            <img
              v-show="!imgError"
              class="viewer__img"
              :src="imageSrc"
              :alt="current?.obs_title || '추적 사진'"
              @load="onImgLoad"
              @error="onImgError"
            >
          </template>
          <div v-else class="viewer__empty">
            <p>등록된 사진이 없습니다.</p>
          </div>
        </div>

        <button
          type="button"
          class="viewer__nav viewer__nav--next"
          :disabled="!canNext"
          aria-label="다음"
          @click="goNext"
        >
          ›
        </button>
      </div>

      <footer v-if="current" class="viewer__meta">
        <p class="viewer__dt">
          {{ current.obs_dt }}
          <span v-if="current.is_current" class="viewer__badge">현재</span>
        </p>
        <p class="viewer__title">{{ current.obs_title || '—' }}</p>
        <p class="viewer__nums">{{ measureLine }}</p>
        <p v-if="deltaLine" class="viewer__delta">{{ deltaLine }}</p>
        <p v-if="current.fruit_rmk" class="viewer__rmk">{{ current.fruit_rmk }}</p>
        <p class="viewer__hint">좌우로 밀어 이전·다음 추적을 볼 수 있습니다.</p>
      </footer>
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
  background: color-mix(in srgb, var(--ods-color-gray-900) 94%, transparent);
  color: var(--ods-color-white);
  padding: env(safe-area-inset-top, 0) env(safe-area-inset-right, 0)
    env(safe-area-inset-bottom, 0) env(safe-area-inset-left, 0);
}
.viewer__bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--ods-space-12) var(--ods-page-padding-x, var(--ods-space-16));
  flex-shrink: 0;
}
.viewer__counter {
  margin: 0;
  font: var(--ods-font-form-help);
  font-weight: 700;
}
.viewer__close {
  min-height: var(--ods-button-height-in-card);
  padding: 0 var(--ods-space-12);
  border: 1px solid color-mix(in srgb, var(--ods-color-white) 35%, transparent);
  border-radius: var(--ods-radius-button);
  background: transparent;
  color: var(--ods-color-white);
  font: var(--ods-font-form-help);
  font-weight: 700;
}
.viewer__stage {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: var(--ods-touch-min) 1fr var(--ods-touch-min);
  align-items: center;
  gap: var(--ods-space-4);
  padding: 0 var(--ods-space-4);
}
.viewer__frame {
  position: relative;
  width: 100%;
  height: min(58dvh, 520px);
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  border-radius: var(--ods-radius-button);
  background: var(--ods-color-gray-900);
}
.viewer__img {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}
.viewer__status,
.viewer__fail,
.viewer__empty {
  margin: 0;
  padding: var(--ods-space-16);
  text-align: center;
  color: color-mix(in srgb, var(--ods-color-white) 80%, transparent);
  font: var(--ods-font-form-help);
}
.viewer__nav {
  height: var(--ods-button-height);
  border: none;
  border-radius: var(--ods-radius-button);
  background: color-mix(in srgb, var(--ods-color-white) 12%, transparent);
  color: var(--ods-color-white);
  font: var(--ods-font-title-1);
  line-height: 1;
}
.viewer__nav:disabled {
  opacity: 0.25;
}
.viewer__meta {
  flex-shrink: 0;
  padding: var(--ods-space-12) var(--ods-page-padding-x, var(--ods-space-16)) var(--ods-space-20);
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-4);
}
.viewer__dt,
.viewer__title,
.viewer__nums,
.viewer__delta,
.viewer__rmk,
.viewer__hint {
  margin: 0;
}
.viewer__dt {
  font: var(--ods-font-form-help);
  font-weight: 700;
}
.viewer__badge {
  margin-left: var(--ods-space-4);
  font: var(--ods-font-card-meta);
  color: var(--ods-color-secondary);
}
.viewer__title {
  font: var(--ods-font-form-value);
  font-weight: 700;
}
.viewer__nums,
.viewer__delta,
.viewer__rmk,
.viewer__hint {
  font: var(--ods-font-card-help);
  color: color-mix(in srgb, var(--ods-color-white) 78%, transparent);
}
.viewer__hint {
  margin-top: var(--ods-space-8);
  opacity: 0.7;
}
</style>
