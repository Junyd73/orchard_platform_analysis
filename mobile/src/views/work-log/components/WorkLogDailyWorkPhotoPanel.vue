<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import { ApiClientError } from '@/api/client'
import {
  deleteWorkPhoto,
  fetchWorkPhotos,
  uploadWorkPhotos,
  workPhotoThumbSrc,
} from '@/api/workPhotos'
import iconPlus from '@/assets/ods/work-log/icon-plus.svg'
import PhotoViewer from '@/views/observation/components/PhotoViewer.vue'
import {
  MSG_WORK_PHOTO_DELETE_CONFIRM,
  MSG_WORK_PHOTO_EMPTY,
  MSG_WORK_PHOTO_LIMIT,
  MSG_WORK_PHOTO_LOADING,
  MSG_WORK_PHOTO_SAVE_FIRST,
  MSG_WORK_PHOTO_UPLOADING,
  WORK_PHOTO_MAX_COUNT,
} from '@/views/work-log/workLogConstants'
import { takeFilesFromInput } from '@/utils/fileInput'
import { isHeicLikeFile, prepareObservationUploadFiles } from '@/shared/heicConvert'
import { resolveMediaUrl } from '@/utils/mediaUrl'
import {
  filterObservationUploadFiles,
  OBS_PHOTO_INPUT_ACCEPT,
  photoIdentityKey,
} from '@/shared/photoFilePolicy'
import type { WorkPhotoItem } from '@/types/workPhoto'

const props = defineProps<{
  farmCd: string
  /** 저장된 작업번호 — 없으면 업로드 불가 */
  workId?: string | null
}>()

const emit = defineEmits<{
  changed: [photos: WorkPhotoItem[]]
}>()

const photos = ref<WorkPhotoItem[]>([])
const maxCount = ref(WORK_PHOTO_MAX_COUNT)
const remaining = ref(WORK_PHOTO_MAX_COUNT)
const loading = ref(false)
const busy = ref(false)
const errorMessage = ref('')
const statusMessage = ref('')
const galleryInput = ref<HTMLInputElement | null>(null)

const viewerOpen = ref(false)
const viewerIndex = ref(0)

let listAbort: AbortController | null = null
let uploadAbort: AbortController | null = null

const savedWorkId = computed(() => String(props.workId || '').trim())
const canUpload = computed(() => Boolean(savedWorkId.value))
const canAdd = computed(
  () => canUpload.value && remaining.value > 0 && !busy.value && !loading.value,
)
const photoCount = computed(() => photos.value.length)

function isAbortError(err: unknown): boolean {
  return err instanceof ApiClientError && err.message.includes('취소')
}

function onThumbError(ev: Event, photo: WorkPhotoItem) {
  const img = ev.target as HTMLImageElement | null
  if (!img) return
  const fallback = resolveMediaUrl(photo.original_url)
  if (!fallback || img.dataset.fallbackTried === '1') return
  img.dataset.fallbackTried = '1'
  if (img.src !== fallback) img.src = fallback
}

