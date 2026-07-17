import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { fetchFarm, fetchFarmSites } from '@/api/farms'
import { fetchHealth } from '@/api/health'
import { ApiClientError, getApiBaseUrl } from '@/api/client'
import { DEFAULT_FARM_CD } from '@/composables/constants/app'
import type { FarmDetail } from '@/types/farm'

export type ConnectionStatus = 'idle' | 'loading' | 'ok' | 'error'

/** @deprecated import from `@/composables/constants/app` */
export { DEFAULT_FARM_CD }

export const useAppStore = defineStore('app', () => {
  const farmCd = ref(DEFAULT_FARM_CD)
  const connectionStatus = ref<ConnectionStatus>('idle')
  const connectionMessage = ref('')
  const farm = ref<FarmDetail | null>(null)
  const siteCount = ref(0)
  const farmError = ref('')

  const farmTitle = computed(() => farm.value?.farm_nm || farmCd.value)

  async function refreshAll() {
    connectionStatus.value = 'loading'
    connectionMessage.value = '확인 중…'
    farmError.value = ''
    try {
      const health = await fetchHealth()
      if (health.status !== 'ok') {
        throw new ApiClientError('서버 상태가 정상이 아닙니다.')
      }
      connectionStatus.value = 'ok'
      connectionMessage.value = '정상 연결'
    } catch (err) {
      connectionStatus.value = 'error'
      const base = getApiBaseUrl()
      connectionMessage.value =
        err instanceof ApiClientError
          ? `${err.message} (API: ${base})`
          : `연결에 실패했습니다. (API: ${base})`
      farm.value = null
      siteCount.value = 0
      return
    }

    try {
      const [farmDetail, sites] = await Promise.all([
        fetchFarm(farmCd.value),
        fetchFarmSites(farmCd.value, true),
      ])
      farm.value = farmDetail
      siteCount.value = sites.length
      farmError.value = ''
    } catch (err) {
      farm.value = null
      siteCount.value = 0
      farmError.value =
        err instanceof ApiClientError ? err.message : '농장 정보를 불러오지 못했습니다.'
    }
  }

  return {
    farmCd,
    connectionStatus,
    connectionMessage,
    farm,
    siteCount,
    farmError,
    farmTitle,
    refreshAll,
  }
})
