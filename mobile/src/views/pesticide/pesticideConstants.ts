/** SCR-020 농약 관리 UI 상수 */

export const MSG_STOCK_TITLE = '농약 관리'
export const MSG_LOW_EMPTY = '부족 품목이 없습니다.'
export const MSG_STOCK_EMPTY_FILTER = '조건에 맞는 농약이 없습니다.'
export const MSG_STOCK_LOADING = '재고 불러오는 중…'
export const MSG_USAGE_EMPTY = '아직 사용 이력이 없습니다.'
export const MSG_USAGE_LOADING = '사용 이력 불러오는 중…'
export const MSG_STOCK_LINK = '재고 보기'
export const MSG_COMING_SOON = '준비 중입니다.'
export const MSG_VIEW_ALL = '전체보기'

/** 스마트방제 브리핑 — 필수 안내 (자동 확정 아님, 관찰·판단 우선) */
export const MSG_SMART_SPRAY_TITLE = '스마트방제 안내'
export const MSG_SMART_SPRAY_CTA_HINT =
  '농약재고·병해충 사전은 버튼을 눌러 해당 화면에서 확인하세요.'
export const MSG_SMART_SPRAY_NO_OBS =
  '이 병해충과 연결된 관찰 기록이 없습니다.'
export const MSG_SMART_SPRAY_JUDGE_MARK = '중요'
export const MSG_SMART_SPRAY_JUDGE_NOTICE =
  '약제 살포를 위한 보조지표입니다. 세밀한 관찰 후 과수원에 맞는 약제 살포를 권고합니다.'
export const LABEL_SMART_SPRAY_LAST_USE = '관련 약제 최근 살포'
export const LABEL_SMART_SPRAY_QTY_UNIT = '병'

/** 발병여건 설정 — 영향항목(키) 한글 표시. 저장 키는 영문 유지 */
export const MSG_OUTBREAK_SETTINGS_TITLE = '발병여건 설정'
export const MSG_OUTBREAK_SETTINGS_NOTICE =
  '병해충을 고른 뒤 영향항목·기준값·비교를 한 화면에서 수정합니다. 월·기온 구간은 5~9 / 22~25 형식으로 등록합니다. 해당 월(시즌)이 있으면 시즌 밖에는 발병 점수가 0입니다. 개인 설정이 농장·시스템 기본보다 우선합니다.'
export const LABEL_OUTBREAK_SCOPE_MINE = '내 설정'
export const LABEL_OUTBREAK_SCOPE_FARM = '농장 기본'
export const LABEL_OUTBREAK_PEST = '병해충'
export const LABEL_OUTBREAK_PARAM_KEY = '영향항목'
export const LABEL_OUTBREAK_COMPARE = '비교'
export const LABEL_OUTBREAK_PARAM_VALUE = '기준값'
export const LABEL_OUTBREAK_EXAMPLE = '등록예시'
export const LABEL_OUTBREAK_SAVE_ALL = '일괄 저장'
export const LABEL_OUTBREAK_COMPARE_GTE = '이상'
export const LABEL_OUTBREAK_COMPARE_LTE = '이하'
export const LABEL_OUTBREAK_COMPARE_NA = '—'
export const LABEL_OUTBREAK_COMPARE_MATCH = '해당'
export const LABEL_OUTBREAK_SOURCE: Readonly<Record<string, string>> = {
  user: '내 설정',
  farm: '농장 기본',
  system: '시스템',
}
/** 기상 항목: 이상(≥) / 이하(≤) 선택·저장 */
export const OUTBREAK_COMPARE_PARAM_KEYS = [
  'rain_sum_7d',
  'rain_days_7d',
  'avg_humidity_7d',
  'avg_temp_3d',
] as const

