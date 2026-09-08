/** 판매 목록 (Stage 5). */

import {
  ITEM_JUICE_DORAJI,
  ITEM_JUICE_MID,
  ITEM_JUICE_PLAIN,
  formatOrderAmt,
  joinDot,
  orderListDateText,
} from '@/views/orders/ordersConstants'
import type { SalesDetailLine, SalesListItem, SalesPaymentItem } from '@/types/sales'

export const SALES_LIST_PAGE_SIZE = 20

export const SALES_STATUS_CONFIRMED = 'CONFIRMED'
export const SALES_STATUS_DRAFT = 'DRAFT'

export const PAYMENT_STATUS_UNPAID = 'UNPAID'
export const PAYMENT_STATUS_PARTIAL = 'PARTIAL'
export const PAYMENT_STATUS_PAID = 'PAID'

export const SALES_SOURCE_AUCTION = 'AUCTION'
export const SALES_SOURCE_AUCTION_RT = 'AUCTION_RT'

export const STATUS_FILTER_ALL = ''

export const LABEL_SALES_STATUS = '판매상태'
export const LABEL_PAYMENT_STATUS = '수금상태'
export const LABEL_SALES_DETAIL = '판매상세'
export const MSG_SALES_DETAIL_SUBTITLE = '거래처와 판매 내역을 확인할 수 있습니다.'
export const LABEL_SALES_PARTY = '거래처'
export const LABEL_SALES_SUMMARY = '판매요약'
export const LABEL_SALES_PRODUCTS = '판매상품'
export const LABEL_PRODUCT_SPEC = '품목 · 규격'
export const LABEL_PRODUCTS_MORE = '더보기'
export const LABEL_PRODUCTS_LESS = '접기'
export const SALES_DETAIL_PRODUCT_PREVIEW = 4
export const LABEL_PAYMENT_HISTORY = '수금내역'
export const LABEL_PAYMENT_REGISTER = '수금 등록'
export const LABEL_PAYMENT_REGISTER_CTA = '+ 수금 등록'
export const LABEL_PAY_DT = '수금일'
export const LABEL_PAY_DT_COL = '일자'
export const LABEL_PAY_METHOD = '결제수단'
export const LABEL_PAY_METHOD_COL = '수금방법'
export const LABEL_PAY_MEMO = '메모'
export const LABEL_PAY_AMOUNT = '수금액'
export const LABEL_PAY_TOTAL = '누적 수금'
export const LABEL_PAY_SUBMIT = '등록'
export const LABEL_PAY_CANCEL = '취소'
export const MSG_PAYMENT_CREATE_FAIL = '수금 등록에 실패했습니다.'
export const MSG_PAYMENT_RESULT_CHECK = '수금 처리 결과를 확인해 주세요.'
export const MSG_PAY_METHOD_REQUIRED = '결제수단을 선택해 주세요.'
export const MSG_PAY_AMOUNT_INVALID = '수금액을 확인해 주세요.'
export const PAY_METHOD_ACCT_PREFIX = 'AS0101'
export const PAY_METHOD_ACCT_LEVEL = 4
export const LABEL_SALES_ROUTE = '판매경로'
export const LABEL_SALES_METHOD = '판매방법'
export const LABEL_SALES_DATE = '판매일자'
export const LABEL_SALES_BOX_QTY = '판매박스수'
export const LABEL_SALES_AMOUNT = '판매금액'
export const LABEL_PAID_AMOUNT = '수금액'
export const LABEL_UNPAID_AMOUNT = '미수금'
export const LABEL_UNPAID_AMOUNT_FULL = '미수금액'
export const LABEL_QTY = '수량'
export const LABEL_UNIT_PRICE = '단가'
export const LABEL_LINE_AMOUNT = '금액'
export const LABEL_ORDER_NO = '주문번호'
export const LABEL_SALES_SEARCH_PLACEHOLDER = '고객명 / 판매번호 / 주문번호'
export const MSG_SALES_LOAD_FAIL = '판매 목록을 불러오지 못했습니다.'
export const MSG_SALES_DETAIL_LOAD_FAIL = '판매 상세를 불러오지 못했습니다.'
export const MSG_PAYMENT_HISTORY_LOAD_FAIL = '수금 내역을 불러오지 못했습니다.'
export const MSG_PAYMENT_HISTORY_EMPTY = '수금 내역이 없습니다.'
export const LABEL_PAYMENT_SOURCE_GENERAL = '일반수금'
export const LABEL_PAYMENT_SOURCE_ORDER_PREPAY = '선입금 자동적용'
export const PAYMENT_SOURCE_GENERAL = 'GENERAL'
export const PAYMENT_SOURCE_ORDER_PREPAY = 'ORDER_PREPAY'
export const MSG_SALES_EMPTY_FILTER = '조건에 맞는 판매가 없습니다.'
export const MSG_SALES_EMPTY_FILTER_DESC =
  '조회기간·판매상태·수금상태·검색을 바꿔 다시 조회해 보세요.'

