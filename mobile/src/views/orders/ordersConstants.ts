/** 판매관리 (단계 2: 주문. 포장/생산·재고·판매 Shell). */

export const TAB_PACK_PROD = 'pack_prod'
export const TAB_STOCK = 'stock'
export const TAB_ORDER = 'order'
export const TAB_SALES = 'sales'

/** 상단 4탭 — 업무영역 분류(강제 workflow 아님). 초기 선택은 TAB_ORDER. */
export const ORDER_SALES_SEGMENT_OPTIONS = [
  { value: TAB_PACK_PROD, label: '포장/생산' },
  { value: TAB_STOCK, label: '재고' },
  { value: TAB_ORDER, label: '주문' },
  { value: TAB_SALES, label: '판매' },
] as const

export const LABEL_PAGE_TITLE = '판매관리'
export const LABEL_SEGMENT_ARIA = '포장·생산, 재고, 주문, 판매'
export const LABEL_FAB_ORDER = '신규 주문'
export const LABEL_FAB_SALES = '직접 판매'
export const LABEL_SHIP = '출고'
export const MSG_STAGE_LATER = '다음 단계에서 구현합니다.'
export const MSG_ORDER_EMPTY_TITLE = '등록된 주문이 없습니다'
export const MSG_ORDER_EMPTY_DESC = '우측 하단 버튼으로 신규 주문을 등록하세요.'
export const MSG_ORDER_EMPTY_FILTER = '조건에 맞는 주문이 없습니다.'
export const MSG_ORDER_EMPTY_FILTER_DESC = '조회기간·상태·검색을 바꿔 다시 조회해 보세요.'
export const MSG_SALES_EMPTY_TITLE = '등록된 판매가 없습니다'
export const MSG_SALES_EMPTY_DESC = '확정된 판매는 출고 후 여기에 모입니다. 직접판매는 재고에서 시작하세요.'
export const MSG_PACK_PROD_EMPTY_TITLE = '포장/생산'
export const MSG_PACK_PROD_EMPTY_DESC = '포장 및 생산관리를 준비 중입니다.'
export const MSG_STOCK_EMPTY_TITLE = '재고'
export const MSG_STOCK_EMPTY_DESC = '원물·상품·배즙 재고를 준비 중입니다.'
export const MSG_ORDER_LOAD_FAIL = '주문 목록을 불러오지 못했습니다.'
export const LABEL_NEW_ORDER = '신규 주문'
export const LABEL_EDIT_ORDER = '주문 수정'
export const LABEL_EDIT = '수정'
export const LABEL_CANCEL_ORDER = '주문 취소'
export const LABEL_CLOSE = '닫기'
export const LABEL_CANCEL_EDIT = '취소'
export const LABEL_ORDER_DETAIL = '주문 상세'
export const LABEL_SAVE_ORDER = '주문 저장'
export const LABEL_BASIC_INFO = '주문 기본정보'
export const LABEL_LINE = '상품'
export const LABEL_REMOVE_LINE = '삭제'
export const LABEL_ADD_LINE = '+ 상품 추가'
export const LABEL_DELIVERY_INFO = '배송정보'
export const LABEL_TOTAL_LINES = '총'
export const LABEL_TOTAL_QTY = '총수량'
export const LABEL_TOTAL_AMT = '총금액'
export const LABEL_EXPAND_LINE = '상품 펼치기'
export const LABEL_COLLAPSE_LINE = '상품 접기'
export const LABEL_EXPAND_SHIP = '배송정보 펼치기'
export const LABEL_COLLAPSE_SHIP = '배송정보 접기'
export const LABEL_CUSTOMER = '고객'
export const LABEL_ORDER_DT = '주문일'
export const LABEL_PREPAY = '선입금액'
export const LABEL_RMK = '비고'
export const LABEL_VARIETY = '품종'
export const LABEL_WEIGHT = '중량'
export const LABEL_GRADE = '등급'
export const LABEL_SIZE = '크기'
export const LABEL_QTY = '수량'
export const LABEL_UNIT_PRICE = '단가'
export const LABEL_AMT = '금액'
export const LABEL_DELIVERY_TP = '배송유형'
export const LABEL_RCV_NAME = '수령인'
export const LABEL_RCV_TEL = '수령 연락처'
export const LABEL_RCV_ADDR = '수령 주소'
export const LABEL_DEST = '배송지'
export const LABEL_DEST_QTY = '배송수량'
export const LABEL_DLVRY_MSG = '배송메시지'
export const LABEL_ADD_DEST = '+ 배송지 추가'
export const LABEL_ALLOC = '배송 배정'
export const LABEL_UNASSIGNED = '미배정'
export const LABEL_OVER = '초과'
export const LABEL_DEST_COUNT_SUFFIX = '곳'
export const LABEL_EXPAND_DEST = '배송지 펼치기'
export const LABEL_COLLAPSE_DEST = '배송지 접기'
export const LABEL_NEW_CUSTOMER = '+ 신규 고객 등록'
export const LABEL_NEW_CUSTOMER_A11Y = '신규 고객 등록'
export const LABEL_NEW_CUSTOMER_PLUS = '+'
export const LABEL_CUSTOMER_NAME = '고객명'
export const LABEL_CUSTOMER_MOBILE = '연락처'
export const LABEL_CUSTOMER_ADDR1 = '주소'
export const LABEL_CUSTOMER_ADDR2 = '상세 주소'
export const LABEL_CUSTOMER_SAVE = '고객 저장'
export const LABEL_CUSTOMER_CANCEL = '닫기'
export const MSG_CUSTOMER_REQUIRED = '고객을 선택해 주십시오.'
export const MSG_LINE_REQUIRED = '상품을 한 줄 이상 입력해 주십시오.'
export const MSG_SAVE_FAIL = '주문을 저장하지 못했습니다.'
export const MSG_CUSTOMER_SAVE_FAIL = '고객을 저장하지 못했습니다.'
export const MSG_PARCEL_DEST_REQUIRED = '택배 배송지를 1건 이상 등록해 주십시오.'
export const MSG_PARCEL_DEST_QTY = '배송수량은 0보다 커야 합니다.'
export const MSG_PARCEL_DEST_INCOMPLETE =
  '택배 배송지의 수령인, 연락처, 주소를 입력해 주십시오.'
