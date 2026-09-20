/** 확정 경락 매칭 READ — GET /farms/{farm}/auction-matches */

export type AuctionConfirmedMatchItem = {
  match_seq: number
  shipment_id: string
  source_key: string
  trade_dt: string
  market_cd: string | null
  market_name: string | null
  corporation_name: string | null
  origin_name: string | null
  variety_name: string | null
  spec_text: string | null
  auction_box_qty: number
  auction_weight_kg: number | null
  auction_price: number | null
  auction_amount: number
  auction_time: string | null
  match_status: 'confirmed'
}

export type AuctionConfirmedMatchListPage = {
  farm_cd: string
  trade_dt: string
  total_count: number
  items: AuctionConfirmedMatchItem[]
}
