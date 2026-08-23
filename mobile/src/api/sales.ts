import { apiGet } from '@/api/client'
import type { SalesListPage, SalesListQuery } from '@/types/sales'

function farmBase(farmCd: string): string {
  return `/farms/${encodeURIComponent(farmCd)}`
}

export function fetchSales(
  farmCd: string,
  query: SalesListQuery = {},
): Promise<SalesListPage> {
  const params = new URLSearchParams()
  if (query.from_date) params.set('from_date', query.from_date)
  if (query.to_date) params.set('to_date', query.to_date)
  if (query.sales_status) params.set('sales_status', query.sales_status)
  if (query.payment_status) params.set('payment_status', query.payment_status)
  if (query.keyword?.trim()) params.set('keyword', query.keyword.trim())
  if (query.page != null) params.set('page', String(query.page))
  if (query.page_size != null) params.set('page_size', String(query.page_size))
  const suffix = params.toString() ? `?${params.toString()}` : ''
  return apiGet<SalesListPage>(`${farmBase(farmCd)}/sales${suffix}`)
}