export const SALES_STATUS_FILTER_OPTIONS = [
  { value: STATUS_FILTER_ALL, label: '전체' },
  { value: SALES_STATUS_CONFIRMED, label: '판매확정' },
  { value: SALES_STATUS_DRAFT, label: '초안' },
] as const

export const PAYMENT_STATUS_FILTER_OPTIONS = [
  { value: STATUS_FILTER_ALL, label: '전체' },
  { value: PAYMENT_STATUS_UNPAID, label: '미수' },
  { value: PAYMENT_STATUS_PARTIAL, label: '부분수금' },
  { value: PAYMENT_STATUS_PAID, label: '수금완료' },
] as const

const JUICE_ITEM_LABEL: Record<string, string> = {
  [ITEM_JUICE_PLAIN]: '일반배즙',
  [ITEM_JUICE_DORAJI]: '도라지배즙',
  [ITEM_JUICE_MID]: '배즙',
}

export function salesStatusLabelOf(status: string): string {
  if (status === SALES_STATUS_CONFIRMED) return '판매확정'
  if (status === SALES_STATUS_DRAFT) return '초안'
  return status || '-'
}

export function salesStatusToneOf(status: string): 'ok' | 'neutral' {
  return status === SALES_STATUS_CONFIRMED ? 'ok' : 'neutral'
}

export function paymentStatusLabelOf(row: Pick<SalesListItem, 'sales_status' | 'payment_status'>): string {
  if (row.sales_status === SALES_STATUS_DRAFT) return '수금대기'
  if (row.payment_status === PAYMENT_STATUS_PAID) return '수금완료'
  if (row.payment_status === PAYMENT_STATUS_PARTIAL) return '부분수금'
  if (row.payment_status === PAYMENT_STATUS_UNPAID) return '미수'
  return '수금대기'
}

export function paymentStatusToneOf(
  row: Pick<SalesListItem, 'sales_status' | 'payment_status'>,
): 'ok' | 'caution' | 'danger' | 'neutral' {
  if (row.sales_status === SALES_STATUS_DRAFT) return 'neutral'
  if (row.payment_status === PAYMENT_STATUS_PAID) return 'ok'
  if (row.payment_status === PAYMENT_STATUS_PARTIAL) return 'caution'
  if (row.payment_status === PAYMENT_STATUS_UNPAID) return 'danger'
  return 'neutral'
}

export function salesRouteLabel(row: Pick<SalesListItem, 'sales_source' | 'order_no'>): string {
  const source = String(row.sales_source || '').trim()
  if (source === SALES_SOURCE_AUCTION || source === SALES_SOURCE_AUCTION_RT) return '경매'
  if (String(row.order_no || '').trim()) return '주문출고'
  return '직접판매'
}

function salesRepWeightText(weight: number | null | undefined): string {
  const n = Number(weight)
  if (!Number.isFinite(n) || n <= 0) return ''
  return `${n}kg`
}

function salesRepProductText(
  row: Pick<
    SalesListItem,
    'rep_item_cd' | 'rep_variety_nm' | 'rep_size_nm' | 'rep_grade_nm' | 'rep_crop_nm' | 'rep_weight'
  >,
): string {
  const juice = JUICE_ITEM_LABEL[String(row.rep_item_cd || '').trim()]
  if (juice) return juice
  const variety = row.rep_variety_nm || ''
  const size = String(row.rep_size_nm || '').trim()
  const grade = row.rep_grade_nm || ''
  const crop = row.rep_crop_nm || ''
  const weight = salesRepWeightText(row.rep_weight)
  // 품종 · 중량 · 등급 · 크기(1다이). size가 이미 kg면 중량 자리로만 사용
  const weightPart = weight || (size.endsWith('kg') ? size : '')
  const sizePart = size && size !== weightPart ? size : ''
  return joinDot([variety, weightPart, grade, sizePart, crop].filter(Boolean))
}

