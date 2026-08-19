/** 주문 Stage 2 API 계약 */

export type OrderListItem = {
  order_no: string
  order_dt: string
  custm_id: string
  customer: string
  status_cd: string
  status_nm: string
  total_qty: number
  total_amt: number
  pre_pay_amt: number
}

export type OrderListQuery = {
  from_date?: string
  to_date?: string
  status_cd?: string
  keyword?: string
  page?: number
  page_size?: number
}

export type OrderListPage = {
  items: OrderListItem[]
  total: number
  page: number
  page_size: number
}

export type OrderDelivery = {
  order_dlvry_id: string
  order_detail_id: string
  delivery_tp_cd: string
  qty: number
  planned_dt: string
  snd_name: string
  snd_tel: string
  snd_addr: string
  rcv_name: string
  rcv_tel: string
  rcv_addr: string
  dlvry_msg?: string
  delivery_tp_nm?: string
}

export type OrderLine = {
  order_detail_id: string
  item_cd: string
  variety_cd: string
  grade_cd: string
  size_cd: string
  weight: number
  qty: number
  unit_price: number
  item_amt: number
  harvest_year: number
  wh_cd: string
  dlvry_tp: string
  variety_nm?: string
  grade_nm?: string
  size_nm?: string
  dlvry_tp_nm?: string
  allocated_qty?: number
  unallocated_qty?: number
  reserved_unshipped_qty?: number
  deliveries: OrderDelivery[]
}

export type OrderDetail = OrderListItem & {
  mobile: string
  stock_status: string
  season_type_cd: string
  tot_order_amt: number
  tot_ship_fee: number
  tot_pay_amt: number
  rmk: string
  sales_no: string
  lines: OrderLine[]
}

export type OrderDeliveryPayload = {
  delivery_tp_cd: string
  qty: number
  planned_dt?: string | null
  snd_name?: string
  snd_tel?: string
  snd_addr?: string
  rcv_name?: string
  rcv_tel?: string
  rcv_addr?: string
  dlvry_msg?: string
}

export type OrderLinePayload = {
  variety_cd: string
  weight: number
  grade_cd: string
  size_cd: string
  qty: number
  unit_price: number
  harvest_year?: number | null
  warehouse_cd?: string | null
  item_cd?: string | null
  dlvry_tp?: string | null
  deliveries: OrderDeliveryPayload[]
}

export type OrderCreatePayload = {
  custm_id: string
  order_dt?: string | null
  season_type_cd?: string
  pre_pay_amt?: number
  tot_ship_fee?: number
  rmk?: string
  lines: OrderLinePayload[]
}

export type CustomerListItem = {
  custm_id: string
  custm_nm: string
  mobile: string
}

export type CustomerCreatePayload = {
  custm_nm: string
  mobile: string
  addr1?: string
  addr2?: string
  rmk?: string
}
