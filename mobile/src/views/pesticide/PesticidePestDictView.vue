<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import OdsAppBar from '@/components/ods/OdsAppBar.vue'
import OdsBadge from '@/components/ods/OdsBadge.vue'
import OdsBottomNav from '@/components/ods/OdsBottomNav.vue'
import OdsCard from '@/components/ods/OdsCard.vue'
import OdsInput from '@/components/ods/OdsInput.vue'
import OdsSkeleton from '@/components/ods/OdsSkeleton.vue'
import { PLACEHOLDER_DASH } from '@/views/pesticide/pesticideConstants'
import {
  MSG_PEST_DICT_EFFICACY_NOTE,
  MSG_PEST_DICT_EMPTY,
  MSG_PEST_DICT_JUDGE,
  MSG_PEST_DICT_SEARCH,
  MSG_PEST_DICT_SUB,
  MSG_PEST_DICT_TITLE,
  TEMP_PEST_DICT,
  activeGenerationWindows,
  filterPestDict,
  isGenerationWindowActive,
  type PestDictEntry,
  type PestDictKind,
} from '@/views/pesticide/pestDictConstants'

const router = useRouter()
const route = useRoute()
const keyword = ref('')
const kindFilter = ref<'all' | PestDictKind>('all')
const detail = ref<PestDictEntry | null>(null)
const detailOpen = ref(false)
const refMonth = computed(() => new Date().getMonth() + 1)

/** 스마트방제 CTA 등에서 지정한 병해충 — 상세 페이지로 바로 표시(모달 없음) */
const pestQuery = computed(() => String(route.query.pest_nm || '').trim())

const focusedEntry = computed((): PestDictEntry | null => {
  const pest = pestQuery.value
  if (!pest) return null
  return (
    TEMP_PEST_DICT.find((it) => it.pest_nm === pest) ||
    filterPestDict(pest)[0] ||
    null
  )
})

const items = computed(() => {
  const base = filterPestDict(keyword.value)
  if (kindFilter.value === 'all') return base
  return base.filter((it) => it.kind === kindFilter.value)
})

/** 목록 모달 또는 CTA 직행 상세 */
const viewDetail = computed(() => focusedEntry.value || detail.value)

const detailActiveWins = computed(() => {
  if (!viewDetail.value) return []
  return activeGenerationWindows(viewDetail.value, refMonth.value)
})

function openDetail(it: PestDictEntry) {
  detail.value = it
  detailOpen.value = true
}

function closeDetail() {
  detailOpen.value = false
}

function onBack() {
  // 목록에서 연 상세 모달만 먼저 닫고, 그다음 히스토리 back
  if (!pestQuery.value && detailOpen.value) {
    closeDetail()
    return
  }
  if (window.history.length > 1) {
    router.back()
    return
  }
  void router.push({
    name: pestQuery.value ? 'pesticide-smart-spray' : 'pesticide',
  })
}

function dash(v: string | null | undefined) {
  return String(v || '').trim() || PLACEHOLDER_DASH
}

function excludeText(it: PestDictEntry) {
  return it.exclude_notes.length
    ? it.exclude_notes.join(' · ')
    : PLACEHOLDER_DASH
}

function candidatesText(it: PestDictEntry) {
  return it.candidate_pesticides.length
    ? it.candidate_pesticides.join(', ')
    : PLACEHOLDER_DASH
}

function listMeta(it: PestDictEntry) {
  return `잔효 ${it.efficacy_days}일 · ${it.summary}`
}

function kindBadgeTone(kind: PestDictKind): 'ok' | 'caution' {
  return kind === 'disease' ? 'ok' : 'caution'
}

function generationLineActive(line: string): boolean {
  const wins = viewDetail.value?.generation_windows
  if (!wins?.length) return false
  const m = refMonth.value
  return wins.some(
    (w) =>
      isGenerationWindowActive(w, m) &&
      (line.includes(w.label) || line.startsWith(w.label)),
  )
}
</script>

