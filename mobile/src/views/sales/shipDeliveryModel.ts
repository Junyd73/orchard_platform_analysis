import {
  MSG_PARCEL_DEST_INCOMPLETE,
  MSG_PARCEL_DEST_NONE,
  MSG_PARCEL_DEST_QTY,
  MSG_PARCEL_DEST_REQUIRED,
  MSG_PARCEL_QTY_MISMATCH,
} from '@/views/orders/ordersConstants'
import { toApiDeliveryAllocation } from '@/views/sales/shipConfirmModel'
import type { ShipDraftLine, ShipDeliveryDraft } from '@/views/sales/shipConfirmModel'

export const MSG_SHIP_ALLOC_FEE_NEG = '배송비는 0 이상이어야 합니다.'
export const QTY_EPS = 1e-9

export type { ShipDeliveryDraft }
let _draftSeq = 0

export function newDeliveryDraftId(): string {
  _draftSeq += 1
  return `d${Date.now().toString(36)}_${_draftSeq}`
}

export function emptyDeliveryDraft(partial?: Partial<ShipDeliveryDraft>): ShipDeliveryDraft {
  return {
    qty: 1,
    rcv_name: '',
    rcv_tel: '',
    rcv_addr: '',
    dlvry_msg: '',
    ship_fee: 0,
    order_dlvry_id: null,
    ...partial,
    draft_id: partial?.draft_id || newDeliveryDraftId(),
  }
}

export function allocQtySum(line: Pick<ShipDraftLine, 'delivery_allocations'>): number {
  const list = line.delivery_allocations || []
  return list.reduce((s, a) => s + Number(a.qty || 0), 0)
}

export function allocShipFeeSum(line: Pick<ShipDraftLine, 'delivery_allocations'>): number {
  const list = line.delivery_allocations || []
  return list.reduce((s, a) => s + Math.max(0, Math.round(Number(a.ship_fee) || 0)), 0)
}

export function totalAllocShipFee(lines: ShipDraftLine[]): number {
  return lines.reduce((s, ln) => s + allocShipFeeSum(ln), 0)
}

/** 배송 상태 문구 — 0/3 · 2/3 · 3/3 · 4/3 */
export function deliveryStatusText(saleQty: number, assigned: number, unit = '박스'): string {
  const sale = Math.max(0, Math.floor(Number(saleQty) || 0))
  const got = Math.floor(Number(assigned) || 0)
  const remain = sale - got
  if (remain > 0) {
    return `배송 ${got}/${sale}${unit} · ${remain}미지정`
  }
  if (remain < 0) {
    return `배송 ${got}/${sale}${unit} · ${-remain}초과`
  }
  return '배송지 등록 완료'
}

/** 주문 택배 — 미배정(0)은 미등록, 그 외는 sales 동일 문구 */
export function orderParcelStatusText(
  orderQty: number,
  assigned: number,
  unit = '박스',
): string {
  if (Number(assigned) <= QTY_EPS) return MSG_PARCEL_DEST_NONE
  return deliveryStatusText(orderQty, assigned, unit)
}

/** ok | warn | danger — 배송상태 시각 구분 */
export function deliveryQtyTone(
  orderQty: number,
  assigned: number,
): 'ok' | 'warn' | 'danger' {
  const sale = Number(orderQty) || 0
  const got = Number(assigned) || 0
  if (Math.abs(got - sale) <= QTY_EPS) return 'ok'
  if (got > sale) return 'danger'
  return 'warn'
}

export function isDeliveryQtyMatched(line: ShipDraftLine): boolean {
  return Math.abs(allocQtySum(line) - Number(line.qty)) <= QTY_EPS
}

/** 택배 시 모든 품목 배송배분 완료 여부 */
export function findParcelDeliveryIssue(lines: ShipDraftLine[]): string {
  for (const ln of lines) {
    const allocs = ln.delivery_allocations
    if (!allocs || !allocs.length) return MSG_PARCEL_DEST_REQUIRED
    for (const a of allocs) {
      if (!(Number(a.qty) > 0)) return MSG_PARCEL_DEST_QTY
      if (!String(a.rcv_name || '').trim() || !String(a.rcv_tel || '').trim() || !String(a.rcv_addr || '').trim()) {
        return MSG_PARCEL_DEST_INCOMPLETE
      }
      if (Number(a.ship_fee) < 0) return MSG_SHIP_ALLOC_FEE_NEG
    }
    if (Math.abs(allocQtySum(ln) - Number(ln.qty)) > QTY_EPS) {
      return MSG_PARCEL_QTY_MISMATCH
    }
  }
  return ''
}

export function toApiDeliveryAllocations(line: ShipDraftLine) {
  return (line.delivery_allocations || []).map(toApiDeliveryAllocation)
}
