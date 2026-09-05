import { readApiClientErrorCode } from '@/api/client'
import type {
  AuctionCandidate,
  AuctionDiscrepancyReason,
  AuctionFinalizeRequest,
  AuctionShipmentSpec,
} from '@/types/auctionShipment'

export const SOURCE_SETTLEMENT = 'SETTLEMENT'
export const SOURCE_REALTIME = 'REALTIME'

export const MSG_AUCTION_MATCH_EMPTY =
  '선택한 날짜에 조건에 맞는 경락자료가 없습니다.'
export const MSG_AUCTION_MATCH_EMPTY_HINT = '경락일자를 확인해 주세요. 필요하면 다른 날짜로 조회해 주세요.'
export const MSG_AUCTION_MATCH_GENERIC = '경락매칭 처리 중 오류가 발생했습니다.'
export const MSG_AUCTION_MATCH_STALE = '경락정보가 변경되었습니다. 경락가를 다시 불러와 주세요.'
export const MSG_AUCTION_MATCH_SETTLEMENT_SOURCE =
  '정산자료를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.'
export const MSG_AUCTION_MATCH_REALTIME_SOURCE =
  '실시간 경락자료를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.'
export const MSG_AUCTION_MATCH_DUPLICATE =
  '이미 다른 출하건에 연결된 경락자료입니다. 경락가를 다시 확인해 주세요.'
export const MSG_AUCTION_MATCH_STATUS = '이미 처리된 경매출하입니다. 목록을 새로고침합니다.'
export const MSG_AUCTION_CANCEL_CONFIRM =
  '경매출하를 취소하면 출하수량이 재고로 복구됩니다. 취소하시겠습니까?'
export const MSG_AUCTION_MATCH_OK = '판매완료되었습니다.'
export const MSG_AUCTION_CANCEL_OK = '경매출하가 취소되었습니다.'
export const MSG_AUCTION_REOPEN_CONFIRM =
  '경락매칭을 정정하면 현재 판매내역은 취소되고 다시 경락가를 선택해야 합니다.\n\n경매출하와 재고수량은 변경되지 않습니다.\n\n진행하시겠습니까?'
export const MSG_AUCTION_REOPEN_OK = '다시 경락가를 선택해 주세요.'
export const MSG_AUCTION_REOPEN_RETURN =
  '반품처리가 완료된 출하건은 경락매칭을 정정할 수 없습니다.'
export const MSG_AUCTION_REOPEN_PAYMENT =
  '수금내역이 있는 판매는 경락매칭을 정정할 수 없습니다.'
export const MSG_AUCTION_REOPEN_STATUS =
  '이미 상태가 변경된 출하건입니다. 목록을 새로고침합니다.'
export const MSG_AUCTION_REOPEN_BLOCKED =
  '현재 상태에서는 경락매칭을 정정할 수 없습니다.'
export const MSG_AUCTION_REOPEN_NOT_FOUND =
  '해당 경매출하 정보를 찾을 수 없습니다.'
export const MSG_AUCTION_REOPEN_GENERIC = '경락매칭 정정 중 오류가 발생했습니다.'

export const CODE_AUCTION_CANDIDATE_STALE = 'AUCTION_CANDIDATE_STALE'
export const CODE_SETTLEMENT_SOURCE_ERROR = 'SETTLEMENT_SOURCE_ERROR'
export const CODE_REALTIME_SOURCE_ERROR = 'REALTIME_SOURCE_ERROR'
export const CODE_AUCTION_MATCH_DUPLICATE_SOURCE = 'AUCTION_MATCH_DUPLICATE_SOURCE'
export const CODE_AUCTION_MATCH_STATUS = 'AUCTION_MATCH_STATUS'
export const CODE_AUCTION_CANDIDATE_STATUS = 'AUCTION_CANDIDATE_STATUS'
export const CODE_AUCTION_SHIP_CANCEL_STATUS = 'AUCTION_SHIP_CANCEL_STATUS'
export const CODE_AUCTION_MATCH_DISCREPANCY = 'AUCTION_MATCH_DISCREPANCY'
export const CODE_AUCTION_CORRECTION_RETURN = 'AUCTION_CORRECTION_RETURN'
export const CODE_AUCTION_CORRECTION_PAYMENT = 'AUCTION_CORRECTION_PAYMENT'
export const CODE_AUCTION_CORRECTION_STATUS = 'AUCTION_CORRECTION_STATUS'
export const CODE_AUCTION_CORRECTION_MATCH = 'AUCTION_CORRECTION_MATCH'
export const CODE_AUCTION_CORRECTION_SALES = 'AUCTION_CORRECTION_SALES'
export const CODE_AUCTION_SHIP_NOT_FOUND = 'AUCTION_SHIP_NOT_FOUND'