export const MSG_PARCEL_QTY_MISMATCH = '택배 배송수량 합계가 주문수량과 같아야 합니다.'
export const MSG_ORDER_LOCKED_DELIVERED = '배송완료된 주문은 수정할 수 없습니다.'
export const MSG_ORDER_LOCKED_CANCEL = '취소된 주문은 수정할 수 없습니다.'
export const MSG_ORDER_QTY_LOCKED = '주문확정 이후에는 상품/수량을 수정할 수 없습니다.'
export const MSG_ORDER_CONFIRMED_LIMITED =
  '주문확정 상태에서는 고객·비고·배송정보만 수정할 수 있습니다.'
export const MSG_ORDER_SHIP_ONLY = '배송준비 상태에서는 배송 정보만 수정할 수 있습니다.'
export const MSG_ORDER_CANCEL_CONFIRM = '이 주문을 취소하시겠습니까?'
export const MSG_ORDER_CANCEL_FORBIDDEN = '현재 상태에서는 주문을 취소할 수 없습니다.'
export const MSG_ORDER_CANCEL_FAIL = '주문을 취소하지 못했습니다.'

export const ORDER_STATUS_RESERVED = 'ST010100'
export const ORDER_STATUS_CONFIRMED = 'ST010200'
export const ORDER_STATUS_PREP = 'ST010300'
export const ORDER_STATUS_DELIVERED = 'ST010400'
export const ORDER_STATUS_CANCEL = 'ST010500'

export const LABEL_FILTER = '필터'
export const LABEL_LOOKUP_PERIOD = '조회기간'
export const LABEL_DATE_FROM = '시작일'
export const LABEL_DATE_TO = '종료일'
export const LABEL_QUICK_RANGE = '빠른조회'
export const LABEL_STATUS = '상태'
export const LABEL_STATUS_ALL = '전체'
export const LABEL_SEARCH = '검색'
export const LABEL_SEARCH_PLACEHOLDER = '고객명 또는 주문번호'
export const LABEL_RESET = '초기화'
export const LABEL_LOOKUP = '조회'
export const LABEL_DETAIL_LOOKUP = '상세조회'
export const LABEL_PAGE_PREV = '이전'
export const LABEL_PAGE_NEXT = '다음'

export const ORDER_LIST_PAGE_SIZE = 20
export const STATUS_FILTER_ALL = ''

export const QUICK_RANGE_1M = '1m'
export const QUICK_RANGE_3M = '3m'
export const QUICK_RANGE_YEAR = 'year'

export const ORDER_QUICK_RANGE_OPTIONS = [
  { value: QUICK_RANGE_1M, label: '1개월' },
  { value: QUICK_RANGE_3M, label: '3개월' },
  { value: QUICK_RANGE_YEAR, label: '올해' },
] as const

/** ST01 명칭 fallback — 화면에는 코드값 미노출 */
export const ORDER_STATUS_FILTER_FALLBACK = [
  { value: ORDER_STATUS_RESERVED, label: '예약접수' },
  { value: ORDER_STATUS_CONFIRMED, label: '주문확정' },
  { value: ORDER_STATUS_PREP, label: '배송준비' },
  { value: ORDER_STATUS_DELIVERED, label: '배송완료' },
  { value: ORDER_STATUS_CANCEL, label: '취소' },
] as const

