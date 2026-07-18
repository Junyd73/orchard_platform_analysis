<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'

import {
  fetchObservationDetail,
  softDeleteObservation,
} from '@/api/observations'
import { fetchObservationTrack } from '@/api/observationFruit'
import { ApiClientError } from '@/api/client'
import heroIllustration from '@/assets/ods/scr004/hero-illustration.svg'
import aiIllustration from '@/assets/ods/scr004/ai-illustration.svg'
import psisIllustration from '@/assets/ods/scr004/psis-illustration.svg'
import badgeCheck from '@/assets/ods/scr004/badge-check.svg'
import badgeRobot from '@/assets/ods/scr004/badge-robot.svg'
import iconAi from '@/assets/ods/scr004/icon-ai.svg'
import iconCalendar from '@/assets/ods/scr004/icon-calendar.svg'
import iconChevron from '@/assets/ods/scr004/icon-chevron.svg'
import iconContent from '@/assets/ods/scr004/icon-content.svg'
import iconCopy from '@/assets/ods/scr004/icon-copy.svg'
import iconEdit from '@/assets/ods/scr004/icon-edit.svg'
import iconLeaf from '@/assets/ods/scr004/icon-leaf.svg'
import iconMeta from '@/assets/ods/scr004/icon-meta.svg'
import iconPencil from '@/assets/ods/scr004/icon-pencil.svg'
import iconPsis from '@/assets/ods/scr004/icon-psis.svg'
import iconTrash from '@/assets/ods/scr004/icon-trash.svg'
import iconUser from '@/assets/ods/scr004/icon-user.svg'
import OdsAppBar from '@/components/ods/OdsAppBar.vue'
import OdsBadge from '@/components/ods/OdsBadge.vue'
import OdsBottomNav from '@/components/ods/OdsBottomNav.vue'
import OdsButton from '@/components/ods/OdsButton.vue'
import OdsCard from '@/components/ods/OdsCard.vue'
import ObservationDeleteDialog from '@/views/observation/components/ObservationDeleteDialog.vue'
import AiAnalysisPanel from '@/views/observation/components/AiAnalysisPanel.vue'
import FruitTrackPanel from '@/views/observation/components/FruitTrackPanel.vue'
import PhotoPanel from '@/views/observation/components/PhotoPanel.vue'
import {
  GUIDE_LOADING,
  GUIDE_RECOMMEND_PENDING,
  GUIDE_STOCK_EMPTY,
  GUIDE_USAGE_FOR_PREFIX,
  GUIDE_USAGE_PICK_HINT,
  GUIDE_USAGE_ROWS,
  PSIS_AI_GUIDE_INTRO,
  PSIS_CARD_TITLE,
  PSIS_LOAD_FAILED,
  PSIS_PREPARING,
  PSIS_RECOMMEND_SECTION,
  PSIS_RESULT_TITLE,
  PSIS_STOCK_SECTION,
  PSIS_USAGE_SECTION,
  aiLabel,
  aiTone,
  formatDilutionWithPerLiter,
  guideDisplayText,
  guideIntroMessage,
  isAiCompleteStatus,
  resolveDilutionUnitFromSpec,
  severityTone,
  type GuideUiPhase,
} from '@/views/observation/scr004DetailUi'
import { useAppStore } from '@/composables/stores/app'
import { OBS_TARGET_FRUIT_CD } from '@/composables/constants/app'
import type {
  ObservationAiAnalysisResponse,
  ObservationDetail,
  ObservationPhotoItem,
  ObservationSmartSprayGuideResponse,
  SmartSprayGuideItem,
} from '@/types/observation'

const route = useRoute()
const router = useRouter()
const store = useAppStore()
const { farmCd, farm } = storeToRefs(store)

const obsId = computed(() => String(route.params.obsId || '').trim())
const detail = ref<ObservationDetail | null>(null)
const loading = ref(true)
const busy = ref(false)
const errorMessage = ref('')
const showDeleteDlg = ref(false)
const relatedTrackCount = ref(0)
const metaOpen = ref(false)
const copyOk = ref(false)

