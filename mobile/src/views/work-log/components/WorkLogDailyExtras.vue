<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { fetchObservations } from '@/api/observations'
import {
  fetchObservationPhotos,
  photoThumbSrc,
} from '@/api/observationPhotos'
import PhotoViewer from '@/views/observation/components/PhotoViewer.vue'
import {
  DAILY_OBS_PHOTO_PREVIEW_MAX,
  MSG_OBS_EMPTY,
  MSG_OBS_LOADING,
  MSG_OBS_PHOTO_EMPTY,
  formatDailyObsMeta,
  formatDailyObsTitle,
} from '@/views/work-log/workLogConstants'
import type {
  ObservationListItem,
  ObservationPhotoItem,
} from '@/types/observation'

const props = defineProps<{
  workDt: string
  farmCd: string
}>()

const router = useRouter()

const items = ref<ObservationListItem[]>([])
const loading = ref(false)
const selectedId = ref('')
/** 선택 관찰의 전체 사진 (크게 보기용) */
const photos = ref<ObservationPhotoItem[]>([])
const photosLoading = ref(false)
const viewerOpen = ref(false)
const viewerIndex = ref(0)

const previewPhotos = computed(() =>
  photos.value.slice(0, DAILY_OBS_PHOTO_PREVIEW_MAX),
)

const emptyPhotoSlotCount = computed(() =>
  Math.max(0, DAILY_OBS_PHOTO_PREVIEW_MAX - previewPhotos.value.length),
)

let listSeq = 0
let photoAbort: AbortController | null = null

async function loadList() {
  const seq = ++listSeq
  selectedId.value = ''
  photos.value = []
  viewerOpen.value = false
  if (!props.farmCd || !props.workDt) {
    items.value = []
    loading.value = false
    return
  }
  loading.value = true
  try {
    const rows = await fetchObservations(props.farmCd, {
      date_from: props.workDt,
      date_to: props.workDt,
      limit: 50,
    })
    if (seq !== listSeq) return
    items.value = rows
    selectedId.value = rows[0]?.obs_id || ''
  } catch {
    if (seq !== listSeq) return
    items.value = []
    selectedId.value = ''
  } finally {
    if (seq === listSeq) loading.value = false
  }
}

async function loadPhotos(obsId: string) {
  photoAbort?.abort()
  photoAbort = null
  photos.value = []
  viewerOpen.value = false
  if (!obsId || !props.farmCd) {
    photosLoading.value = false
    return
  }
  const ac = new AbortController()
  photoAbort = ac
  photosLoading.value = true
  try {
    const res = await fetchObservationPhotos(props.farmCd, obsId, ac.signal)
    if (ac.signal.aborted) return
    photos.value = res.photos
  } catch {
    if (!ac.signal.aborted) photos.value = []
  } finally {
    if (!ac.signal.aborted) photosLoading.value = false
  }
}

watch(
  () => [props.farmCd, props.workDt] as const,
  () => {
    void loadList()
  },
  { immediate: true },
)

watch(selectedId, (id) => {
  void loadPhotos(id)
})

function onSelect(obsId: string) {
  selectedId.value = obsId
}

function openDetail() {
  if (!selectedId.value) return
  void router.push({
    name: 'observation-detail',
    params: { obsId: selectedId.value },
    query: { work_dt: props.workDt },
  })
}

function openViewer(index: number) {
  if (!photos.value.length) return
  viewerIndex.value = index
  viewerOpen.value = true
}

function closeViewer() {
  viewerOpen.value = false
}

function thumbSrc(ph: ObservationPhotoItem): string {
  return photoThumbSrc(ph)
}
</script>

