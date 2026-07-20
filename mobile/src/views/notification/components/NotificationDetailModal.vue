<script setup lang="ts">
import { computed } from 'vue'

import OdsBadge from '@/components/ods/OdsBadge.vue'
import OdsButton from '@/components/ods/OdsButton.vue'
import { resolveNotificationDeepLink } from '@/views/notification/notificationDeepLink'
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
  max_price: number
  avg_price: number
  max_price_origin?: string
  max_price_box_qty?: number
  max_price_kg?: number
  qty_change_vs_prev?: number
}

type WeatherSummary = {
  temp_min?: number
  temp_max?: number
  rain_prob?: number
  rain_amount?: number
  wind_speed?: number
  humidity?: number
}

function badgeTone(
  item: NotificationItem,
): 'neutral' | 'ok' | 'caution' | 'danger' | 'ai' {
  if (item.priority_cd === PRIORITY_URGENT) return 'danger'
  const t = item.noti_type_cd
  if (t === 'NT010200') return 'caution'
  if (t === 'NT010300' || t === 'NT010500' || t === 'NT011000') return 'ai'
  if (t === 'NT010100' || t === 'NT010400' || t === 'NT010600') return 'ok'
  return 'neutral'
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

function asRecord(v: unknown): Record<string, unknown> | null {
  if (!v || typeof v !== 'object' || Array.isArray(v)) return null
  return v as Record<string, unknown>
}

const corpRows = computed((): CorpRow[] => {
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
  const src = weather || (payload as Record<string, unknown>)
  return {
    temp_min: src.temp_min == null ? undefined : Number(src.temp_min),
    temp_max: src.temp_max == null ? undefined : Number(src.temp_max),
    rain_prob: src.rain_prob == null ? undefined : Number(src.rain_prob),
    rain_amount: src.rain_amount == null ? undefined : Number(src.rain_amount),
    wind_speed: src.wind_speed == null ? undefined : Number(src.wind_speed),
    humidity: src.humidity == null ? undefined : Number(src.humidity),
  }
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
        <header class="ntf-sheet__head">
          <div class="ntf-sheet__head-main">
            <OdsBadge :tone="badgeTone(item)">
              {{ item.noti_type_nm || item.noti_type_cd }}
            </OdsBadge>
            <time class="ntf-sheet__time">{{ formatEventAt(item.event_at) }}</time>
          </div>
          <button type="button" class="ntf-sheet__x" aria-label="닫기" @click="emit('close')">
            ×
          </button>
        </header>

        <div class="ntf-sheet__body">
          <h2 class="ntf-sheet__title">{{ item.title }}</h2>
          <p class="ntf-sheet__text">
            {{ item.body || '상세 본문이 없습니다.' }}
          </p>

          <section v-if="corpRows.length" class="ntf-sheet__block" aria-label="가락 시세">
            <h3 class="ntf-sheet__block-title">도매법인별 출하 현황</h3>
            <div class="ntf-sheet__table-wrap">
              <table class="ntf-sheet__table">
                <thead>
                  <tr>
                    <th scope="col">도매법인</th>
                    <th scope="col">출하량(box)</th>
                    <th scope="col">최고가</th>
                    <th scope="col">최고가 출하지</th>
                    <th scope="col">출하량(kg)</th>
                    <th scope="col">평균가</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="row in corpRows" :key="row.corp_name">
                    <td>{{ row.corp_name }}</td>
                    <td class="num">{{ formatNum(row.box_qty) }}</td>
                    <td class="num">{{ formatNum(row.max_price) }}</td>
                    <td>{{ row.max_price_origin || '—' }}</td>
                    <td class="num">{{ formatNum(row.max_price_kg, 1) }}</td>
                    <td class="num">{{ formatNum(row.avg_price) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          <section
            v-if="weatherSummary"
            class="ntf-sheet__block"
            aria-label="기상 요약"
          >
            <h3 class="ntf-sheet__block-title">오늘의 기상 요약</h3>
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
  align-items: center;
  justify-content: space-between;
  gap: var(--ods-space-12);
  padding: var(--ods-space-16);
  border-bottom: 1px solid var(--ods-color-gray-100);
}

.ntf-sheet__head-main {
  display: flex;
  align-items: center;
  gap: var(--ods-space-8);
  min-width: 0;
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

.ntf-sheet__table--weather th {
  width: 48%;
  font-weight: 600;
  color: var(--ods-color-text-secondary);
  background: var(--ods-color-white);
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
