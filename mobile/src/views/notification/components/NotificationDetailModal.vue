<script setup lang="ts">
import { computed } from 'vue'

import iconWarn from '@/assets/ods/common/icon-kpi-warn.svg'
import iconPest from '@/assets/ods/common/icon-kpi-pest.svg'
import OdsBadge from '@/components/ods/OdsBadge.vue'
import OdsButton from '@/components/ods/OdsButton.vue'
import { resolveNotificationDeepLink } from '@/views/notification/notificationDeepLink'
import { resolveNotificationGroup } from '@/views/notification/notificationGroupTheme'
import { resolveNotificationTypeLabel } from '@/views/notification/notificationTypeBadge'
import type { NotificationItem, NotificationPayload } from '@/types/notification'

const PRIORITY_URGENT = 'NP010100'

const props = defineProps<{
  open: boolean
  item: NotificationItem | null
}>()

const emit = defineEmits<{
  close: []
  navigate: []
}>()

type CorpRow = {
  corp_name: string
  box_qty: number
  qty_kg?: number
  max_price: number
  avg_price: number
  max_price_origin?: string
  max_price_box_qty?: number
  max_price_kg?: number
  qty_change_vs_prev?: number
}

type FlowCell = { date: string; price: number | null }
type FlowRow = {
  corp_name: string
  values: FlowCell[]
  today_price?: number | null
  pct_vs_prev?: number | null
}

type WeatherSummary = {
  temp_min?: number
  temp_max?: number
  rain_prob?: number
  rain_amount?: number
  wind_speed?: number
  humidity?: number
}

type SprayAssessment = {
  grade: 'good' | 'caution' | 'bad' | string
  grade_label: string
  rain_prob: number
  rain_amount: number
  wind_speed: number
  rain_prob_24h: number
}

const groupTheme = computed(() =>
  resolveNotificationGroup(props.item?.noti_type_cd),
)

function badgeTone(
  item: NotificationItem,
): 'neutral' | 'ok' | 'caution' | 'danger' | 'ai' {
  if (item.priority_cd === PRIORITY_URGENT) return 'danger'
  return resolveNotificationGroup(item.noti_type_cd).badgeTone
}

function formatEventAt(raw: string): string {
  const s = String(raw || '').trim()
  if (s.length >= 16) return `${s.slice(5, 10)} ${s.slice(11, 16)}`
  if (s.length >= 10) return s.slice(5, 10)
  return s || '—'
}

function formatNum(v: unknown, digits = 0): string {
  const n = Number(v)
  if (!Number.isFinite(n)) return '—'
  return n.toLocaleString('ko-KR', {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  })
}

function formatDateLabel(iso: string, isLast: boolean): string {
  const s = String(iso || '').trim()
  const md = s.length >= 10 ? s.slice(5, 10) : s
  return isLast ? `${md}(당일)` : md
}

function formatPct(pct: number | null | undefined): string {
  if (pct == null || !Number.isFinite(pct)) return ''
  const sign = pct > 0 ? '+' : ''
  return `(${sign}${pct.toFixed(1)}%)`
}

function asRecord(v: unknown): Record<string, unknown> | null {
  if (!v || typeof v !== 'object' || Array.isArray(v)) return null
  return v as Record<string, unknown>
}

function parseFlowRows(raw: unknown): FlowRow[] {
  if (!Array.isArray(raw)) return []
  return raw
    .map((row) => {
      const r = asRecord(row)
      if (!r) return null
      const valuesRaw = Array.isArray(r.values) ? r.values : []
      const values: FlowCell[] = valuesRaw.map((cell) => {
        const c = asRecord(cell)
        const price = c?.price == null ? null : Number(c.price)
        return {
          date: String(c?.date || ''),
          price: price != null && Number.isFinite(price) && price > 0 ? price : null,
        }
      })
      return {
        corp_name: String(r.corp_name || '—'),
        values,
        today_price: r.today_price == null ? null : Number(r.today_price),
        pct_vs_prev: r.pct_vs_prev == null ? null : Number(r.pct_vs_prev),
      }
    })
    .filter((x): x is FlowRow => x != null)
}

