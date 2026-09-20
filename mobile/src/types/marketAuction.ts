/** 경매조회 READ — GET /api/v1/market-auctions (R26-B f1133eb) */

export type MarketAuctionSummary = {
  auction_box_qty: string
  auction_weight_kg: string
  auction_amount: number
}

export type MarketAuctionItem = {
  trade_date: string
  auction_time: string | null
  market_cd: string
  market_name: string | null
  corporation_cd: string | null
  corporation_name: string | null
  origin_cd: string | null
  origin_name: string | null
  variety_cd: string | null
  variety_name: string | null
  unit_qty: string | null
  unit_nm: string | null
  spec_text: string | null
  auction_box_qty: string | null
  auction_weight_kg: string | null
  auction_price: number | null
  auction_amount: number
}

export type MarketAuctionListPage = {
  trade_date: string
  fetched_at: string
  cache_hit: boolean
  stale: boolean
  market_cd: string
  market_name: string | null
  total_count: number
  page: number
  page_size: number
  has_more: boolean
  summary: MarketAuctionSummary
  items: MarketAuctionItem[]
}

export type MarketAuctionQuery = {
  trade_date: string
  market_cd?: string
  corporation_cd?: string
  origin_cd?: string // 콤마 구분 다중(OR). 미지정=전체
  variety?: string
  refresh?: boolean
  page?: number
  page_size?: number
}
