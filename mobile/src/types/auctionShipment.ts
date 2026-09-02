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
}

export type AuctionShipmentListPage = {
  items: AuctionShipmentListItem[]
  total: number
}
