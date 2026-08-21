/** 신규/수정 주문 공통 form model — Stage 2 */

import {
  DEFAULT_WAREHOUSE_CD,
  DELIVERY_TP_VISIT,
  MSG_LINE_REQUIRED,
  MSG_PARCEL_DEST_INCOMPLETE,
  MSG_PARCEL_DEST_QTY,
  MSG_PARCEL_QTY_OVER,
  isParcelDelivery,
  parseWeightFromCodeNm,
} from '@/views/orders/ordersConstants'
import type { OrderCreatePayload, OrderDetail, OrderLine } from '@/types/order'

export type EditDest = {
  qty: string
  rcv_name: string
  rcv_tel: string
  rcv_addr: string
  dlvry_msg: string
}

export type EditLine = {
  variety_cd: string
  weight_cd: string
  grade_cd: string
  size_cd: string
  qty: string
  unit_price: string
  delivery_tp_cd: string
  dests: EditDest[]
}

export type SaveIssue = {
  lineIdx: number
  destIdx: number | null
  ship: boolean
  message: string
}

const QTY_EPS = 1e-9

export function num(raw: string): number {
  const n = Number(String(raw || '').replace(/,/g, ''))
  return Number.isFinite(n) ? n : 0
}

export function emptyDest(): EditDest {
  return {
    qty: '1',
    rcv_name: '',
    rcv_tel: '',
    rcv_addr: '',
    dlvry_msg: '',
  }
}

export function emptyLine(): EditLine {
  return {
    variety_cd: '',
    weight_cd: '',
    grade_cd: '',
    size_cd: '',
    qty: '1',
    unit_price: '0',
    delivery_tp_cd: DELIVERY_TP_VISIT,
    dests: [emptyDest()],
  }
}

/** 완전 공백 draft — 배송지 없음으로 취급 (기본 qty 무시). */
export function isBlankDestDraft(dest: EditDest): boolean {
  return !(
    dest.rcv_name.trim() ||
    dest.rcv_tel.trim() ||
    dest.rcv_addr.trim() ||
    dest.dlvry_msg.trim()
  )
}

export function effectiveDests(line: EditLine): EditDest[] {
  return line.dests.filter((d) => !isBlankDestDraft(d))
}

export function destQtySum(line: EditLine): number {
  return effectiveDests(line).reduce((sum, d) => sum + num(d.qty), 0)
}

export function findSaveIssue(
  lines: EditLine[],
  lineWeightValue: (line: EditLine) => number,
): SaveIssue | null {
  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i]
    if (
      !(
        line.variety_cd &&
        line.size_cd &&
        line.weight_cd &&
        lineWeightValue(line) > 0 &&
        num(line.qty) > 0
      )
    ) {
      return { lineIdx: i, destIdx: null, ship: false, message: MSG_LINE_REQUIRED }
    }
    if (!isParcelDelivery(line.delivery_tp_cd)) continue
    const dests = effectiveDests(line)
    for (let j = 0; j < dests.length; j += 1) {
      const dest = dests[j]
      const origIdx = line.dests.indexOf(dest)
      if (num(dest.qty) <= 0) {
        return { lineIdx: i, destIdx: origIdx, ship: true, message: MSG_PARCEL_DEST_QTY }
      }
      if (!dest.rcv_name.trim() || !dest.rcv_tel.trim() || !dest.rcv_addr.trim()) {
        return {
          lineIdx: i,
          destIdx: origIdx,
          ship: true,
          message: MSG_PARCEL_DEST_INCOMPLETE,
        }
      }
    }
    if (destQtySum(line) - num(line.qty) > QTY_EPS) {
      return { lineIdx: i, destIdx: null, ship: true, message: MSG_PARCEL_QTY_OVER }
    }
  }
  return null
}

export function weightCdFromWeight(
  weight: number,
  codes: { code_cd: string; code_nm: string }[],
): string {
  const hit = codes.find(
    (c) => Math.abs(parseWeightFromCodeNm(c.code_nm) - Number(weight)) < QTY_EPS,
  )
  return hit?.code_cd || codes[0]?.code_cd || ''
}

export function lineFromOrderLine(
  line: OrderLine,
  weightCodes: { code_cd: string; code_nm: string }[],
): EditLine {
  const tp = line.dlvry_tp || line.deliveries?.[0]?.delivery_tp_cd || DELIVERY_TP_VISIT
  const dests = (line.deliveries || []).map((d) => ({
    qty: String(d.qty ?? ''),
    rcv_name: d.rcv_name || '',
    rcv_tel: d.rcv_tel || '',
    rcv_addr: d.rcv_addr || '',
    dlvry_msg: d.dlvry_msg || '',
  }))
  return {
    variety_cd: line.variety_cd,
    weight_cd: weightCdFromWeight(line.weight, weightCodes),
    grade_cd: line.grade_cd,
    size_cd: line.size_cd,
    qty: String(line.qty),
    unit_price: String(line.unit_price),
    delivery_tp_cd: tp,
    dests: dests.length ? dests : [{ ...emptyDest(), qty: String(line.qty || 1) }],
  }
}

export function linesFromDetail(
  detail: OrderDetail,
  weightCodesFor: (line: { variety_cd: string }) => { code_cd: string; code_nm: string }[],
): EditLine[] {
  const src = detail.lines || []
  if (!src.length) return [emptyLine()]
  return src.map((line) => lineFromOrderLine(line, weightCodesFor(line)))
}

export function buildOrderPayload(
  input: {
    custmId: string
    orderDt: string
    prePay: number
    rmk: string
    harvestYear: number
    lines: EditLine[]
    lineWeightValue: (line: EditLine) => number
    lineDeliveries: (line: EditLine) => OrderCreatePayload['lines'][number]['deliveries']
  },
): OrderCreatePayload {
  return {
    custm_id: input.custmId,
    order_dt: input.orderDt,
    pre_pay_amt: input.prePay,
    rmk: input.rmk,
    lines: input.lines.map((l) => ({
      variety_cd: l.variety_cd,
      weight: input.lineWeightValue(l),
      grade_cd: l.grade_cd,
      size_cd: l.size_cd,
      qty: num(l.qty),
      unit_price: num(l.unit_price),
      harvest_year: input.harvestYear,
      warehouse_cd: DEFAULT_WAREHOUSE_CD,
      dlvry_tp: l.delivery_tp_cd || DELIVERY_TP_VISIT,
      deliveries: input.lineDeliveries(l),
    })),
  }
}
