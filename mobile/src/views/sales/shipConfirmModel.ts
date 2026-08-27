import type {
  ShipConfirmLine,
  ShipConfirmRequest,
  ShipDeliveryAllocation,
  ShipMode,
} from '@/types/shipment'
import { orderStatusLabelOf } from '@/views/orders/ordersConstants'
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
  '예약주문 출고입니다. 출고하면 잔량이 있으면 부분출고, 전량이면 배송완료입니다.'
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

/** S4A 직접판매 분류 */
export const LABEL_SALES_CLASS = '판매 분류'
export const LABEL_SALES_TYPE = '판매유형'
export const LABEL_SALES_CATEGORY = '판매구분'
export const CODE_PARENT_SALES_TYPE = 'SA01'
export const CODE_PARENT_SALES_CATEGORY = 'SA02'
export const DEFAULT_DIRECT_SALES_TYPE_CD = 'SA010100'
export const DEFAULT_DIRECT_SALES_CATEGORY_CD = 'SA020100'
/** SA02 경매판매 — 직접판매 Select에서 제외 */
export const SALES_CATEGORY_AUCTION_CD = 'SA020400'
export const MSG_DIRECT_SALES_TYPE_REQUIRED = '판매유형을 선택해 주세요.'
export const MSG_DIRECT_SALES_CATEGORY_REQUIRED = '판매구분을 선택해 주세요.'
export const MSG_DIRECT_SALES_TYPE_INVALID = '올바른 판매유형이 아닙니다.'
export const MSG_DIRECT_SALES_CATEGORY_INVALID = '직접판매에서 사용할 수 없는 판매구분입니다.'

export { ORDER_STATUS_PREP, ORDER_STATUS_DELIVERED } from '@/views/orders/ordersConstants'

export type ShipEntrySource = 'PRODUCTION' | 'ORDER' | 'STOCK'

export type ShipDeliveryDraft = {
  draft_id: string
  qty: number
  rcv_name: string
  rcv_tel: string
  rcv_addr: string
  dlvry_msg: string
  ship_fee: number
  /** 주문 배송지 원천. 화면에서 새로 만든 배송지는 null */
  order_dlvry_id?: string | null
}

export type ShipDraftLine = {
  order_detail_id: string | null
  item_cd: string
  variety_cd: string
  grade_cd: string
  size_cd: string
  weight: number
  harvest_year: number
  wh_cd: string
  storage_dt?: string
  available_qty?: number
  qty: number
  unit_price: number
  remaining_qty: number | null
  alloc_remaining: number
  variety_nm?: string
  grade_nm?: string
  size_nm?: string
  item_nm?: string
  /** 주문 line 배송방식 — 주문 출고 UI 분기·혼합 차단용 */
  dlvry_tp?: string
  /** order_dlvry_id 없이 출고된 이력 수량 (>0이면 배송지 재확인 안내) */
  untracked_delivery_shipped_qty?: number
  /** STOCK 택배 상품별 배송배분 (UI draft_id 포함). 수량 변경 시 자동 수정하지 않음. */
  delivery_allocations?: ShipDeliveryDraft[]
}

/** 재고 draft 중복 판별 키 (storage_dt 포함) — LOT/재고추적·기존 호환용. 판매 UI 식별에 쓰지 말 것. */
export function stockDraftKey(ln: Pick<
  ShipDraftLine,
  'item_cd' | 'variety_cd' | 'grade_cd' | 'size_cd' | 'weight' | 'harvest_year' | 'wh_cd' | 'storage_dt'
>): string {
  return [
    ln.item_cd,
    ln.variety_cd,
    ln.grade_cd,
    ln.size_cd,
    String(ln.weight),
    String(ln.harvest_year),
    ln.storage_dt || '',
    ln.wh_cd,
  ].join('|')
}

/**
 * 재고 직접판매 규격 키 (storage_dt 제외).
 * 사용자 판매 상품 식별 = wh + item + variety + grade + size + weight + harvest_year
 * 실제 OUT LOT는 Core DIRECT FIFO가 담당한다.
 */
