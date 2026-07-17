/**
 * Analysis 미러 전용 API 스텁 (공개 저장소).
 * 실제 HTTP·LAN URL·인증정보 없음. 타입·인터페이스·mock 반환만 제공.
 */
export class ApiClientError extends Error {
  readonly status?: number
  readonly errorCode?: string

  constructor(message: string, options?: { status?: number; errorCode?: string }) {
    super(message)
    this.name = 'ApiClientError'
    this.status = options?.status
    this.errorCode = options?.errorCode
  }
}

const STUB_MSG = 'Analysis mirror: 런타임 API 미구현 (설계·타입 검증용)'

export function getApiBaseUrl(): string {
  return '/api/v1'
}

export async function apiGet<T>(_path: string, _options?: unknown): Promise<T> {
  throw new ApiClientError(STUB_MSG)
}

export async function apiPostJson<T>(_path: string, _body?: unknown, _options?: unknown): Promise<T> {
  throw new ApiClientError(STUB_MSG)
}

export async function apiPutJson<T>(_path: string, _body?: unknown, _options?: unknown): Promise<T> {
  throw new ApiClientError(STUB_MSG)
}

export async function apiDelete<T>(_path: string, _options?: unknown): Promise<T> {
  throw new ApiClientError(STUB_MSG)
}

export async function apiUploadForm<T>(
  _path: string,
  _form: FormData,
  _options?: unknown,
): Promise<T> {
  throw new ApiClientError(STUB_MSG)
}