export const OUTBREAK_PARAM_KEY_OPTIONS = [
  { key: 'min_score', label: '최소 발병점수', example: '5', compare: false },
  { key: 'efficacy_days', label: '약효(잔효) 일수', example: '7 · 10', compare: false },
  {
    key: 'rain_sum_7d',
    label: '7일 총강수(mm)',
    example: '40(이상) · 5(이하)',
    compare: true,
  },
  {
    key: 'rain_days_7d',
    label: '7일 강수일수',
    example: '3(이상)',
    compare: true,
  },
  {
    key: 'avg_humidity_7d',
    label: '7일 평균습도(%)',
    example: '75(이상) · 70(이하)',
    compare: true,
  },
  {
    key: 'avg_temp_3d',
    label: '3일 평균기온(℃)',
    example: '22~25 · 28(이상)',
    compare: true,
  },
  {
    key: 'current_month',
    label: '해당 월',
    example: '5 · 5~9 · 5,7,9',
    compare: false,
  },
] as const

export function outbreakParamKeyLabel(key: string): string {
  const found = OUTBREAK_PARAM_KEY_OPTIONS.find((x) => x.key === key)
  return found?.label || key
}

export function outbreakParamKeyExample(key: string): string {
  const found = OUTBREAK_PARAM_KEY_OPTIONS.find((x) => x.key === key)
  return found?.example || ''
}

export function outbreakCompareEnabled(key: string): boolean {
  return (OUTBREAK_COMPARE_PARAM_KEYS as readonly string[]).includes(key)
}

/** 기준값이 구간(22~25) 또는 목록이면 비교(이상/이하) 비활성 */
export function outbreakValueIsRangeOrSet(displayValue: string): boolean {
  const t = String(displayValue || '').trim()
  if (!t) return false
  if (/^\d+(?:\.\d+)?\s*[~\-–—]\s*\d+(?:\.\d+)?$/.test(t)) return true
  if (t.includes(',')) return true
  return false
}

export function outbreakRowCompareEnabled(
  key: string,
  displayValue: string,
  apiCompareEnabled?: boolean | null,
): boolean {
  if (apiCompareEnabled === false) return false
  if (!outbreakCompareEnabled(key)) return false
  if (outbreakValueIsRangeOrSet(displayValue)) return false
  return true
}

/** UI 기준값 + 비교 → 저장 문자열 (>=40, 5~9 등) */
export function formatOutbreakParamValueForStorage(
  paramKey: string,
  displayValue: string,
  compareOp?: string | null,
): string {
  const key = String(paramKey || '').trim()
  const disp = String(displayValue || '').trim()
  if (!disp) return ''
  if (key === 'current_month' || key === 'min_score' || key === 'efficacy_days') {
    return disp
  }
  if (outbreakValueIsRangeOrSet(disp)) {
    return disp.replace(/\s*[~\-–—]\s*/g, '~').replace(/\s*,\s*/g, ',')
  }
  if (outbreakCompareEnabled(key) && (compareOp === '>=' || compareOp === '<=')) {
    const body = disp.replace(/^(>=|<=|==)\s*/, '').trim() || disp
    return `${compareOp}${body}`
  }
  return disp
}

/** 로드 시 param_value에서 표시값·비교 op 분리 */
export function splitOutbreakParamValue(
  paramKey: string,
  raw: string,
  fallbackOp?: string | null,
): { display: string; op: string } {
  const key = String(paramKey || '').trim()
  const text = String(raw || '').trim()
  if (!outbreakCompareEnabled(key)) {
    return { display: text, op: key === 'current_month' ? 'match' : '' }
  }
  if (outbreakValueIsRangeOrSet(text.replace(/^(>=|<=|==)\s*/, ''))) {
    const body = text.replace(/^(>=|<=|==)\s*/, '').trim()
    return { display: body, op: 'match' }
  }
  const m = /^(>=|<=|==)\s*(.+)$/.exec(text)
  if (m) {
    return { display: m[2].trim(), op: m[1] === '==' ? '>=' : m[1] }
  }
  if (fallbackOp === 'match' || fallbackOp === 'in_range' || fallbackOp === 'in_set') {
    return { display: text, op: 'match' }
  }
  const op =
    fallbackOp === '<=' || fallbackOp === '>=' ? fallbackOp : '>='
  return { display: text, op }
}

