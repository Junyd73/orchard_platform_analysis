import { apiGet, apiPostJson } from '@/api/client'
import { apiUserHeaders } from '@/api/userHeaders'

export type StockItem = {
  farm_cd: string
  wh_cd: string
  item_cd: string
  item_nm: string
  variety_cd: string
  variety_nm: string
  grade_cd: string
  grade_nm: string
  size_cd: string
  size_nm: string
  weight: number
  harvest_year: number
  storage_dt: string
  in_qty: number
  out_qty: number
  real_qty: number
  reserved_qty: number
  available_qty: number
}

export type StockLog = {
  log_id: number
  farm_cd: string
  item_cd: string
  variety_cd: string
  variety_nm: string
  harvest_year: number
  grade_cd: string
  grade_nm: string
  size_cd: string
  size_nm: string
  weight: number
  io_type: string
  io_type_nm: string
  qty: number
  remark: string
  reg_id: string
  reg_dt: string
}

export async function listFruitStock(
  farmCd: string,
  params?: {
    item_cd?: string
    variety_cd?: string
    include_zero?: boolean
  },
): Promise<StockItem[]> {
  const q = new URLSearchParams()
  if (params?.item_cd)     q.set('item_cd', params.item_cd)
  if (params?.variety_cd)  q.set('variety_cd', params.variety_cd)
  if (params?.include_zero) q.set('include_zero', 'true')
  const qs = q.toString() ? `?${q}` : ''
  return apiGet<StockItem[]>(
    `/farms/${encodeURIComponent(farmCd)}/fruit-stock${qs}`,
    { headers: apiUserHeaders() },
  )
}

export async function listStockLogs(
  farmCd: string,
  params: {
    item_cd?: string
    variety_cd?: string
    grade_cd?: string
    size_cd?: string
    weight?: number
    storage_dt?: string
    harvest_year?: number
    limit?: number
  },
): Promise<StockLog[]> {
  const q = new URLSearchParams()
  if (params.item_cd)     q.set('item_cd', params.item_cd)
  if (params.variety_cd)  q.set('variety_cd', params.variety_cd)
  if (params.grade_cd)    q.set('grade_cd', params.grade_cd)
  if (params.size_cd)     q.set('size_cd', params.size_cd)
  if (params.weight != null) q.set('weight', String(params.weight))
  if (params.storage_dt)  q.set('storage_dt', params.storage_dt)
  if (params.harvest_year != null) q.set('harvest_year', String(params.harvest_year))
  if (params.limit)       q.set('limit', String(params.limit))
  return apiGet<StockLog[]>(
    `/farms/${encodeURIComponent(farmCd)}/fruit-stock/logs?${q}`,
    { headers: apiUserHeaders() },
  )
}

export type StockAdjustPayload = {
  wh_cd: string
  item_cd: string
  variety_cd: string
  grade_cd: string
  size_cd: string
  weight: number
  harvest_year: number
  storage_dt: string
  io_type: 'IN' | 'OUT'
  qty: number
  reason_cd: string
}

export async function adjustStock(
  farmCd: string,
  payload: StockAdjustPayload,
): Promise<{ ok: boolean; qty: number; io_type: string }> {
  return apiPostJson(
    `/farms/${encodeURIComponent(farmCd)}/fruit-stock/adjust`,
    payload,
    { headers: apiUserHeaders() },
  )
}