<template>
  <div class="page">
    <main class="content ods-page-content">
      <OdsAppBar
        show-back
        back-mode="emit"
        back-fallback="pesticide"
        @back="onBack"
      />

      <!-- 스마트방제 CTA: 해당 병해충 상세만 페이지로 표시(모달·목록 없음) -->
      <div v-if="pestQuery" class="stack">
        <OdsSkeleton v-if="!focusedEntry" height="160px" />
        <template v-else>
          <header class="head">
            <div class="head__row">
              <h1 class="head__title">{{ focusedEntry.pest_nm }}</h1>
              <OdsBadge :tone="kindBadgeTone(focusedEntry.kind)">
                {{ focusedEntry.kind_label }}
              </OdsBadge>
            </div>
            <p class="head__sub">{{ MSG_PEST_DICT_TITLE }}</p>
          </header>

          <div class="sections sections--page">
            <section class="sec">
              <h3 class="sec__title">기본 정보</h3>
              <dl class="dl">
                <div class="dl__row">
                  <dt>요약</dt>
                  <dd>{{ dash(focusedEntry.summary) }}</dd>
                </div>
                <div class="dl__row dl__row--inline">
                  <dt>잔효 참고</dt>
                  <dd>{{ focusedEntry.efficacy_days }}일</dd>
                </div>
                <div class="dl__row dl__row--inline">
                  <dt>안내 기준</dt>
                  <dd>점수 {{ focusedEntry.min_score }} 이상</dd>
                </div>
                <div class="dl__row">
                  <dt>안내 제외</dt>
                  <dd>{{ excludeText(focusedEntry) }}</dd>
                </div>
              </dl>
            </section>

            <section class="sec">
              <h3 class="sec__title">발생 · 피해</h3>
              <dl class="dl">
                <div class="dl__row">
                  <dt>발병 시기</dt>
                  <dd>{{ dash(focusedEntry.season_period) }}</dd>
                </div>
                <div class="dl__row">
                  <dt>세대별 시기</dt>
                  <dd>
                    <p
                      v-if="detailActiveWins.length"
                      class="gen-now"
                      role="status"
                    >
                      이번 달({{ refMonth }}월) 해당:
                      {{ detailActiveWins.map((w) => w.label).join(' · ') }}
                    </p>
                    <ul
                      v-if="focusedEntry.generation_windows?.length"
                      class="bullets"
                    >
                      <li
                        v-for="w in focusedEntry.generation_windows"
                        :key="w.id"
                        :class="{
                          'bullets__item--on': isGenerationWindowActive(
                            w,
                            refMonth,
                          ),
                        }"
                      >
                        {{ w.label }} ({{ w.month_from }}~{{ w.month_to }}월)
                      </li>
                    </ul>
                    <ul v-else class="bullets">
                      <li
                        v-for="(g, i) in focusedEntry.generation_periods"
                        :key="i"
                        :class="{
                          'bullets__item--on': generationLineActive(g),
                        }"
                      >
                        {{ g }}
                      </li>
                    </ul>
                  </dd>
                </div>
                <div class="dl__row">
                  <dt>발병 피해</dt>
                  <dd>{{ dash(focusedEntry.damage) }}</dd>
                </div>
              </dl>
            </section>

            <section class="sec">
              <h3 class="sec__title">방제 참고</h3>
              <dl class="dl">
                <div class="dl__row">
                  <dt>발병 여건</dt>
                  <dd>
                    <ul class="bullets">
                      <li
                        v-for="(r, i) in focusedEntry.outbreak_rules"
                        :key="i"
                      >
                        {{ r.summary }}
                        <span class="bullets__meta">(+{{ r.score }})</span>
                      </li>
                    </ul>
                  </dd>
                </div>
                <div class="dl__row">
                  <dt>관련 약제</dt>
                  <dd>{{ candidatesText(focusedEntry) }}</dd>
                </div>
                <div class="dl__row">
                  <dt>참고</dt>
                  <dd>{{ MSG_PEST_DICT_EFFICACY_NOTE }}</dd>
                </div>
              </dl>
            </section>
          </div>
        </template>
      </div>

      <!-- 병해충 사전 목록 -->
      <div v-else class="stack">
        <header class="head">
          <h1 class="head__title">{{ MSG_PEST_DICT_TITLE }}</h1>
          <p class="head__sub">{{ MSG_PEST_DICT_SUB }}</p>
        </header>

        <OdsCard role="note">{{ MSG_PEST_DICT_JUDGE }}</OdsCard>

        <OdsInput
          v-model="keyword"
          bare
          type="search"
          :placeholder="MSG_PEST_DICT_SEARCH"
        />

        <div class="tabs" role="tablist" aria-label="병해충 구분">
          <button
            type="button"
            class="tabs__btn"
            :class="{ 'tabs__btn--on': kindFilter === 'all' }"
            role="tab"
            :aria-selected="kindFilter === 'all'"
            @click="kindFilter = 'all'"
          >
            전체
          </button>
          <button
            type="button"
            class="tabs__btn"
            :class="{ 'tabs__btn--on': kindFilter === 'disease' }"
            role="tab"
            :aria-selected="kindFilter === 'disease'"
            @click="kindFilter = 'disease'"
          >
            병해
          </button>
          <button
            type="button"
            class="tabs__btn"
            :class="{ 'tabs__btn--on': kindFilter === 'pest' }"
            role="tab"
            :aria-selected="kindFilter === 'pest'"
            @click="kindFilter = 'pest'"
          >
            해충
          </button>
        </div>

        <ul class="list">
          <li
            v-for="it in items"
            :key="it.id"
            class="list__row"
            @click="openDetail(it)"
          >
            <div class="list__top">
              <p class="list__nm">{{ it.pest_nm }}</p>
              <OdsBadge :tone="kindBadgeTone(it.kind)">
                {{ it.kind_label }}
              </OdsBadge>
            </div>
            <p class="list__sub">{{ listMeta(it) }}</p>
          </li>
          <li v-if="!items.length" class="hint">{{ MSG_PEST_DICT_EMPTY }}</li>
        </ul>
      </div>
    </main>

    <div
      v-if="!pestQuery && detailOpen && detail"
      class="modal"
      role="dialog"
      aria-modal="true"
      :aria-label="detail.pest_nm"
      @click.self="closeDetail"
    >
      <div class="modal__card">
        <header class="modal__head">
          <div class="modal__titles">
            <h2>{{ detail.pest_nm }}</h2>
            <OdsBadge :tone="kindBadgeTone(detail.kind)">
              {{ detail.kind_label }}
            </OdsBadge>
          </div>
          <button type="button" class="modal__close" @click="closeDetail">
            닫기
          </button>
        </header>

        <div class="sections">
          <section class="sec">
            <h3 class="sec__title">기본 정보</h3>
            <dl class="dl">
              <div class="dl__row">
                <dt>요약</dt>
                <dd>{{ dash(detail.summary) }}</dd>
              </div>
              <div class="dl__row dl__row--inline">
                <dt>잔효 참고</dt>
                <dd>{{ detail.efficacy_days }}일</dd>
              </div>
              <div class="dl__row dl__row--inline">
                <dt>안내 기준</dt>
                <dd>점수 {{ detail.min_score }} 이상</dd>
              </div>
              <div class="dl__row">
                <dt>안내 제외</dt>
                <dd>{{ excludeText(detail) }}</dd>
              </div>
            </dl>
          </section>

          <section class="sec">
            <h3 class="sec__title">발생 · 피해</h3>
            <dl class="dl">
              <div class="dl__row">
                <dt>발병 시기</dt>
                <dd>{{ dash(detail.season_period) }}</dd>
              </div>
              <div class="dl__row">
                <dt>세대별 시기</dt>
                <dd>
                  <p
                    v-if="detailActiveWins.length"
                    class="gen-now"
                    role="status"
                  >
                    이번 달({{ refMonth }}월) 해당:
                    {{ detailActiveWins.map((w) => w.label).join(' · ') }}
                  </p>
                  <ul
                    v-if="detail.generation_windows?.length"
                    class="bullets"
                  >
                    <li
                      v-for="w in detail.generation_windows"
                      :key="w.id"
                      :class="{
                        'bullets__item--on': isGenerationWindowActive(
                          w,
                          refMonth,
                        ),
                      }"
                    >
                      {{ w.label }} ({{ w.month_from }}~{{ w.month_to }}월)
                    </li>
                  </ul>
                  <ul v-else class="bullets">
                    <li
                      v-for="(g, i) in detail.generation_periods"
                      :key="i"
                      :class="{ 'bullets__item--on': generationLineActive(g) }"
                    >
                      {{ g }}
                    </li>
                  </ul>
                </dd>
              </div>
              <div class="dl__row">
                <dt>발병 피해</dt>
                <dd>{{ dash(detail.damage) }}</dd>
              </div>
            </dl>
          </section>

          <section class="sec">
            <h3 class="sec__title">방제 참고</h3>
            <dl class="dl">
              <div class="dl__row">
                <dt>발병 여건</dt>
                <dd>
                  <ul class="bullets">
                    <li v-for="(r, i) in detail.outbreak_rules" :key="i">
                      {{ r.summary }}
                      <span class="bullets__meta">(+{{ r.score }})</span>
                    </li>
                  </ul>
                </dd>
              </div>
              <div class="dl__row">
                <dt>관련 약제</dt>
                <dd>{{ candidatesText(detail) }}</dd>
              </div>
              <div class="dl__row">
                <dt>참고</dt>
                <dd>{{ MSG_PEST_DICT_EFFICACY_NOTE }}</dd>
              </div>
            </dl>
          </section>
        </div>
      </div>
    </div>

    <OdsBottomNav />
  </div>
