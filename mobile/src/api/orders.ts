import { apiGet, apiPostJson, apiPutJson } from '@/api/client'
import { apiUserHeaders } from '@/api/userHeaders'
import type {
  CustomerCreatePayload,
  CustomerListItem,
  OrderCreatePayload,
  OrderDetail,
  OrderListPage,
  OrderListQuery,
} from '@/types/order'

function farmBase(farmCd: string): string {
  return `/farms/${encodeURIComponent(farmCd)}`
}

export function fetchOrders(
  farmCd: string,
  query: OrderListQuery = {},
): Promise<OrderListPage> {
  const params = new URLSearchParams()
  if (query.from_date) params.set('from_date', query.from_date)
  if (query.to_date) params.set('to_date', query.to_date)
  if (query.status_cd) params.set('status_cd', query.status_cd)
  if (query.keyword?.trim()) params.set('keyword', query.keyword.trim())
  if (query.page != null) params.set('page', String(query.page))
  if (query.page_size != null) params.set('page_size', String(query.page_size))
  const suffix = params.toString() ? `?${params.toString()}` : ''
  return apiGet<OrderListPage>(`${farmBase(farmCd)}/orders${suffix}`)
}

export function fetchOrder(farmCd: string, orderNo: string): Promise<OrderDetail> {
  return apiGet<OrderDetail>(
    `${farmBase(farmCd)}/orders/${encodeURIComponent(orderNo)}`,
  )
}

export function createOrder(
  farmCd: string,
  payload: OrderCreatePayload,
): Promise<OrderDetail> {
  return apiPostJson<OrderDetail>(`${farmBase(farmCd)}/orders`, payload, {
    headers: apiUserHeaders(),
  })
}

export function updateOrder(
  farmCd: string,
  orderNo: string,
  payload: OrderCreatePayload,
): Promise<OrderDetail> {
  return apiPutJson<OrderDetail>(
    `${farmBase(farmCd)}/orders/${encodeURIComponent(orderNo)}`,
    payload,
    { headers: apiUserHeaders() },
  )
}

export function cancelOrder(
  farmCd: string,
  orderNo: string,
): Promise<OrderDetail> {
  return apiPostJson<OrderDetail>(
    `${farmBase(farmCd)}/orders/${encodeURIComponent(orderNo)}/cancel`,
    {},
    { headers: apiUserHeaders() },
  )
}

export function confirmOrder(
  farmCd: string,
  orderNo: string,
): Promise<OrderDetail> {
  return apiPostJson<OrderDetail>(
    `${farmBase(farmCd)}/orders/${encodeURIComponent(orderNo)}/confirm`,
    {},
    { headers: apiUserHeaders() },
  )
}

export function createCustomer(
  farmCd: string,
  payload: CustomerCreatePayload,
): Promise<CustomerListItem> {
  return apiPostJson<CustomerListItem>(`${farmBase(farmCd)}/customers`, payload, {
    headers: apiUserHeaders(),
  })
}

export function fetchCustomers(
  farmCd: string,
  q?: string,
): Promise<CustomerListItem[]> {
  const params = new URLSearchParams()
  if (q?.trim()) params.set('q', q.trim())
  const suffix = params.toString() ? `?${params.toString()}` : ''
  return apiGet<CustomerListItem[]>(`${farmBase(farmCd)}/customers${suffix}`)
}