async function loadPhotos() {
  listAbort?.abort()
  const wid = savedWorkId.value
  if (!props.farmCd || !wid) {
    photos.value = []
    remaining.value = WORK_PHOTO_MAX_COUNT
    maxCount.value = WORK_PHOTO_MAX_COUNT
    errorMessage.value = ''
    emit('changed', [])
    return
  }
  listAbort = new AbortController()
  loading.value = true
  errorMessage.value = ''
  try {
    const res = await fetchWorkPhotos(props.farmCd, wid, listAbort.signal)
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
  () => [props.farmCd, savedWorkId.value],
  () => {
    viewerOpen.value = false
    void loadPhotos()
  },
  { immediate: true },
)

function onAddClick() {
  if (!canUpload.value) {
    errorMessage.value = MSG_WORK_PHOTO_SAVE_FIRST
    return
  }
  if (!canAdd.value) return
  galleryInput.value?.click()
}

async function onGalleryChange(ev: Event) {
  const input = ev.target as HTMLInputElement | null
  if (!input) return
  const selected = takeFilesFromInput(input)
  if (!selected.length) return
  await uploadSelected(selected)
}

async function uploadSelected(selected: File[]) {
  const wid = savedWorkId.value
  if (!wid) {
    errorMessage.value = MSG_WORK_PHOTO_SAVE_FIRST
    return
  }
  if (busy.value) return
  if (selected.length > remaining.value) {
    errorMessage.value = `남은 등록 가능 개수는 ${remaining.value}장입니다. (최대 ${maxCount.value}장)`
    return
  }

  busy.value = true
  errorMessage.value = ''
  const needsHeic = selected.some((f) => isHeicLikeFile(f))
  statusMessage.value = needsHeic ? 'HEIC → JPG 변환 중…' : MSG_WORK_PHOTO_UPLOADING
  uploadAbort?.abort()
  uploadAbort = new AbortController()

  try {
    const prepared = await prepareObservationUploadFiles(selected)
    if (!prepared.ok) {
      errorMessage.value = prepared.message
      statusMessage.value = ''
      return
    }
    const existingKeys = new Set(
      photos.value.map((p) =>
        photoIdentityKey({ name: p.original_nm, size: p.file_size }),
      ),
    )
    const checked = filterObservationUploadFiles(prepared.files, {
      remaining: remaining.value,
      maxCount: maxCount.value,
      existingKeys,
    })
    if (!checked.ok) {
      errorMessage.value = checked.message
      statusMessage.value = ''
      return
    }
    statusMessage.value = `${MSG_WORK_PHOTO_UPLOADING} (${checked.files.length}장)`
    const res = await uploadWorkPhotos(props.farmCd, wid, checked.files, {
      signal: uploadAbort.signal,
    })
    try {
      const listed = await fetchWorkPhotos(props.farmCd, wid, uploadAbort.signal)
      photos.value = listed.photos
      remaining.value = listed.remaining
      maxCount.value = listed.max_count
      emit('changed', listed.photos)
    } catch {
      if (res.uploaded?.length) {
        photos.value = res.uploaded
        remaining.value = res.remaining
        maxCount.value = res.max_count
        emit('changed', res.uploaded)
      }
    }
    statusMessage.value = res.message || ''
  } catch (err) {
    if (isAbortError(err)) return
    errorMessage.value =
      err instanceof ApiClientError ? err.message : '사진 업로드에 실패했습니다.'
    statusMessage.value = ''
  } finally {
    busy.value = false
  }
}

function openViewer(index: number) {
  viewerIndex.value = index
  viewerOpen.value = true
}

async function onDelete(photo: WorkPhotoItem) {
  const wid = savedWorkId.value
  if (!wid || busy.value) return
  if (!window.confirm(MSG_WORK_PHOTO_DELETE_CONFIRM)) return
  busy.value = true
  errorMessage.value = ''
  try {
    await deleteWorkPhoto(props.farmCd, wid, photo.photo_id)
    await loadPhotos()
  } catch (err) {
    errorMessage.value =
      err instanceof ApiClientError ? err.message : '사진 삭제에 실패했습니다.'
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="panel">
    <div class="panel__head">
      <h3 class="panel__title">작업 결과 사진</h3>
      <span class="panel__count">{{ photoCount }}/{{ maxCount }}</span>
    </div>
    <p class="panel__hint">{{ MSG_WORK_PHOTO_LIMIT }}</p>
    <p v-if="!canUpload" class="panel__warn">{{ MSG_WORK_PHOTO_SAVE_FIRST }}</p>
    <p v-if="loading" class="panel__status">{{ MSG_WORK_PHOTO_LOADING }}</p>
    <p v-else-if="statusMessage" class="panel__status">{{ statusMessage }}</p>
    <p v-if="errorMessage" class="panel__error" role="alert">{{ errorMessage }}</p>

    <p v-if="!loading && photoCount === 0" class="panel__empty">{{ MSG_WORK_PHOTO_EMPTY }}</p>

    <div class="grid" aria-label="작업 사진">
      <button
        v-for="(photo, index) in photos"
        :key="photo.photo_id"
        type="button"
        class="grid__slot grid__slot--photo"
        @click="openViewer(index)"
        @contextmenu.prevent="onDelete(photo)"
      >
        <img
          class="grid__img"
          :src="workPhotoThumbSrc(photo)"
          :alt="photo.display_nm || `사진 ${index + 1}`"
          @error="onThumbError($event, photo)"
        />
        <span class="grid__del" @click.stop="onDelete(photo)">삭제</span>
      </button>
      <button
        v-if="canAdd || !canUpload"
        type="button"
        class="grid__slot grid__slot--add"
        :disabled="busy || loading"
        @click="onAddClick"
      >
        <img :src="iconPlus" alt="" />
        <span>추가</span>
      </button>
    </div>

    <input
      ref="galleryInput"
      class="panel__file"
      type="file"
      :accept="OBS_PHOTO_INPUT_ACCEPT"
      multiple
      @change="onGalleryChange"
    />

    <PhotoViewer
      :open="viewerOpen"
      :photos="photos"
      :index="viewerIndex"
      @close="viewerOpen = false"
      @update:index="viewerIndex = $event"
    />
  </div>
</template>

<style scoped>
.panel {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-12);
}
.panel__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.panel__title {
  margin: 0;
  font: var(--ods-font-form-help);
  font-weight: 700;
  color: var(--ods-color-text);
}
.panel__count {
  font: var(--ods-font-card-help);
  font-weight: 700;
  color: var(--ods-color-primary);
}
.panel__hint {
  margin: 0;
  font: var(--ods-font-card-help);
  color: var(--ods-color-text-secondary);
}
.panel__warn,
.panel__status,
.panel__error {
  margin: 0;
  font: var(--ods-font-card-help);
}
.panel__warn {
  color: var(--ods-color-caution);
}
.panel__status {
  color: var(--ods-color-text-secondary);
}
.panel__error {
  color: var(--ods-color-danger);
}
.panel__empty {
  margin: 0;
  padding: var(--ods-space-12);
  text-align: center;
  font: var(--ods-font-form-help);
  color: var(--ods-color-text-secondary);
  background: var(--ods-color-bg-muted);
  border-radius: var(--ods-radius-button);
}
.panel__file {
  display: none;
}
.grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--ods-space-8);
}
.grid__slot {
  aspect-ratio: 1;
  margin: 0;
  padding: 0;
  border: 1px dashed var(--ods-color-border);
  border-radius: var(--ods-radius-button);
  background: var(--ods-color-bg-muted);
  display: grid;
  place-items: center;
  gap: var(--ods-space-4);
  font: var(--ods-font-card-help);
  color: var(--ods-color-text-secondary);
  cursor: pointer;
  position: relative;
  overflow: hidden;
}
.grid__slot--photo {
  border-style: solid;
  padding: 0;
}
.grid__slot--add {
  border-style: solid;
  border-color: var(--ods-color-primary);
  color: var(--ods-color-primary);
  font-weight: 700;
}
.grid__slot--add:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.grid__slot--add img {
  width: var(--ods-icon-md);
  height: var(--ods-icon-md);
}
.grid__img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.grid__del {
  position: absolute;
  right: var(--ods-space-4);
  bottom: var(--ods-space-4);
  padding: var(--ods-space-4) var(--ods-space-8);
  border-radius: var(--ods-radius-button);
  background: color-mix(in srgb, black 55%, transparent);
  color: var(--ods-color-white);
  font: var(--ods-font-card-help);
  font-weight: 700;
}
</style>
