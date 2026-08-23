export type PaymentStatus = 'UNPAID' | 'PARTIAL' | 'PAID' | null

export type PaymentSource = 'GENERAL' | 'ORDER_PREPAY'

export interface SalesListItem {
  sales_no: string
  sales_dt: string
  custm_id: string
  customer: string
  order_no: string | null
  sales_status: string
  sales_source: string
  tot_sales_amt: number
  paid_amt: number
  unpaid_amt: number
  payment_status: PaymentStatus
  rep_item_cd: string
  rep_variety_cd: string
  rep_variety_nm: string
  rep_weight: number
  rep_grade_cd: string
  rep_grade_nm: string
  rep_size_cd: string
  rep_size_nm: string
  rep_crop_nm: string
}

export interface SalesListQuery {
  from_date?: string
  to_date?: string
  sales_status?: string
  payment_status?: string
  keyword?: string
  page?: number
  page_size?: number
}

export interface SalesListPage {
  items: SalesListItem[]
  total: number
  page: number
  page_size: number
}

export interface SalesDetailLine {
  sale_detail_no: string
  order_detail_id: string | null
  item_cd: string
  variety_cd: string
  variety_nm: string
  grade_cd: string
  grade_nm: string
  size_cd: string
  size_nm: string
  crop_nm: string
  qty: number
  unit_price: number
  item_amt: number
  wh_cd?: string | null
  dlvry_tp?: string | null
  stock_seq?: number | null
}

export interface SalesDetail {
  sales_no: string
  sales_dt: string
  custm_id: string
  customer: string
  order_no: string | null
  sales_status: string
  sales_source: string
  tot_sales_amt: number
  paid_amt: number
  unpaid_amt: number
  payment_status: PaymentStatus
  lines: SalesDetailLine[]
}

export interface SalesPaymentItem {
  paid_detail_no: string
  pay_dt: string
  pay_method_cd: string
  pay_method_nm: string
  pay_amt: number
  payment_source: PaymentSource
  source_order_no: string | null
}

export interface SalesPaymentHistory {
  sales_no: string
  sales_status: string
  tot_sales_amt: number
  paid_amt: number
  unpaid_amt: number
  payment_status: PaymentStatus
  payments: SalesPaymentItem[]
}

export interface SalesPaymentCreatePayload {
  pay_dt: string
  pay_amt: number
  pay_method_cd: string
}