</template>

<style scoped>
.page {
  min-height: 100dvh;
  background: var(--ods-color-bg-muted);
  padding-bottom: calc(var(--ods-thumb-sm) + env(safe-area-inset-bottom));
}

/* AppBar 아래 블록 간격 — ODS page-content-gap(16) 통일 */
.stack {
  display: flex;
  flex-direction: column;
  gap: var(--ods-page-content-gap);
}

.head {
  margin: 0;
}
.head__title {
  margin: 0;
  font: var(--ods-font-title-2);
  font-weight: 800;
  color: var(--ods-color-text);
}
.head__sub {
  margin: var(--ods-section-title-gap) 0 0;
  font: var(--ods-font-form-help);
  color: var(--ods-color-text-secondary);
  line-height: 1.45;
}
.head__row {
  display: flex;
  align-items: center;
  gap: var(--ods-space-8);
  flex-wrap: wrap;
}
.sections--page {
  display: flex;
  flex-direction: column;
  gap: var(--ods-page-content-gap);
}

.tabs {
  display: flex;
  gap: var(--ods-space-8);
  margin: 0;
}
.tabs__btn {
  flex: 1 1 0;
  min-height: var(--ods-control-height);
  margin: 0;
  padding: 0 var(--ods-space-8);
  border: 1px solid var(--ods-color-border);
  border-radius: var(--ods-radius-badge);
  background: var(--ods-color-white);
  font: var(--ods-font-card-help);
  font-weight: 700;
  color: var(--ods-color-text-secondary);
  cursor: pointer;
}
.tabs__btn--on {
  border-color: var(--ods-color-primary);
  background: color-mix(in srgb, var(--ods-color-primary) 12%, var(--ods-color-white));
  color: var(--ods-color-primary);
}