const isSignalView = computed(() => {
  const payload = props.item?.payload as NotificationPayload | null | undefined
  if (!payload) return false
  if (String(payload.view || '') === 'signal') return true
  const market = asRecord(payload.market)
  const flow = asRecord(market?.flow)
  return Boolean(flow?.max_flow || flow?.avg_flow)
})

const sprayAssessment = computed((): SprayAssessment | null => {
  const payload = props.item?.payload as NotificationPayload | null | undefined
  const spray = asRecord(payload?.spray)
  if (!spray) return null
  const grade = String(spray.grade || '')
  const label = String(spray.grade_label || '').trim()
  if (!grade && !label) return null
  return {
    grade: grade || 'bad',
    grade_label: label || '—',
    rain_prob: Number(spray.rain_prob) || 0,
    rain_amount: Number(spray.rain_amount) || 0,
    wind_speed: Number(spray.wind_speed) || 0,
    rain_prob_24h: Number(spray.rain_prob_24h) || 0,
  }
})

const sprayGradeClass = computed(() => {
  const g = sprayAssessment.value?.grade
  if (g === 'good') return 'ntf-spray__grade--good'
  if (g === 'caution') return 'ntf-spray__grade--caution'
  return 'ntf-spray__grade--bad'
})

const sourceOrg = computed(() => {
  const payload = props.item?.payload as NotificationPayload | null | undefined
  const org = String(payload?.source_org || '').trim()
  return org || ''
})

const sprayGuide = computed(() => {
  const payload = props.item?.payload as NotificationPayload | null | undefined
  const guide = asRecord(payload?.spray_guide)
  if (!guide) return null
  const title = String(guide.title || '추천 방제 및 대응 가이드').trim()
  const text = String(guide.text || '').trim()
  if (!text) return null
  const pesticides = Array.isArray(guide.pesticides)
    ? guide.pesticides.map((x) => String(x || '').trim()).filter(Boolean)
    : []
  return { title, text, pesticides }
})

const agencyLines = computed((): { agency: string; content: string }[] => {
  const payload = props.item?.payload as NotificationPayload | null | undefined
  const raw = payload?.agency_lines
  if (!Array.isArray(raw)) return []
  return raw
    .map((row) => {
      const r = asRecord(row)
      if (!r) return null
      const agency = String(r.agency || '').trim()
      const content = String(r.content || '').trim()
      if (!agency || !content) return null
      return { agency, content }
    })
    .filter((x): x is { agency: string; content: string } => x != null)
})

const flowDates = computed((): string[] => {
  const payload = props.item?.payload as NotificationPayload | null | undefined
  const market = asRecord(payload?.market)
  const flow = asRecord(market?.flow)
  const dates = flow?.dates
  if (Array.isArray(dates) && dates.length) return dates.map((d) => String(d))
  const first = maxFlowRows.value[0] || avgFlowRows.value[0]
  return (first?.values || []).map((v) => v.date)
})

const maxFlowRows = computed((): FlowRow[] => {
  const payload = props.item?.payload as NotificationPayload | null | undefined
  const market = asRecord(payload?.market)
  const flow = asRecord(market?.flow)
  return parseFlowRows(flow?.max_flow)
})

const avgFlowRows = computed((): FlowRow[] => {
  const payload = props.item?.payload as NotificationPayload | null | undefined
  const market = asRecord(payload?.market)
  const flow = asRecord(market?.flow)
  return parseFlowRows(flow?.avg_flow)
})