const canDelete = computed(() => Boolean(detail.value?.can_delete))
const isFruitObs = computed(
  () => String(detail.value?.target_type_cd || '').trim() === OBS_TARGET_FRUIT_CD,
)
/** 1차 관찰(추적 부모 없음) — 삭제 시 2차 이상 cascade 대상 */
const isRootObs = computed(
  () => !String(detail.value?.parent_obs_id || '').trim(),
)
const photoIds = ref<string[]>([])
const guidePhase = ref<GuideUiPhase>('idle')
const guide = ref<ObservationSmartSprayGuideResponse | null>(null)

const contextLine = computed(() => {
  const d = detail.value
  if (!d) return ''
  const target = (d.target_type_nm || '').trim() || '관찰'
  const site = (d.site_nm || d.site_id || '').trim() || '필지'
  return `${target} · ${site}`
})

const headline = computed(() => {
  const t = (detail.value?.obs_title || '').trim()
  return t || '(제목 없음)'
})

const locationChips = computed(() => {
  const d = detail.value
  if (!d) return []
  const items = [
    { label: '필지', value: d.site_nm || d.site_id },
    { label: '구역', value: d.zone_nm },
    { label: '열', value: d.row_no },
    { label: '나무', value: d.tree_no },
    { label: '표본', value: d.sample_no },
  ]
  return items
    .map((item) => ({ ...item, text: String(item.value || '').trim() }))
    .filter((item) => item.text)
})

const hasContent = computed(() => Boolean((detail.value?.obs_content || '').trim()))

type MetaRow = { key: string; label: string; value: string }

const metaRows = computed((): MetaRow[] => {
  const d = detail.value
  if (!d) return []
  const rows: MetaRow[] = [
    { key: 'reg', label: '작성일', value: formatDateTime(d.reg_dt || d.obs_dt) },
    { key: 'mod', label: '수정일', value: formatDateTime(d.mod_dt) },
    { key: 'author', label: '작성자', value: d.reg_id || '' },
    { key: 'editor', label: '수정자', value: d.mod_id || '' },
    { key: 'done', label: '완료일', value: formatDateTime(d.completed_at) },
    { key: 'lifecycle', label: 'Lifecycle', value: lifecycleLabel(d) },
    { key: 'obs', label: '관찰번호', value: d.obs_id },
  ]
  return rows.filter((r) => r.key === 'obs' || (r.value && r.value !== '—'))
})

function formatDateTime(raw: string | null | undefined): string {
  const s = String(raw || '').trim()
  if (!s) return '—'
  return s.length > 16 ? s.slice(0, 16) : s
}

function formatModShort(raw: string | null | undefined): string {
  const s = String(raw || '').trim()
  if (!s) return '—'
  const m = s.match(/(\d{1,2}):(\d{2})/)
  if (m) return `수정 ${m[1].padStart(2, '0')}:${m[2]}`
  return s
}

function lifecycleLabel(d: ObservationDetail): string {
  const rs = String(d.record_status || 'ACTIVE').toUpperCase()
  const os = String(d.observation_status || 'DRAFT').toUpperCase()
  if (rs === 'DELETED') return '삭제됨'
  if (os === 'DRAFT') return '작성 중'
  if (os === 'COMPLETED') return '완료'
  if (os === 'CANCELLED') return '취소'
  return os
}

function severityLabel(d: ObservationDetail): string {
  return (d.severity_nm || '').trim() || '상태'
}

const aiComplete = computed(() => isAiCompleteStatus(detail.value?.ai_status || ''))

const guideIntro = computed(() => {
  if (guidePhase.value === 'loading') return GUIDE_LOADING
  if (guidePhase.value === 'idle') {
    const s = String(detail.value?.ai_status || '').toUpperCase()
    if (s === 'ANALYZING') return PSIS_PREPARING
    if (s === 'FAILED') return PSIS_LOAD_FAILED
    if (aiComplete.value) return PSIS_AI_GUIDE_INTRO
    return ''
  }
  return guideIntroMessage(guidePhase.value)
})

const guideItems = computed(() => guide.value?.items || [])
const stockItems = computed(() => guideItems.value.filter((i) => i.has_stock))
/** ② 추천은 보완 개발 중 — 선택·사용기준은 보유 재고만 사용 */
const selectableGuideItems = computed(() => [...stockItems.value])

const selectedGuideKey = ref('')

function guideItemKey(c: SmartSprayGuideItem): string {
  return [
    c.info_id || 0,
    c.item_id || 0,
    c.rank || 0,
    c.pesticide_name || c.brand_name || '',
  ].join(':')
}