.list {
  margin: 0;
  padding: 0;
  list-style: none;
  border-radius: var(--ods-radius-card);
  background: var(--ods-color-white);
  border: 1px solid var(--ods-color-border);
  box-shadow: var(--ods-shadow-card);
  overflow: hidden;
}
.list__row {
  padding: var(--ods-space-12) var(--ods-card-padding);
  border-bottom: 1px solid var(--ods-color-border);
  cursor: pointer;
}
.list__row:last-child {
  border-bottom: none;
}
.list__row:active {
  background: var(--ods-color-bg-muted);
}
.list__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ods-space-8);
}
.list__nm {
  margin: 0;
  font: var(--ods-font-form-value);
  font-weight: 700;
  color: var(--ods-color-text);
}
.list__sub {
  margin: var(--ods-space-4) 0 0;
  font: var(--ods-font-card-section);
  color: var(--ods-color-text-secondary);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.hint {
  margin: 0;
  padding: var(--ods-space-16);
  text-align: center;
  font: var(--ods-font-form-help);
  color: var(--ods-color-text-secondary);
}

.modal {
  position: fixed;
  inset: 0;
  z-index: 80;
  display: flex;
  align-items: flex-end;
  justify-content: center;
  padding: var(--ods-space-12);
  background: color-mix(in srgb, var(--ods-color-gray-900) 45%, transparent);
}
.modal__card {
  width: min(520px, 100%);
  max-height: 80dvh;
  overflow: auto;
  padding: var(--ods-space-16);
  border: 1px solid var(--ods-color-border);
  border-radius: var(--ods-radius-card) var(--ods-radius-card)
    var(--ods-radius-button) var(--ods-radius-button);
  background: var(--ods-color-white);
  box-shadow: var(--ods-shadow-card);
}
.modal__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--ods-space-8);
  margin-bottom: var(--ods-form-field-gap);
  padding-bottom: var(--ods-space-12);
  border-bottom: 1px solid var(--ods-color-border);
}
.modal__titles {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--ods-space-8);
  min-width: 0;
}
.modal__head h2 {
  margin: 0;
  font: var(--ods-font-title-2);
  font-weight: 800;
  color: var(--ods-color-text);
}
.modal__close {
  flex-shrink: 0;
  min-height: var(--ods-control-height);
  margin: 0;
  padding: 0 var(--ods-space-8);
  border: 0;
  background: transparent;
  font: var(--ods-font-form-label);
  color: var(--ods-color-primary);
  cursor: pointer;
}