export type SelectedCandidate = {
  sourceKey: string
  userGradeCd: string | null
}

export type DiscrepancyDraft = {
  reason: AuctionDiscrepancyReason | ''
  remark: string
  returnConfirmed: boolean
}

export type SpecDiffRow = {
  spec: AuctionShipmentSpec
  shipped: number
  matched: number
  diff: number
}

const WEIGHT_EPS = 0.05

export function defaultTradeDt(shipDt: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(shipDt || '').trim())
  if (!m) return String(shipDt || '').trim()
  const dt = new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3])))
  dt.setUTCDate(dt.getUTCDate() - 1)
  return dt.toISOString().slice(0, 10)
}

export function sourceUsedLabel(source: string): string {
  if (source === SOURCE_SETTLEMENT) return '정산자료'
  if (source === SOURCE_REALTIME) return '실시간 경락자료'
  return ''
}

export function reasonLabel(reason: AuctionDiscrepancyReason): string {
  if (reason === 'QTY_ERROR') return '수량오류'
  if (reason === 'RETURN') return '반품처리'
  if (reason === 'DAMAGE') return '파손/폐기'
  return '기타'
}

export function roundWeight(weight: number): number {
  return Math.round(Number(weight) * 1e6) / 1e6
}

export function specKey(spec: {
  variety_cd: string
  grade_cd: string
  size_cd: string
  weight: number
}): string {
  return `${spec.variety_cd}|${spec.grade_cd}|${spec.size_cd}|${roundWeight(spec.weight)}`
}

export function weightClose(a: number | null | undefined, b: number): boolean {
  if (a == null || !Number.isFinite(Number(a))) return false
  return Math.abs(Number(a) - Number(b)) < WEIGHT_EPS
}

function labelKey(value: string | null | undefined): string {
  return String(value || '').replace(/\s+/g, '').toLowerCase()
}

export function uniqueSpecGrades(
  specs: AuctionShipmentSpec[],
): { grade_cd: string; grade_name: string }[] {
  const map = new Map<string, string>()
  for (const spec of specs) {
    const cd = String(spec.grade_cd || '').trim()
    if (!cd || map.has(cd)) continue
    map.set(cd, spec.grade_name || cd)
  }
  return [...map.entries()].map(([grade_cd, grade_name]) => ({ grade_cd, grade_name }))
}

export function mapCandidateToSpec(
  candidate: AuctionCandidate,
  specs: AuctionShipmentSpec[],
  userGradeCd?: string | null,
): AuctionShipmentSpec | null {
  const byWeight = specs.filter((spec) => weightClose(candidate.spec_kg, spec.weight))
  const pool = byWeight.length ? byWeight : specs
  if (candidate.requires_grade_input) {
    const grade = String(userGradeCd || '').trim()
    if (!grade) return null
    const hits = pool.filter((spec) => spec.grade_cd === grade)
    return hits.length === 1 ? hits[0] : null
  }
  const hits = pool.filter((spec) => {
    const gradeOk =
      !candidate.grade_name || labelKey(candidate.grade_name) === labelKey(spec.grade_name)
    const sizeOk =
      !candidate.size_name || labelKey(candidate.size_name) === labelKey(spec.size_name)
    return gradeOk && sizeOk
  })
  return hits.length === 1 ? hits[0] : null
}

export function computeSpecDiffs(
  specs: AuctionShipmentSpec[],
  selected: { candidate: AuctionCandidate; userGradeCd?: string | null }[],
): SpecDiffRow[] {
  const matched = new Map<string, number>()
  for (const spec of specs) matched.set(specKey(spec), 0)
  for (const row of selected) {
    const spec = mapCandidateToSpec(row.candidate, specs, row.userGradeCd)
    if (!spec) continue
    const key = specKey(spec)
    matched.set(key, (matched.get(key) || 0) + Number(row.candidate.qty || 0))
  }
  return specs.map((spec) => {
    const shipped = Number(spec.farm_shipped_qty || 0)
    const qty = matched.get(specKey(spec)) || 0
    return { spec, shipped, matched: qty, diff: qty - shipped }
  })
}

export function selectedTotals(candidates: AuctionCandidate[]): {
  count: number
  qty: number
  amount: number
} {
  return {
    count: candidates.length,
    qty: candidates.reduce((sum, item) => sum + Number(item.qty || 0), 0),
    amount: candidates.reduce((sum, item) => sum + Number(item.amount || 0), 0),
  }
}

export function allowedReasons(diff: number): AuctionDiscrepancyReason[] {
  if (diff > 0) return ['QTY_ERROR', 'OTHER']
  return ['QTY_ERROR', 'RETURN', 'DAMAGE', 'OTHER']
}

