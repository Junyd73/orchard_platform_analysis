<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import {
  fetchSmartSprayBriefing,
  type SmartSprayBriefingCard,
  type SmartSprayCta,
} from '@/api/smartSpray'
import OdsAppBar from '@/components/ods/OdsAppBar.vue'
import OdsBadge from '@/components/ods/OdsBadge.vue'
import OdsBottomNav from '@/components/ods/OdsBottomNav.vue'
import OdsButton from '@/components/ods/OdsButton.vue'
import OdsCard from '@/components/ods/OdsCard.vue'
import OdsSkeleton from '@/components/ods/OdsSkeleton.vue'
import {
  LABEL_SMART_SPRAY_LAST_USE,
  LABEL_SMART_SPRAY_QTY_UNIT,
  MSG_SMART_SPRAY_CTA_HINT,
  MSG_SMART_SPRAY_JUDGE_MARK,
  MSG_SMART_SPRAY_JUDGE_NOTICE,
  MSG_SMART_SPRAY_NO_OBS,
  MSG_SMART_SPRAY_TITLE,
  PLACEHOLDER_DASH,
} from '@/views/pesticide/pesticideConstants'
import { useAppStore } from '@/composables/stores/app'
import { resolveMediaUrl } from '@/utils/mediaUrl'

const router = useRouter()
const app = useAppStore()
const farmCd = computed(() => app.farmCd)

const cards = ref<SmartSprayBriefingCard[]>([])
const workDt = ref('')
const computedAt = ref('')
const loading = ref(false)
const error = ref('')
const toastMsg = ref('')

const subtitle = computed(() => {
  const dt = workDt.value
  if (!dt) return ''
  const at = computedAt.value.trim()
  if (at.length >= 16) {
    return `${dt} · ${at.slice(11, 16)} 산출 · 예상 병해충`
  }
  return `${dt} 기준 · 예상 병해충`
})

function resolvePhotoUrl(raw: string | null | undefined): string | null {
  const url = resolveMediaUrl(raw)
  return url || null
}

function riskLabel(c: SmartSprayBriefingCard) {
  const lv = String(c.risk_level || '').trim() || PLACEHOLDER_DASH
  return `${lv} · 점수 ${c.score}`
}

function riskTone(c: SmartSprayBriefingCard): 'danger' | 'caution' | 'neutral' {
  const lv = String(c.risk_level || '').trim()
  if (lv === '위험') return 'danger'
  if (lv === '주의') return 'caution'
  return 'neutral'
}

function lastSprayLine(c: SmartSprayBriefingCard): string | null {
  const dt = String(c.last_spray_dt || '').trim()
  if (!dt) return null
  const nm = String(c.last_spray_item_nm || '').trim() || PLACEHOLDER_DASH
  const qty =
    c.last_spray_qty != null && Number(c.last_spray_qty) > 0
      ? `${c.last_spray_qty}${LABEL_SMART_SPRAY_QTY_UNIT}`
      : PLACEHOLDER_DASH
  return `${dt} · ${nm} · ${qty}`
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const res = await fetchSmartSprayBriefing(farmCd.value)
    cards.value = res.cards || []
    workDt.value = res.work_dt || ''
    computedAt.value = res.computed_at || ''
  } catch (e) {
    error.value = e instanceof Error ? e.message : '브리핑 불러오기 실패'
    cards.value = []
  } finally {
    loading.value = false
  }
}

function showToast(msg: string) {
  toastMsg.value = msg
  window.setTimeout(() => {
    if (toastMsg.value === msg) toastMsg.value = ''
  }, 2200)
}

function goCta(cta: SmartSprayCta) {
  const raw = String(cta.route || '').trim()
  if (cta.kind === 'observation') {
    // /observation/{id} 만 이동. 목록(/observation) 폴백 금지
    if (!raw || raw === '/observation' || !raw.startsWith('/observation/')) {
      showToast(MSG_SMART_SPRAY_NO_OBS)
      return
    }
  }
  if (!raw) {
    showToast(MSG_SMART_SPRAY_NO_OBS)
    return
  }
  const qIdx = raw.indexOf('?')
  const path = qIdx >= 0 ? raw.slice(0, qIdx) : raw
  const query: Record<string, string> = {}
  if (qIdx >= 0) {
    new URLSearchParams(raw.slice(qIdx + 1)).forEach((v, k) => {
      query[k] = v
    })
  }
  void router.push({ path, query })
}

