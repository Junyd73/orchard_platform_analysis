import { apiDelete, apiGet, apiPostJson, apiPutJson } from '@/api/client'
import type {
  ObservationBasicSavePayload,
  ObservationDetail,
  ObservationDraftItem,
  ObservationListItem,
  ObservationListQuery,
  ObservationSaveResponse,
  ObservationSummary,
} from '@/types/observation'

/** Analysis stub — 실제 인증 없음. 시그니처만 Private 와 동일 */
const USER_HEADER = { 'X-User-Id': 'MIRROR' }

export function fetchObservationSummary(
  farmCd: string,
  asOfDate?: string,
): Promise<ObservationSummary> {
  const q = asOfDate ? `?as_of_date=${encodeURIComponent(asOfDate)}` : ''
  return apiGet<ObservationSummary>(`/farms/${encodeURIComponent(farmCd)}/observations/summary${q}`)
}

export function fetchObservations(
  farmCd: string,
  query: ObservationListQuery = {},
): Promise<ObservationListItem[]> {
  const params = new URLSearchParams()
  if (query.date_from) params.set('date_from', query.date_from)
  if (query.date_to) params.set('date_to', query.date_to)
  if (query.site_id) params.set('site_id', query.site_id)
  if (query.keyword) params.set('keyword', query.keyword)
  if (query.sort) params.set('sort', query.sort)
  if (query.limit != null) params.set('limit', String(query.limit))
  const qs = params.toString()
  const path = `/farms/${encodeURIComponent(farmCd)}/observations${qs ? `?${qs}` : ''}`
  return apiGet<ObservationListItem[]>(path)
}

export function fetchObservationDrafts(
  farmCd: string,
  limit = 50,
): Promise<ObservationDraftItem[]> {
  return apiGet<ObservationDraftItem[]>(
    `/farms/${encodeURIComponent(farmCd)}/observations/drafts?limit=${limit}`,
  )
}

export function fetchObservationDetail(
  farmCd: string,
  obsId: string,
): Promise<ObservationDetail> {
  return apiGet<ObservationDetail>(
    `/farms/${encodeURIComponent(farmCd)}/observations/${encodeURIComponent(obsId)}`,
    { headers: USER_HEADER },
  )
}

export function createObservationBasic(
  farmCd: string,
  payload: ObservationBasicSavePayload,
): Promise<ObservationSaveResponse> {
  return apiPostJson<ObservationSaveResponse>(
    `/farms/${encodeURIComponent(farmCd)}/observations`,
    payload,
    { headers: USER_HEADER },
  )
}

export function updateObservationBasic(
  farmCd: string,
  obsId: string,
  payload: ObservationBasicSavePayload,
): Promise<ObservationSaveResponse> {
  return apiPutJson<ObservationSaveResponse>(
    `/farms/${encodeURIComponent(farmCd)}/observations/${encodeURIComponent(obsId)}/basic`,
    payload,
    { headers: USER_HEADER },
  )
}

export function completeObservation(
  farmCd: string,
  obsId: string,
): Promise<ObservationSaveResponse> {
  return apiPostJson<ObservationSaveResponse>(
    `/farms/${encodeURIComponent(farmCd)}/observations/${encodeURIComponent(obsId)}/complete`,
    {},
    { headers: USER_HEADER },
  )
}

export function cancelObservationDraft(
  farmCd: string,
  obsId: string,
): Promise<ObservationSaveResponse> {
  return apiPostJson<ObservationSaveResponse>(
    `/farms/${encodeURIComponent(farmCd)}/observations/${encodeURIComponent(obsId)}/cancel`,
    {},
    { headers: USER_HEADER },
  )
}

export function softDeleteObservation(
  farmCd: string,
  obsId: string,
  deleteReason?: string,
): Promise<ObservationSaveResponse> {
  const q = deleteReason
    ? `?delete_reason=${encodeURIComponent(deleteReason)}`
    : ''
  return apiDelete<ObservationSaveResponse>(
    `/farms/${encodeURIComponent(farmCd)}/observations/${encodeURIComponent(obsId)}${q}`,
    { headers: USER_HEADER },
  )
}