const corpRows = computed((): CorpRow[] => {
  if (isSignalView.value) return []
  const payload = props.item?.payload as NotificationPayload | null | undefined
  if (!payload) return []
  const market = asRecord(payload.market)
  const raw = (market?.corps ?? payload.corps) as unknown
  if (!Array.isArray(raw)) return []
  return raw
    .map((row) => {
      const r = asRecord(row)
      if (!r) return null
      return {
        corp_name: String(r.corp_name || '—'),
        box_qty: Number(r.box_qty) || 0,
        qty_kg: r.qty_kg == null ? undefined : Number(r.qty_kg),
        max_price: Number(r.max_price) || 0,
        avg_price: Number(r.avg_price) || 0,
        max_price_origin: String(r.max_price_origin || '').trim() || '—',
        max_price_box_qty:
          r.max_price_box_qty == null ? undefined : Number(r.max_price_box_qty),
        max_price_kg: r.max_price_kg == null ? undefined : Number(r.max_price_kg),
        qty_change_vs_prev:
          r.qty_change_vs_prev == null ? undefined : Number(r.qty_change_vs_prev),
      }
    })
    .filter((x): x is CorpRow => x != null)
})

function parseWeatherSummary(src: Record<string, unknown> | null): WeatherSummary | null {
  if (!src) return null
  const hasAny =
    src.temp_min != null ||
    src.temp_max != null ||
    src.rain_prob != null ||
    src.rain_amount != null ||
    src.wind_speed != null ||
    src.humidity != null
  if (!hasAny) return null
  return {
    temp_min: src.temp_min == null ? undefined : Number(src.temp_min),
    temp_max: src.temp_max == null ? undefined : Number(src.temp_max),
    rain_prob: src.rain_prob == null ? undefined : Number(src.rain_prob),
    rain_amount: src.rain_amount == null ? undefined : Number(src.rain_amount),
    wind_speed: src.wind_speed == null ? undefined : Number(src.wind_speed),
    humidity: src.humidity == null ? undefined : Number(src.humidity),
  }
}

const weatherSummary = computed((): WeatherSummary | null => {
  const payload = props.item?.payload as NotificationPayload | null | undefined
  if (!payload) return null
  const weather = asRecord(payload.weather) || asRecord(payload.metrics)
  const hasTop =
    payload.temp_min != null ||
    payload.temp_max != null ||
    payload.rain_prob != null ||
    payload.rain_amount != null
  if (!weather && !hasTop) return null
  return parseWeatherSummary(weather || (payload as Record<string, unknown>))
})

const weatherTomorrow = computed((): WeatherSummary | null => {
  const payload = props.item?.payload as NotificationPayload | null | undefined
  return parseWeatherSummary(asRecord(payload?.weather_tomorrow))
})

const hasDeepLink = computed(() => {
  return resolveNotificationDeepLink(props.item?.payload) != null
})

function onConfirm() {
  emit('close')
}

