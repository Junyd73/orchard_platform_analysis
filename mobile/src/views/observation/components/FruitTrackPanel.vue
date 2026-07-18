<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { ApiClientError } from '@/api/client'
import { fetchObservationTrack } from '@/api/observationFruit'
import { observationListThumbSrc } from '@/api/observationPhotos'
import OdsButton from '@/components/ods/OdsButton.vue'
import FruitTrackSlideViewer from '@/views/observation/components/FruitTrackSlideViewer.vue'
import type { ObservationDetail, ObservationTrackItem } from '@/types/observation'

const props = defineProps<{
  farmCd: string
  detail: ObservationDetail
}>()

const router = useRouter()

const loading = ref(false)
const errorMessage = ref('')
const trackItems = ref<ObservationTrackItem[]>([])
const trackCount = ref(0)

const viewerOpen = ref(false)
const viewerIndex = ref(0)

let loadAbort: AbortController | null = null
let alive = true

const sampleLabel = computed(() => {
  const d = props.detail
  const parts: string[] = []
  if (d.site_nm) parts.push(d.site_nm)
  if (d.zone_nm) parts.push(d.zone_nm)
  if (d.tree_no) parts.push(`나무 ${d.tree_no}`)
  if (d.sample_no) parts.push(`표본 ${d.sample_no}`)
  return parts.length ? parts.join(' · ') : '표본 위치 미입력'
})

const isCompleted = computed(
  () => String(props.detail.observation_status || '').toUpperCase() === 'COMPLETED',
)

/** 타임라인 위치 (0=1차, 1=2차, 2=3차…) */
const currentTrackIndex = computed(() => {
  const id = String(props.detail.obs_id || '').trim()
  const idx = trackItems.value.findIndex((x) => x.obs_id === id)
  return idx >= 0 ? idx : 0
})

/** 1차(최초)에서만 다음 추적(2차~) 등록 — 2차 이상은 버튼 미표시 */
const canStartTrack = computed(
  () => isCompleted.value && currentTrackIndex.value === 0,
)

/** 추적관찰 버튼 영역: 1차 상세에서만 노출 */
const showTrackAction = computed(() => currentTrackIndex.value === 0)

function roundLabel(index: number): string {
  return `${index + 1}차`
}

const currentItem = computed(
  () => trackItems.value.find((x) => x.is_current) || trackItems.value.at(-1) || null,
)

const prevItem = computed(() => {
  const list = trackItems.value
  const idx = list.findIndex((x) => x.is_current)
  if (idx > 0) return list[idx - 1]
  if (list.length >= 2) return list[list.length - 2]
  return null
})

const summaryLine = computed(() => {
  const cur = currentItem.value
  const prev = prevItem.value
  if (!cur) return ''
  const curTxt = `이번 ${fmtNum(cur.width_mm)}×${fmtNum(cur.height_mm)} · 둘레 ${fmtNum(cur.circumference_mm)}`
  if (!prev) return curTxt
  return `이전 ${fmtNum(prev.width_mm)}×${fmtNum(prev.height_mm)} → ${curTxt}`
})

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

function thumbSrc(item: ObservationTrackItem | null): string {
  if (!item?.thumb_photo_id && !item?.thumb_path) return ''
  return observationListThumbSrc({
    farm_cd: item.farm_cd,
    obs_id: item.obs_id,
    thumb_photo_id: item.thumb_photo_id,
    thumb_path: item.thumb_path,
  })
}

function openViewer(index: number) {
  if (!trackItems.value.length) return
  viewerIndex.value = index
  viewerOpen.value = true
}

function closeViewer() {
  viewerOpen.value = false
}

function goItemDetail(obsId: string) {
  const id = String(obsId || '').trim()
  if (!id) return
  void router.push({
    name: 'observation-detail',
    params: { obsId: id },
  })
}

async function loadAll() {
  if (!props.farmCd || !props.detail.obs_id) return
  loadAbort?.abort()
  loadAbort = new AbortController()
  loading.value = true
  errorMessage.value = ''
  try {
    const track = await fetchObservationTrack(
      props.farmCd,
      props.detail.obs_id,
      loadAbort.signal,
    )
    if (!alive) return
    trackItems.value = track.items || []
    trackCount.value = track.track_count || trackItems.value.length
  } catch (err) {
    if (!alive) return
    if (err instanceof ApiClientError && err.message.includes('취소')) return
    errorMessage.value =
      err instanceof ApiClientError ? err.message : '과실 추적 정보를 불러오지 못했습니다.'
  } finally {
    if (alive) loading.value = false
  }
}

function goTrackObservation() {
  if (!canStartTrack.value) return
  void router.push({
    name: 'observation-new',
    query: {
      parent_obs_id: props.detail.obs_id,
      from: 'fruit-track',
    },
  })
}

watch(
  () => [props.farmCd, props.detail.obs_id] as const,
  () => {
    viewerOpen.value = false
    void loadAll()
  },
)

onMounted(() => {
  alive = true
  void loadAll()
})

onBeforeUnmount(() => {
  alive = false
  loadAbort?.abort()
})

defineExpose({ reload: loadAll })
</script>