export const MSG_PESTICIDE_DICT_TITLE = '농약 사전'
export const MSG_PESTICIDE_DICT_SEARCH = '농약명·대상병해충·성분 검색'
export const MSG_PESTICIDE_DICT_EMPTY = '검색 결과가 없습니다.'
export const MSG_PESTICIDE_DICT_LOAD_FAIL = '사전을 불러오지 못했습니다.'
export const MSG_PESTICIDE_DICT_DETAIL_FAIL = '상세를 불러오지 못했습니다.'

export const PLACEHOLDER_SEARCH = '품목명·성분·대상병해충 검색'
export const PLACEHOLDER_PURPOSE = '예: 깍지벌레'
export const PLACEHOLDER_DASH = '—'

/** UI 미리보기용 샘플 (API 연동 전) */
export const DEMO_LAST_SPRAY_DT = '2026-07-18'
export const DEMO_NEXT_SPRAY_DT = '2026-07-25'

export type DemoCategoryShare = {
  key: string
  label: string
  tone: string
  /** 품목 종류 수 (qty>0) */
  kinds: number
  qty: number
  pct: number
}

/** 분류별 도넛 색 (실데이터 집계용) */
export const CATEGORY_TONE_BY_LABEL: Record<string, string> = {
  살균제: 'var(--ods-color-primary)',
  살충제: 'var(--ods-color-secondary)',
  제초제: 'color-mix(in srgb, var(--ods-color-primary) 45%, white)',
  영양제: 'var(--ods-color-caution)',
  기타제: 'var(--ods-color-gray-500)',
}

export const CATEGORY_TONE_FALLBACK = 'var(--ods-color-gray-500)'

export const CATEGORY_ORDER = [
  '살충제',
  '살균제',
  '영양제',
  '제초제',
  '기타제',
] as const

export const DEMO_CATEGORY_SHARES: readonly DemoCategoryShare[] = [
  { key: 'fung', label: '살균제', tone: 'var(--ods-color-primary)', kinds: 18, qty: 235, pct: 41 },
  { key: 'ins', label: '살충제', tone: 'var(--ods-color-secondary)', kinds: 12, qty: 148, pct: 26 },
  { key: 'herb', label: '제초제', tone: 'color-mix(in srgb, var(--ods-color-primary) 45%, white)', kinds: 6, qty: 97, pct: 17 },
  { key: 'nut', label: '영양제', tone: 'var(--ods-color-caution)', kinds: 9, qty: 88, pct: 16 },
] as const

export const DEMO_TOTAL_PIECE = DEMO_CATEGORY_SHARES.reduce((s, r) => s + r.qty, 0)

export const LABEL_UNIT_DEFAULT = '개'
export const RECENT_USAGE_DAYS = 30
export const RECENT_USAGE_MAX_DAYS = 10

export type DemoUsageLine = {
  item_nm: string
  qty: number
  unit: string
}

export type DemoUsageRow = {
  use_dt: string
  lines: readonly DemoUsageLine[]
}

export const DEMO_RECENT_USAGE: readonly DemoUsageRow[] = [
  {
    use_dt: '2026-07-18',
    lines: [
      { item_nm: '노블레스', qty: 15, unit: '병' },
      { item_nm: '다이센엠45', qty: 10, unit: '봉지' },
    ],
  },
  {
    use_dt: '2026-07-15',
    lines: [{ item_nm: '이미다클로프리드', qty: 3, unit: '병' }],
  },
  {
    use_dt: '2026-07-10',
    lines: [
      { item_nm: '요소 엽면시비', qty: 2, unit: '포' },
      { item_nm: '칼슘제', qty: 1, unit: '병' },
    ],
  },
  {
    use_dt: '2026-07-05',
    lines: [{ item_nm: '보스칼리드', qty: 4, unit: '봉지' }],
  },
  {
    use_dt: '2026-06-28',
    lines: [{ item_nm: '글리포세이트', qty: 2, unit: '병' }],
  },
] as const