export function stockSaleSpecKey(ln: Pick<
  ShipDraftLine | { wh_cd: string; item_cd: string; variety_cd: string; grade_cd: string; size_cd: string; weight: number; harvest_year: number },
  'wh_cd' | 'item_cd' | 'variety_cd' | 'grade_cd' | 'size_cd' | 'weight' | 'harvest_year'
>): string {
  return [
    ln.wh_cd,
    ln.item_cd,
    ln.variety_cd,
    ln.grade_cd,
    ln.size_cd,
    String(ln.weight),
    String(ln.harvest_year),
  ].join('|')
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

/** draft → API 배송배분 1건. order_dlvry_id는 신규 배송지면 null */
export function toApiDeliveryAllocation(a: ShipDeliveryDraft): ShipDeliveryAllocation {
  return {
    qty: Number(a.qty),
    rcv_name: String(a.rcv_name || '').trim(),
    rcv_tel: String(a.rcv_tel || '').trim(),
    rcv_addr: String(a.rcv_addr || '').trim(),
    dlvry_msg: String(a.dlvry_msg || '').trim(),
    ship_fee: Math.max(0, Math.round(Number(a.ship_fee) || 0)),
    order_dlvry_id: a.order_dlvry_id || null,
  }
}

export function buildShipConfirmRequest(input: {
  shipMode: ShipMode
  salesDt: string
  orderNo: string | null
  custmId: string | null
  lines: ShipDraftLine[]
  rmk?: string
  dlvryTp?: string
  shipFee?: number
  rcvName?: string
  rcvTel?: string
  rcvAddr?: string
  dlvryMsg?: string
  sndName?: string
  sndTel?: string
  sndAddr?: string
  /** true면 각 line에 delivery_allocations 배열 포함 (STOCK 택배 2C) */
  includeDeliveryAllocations?: boolean
  salesTypeCd?: string | null
  salesCategoryCd?: string | null
}): ShipConfirmRequest {
  const includeAlloc = Boolean(input.includeDeliveryAllocations)
  const lines: ShipConfirmLine[] = input.lines.map((ln) => {
    const base: ShipConfirmLine = {
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
    }
    if (includeAlloc) {
      base.delivery_allocations = (ln.delivery_allocations || []).map(toApiDeliveryAllocation)
    }
    return base
  })
  return {
    ship_mode: input.shipMode,
    sales_dt: input.salesDt,
    order_no: input.orderNo,
    custm_id: input.custmId,
    rmk: input.rmk || '',
    dlvry_tp: input.dlvryTp || '',
    ship_fee: Number(input.shipFee) || 0,
    rcv_name: input.rcvName || '',
    rcv_tel: input.rcvTel || '',
    rcv_addr: input.rcvAddr || '',
    dlvry_msg: input.dlvryMsg || '',
    snd_name: input.sndName || '',
    snd_tel: input.sndTel || '',
    snd_addr: input.sndAddr || '',
    sales_type_cd: input.salesTypeCd ?? null,
    sales_category_cd: input.salesCategoryCd ?? null,
    lines,
  }
}

export function findShipQtyIssue(lines: ShipDraftLine[]): string {
  for (const ln of lines) {
    if (!(Number(ln.qty) > 0)) return MSG_QTY_INVALID
    if (ln.remaining_qty != null && Number(ln.qty) > Number(ln.remaining_qty) + 1e-9) {
      return MSG_QTY_OVER_REMAINING
    }
    if (
      ln.available_qty != null
      && Number(ln.qty) > Number(ln.available_qty) + 1e-9
    ) {
      return '가용재고보다 많이 판매할 수 없습니다.'
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
  if (code === 'DIRECT_SALES_TYPE_REQUIRED') return MSG_DIRECT_SALES_TYPE_REQUIRED
  if (code === 'DIRECT_SALES_TYPE_INVALID') return MSG_DIRECT_SALES_TYPE_INVALID
  if (code === 'DIRECT_SALES_CATEGORY_REQUIRED') return MSG_DIRECT_SALES_CATEGORY_REQUIRED
  if (code === 'DIRECT_SALES_CATEGORY_INVALID') return MSG_DIRECT_SALES_CATEGORY_INVALID
  return err.message || '판매를 확정하지 못했습니다.'
}

export function orderStatusLabel(statusCd: string | null | undefined): string {
  return orderStatusLabelOf(statusCd)
}
