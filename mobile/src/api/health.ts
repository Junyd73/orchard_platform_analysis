import { apiGet } from '@/api/client'

export function fetchHealth(): Promise<{ status: string }> {
  return apiGet<{ status: string }>('/health')
}
