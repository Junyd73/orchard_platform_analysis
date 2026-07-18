<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import { ApiClientError } from '@/api/client'
import {
  deleteObservationPhoto,
  fetchObservationPhotos,
  photoThumbSrc,
  reorderObservationPhotos,
  uploadObservationPhotos,
} from '@/api/observationPhotos'
import OdsButton from '@/components/ods/OdsButton.vue'
import OdsCard from '@/components/ods/OdsCard.vue'
import PhotoViewer from '@/views/observation/components/PhotoViewer.vue'
import { OBS_PHOTO_MAX_COUNT } from '@/composables/constants/app'
import { takeFilesFromInput } from '@/utils/fileInput'
import {
  filterObservationUploadFiles,
  photoIdentityKey,
} from '@/shared/photoFilePolicy'
import { formatPhotoCardLabel } from '@/utils/photoCardLabel'
import type { ObservationPhotoItem } from '@/types/observation'

import iconCamera from '@/assets/ods/scr004/icon-camera.svg'
import iconGallery from '@/assets/ods/scr004/icon-gallery.svg'
import iconPhoto from '@/assets/ods/scr004/icon-photo.svg'
import iconChevronRight from '@/assets/ods/scr004/icon-chevron-right.svg'

const props = withDefaults(
  defineProps<{
    farmCd: string
    obsId: string
    variant?: 'default' | 'scr004'
  }>(),
  { variant: 'default' },
)

const emit = defineEmits<{
  changed: [photos: ObservationPhotoItem[]]
}>()

const photos = ref<ObservationPhotoItem[]>([])
const maxCount = ref(OBS_PHOTO_MAX_COUNT)
const remaining = ref(OBS_PHOTO_MAX_COUNT)
const loading = ref(false)
const busy = ref(false)
const errorMessage = ref('')
const statusMessage = ref('')
const galleryInput = ref<HTMLInputElement | null>(null)
const cameraInput = ref<HTMLInputElement | null>(null)
/** 실패 시 재시도용 (이미 복사된 File[]) */
const pendingRetryFiles = ref<File[] | null>(null)

const viewerOpen = ref(false)
const viewerIndex = ref(0)

let listAbort: AbortController | null = null
let uploadAbort: AbortController | null = null

const countLabel = computed(() => `${photos.value.length} / ${maxCount.value} 장`)
const isScr004 = computed(() => props.variant === 'scr004')
const canAdd = computed(() => remaining.value > 0 && !busy.value)
const canRetryUpload = computed(() => Boolean(pendingRetryFiles.value?.length) && !busy.value)

function cardLabel(photo: ObservationPhotoItem, index: number) {
  return formatPhotoCardLabel(photo.display_nm, index)
}

function isAbortError(err: unknown): boolean {
  return err instanceof ApiClientError && err.message.includes('취소')
}

async function loadPhotos() {
  listAbort?.abort()
  listAbort = new AbortController()
  loading.value = true
  errorMessage.value = ''
  try {
    const res = await fetchObservationPhotos(props.farmCd, props.obsId, listAbort.signal)
    photos.value = res.photos
    maxCount.value = res.max_count
    remaining.value = res.remaining
    emit('changed', res.photos)
  } catch (err) {
    if (isAbortError(err)) return
    photos.value = []
    errorMessage.value =
      err instanceof ApiClientError ? err.message : '사진 목록을 불러오지 못했습니다.'
  } finally {
    loading.value = false
  }
}

watch(
  () => [props.farmCd, props.obsId],
  () => {
    pendingRetryFiles.value = null
    viewerOpen.value = false
    void loadPhotos()
  },
  { immediate: true },
)

function openGallery() {
  if (!canAdd.value) return
  galleryInput.value?.click()
}

function openCamera() {
  if (!canAdd.value) return
  cameraInput.value?.click()
}

function openViewer(index: number) {
  viewerIndex.value = index
  viewerOpen.value = true
}

function closeViewer() {
  viewerOpen.value = false
}

