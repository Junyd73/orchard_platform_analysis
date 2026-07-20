<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'

import {
  fetchNotifications,
  markAllNotificationsRead,
  markNotificationRead,
} from '@/api/notifications'
import { ApiClientError } from '@/api/client'
import iconBell from '@/assets/ods/common/icon-bell.svg'
import iconCalendar from '@/assets/ods/common/icon-kpi-calendar.svg'
import iconPest from '@/assets/ods/common/icon-kpi-pest.svg'
import iconRobot from '@/assets/ods/common/icon-kpi-robot.svg'
import iconWarn from '@/assets/ods/common/icon-kpi-warn.svg'
import iconChevronRight from '@/assets/ods/scr004/icon-chevron-right.svg'
import OdsAppBar from '@/components/ods/OdsAppBar.vue'
import OdsBadge from '@/components/ods/OdsBadge.vue'
import OdsBottomNav from '@/components/ods/OdsBottomNav.vue'
import OdsEmptyState from '@/components/ods/OdsEmptyState.vue'
import NotificationDetailModal from '@/views/notification/components/NotificationDetailModal.vue'
import { resolveNotificationDeepLink } from '@/views/notification/notificationDeepLink'
import { formatNotificationTypeBadge } from '@/views/notification/notificationTypeBadge'
import { useAppStore } from '@/composables/stores/app'
import { useNotificationBadgeStore } from '@/composables/stores/notificationBadge'
import type { NotificationItem } from '@/types/notification'

const PRIORITY_URGENT = 'NP010100'

const router = useRouter()
const store = useAppStore()
const badgeStore = useNotificationBadgeStore()
const { farmCd } = storeToRefs(store)
const { unreadCount } = storeToRefs(badgeStore)

const loading = ref(true)
const errorMsg = ref('')
const items = ref<NotificationItem[]>([])
const markingAll = ref(false)
const clickingId = ref<string | null>(null)
const detailOpen = ref(false)
const selectedItem = ref<NotificationItem | null>(null)

const headerCountLabel = computed(() => {
  const total = items.value.length
  const unread = unreadCount.value
  if (loading.value) return '알림 불러오는 중…'
  if (total <= 0) return '전체 알림 0건'
  if (unread > 0) return `전체 알림 ${total}건 · 미읽음 ${unread}`
  return `전체 알림 ${total}건`
})

function badgeTone(item: NotificationItem): 'neutral' | 'ok' | 'caution' | 'danger' | 'ai' {
  if (item.priority_cd === PRIORITY_URGENT) return 'danger'
  const t = item.noti_type_cd
  if (t === 'NT010200') return 'caution'
  if (t === 'NT010300' || t === 'NT010500') return 'ai'
  if (t === 'NT010100' || t === 'NT010400') return 'ok'
  return 'neutral'
}

function typeIcon(item: NotificationItem): string {
  if (item.priority_cd === PRIORITY_URGENT || item.noti_type_cd === 'NT010200') {
    return iconWarn
  }
  if (item.noti_type_cd === 'NT010300') return iconRobot
  if (item.noti_type_cd === 'NT010100' || item.noti_type_cd === 'NT010400') {
    return iconCalendar
  }
  if (item.noti_type_cd === 'NT010500') return iconPest
  return iconBell
}

function typeIconTone(item: NotificationItem): string {
  return `ntf-card__icon--${badgeTone(item)}`
}

function hasDeepLink(item: NotificationItem): boolean {
  return resolveNotificationDeepLink(item.payload) != null
}

function formatEventAt(raw: string): string {
  const s = String(raw || '').trim()
  if (s.length >= 16) return `${s.slice(5, 10)} ${s.slice(11, 16)}`
  if (s.length >= 10) return s.slice(5, 10)
  return s || '—'
}

function goBack() {
  if (window.history.length > 1) router.back()
  else router.push({ name: 'observation' })
}

function closeDetail() {
  detailOpen.value = false
  selectedItem.value = null
}

async function navigateFromDetail() {
  const item = selectedItem.value
  if (!item) return
  const target = resolveNotificationDeepLink(item.payload)
  closeDetail()
  if (target) {
    await router.push(target)
  }
}

