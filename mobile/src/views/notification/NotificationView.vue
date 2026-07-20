<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'

import {
  fetchNotificationSummary,
  fetchNotifications,
  markAllNotificationsRead,
  markNotificationRead,
} from '@/api/notifications'
import { ApiClientError } from '@/api/client'
import OdsAppBar from '@/components/ods/OdsAppBar.vue'
import OdsBadge from '@/components/ods/OdsBadge.vue'
import OdsBottomNav from '@/components/ods/OdsBottomNav.vue'
import OdsButton from '@/components/ods/OdsButton.vue'
import OdsEmptyState from '@/components/ods/OdsEmptyState.vue'
import { useAppStore } from '@/composables/stores/app'
import type { NotificationItem } from '@/types/notification'

const PRIORITY_URGENT = 'NP010100'

const router = useRouter()
const store = useAppStore()
const { farmCd } = storeToRefs(store)

const loading = ref(true)
const errorMsg = ref('')
const items = ref<NotificationItem[]>([])
const unreadCount = ref(0)
const urgentCount = ref(0)
const markingAll = ref(false)

const summaryLine = computed(() => {
  const u = unreadCount.value
  const g = urgentCount.value
  if (u <= 0) return '새 알림이 없습니다.'
  if (g > 0) return `미읽음 ${u}건 · 긴급 ${g}건`
  return `미읽음 ${u}건`
})

function badgeTone(item: NotificationItem): 'neutral' | 'ok' | 'caution' | 'danger' | 'ai' {
  if (item.priority_cd === PRIORITY_URGENT) return 'danger'
  const t = item.noti_type_cd
  if (t === 'NT010200') return 'caution'
  if (t === 'NT010300' || t === 'NT010500') return 'ai'
  if (t === 'NT010100' || t === 'NT010400') return 'ok'
  return 'neutral'
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

async function loadAll() {
  const farm = farmCd.value
  if (!farm) return
  loading.value = true
  errorMsg.value = ''
  try {
    const [list, summary] = await Promise.all([
      fetchNotifications(farm, { limit: 50 }),
      fetchNotificationSummary(farm),
    ])
    items.value = list
    unreadCount.value = summary.unread_count
    urgentCount.value = summary.urgent_count
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
  if (!farm || markingAll.value) return
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

function navigatePayload(item: NotificationItem) {
  const p = item.payload || {}
  const route = String(p.route || '').trim()
  if (route === 'observation-detail' && p.obs_id) {
    void router.push({
      name: 'observation-detail',
      params: { obsId: String(p.obs_id) },
    })
    return
  }
  if (route === 'observation-list') {
    void router.push({ name: 'observation' })
    return
  }
  if (route === 'work-log-daily' && p.work_dt) {
    void router.push({
      name: 'work-log-daily',
      params: { workDt: String(p.work_dt) },
    })
    return
  }
}

async function onItemClick(item: NotificationItem) {
  const farm = farmCd.value
  if (!farm) return
  try {
    if (item.read_yn !== 'Y') {
      await markNotificationRead(farm, item.noti_id)
      item.read_yn = 'Y'
      unreadCount.value = Math.max(0, unreadCount.value - 1)
      if (item.priority_cd === PRIORITY_URGENT) {
        urgentCount.value = Math.max(0, urgentCount.value - 1)
      }
    }
  } catch {
    /* 읽음 실패해도 딥링크는 시도 */
  }
  navigatePayload(item)
}

onMounted(() => {
  void loadAll()
})
</script>

<template>
  <main class="ods-page-content ntf-page">
    <OdsAppBar show-back @back="goBack" />

    <section class="ntf-toolbar" aria-label="알림 도구">
      <p class="ntf-summary">{{ summaryLine }}</p>
      <OdsButton
        variant="secondary"
        :block="false"
        :disabled="markingAll || unreadCount <= 0"
        :busy="markingAll"
        @click="onReadAll"
      >
        전체 읽음
      </OdsButton>
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
          :class="{ 'ntf-card--unread': item.read_yn !== 'Y' }"
          @click="onItemClick(item)"
        >
          <span
            v-if="item.priority_cd === PRIORITY_URGENT"
            class="ntf-card__urgent"
            aria-hidden="true"
          />
          <div class="ntf-card__body">
            <div class="ntf-card__meta">
              <OdsBadge :tone="badgeTone(item)">
                {{ item.noti_type_nm || item.noti_type_cd }}
              </OdsBadge>
              <OdsBadge
                v-if="item.priority_cd === PRIORITY_URGENT"
                tone="danger"
              >
                {{ item.priority_nm || '긴급' }}
              </OdsBadge>
              <time class="ntf-card__time">{{ formatEventAt(item.event_at) }}</time>
            </div>
            <p class="ntf-card__title">{{ item.title }}</p>
            <p v-if="item.body" class="ntf-card__text">{{ item.body }}</p>
          </div>
        </button>
      </li>
    </ul>

    <OdsBottomNav />
  </main>
</template>

<style scoped>
.ntf-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ods-space-12);
}
.ntf-summary {
  margin: 0;
  font: var(--ods-font-body-2);
  color: var(--ods-color-text-secondary);
}
.ntf-error {
  margin: 0;
  padding: var(--ods-space-12);
  border-radius: var(--ods-radius-card);
  background: #fdecea;
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
  gap: var(--ods-space-10);
}
.ntf-card {
  position: relative;
  display: flex;
  width: 100%;
  text-align: left;
  border: 1px solid var(--ods-color-border);
  border-radius: var(--ods-radius-card);
  background: var(--ods-color-white);
  box-shadow: var(--ods-shadow-card);
  padding: var(--ods-space-12) var(--ods-space-14);
  min-height: var(--ods-touch-min);
  cursor: pointer;
}
.ntf-card--unread {
  background: var(--ods-color-primary-soft, #eef6ee);
}
.ntf-card__urgent {
  position: absolute;
  left: 0;
  top: 8px;
  bottom: 8px;
  width: 4px;
  border-radius: 0 4px 4px 0;
  background: var(--ods-color-danger);
}
.ntf-card__body {
  flex: 1;
  min-width: 0;
  padding-left: var(--ods-space-4);
}
.ntf-card__meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--ods-space-6);
  margin-bottom: var(--ods-space-6);
}
.ntf-card__time {
  margin-left: auto;
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
}
.ntf-card__title {
  margin: 0;
  font: var(--ods-font-body-1);
  font-weight: 700;
  color: var(--ods-color-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.ntf-card__text {
  margin: var(--ods-space-4) 0 0;
  font: var(--ods-font-body-2);
  color: var(--ods-color-text-secondary);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
