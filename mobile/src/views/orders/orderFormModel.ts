/** 신규/수정 주문 공통 form model — Stage 2 */

import {
  DEFAULT_WAREHOUSE_CD,
  DELIVERY_TP_VISIT,
  MSG_LINE_REQUIRED,
  MSG_JUICE_PACK_REQUIRED,
  MSG_PARCEL_DEST_INCOMPLETE,
  MSG_PARCEL_DEST_QTY,
  MSG_PARCEL_QTY_OVER,
  ORDER_PRODUCT_JUICE,
  ORDER_PRODUCT_PEAR,
  PEAR_ITEM_CD,
  isJuiceItemCd,
  isParcelDelivery,
  parseWeightFromCodeNm,
} from '@/views/orders/ordersConstants'
import {
  juicePackKeyFromStockFields,
  juicePackLabel,
} from '@/views/orders/orderJuiceModel'
import type { OrderCreatePayload, OrderDetail, OrderLine } from '@/types/order'

export type EditDest = {
  qty: string
  rcv_name: string
  rcv_tel: string
  rcv_addr: string
  dlvry_msg: string
}

export type EditLine = {
  product_kind: typeof ORDER_PRODUCT_PEAR | typeof ORDER_PRODUCT_JUICE
  item_cd: string
  variety_cd: string
  weight_cd: string
  grade_cd: string
  size_cd: string
  /** 배즙 재고 weight (배 라인은 payload 시 weight_cd에서 산출) */
  juice_weight: number
  juice_wh_cd: string
  juice_harvest_year: number
  juice_pack_key: string
  juice_pack_label: string
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
    product_kind: ORDER_PRODUCT_PEAR,
    item_cd: PEAR_ITEM_CD,
    variety_cd: '',
    weight_cd: '',
    grade_cd: '',
    size_cd: '',
    juice_weight: 0,
    juice_wh_cd: '',
    juice_harvest_year: 0,
    juice_pack_key: '',
    juice_pack_label: '',
    qty: '1',
    unit_price: '0',
    delivery_tp_cd: DELIVERY_TP_VISIT,
    dests: [emptyDest()],
  }
}

export function isJuiceEditLine(line: Pick<EditLine, 'product_kind' | 'item_cd'>): boolean {
  return (
    line.product_kind === ORDER_PRODUCT_JUICE || isJuiceItemCd(line.item_cd)
  )
}

export function clearJuiceSpec(line: EditLine): void {
  line.juice_weight = 0
  line.juice_wh_cd = ''
  line.juice_harvest_year = 0
  line.juice_pack_key = ''
  line.juice_pack_label = ''
}

export function applyJuicePackToLine(
  line: EditLine,
  pack: {
    key: string
    label: string
    item_cd: string
    variety_cd: string
    grade_cd: string
    size_cd: string
    weight: number
    wh_cd: string
    harvest_year: number
  },
): void {
  line.product_kind = ORDER_PRODUCT_JUICE
  line.item_cd = pack.item_cd
  line.variety_cd = pack.variety_cd
  line.grade_cd = pack.grade_cd
  line.size_cd = pack.size_cd
  line.weight_cd = ''
  line.juice_weight = Number(pack.weight) || 0
  line.juice_wh_cd = pack.wh_cd || DEFAULT_WAREHOUSE_CD
  line.juice_harvest_year = Number(pack.harvest_year) || 0
  line.juice_pack_key = pack.key
  line.juice_pack_label = pack.label
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
    if (isJuiceEditLine(line)) {
      if (
        !(
          line.item_cd &&
          line.variety_cd &&
          line.grade_cd &&
          line.size_cd &&
          line.juice_pack_key &&
          line.juice_weight > 0 &&
          num(line.qty) > 0
        )
      ) {
        return {
          lineIdx: i,
          destIdx: null,
          ship: false,
          message: line.juice_pack_key ? MSG_LINE_REQUIRED : MSG_JUICE_PACK_REQUIRED,
        }
      }
    } else if (
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
  const juice = isJuiceItemCd(line.item_cd)
  const weight = Number(line.weight) || 0
  const wh = String(line.wh_cd || '').trim() || DEFAULT_WAREHOUSE_CD
  const harvest = Number(line.harvest_year) || 0
  const base = emptyLine()
  if (juice) {
    const packKey = juicePackKeyFromStockFields({
      wh_cd: wh,
      item_cd: line.item_cd,
      variety_cd: line.variety_cd,
      grade_cd: line.grade_cd,
      size_cd: line.size_cd,
      weight,
      harvest_year: harvest,
    })
    return {
      ...base,
      product_kind: ORDER_PRODUCT_JUICE,
      item_cd: line.item_cd,
      variety_cd: line.variety_cd,
      weight_cd: '',
      grade_cd: line.grade_cd,
      size_cd: line.size_cd,
      juice_weight: weight,
      juice_wh_cd: wh,
      juice_harvest_year: harvest,
      juice_pack_key: packKey,
      juice_pack_label: juicePackLabel({
        grade_nm: line.grade_nm || '',
        size_nm: line.size_nm || '',
        weight,
      }),
      qty: String(line.qty),
      unit_price: String(line.unit_price),
      delivery_tp_cd: tp,
      dests: dests.length ? dests : [{ ...emptyDest(), qty: String(line.qty || 1) }],
    }
  }
  return {
    ...base,
    product_kind: ORDER_PRODUCT_PEAR,
    item_cd: PEAR_ITEM_CD,
    variety_cd: line.variety_cd,
    weight_cd: weightCdFromWeight(weight, weightCodes),
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
    salesTypeCd: string
    seasonTypeCd: string
    prePay: number
    prePayMethodCd: string | null
    rmk: string
    harvestYear: number
    lines: EditLine[]
    lineWeightValue: (line: EditLine) => number
    lineDeliveries: (line: EditLine) => OrderCreatePayload['lines'][number]['deliveries']
  },
): OrderCreatePayload {
  const prePay = input.prePay > 0 ? input.prePay : 0
  return {
    custm_id: input.custmId,
    order_dt: input.orderDt,
    sales_type_cd: input.salesTypeCd,
    season_type_cd: input.seasonTypeCd,
    pre_pay_amt: prePay,
    pre_pay_method_cd: prePay > 0 ? input.prePayMethodCd || null : null,
    rmk: input.rmk,
    lines: input.lines.map((l) => {
      const juice = isJuiceEditLine(l)
      return {
        item_cd: juice ? l.item_cd : PEAR_ITEM_CD,
        variety_cd: l.variety_cd,
        weight: juice ? l.juice_weight : input.lineWeightValue(l),
        grade_cd: l.grade_cd,
        size_cd: l.size_cd,
        qty: num(l.qty),
        unit_price: num(l.unit_price),
        harvest_year: juice && l.juice_harvest_year > 0 ? l.juice_harvest_year : input.harvestYear,
        warehouse_cd: juice && l.juice_wh_cd ? l.juice_wh_cd : DEFAULT_WAREHOUSE_CD,
        dlvry_tp: l.delivery_tp_cd || DELIVERY_TP_VISIT,
        deliveries: input.lineDeliveries(l),
      }
    }),
  }
}
