import { getApiBaseUrl } from '@/api/client'

type ApiBaseParts = { origin: string; prefix: string }

function splitApiBase(apiBase: string): ApiBaseParts {
  const trimmed = apiBase.replace(/\/+$/, '')
  if (/^https?:\/\//i.test(trimmed)) {
    const u = new URL(trimmed)
    return { origin: u.origin, prefix: u.pathname.replace(/\/+$/, '') }
  }
  const origin =
    typeof window !== 'undefined' && window.location?.origin
      ? window.location.origin
      : 'http://127.0.0.1:5173'
  const prefix = trimmed.startsWith('/') ? trimmed : `/${trimmed}`
  return { origin, prefix }
}

/**
 * 관찰 미디어 URL 공통 해석.
 * - VITE_API_BASE_URL(…/api/v1) + 상대경로(/farms/…)
 * - LAN 모드: /api/v1 상대경로 → 현재 페이지 origin 사용
 * - 서버가 실수로 /api/v1 을 포함해도 중복하지 않음
 * - localhost/127.0.0.1 절대 URL은 API 호스트로 치환 (Android)
 */
export function resolveMediaUrl(pathOrUrl: string | null | undefined): string {
  const raw = String(pathOrUrl || '').trim()
  if (!raw) return ''

  const { origin, prefix: apiPrefix } = splitApiBase(getApiBaseUrl())

  if (/^https?:\/\//i.test(raw)) {
    try {
      const abs = new URL(raw)
      if (abs.hostname === 'localhost' || abs.hostname === '127.0.0.1') {
        let path = abs.pathname
        if (apiPrefix && path.startsWith(`${apiPrefix}/`)) {
          path = path.slice(apiPrefix.length)
        } else if (path.startsWith('/api/v1/')) {
          path = path.slice('/api/v1'.length)
        }
        return `${origin}${apiPrefix}${path}${abs.search}${abs.hash}`
      }
      return abs.toString()
    } catch {
      return raw
    }
  }

  let path = raw.startsWith('/') ? raw : `/${raw}`
  // /api/v1/farms/... → /farms/... (base 에 이미 /api/v1)
  if (apiPrefix && path.startsWith(`${apiPrefix}/`)) {
    path = path.slice(apiPrefix.length)
  } else if (path.startsWith('/api/v1/')) {
    path = path.slice('/api/v1'.length)
  }

  return `${origin}${apiPrefix}${path.startsWith('/') ? path : `/${path}`}`
}

/** @deprecated resolveMediaUrl 사용 */
export function mediaAbsoluteUrl(path: string): string {
  return resolveMediaUrl(path)
}