function onNavigate() {
  emit('navigate')
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open && item"
      class="ntf-sheet"
      role="dialog"
      aria-modal="true"
      :aria-label="item.title"
    >
      <button
        type="button"
        class="ntf-sheet__backdrop"
        aria-label="닫기"
        @click="emit('close')"
      />
      <div class="ntf-sheet__panel">
        <header class="ntf-sheet__head" :class="groupTheme.className">
          <div class="ntf-sheet__head-main">
            <OdsBadge :tone="badgeTone(item)" class="ntf-sheet__type">
              {{
                resolveNotificationTypeLabel(
                  item.noti_type_cd,
                  item.noti_type_nm || item.noti_type_cd,
                )
              }}
            </OdsBadge>
            <time class="ntf-sheet__time">{{ formatEventAt(item.event_at) }}</time>
          </div>
          <button type="button" class="ntf-sheet__x" aria-label="닫기" @click="emit('close')">
            ×
          </button>
          <p v-if="sourceOrg" class="ntf-sheet__source">출처: {{ sourceOrg }}</p>
        </header>

        <div class="ntf-sheet__body">
          <h2 class="ntf-sheet__title">{{ item.title }}</h2>
          <p
            v-if="!sprayAssessment && !agencyLines.length"
            class="ntf-sheet__text"
            :class="{ 'ntf-sheet__text--pre': isSignalView || Boolean(sprayGuide) }"
          >
            {{ item.body || '상세 본문이 없습니다.' }}
          </p>

          <section
            v-if="agencyLines.length"
            class="ntf-sheet__block ntf-agency"
            aria-label="기관별 병해충 안내"
          >
            <h3 class="ntf-sheet__block-title">기관별 안내</h3>
            <ul class="ntf-agency__list">
              <li
                v-for="(line, idx) in agencyLines"
                :key="`${line.agency}-${idx}`"
                class="ntf-agency__row"
              >
                <strong class="ntf-agency__name">{{ line.agency }}</strong>
                <span class="ntf-agency__sep">:</span>
                <span class="ntf-agency__content">{{ line.content }}</span>
              </li>
            </ul>
          </section>

          <section
            v-if="sprayGuide"
            class="ntf-sheet__block ntf-guide"
            aria-label="추천 방제 및 대응 가이드"
          >
            <h3 class="ntf-sheet__block-title">{{ sprayGuide.title }}</h3>
            <div class="ntf-guide__box">
              <p class="ntf-guide__text">{{ sprayGuide.text }}</p>
              <ul v-if="sprayGuide.pesticides.length" class="ntf-guide__list">
                <li v-for="name in sprayGuide.pesticides" :key="name">{{ name }}</li>
              </ul>
            </div>
          </section>

          <section
            v-if="sprayAssessment"
            class="ntf-sheet__block ntf-spray"
            aria-label="방제작업여건"
          >
            <ul class="ntf-spray__list">
              <li class="ntf-spray__row">
                <img class="ntf-spray__icon" :src="iconPest" alt="" />
                <span>
                  방제작업여건
                  <strong class="ntf-spray__grade" :class="sprayGradeClass">
                    {{ sprayAssessment.grade_label }}
                  </strong>
                </span>
              </li>
              <li class="ntf-spray__row">
                <img class="ntf-spray__icon" :src="iconWarn" alt="" />
                <span>
                  방제안내 : 강수확률({{ formatNum(sprayAssessment.rain_prob) }}%),
                  예상강수량({{ formatNum(sprayAssessment.rain_amount, 1) }}mm)
                </span>
              </li>
              <li class="ntf-spray__row">
                <img class="ntf-spray__icon" :src="iconWarn" alt="" />
                <span>풍속 : {{ formatNum(sprayAssessment.wind_speed, 1) }} m/s</span>
              </li>
              <li class="ntf-spray__row">
                <img class="ntf-spray__icon" :src="iconWarn" alt="" />
                <span>
                  24시간내 비 올 확률 : {{ formatNum(sprayAssessment.rain_prob_24h) }}%
                </span>
              </li>
            </ul>
          </section>

          <template v-if="isSignalView">
            <section
              v-if="maxFlowRows.length"
              class="ntf-sheet__block"
              aria-label="최고가 흐름"
            >
              <h3 class="ntf-sheet__block-title">도매법인별 최고가 흐름표 (최근 5영업일)</h3>
              <div class="ntf-sheet__table-wrap">
                <table class="ntf-sheet__table">
                  <thead>
                    <tr>
                      <th scope="col">법인명</th>
                      <th
                        v-for="(d, idx) in flowDates"
                        :key="`max-h-${d}`"
                        scope="col"
                      >
                        {{ formatDateLabel(d, idx === flowDates.length - 1) }}
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="row in maxFlowRows" :key="`max-${row.corp_name}`">
                      <td>{{ row.corp_name }}</td>
                      <td
                        v-for="(cell, idx) in row.values"
                        :key="`max-${row.corp_name}-${cell.date}`"
                        class="num"
                        :class="{
                          today: idx === row.values.length - 1,
                          up: idx === row.values.length - 1 && (row.pct_vs_prev || 0) > 0,
                          down: idx === row.values.length - 1 && (row.pct_vs_prev || 0) < 0,
                        }"
                      >
                        {{ formatNum(cell.price) }}
                        <span
                          v-if="idx === row.values.length - 1 && row.pct_vs_prev != null"
                          class="chg"
                        >{{ formatPct(row.pct_vs_prev) }}</span>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </section>

            <section
              v-if="avgFlowRows.length"
              class="ntf-sheet__block"
              aria-label="평균가 흐름"
            >
              <h3 class="ntf-sheet__block-title">도매법인별 평균가 흐름표 (최근 5영업일)</h3>
              <div class="ntf-sheet__table-wrap">
                <table class="ntf-sheet__table">
                  <thead>
                    <tr>
                      <th scope="col">법인명</th>
                      <th
                        v-for="(d, idx) in flowDates"
                        :key="`avg-h-${d}`"
                        scope="col"
                      >
                        {{ formatDateLabel(d, idx === flowDates.length - 1) }}
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="row in avgFlowRows" :key="`avg-${row.corp_name}`">
                      <td>{{ row.corp_name }}</td>
                      <td
                        v-for="(cell, idx) in row.values"
                        :key="`avg-${row.corp_name}-${cell.date}`"
                        class="num"
                        :class="{
                          today: idx === row.values.length - 1,
                          up: idx === row.values.length - 1 && (row.pct_vs_prev || 0) > 0,
                          down: idx === row.values.length - 1 && (row.pct_vs_prev || 0) < 0,
                        }"
                      >
                        {{ formatNum(cell.price) }}
                        <span
                          v-if="idx === row.values.length - 1 && row.pct_vs_prev != null"
                          class="chg"
                        >{{ formatPct(row.pct_vs_prev) }}</span>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </section>
          </template>

          <section v-else-if="corpRows.length" class="ntf-sheet__block" aria-label="가락 시세">
            <h3 class="ntf-sheet__block-title">도매법인별 출하 현황</h3>
            <div class="ntf-sheet__table-wrap">
              <table class="ntf-sheet__table">
                <thead>
                  <tr>
                    <th scope="col">법인명</th>
                    <th scope="col">출하량(박스)</th>
                    <th scope="col">출하량(kg)</th>
                    <th scope="col">출하지</th>
                    <th scope="col">최고가</th>
                    <th scope="col">평균가</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="row in corpRows" :key="row.corp_name">
                    <td>{{ row.corp_name }}</td>
                    <td class="num">{{ formatNum(row.box_qty) }}</td>
                    <td class="num">{{ formatNum(row.qty_kg ?? row.max_price_kg, 1) }}</td>
                    <td>{{ row.max_price_origin || '—' }}</td>
                    <td class="num">{{ formatNum(row.max_price) }}</td>
                    <td class="num">{{ formatNum(row.avg_price) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          <section
            v-if="weatherSummary"
            class="ntf-sheet__block"
            aria-label="오늘의 기상 요약"
          >
            <h3 class="ntf-sheet__block-title">오늘의 기상요약</h3>
            <div class="ntf-sheet__table-wrap">
              <table class="ntf-sheet__table ntf-sheet__table--weather">
                <tbody>
                  <tr>
                    <th scope="row">기온 (최저 / 최고)</th>
                    <td>
                      {{ formatNum(weatherSummary.temp_min, 1) }}℃
                      /
                      {{ formatNum(weatherSummary.temp_max, 1) }}℃
                    </td>
                  </tr>
                  <tr>
                    <th scope="row">강수확률 / 예상 강수량</th>
                    <td>
                      {{ formatNum(weatherSummary.rain_prob) }}%
                      /
                      {{ formatNum(weatherSummary.rain_amount, 1) }}mm
                    </td>
                  </tr>
                  <tr>
                    <th scope="row">풍속 / 습도</th>
                    <td>
                      {{ formatNum(weatherSummary.wind_speed, 1) }}m/s
                      /
                      {{ formatNum(weatherSummary.humidity, 1) }}%
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          <section
            v-if="weatherTomorrow"
            class="ntf-sheet__block"
            aria-label="내일의 기상 요약"
          >
            <h3 class="ntf-sheet__block-title">내일의 기상요약</h3>
            <div class="ntf-sheet__table-wrap">
              <table class="ntf-sheet__table ntf-sheet__table--weather">
                <tbody>
                  <tr>
                    <th scope="row">기온 (최저 / 최고)</th>
                    <td>
                      {{ formatNum(weatherTomorrow.temp_min, 1) }}℃
                      /
                      {{ formatNum(weatherTomorrow.temp_max, 1) }}℃
                    </td>
                  </tr>
                  <tr>
                    <th scope="row">강수확률 / 예상 강수량</th>
                    <td>
                      {{ formatNum(weatherTomorrow.rain_prob) }}%
                      /
                      {{ formatNum(weatherTomorrow.rain_amount, 1) }}mm
                    </td>
                  </tr>
                  <tr>
                    <th scope="row">풍속</th>
                    <td>{{ formatNum(weatherTomorrow.wind_speed, 1) }}m/s</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>
        </div>

        <footer class="ntf-sheet__foot">
          <OdsButton type="button" variant="primary" block @click="onConfirm">
            확인
          </OdsButton>
          <button
            v-if="hasDeepLink"
            type="button"
            class="ntf-sheet__link"
            @click="onNavigate"
          >
            해당 화면으로 이동 &gt;
          </button>
        </footer>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.ntf-sheet {
  position: fixed;
  inset: 0;
  z-index: 90;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
}

.ntf-sheet__backdrop {
  position: absolute;
  inset: 0;
  margin: 0;
  padding: 0;
  border: none;
  background: color-mix(in srgb, var(--ods-color-gray-900) 40%, transparent);
  cursor: pointer;
}

.ntf-sheet__panel {
  position: relative;
  max-height: min(78dvh, 640px);
  display: flex;
  flex-direction: column;
  border-radius: var(--ods-radius-card) var(--ods-radius-card) 0 0;
  background: var(--ods-color-white);
  box-shadow: var(--ods-shadow-elevated);
  padding-bottom: calc(env(safe-area-inset-bottom) + var(--ods-space-12));
}

.ntf-sheet__head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--ods-space-8) var(--ods-space-12);
  padding: var(--ods-space-16);
  border-bottom: 1px solid var(--ods-color-gray-100);
  border-top: 4px solid var(--ods-color-gray-300);
}