export function salesListSecondaryText(row: SalesListItem): string {
  return joinDot([
    salesRepProductText(row),
    orderListDateText(row.sales_dt),
    salesRouteLabel(row),
  ])
}

export function salesListAmountLine(row: SalesListItem): string {
  return `${formatOrderAmt(row.tot_sales_amt)} | ${formatOrderAmt(row.paid_amt)} / ${formatOrderAmt(row.unpaid_amt)}`
}

export function salesListBoxQtyText(row: Pick<SalesListItem, 'tot_qty'>): string {
  const n = Number(row.tot_qty)
  const qty = Number.isFinite(n) ? Math.max(0, Math.round(n)) : 0
  return `${formatOrderAmt(qty)}박스`
}

export function salesListWonText(amount: number): string {
  return `${formatOrderAmt(amount)}원`
}

export function salesCustomerLabel(row: Pick<SalesListItem, 'customer' | 'custm_id'>): string {
  const name = String(row.customer || '').trim()
  if (name && name !== '-') return name
  const id = String(row.custm_id || '').trim()
  return id || '-'
}

function salesProductSpecKey(line: Pick<
  SalesDetailLine,
  'variety_cd' | 'size_cd' | 'grade_cd' | 'crop_nm'
>): string {
  return [
    line.variety_cd,
    line.size_cd,
    line.grade_cd,
    line.crop_nm,
  ].join('|')
}

export function salesDetailProductText(
  line: Pick<
    SalesDetailLine,
    'item_cd' | 'variety_nm' | 'size_nm' | 'grade_nm' | 'crop_nm' | 'weight'
  >,
): string {
  const juice = JUICE_ITEM_LABEL[String(line.item_cd || '').trim()]
  if (juice) return juice
  const size = String(line.size_nm || '').trim()
  const weight = salesRepWeightText(line.weight)
  const weightPart = weight || (size.endsWith('kg') ? size : '')
  const sizePart = size && size !== weightPart ? size : ''
  return joinDot(
    [line.variety_nm, weightPart, line.grade_nm, sizePart, line.crop_nm].filter(Boolean),
  )
}

export function salesProductsCountLabel(count: number): string {
  return `총 ${Math.max(0, Number(count) || 0)}개 상품`
}

export function paymentSourceLabelOf(
  item: Pick<SalesPaymentItem, 'payment_source' | 'source_order_no'>,
): string {
  if (item.payment_source === PAYMENT_SOURCE_ORDER_PREPAY) {
    const orderNo = String(item.source_order_no || '').trim()
    return orderNo
      ? `${LABEL_PAYMENT_SOURCE_ORDER_PREPAY} · ${orderNo}`
      : LABEL_PAYMENT_SOURCE_ORDER_PREPAY
  }
  return LABEL_PAYMENT_SOURCE_GENERAL
}

/** 수금내역 메모 표시. 자동 기본문구(판매입금)는 '-' 처리. */
export function paymentMemoText(
  item: Pick<SalesPaymentItem, 'rmk' | 'payment_source' | 'source_order_no'>,
): string {
  const rmk = String(item.rmk || '').trim()
  if (rmk && !/^판매입금\s*\(/u.test(rmk)) return rmk
  if (item.payment_source === PAYMENT_SOURCE_ORDER_PREPAY) {
    return paymentSourceLabelOf(item)
  }
  return '-'
}

/** FIFO raw rows → 논리 표시 line (order_detail_id NULL은 합치지 않음). */
export function groupSalesDetailLines(lines: SalesDetailLine[]): SalesDetailLine[] {
  const grouped = new Map<string, SalesDetailLine>()
  const slots: Array<
    | { kind: 'raw'; line: SalesDetailLine }
    | { kind: 'group'; key: string }
  > = []

  for (const line of lines) {
    const orderDetailId = String(line.order_detail_id || '').trim()
    if (!orderDetailId) {
      slots.push({ kind: 'raw', line: { ...line } })
      continue
    }
    const key = [
      orderDetailId,
      String(line.item_cd || ''),
      salesProductSpecKey(line),
      String(line.unit_price),
    ].join('::')
    const existing = grouped.get(key)
    if (existing) {
      existing.qty += line.qty
      existing.item_amt += line.item_amt
      continue
    }
    grouped.set(key, { ...line })
    slots.push({ kind: 'group', key })
  }

  return slots.map((slot) => {
    if (slot.kind === 'raw') return slot.line
    return grouped.get(slot.key)!
  })
}