async function loadAll() {
  const farm = farmCd.value
  if (!farm) return
  loading.value = true
  errorMsg.value = ''
  try {
    const list = await fetchNotifications(farm, { limit: 50 })
    items.value = list
    await badgeStore.refresh(farm)
  } catch (err) {
    errorMsg.value =
      err instanceof ApiClientError ? err.message : '알림을 불러오지 못했습니다.'
    items.value = []
  } finally {
    loading.value = false
  }
}

async function onReadAll() {
  const farm = farmCd.value
  if (!farm || markingAll.value || unreadCount.value <= 0) return
  markingAll.value = true
  try {
    await markAllNotificationsRead(farm)
    await loadAll()
  } catch (err) {
    errorMsg.value =
      err instanceof ApiClientError ? err.message : '전체 읽음 처리에 실패했습니다.'
  } finally {
    markingAll.value = false
  }
}

async function handleNotificationClick(item: NotificationItem) {
  const farm = farmCd.value
  if (!farm || clickingId.value) return
  clickingId.value = item.noti_id
  try {
    if (item.read_yn !== 'Y') {
      try {
        await markNotificationRead(farm, item.noti_id)
        item.read_yn = 'Y'
      } catch {
        /* 읽음 실패해도 상세 모달은 연다 */
      }
      await badgeStore.refresh(farm)
    }
    selectedItem.value = item
    detailOpen.value = true
  } finally {
    clickingId.value = null
  }
}

onMounted(() => {
  void loadAll()
})
</script>

<template>
  <main class="ods-page-content ntf-page">
    <OdsAppBar show-back @back="goBack" />

    <section class="ntf-toolbar" aria-label="알림 도구">
      <p class="ntf-summary">{{ headerCountLabel }}</p>
      <button
        type="button"
        class="ntf-read-all"
        :disabled="markingAll || unreadCount <= 0"
        @click="onReadAll"
      >
        {{ markingAll ? '처리 중…' : '모두 읽음' }}
      </button>
    </section>

    <p v-if="errorMsg" class="ntf-error" role="alert">{{ errorMsg }}</p>
    <p v-if="loading" class="ntf-loading">불러오는 중…</p>

    <OdsEmptyState
      v-else-if="!items.length"
      title="새 알림이 없습니다."
      description="관찰·작업 관련 알림이 여기 표시됩니다."
    />

    <ul v-else class="ntf-list" aria-label="알림 목록">
      <li v-for="item in items" :key="item.noti_id">
        <button
          type="button"
          class="ntf-card"
          :class="{
            'ntf-card--unread': item.read_yn !== 'Y',
            'ntf-card--read': item.read_yn === 'Y',
            'ntf-card--busy': clickingId === item.noti_id,
          }"
          :disabled="clickingId === item.noti_id"
          @click="handleNotificationClick(item)"
        >
          <span class="ntf-card__icon" :class="typeIconTone(item)" aria-hidden="true">
            <img :src="typeIcon(item)" alt="">
          </span>

          <span class="ntf-card__center">
            <span class="ntf-card__header">
              <span
                v-if="item.read_yn !== 'Y'"
                class="ntf-card__dot"
                aria-label="미읽음"
              />
              <OdsBadge class="ntf-card__type" :tone="badgeTone(item)">
                {{ formatNotificationTypeBadge(item.noti_type_nm || item.noti_type_cd) }}
              </OdsBadge>
              <span class="ntf-card__title">{{ item.title }}</span>
            </span>
            <span v-if="item.body" class="ntf-card__body">{{ item.body }}</span>
          </span>

          <span class="ntf-card__right">
            <time class="ntf-card__time">{{ formatEventAt(item.event_at) }}</time>
            <img
              class="ntf-card__chev"
              :class="{ 'ntf-card__chev--muted': !hasDeepLink(item) }"
              :src="iconChevronRight"
              alt=""
              aria-hidden="true"
            >
          </span>
        </button>
      </li>
    </ul>

    <NotificationDetailModal
      :open="detailOpen"
      :item="selectedItem"
      @close="closeDetail"
      @navigate="navigateFromDetail"
    />

    <OdsBottomNav />
  </main>
</template>

