/** 경매 출하 DEC-036-B/C2 */

export type AuctionShipmentLinePayload = {
  wh_cd: string
  item_cd: string
  variety_cd: string
  grade_cd: string
  size_cd: string
  weight: number
  harvest_year: number
  qty: number
}

export type AuctionShipmentCreatePayload = {
  ship_dt: string
  market_cd: string
  market_name: string
  corporation_name: string
  custm_id: string | null
  lines: AuctionShipmentLinePayload[]
}

export type AuctionShipmentCreated = {
  shipment_id: string
  ship_dt: string
  market_cd: string
  market_name: string
  corporation_name: string
  custm_id: string | null
  status: string
  total_shipped_qty: number
  spec_count: number
  total_line_count: number
}

export type AuctionShipmentListItem = {
  shipment_id: string
  ship_dt: string
  market_cd: string
  market_name: string
  corporation_name: string
  custm_id: string | null
  status: string
  total_shipped_qty: number
  spec_count: number
  total_line_count: number
  reg_dt: string
  sales_no?: string | null
  match_trade_dt?: string | null
  gross_sales_amount?: number | null
  cancel_allowed: boolean
  reopen_allowed: boolean
}

export type AuctionShipmentListPage = {
  items: AuctionShipmentListItem[]
  total: number
}

export type AuctionShipmentSpec = {
  variety_cd: string
  variety_name: string
  grade_cd: string
  grade_name: string
  size_cd: string
  size_name: string
  weight: number
  farm_shipped_qty: number
  matched_qty?: number | null
  diff_qty?: number | null
  discrepancy_reason?: string | null
}

export type AuctionShipmentDetail = {
  shipment_id: string
  ship_dt: string
  market_cd: string
  market_name: string
  corporation_name: string
  custm_id: string | null
  status: string
  sales_no: string | null
  match_trade_dt: string | null
  total_shipped_qty: number
  gross_sales_amount: number | null
  specs: AuctionShipmentSpec[]
  cancel_allowed: boolean
  reopen_allowed: boolean
}

export type AuctionCandidate = {
  source_type: string
  trade_dt: string
  market_cd: string
  market_name: string
  corporation_name: string
  origin_name: string | null
  variety_name: string | null
  grade_cd: string | null
  grade_name: string | null
  size_name: string | null
  spec_name: string | null
  spec_kg: number | null
  qty: number
  unit_price: number
  amount: number
  auction_time: string | null
  requires_grade_input: boolean
  source_key: string
}

export type AuctionCandidateResponse = {
  shipment_id: string
  trade_dt: string
  source_used: string
  items: AuctionCandidate[]
}

export type AuctionDiscrepancyReason = 'QTY_ERROR' | 'RETURN' | 'DAMAGE' | 'OTHER'

export type AuctionFinalizeSelected = {
  source_key: string
  user_grade_cd?: string | null
}

export type AuctionFinalizeDiscrepancy = {
  variety_cd: string
  grade_cd: string
  size_cd: string
  weight: number
  reason_cd: AuctionDiscrepancyReason
  remark?: string | null
  return_confirmed?: boolean
}

export type AuctionFinalizeRequest = {
  trade_dt: string
  selected_candidates: AuctionFinalizeSelected[]
  discrepancies: AuctionFinalizeDiscrepancy[]
}

export type AuctionFinalizeResponse = {
  shipment_id: string
  status: string
  sales_no: string
  match_trade_dt: string
  total_sales_qty: number
  gross_sales_amount: number
  matched_count: number
  discrepancy_count: number
}

export type AuctionCancelResponse = {
  shipment_id: string
  status: string
  restored_qty: number
}

export type AuctionReopenRequest = {
  remark?: string | null
}

export type AuctionReopenResponse = {
  shipment_id: string
  status: string
  sales_no: string | null
  match_trade_dt: string | null
  cancelled_sales_no: string
}