.ntf-sheet__head.ntf-group--market {
  border-top-color: var(--ods-color-primary);
}
.ntf-sheet__head.ntf-group--weather {
  border-top-color: var(--ods-color-ai);
}
.ntf-sheet__head.ntf-group--rda {
  border-top-color: var(--ods-color-caution);
}
.ntf-sheet__head.ntf-group--system {
  border-top-color: var(--ods-color-gray-500);
}

.ntf-sheet__head-main {
  display: flex;
  align-items: center;
  gap: var(--ods-space-8);
  min-width: 0;
  flex: 1 1 auto;
}

.ntf-sheet__source {
  flex: 1 1 100%;
  margin: 0;
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
  line-height: 1.35;
}

.ntf-sheet__time {
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
  white-space: nowrap;
}

.ntf-sheet__x {
  flex: 0 0 auto;
  width: var(--ods-touch-min);
  height: var(--ods-touch-min);
  margin: 0;
  border: none;
  border-radius: var(--ods-radius-button);
  background: var(--ods-color-gray-100);
  color: var(--ods-color-text);
  font-size: 22px;
  line-height: 1;
  cursor: pointer;
}

.ntf-sheet__body {
  flex: 1 1 auto;
  overflow-y: auto;
  padding: var(--ods-space-16);
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-16);
}