export const LABEL_PIECE = '낱개'
export const LABEL_LOW = '부족'
/** 재고 목록 표시: 이 수량 미만이면 농약명 붉은색 */
export const STOCK_QTY_WARN_BELOW = 10
export const LABEL_STOCK_SECTION = '재고'
export const LABEL_USAGE_SECTION = '사용 이력'
export const LABEL_THRESHOLD = '부족 기준'
export const LABEL_THRESHOLD_ITEM = '품목 설정'
export const LABEL_THRESHOLD_DEFAULT = '기본값'
export const LABEL_STANDALONE_USE = '단독 사용'

/** Hero 카피 */
export const HERO_GREETING_LINE1 = '방제 준비부터'
export const HERO_GREETING_LINE2_PREFIX = '재고 관리까지 '
export const HERO_GREETING_HIGHLIGHT = '한 손으로!'
export const HERO_SUBCOPY =
  '필요한 농약을 확인하고 사용 이력과 재고를 한 번에 관리하세요.'

/** @deprecated 조합용 — 하이라이트 분리 사용 */
export const HERO_GREETING_LINE2 = `${HERO_GREETING_LINE2_PREFIX}${HERO_GREETING_HIGHLIGHT}`

export const LABEL_KPI_TOTAL = '재고 품목'
export const LABEL_KPI_LOW = '부족 품목'
export const LABEL_KPI_LAST_SPRAY = '최근 방제일'
export const LABEL_KPI_NEXT_SPRAY = '방제 예정일'
export const LABEL_KPI_OK = '정상'

export const SECTION_STOCK_STATUS = '재고 현황'
export const SECTION_HOLDINGS = '보유 현황'
export const SECTION_RECENT_USAGE = '최근 사용 내역 (최근 30일)'

export const MSG_HOLDINGS_EMPTY = '해당 분류에 등록된 품목이 없습니다.'
export const MSG_HOLDINGS_DEMO_TAP =
  '미리보기 품목입니다. PC에 등록된 품목을 불러오면 상세로 이동합니다.'

export type HoldingsCategoryKey = 'insect' | 'fungus' | 'nutrient' | 'other'

export type HoldingsCategoryDef = {
  key: HoldingsCategoryKey
  label: string
  /** 그룹 헤더 강조색 */
  tone: string
  /** 기본 펼침 */
  defaultOpen: boolean
}

/** 보유 현황 아코디언 순서 · 살충제만 기본 펼침 */
export const HOLDINGS_CATEGORIES: readonly HoldingsCategoryDef[] = [
  { key: 'insect', label: '살충제', tone: 'var(--ods-color-danger)', defaultOpen: true },
  { key: 'fungus', label: '살균제', tone: 'var(--ods-color-ai)', defaultOpen: false },
  { key: 'nutrient', label: '영양제', tone: 'var(--ods-color-caution)', defaultOpen: false },
  { key: 'other', label: '기타제', tone: 'var(--ods-color-gray-700)', defaultOpen: false },
] as const

export type DemoHoldingItem = {
  item_id: number
  item_nm: string
  pest_target_nm: string
  ingredient_nm: string
  qty_piece: number
}

