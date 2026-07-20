import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { fetchNotificationSummary } from '@/api/notifications'

/** AppBar·알림 화면 공통 미읽음 배지 */
export const useNotificationBadgeStore = defineStore('notificationBadge', () => {
  const unreadCount = ref(0)
  const urgentCount = ref(0)
  const loading = ref(false)

  const unreadBadge = computed(() => {
    const n = unreadCount.value
    if (n <= 0) return ''
    return n > 99 ? '99+' : String(n)
  })

  function setCounts(unread: number, urgent = 0) {
    unreadCount.value = Math.max(0, Number(unread) || 0)
    urgentCount.value = Math.max(0, Number(urgent) || 0)
  }

  async function refresh(farmCd: string | null | undefined) {
    const farm = String(farmCd || '').trim()
    if (!farm) {
      setCounts(0, 0)
      return
    }
    loading.value = true
    try {
      const s = await fetchNotificationSummary(farm)
      setCounts(s.unread_count, s.urgent_count)
    } catch {
      /* 배지 실패는 무시 */
    } finally {
      loading.value = false
    }
  }

  return {
    unreadCount,
    urgentCount,
    unreadBadge,
    loading,
    setCounts,
    refresh,
  }
})