function selectGuideItem(c: SmartSprayGuideItem) {
  selectedGuideKey.value = guideItemKey(c)
}

const usageSelected = computed((): SmartSprayGuideItem | null => {
  const key = selectedGuideKey.value
  if (key) {
    const found = selectableGuideItems.value.find((c) => guideItemKey(c) === key)
    if (found) return found
  }
  return selectableGuideItems.value[0] || null
})

watch(
  selectableGuideItems,
  (list) => {
    if (!list.length) {
      selectedGuideKey.value = ''
      return
    }
    if (!list.some((c) => guideItemKey(c) === selectedGuideKey.value)) {
      selectedGuideKey.value = guideItemKey(list[0])
    }
  },
  { immediate: true },
)

const showGuideSections = computed(
  () => guidePhase.value === 'ready' || guidePhase.value === 'loading',
)

function onPhotosChanged(photos: ObservationPhotoItem[]) {
  photoIds.value = photos.map((p) => p.photo_id)
}

function onAiUpdated(res: ObservationAiAnalysisResponse) {
  if (detail.value && res.ai_status) {
    detail.value = { ...detail.value, ai_status: res.ai_status }
  }
}

function onAiConfirmed(payload: {
  ai_status: string
  confirmed_name: string
}) {
  if (detail.value) {
    detail.value = { ...detail.value, ai_status: payload.ai_status || 'CONFIRMED' }
  }
}

function onGuideUpdated(payload: {
  phase: GuideUiPhase
  guide: ObservationSmartSprayGuideResponse | null
}) {
  guidePhase.value = payload.phase
  // 로딩 중에는 기존 데이터 유지(깜빡임 최소화)
  if (payload.phase === 'loading') return
  guide.value = payload.guide
}

function usageValue(item: SmartSprayGuideItem, key: string): string {
  const map: Record<string, string | null | undefined> = {
    dilution: item.dilution,
    phi: item.phi,
    max_use_count: item.max_use_count,
    usage_method: item.usage_method,
    toxicity: item.toxicity,
  }
  const raw = map[key]
  if (key === 'dilution') {
    const unit =
      item.dilution_unit ||
      resolveDilutionUnitFromSpec(
        item.spec_nm,
        item.pesticide_name,
        item.brand_name,
      )
    return formatDilutionWithPerLiter(raw, unit)
  }
  return guideDisplayText(raw)
}

async function load() {
  if (!obsId.value) {
    errorMessage.value = '관찰 번호가 없습니다.'
    loading.value = false
    return
  }
  loading.value = true
  errorMessage.value = ''
  try {
    detail.value = await fetchObservationDetail(farmCd.value, obsId.value)
  } catch (err) {
    detail.value = null
    errorMessage.value =
      err instanceof ApiClientError ? err.message : '상세를 불러오지 못했습니다.'
  } finally {
    loading.value = false
  }
}

function goList(toast?: string) {
  void router.push({
    name: 'observation',
    query: toast ? { toast } : undefined,
  })
}

/** 항상 관찰 목록으로 이동 (수정 화면 등 history 중간 진입점 회피) */
function goBack() {
  if (busy.value) return
  goList()
}

function goEdit() {
  void router.push({
    name: 'observation-new',
    query: { obs_id: obsId.value, from: 'detail' },
  })
}

async function openDelete() {
  if (!canDelete.value || busy.value) return
  relatedTrackCount.value = 0
  if (isRootObs.value && obsId.value && farmCd.value) {
    busy.value = true
    try {
      const track = await fetchObservationTrack(farmCd.value, obsId.value)
      const total = Math.max(0, Number(track.track_count || track.items?.length || 0))
      relatedTrackCount.value = Math.max(0, total - 1)
    } catch {
      // 추적 조회 실패 시에도 삭제 확인은 진행 (서버에서 cascade 처리)
      relatedTrackCount.value = 0
    } finally {
      busy.value = false
    }
  }
  showDeleteDlg.value = true
}

async function confirmDelete() {
  if (!obsId.value || busy.value) return
  showDeleteDlg.value = false
  busy.value = true
  try {
    const res = await softDeleteObservation(
      farmCd.value,
      obsId.value,
      '사용자 삭제',
    )
    goList(res.message || '관찰 기록이 삭제되었습니다.')
  } catch (err) {
    errorMessage.value =
      err instanceof ApiClientError ? err.message : '삭제에 실패했습니다.'
  } finally {
    busy.value = false
  }
}