async function uploadSelected(selected: File[]) {
  if (!selected.length) return
  if (busy.value) return
  if (selected.length > remaining.value) {
    errorMessage.value = `남은 등록 가능 개수는 ${remaining.value}장입니다. (최대 ${maxCount.value}장)`
    pendingRetryFiles.value = null
    return
  }

  const existingKeys = new Set(
    photos.value.map((p) =>
      photoIdentityKey({ name: p.original_nm, size: p.file_size }),
    ),
  )
  const checked = filterObservationUploadFiles(selected, {
    remaining: remaining.value,
    maxCount: maxCount.value,
    existingKeys,
  })
  if (!checked.ok) {
    errorMessage.value = checked.message
    pendingRetryFiles.value = null
    return
  }
  const toUpload = checked.files

  busy.value = true
  errorMessage.value = ''
  statusMessage.value = `업로드 중… (${toUpload.length}장)`
  pendingRetryFiles.value = toUpload
  uploadAbort?.abort()
  uploadAbort = new AbortController()

  try {
    const res = await uploadObservationPhotos(props.farmCd, props.obsId, toUpload, {
      signal: uploadAbort.signal,
    })
    const listed = await fetchObservationPhotos(
      props.farmCd,
      props.obsId,
      uploadAbort.signal,
    )
    photos.value = listed.photos
    remaining.value = res.remaining
    maxCount.value = res.max_count
    pendingRetryFiles.value = null
    statusMessage.value = res.message || '업로드 성공'
    emit('changed', listed.photos)
  } catch (err) {
    if (isAbortError(err)) {
      statusMessage.value = '업로드가 취소되었습니다.'
      return
    }
    const reason =
      err instanceof ApiClientError
        ? err.message
        : '업로드에 실패했습니다.'
    errorMessage.value = `업로드 실패: ${reason}`
    statusMessage.value = ''
  } finally {
    busy.value = false
  }
}

async function onFilesSelected(ev: Event) {
  const input = ev.target as HTMLInputElement
  // Android: FileList live — value 초기화 전에 반드시 복사
  const selected = takeFilesFromInput(input)
  if (!selected.length) return
  await uploadSelected(selected)
}

async function removePhoto(photo: ObservationPhotoItem) {
  if (busy.value) return
  busy.value = true
  errorMessage.value = ''
  statusMessage.value = '삭제 중…'
  try {
    await deleteObservationPhoto(props.farmCd, props.obsId, photo.photo_id)
    await loadPhotos()
    statusMessage.value = '사진을 삭제했습니다.'
  } catch (err) {
    errorMessage.value =
      err instanceof ApiClientError ? err.message : '삭제에 실패했습니다.'
    statusMessage.value = ''
  } finally {
    busy.value = false
  }
}

async function movePhoto(index: number, delta: -1 | 1) {
  const next = index + delta
  if (next < 0 || next >= photos.value.length || busy.value) return
  const ids = photos.value.map((p) => p.photo_id)
  ;[ids[index], ids[next]] = [ids[next], ids[index]]
  busy.value = true
  errorMessage.value = ''
  try {
    const res = await reorderObservationPhotos(props.farmCd, props.obsId, ids)
    photos.value = res.photos
    remaining.value = res.remaining
    statusMessage.value = '순서를 변경했습니다. 첫 번째가 대표사진입니다.'
    emit('changed', res.photos)
  } catch (err) {
    errorMessage.value =
      err instanceof ApiClientError ? err.message : '순서 변경에 실패했습니다.'
  } finally {
    busy.value = false
  }
}

async function onRetry() {
  if (canRetryUpload.value && pendingRetryFiles.value) {
    await uploadSelected([...pendingRetryFiles.value])
    return
  }
  await loadPhotos()
}

defineExpose({ reload: loadPhotos })
</script>

