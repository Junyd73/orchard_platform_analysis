/** 포장/생산 Stage P — UI 상수 (코드값 미노출). */

export const PROD_TYPE_PACK = 'PACK'
export const PROD_TYPE_PROCESS = 'PROCESS'

export const INPUT_HARVEST = 'HARVEST'
export const INPUT_RAW_STOCK = 'RAW_STOCK'

export const PROD_TYPE_OPTIONS = [
  { value: PROD_TYPE_PACK, label: '배 포장' },
  { value: PROD_TYPE_PROCESS, label: '배즙 생산' },
] as const

export const INPUT_SOURCE_PACK_OPTIONS = [
  { value: INPUT_HARVEST, label: '수확 직후' },
  { value: INPUT_RAW_STOCK, label: '저장 원물' },
] as const

export const INPUT_SOURCE_PROCESS_OPTIONS = [
  { value: INPUT_RAW_STOCK, label: '저장 원물' },
] as const

export const LABEL_PROD_TYPE = '생산구분'
export const LABEL_INPUT_SOURCE = '원료'
export const LABEL_HARVEST_RECORD = '수확기록'
export const LABEL_RAW_STOCK = '원물 재고'
export const LABEL_VARIETY = '품종'
export const LABEL_WEIGHT = '포장중량'
export const LABEL_PRODUCTION = '생산결과'
export const LABEL_JUICE_KIND = '배즙 종류'
export const LABEL_JUICE_BOXES = '배즙 박스 수'
export const ITEM_JUICE_PLAIN = 'FR010202'
export const ITEM_JUICE_DORAJI = 'FR010201'
export const JUICE_KIND_OPTIONS = [
  { value: ITEM_JUICE_PLAIN, label: '일반배즙' },
  { value: ITEM_JUICE_DORAJI, label: '도라지배즙' },
] as const
export const LABEL_CONFIRM = '생산확정'
export const LABEL_SAVE_STOCK = '재고로 저장'
export const LABEL_GO_SALES = '바로 판매'
export const LABEL_HARVEST_DT = '수확일'
export const LABEL_HARVEST_BOXES = '수확 상자 수'
export const LABEL_GRADE = '등급'
export const LABEL_SIZE = '과수(규격)'
export const LABEL_QTY = '박스'
export const LABEL_BOX_UNIT = '상자'
export const LABEL_ADD_WEIGHT = '+ 포장중량 추가'
export const LABEL_ADD_SIZE = '+'
export const LABEL_TOTAL_BOXES = '총'
export const LABEL_DELETE = '삭제'

export const MSG_CONFIRM_OK = '생산이 확정되었습니다.'
export const MSG_CONFIRM_FAIL = '생산확정에 실패했습니다.'
export const MSG_HARVEST_LOAD_FAIL = '수확 기록을 불러오지 못했습니다.'
export const MSG_HARVEST_EMPTY = '최근 수확 기록이 없습니다.'
export const MSG_RAW_LOAD_FAIL = '원물 재고를 불러오지 못했습니다.'
export const MSG_SELECT_HARVEST = '수확 기록을 선택해 주세요.'
export const MSG_SELECT_RAW = '원물 재고를 선택해 주세요.'
export const MSG_MIXED_YEAR = '수확연도가 다른 원물은 한 생산에 함께 넣을 수 없습니다.'
export const MSG_MIXED_VARIETY = '품종이 다른 원물은 한 생산에 함께 넣을 수 없습니다.'
export const MSG_ENTER_QTY = '생산 수량을 입력해 주세요.'
export const MSG_ENTER_JUICE = '배즙 박스 수를 입력해 주세요.'
export const MSG_ADD_WEIGHT = '포장중량을 하나 이상 추가해 주세요.'
export const MSG_ADD_SIZE = '각 포장중량에 과수를 하나 이상 추가해 주세요.'
export const MSG_DELETE_WEIGHT_CONFIRM = '입력한 수량이 있습니다. 삭제하시겠습니까?'
export const MSG_DELETE_SIZE_CONFIRM = '입력한 수량이 있습니다. 삭제하시겠습니까?'

export const CODE_PARENT_VARIETY = 'FR010100'
export const CODE_PARENT_GRADE = 'GR01'
export const CODE_PARENT_SIZE = 'FR020100'
export const CODE_PARENT_WEIGHT = 'SZ01'

export const DEFAULT_WH_CD = 'WH01'
export const DEFAULT_WEIGHT_KG = 15
