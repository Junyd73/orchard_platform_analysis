/** 경매조회 탭 — 라벨·표시 포맷 (R26-C). Decimal은 문자열로 보존한다. */

export const TAB_AUCTION = 'auction'

export const AUCTION_DEFAULT_MARKET_CD = '110001'
export const AUCTION_PAGE_SIZE = 50
export const AUCTION_FILTER_ALL = ''

export const LABEL_AUCTION_TAB = '경매'
export const LABEL_AUCTION_TRADE_DATE = '조회일자'
export const LABEL_AUCTION_DATE_PREV = '이전 날짜'
export const LABEL_AUCTION_DATE_NEXT = '다음 날짜'
export const LABEL_AUCTION_MARKET = '시장'
export const LABEL_AUCTION_CORP = '청과법인'
export const LABEL_AUCTION_ORIGIN = '산지'
export const LABEL_AUCTION_VARIETY = '품종'
export const LABEL_AUCTION_LOOKUP = '조회하기'
export const LABEL_AUCTION_RESET = '초기화'
export const LABEL_AUCTION_MORE = '더보기'
export const LABEL_AUCTION_UNIT_BOX = '박스'
export const LABEL_AUCTION_UNIT_KG = 'kg'
export const LABEL_AUCTION_UNIT_WON = '원'
export const LABEL_AUCTION_PRICE = '경락가'
export const LABEL_AUCTION_FILTER_ALL = '전체'
export const LABEL_AUCTION_FILTER_DETAIL = '상세조건'
export const LABEL_AUCTION_RESULT_PREFIX = '경매결과'
export const LABEL_AUCTION_RESULT_SUFFIX = '건'
export const LABEL_AUCTION_SORT_HINT = '경매시간 최신순'
export const LABEL_AUCTION_MODE_ALL = '전체 경매'
export const LABEL_AUCTION_MODE_MINE = '내 경매'
export const LABEL_AUCTION_STATUS_CANDIDATE = '후보'
export const LABEL_AUCTION_STATUS_CONFIRMED = '확정'
export const LABEL_AUCTION_COL_TIME = '시간'
export const LABEL_AUCTION_COL_CORP = '청과법인'
export const LABEL_AUCTION_COL_VARIETY = '품종'
export const LABEL_AUCTION_COL_ORIGIN = '산지'
export const LABEL_AUCTION_COL_SPEC = '규격'
export const LABEL_AUCTION_COL_QTY = '건수'
export const LABEL_AUCTION_COL_WEIGHT = '중량'
export const LABEL_AUCTION_COL_PRICE = '경락가'
export const LABEL_AUCTION_COL_AMOUNT = '합계액'
export const LABEL_AUCTION_COL_QTY_UNIT = '(박스)'
export const LABEL_AUCTION_COL_WEIGHT_UNIT = '(kg)'
export const LABEL_AUCTION_COL_PRICE_UNIT = '(원)'
export const LABEL_AUCTION_COL_AMOUNT_UNIT = '(원)'
export const MSG_AUCTION_EMPTY = '선택한 날짜의 경매 데이터가 없습니다'
export const MSG_AUCTION_MINE_EMPTY = '선택한 날짜에 확인할 내 경매 결과가 없습니다'
export const MSG_AUCTION_MINE_NO_CANDIDATE =
  '출하내역은 있으나 조건에 맞는 경매결과를 찾지 못했습니다'
export const MSG_AUCTION_LOAD_FAIL = '경매 데이터를 불러오지 못했습니다'
export const MSG_AUCTION_STALE = '최근 조회 데이터를 표시합니다'
export const LABEL_AUCTION_RETRY = '재시도'

export const AUCTION_MODE_ALL = 'all'
export const AUCTION_MODE_MINE = 'mine'
export type AuctionResultMode = typeof AUCTION_MODE_ALL | typeof AUCTION_MODE_MINE

export const AUCTION_MATCH_STATUS_CANDIDATE = 'candidate'
export const AUCTION_MATCH_STATUS_CONFIRMED = 'confirmed'
export type AuctionMatchStatus =
  | typeof AUCTION_MATCH_STATUS_CANDIDATE
  | typeof AUCTION_MATCH_STATUS_CONFIRMED