<template>
  <OdsCard v-if="isScr004" class="panel panel--scr004" aria-label="관찰 사진">
    <header class="head">
      <h2 class="title">
        <img v-if="isScr004" class="title-icon" :src="iconPhoto" alt="" aria-hidden="true">
        사진
      </h2>
      <p class="count" :class="{ 'count--full': remaining <= 0 }">
        {{ countLabel }}
        <img
          v-if="isScr004"
          class="count-chev"
          :src="iconChevronRight"
          alt=""
          aria-hidden="true"
        >
      </p>
    </header>
    <input
      ref="cameraInput"
      class="sr-only"
      type="file"
      accept="image/jpeg,image/jpg,image/png,image/webp,image/*"
      capture="environment"
      @change="onFilesSelected"
    >
    <input
      ref="galleryInput"
      class="sr-only"
      type="file"
      accept="image/jpeg,image/jpg,image/png,image/webp,image/*"
      multiple
      @change="onFilesSelected"
    >

    <p v-if="loading" class="status status--loading" role="status">불러오는 중…</p>
    <p v-else-if="busy && statusMessage" class="status status--loading" role="status">
      {{ statusMessage }}
    </p>
    <p v-else-if="statusMessage" class="status status--ok" role="status">{{ statusMessage }}</p>
    <p v-if="errorMessage" class="error" role="alert">
      {{ errorMessage }}
      <button type="button" class="retry" @click="onRetry">
        {{ canRetryUpload ? '다시 시도(업로드)' : '다시 시도' }}
      </button>
    </p>

    <ul v-if="photos.length" class="strip" role="list" aria-label="관찰 사진 목록">
      <li
        v-for="(photo, index) in photos"
        :key="photo.photo_id"
        class="strip__cell"
        role="listitem"
      >
        <button
          type="button"
          class="strip__thumb"
          :aria-label="`${cardLabel(photo, index).fullName} 확대 보기`"
          @click="openViewer(index)"
        >
          <img
            class="strip__img"
            :src="photoThumbSrc(photo)"
            :alt="cardLabel(photo, index).fullName"
            loading="lazy"
          >
          <span v-if="index === 0 && photo.is_representative" class="strip__rep">대표</span>
          <span
            class="strip__del"
            role="button"
            tabindex="0"
            aria-label="사진 삭제"
            @click.stop="removePhoto(photo)"
            @keydown.enter.stop.prevent="removePhoto(photo)"
          >×</span>
        </button>
      </li>
    </ul>
    <p v-else-if="!loading" class="empty empty--scr004">
      등록된 사진이 없습니다. 카메라 또는 갤러리로 추가하세요.
    </p>

    <div class="actions actions--scr004">
      <OdsButton
        variant="secondary"
        :disabled="!canAdd"
        :block="false"
        aria-label="카메라"
        @click="openCamera"
      >
        <span class="btn-inner">
          <img class="btn-icon" :src="iconCamera" alt="" aria-hidden="true">
          카메라
        </span>
      </OdsButton>
      <OdsButton
        variant="secondary"
        :disabled="!canAdd"
        :block="false"
        aria-label="갤러리"
        @click="openGallery"
      >
        <span class="btn-inner">
          <img class="btn-icon" :src="iconGallery" alt="" aria-hidden="true">
          갤러리
        </span>
      </OdsButton>
    </div>

    <PhotoViewer
      :open="viewerOpen"
      :photos="photos"
      :index="viewerIndex"
      @close="closeViewer"
      @update:index="viewerIndex = $event"
    />
  </OdsCard>
  <section v-else class="panel" aria-label="관찰 사진">
    <header class="head">
      <h2 class="title">사진</h2>
      <p class="count" :class="{ 'count--full': remaining <= 0 }">{{ countLabel }}</p>
    </header>
    <p class="hint">최대 {{ maxCount }}장 · 첫 번째 사진이 대표사진입니다.</p>

    <div class="actions">
      <OdsButton variant="primary" :disabled="!canAdd" :block="false" @click="openCamera">
        카메라 촬영
      </OdsButton>
      <OdsButton variant="secondary" :disabled="!canAdd" :block="false" @click="openGallery">
        갤러리 선택
      </OdsButton>
    </div>

    <input
      ref="cameraInput"
      class="sr-only"
      type="file"
      accept="image/jpeg,image/jpg,image/png,image/webp,image/*"
      capture="environment"
      @change="onFilesSelected"
    >
    <input
      ref="galleryInput"
      class="sr-only"
      type="file"
      accept="image/jpeg,image/jpg,image/png,image/webp,image/*"
      multiple
      @change="onFilesSelected"
    >

    <p v-if="loading" class="status status--loading" role="status">불러오는 중…</p>
    <p v-else-if="busy && statusMessage" class="status status--loading" role="status">
      {{ statusMessage }}
    </p>
    <p v-else-if="statusMessage" class="status status--ok" role="status">{{ statusMessage }}</p>
    <p v-if="errorMessage" class="error" role="alert">
      {{ errorMessage }}
      <button type="button" class="retry" @click="onRetry">
        {{ canRetryUpload ? '다시 시도(업로드)' : '다시 시도' }}
      </button>
    </p>

    <ul v-if="photos.length" class="list">
      <li v-for="(photo, index) in photos" :key="photo.photo_id" class="item">
        <button
          type="button"
          class="thumb-wrap"
          :aria-label="`${cardLabel(photo, index).fullName} 확대 보기`"
          @click="openViewer(index)"
        >
          <img
            class="thumb"
            :src="photoThumbSrc(photo)"
            :alt="cardLabel(photo, index).fullName"
            loading="lazy"
          >
          <span v-if="index === 0 && photo.is_representative" class="rep">대표</span>
        </button>
        <div class="meta">
          <p
            class="file-name"
            :title="cardLabel(photo, index).fullName"
            :aria-label="cardLabel(photo, index).fullName"
          >
            <span class="file-name__primary">{{ cardLabel(photo, index).primary }}</span>
            <span class="file-name__secondary">{{ cardLabel(photo, index).secondary }}</span>
          </p>
          <div class="item-actions">
            <button
              type="button"
              class="icon-btn"
              :disabled="busy || index === 0"
              aria-label="위로"
              @click="movePhoto(index, -1)"
            >
              ↑
            </button>
            <button
              type="button"
              class="icon-btn"
              :disabled="busy || index === photos.length - 1"
              aria-label="아래로"
              @click="movePhoto(index, 1)"
            >
              ↓
            </button>
            <button
              type="button"
              class="icon-btn icon-btn--danger"
              :disabled="busy"
              aria-label="삭제"
              @click="removePhoto(photo)"
            >
              삭제
            </button>
          </div>
        </div>
      </li>
    </ul>
    <p v-else-if="!loading" class="empty">등록된 사진이 없습니다. 촬영 또는 갤러리에서 추가하세요.</p>

    <PhotoViewer
      :open="viewerOpen"
      :photos="photos"
      :index="viewerIndex"
      @close="closeViewer"
      @update:index="viewerIndex = $event"
    />
  </section>