export function discrepancyReady(
  diffs: SpecDiffRow[],
  drafts: Record<string, DiscrepancyDraft>,
): { ok: boolean; message: string | null } {
  for (const row of diffs) {
    if (row.diff === 0) continue
    const draft = drafts[specKey(row.spec)]
    if (!draft?.reason) {
      return { ok: false, message: '수량차이가 있는 규격의 처리 유형을 선택해 주세요.' }
    }
    if (!allowedReasons(row.diff).includes(draft.reason)) {
      return { ok: false, message: '선택한 처리 유형을 이 수량차이에 사용할 수 없습니다.' }
    }
    if (draft.reason === 'OTHER' && !String(draft.remark || '').trim()) {
      return { ok: false, message: '기타는 비고가 필요합니다.' }
    }
    if (draft.reason === 'RETURN' && !draft.returnConfirmed) {
      return { ok: false, message: '반품 반영을 확인해 주세요.' }
    }
  }
  return { ok: true, message: null }
}

export function buildFinalizeRequest(params: {
  tradeDt: string
  selected: { candidate: AuctionCandidate; userGradeCd?: string | null }[]
  diffs: SpecDiffRow[]
  drafts: Record<string, DiscrepancyDraft>
}): AuctionFinalizeRequest {
  const selected_candidates = params.selected.map((row) => ({
    source_key: row.candidate.source_key,
    user_grade_cd: row.candidate.requires_grade_input
      ? String(row.userGradeCd || '').trim() || null
      : null,
  }))
  const discrepancies = params.diffs
    .filter((row) => row.diff !== 0)
    .map((row) => {
      const draft = params.drafts[specKey(row.spec)]
      const reason = (draft?.reason || 'QTY_ERROR') as AuctionDiscrepancyReason
      return {
        variety_cd: row.spec.variety_cd,
        grade_cd: row.spec.grade_cd,
        size_cd: row.spec.size_cd,
        weight: row.spec.weight,
        reason_cd: reason,
        remark: String(draft?.remark || '').trim() || null,
        return_confirmed: reason === 'RETURN' ? Boolean(draft?.returnConfirmed) : false,
      }
    })
  return {
    trade_dt: params.tradeDt,
    selected_candidates,
    discrepancies,
  }
}

export function selectionComplete(
  selected: { candidate: AuctionCandidate; userGradeCd?: string | null }[],
): boolean {
  if (!selected.length) return false
  return selected.every((row) => {
    if (!row.candidate.requires_grade_input) return true
    return Boolean(String(row.userGradeCd || '').trim())
  })
}

export function auctionMatchUserMessage(err: unknown): string {
  const code = readApiClientErrorCode(err)
  if (code === CODE_AUCTION_CANDIDATE_STALE) return MSG_AUCTION_MATCH_STALE
  if (code === CODE_SETTLEMENT_SOURCE_ERROR) return MSG_AUCTION_MATCH_SETTLEMENT_SOURCE
  if (code === CODE_REALTIME_SOURCE_ERROR) return MSG_AUCTION_MATCH_REALTIME_SOURCE
  if (code === CODE_AUCTION_MATCH_DUPLICATE_SOURCE) return MSG_AUCTION_MATCH_DUPLICATE
  if (
    code === CODE_AUCTION_MATCH_STATUS
    || code === CODE_AUCTION_SHIP_CANCEL_STATUS
    || code === CODE_AUCTION_CANDIDATE_STATUS
  ) {
    return MSG_AUCTION_MATCH_STATUS
  }
  if (code === 'INVALID_DISCREPANCY' || code === CODE_AUCTION_MATCH_DISCREPANCY) {
    return '수량차이 처리 내용을 확인해 주세요.'
  }
  if (code === 'AUCTION_MATCH_UNRESOLVED') return '수량차이가 있는 규격의 처리 유형을 선택해 주세요.'
  if (code === 'AUCTION_MATCH_GRADE') return '실시간 경락은 출하에 있는 등급을 선택해 주세요.'
  if (code === 'AUCTION_MATCH_AMBIGUOUS_SPEC' || code === 'AUCTION_MATCH_SPEC_UNMATCHED') {
    return '선택한 경락자료가 출하 규격과 맞지 않습니다. 선택을 확인해 주세요.'
  }
  return MSG_AUCTION_MATCH_GENERIC
}

export function isStaleCandidateError(err: unknown): boolean {
  return readApiClientErrorCode(err) === CODE_AUCTION_CANDIDATE_STALE
}

export function isSourceFetchError(err: unknown): boolean {
  const code = readApiClientErrorCode(err)
  return code === CODE_SETTLEMENT_SOURCE_ERROR || code === CODE_REALTIME_SOURCE_ERROR
}