.sections {
  display: flex;
  flex-direction: column;
  gap: var(--ods-form-field-gap);
}
.sec__title {
  margin: 0 0 var(--ods-form-label-gap);
  font: var(--ods-font-form-label);
  color: var(--ods-color-text);
}
.dl {
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: var(--ods-form-field-gap);
}
.dl__row {
  display: flex;
  flex-direction: column;
  gap: var(--ods-form-label-gap);
}
.dl__row--inline {
  display: grid;
  grid-template-columns: 88px 1fr;
  gap: var(--ods-space-8);
  align-items: start;
}
.dl__row dt {
  margin: 0;
  font: var(--ods-font-card-section);
  color: var(--ods-color-text-secondary);
}
.dl__row dd {
  margin: 0;
  font: var(--ods-font-form-value);
  color: var(--ods-color-text);
  word-break: keep-all;
  line-height: 1.45;
}
.dl__row--inline dt {
  font: var(--ods-font-form-help);
  font-weight: 600;
}
.dl__row--inline dd {
  font: var(--ods-font-form-help);
  font-weight: 600;
}

.bullets {
  margin: 0;
  padding-left: var(--ods-space-16);
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-4);
}
.bullets li {
  font: var(--ods-font-form-help);
  font-weight: 600;
  color: var(--ods-color-text);
  line-height: 1.45;
}
.bullets__item--on {
  font-weight: 800;
  color: var(--ods-color-primary);
}
.gen-now {
  margin: 0 0 var(--ods-space-8);
  padding: var(--ods-space-8);
  border-radius: var(--ods-radius-badge);
  background: color-mix(in srgb, var(--ods-color-primary) 12%, var(--ods-color-white));
  color: var(--ods-color-primary);
  font: var(--ods-font-card-meta);
  font-weight: 700;
}
.bullets__meta {
  font-weight: 500;
  color: var(--ods-color-text-secondary);
}
</style>