</template>

<style scoped>
.panel {
  background: var(--ods-color-white);
  border: 1px solid var(--ods-color-border);
  border-radius: var(--ods-radius-card);
  padding: var(--ods-space-16);
  box-shadow: var(--ods-shadow-card);
  width: 100%;
  min-width: 0;
  box-sizing: border-box;
  overflow: hidden;
}
.head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--ods-space-12);
}
.title {
  margin: 0;
  font: var(--ods-font-headline);
  color: var(--ods-color-text);
}
.count {
  margin: 0;
  font: var(--ods-font-body-1);
  font-weight: 700;
  color: var(--ods-color-primary);
}
.count--full {
  color: var(--ods-color-danger);
}
.hint {
  margin: var(--ods-space-8) 0 0;
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
}
.actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--ods-space-8);
  margin-top: var(--ods-space-16);
}
.actions :deep(.ods-btn) {
  flex: 1 1 140px;
  min-width: 0;
}
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  border: 0;
}
.status,
.error,
.empty {
  margin: var(--ods-space-12) 0 0;
  font: var(--ods-font-body-2);
}
.status {
  color: var(--ods-color-text-secondary);
}
.status--loading {
  color: var(--ods-color-ai);
  font-weight: 600;
}
.status--ok {
  color: var(--ods-color-primary);
  font-weight: 600;
}
.error {
  color: var(--ods-color-danger);
}
.retry {
  margin-left: var(--ods-space-8);
  border: none;
  background: transparent;
  color: var(--ods-color-primary);
  font: var(--ods-font-body-2);
  font-weight: 700;
  text-decoration: underline;
  cursor: pointer;
}
.empty {
  color: var(--ods-color-text-secondary);
}
.list {
  list-style: none;
  margin: var(--ods-space-16) 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-12);
  width: 100%;
  min-width: 0;
}
.item {
  display: grid;
  grid-template-columns: 96px minmax(0, 1fr);
  gap: var(--ods-space-12);
  padding: var(--ods-space-8);
  border: 1px solid var(--ods-color-border);
  border-radius: 12px;
  background: var(--ods-color-bg-muted);
  width: 100%;
  min-width: 0;
  box-sizing: border-box;
  overflow: hidden;
  align-items: start;
}
.thumb-wrap {
  position: relative;
  width: 96px;
  height: 96px;
  padding: 0;
  border: none;
  border-radius: 10px;
  overflow: hidden;
  background: var(--ods-color-gray-100);
  cursor: pointer;
  flex: 0 0 96px;
}
.thumb {
  width: 96px;
  height: 96px;
  object-fit: cover;
  display: block;
}
.rep {
  position: absolute;
  left: 4px;
  top: 4px;
  height: 22px;
  line-height: 22px;
  padding: 0 6px;
  border-radius: 4px;
  background: color-mix(in srgb, var(--ods-color-primary) 82%, transparent);
  color: var(--ods-color-white);
  font: var(--ods-font-caption);
  font-size: 11px;
  font-weight: 700;
  pointer-events: none;
}
.meta {
  min-width: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-8);
}
.file-name {
  margin: 0;
  min-width: 0;
  max-width: 100%;
  display: flex;
  flex-direction: column;
  gap: 2px;
  font: var(--ods-font-body-2);
  font-weight: 600;
  color: var(--ods-color-text);
}
.file-name__primary,
.file-name__secondary {
  display: block;
  min-width: 0;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}