export const DEMO_HOLDINGS: Record<HoldingsCategoryKey, readonly DemoHoldingItem[]> = {
  insect: [
    {
      item_id: 101,
      item_nm: '이미다클로프리드',
      pest_target_nm: '진딧물, 깍지벌레',
      ingredient_nm: '이미다클로프리드 10%',
      qty_piece: 12,
    },
    {
      item_id: 102,
      item_nm: '아세타미프리드',
      pest_target_nm: '진딧물',
      ingredient_nm: '아세타미프리드 8%',
      qty_piece: 5,
    },
    {
      item_id: 103,
      item_nm: '비펜트린',
      pest_target_nm: '응애',
      ingredient_nm: '비펜트린 2%',
      qty_piece: 2,
    },
    {
      item_id: 104,
      item_nm: '에토펜프록스',
      pest_target_nm: '나방류',
      ingredient_nm: '에토펜프록스 10%',
      qty_piece: 8,
    },
  ],
  fungus: [
    {
      item_id: 201,
      item_nm: '디노캡 유제',
      pest_target_nm: '흰가루병',
      ingredient_nm: '디노캡 35%',
      qty_piece: 6,
    },
    {
      item_id: 202,
      item_nm: '보스칼리드',
      pest_target_nm: '잿빛곰팡이병',
      ingredient_nm: '보스칼리드',
      qty_piece: 4,
    },
    {
      item_id: 203,
      item_nm: '테부코나졸',
      pest_target_nm: '검은별무늬병',
      ingredient_nm: '테부코나졸 25%',
      qty_piece: 1,
    },
  ],
  nutrient: [
    {
      item_id: 301,
      item_nm: '요소 엽면시비',
      pest_target_nm: '—',
      ingredient_nm: '요소 46%',
      qty_piece: 20,
    },
    {
      item_id: 302,
      item_nm: '칼슘제',
      pest_target_nm: '—',
      ingredient_nm: '칼슘',
      qty_piece: 9,
    },
  ],
  other: [
    {
      item_id: 401,
      item_nm: '전착제 A',
      pest_target_nm: '—',
      ingredient_nm: '전착제',
      qty_piece: 7,
    },
    {
      item_id: 402,
      item_nm: '글리포세이트',
      pest_target_nm: '잡초',
      ingredient_nm: '글리포세이트 41%',
      qty_piece: 3,
    },
  ],
}


export const COL_RANK = '순위'
export const COL_ITEM_NM = '농약명'
export const COL_PEST_TARGET = '대상병해충'
export const COL_INGREDIENT = '성분'
export const COL_STOCK = '재고'
export const COL_QTY = '현재고'
export const COL_DATE = '날짜'
export const COL_USED = '사용 농약'

/** 입고 화면 라벨 */
export const LABEL_RECEIPT_TITLE = '입고 등록'
export const LABEL_RECEIPT_NEW_TITLE = '입고 신규'
export const LABEL_RECEIPT_DETAIL_TITLE = '입고 상세'
export const LABEL_RECEIPT_NEW_BTN = '신규'
export const LABEL_RECEIPT_SUPPLIER_FALLBACK = '공급자 미지정'
export const LABEL_RECEIPT_APPLIED = '반영'
export const LABEL_RECEIPT_PENDING = '미반영'
export const LABEL_RECEIPT_APPLIED_BANNER =
  '재고에 반영된 입고입니다. 저장 시 수량·품목이 다시 맞춰집니다.'
export const LABEL_RECEIPT_EMPTY = '입고 내역이 없습니다.'
export const LABEL_RECEIPT_ITEMS = '입고 품목'
export const LABEL_RECEIPT_ITEM_ADD = '품목 추가'
export const LABEL_RECEIPT_ITEM_REMOVE = '품목 삭제'
export const LABEL_RECEIPT_LINK_STOCK = '기존 재고 선택'
export const LABEL_RECEIPT_LINK_STOCK_EMPTY = '선택 안 함 (직접 입력)'
export const LABEL_RECEIPT_SUPPLIER = '공급자'
export const LABEL_RECEIPT_SUPPLIER_DIRECT = '직접 입력'
export const LABEL_RECEIPT_SUPPLIER_NM = '공급자명'
export const LABEL_RECEIPT_ITEM_NM = '품목명'
export const LABEL_RECEIPT_SPEC_LABEL = '규격(용량)'
export const LABEL_RECEIPT_DICT_PICK = '사전에서 찾기'
export const LABEL_RECEIPT_DICT_LINKED = '사전 연결됨'
export const LABEL_RECEIPT_DICT_CLEAR = '연결 해제'
export const LABEL_RECEIPT_DICT_SEARCH = '농약명·상표·성분·병해충 검색'
export const LABEL_RECEIPT_DICT_EMPTY = '검색 결과가 없습니다.'
export const LABEL_RECEIPT_DICT_APPLY = '선택 적용'
export const LABEL_RECEIPT_DICT_LOAD_FAIL = '사전을 불러오지 못했습니다.'
export const MSG_RECEIPT_SAVE_FAIL = '저장하지 못했습니다.'
export const MSG_RECEIPT_LINE_REQUIRED = '품목명과 수량(1 이상)을 입력해 주세요.'
export const LABEL_RECEIPT_SAVE = '저장'
export const LABEL_RECEIPT_ITEM_COUNT = '품목'