<template>
  <div class="fruit-track" aria-label="과실 추적">
    <p v-if="loading" class="hint">추적 정보를 불러오는 중…</p>
    <p v-if="errorMessage" class="error" role="alert">{{ errorMessage }}</p>

    <section class="block">
      <h3 class="block__title">추적 요약</h3>
      <p class="meta">{{ sampleLabel }}</p>
      <p class="meta">
        {{ trackCount > 0 ? `1~${trackCount}차 · 총 ${trackCount}건` : '관찰 이력 없음' }}
      </p>
      <p v-if="summaryLine" class="summary">{{ summaryLine }}</p>
    </section>

    <section class="block">
      <h3 class="block__title">타임라인</h3>
      <p v-if="trackItems.length" class="hint">
        사진 → 크게 보기 · 내용 → 해당 관찰 상세(수정·삭제)
      </p>
      <ul v-if="trackItems.length" class="timeline" role="list">
        <li
          v-for="(item, index) in trackItems"
          :key="item.obs_id"
          class="timeline__item"
          :class="{ 'timeline__item--current': item.is_current }"
          role="listitem"
        >
          <button
            type="button"
            class="timeline__thumb-btn"
            :aria-label="`${roundLabel(index)} ${item.obs_dt} 사진 크게 보기`"
            @click="openViewer(index)"
          >
            <img
              v-if="thumbSrc(item)"
              class="timeline__thumb"
              :src="thumbSrc(item)"
              alt=""
            >
            <span v-else class="timeline__thumb timeline__thumb--empty" aria-hidden="true">-</span>
          </button>
          <button
            type="button"
            class="timeline__body-btn"
            :aria-label="`${roundLabel(index)} ${item.obs_title || '관찰'} 상세 보기`"
            @click="goItemDetail(item.obs_id)"
          >
            <span class="timeline__dt">
              <span class="timeline__round">{{ roundLabel(index) }}</span>
              {{ item.obs_dt }}
              <span v-if="item.is_current" class="timeline__badge">현재</span>
            </span>
            <span class="timeline__title">{{ item.obs_title || '—' }}</span>
            <span class="timeline__nums">
              {{ fmtNum(item.width_mm) }}×{{ fmtNum(item.height_mm) }} mm
              · 둘레 {{ fmtNum(item.circumference_mm) }}
            </span>
            <span v-if="item.delta_width_mm != null" class="timeline__delta">
              Δ 가로 {{ fmtDelta(item.delta_width_mm) }}
              · 둘레 {{ fmtDelta(item.delta_circumference_mm) }}
            </span>
          </button>
        </li>
      </ul>
      <p v-else-if="!loading" class="hint">아직 추적 이력이 없습니다.</p>
    </section>

    <div v-if="showTrackAction" class="actions">
      <OdsButton
        variant="primary"
        :disabled="!canStartTrack || loading"
        @click="goTrackObservation"
      >
        추적관찰
      </OdsButton>
      <p v-if="!isCompleted" class="hint hint--gate">
        1차 관찰을 확정 저장한 뒤 추적관찰(2차)을 시작할 수 있습니다.
      </p>
    </div>

    <FruitTrackSlideViewer
      :open="viewerOpen"
      :items="trackItems"
      :index="viewerIndex"
      @close="closeViewer"
      @update:index="viewerIndex = $event"
    />
  </div>
</template>

<style scoped>
.fruit-track {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-16);
}
.block__title {
  margin: 0 0 var(--ods-space-8);
  font: var(--ods-font-body-2);
  font-weight: 700;
  color: var(--ods-color-text);
}
.meta,
.hint,
.summary,
.timeline__nums,
.timeline__delta,
.timeline__title {
  margin: 0;
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
}
.summary {
  margin-top: var(--ods-space-8);
  font-weight: 600;
  color: var(--ods-color-text);
}
.error {
  margin: 0;
  color: var(--ods-color-danger);
  font: var(--ods-font-body-2);
}
.timeline {
  list-style: none;
  margin: var(--ods-space-8) 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-8);
}
.timeline__item {
  margin: 0;
  padding: 0;
  border: 1px solid var(--ods-color-border);
  border-radius: 8px;
  background: #fff;
  overflow: hidden;
  display: flex;
  align-items: stretch;
}
.timeline__item--current {
  border-color: var(--ods-color-primary);
  background: color-mix(in srgb, var(--ods-color-primary) 8%, white);
}
.timeline__thumb-btn {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--ods-space-8);
  border: none;
  border-right: 1px solid var(--ods-color-border);
  background: transparent;
  cursor: pointer;
}
.timeline__body-btn {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: var(--ods-space-8);
  border: none;
  background: transparent;
  text-align: left;
  cursor: pointer;
  color: inherit;
}
.timeline__thumb {
  width: 56px;
  height: 56px;
  object-fit: cover;
  border-radius: 6px;
  flex-shrink: 0;
  background: var(--ods-color-gray-100, #f3f4f6);
}
.timeline__thumb--empty {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--ods-color-gray-500);
  font-weight: 700;
}
.timeline__dt {
  font: var(--ods-font-body-2);
  font-weight: 700;
  color: var(--ods-color-text);
}
.timeline__round {
  display: inline-block;
  margin-right: 6px;
  padding: 0 6px;
  border-radius: 4px;
  background: color-mix(in srgb, var(--ods-color-primary) 14%, white);
  color: var(--ods-color-primary);
  font-size: 11px;
  font-weight: 700;
  vertical-align: 1px;
}
.timeline__badge {
  margin-left: 6px;
  font-size: 11px;
  color: var(--ods-color-primary);
}
.timeline__title {
  font-weight: 600;
  color: var(--ods-color-text);
}
.actions {
  margin-top: var(--ods-space-8);
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-8);
}
.hint--gate {
  color: var(--ods-color-caution, #b45309);
}
</style>