.ntf-sheet__title {
  margin: 0;
  font: var(--ods-font-title-2);
  color: var(--ods-color-text);
}

.ntf-sheet__text {
  margin: 0;
  font: var(--ods-font-body-1);
  color: var(--ods-color-text-secondary);
  white-space: pre-wrap;
  word-break: break-word;
}

.ntf-sheet__text--pre {
  white-space: pre-line;
}

.ntf-sheet__block {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-8);
}

.ntf-sheet__block-title {
  margin: 0;
  font: var(--ods-font-headline);
  color: var(--ods-color-text);
}

.ntf-sheet__table-wrap {
  overflow-x: auto;
  border: 1px solid var(--ods-color-gray-100);
  border-radius: var(--ods-radius-button);
  background: var(--ods-color-bg-muted);
}

.ntf-sheet__table {
  width: 100%;
  border-collapse: collapse;
  font: var(--ods-font-body-2);
  color: var(--ods-color-text);
}

.ntf-sheet__table th,
.ntf-sheet__table td {
  padding: var(--ods-space-8) var(--ods-space-12);
  text-align: left;
  border-bottom: 1px solid var(--ods-color-gray-100);
  white-space: nowrap;
}

.ntf-sheet__table thead th {
  font-weight: 600;
  background: var(--ods-color-white);
  color: var(--ods-color-text-secondary);
}

