/** Stage 6 판매출고 confirm API 계약 — stock_seq 없음 */

export type ShipMode = 'STOCK' | 'DIRECT'

export type ShipDeliveryAllocation = {
  qty: number
  rcv_name: string
  rcv_tel: string
  rcv_addr: string
  dlvry_msg?: string
  ship_fee: number
}

export type ShipConfirmLine = {
  qty: number
  order_detail_id?: string | null
  item_cd?: string
  variety_cd?: string
  grade_cd?: string
  size_cd?: string
  weight?: number
  harvest_year?: number
  wh_cd?: string
  unit_price?: number
  /** null/미전송 = legacy. 배열 = 2C STOCK 택배 */
  delivery_allocations?: ShipDeliveryAllocation[] | null
}

export type ShipConfirmRequest = {
  ship_mode: ShipMode
  sales_dt?: string
  order_no?: string | null
  custm_id?: string | null
  rmk?: string
  dlvry_tp?: string
  ship_fee?: number
  rcv_name?: string
  rcv_tel?: string
  rcv_addr?: string
  dlvry_msg?: string
  lines: ShipConfirmLine[]
}

export type ShipConfirmDetail = {
  sale_detail_no: string
  order_detail_id: string | null
  stock_seq: number
  qty: number
}

export type RemainingOrderLine = {
  order_detail_id: string
  order_qty: number
  confirmed_shipped_qty: number
  remaining_order_qty: number
}

export type ShipConfirmResponse = {
  ok: boolean
  sales_no: string
  sales_status: string
  ship_mode: ShipMode | string
  order_no: string | null
  details: ShipConfirmDetail[]
  order_status: string | null
  remaining_order_qty: number | null
  remaining_order: RemainingOrderLine[]
}