export const CODE_PARENT_FRUIT = 'FR01'
export const CODE_PARENT_GRADE = 'GR01'
/** 중량 규격(5kg / 7.5kg / 15kg · 포). 크기(과이내)가 아님. */
export const CODE_PARENT_SPEC = 'SZ01'
export const CODE_PARENT_SIZE = 'FR020100'
export const CODE_PARENT_DELIVERY = 'LO01'
export const CODE_PARENT_STATUS = 'ST01'

export const PEAR_ITEM_CD = 'FR010100'
export const WEIGHT_UNIT_KG = 'kg'
export const WEIGHT_UNIT_PACK = '포'
export const DEFAULT_WEIGHT_KG = 15
export const ITEM_MID_SUFFIX = '00'

export const DELIVERY_TP_VISIT = 'LO010100'
export const DELIVERY_TP_PARCEL = 'LO010200'
export const DEFAULT_WAREHOUSE_CD = 'WH01'

const WEIGHT_NUM_RE = /(\d+(?:\.\d+)?)/

/** 소분류(품종): 8자리이며 끝이 00이 아님 */
export function isVarietyCode(codeCd: string): boolean {
  const c = String(codeCd || '').trim()
  return c.length === 8 && !c.endsWith('00')
}

export function itemCdFromVariety(varietyCd: string): string {
  const c = String(varietyCd || '').trim()
  return c.length >= 6 ? `${c.slice(0, 6)}${ITEM_MID_SUFFIX}` : ''
}

export function isPearVariety(varietyCd: string): boolean {
  return itemCdFromVariety(varietyCd) === PEAR_ITEM_CD
}

export function isWeightKgName(codeNm: string): boolean {
  return String(codeNm || '').toLowerCase().includes(WEIGHT_UNIT_KG)
}

export function isWeightPackName(codeNm: string): boolean {
  return String(codeNm || '').includes(WEIGHT_UNIT_PACK)
}

export function parseWeightFromCodeNm(codeNm: string): number {
  const m = String(codeNm || '').match(WEIGHT_NUM_RE)
  if (!m) return 0
  const n = Number(m[1])
  return Number.isFinite(n) ? n : 0
}

export function pickDefaultWeightCd(
  codes: { code_cd: string; code_nm: string }[],
): string {
  const hit = codes.find((c) => parseWeightFromCodeNm(c.code_nm) === DEFAULT_WEIGHT_KG)
  return hit?.code_cd || codes[0]?.code_cd || ''
}

export function formatOrderAmt(n: number): string {
  const v = Number.isFinite(n) ? Math.round(n) : 0
  return v.toLocaleString('ko-KR')
}

export function isParcelDelivery(codeCd: string): boolean {
  return String(codeCd || '').trim() === DELIVERY_TP_PARCEL
}

export function joinDot(parts: Array<string | null | undefined>): string {
  return parts.map((p) => String(p || '').trim()).filter(Boolean).join(' · ')
}

export function formatWeightLabel(weight: number): string {
  const n = Number(weight)
  if (!Number.isFinite(n) || n <= 0) return ''
  if (Number.isInteger(n)) return `${n}kg`
  return `${n}kg`
}

export function formatOrderLineSpec(line: {
  item_nm?: string
  variety_nm?: string
  variety_cd: string
  grade_nm?: string
  grade_cd: string
  size_nm?: string
  size_cd: string
  weight: number
}): string {
  return joinDot([
    line.item_nm,
    line.variety_nm || line.variety_cd,
    formatWeightLabel(line.weight),
    line.grade_nm || line.grade_cd,
    line.size_nm || line.size_cd,
  ])
}

export function formatOrderLineShip(line: {
  dlvry_tp: string
  dlvry_tp_nm?: string
  deliveries?: { qty?: number }[]
}): string {
  const tpNm = line.dlvry_tp_nm || line.dlvry_tp
  const n = line.deliveries?.length || 0
  if (isParcelDelivery(line.dlvry_tp)) {
    return joinDot([tpNm, `배송지 ${n}${LABEL_DEST_COUNT_SUFFIX}`])
  }
  return tpNm
}

export function canCancelOrder(statusCd: string): boolean {
  return statusCd === ORDER_STATUS_RESERVED || statusCd === ORDER_STATUS_CONFIRMED
}

export function isOrderEditLocked(statusCd: string): boolean {
  return statusCd === ORDER_STATUS_DELIVERED || statusCd === ORDER_STATUS_CANCEL
}

export function canEnterOrderEdit(statusCd: string): boolean {
  return (
    statusCd === ORDER_STATUS_RESERVED ||
    statusCd === ORDER_STATUS_CONFIRMED ||
    statusCd === ORDER_STATUS_PREP
  )
}

export function orderEditLockMessage(statusCd: string): string {
  if (statusCd === ORDER_STATUS_DELIVERED) return MSG_ORDER_LOCKED_DELIVERED
  if (statusCd === ORDER_STATUS_CANCEL) return MSG_ORDER_LOCKED_CANCEL
  return ''
}