function goOutbreakSettings() {
  void router.push({ name: 'pesticide-outbreak-settings' })
}

watch(farmCd, () => {
  void load()
})

onMounted(() => {
  void load()
})
</script>

<template>
  <div class="page">
    <main class="content ods-page-content">
      <OdsAppBar show-back back-fallback="pesticide" />

      <div class="stack">
        <header class="head">
          <div class="head__text">
            <h1 class="head__title">{{ MSG_SMART_SPRAY_TITLE }}</h1>
            <p v-if="subtitle" class="head__sub">{{ subtitle }}</p>
          </div>
          <OdsButton
            variant="secondary"
            :block="false"
            @click="goOutbreakSettings"
          >
            발병여건
          </OdsButton>
        </header>

        <OdsCard role="note" aria-label="살포 권고 안내">
          <p class="notice__lead">
            <OdsBadge tone="danger" class="notice__mark">
              {{ MSG_SMART_SPRAY_JUDGE_MARK }}
            </OdsBadge>
            {{ MSG_SMART_SPRAY_JUDGE_NOTICE }}
          </p>
          <p class="notice__hint">{{ MSG_SMART_SPRAY_CTA_HINT }}</p>
        </OdsCard>

        <OdsSkeleton v-if="loading" height="160px" />
        <p v-else-if="error" class="error" role="alert">{{ error }}</p>
        <ul v-else class="cards">
          <li v-for="c in cards" :key="c.pest_nm" class="card">
            <div class="card__top">
              <div class="card__main">
                <img
                  v-if="resolvePhotoUrl(c.photo_url)"
                  class="card__photo"
                  :src="resolvePhotoUrl(c.photo_url) || undefined"
                  alt=""
                />
                <div class="card__meta">
                  <h2 class="card__nm">{{ c.pest_nm }}</h2>
                  <p
                    class="card__risk"
                    :class="`card__risk--${riskTone(c)}`"
                  >
                    {{ riskLabel(c) }}
                  </p>
                </div>
              </div>
              <div class="card__badges">
                <OdsBadge :tone="riskTone(c)">
                  {{ c.risk_level || PLACEHOLDER_DASH }}
                </OdsBadge>
                <OdsBadge tone="ok">재고 {{ c.stock_count }}</OdsBadge>
              </div>
            </div>

            <div v-if="c.reasons?.length" class="why">
              <h3 class="why__title">선정 사유</h3>
              <ul class="reasons">
                <li v-for="(r, i) in c.reasons" :key="i">{{ r }}</li>
              </ul>
            </div>

            <div v-if="lastSprayLine(c)" class="last-use">
              <h3 class="last-use__title">{{ LABEL_SMART_SPRAY_LAST_USE }}</h3>
              <p class="last-use__line">{{ lastSprayLine(c) }}</p>
            </div>

            <p v-if="c.efficacy_active" class="eff">
              약효 참고 {{ c.efficacy_days_left }}일 남음
              <template v-if="c.last_spray_dt">
                · 살포 {{ c.last_spray_dt }}
              </template>
            </p>
            <p v-if="c.obs_id" class="obs">관찰 연결: {{ c.obs_id }}</p>

            <div v-if="c.ctas?.length" class="ctas">
              <OdsButton
                v-for="cta in c.ctas"
                :key="cta.kind"
                type="button"
                variant="secondary"
                :block="false"
                @click="goCta(cta)"
              >
                {{ cta.label }}
              </OdsButton>
            </div>
          </li>
          <li v-if="!cards.length" class="hint">
            표시할 예상 병해충이 없습니다.
          </li>
        </ul>
      </div>
    </main>
    <p v-if="toastMsg" class="toast" role="status">{{ toastMsg }}</p>
    <OdsBottomNav />
  </div>
</template>

<style scoped>
.page {
  min-height: 100dvh;
  background: var(--ods-color-bg-muted);
  padding-bottom: calc(var(--ods-thumb-sm) + env(safe-area-inset-bottom));
}