<style scoped>
.ntf-page {
  /* padding/max-width/gap -> .ods-page-content (AppBar SSOT) */
  background: var(--ods-color-bg-muted);
  min-height: 100%;
}

.ntf-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ods-space-12);
  min-height: var(--ods-touch-min);
}

.ntf-summary {
  margin: 0;
  font: var(--ods-font-headline);
  color: var(--ods-color-text);
}

.ntf-read-all {
  flex: 0 0 auto;
  border: none;
  background: transparent;
  padding: var(--ods-space-8) var(--ods-space-4);
  min-height: var(--ods-touch-min);
  font: var(--ods-font-body-1);
  font-weight: 600;
  color: var(--ods-color-primary);
  cursor: pointer;
}

.ntf-read-all:disabled {
  color: var(--ods-color-gray-500);
  cursor: default;
}

.ntf-error {
  margin: 0;
  padding: var(--ods-space-12) var(--ods-space-16);
  border-radius: var(--ods-radius-button);
  background: color-mix(in srgb, var(--ods-color-danger) 12%, white);
  color: var(--ods-color-danger);
  font: var(--ods-font-body-2);
}

.ntf-loading {
  margin: 0;
  font: var(--ods-font-body-2);
  color: var(--ods-color-text-secondary);
}

.ntf-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-12);
}

.ntf-card {
  display: grid;
  grid-template-columns: 44px minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--ods-space-12);
  width: 100%;
  box-sizing: border-box;
  text-align: left;
  border: 1px solid var(--ods-color-gray-100);
  border-radius: var(--ods-radius-button);
  background: var(--ods-color-white);
  box-shadow: var(--ods-shadow-card);
  padding: var(--ods-space-16);
  min-height: var(--ods-touch-min);
  cursor: pointer;
  transition: opacity var(--ods-motion-fast) var(--ods-motion-ease);
}

.ntf-card--unread {
  background: color-mix(in srgb, var(--ods-color-primary-soft) 70%, white);
  border-color: color-mix(in srgb, var(--ods-color-primary) 12%, var(--ods-color-gray-100));
}

.ntf-card--read {
  opacity: 0.7;
}

.ntf-card--busy {
  opacity: 0.55;
}

.ntf-card__icon {
  width: 44px;
  height: 44px;
  border-radius: var(--ods-radius-button);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
}

.ntf-card__icon img {
  width: 22px;
  height: 22px;
  display: block;
}

.ntf-card__icon--danger {
  background: color-mix(in srgb, var(--ods-color-danger) 14%, white);
}
.ntf-card__icon--caution {
  background: color-mix(in srgb, var(--ods-color-caution) 18%, white);
}
.ntf-card__icon--ai {
  background: color-mix(in srgb, var(--ods-color-ai) 14%, white);
}
.ntf-card__icon--ok {
  background: color-mix(in srgb, var(--ods-color-primary) 12%, white);
}
.ntf-card__icon--neutral {
  background: var(--ods-color-gray-100);
}

.ntf-card__center {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-4);
}

.ntf-card__header {
  display: flex;
  align-items: center;
  gap: var(--ods-space-8);
  min-width: 0;
}

.ntf-card__type {
  flex: 0 0 auto;
  box-sizing: border-box;
  width: 2.75em;
  min-height: 2.5em;
  padding: 2px 4px;
  justify-content: center;
  text-align: center;
  white-space: pre-line;
  line-height: 1.2;
  letter-spacing: 0;
}

.ntf-card__dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: var(--ods-color-primary);
  flex: 0 0 auto;
}

.ntf-card__title {
  min-width: 0;
  font: var(--ods-font-headline);
  font-weight: 600;
  color: var(--ods-color-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.ntf-card__body {
  margin: 0;
  font: var(--ods-font-body-1);
  color: var(--ods-color-text-secondary);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.ntf-card__right {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--ods-space-8);
  align-self: stretch;
  flex: 0 0 auto;
  min-width: 52px;
}

.ntf-card__time {
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
  white-space: nowrap;
}

.ntf-card__chev {
  width: 16px;
  height: 16px;
  display: block;
  opacity: 0.7;
}

.ntf-card__chev--muted {
  opacity: 0.35;
}
</style>
