/** 주문/판매 셸 (단계 1). 목록·등록은 단계 2·5. */

export const TAB_ORDER = 'order'
export const TAB_SALES = 'sales'

export const ORDER_SALES_SEGMENT_OPTIONS = [
  { value: TAB_ORDER, label: '주문' },
  { value: TAB_SALES, label: '판매' },
] as const

export const LABEL_PAGE_TITLE = '주문/판매'
export const LABEL_SEGMENT_ARIA = '주문 또는 판매'
export const LABEL_FAB_ORDER = '신규 주문'
export const LABEL_FAB_SALES = '직접 판매'
export const MSG_STAGE_LATER = '다음 단계에서 구현합니다.'
export const MSG_ORDER_EMPTY_TITLE = '등록된 주문이 없습니다'
export const MSG_ORDER_EMPTY_DESC = '주문 조회·등록은 단계 2에서 구현합니다.'
export const MSG_SALES_EMPTY_TITLE = '등록된 판매가 없습니다'
export const MSG_SALES_EMPTY_DESC = '판매 목록·직접판매는 단계 5에서 구현합니다.'