/** Decimal 문자열 표시 — Number()로 원본을 훼손하지 않는다. */
export function formatAuctionDecimal(raw: string | null | undefined): string {
  const text = String(raw ?? '').trim()
  if (!text) return '0'
  const neg = text.startsWith('-')
  const body = neg ? text.slice(1) : text
  if (!/^\d+(\.\d+)?$/.test(body)) return text
  let intPart = body
  let frac = ''
  const dot = body.indexOf('.')
  if (dot >= 0) {
    intPart = body.slice(0, dot) || '0'
    frac = body.slice(dot + 1).replace(/0+$/, '')
  }
  const withComma = intPart.replace(/\B(?=(\d{3})+(?!\d))/g, ',')
  const signed = `${neg ? '-' : ''}${withComma}`
  return frac ? `${signed}.${frac}` : signed
}

export function formatAuctionWon(amount: number | null | undefined): string {
  const n = Number(amount)
  const v = Number.isFinite(n) ? Math.round(n) : 0
  return v.toLocaleString('ko-KR')
}

export function formatAuctionCount(n: number): string {
  const v = Number.isFinite(n) ? Math.trunc(n) : 0
  return v.toLocaleString('ko-KR')
}

export function formatAuctionResultTitle(totalCount: number): string {
  return `${LABEL_AUCTION_RESULT_PREFIX} ${formatAuctionCount(totalCount)}${LABEL_AUCTION_RESULT_SUFFIX}`
}

/** API 원본 산지 보존. 표시만 시/군 축약. */
export function originDisplayLabel(full: string | null | undefined): string {
  const text = String(full || '').trim()
  if (!text) return ''
  const parts = text.split(/\s+/).filter(Boolean)
  return parts[parts.length - 1] || text
}

export function joinAuctionOriginCds(selected: string[]): string | undefined {
  const values = selected.map((v) => String(v || '').trim()).filter(Boolean)
  return values.length ? values.join(',') : undefined
}

export function auctionTimeLabel(raw: string | null | undefined): string {
  const text = String(raw || '').trim()
  if (!text) return ''
  const m = text.match(/(\d{1,2}):(\d{2})(?::\d{2})?/)
  if (m) return `${m[1].padStart(2, '0')}:${m[2]}`
  return text
}

/** 규격: 원본 spec_text 우선, 없으면 unit_qty+unit_nm. 임의 환산 금지. */
export function formatAuctionSpecText(row: {
  spec_text?: string | null
  unit_qty?: string | number | null
  unit_nm?: string | null
}): string {
  const spec = String(row.spec_text || '').trim()
  if (spec) return spec
  const qty = String(row.unit_qty ?? '').trim()
  const nm = String(row.unit_nm || '').trim()
  if (!qty && !nm) return ''
  return `${qty}${nm}`
}

export function formatAuctionQtyCell(raw: string | number | null | undefined): string {
  if (raw == null || raw === '') return ''
  return formatAuctionDecimal(String(raw))
}

export function formatAuctionWeightCell(raw: string | number | null | undefined): string {
  if (raw == null || raw === '') return ''
  return formatAuctionDecimal(String(raw))
}

export function auctionRowKey(row: {
  auction_time?: string | null
  corporation_cd?: string | null
  corporation_name?: string | null
  origin_cd?: string | null
  origin_name?: string | null
  variety_cd?: string | null
  variety_name?: string | null
  unit_qty?: string | null
  auction_box_qty?: string | null
  auction_price?: number | null
  auction_amount?: number
}): string {
  return [
    row.auction_time ?? '',
    row.corporation_cd ?? '',
    row.corporation_name ?? '',
    row.origin_cd ?? '',
    row.origin_name ?? '',
    row.variety_cd ?? '',
    row.variety_name ?? '',
    row.unit_qty ?? '',
    row.auction_box_qty ?? '',
    row.auction_price ?? '',
    row.auction_amount ?? '',
  ].join('|')
}

export function clampTradeDateToToday(iso: string, today: string): string {
  const v = String(iso || '').trim()
  if (!/^\d{4}-\d{2}-\d{2}$/.test(v)) return today
  return v > today ? today : v
}

/** 조회일 ±N일. 미래일은 today로 클램프. */
export function shiftTradeDate(iso: string, deltaDays: number, today: string): string {
  const base = clampTradeDateToToday(iso, today)
  const m = base.match(/^(\d{4})-(\d{2})-(\d{2})$/)
  if (!m) return today
  const dt = new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3])))
  dt.setUTCDate(dt.getUTCDate() + deltaDays)
  const y = dt.getUTCFullYear()
  const mo = String(dt.getUTCMonth() + 1).padStart(2, '0')
  const d = String(dt.getUTCDate()).padStart(2, '0')
  return clampTradeDateToToday(`${y}-${mo}-${d}`, today)
}
