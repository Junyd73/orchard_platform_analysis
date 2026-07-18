import { ApiClientError } from '@/api/client'

/** Analysis 미러 스텁 — HTTP 미호출, 시그니처만 Private 와 동일 */
export function fetchObservationAiAnalysis(
  _farmCd: string,
  _obsId: string,
  _signal?: AbortSignal,
): Promise<never> {
  return Promise.reject(new ApiClientError('Analysis mirror stub'))
}

export function requestObservationAiAnalysis(
  _farmCd: string,
  _obsId: string,
  _body: unknown,
  _options?: { signal?: AbortSignal },
): Promise<never> {
  return Promise.reject(new ApiClientError('Analysis mirror stub'))
}
