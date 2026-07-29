/** SCR-020 농약 재고 타입 */

export type PesticideWarnSource = 'item' | 'default'

export interface PesticideStockSummary {
  total_count: number
  low_count: number
  default_warn_piece_below: number
  last_spray_dt: string | null
}

export interface PesticideStockItem {
  item_id: number
  item_nm: string
  spec_nm: string | null
  pest_category_nm: string | null
  qty_piece: number
  warn_piece_below: number | null
  warn_threshold: number
  warn_source: PesticideWarnSource
  is_low: boolean
  info_id: number | null
  info_pesticide_nm: string | null
  ingredient_nm: string | null
  pest_target_nm: string | null
}

export interface PesticideStockItemDetail extends PesticideStockItem {
  rmk: string | null
}

export interface PesticideStockListResponse {
  summary: PesticideStockSummary
  items: PesticideStockItem[]
}

export interface PesticideUsageRow {
  use_id: number
  use_line_id: number
  use_dt: string
  use_qty: number
  purpose_nm: string | null
  work_id: string | null
  worker_nm: string | null
  site_nm: string | null
  item_nm?: string | null
}

export interface PesticideStockDetailResponse {
  item: PesticideStockItemDetail
  recent_usage: PesticideUsageRow[]
}

export interface PesticideUsageListResponse {
  item_id: number
  total: number
  offset: number
  limit: number
  rows: PesticideUsageRow[]
}

export interface PesticideRecentUsageLine {
  item_nm: string
  use_qty: number
  unit: string
}

export interface PesticideRecentUsageDay {
  use_dt: string
  lines: PesticideRecentUsageLine[]
}

export interface PesticideRecentUsageResponse {
  last_spray_dt: string | null
  days: PesticideRecentUsageDay[]
}

export type PesticideCategoryShare = {
  key: string
  label: string
  tone: string
  qty: number
  pct: number
}

export interface PesticideYearlyStatsItem {
  item_id: number
  item_nm: string
  spec_nm: string | null
  pest_category_nm?: string | null
  total_qty: number
  current_stock: number
  daily: Record<string, number>
}

export interface PesticideYearlyStatsResponse {
  year: number
  spray_count_total: number
  monthly_spray_counts: Record<string, number>
  items: PesticideYearlyStatsItem[]
}

export interface PesticideInfoSummary {
  info_id: number
  pesticide_nm: string
  maker_nm: string | null
  ingredient_nm: string | null
  category_nm: string | null
  brand_nm: string | null
  stock_qty: number
}

export interface PesticideInfoListResponse {
  items: PesticideInfoSummary[]
}

export interface PesticideInfoDetail extends PesticideInfoSummary {
  spec_nm: string | null
  dilution_guide: string | null
  usage_note: string | null
  caution_note: string | null
  rmk: string | null
  last_use_dt: string | null
  annual_use_qty: number
  annual_use_cnt: number
  pest_target_nm: string | null
}

export interface PesticideSupplier {
  supplier_id: number
  supplier_nm: string
  biz_reg_no: string | null
  ceo_nm: string | null
  addr: string | null
}

export interface PesticideSupplierListResponse {
  items: PesticideSupplier[]
}

export interface PesticideReceiptLine {
  line_id?: number | null
  line_no?: number
  link_item_id?: number | null
  info_id?: number | null
  item_nm: string
  spec_nm?: string | null
  qty: number
  unit_price?: number | null
  supply_amt?: number | null
  tax_amt?: number | null
  line_rmk?: string | null
}

export interface PesticideReceiptSummary {
  receipt_id: number
  receipt_dt: string
  supplier_id: number | null
  supplier_nm: string | null
  recipient_nm: string | null
  rmk: string | null
  stock_applied_yn: string
  line_count: number
  total_qty: number
}

export interface PesticideReceiptListResponse {
  items: PesticideReceiptSummary[]
}

export interface PesticideReceiptDetail {
  receipt_id: number
  receipt_dt: string
  supplier_id: number | null
  supplier_nm_text: string | null
  recipient_nm: string | null
  rmk: string | null
  stock_applied_yn: string
  stock_applied_dt: string | null
  lines: PesticideReceiptLine[]
}

export interface PesticideReceiptSaveBody {
  receipt_dt: string
  supplier_id?: number | null
  supplier_nm_text?: string
  recipient_nm?: string
  rmk?: string
  lines: PesticideReceiptLine[]
}

export interface PesticideReceiptSaveResponse {
  receipt_id: number
  message: string
}

export interface PesticideReceiptApplyResponse {
  applied_count: number
  created_names: string[]
  notes: string[]
  message: string
}

export interface PesticideMessageResponse {
  message: string
}

export interface PesticideItemUpdateBody {
  item_nm: string
  spec_nm?: string
  pest_category_nm?: string
  qty_piece: number
  warn_piece_below?: number | null
  rmk?: string
  info_id?: number | null
}

export interface PesticideStockOutBody {
  qty: number
  buyer_nm?: string
  rmk?: string
}

export interface PesticideStockOutResponse {
  item_id: number
  qty: number
  qty_after: number
  message: string
}

export interface PesticideStockHistRow {
  hist_id: number
  trans_type: string
  ref_table: string | null
  ref_id: number | null
  qty_delta: number
  qty_after: number | null
  trans_dt: string
  rmk: string | null
  receipt_dt?: string | null
  supplier_nm?: string | null
}

export interface PesticideStockHistListResponse {
  item_id: number
  item_nm: string
  rows: PesticideStockHistRow[]
}
