/** 판매 목록 (Stage 5). */

import {
  ITEM_JUICE_DORAJI,
  ITEM_JUICE_MID,
  ITEM_JUICE_PLAIN,
  formatOrderAmt,
  joinDot,
  orderListDateText,
} from '@/views/orders/ordersConstants'
import type { SalesDetailLine, SalesListItem } from '@/types/sales'

export const SALES_LIST_PAGE_SIZE = 20

export const SALES_STATUS_CONFIRMED = 'CONFIRMED'
export const SALES_STATUS_DRAFT = 'DRAFT'

export const PAYMENT_STATUS_UNPAID = 'UNPAID'
export const PAYMENT_STATUS_PARTIAL = 'PARTIAL'
export const PAYMENT_STATUS_PAID = 'PAID'

export const SALES_SOURCE_AUCTION_RT = 'AUCTION_RT'

export const STATUS_FILTER_ALL = ''

export const LABEL_SALES_STATUS = '판매상태'
export const LABEL_PAYMENT_STATUS = '수금상태'
export const LABEL_SALES_DETAIL = '판매상세'
export const LABEL_SALES_SUMMARY = '판매요약'
export const LABEL_SALES_PRODUCTS = '판매상품'
export const LABEL_SALES_ROUTE = '판매경로'
export const LABEL_SALES_AMOUNT = '판매금액'
export const LABEL_PAID_AMOUNT = '수금액'
export const LABEL_UNPAID_AMOUNT = '미수금'
export const LABEL_QTY = '수량'
export const LABEL_UNIT_PRICE = '단가'
export const LABEL_LINE_AMOUNT = '금액'
export const LABEL_ORDER_NO = '주문번호'
export const LABEL_SALES_SEARCH_PLACEHOLDER = '고객명 / 판매번호 / 주문번호'
export const MSG_SALES_LOAD_FAIL = '판매 목록을 불러오지 못했습니다.'
export const MSG_SALES_DETAIL_LOAD_FAIL = '판매 상세를 불러오지 못했습니다.'
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
  if (row.sales_source === SALES_SOURCE_AUCTION_RT) return '경매'
  if (String(row.order_no || '').trim()) return '주문출고'
  return '직접판매'
}

function salesRepProductText(
  row: Pick<
    SalesListItem,
    'rep_item_cd' | 'rep_variety_nm' | 'rep_size_nm' | 'rep_grade_nm' | 'rep_crop_nm'
  >,
): string {
  const juice = JUICE_ITEM_LABEL[String(row.rep_item_cd || '').trim()]
  if (juice) return juice
  const variety = row.rep_variety_nm || ''
  const size = row.rep_size_nm || ''
  const grade = row.rep_grade_nm || ''
  const crop = row.rep_crop_nm || ''
  return joinDot([variety, size, grade, crop].filter(Boolean))
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
    'item_cd' | 'variety_nm' | 'size_nm' | 'grade_nm' | 'crop_nm'
  >,
): string {
  const juice = JUICE_ITEM_LABEL[String(line.item_cd || '').trim()]
  if (juice) return juice
  return joinDot(
    [line.variety_nm, line.size_nm, line.grade_nm, line.crop_nm].filter(Boolean),
  )
}

/** FIFO raw rows → 논리 표시 line (order_detail_id NULL은 합치지 않음). */
export function groupSalesDetailLines(lines: SalesDetailLine[]): SalesDetailLine[] {
  const out: SalesDetailLine[] = []
  const grouped = new Map<string, SalesDetailLine>()
  const groupedOrder: string[] = []

  for (const line of lines) {
    const orderDetailId = String(line.order_detail_id || '').trim()
    if (!orderDetailId) {
      out.push({ ...line })
      continue
    }
    const key = [
      orderDetailId,
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
    groupedOrder.push(key)
  }

  for (const key of groupedOrder) {
    const row = grouped.get(key)
    if (row) out.push(row)
  }
  return out
}