export const LABEL_STOCK_HIST_TITLE = '재고·입고 변동 이력'
export const LABEL_HIST_IN = '입고'
export const LABEL_HIST_USE = '사용'
export const LABEL_HIST_ADJ = '조정'
export const LABEL_HIST_OUT = '출고(판매)'
export const LABEL_HIST_CANCEL = '취소'

export const HIST_TYPE_LABEL: Readonly<Record<string, string>> = {
  IN: LABEL_HIST_IN,
  USE: LABEL_HIST_USE,
  ADJ: LABEL_HIST_ADJ,
  OUT: LABEL_HIST_OUT,
  CANCEL: LABEL_HIST_CANCEL,
}

export const LABEL_STOCK_OUT = '출고(판매)'
export const LABEL_STOCK_OUT_BUYER = '구매처'
export const LABEL_STOCK_OUT_QTY = '출고 수량'
export const LABEL_STOCK_OUT_RMK = '비고'
export const MSG_STOCK_OUT_CONFIRM = '출고(판매)를 반영할까요? 재고가 차감됩니다.'

/** 살충제/살균제/영양제/기타제 키 매핑 */
export function holdingsCategoryKeyOf(
  raw: string | null | undefined,
): HoldingsCategoryKey {
  const s = String(raw || '').trim()
  if (s === '살충제') return 'insect'
  if (s === '살균제') return 'fungus'
  if (s === '영양제') return 'nutrient'
  return 'other'
}

export type PesticideQuickActionKey =
  | 'stock'
  | 'stats'
  | 'dict'
  | 'pest-dict'
  | 'receipt'
  | 'low'

export type PesticideQuickAction = {
  key: PesticideQuickActionKey
  label: string
  ready: boolean
}

/** 빠른메뉴 — 재고관리 옆 입고등록 · 농약사전 옆 병해충사전 */
export const PESTICIDE_QUICK_ACTIONS: readonly PesticideQuickAction[] = [
  { key: 'stock', label: '재고 관리', ready: true },
  { key: 'receipt', label: '입고 등록', ready: true },
  { key: 'stats', label: '사용 통계', ready: true },
  { key: 'dict', label: '농약 사전', ready: true },
  { key: 'pest-dict', label: '병해충 사전', ready: true },
  { key: 'low', label: '부족 확인', ready: true },
] as const

const PURPOSE_STORAGE_PREFIX = 'orchard.pesticide.recentPurpose.'

export function formatStockSummary(total: number, low: number): string {
  if (low > 0) return `보유 ${total}종 · 부족 ${low}종`
  return `보유 ${total}종`
}

export function formatQtyPiece(qty: number): string {
  return `${LABEL_PIECE} ${qty}`
}

/** 재고 현황 목록용 — 숫자만 */
export function formatStockQty(qty: number): string {
  return String(Math.max(0, Math.trunc(qty)))
}

/** 재고 수량 경고색 (STOCK_QTY_WARN_BELOW 미만) */
export function isStockQtyWarn(qty: number): boolean {
  return Math.trunc(qty) < STOCK_QTY_WARN_BELOW
}