.ntf-sheet__table tbody tr:last-child th,
.ntf-sheet__table tbody tr:last-child td {
  border-bottom: none;
}

.ntf-sheet__table .num {
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.ntf-sheet__table .num.today {
  font-weight: 700;
}

.ntf-sheet__table .num.up {
  color: #e53935;
}

.ntf-sheet__table .num.down {
  color: #1e88e5;
}

.ntf-sheet__table .chg {
  display: block;
  font: var(--ods-font-caption);
  font-weight: 600;
}

.ntf-sheet__table--weather th {
  width: 48%;
  font-weight: 600;
  color: var(--ods-color-text-secondary);
  background: var(--ods-color-white);
}

.ntf-spray__list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-8);
}

.ntf-spray__row {
  display: flex;
  align-items: flex-start;
  gap: var(--ods-space-8);
  font: var(--ods-font-body-1);
  color: var(--ods-color-text);
}

.ntf-spray__icon {
  width: 18px;
  height: 18px;
  flex-shrink: 0;
  margin-top: 2px;
}

.ntf-spray__grade {
  margin-left: var(--ods-space-4);
  font-weight: 700;
}

.ntf-spray__grade--good {
  color: #2e7d32;
}

.ntf-spray__grade--caution {
  color: #ef6c00;
}

.ntf-spray__grade--bad {
  color: #e53935;
}

.ntf-guide__box {
  padding: var(--ods-space-12);
  border-radius: var(--ods-radius-button);
  border: 1px solid color-mix(in srgb, var(--ods-color-danger) 28%, var(--ods-color-gray-100));
  background: color-mix(in srgb, var(--ods-color-danger) 8%, white);
}

.ntf-guide__text {
  margin: 0;
  font: var(--ods-font-body-1);
  color: var(--ods-color-text);
  white-space: pre-line;
}

.ntf-guide__list {
  margin: var(--ods-space-8) 0 0;
  padding-left: 1.2em;
  font: var(--ods-font-body-2);
  color: var(--ods-color-text-secondary);
}

.ntf-agency__list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-12);
}

.ntf-agency__row {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  gap: var(--ods-space-4);
  padding: var(--ods-space-12);
  border-radius: var(--ods-radius-button);
  background: color-mix(in srgb, var(--ods-color-caution) 10%, white);
  border: 1px solid color-mix(in srgb, var(--ods-color-caution) 22%, var(--ods-color-gray-100));
  font: var(--ods-font-body-1);
  color: var(--ods-color-text);
}

.ntf-agency__name {
  flex: 0 0 auto;
  color: #e65100;
  font-weight: 700;
}

.ntf-agency__sep {
  flex: 0 0 auto;
  color: var(--ods-color-text-secondary);
}

.ntf-agency__content {
  flex: 1 1 12rem;
  min-width: 0;
  white-space: pre-line;
  word-break: break-word;
}

.ntf-sheet__foot {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-8);
  padding: var(--ods-space-12) var(--ods-space-16) 0;
}

.ntf-sheet__link {
  align-self: flex-end;
  margin: 0;
  padding: var(--ods-space-8) var(--ods-space-4);
  border: none;
  background: transparent;
  font: var(--ods-font-body-2);
  font-weight: 600;
  color: var(--ods-color-primary);
  cursor: pointer;
}
</style>
