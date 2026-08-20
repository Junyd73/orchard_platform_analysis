import type { ShipConfirmLine, ShipConfirmRequest, ShipMode } from '@/types/shipment'
import { ApiClientError } from '@/api/client'

export const SHIP_MODE_STOCK: ShipMode = 'STOCK'
export const SHIP_MODE_DIRECT: ShipMode = 'DIRECT'

export const LABEL_SHIP_PAGE = '판매/출고'
export const LABEL_CONFIRM_SHIP = '판매/출고 확정'
export const HINT_SHIP_PRODUCTION =
  '주문 없이 생산 결과를 바로 판매합니다. 예약접수와 무관합니다.'
export const HINT_SHIP_STOCK =
  '주문 없이 선택한 재고를 바로 판매합니다. 여러 상품을 한 번에 담을 수 있습니다.'
export const HINT_SHIP_ORDER =
  '예약주문 출고입니다. 출고하면 잔량이 있으면 배송준비, 전량이면 배송완료입니다.'
export const LABEL_MODE = '출고방식'
export const LABEL_MODE_STOCK = '배정재고 사용'
export const LABEL_MODE_DIRECT = '일반재고 사용'
export const LABEL_CUSTOMER = '고객'
export const LABEL_QTY = '판매수량'
export const LABEL_UNIT_PRICE = '단가'
export const LABEL_ORDER = '주문'
export const LABEL_REMAINING = '주문 잔여'
export const LABEL_SHIP_LINE = '출고'
export const MSG_NO_PREFILL = '출고할 상품이 없습니다. 주문 또는 재고에서 들어와 주세요.'
export const MSG_QTY_INVALID = '판매수량은 0보다 커야 합니다.'
export const MSG_QTY_OVER_REMAINING = '주문 잔여수량보다 출고수량이 많습니다.'
export const MSG_CONFIRM_OK = '판매가 확정되었습니다.'
export const MSG_STOCK_MODE_NEED_ALLOC = '배정된 재고가 없어 일반재고로 출고합니다.'
export const MSG_STOCK_MODE_PARTIAL_ALLOC = '선택한 상품 중 배정재고가 부족한 항목이 있습니다.'
export const MSG_STOCK_MODE_NEED_ORDER = '배정재고 출고는 주문이 필요합니다.'
export const QTY_EPS = 1e-9

export const ORDER_STATUS_PREP = 'ST010300'
export const ORDER_STATUS_DELIVERED = 'ST010400'

export type ShipEntrySource = 'PRODUCTION' | 'ORDER' | 'STOCK'

export type ShipDraftLine = {
  order_detail_id: string | null
  item_cd: string
  variety_cd: string
  grade_cd: string
  size_cd: string
  weight: number
  harvest_year: number
  wh_cd: string
  qty: number
  unit_price: number
  remaining_qty: number | null
  alloc_remaining: number
  variety_nm?: string
  grade_nm?: string
  size_nm?: string
  item_nm?: string
}

export function canUseStockMode(lines: ShipDraftLine[]): boolean {
  if (!lines.length) return false
  return lines.every((ln) => Number(ln.alloc_remaining) + QTY_EPS >= Number(ln.qty))
}

export function findStockModeIssue(lines: ShipDraftLine[]): string {
  if (!lines.length) return ''
  for (const ln of lines) {
    if (Number(ln.alloc_remaining) + QTY_EPS < Number(ln.qty)) {
      return MSG_STOCK_MODE_PARTIAL_ALLOC
    }
  }
  return ''
}

export function defaultShipMode(allocRemaining: number, hasOrder: boolean): ShipMode {
  if (!hasOrder) return SHIP_MODE_DIRECT
  return allocRemaining > 1e-9 ? SHIP_MODE_STOCK : SHIP_MODE_DIRECT
}

export function shipModeLabel(mode: ShipMode): string {
  return mode === SHIP_MODE_STOCK ? LABEL_MODE_STOCK : LABEL_MODE_DIRECT
}

export function buildShipConfirmRequest(input: {
  shipMode: ShipMode
  salesDt: string
  orderNo: string | null
  custmId: string | null
  lines: ShipDraftLine[]
}): ShipConfirmRequest {
  const lines: ShipConfirmLine[] = input.lines.map((ln) => ({
    qty: Number(ln.qty),
    order_detail_id: ln.order_detail_id,
    item_cd: ln.item_cd,
    variety_cd: ln.variety_cd,
    grade_cd: ln.grade_cd,
    size_cd: ln.size_cd,
    weight: ln.weight,
    harvest_year: ln.harvest_year,
    wh_cd: ln.wh_cd,
    unit_price: ln.unit_price,
  }))
  return {
    ship_mode: input.shipMode,
    sales_dt: input.salesDt,
    order_no: input.orderNo,
    custm_id: input.custmId,
    lines,
  }
}

export function findShipQtyIssue(lines: ShipDraftLine[]): string {
  for (const ln of lines) {
    if (!(Number(ln.qty) > 0)) return MSG_QTY_INVALID
    if (ln.remaining_qty != null && Number(ln.qty) > Number(ln.remaining_qty) + 1e-9) {
      return MSG_QTY_OVER_REMAINING
    }
  }
  return ''
}

export function mapShipApiError(err: unknown): string {
  if (!(err instanceof ApiClientError)) {
    return '판매를 확정하지 못했습니다.'
  }
  const code = err.errorCode || ''
  if (code === 'ORDER_OVER_SHIP') return MSG_QTY_OVER_REMAINING
  if (code === 'STOCK_UNAVAILABLE') return '판매 가능한 재고가 부족합니다.'
  if (code === 'ALLOC_OVER_SHIP') return '배정된 재고가 부족합니다.'
  if (code === 'SCHEMA_PRECONDITION') {
    return '내부 데이터 준비가 필요합니다. 관리자 확인이 필요합니다.'
  }
  if (code === 'SHIP_STOCK_REQUIRES_ORDER') return MSG_STOCK_MODE_NEED_ORDER
  if (code === 'DATA_INTEGRITY') return '재고 정보가 맞지 않습니다. 다시 조회해 주세요.'
  return err.message || '판매를 확정하지 못했습니다.'
}

export function orderStatusLabel(statusCd: string | null | undefined): string {
  if (statusCd === ORDER_STATUS_PREP) return '배송준비'
  if (statusCd === ORDER_STATUS_DELIVERED) return '배송완료'
  return statusCd || ''
}
