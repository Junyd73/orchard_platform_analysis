<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'

import { observationListThumbSrc } from '@/api/observationPhotos'
import iconChevronRight from '@/assets/ods/scr004/icon-chevron-right.svg'
import iconPin from '@/assets/ods/common/icon-pin.svg'
import { severityTone } from '@/views/observation/scr004DetailUi'
import { WEEKDAY_LABELS } from '@/views/work-log/workLogConstants'
import type { ObservationListItem } from '@/types/observation'

type ChipTone = 'ai' | 'ok' | 'caution' | 'danger' | 'neutral'

const props = defineProps<{
  item: ObservationListItem
}>()

const router = useRouter()
const thumbBroken = ref(false)

const thumbSrc = computed(() => observationListThumbSrc(props.item))
const showImage = computed(() => Boolean(thumbSrc.value) && !thumbBroken.value)

const siteLabel = computed(() => {
  const site = String(props.item.site_nm || '').trim()
  if (site) return site
  return String(props.item.location_text || '').trim() || '필지 미지정'
})

const titleLabel = computed(() => {
  const target = String(props.item.target_type_nm || '').trim()
  const title = String(props.item.obs_title || '').trim()
  if (target && title) return `${target} - ${title}`
  return title || target || '(제목 없음)'
})

const dateLabel = computed(() => formatObsListDate(props.item.obs_dt))

/** 목록: 분석 진행 상태 (확정 포함 → 분석 완료로 요약) */
const aiBadge = computed(() => listAiBadge(props.item.ai_status))

/** 목록: 위험도(OS01) — 분석 상태와 병행 표시 */
const severityBadge = computed(() => listSeverityBadge(props.item))

function formatObsListDate(iso: string): string {
  const day = String(iso || '').slice(0, 10)
  const m = day.match(/^(\d{4})-(\d{2})-(\d{2})$/)
  if (!m) return day
  const wd = WEEKDAY_LABELS[new Date(`${day}T12:00:00`).getDay()] || ''
  return `${m[1]}.${m[2]}.${m[3]} (${wd})`
}

function listAiBadge(status: string): { label: string; tone: ChipTone } {
  const s = String(status || '').trim().toUpperCase()
  if (s === 'NONE' || s === 'PENDING') return { label: 'AI 대기', tone: 'ai' }
  if (s === 'ANALYZING') return { label: '분석 중', tone: 'ai' }
  if (s === 'ANALYZED' || s === 'COMPLETED' || s === 'CONFIRMED') {
    return { label: '분석 완료', tone: 'ok' }
  }
  if (s === 'FAILED') return { label: '분석 실패', tone: 'caution' }
  if (s === 'REVIEW_REQUIRED') return { label: '검토 필요', tone: 'ai' }
  if (s === 'HOLD') return { label: '보류', tone: 'neutral' }
  return { label: s || 'AI', tone: 'neutral' }
}

function listSeverityBadge(item: ObservationListItem): { label: string; tone: ChipTone } {
  const label =
    String(item.severity_nm || '').trim() ||
    String(item.severity_cd || '').trim() ||
    '정상'
  return { label, tone: severityTone(String(item.severity_cd || '').trim()) }
}

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
</script>

<template>
  <article class="card">
    <button
      type="button"
      class="thumb"
      :class="{ 'thumb--nav': item.has_photo, 'thumb--static': !item.has_photo }"
      :aria-label="
        item.has_photo
          ? `${titleLabel} 사진 관리`
          : `${titleLabel} 사진 없음`
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
      <span v-else class="thumb__mark thumb__mark--empty">없음</span>
    </button>

    <button
      type="button"
      class="body"
      :aria-label="`${titleLabel} 상세`"
      @click="openDetail"
    >
      <p class="site">
        <img class="site__pin" :src="iconPin" alt="" aria-hidden="true">
        <span class="site__text">{{ siteLabel }}</span>
      </p>
      <h3 class="title">{{ titleLabel }}</h3>
      <p class="date">{{ dateLabel }}</p>
    </button>

    <button
      type="button"
      class="aside"
      :aria-label="`${titleLabel} 상세, ${aiBadge.label}, ${severityBadge.label}`"
      @click="openDetail"
    >
      <span class="aside__chips">
        <span class="ai-chip" :class="`ai-chip--${aiBadge.tone}`">
          {{ aiBadge.label }}
        </span>
        <span class="ai-chip" :class="`ai-chip--${severityBadge.tone}`">
          {{ severityBadge.label }}
        </span>
      </span>
      <img
        class="aside__chev"
        :src="iconChevronRight"
        alt=""
        aria-hidden="true"
      >
    </button>
  </article>
</template>

<style scoped>
.card {
  display: grid;
  grid-template-columns: 72px minmax(0, 1fr) auto;
  align-items: center;
  gap: 12px;
  width: 100%;
  min-width: 0;
  box-sizing: border-box;
  padding: 12px;
  background: var(--ods-color-white);
  border: 1px solid var(--ods-color-gray-100);
  border-radius: var(--ods-radius-card);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  overflow: hidden;
}
.thumb {
  width: 72px;
  height: 72px;
  min-height: 72px;
  margin: 0;
  padding: 0;
  border: none;
  border-radius: 12px;
  background: var(--ods-color-gray-100);
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  flex: 0 0 auto;
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
  font-weight: 500;
}
.body {
  min-width: 0;
  margin: 0;
  padding: 0;
  border: none;
  background: transparent;
  text-align: left;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.site {
  margin: 0;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  min-width: 0;
  max-width: 100%;
}
.site__pin {
  width: 12px;
  height: 12px;
  flex: 0 0 auto;
  display: block;
}
.site__text {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
  font-weight: 700;
  line-height: 1.3;
  color: var(--ods-color-primary);
}
.title {
  margin: 0;
  font-size: 15px;
  font-weight: 800;
  line-height: 1.3;
  letter-spacing: -0.02em;
  color: var(--ods-color-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.date {
  margin: 0;
  font-size: 12px;
  font-weight: 500;
  line-height: 1.3;
  color: var(--ods-color-text-secondary);
}
.aside {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin: 0;
  padding: 0;
  border: none;
  background: transparent;
  cursor: pointer;
  flex: 0 0 auto;
  align-self: center;
}
.aside__chips {
  display: inline-flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
}
.ai-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 22px;
  padding: 0 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
  line-height: 1.2;
  white-space: nowrap;
}
.ai-chip--ai {
  background: color-mix(in srgb, var(--ods-color-ai) 14%, white);
  color: var(--ods-color-ai);
}
.ai-chip--ok {
  background: color-mix(in srgb, var(--ods-color-primary) 12%, white);
  color: var(--ods-color-primary);
}
.ai-chip--caution {
  background: #fff3e0;
  color: #e65100;
}
.ai-chip--danger {
  background: #fdecea;
  color: var(--ods-color-danger);
}
.ai-chip--neutral {
  background: var(--ods-color-gray-100);
  color: var(--ods-color-gray-700);
}
.aside__chev {
  width: 16px;
  height: 16px;
  display: block;
  opacity: 0.45;
}
</style>
