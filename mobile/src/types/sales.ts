export type PaymentStatus = 'UNPAID' | 'PARTIAL' | 'PAID' | null

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
