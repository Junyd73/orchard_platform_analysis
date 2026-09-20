/** 경매 결과 표 행 모델 — 전체/내 경매 공통. */

import {
  AUCTION_MATCH_STATUS_CANDIDATE,
  AUCTION_MATCH_STATUS_CONFIRMED,
  formatAuctionSpecText,
  originDisplayLabel,
  type AuctionMatchStatus,
} from '@/views/orders/auctionLookupFormat'
import type { AuctionConfirmedMatchItem } from '@/types/auctionMatch'
import type { AuctionCandidate } from '@/types/auctionShipment'
import type { MarketAuctionItem } from '@/types/marketAuction'

export type AuctionTableRow = {
  row_key: string
  auction_time: string | null
  corporation_name: string | null
  variety_name: string | null
  origin_name: string | null
  origin_cd: string | null
  spec_text: string
  auction_box_qty: string | number | null
  auction_weight_kg: string | number | null
  auction_price: number | null
  auction_amount: number
  market_cd: string | null
  match_status: AuctionMatchStatus | null
  shipment_id: string | null
  source_key: string | null
  selectable: boolean
}

export function marketItemToTableRow(row: MarketAuctionItem, index: number): AuctionTableRow {
  return {
    row_key: `all|${row.auction_time || ''}|${row.corporation_cd || ''}|${row.origin_cd || ''}|${row.variety_cd || ''}|${row.auction_box_qty || ''}|${row.auction_price ?? ''}|${index}`,
    auction_time: row.auction_time,
    corporation_name: row.corporation_name,
    variety_name: row.variety_name,
    origin_name: row.origin_name,
    origin_cd: row.origin_cd,
    spec_text: formatAuctionSpecText(row),
    auction_box_qty: row.auction_box_qty,
    auction_weight_kg: row.auction_weight_kg,
    auction_price: row.auction_price,
    auction_amount: row.auction_amount,
    market_cd: row.market_cd,
    match_status: null,
    shipment_id: null,
    source_key: null,
    selectable: false,
  }
}

export function confirmedMatchToTableRow(row: AuctionConfirmedMatchItem): AuctionTableRow {
  return {
    row_key: `confirmed|${row.source_key}|${row.match_seq}`,
    auction_time: row.auction_time,
    corporation_name: row.corporation_name,
    variety_name: row.variety_name,
    origin_name: row.origin_name,
    origin_cd: null,
    spec_text: String(row.spec_text || '').trim(),
    auction_box_qty: row.auction_box_qty,
    auction_weight_kg: row.auction_weight_kg,
    auction_price: row.auction_price,
    auction_amount: row.auction_amount,
    market_cd: row.market_cd,
    match_status: AUCTION_MATCH_STATUS_CONFIRMED,
    shipment_id: row.shipment_id,
    source_key: row.source_key,
    selectable: false,
  }
}

export function candidateToTableRow(
  row: AuctionCandidate,
  shipmentId: string,
): AuctionTableRow {
  return {
    row_key: `candidate|${row.source_key}|${shipmentId}`,
    auction_time: row.auction_time,
    corporation_name: row.corporation_name,
    variety_name: row.variety_name,
    origin_name: row.origin_name,
    origin_cd: null,
    spec_text: formatAuctionSpecText({
      spec_text: row.spec_name,
      unit_qty: row.spec_kg,
      unit_nm: row.spec_kg != null ? 'kg' : '',
    }),
    auction_box_qty: row.qty,
    auction_weight_kg:
      row.spec_kg != null && Number.isFinite(row.spec_kg)
        ? row.qty * row.spec_kg
        : null,
    auction_price: row.unit_price,
    auction_amount: row.amount,
    market_cd: row.market_cd,
    match_status: AUCTION_MATCH_STATUS_CANDIDATE,
    shipment_id: shipmentId,
    source_key: row.source_key,
    selectable: true,
  }
}

export function passesAuctionTableFilters(
  row: AuctionTableRow,
  filters: {
    marketCd?: string
    corporation?: string
    origins?: string[]
    variety?: string
  },
): boolean {
  const market = String(filters.marketCd || '').trim()
  if (market && String(row.market_cd || '').trim() !== market) return false

  const corp = String(filters.corporation || '').trim()
  if (corp) {
    const name = String(row.corporation_name || '').trim()
    if (name !== corp) return false
  }

  const variety = String(filters.variety || '').trim()
  if (variety) {
    const name = String(row.variety_name || '').trim()
    if (name !== variety && !name.includes(variety) && variety !== name) return false
  }

  const origins = filters.origins || []
  if (origins.length) {
    const originCd = String(row.origin_cd || '').trim()
    const originName = String(row.origin_name || '').trim()
    const short = originDisplayLabel(originName)
    const hit = origins.some((token) => {
      const t = String(token || '').trim()
      if (!t) return false
      return t === originCd || t === originName || t === short || originName.includes(t)
    })
    if (!hit) return false
  }
  return true
}

/** source_key 중복 제거. 확정이 후보보다 우선. shipment_id는 첫 행에 보존. */
export function dedupeAuctionTableRows(rows: AuctionTableRow[]): AuctionTableRow[] {
  const byKey = new Map<string, AuctionTableRow>()
  for (const row of rows) {
    const key = String(row.source_key || '').trim()
    if (!key) {
      byKey.set(row.row_key, row)
      continue
    }
    const prev = byKey.get(key)
    if (!prev) {
      byKey.set(key, row)
      continue
    }
    if (
      prev.match_status !== AUCTION_MATCH_STATUS_CONFIRMED &&
      row.match_status === AUCTION_MATCH_STATUS_CONFIRMED
    ) {
      byKey.set(key, row)
    }
  }
  return Array.from(byKey.values())
}

export function sortAuctionTableRows(rows: AuctionTableRow[]): AuctionTableRow[] {
  return [...rows].sort((a, b) => {
    const ta = String(a.auction_time || '')
    const tb = String(b.auction_time || '')
    if (ta && tb) return tb.localeCompare(ta)
    if (ta && !tb) return -1
    if (!ta && tb) return 1
    return a.row_key.localeCompare(b.row_key)
  })
}
