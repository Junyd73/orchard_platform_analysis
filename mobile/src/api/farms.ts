import { apiGet } from '@/api/client'
import type { FarmDetail, FarmSiteSummary } from '@/types/farm'

export function fetchFarm(farmCd: string): Promise<FarmDetail> {
  return apiGet<FarmDetail>(`/farms/${encodeURIComponent(farmCd)}`)
}

export function fetchFarmSites(
  farmCd: string,
  activeOnly = true,
): Promise<FarmSiteSummary[]> {
  const q = activeOnly ? '?active_only=true' : '?active_only=false'
  return apiGet<FarmSiteSummary[]>(`/farms/${encodeURIComponent(farmCd)}/sites${q}`)
}