.file-name__secondary {
  font: var(--ods-font-caption);
  font-weight: 600;
  color: var(--ods-color-text-secondary);
}
.item-actions {
  display: flex;
  flex-wrap: nowrap;
  gap: 6px;
  flex: 0 0 auto;
  min-width: 0;
}
.icon-btn {
  box-sizing: border-box;
  min-height: 44px;
  min-width: 44px;
  height: 44px;
  padding: 0 var(--ods-space-8);
  border: 1px solid var(--ods-color-border);
  border-radius: var(--ods-radius-button);
  background: var(--ods-color-white);
  color: var(--ods-color-text);
  font: var(--ods-font-caption);
  font-weight: 700;
  cursor: pointer;
  flex: 0 0 auto;
}
.icon-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
  background: var(--ods-color-gray-100);
  color: var(--ods-color-gray-500);
}
.icon-btn--danger {
  color: var(--ods-color-danger);
  border-color: color-mix(in srgb, var(--ods-color-danger) 40%, white);
}
.icon-btn--danger:disabled {
  color: color-mix(in srgb, var(--ods-color-danger) 45%, var(--ods-color-gray-500));
}

.panel--scr004 {
  padding: var(--ods-space-20);
}
.panel--scr004 .title {
  display: flex;
  align-items: center;
  gap: var(--ods-space-8);
  font-size: 18px;
  font-weight: 700;
  color: var(--ods-color-primary);
}
.title-icon {
  width: 22px;
  height: 22px;
  flex: 0 0 auto;
}
.panel--scr004 .count {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  font-size: 14px;
  color: var(--ods-color-text-secondary);
  font-weight: 600;
}
.count-chev {
  width: 14px;
  height: 14px;
  opacity: 0.55;
}
/* SCR-004: horizontal swipe strip (~2.75 visible) */
.strip {
  --photo-strip-visible: 2.75;
  list-style: none;
  margin: var(--ods-space-16) 0 0;
  padding: 0 0 var(--ods-space-4);
  display: flex;
  gap: var(--ods-space-8);
  overflow-x: auto;
  overflow-y: hidden;
  scroll-snap-type: x mandatory;
  -webkit-overflow-scrolling: touch;
  overscroll-behavior-x: contain;
  scrollbar-width: none;
}
.strip::-webkit-scrollbar {
  display: none;
}
.strip__cell {
  flex: 0 0 calc((100% - 2 * var(--ods-space-8)) / var(--photo-strip-visible));
  min-width: 0;
  scroll-snap-align: start;
}
.strip__thumb {
  position: relative;
  display: block;
  width: 100%;
  aspect-ratio: 1;
  padding: 0;
  border: none;
  border-radius: 10px;
  overflow: hidden;
  cursor: pointer;
  background: var(--ods-color-gray-100);
  min-height: var(--ods-touch-min);
}
.strip__img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  position: relative;
  z-index: 0;
}
.strip__rep {
  position: absolute;
  left: 3px;
  top: 3px;
  padding: 0 5px;
  height: 18px;
  line-height: 18px;
  border-radius: 4px;
  background: var(--ods-color-primary);
  color: var(--ods-color-white);
  font-size: 10px;
  font-weight: 700;
  pointer-events: none;
}
.strip__del {
  position: absolute;
  right: 3px;
  top: 3px;
  width: 22px;
  height: 22px;
  border-radius: 999px;
  background: var(--ods-color-white);
  color: var(--ods-color-gray-700);
  border: 1px solid var(--ods-color-border);
  box-shadow: 0 1px 2px rgba(33, 33, 33, 0.08);
  font-size: 14px;
  line-height: 20px;
  text-align: center;
  font-weight: 600;
  z-index: 1;
}
.empty--scr004 {
  margin: var(--ods-space-16) 0 0;
  font: var(--ods-font-body-2);
  color: var(--ods-color-text-secondary);
}
.actions--scr004 {
  margin-top: var(--ods-space-12);
  gap: var(--ods-space-8);
}
.actions--scr004 :deep(.ods-btn) {
  flex: 1 1 0;
  min-height: var(--ods-touch-min);
  padding: 0 var(--ods-space-12);
  font: var(--ods-font-body-2);
  font-weight: 600;
}
.btn-inner {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--ods-space-4);
}
.btn-icon {
  width: 16px;
  height: 16px;
}

@media (prefers-reduced-motion: reduce) {
  .strip {
    scroll-behavior: auto;
  }
}

@media (max-width: 360px) {
  .strip {
    --photo-strip-visible: 2.4;
  }
  .item {
    grid-template-columns: 88px minmax(0, 1fr);
  }
  .thumb-wrap,
  .thumb {
    width: 88px;
    height: 88px;
  }
  .thumb-wrap {
    flex-basis: 88px;
  }
}
</style>
