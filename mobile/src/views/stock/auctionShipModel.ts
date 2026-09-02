import type { StockItem } from '@/api/stock'
import { stockSaleSpecKey, type ShipDraftLine } from '@/views/sales/shipConfirmModel'
import { buildStockListEntries } from '@/views/stock/stockSaleList'
import type {
  AuctionShipmentCreatePayload,
  AuctionShipmentLinePayload,
} from '@/types/auctionShipment'

export const AUCTION_STATUS_IN_TRANSIT = 'IN_TRANSIT'

/** core/stock_constants.py FR010100 — 경매 출하 대상 상품 */
export const ITEM_CD_PRODUCT = 'FR010100'

export const MSG_AUCTION_SHIP_OK = '경매 출하 등록이 완료되었습니다.'
export const MSG_AUCTION_SHIP_QTY_UNAVAILABLE =
  '재고가 변경되어 출하 가능한 수량이 부족합니다. 최신 재고를 확인해 주세요.'
export const CODE_AUCTION_SHIP_QTY_UNAVAILABLE = 'AUCTION_SHIP_QTY_UNAVAILABLE'

export const MSG_AUCTION_STOCK_REFRESH_FAIL =
  '재고 정보를 다시 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.'
export const MSG_AUCTION_SPEC_UNAVAILABLE =
  '재고가 변경되어 출하할 수 없는 규격이 포함되어 있습니다. 재고를 다시 확인해 주세요.'

const QTY_EPS = 1e-9

export type AuctionShipRefreshIssue =
  | { kind: 'missing_spec'; key: string }
  | { kind: 'zero_available'; key: string; latestAvailable: number }
  | { kind: 'qty_exceeds'; key: string; latestAvailable: number; qty: number }

export type AuctionShipSubmitAssessment = {
  blocked: boolean
  message: string | null
  issues: AuctionShipRefreshIssue[]
}

export function formatQtyExceedsAvailableMessage(latestAvailable: number): string {
  const n = Math.max(0, Math.floor(Number(latestAvailable) || 0))
  return `현재 출하 가능 수량이 ${n}박스로 변경되었습니다. 출하수량을 다시 확인해 주세요.`
}

/** fruit-stock 응답 → 판매규격(storage_dt 제외)별 최신 available_qty */
export function buildProductSpecAvailableMap(stockRows: StockItem[]): Map<string, number> {
  const productRows = stockRows.filter((r) => r.item_cd === ITEM_CD_PRODUCT)
  const entries = buildStockListEntries(productRows, { raw: false })
  return new Map(entries.map((e) => [e.listKey, Number(e.row.available_qty) || 0]))
}

function assessLinesAgainstAvailable(
  lines: ShipDraftLine[],
  availMap: Map<string, number>,
): AuctionShipSubmitAssessment {
  const issues: AuctionShipRefreshIssue[] = []

  for (const ln of lines) {
    const key = stockSaleSpecKey(ln)
    if (!availMap.has(key)) {
      issues.push({ kind: 'missing_spec', key })
      continue
    }
    const latest = availMap.get(key)!
    if (latest <= QTY_EPS) {
      issues.push({ kind: 'zero_available', key, latestAvailable: latest })
    } else if (Number(ln.qty) > latest + QTY_EPS) {
      issues.push({
        kind: 'qty_exceeds',
        key,
        latestAvailable: latest,
        qty: Number(ln.qty),
      })
    }
  }

  let message: string | null = null
  if (issues.some((i) => i.kind === 'missing_spec' || i.kind === 'zero_available')) {
    message = MSG_AUCTION_SPEC_UNAVAILABLE
  } else {
    const exceeds = issues.find((i) => i.kind === 'qty_exceeds')
    if (exceeds && exceeds.kind === 'qty_exceeds') {
      message = formatQtyExceedsAvailableMessage(exceeds.latestAvailable)
    }
  }

  return { blocked: issues.length > 0, message, issues }
}

/** cart line의 available_qty만 최신 fruit-stock 기준으로 갱신(qty 변경 없음) */
export function refreshAuctionShipLines(
  cartLines: ShipDraftLine[],
  stockRows: StockItem[],
): { lines: ShipDraftLine[]; assessment: AuctionShipSubmitAssessment } {
  const availMap = buildProductSpecAvailableMap(stockRows)
  const lines = cartLines.map((ln) => {
    const key = stockSaleSpecKey(ln)
    const latest = availMap.get(key)
    return {
      ...ln,
      available_qty: latest != null ? latest : 0,
    }
  })
  return { lines, assessment: assessLinesAgainstAvailable(lines, availMap) }
}

/** 확인창 submit 가능 여부 — 최신 available_qty 기준 */
export function assessAuctionShipSubmit(lines: ShipDraftLine[]): AuctionShipSubmitAssessment {
  const availMap = new Map<string, number>()
  for (const ln of lines) {
    availMap.set(stockSaleSpecKey(ln), Number(ln.available_qty) || 0)
  }
  return assessLinesAgainstAvailable(lines, availMap)
}

export function isAuctionQtyUnavailableError(err: unknown): boolean {
  if (!err || typeof err !== 'object') return false
  const rec = err as { errorCode?: unknown; error_code?: unknown; name?: unknown }
  if (rec.errorCode === CODE_AUCTION_SHIP_QTY_UNAVAILABLE) return true
  if (rec.error_code === CODE_AUCTION_SHIP_QTY_UNAVAILABLE) return true
  return false
}

/** DB status → 사용자 표시 */
export function auctionShipmentStatusLabel(status: string): string {
  if (status === AUCTION_STATUS_IN_TRANSIT) return '출하중'
  return '처리중'
}

export function shipDraftLinesToAuctionLines(
  lines: ShipDraftLine[],
): AuctionShipmentLinePayload[] {
  return lines.map((ln) => ({
    wh_cd: ln.wh_cd,
    item_cd: ln.item_cd,
    variety_cd: ln.variety_cd,
    grade_cd: ln.grade_cd,
    size_cd: ln.size_cd,
    weight: Number(ln.weight),
    harvest_year: Number(ln.harvest_year),
    qty: Number(ln.qty),
  }))
}

export function buildAuctionShipmentPayload(params: {
  shipDt: string
  marketCd: string
  marketName: string
  corporationName: string
  custmId: string | null
  lines: ShipDraftLine[]
}): AuctionShipmentCreatePayload {
  return {
    ship_dt: params.shipDt,
    market_cd: params.marketCd,
    market_name: params.marketName,
    corporation_name: params.corporationName,
    custm_id: params.custmId,
    lines: shipDraftLinesToAuctionLines(params.lines),
  }
}