.stack {
  display: flex;
  flex-direction: column;
  gap: var(--ods-page-content-gap);
}

.head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--ods-space-12);
  margin: 0;
}
.head__text {
  min-width: 0;
  flex: 1 1 auto;
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

.notice__lead {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  gap: var(--ods-space-8);
  margin: 0;
  font: var(--ods-font-form-help);
  font-weight: 700;
  color: var(--ods-color-text);
  line-height: 1.45;
}
.notice__mark {
  flex: none;
  min-height: auto;
  padding: 2px var(--ods-space-8);
  transform: translateY(1px);
}
.notice__hint {
  margin: var(--ods-space-8) 0 0;
  font: var(--ods-font-form-help);
  color: var(--ods-color-text-secondary);
  line-height: 1.45;
}

.hint,
.error {
  margin: 0;
  padding: var(--ods-card-padding);
  text-align: center;
  font: var(--ods-font-form-help);
  color: var(--ods-color-text-secondary);
}
.error {
  color: var(--ods-color-danger);
}

.cards {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--ods-page-content-gap);
}
.card {
  margin: 0;
  padding: var(--ods-card-padding);
  border: 1px solid var(--ods-color-border);
  border-radius: var(--ods-radius-card);
  background: var(--ods-color-white);
  box-shadow: var(--ods-shadow-card);
}
.card__top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--ods-space-8);
}
.card__main {
  display: flex;
  gap: var(--ods-space-12);
  min-width: 0;
  flex: 1 1 auto;
}
.card__photo {
  width: var(--ods-thumb-sm);
  height: var(--ods-thumb-sm);
  object-fit: cover;
  border-radius: var(--ods-radius-button);
  flex-shrink: 0;
  background: var(--ods-color-bg-muted);
}
.card__meta {
  min-width: 0;
}
.card__nm {
  margin: 0;
  font: var(--ods-font-form-value);
  font-weight: 700;
  color: var(--ods-color-text);
}
.card__risk {
  margin: var(--ods-space-4) 0 0;
  font: var(--ods-font-form-help);
  font-weight: 700;
  color: var(--ods-color-text-secondary);
}
.card__risk--danger {
  color: var(--ods-color-danger);
}
.card__risk--caution {
  color: var(--ods-color-caution);
}
.card__risk--neutral {
  color: var(--ods-color-text-secondary);
}
.card__badges {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: var(--ods-space-4);
}

.why {
  margin: var(--ods-form-label-gap) 0 0;
}
.why__title {
  margin: 0 0 var(--ods-space-4);
  font: var(--ods-font-card-section);
  font-weight: 700;
  color: var(--ods-color-text);
}
.reasons {
  margin: 0;
  padding-left: var(--ods-space-16);
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-4);
  font: var(--ods-font-form-help);
  color: var(--ods-color-text);
  line-height: 1.45;
}

.last-use {
  margin: var(--ods-form-label-gap) 0 0;
}
.last-use__title {
  margin: 0 0 var(--ods-space-4);
  font: var(--ods-font-card-section);
  font-weight: 700;
  color: var(--ods-color-text);
}
.last-use__line {
  margin: 0;
  font: var(--ods-font-form-help);
  color: var(--ods-color-text);
  line-height: 1.45;
}

.eff {
  margin: var(--ods-form-label-gap) 0 0;
  font: var(--ods-font-card-section);
  font-weight: 700;
  color: var(--ods-color-primary);
}
.obs {
  margin: var(--ods-space-4) 0 0;
  font: var(--ods-font-card-help);
  color: var(--ods-color-text-secondary);
}

.ctas {
  display: flex;
  flex-wrap: wrap;
  gap: var(--ods-space-8);
  margin-top: var(--ods-form-field-gap);
}
.toast {
  position: fixed;
  left: 50%;
  bottom: calc(var(--ods-space-64) + var(--ods-space-8) + env(safe-area-inset-bottom));
  transform: translateX(-50%);
  z-index: 60;
  margin: 0;
  padding: var(--ods-space-8) var(--ods-space-16);
  border-radius: var(--ods-radius-button);
  background: var(--ods-color-gray-900);
  color: var(--ods-color-white);
  font: var(--ods-font-card-help);
}
</style>