<template>
  <section class="obs-card" aria-label="생육관찰">
    <div class="obs-card__head">
      <h2 class="obs-card__title">생육관찰</h2>
      <button
        v-if="selectedId"
        type="button"
        class="obs-card__link"
        @click="openDetail"
      >
        자세히보기 ›
      </button>
    </div>

    <p v-if="loading" class="obs-card__empty">{{ MSG_OBS_LOADING }}</p>
    <p v-else-if="items.length === 0" class="obs-card__empty">{{ MSG_OBS_EMPTY }}</p>

    <div v-else class="obs-body">
      <div class="obs-body__list">
        <ul class="obs-list" aria-label="관찰 목록">
          <li v-for="it in items" :key="it.obs_id">
            <button
              type="button"
              class="obs-list__item"
              :class="{ 'obs-list__item--on': selectedId === it.obs_id }"
              @click="onSelect(it.obs_id)"
            >
              <span class="obs-list__title">{{ formatDailyObsTitle(it.obs_title) }}</span>
              <span class="obs-list__meta">{{ formatDailyObsMeta(it) }}</span>
            </button>
          </li>
        </ul>
      </div>

      <div class="obs-body__photos" aria-label="선택 관찰 사진">
        <p v-if="photosLoading" class="photos__empty">{{ MSG_OBS_LOADING }}</p>
        <p v-else-if="previewPhotos.length === 0" class="photos__empty">{{ MSG_OBS_PHOTO_EMPTY }}</p>
        <template v-else>
          <button
            v-for="(ph, idx) in previewPhotos"
            :key="ph.photo_id"
            type="button"
            class="photos__slot"
            :aria-label="`${ph.display_nm || '사진'} 크게 보기`"
            @click="openViewer(idx)"
          >
            <img
              class="photos__img"
              :src="thumbSrc(ph)"
              :alt="ph.display_nm || ''"
              loading="lazy"
            >
            <span v-if="idx === 0" class="photos__badge">대표</span>
          </button>
          <div
            v-for="n in emptyPhotoSlotCount"
            :key="`empty-${n}`"
            class="photos__slot photos__slot--empty"
            aria-hidden="true"
          />
        </template>
      </div>
    </div>

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
.obs-card {
  padding: var(--ods-space-16);
  border-radius: var(--ods-radius-card);
  background: var(--ods-color-white);
  border: 1px solid var(--ods-color-border);
  box-shadow: var(--ods-shadow-card);
}

.obs-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ods-space-8);
  margin-bottom: var(--ods-space-12);
}

.obs-card__title {
  margin: 0;
  font: var(--ods-font-headline);
  color: var(--ods-color-text);
}

.obs-card__link {
  margin: 0;
  padding: 0;
  border: none;
  background: transparent;
  font: var(--ods-font-caption);
  font-weight: 700;
  color: var(--ods-color-primary);
  cursor: pointer;
  min-height: 28px;
}

.obs-card__empty {
  margin: 0;
  font: var(--ods-font-body-2);
  color: var(--ods-color-text-secondary);
  text-align: center;
  padding: var(--ods-space-8) 0;
}

.obs-body {
  display: flex;
  flex-direction: row;
  flex-wrap: nowrap;
  align-items: stretch;
  gap: var(--ods-space-12);
  width: 100%;
  box-sizing: border-box;
}

.obs-body__list {
  flex: 1 1 0;
  min-width: 0;
  max-height: 140px;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
}

.obs-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-4);
}

.obs-list__item {
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  margin: 0;
  padding: var(--ods-space-8);
  border: 1px solid var(--ods-color-border);
  border-radius: var(--ods-radius-button);
  background: var(--ods-color-bg-muted);
  text-align: left;
  cursor: pointer;
  box-sizing: border-box;
}

.obs-list__item--on {
  border-color: var(--ods-color-primary);
  background: color-mix(in srgb, var(--ods-color-primary) 8%, var(--ods-color-white));
  box-shadow: 0 0 0 1px color-mix(in srgb, var(--ods-color-primary) 25%, transparent);
}

.obs-list__title {
  font: var(--ods-font-body-2);
  font-weight: 700;
  color: var(--ods-color-text);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  width: 100%;
}

.obs-list__meta {
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}

.obs-body__photos {
  flex: 0 0 132px;
  width: 132px;
  height: 132px;
  display: grid;
  grid-template-columns: 1fr 1fr;
  grid-template-rows: 1fr 1fr;
  gap: var(--ods-space-4);
  box-sizing: border-box;
  position: relative;
}

.photos__empty {
  position: absolute;
  inset: 0;
  margin: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
  text-align: center;
  padding: var(--ods-space-8);
  border: 1px solid var(--ods-color-border);
  border-radius: 8px;
  background: var(--ods-color-bg-muted);
  box-sizing: border-box;
}

.photos__slot {
  position: relative;
  min-width: 0;
  min-height: 0;
  margin: 0;
  padding: 0;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid var(--ods-color-border);
  background: var(--ods-color-bg-muted);
  cursor: pointer;
}

.photos__slot--empty {
  border-style: dashed;
  opacity: 0.45;
  cursor: default;
  pointer-events: none;
}

.photos__img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
  pointer-events: none;
}

.photos__badge {
  position: absolute;
  top: 4px;
  left: 4px;
  padding: 1px 6px;
  border-radius: var(--ods-radius-badge);
  background: var(--ods-color-primary);
  color: var(--ods-color-white);
  font: var(--ods-font-caption);
  font-size: 9px;
  font-weight: 700;
  pointer-events: none;
}
</style>