async function copyObsId() {
  const id = detail.value?.obs_id
  if (!id) return
  try {
    await navigator.clipboard.writeText(id)
    copyOk.value = true
    window.setTimeout(() => {
      copyOk.value = false
    }, 1600)
  } catch {
    copyOk.value = false
  }
}

onMounted(async () => {
  if (!farm.value) await store.refreshAll()
  await load()
})

watch(obsId, () => {
  guidePhase.value = 'idle'
  guide.value = null
  photoIds.value = []
  void load()
})

watch(showDeleteDlg, async (open) => {
  if (open) await nextTick()
})
</script>

<template>
  <div class="page">
    <main class="content">
      <OdsAppBar show-back @back="goBack" />

      <p v-if="loading" class="status">불러오는 중…</p>
      <p v-else-if="errorMessage" class="error" role="alert">{{ errorMessage }}</p>

      <template v-else-if="detail">
        <section class="card hero" aria-label="관찰 요약">
          <div class="hero__body">
            <p class="hero__ctx">
              <img class="hero__ctx-icon" :src="iconLeaf" alt="" aria-hidden="true">
              {{ contextLine }}
            </p>
            <h2 class="hero__title">{{ headline }}</h2>
            <div class="hero__badges">
              <OdsBadge :tone="severityTone(detail.severity_cd)" class="hero__badge">
                <img class="badge-icon" :src="badgeCheck" alt="" aria-hidden="true">
                {{ severityLabel(detail) }}
              </OdsBadge>
              <OdsBadge
                v-if="!isFruitObs"
                :tone="aiTone(detail.ai_status)"
                class="hero__badge"
              >
                <img class="badge-icon" :src="badgeRobot" alt="" aria-hidden="true">
                {{ aiLabel(detail.ai_status) }}
              </OdsBadge>
            </div>
            <ul v-if="locationChips.length" class="hero__chips">
              <li v-for="chip in locationChips" :key="chip.label" class="hero__chip">
                <span class="hero__chip-k">{{ chip.label }}</span>
                <span class="hero__chip-v">{{ chip.text }}</span>
              </li>
            </ul>
            <div class="hero__meta">
              <span class="hero__meta-item">
                <img :src="iconCalendar" alt="" aria-hidden="true">
                {{ formatDateTime(detail.reg_dt || detail.obs_dt) }}
              </span>
              <span class="hero__meta-item">
                <img :src="iconUser" alt="" aria-hidden="true">
                {{ detail.reg_id || '—' }}
              </span>
              <span class="hero__meta-item">
                <img :src="iconPencil" alt="" aria-hidden="true">
                {{ formatModShort(detail.mod_dt) }}
              </span>
            </div>
          </div>
          <img class="hero__illus" :src="heroIllustration" alt="" aria-hidden="true">
        </section>

        <OdsCard v-if="hasContent" class="detail-card" aria-label="관찰 내용">
          <h2 class="card-title">
            <img class="card-title__icon" :src="iconContent" alt="" aria-hidden="true">
            관찰 내용
          </h2>
          <p class="body-text">{{ detail.obs_content }}</p>
        </OdsCard>

        <PhotoPanel
          :farm-cd="farmCd"
          :obs-id="obsId"
          variant="scr004"
          @changed="onPhotosChanged"
        />

        <OdsCard
          v-if="isFruitObs"
          class="detail-card detail-card--fruit"
          aria-label="과실 추적"
        >
          <div class="card__head">
            <h2 class="card-title card-title--fruit">
              <img class="card-title__icon" :src="iconLeaf" alt="" aria-hidden="true">
              과실 추적
            </h2>
          </div>
          <FruitTrackPanel
            :farm-cd="farmCd"
            :detail="detail"
          />
        </OdsCard>

        <OdsCard
          v-if="!isFruitObs"
          class="detail-card detail-card--ai"
          aria-label="AI 분석"
        >
          <div class="card__head">
            <h2 class="card-title card-title--ai">
              <img class="card-title__icon" :src="iconAi" alt="" aria-hidden="true">
              AI 분석
            </h2>
            <img class="card__illus" :src="aiIllustration" alt="" aria-hidden="true">
          </div>
          <AiAnalysisPanel
            :farm-cd="farmCd"
            :obs-id="obsId"
            :photo-ids="photoIds"
            crop-name="배"
            @updated="onAiUpdated"
            @confirmed="onAiConfirmed"
            @guide-updated="onGuideUpdated"
          />
        </OdsCard>

        <OdsCard
          v-if="!isFruitObs"
          class="detail-card detail-card--psis"
          :aria-label="PSIS_CARD_TITLE"
        >
          <div class="card__head">
            <h2 class="card-title card-title--psis">
              <img class="card-title__icon" :src="iconPsis" alt="" aria-hidden="true">
              {{ PSIS_CARD_TITLE }}
            </h2>
            <img class="card__illus" :src="psisIllustration" alt="" aria-hidden="true">
          </div>
          <p v-if="guideIntro" class="ext-hint ext-hint--guide">{{ guideIntro }}</p>
          <div class="guide-block" aria-label="방제 가이드 결과">
            <h3 class="guide-block__title">{{ PSIS_RESULT_TITLE }}</h3>

            <template v-if="showGuideSections">
              <section class="guide-sec">
                <h4 class="guide-sec__h">① {{ PSIS_STOCK_SECTION }}</h4>
                <p v-if="guidePhase === 'loading' && !stockItems.length" class="guide-sec__empty">
                  {{ GUIDE_LOADING }}
                </p>
                <ul v-else-if="stockItems.length" class="guide-list" role="listbox" aria-label="보유 재고">
                  <li
                    v-for="c in stockItems"
                    :key="`stock-${guideItemKey(c)}`"
                    class="guide-list__item"
                    :class="{ 'guide-list__item--selected': guideItemKey(c) === selectedGuideKey }"
                    role="option"
                    :aria-selected="guideItemKey(c) === selectedGuideKey"
                    tabindex="0"
                    @click="selectGuideItem(c)"
                    @keydown.enter.prevent="selectGuideItem(c)"
                    @keydown.space.prevent="selectGuideItem(c)"
                  >
                    {{ guideDisplayText(c.pesticide_name || c.brand_name) }}
                    · 재고 {{ c.stock_qty }}{{ c.stock_unit || '' }}
                    <span v-if="c.last_used_date">
                      · 최근 사용 {{ c.last_used_date }}
                    </span>
                  </li>
                </ul>
                <p v-else class="guide-sec__empty">{{ GUIDE_STOCK_EMPTY }}</p>
              </section>
              <section class="guide-sec">
                <h4 class="guide-sec__h">② {{ PSIS_RECOMMEND_SECTION }}</h4>
                <p class="guide-sec__empty guide-sec__empty--pending">
                  {{ GUIDE_RECOMMEND_PENDING }}
                </p>
              </section>
              <section class="guide-sec">
                <h4 class="guide-sec__h">③ {{ PSIS_USAGE_SECTION }}</h4>
                <p v-if="!usageSelected" class="guide-sec__empty">{{ GUIDE_USAGE_PICK_HINT }}</p>
                <template v-else>
                  <p class="guide-usage__pick">
                    {{ GUIDE_USAGE_FOR_PREFIX }}
                    {{ guideDisplayText(usageSelected.pesticide_name || usageSelected.brand_name) }}
                  </p>
                  <ul class="guide-usage">
                    <li
                      v-for="row in GUIDE_USAGE_ROWS"
                      :key="row.key"
                      class="guide-usage__row"
                    >
                      <span class="guide-usage__k">{{ row.label }}</span>
                      <span class="guide-usage__v">
                        {{ usageValue(usageSelected, row.key) }}
                      </span>
                    </li>
                  </ul>
                </template>
              </section>
            </template>
          </div>
        </OdsCard>

        <OdsCard class="detail-card detail-card--meta" aria-label="관리정보">
          <button
            type="button"
            class="meta-toggle"
            :aria-expanded="metaOpen"
            @click="metaOpen = !metaOpen"
          >
            <span class="card-title meta-toggle__title">
              <img class="card-title__icon" :src="iconMeta" alt="" aria-hidden="true">
              관리정보
            </span>
            <img
              class="meta-toggle__chev"
              :class="{ 'meta-toggle__chev--open': metaOpen }"
              :src="iconChevron"
              alt=""
              aria-hidden="true"
            >
          </button>
          <div class="meta-panel" :class="{ 'meta-panel--open': metaOpen }">
            <div class="meta-inner">
              <p
                v-for="row in metaRows"
                :key="row.key"
                class="row"
                :class="{ 'row--obs': row.key === 'obs' }"
              >
                <span class="k">{{ row.label }}</span>
                <span class="v" :class="{ 'v--mono': row.key === 'obs' }">
                  {{ row.value }}
                  <button
                    v-if="row.key === 'obs'"
                    type="button"
                    class="copy"
                    @click="copyObsId"
                  >
                    <img :src="iconCopy" alt="" aria-hidden="true">
                    {{ copyOk ? '복사됨' : '복사' }}
                  </button>
                </span>
              </p>
            </div>
          </div>
        </OdsCard>
      </template>
    </main>

    <div v-if="detail && !loading" class="footer-actions">
      <OdsButton variant="secondary" :disabled="busy" :block="false" class="footer-btn" @click="goEdit">
        <span class="footer-btn__inner">
          <img :src="iconEdit" alt="" aria-hidden="true">
          수정
        </span>
      </OdsButton>
      <OdsButton
        v-if="canDelete"
        variant="danger"
        :disabled="busy"
        :block="false"
        class="footer-btn"
        @click="openDelete"
      >
        <span class="footer-btn__inner">
          <img :src="iconTrash" alt="" aria-hidden="true">
          삭제
        </span>
      </OdsButton>
    </div>

    <ObservationDeleteDialog
      :open="showDeleteDlg"
      :related-track-count="relatedTrackCount"
      @cancel="showDeleteDlg = false"
      @confirm="confirmDelete"
    />
    <OdsBottomNav />
  </div>
