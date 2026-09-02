/** 경매 출하 lookup — DEC-036-C1 */

export type AuctionMarketItem = {
  market_cd: string
  market_name: string
}

export type AuctionMarketListPage = {
  items: AuctionMarketItem[]
}

export type AuctionCorporationItem = {
  corporation_name: string
  custm_id: string | null
}

export type AuctionCorporationListPage = {
  items: AuctionCorporationItem[]
}