export function isStatusConflictError(err: unknown): boolean {
  const code = readApiClientErrorCode(err)
  return (
    code === CODE_AUCTION_MATCH_STATUS
    || code === CODE_AUCTION_SHIP_CANCEL_STATUS
    || code === CODE_AUCTION_CANDIDATE_STATUS
  )
}

export function isDuplicateSourceError(err: unknown): boolean {
  return readApiClientErrorCode(err) === CODE_AUCTION_MATCH_DUPLICATE_SOURCE
}

export function auctionReopenUserMessage(err: unknown): string {
  const rec = err as { status?: unknown } | null
  const status = typeof rec?.status === 'number' ? rec.status : 0
  const code = readApiClientErrorCode(err)
  if (status === 404 || code === CODE_AUCTION_SHIP_NOT_FOUND) {
    return MSG_AUCTION_REOPEN_NOT_FOUND
  }
  if (code === CODE_AUCTION_CORRECTION_RETURN) return MSG_AUCTION_REOPEN_RETURN
  if (code === CODE_AUCTION_CORRECTION_PAYMENT) return MSG_AUCTION_REOPEN_PAYMENT
  if (code === CODE_AUCTION_CORRECTION_STATUS) return MSG_AUCTION_REOPEN_STATUS
  if (code === CODE_AUCTION_CORRECTION_MATCH || code === CODE_AUCTION_CORRECTION_SALES) {
    return MSG_AUCTION_REOPEN_BLOCKED
  }
  return MSG_AUCTION_REOPEN_GENERIC
}

export function isReopenNotFoundError(err: unknown): boolean {
  const rec = err as { status?: unknown } | null
  const status = typeof rec?.status === 'number' ? rec.status : 0
  return status === 404 || readApiClientErrorCode(err) === CODE_AUCTION_SHIP_NOT_FOUND
}

export function isReopenStatusConflictError(err: unknown): boolean {
  return readApiClientErrorCode(err) === CODE_AUCTION_CORRECTION_STATUS
}

export function formatWon(amount: number): string {
  return `${Math.round(Number(amount) || 0).toLocaleString('ko-KR')}원`
}

export function specTitle(spec: AuctionShipmentSpec): string {
  const parts = [
    spec.grade_name || spec.grade_cd,
    spec.size_name || spec.size_cd,
    spec.weight > 0 ? `${spec.weight}kg` : '',
  ]
  return parts.filter(Boolean).join(' · ')
}

export function mergeShipmentLists<T extends { shipment_id: string }>(
  pages: { items?: T[] }[],
): T[] {
  const byId = new Map<string, T>()
  for (const page of pages) {
    for (const item of page.items ?? []) {
      if (!item.shipment_id) continue
      byId.set(item.shipment_id, item)
    }
  }
  return [...byId.values()]
}

/** ship_dt(YYYY-MM-DD) → YYYY-MM. 형식이 아니면 빈 문자열. */
export function shipmentYearMonth(shipDt: string): string {
  const raw = String(shipDt || '')
  return /^\d{4}-\d{2}/.test(raw) ? raw.slice(0, 7) : ''
}

export function formatShipmentYearMonthLabel(yearMonth: string): string {
  const matched = /^(\d{4})-(\d{2})$/.exec(yearMonth)
  if (!matched) return yearMonth
  return `${matched[1]}년 ${Number(matched[2])}월`
}

export function uniqueShipmentYearMonths(items: { ship_dt: string }[]): string[] {
  const months = new Set<string>()
  for (const item of items) {
    const yearMonth = shipmentYearMonth(item.ship_dt)
    if (yearMonth) months.add(yearMonth)
  }
  return [...months].sort((a, b) => b.localeCompare(a))
}

export function filterShipmentsByYearMonth<T extends { ship_dt: string }>(
  items: T[],
  yearMonth: string,
): T[] {
  if (!yearMonth) return items
  return items.filter((item) => shipmentYearMonth(item.ship_dt) === yearMonth)
}

const STATUS_RANK: Record<string, number> = {
  IN_TRANSIT: 0,
  COMPLETED: 1,
  CANCELLED: 2,
}

export function sortAuctionShipments<T extends { status: string; ship_dt: string; reg_dt?: string }>(
  items: T[],
): T[] {
  return [...items].sort((a, b) => {
    const rank = (STATUS_RANK[a.status] ?? 9) - (STATUS_RANK[b.status] ?? 9)
    if (rank) return rank
    const byDate = String(b.ship_dt).localeCompare(String(a.ship_dt))
    if (byDate) return byDate
    return String(b.reg_dt || '').localeCompare(String(a.reg_dt || ''))
  })
}