</template>

<style scoped>
.page {
  min-height: 100dvh;
  background: var(--ods-color-bg-muted);
  padding-bottom: calc(148px + env(safe-area-inset-bottom, 0px));
}
.content {
  max-width: 480px;
  margin: 0 auto;
  padding: var(--ods-space-12) var(--ods-page-padding-x) var(--ods-space-16);
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-16);
}
.card {
  background: var(--ods-color-white);
  border: 1px solid var(--ods-color-border);
  border-radius: var(--ods-radius-card);
  padding: var(--ods-space-20);
  box-shadow: var(--ods-shadow-card);
}
:deep(.detail-card.ods-card) {
  padding: var(--ods-space-20);
}
.card-title {
  margin: 0 0 var(--ods-space-12);
  display: flex;
  align-items: center;
  gap: var(--ods-space-8);
  font-size: 18px;
  line-height: 1.35;
  font-weight: 700;
  color: var(--ods-color-primary);
}
.card-title--ai {
  color: var(--ods-color-ai);
}
.card-title--fruit {
  color: var(--ods-color-primary);
}
.card-title--psis {
  color: var(--ods-color-ai);
}
.card-title__icon {
  width: 22px;
  height: 22px;
  flex: 0 0 auto;
}
.hero {
  position: relative;
  overflow: hidden;
  background: linear-gradient(
    135deg,
    var(--ods-color-white) 55%,
    color-mix(in srgb, var(--ods-color-secondary) 22%, white)
  );
  padding-right: 108px;
  min-height: 168px;
}
.hero__body {
  position: relative;
  z-index: 1;
  min-width: 0;
}
.hero__illus {
  position: absolute;
  right: 8px;
  top: 50%;
  transform: translateY(-50%);
  width: 108px;
  height: auto;
  pointer-events: none;
}
.hero__ctx {
  margin: 0;
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 700;
  color: var(--ods-color-primary);
}
.hero__ctx-icon {
  width: 18px;
  height: 18px;
}
.hero__title {
  margin: var(--ods-space-8) 0 0;
  font-size: 23px;
  line-height: 1.25;
  font-weight: 600;
  color: var(--ods-color-text);
  word-break: break-word;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
}
.hero__badges {
  display: flex;
  flex-wrap: wrap;
  gap: var(--ods-space-8);
  margin-top: var(--ods-space-12);
}
.hero__badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 34px;
  padding: 0 14px;
  font-size: 13px;
  font-weight: 700;
}
.badge-icon {
  width: 16px;
  height: 16px;
}
.hero__chips {
  list-style: none;
  margin: var(--ods-space-12) 0 0;
  padding: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.hero__chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  border-radius: 8px;
  background: color-mix(in srgb, var(--ods-color-primary) 8%, white);
  border: 1px solid color-mix(in srgb, var(--ods-color-primary) 18%, var(--ods-color-border));
  font-size: 12px;
  line-height: 1.3;
}
.hero__chip-k {
  color: var(--ods-color-text-secondary);
  font-weight: 600;
}
.hero__chip-v {
  color: var(--ods-color-text);
  font-weight: 700;
}
.hero__meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--ods-space-12);
  margin-top: var(--ods-space-16);
  font-size: 13px;
  color: var(--ods-color-text-secondary);
}
.hero__meta-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.hero__meta-item img {
  width: 16px;
  height: 16px;
  opacity: 0.85;
}
.body-text {
  margin: 0;
  font-size: 16px;
  line-height: 1.55;
  color: var(--ods-color-text);
  white-space: pre-wrap;
  word-break: break-word;
}
.card__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--ods-space-8);
  margin-bottom: var(--ods-space-8);
}
.card__head .card-title {
  flex: 1;
  min-width: 0;
  margin: 0;
}
.card__illus {
  width: 72px;
  height: auto;
  flex: 0 0 72px;
  align-self: flex-start;
}
.ext-lead {
  margin: 0;
  font-size: 20px;
  line-height: 1.3;
  font-weight: 700;
  color: var(--ods-color-text);
}
.ext-hint {
  margin: var(--ods-space-8) 0 0;
  font-size: 13px;
  line-height: 1.45;
  color: var(--ods-color-text-secondary);
}
.detail-dl {
  margin: var(--ods-space-12) 0 0;
}
.detail-dl__row {
  display: grid;
  grid-template-columns: 72px 1fr;
  gap: var(--ods-space-8);
  margin-bottom: 6px;
  font-size: 14px;
}
.detail-dl__row dt {
  color: var(--ods-color-text-secondary);
  font-weight: 600;
}
.detail-dl__row dd {
  margin: 0;
  color: var(--ods-color-text);
}
.reanalyze {
  margin-top: var(--ods-space-12);
}
.card--ai {
  border-color: color-mix(in srgb, var(--ods-color-ai) 28%, var(--ods-color-border));
  background: linear-gradient(
    135deg,
    var(--ods-color-white) 70%,
    color-mix(in srgb, var(--ods-color-ai) 8%, white)
  );
}
:deep(.detail-card--ai.ods-card) {
  border-color: color-mix(in srgb, var(--ods-color-ai) 28%, var(--ods-color-border));
  background: linear-gradient(
    135deg,
    var(--ods-color-white) 70%,
    color-mix(in srgb, var(--ods-color-ai) 8%, white)
  );
}
.card--psis {
  border-color: color-mix(in srgb, var(--ods-color-ai) 22%, var(--ods-color-border));
  background: linear-gradient(
    135deg,
    var(--ods-color-white) 70%,
    color-mix(in srgb, var(--ods-color-ai) 6%, white)
  );
}
:deep(.detail-card--psis.ods-card) {
  border-color: color-mix(in srgb, var(--ods-color-ai) 22%, var(--ods-color-border));
  background: linear-gradient(
    135deg,
    var(--ods-color-white) 70%,
    color-mix(in srgb, var(--ods-color-ai) 6%, white)
  );
}
.ext-hint--api {
  color: var(--ods-color-text-secondary);
  font-weight: 600;
}
.ext-hint--guide {
  margin: 0 0 var(--ods-space-12);
  color: var(--ods-color-text-secondary);
  font-weight: 600;
}
.guide-block {
  margin-top: var(--ods-space-4);
}
.guide-block__title {
  margin: 0 0 var(--ods-space-12);
  font-size: 15px;
  line-height: 1.35;
  font-weight: 700;
  color: var(--ods-color-text);
}
.guide-sec {
  margin: 0 0 var(--ods-space-12);
}
.guide-sec:last-child {
  margin-bottom: 0;
}
.guide-sec__h {
  margin: 0 0 var(--ods-space-8);
  font-size: 13px;
  line-height: 1.4;
  font-weight: 700;
  color: var(--ods-color-primary);
}
.guide-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 13px;
  line-height: 1.45;
  color: var(--ods-color-text);
}
.guide-list__item {
  margin: 0;
  padding: 8px 10px;
  border-radius: 8px;
  border: 1px solid color-mix(in srgb, var(--ods-color-border) 80%, white);
  background: #fff;
  cursor: pointer;
  text-align: left;
}
.guide-list__item:focus-visible {
  outline: 2px solid color-mix(in srgb, var(--ods-color-primary) 55%, white);
  outline-offset: 1px;
}
.guide-list__item--selected {
  border-color: color-mix(in srgb, var(--ods-color-primary) 45%, var(--ods-color-border));
  background: color-mix(in srgb, var(--ods-color-primary) 8%, white);
  box-shadow: inset 3px 0 0 var(--ods-color-primary);
}
.guide-sec__empty {
  margin: 0;
  font: var(--ods-font-body-2);
  color: var(--ods-color-text-secondary);
}
.guide-sec__empty--pending {
  font-style: italic;
}
.guide-usage__pick {
  margin: 0 0 var(--ods-space-8);
  font: var(--ods-font-caption);
  font-weight: 700;
  color: var(--ods-color-primary);
}
.guide-usage {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-8);
}
.guide-usage__row {
  display: grid;
  grid-template-columns: minmax(0, 7.5rem) minmax(0, 1fr);
  gap: var(--ods-space-8);
  align-items: start;
}
.guide-usage__k {
  font: var(--ods-font-caption);
  font-weight: 600;
  color: var(--ods-color-text-secondary);
}
.guide-usage__v {
  font: var(--ods-font-body-2);
  color: var(--ods-color-text);
  word-break: break-word;
}
.meta-toggle {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ods-space-8);
  border: none;
  background: transparent;
  padding: 0;
  cursor: pointer;
  min-height: var(--ods-touch-min);
}
.meta-toggle__title {
  margin: 0;
  color: var(--ods-color-text-secondary);
}
.meta-toggle__chev {
  width: 18px;
  height: 18px;
  transition: transform 220ms ease;
}
.meta-toggle__chev--open {
  transform: rotate(180deg);
}
.meta-panel {
  display: grid;
  grid-template-rows: 0fr;
  transition: grid-template-rows 220ms ease;
}
.meta-panel--open {
  grid-template-rows: 1fr;
}
.meta-inner {
  overflow: hidden;
  min-height: 0;
}
.meta-panel--open .meta-inner {
  padding-top: var(--ods-space-12);
}
.row {
  display: grid;
  grid-template-columns: 88px 1fr;
  gap: var(--ods-space-8);
  margin: 0 0 var(--ods-space-8);
  font-size: 14px;
  line-height: 1.45;
}
.row:last-child {
  margin-bottom: 0;
}
.k {
  color: var(--ods-color-text-secondary);
  font-weight: 600;
}
.v {
  color: var(--ods-color-text);
  word-break: break-word;
}
.v--mono {
  display: inline-flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--ods-space-8);
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 13px;
}
.copy {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border: 1px solid var(--ods-color-border);
  background: var(--ods-color-white);
  border-radius: 8px;
  min-height: 32px;
  padding: 0 10px;
  font-size: 12px;
  font-weight: 700;
  color: var(--ods-color-primary);
  cursor: pointer;
}
.copy img {
  width: 14px;
  height: 14px;
}
.footer-actions {
  position: fixed;
  left: 0;
  right: 0;
  bottom: calc(64px + env(safe-area-inset-bottom, 0px));
  z-index: 30;
  display: flex;
  gap: var(--ods-space-8);
  max-width: 480px;
  margin: 0 auto;
  padding: var(--ods-space-8) var(--ods-page-padding-x)
    calc(var(--ods-space-8) + env(safe-area-inset-bottom, 0px));
  background: color-mix(in srgb, var(--ods-color-bg-muted) 92%, transparent);
  backdrop-filter: blur(8px);
}
.footer-btn {
  flex: 1;
}
.footer-actions :deep(.footer-btn.ods-btn--secondary) {
  background: #e8f5e9;
  color: var(--ods-color-primary);
  border: 1px solid color-mix(in srgb, var(--ods-color-primary) 20%, white);
}
.footer-btn__inner {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--ods-space-8);
}
.footer-btn__inner img {
  width: 18px;
  height: 18px;
}
.footer-actions :deep(.ods-btn) {
  min-height: 48px;
}
.status {
  font: var(--ods-font-body-2);
  color: var(--ods-color-text-secondary);
}
.error {
  font: var(--ods-font-body-2);
  color: var(--ods-color-danger);
}
</style>