/** 일자별 사용 농약: `노블레스 15병 , 다이센엠45 10봉지` */
export function formatUsageLines(
  lines: readonly { item_nm: string; qty: number; unit: string }[],
): string {
  return lines
    .map((ln) => {
      const nm = String(ln.item_nm || '').trim() || PLACEHOLDER_DASH
      const qty = Math.max(0, Math.trunc(ln.qty || 0))
      const unit = String(ln.unit || '').trim() || LABEL_UNIT_DEFAULT
      return `${nm} ${qty}${unit}`
    })
    .join(' , ')
}

/** 재고 품목 → 분류별 수량 비중 (qty>0만) */
export function buildCategoryShares(
  items: readonly {
    pest_category_nm: string | null
    qty_piece: number
  }[],
): DemoCategoryShare[] {
  const qtyByLabel = new Map<string, number>()
  const kindsByLabel = new Map<string, number>()
  for (const it of items) {
    const qty = Math.max(0, Math.trunc(it.qty_piece || 0))
    if (qty <= 0) continue
    const raw = String(it.pest_category_nm || '').trim()
    const label =
      raw === '살충제' ||
      raw === '살균제' ||
      raw === '영양제' ||
      raw === '제초제'
        ? raw
        : '기타제'
    qtyByLabel.set(label, (qtyByLabel.get(label) || 0) + qty)
    kindsByLabel.set(label, (kindsByLabel.get(label) || 0) + 1)
  }
  const total = [...qtyByLabel.values()].reduce((s, n) => s + n, 0)
  if (total <= 0) return []

  const labels = [
    ...CATEGORY_ORDER.filter((lb) => qtyByLabel.has(lb)),
    ...[...qtyByLabel.keys()].filter(
      (lb) => !(CATEGORY_ORDER as readonly string[]).includes(lb),
    ),
  ]
  return labels.map((label) => {
    const qty = qtyByLabel.get(label) || 0
    return {
      key: label,
      label,
      tone: CATEGORY_TONE_BY_LABEL[label] || CATEGORY_TONE_FALLBACK,
      kinds: kindsByLabel.get(label) || 0,
      qty,
      pct: Math.round((qty / total) * 100),
    }
  })
}

export function formatThreshold(threshold: number, source: 'item' | 'default'): string {
  const src = source === 'item' ? LABEL_THRESHOLD_ITEM : LABEL_THRESHOLD_DEFAULT
  return `${threshold} 이하 (${src})`
}

/** work_id YYYYMMDD-NN → 라우트 workDt YYYY-MM-DD */
export function workIdToRouteDate(workId: string): string {
  const raw = String(workId || '').trim()
  const d = raw.slice(0, 8)
  if (d.length !== 8 || !/^\d{8}$/.test(d)) return ''
  return `${d.slice(0, 4)}-${d.slice(4, 6)}-${d.slice(6, 8)}`
}

export function loadRecentPurposes(farmCd: string): string[] {
  try {
    const raw = localStorage.getItem(`${PURPOSE_STORAGE_PREFIX}${farmCd}`)
    if (!raw) return []
    const parsed = JSON.parse(raw) as unknown
    if (!Array.isArray(parsed)) return []
    return parsed
      .map((v) => String(v || '').trim())
      .filter(Boolean)
      .slice(0, 8)
  } catch {
    return []
  }
}

export function rememberRecentPurpose(farmCd: string, purpose: string): void {
  const p = String(purpose || '').trim()
  if (!p || !farmCd) return
  const prev = loadRecentPurposes(farmCd).filter((x) => x !== p)
  const next = [p, ...prev].slice(0, 8)
  try {
    localStorage.setItem(
      `${PURPOSE_STORAGE_PREFIX}${farmCd}`,
      JSON.stringify(next),
    )
  } catch {
    /* ignore quota */
  }
}
