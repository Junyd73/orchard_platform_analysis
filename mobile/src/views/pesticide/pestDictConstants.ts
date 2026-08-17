/** 임시 병해충사전(10종) — 스마트방제 PEST_RULES와 이름·min_score·efficacy_days 동기화 유지.
 *  발병여건 병해충 콤보는 PEST_DICT_NAMES 사용. 불일치 시 test_pest_dict_seed_matches_pest_rules 실패.
 */

import { todayBizParts } from '@/shared/bizDate'

export type PestDictKind = 'disease' | 'pest'

export type PestDictRuleLine = {
  /** 화면 표시용 조건 요약 */
  summary: string
  score: number
}

export type PestDictGenerationWindow = {
  id: string
  label: string
  /** 포함 시작 월(1~12) */
  month_from: number
  /** 포함 종료 월(1~12) */
  month_to: number
}

export type PestDictEntry = {
  id: string
  pest_nm: string
  kind: PestDictKind
  kind_label: string
  /** 잔효 추천(기본) 일수 — PHI와 별개 */
  efficacy_days: number
  min_score: number
  /** 예: 봉지 후 안내 제외 */
  exclude_notes: string[]
  /** 발병·발생 여건(기상 점수 규칙) */
  outbreak_rules: PestDictRuleLine[]
  /** 발병·발생 시기(월·생육 단계) */
  season_period: string
  /** 세대별(또는 감염 차수별) 발병·발생 시기 */
  generation_periods: string[]
  /** 구조화 세대 창(채점 미연동, 안내·하이라이트) */
  generation_windows?: readonly PestDictGenerationWindow[]
  /** 발병 시 피해 */
  damage: string
  /** 관련 약제 후보(표시명) */
  candidate_pesticides: string[]
  /** 한 줄 요약 */
  summary: string
}

export const MSG_PEST_DICT_TITLE = '병해충 사전'
export const MSG_PEST_DICT_SUB =
  '임시 사전입니다. 잔효·발병여건은 참고값이며, 농장 관찰 후 살포를 판단하세요.'
export const MSG_PEST_DICT_SEARCH = '병해충명 검색'
export const MSG_PEST_DICT_EMPTY = '검색 결과가 없습니다.'
export const MSG_PEST_DICT_EFFICACY_NOTE =
  '잔효는 재방제 참고 일수입니다. 수확 전 안전사용기간(PHI)과 다릅니다.'
export const MSG_PEST_DICT_JUDGE =
  '기상여건/약효지속기간만으로 살포를 결정하지 마세요. 농장 관찰 상황을 확인한 뒤 필요 시에만 살포하세요.'

export const TEMP_PEST_DICT: readonly PestDictEntry[] = [
  {
    id: 'scab',
    pest_nm: '검은별무늬병',
    kind: 'disease',
    kind_label: '병해',
    efficacy_days: 10,
    min_score: 5,
    exclude_notes: ['봉지 작업 완료 후 스마트방제 안내에서 제외'],
    outbreak_rules: [
      { summary: '발생 적기 4~7월', score: 2 },
      { summary: '최근 7일 강수량 ≥ 40mm', score: 3 },
      { summary: '최근 7일 강우일수 ≥ 3일', score: 2 },
      { summary: '평균 습도 ≥ 75%', score: 2 },
      { summary: '강수량 ≥ 60mm', score: 5 },
      { summary: '습도 ≥ 85%', score: 3 },
    ],
    season_period:
      '개화기~봉지 전(대략 4~7월)이 핵심. 강우·다습 시 연중 반복 감염 가능.',
    generation_periods: [
      '1차(개화~낙화): 꽃·유과 감염 — 가장 중요한 방제 구간',
      '2차(유과~봉지 전): 강우마다 반복 감염, 7~14일 간격 참고',
      '3차(봉지 후~생육기): 잎·가지 위주, 과실 피해는 상대적으로 감소',
      '월동기: 가지 병반·낙엽에서 월동 후 이듬해 1차 전염원',
    ],
    damage:
      '잎·가지·과실에 검은 반점·그을음 병반. 심하면 기형과·열과, 가지 고사로 수량·품질 저하.',
    candidate_pesticides: ['다코닐', '델란', '카브리오'],
    summary: '강우·다습 시 주의. 봉지 전 집중 관리.',
  },
  {
    id: 'mite',
    pest_nm: '응애',
    kind: 'pest',
    kind_label: '해충',
    efficacy_days: 7,
    min_score: 4,
    exclude_notes: [],
    outbreak_rules: [
      { summary: '발생 적기 6~9월', score: 2 },
      { summary: '최근 평균기온 높음 (≥28℃)', score: 3 },
      { summary: '최근 7일 강수량 ≤ 5mm', score: 3 },
      { summary: '최근 평균기온 높음 (≥30℃)', score: 5 },
    ],
    season_period: '초여름~가을(대략 6~9월). 고온·건조기에 밀도 급증.',
    generation_periods: [
      '봄세대: 월동 후 밀도 형성(발생 초기 예찰)',
      '여름세대: 고온·건조 시 세대 간격 짧아져 급증(6~8월 주의)',
      '가을세대: 후기 밀도·월동 대비, 낙엽 전 관리',
      '※ 종·기온에 따라 연중 다세대 — 한잎당 2~3마리 수준에서 조기 방제',
    ],
    damage:
      '잎 뒷면 흡즙으로 황화·낙엽. 광합 저하·과실 비대 불량, 심하면 나무 세력 약화.',
    candidate_pesticides: ['아바멕틴', '스피로메시펜'],
    summary: '고온·건조 시 밀도 급증. 발생 초기 예찰.',
  },
  {
    id: 'scale',
    pest_nm: '깍지벌레',
    kind: 'pest',
    kind_label: '해충',
    efficacy_days: 14,
    min_score: 4,
    exclude_notes: [],
    outbreak_rules: [
      { summary: '발생 적기 4~8월', score: 2 },
      { summary: '최근 평균기온 ≥ 25℃', score: 2 },
      { summary: '평균 습도 ≥ 70%', score: 2 },
    ],
    season_period:
      '1세대 약충(신고 만개 후 약 2주, 보통 4월 중하순)이 1차 적기. 이후 세대는 6~8월.',
    generation_periods: [
      '1세대 약충: 만개 후 10~15일(보통 4월 중하순) — 가장 효과적인 방제 적기',
      '1세대 보완: 피해 심한 과원은 1차 방제 약 1주 후 2차',
      '2세대 약충: 봉지 씌우기 전후(대략 6월) — 봉지 침입 예방',
      '3세대 약충: 8월 중하순 — 조생종 수확과 겹쳐 방제 어려움, 1~2세대 철저 관리가 중요',
    ],
    damage:
      '가지·과실 흡즙. 감로로 그을음병 유발, 봉지 안 침입 시 상품과 피해. 세력 약화.',
    candidate_pesticides: ['부프로페진', '이미다클로프리드'],
    summary: '약충기 방제가 중요. 1세대 시기에 집중.',
  },
  {
    id: 'spotted-lanternfly',
    pest_nm: '미국선녀벌레',
    kind: 'pest',
    kind_label: '해충',
    efficacy_days: 10,
    min_score: 4,
    exclude_notes: [],
    outbreak_rules: [
      { summary: '발생 적기 5~9월', score: 2 },
      { summary: '최근 기온 상승 (22~25℃)', score: 1 },
      { summary: '최근 기온 상승 (≥25℃)', score: 1 },
    ],
    season_period:
      '약충 5월 중~7월 초, 성충 7월 하~9월 초. 연 1세대.',
    generation_periods: [
      '월동알: 가지 틈에서 월동',
      '약충 1차: 5월 중순~6월 초순',
      '약충 2차: 6월 중순~7월 초순',
      '성충 1차: 7월 하순~8월 중순',
      '성충 2차: 8월 하순~9월 초순 (산란·확산)',
    ],
    /** 채점 미연동 — 사전 안내·현재 세대 하이라이트용 */
    generation_windows: [
      { id: 'nymph1', label: '약충 1차', month_from: 5, month_to: 6 },
      { id: 'nymph2', label: '약충 2차', month_from: 6, month_to: 7 },
      { id: 'adult1', label: '성충 1차', month_from: 7, month_to: 8 },
      { id: 'adult2', label: '성충 2차', month_from: 8, month_to: 9 },
    ],
    damage:
      '흡즙으로 생육 부진. 흰색 분비물·감로로 그을음병, 잎·가지·과실 오염.',
    candidate_pesticides: ['아세타미프리드', '에토펜프록스', '델타메트린'],
    summary: '약충·성충 시기별 1·2차 방제 참고.',
  },
  {
    id: 'psylla',
    pest_nm: '배나무이',
    kind: 'pest',
    kind_label: '해충',
    efficacy_days: 10,
    min_score: 4,
    exclude_notes: [],
    outbreak_rules: [
      { summary: '발생 적기 4~9월', score: 1 },
      { summary: '평균기온 ≥ 15℃ (활동 시작)', score: 2 },
      { summary: '평균기온 ≥ 20℃ (활동 증가)', score: 4 },
    ],
    season_period: '봄(4월~)부터 활동. 기온 상승과 함께 밀도 증가.',
    generation_periods: [
      '월동세대: 성충·약충이 눈·가지에서 월동',
      '1세대: 봄(4월~, 기온 15℃ 전후) 활동 시작 — 초기 밀도 관리',
      '2세대 이후: 기온 20℃ 이상에서 증식 가속(5~7월)',
      '여름~가을: 다세대 반복, 감로·그을음 병반과 동반 주의',
    ],
    damage:
      '신초·잎 흡즙, 감로로 그을음. 잎 말림·생육 저하, 과실 품질 저하.',
    candidate_pesticides: ['아세타미프리드', '플로니카미드', '설폭사플로르'],
    summary: '봄철 기온 상승과 함께 활동 증가.',
  },
  {
    id: 'oriental-fruit-moth',
    pest_nm: '복숭아순나방',
    kind: 'pest',
    kind_label: '해충',
    efficacy_days: 10,
    min_score: 4,
    exclude_notes: [],
    outbreak_rules: [
      { summary: '발생 적기 5~9월', score: 1 },
      { summary: '평균기온 ≥ 18℃', score: 2 },
      { summary: '평균기온 ≥ 22℃', score: 4 },
    ],
    season_period:
      '연 4~5세대. 5월부터 본격, 늦여름 세대가 만생종 과실 피해에 중요.',
    generation_periods: [
      '1세대: 봄(대략 5월) — 신초·초기 과실 가해',
      '2~3세대: 초~중여름 — 밀도·피해 확대',
      '4세대(늦여름): 만생종 과실 집중 피해 — 알 부화 시점 방제 중요',
      '5세대(지역·연도): 수확기 전후 추가 피해 가능',
      '※ 필요 시 적기부터 1주일 간격 2회 살포 참고',
    ],
    damage:
      '신초·과실 가해. 유충이 과실 속으로 파고들어 낙과·상품성 상실.',
    candidate_pesticides: [
      '클로란트라닐리프롤',
      '에마멕틴벤조에이트',
      '루페뉴론',
    ],
    summary: '알 부화 시기 맞춤 방제. 필요 시 1주 간격 참고.',
  },
  {
    id: 'rust',
    pest_nm: '붉은별무늬병',
    kind: 'disease',
    kind_label: '병해',
    efficacy_days: 10,
    min_score: 4,
    exclude_notes: [],
    outbreak_rules: [
      { summary: '발생 적기 5~9월', score: 1 },
      { summary: '최근 7일 강우일수 ≥ 3일', score: 2 },
      { summary: '평균 습도 ≥ 75%', score: 2 },
    ],
    season_period: '봄~초여름(대략 5~7월). 강우·다습 시 잎 감염 증가.',
    generation_periods: [
      '1차 감염(봄): 중간기주·비산 포자로 잎 감염 시작(5월~)',
      '2차 감염(초여름): 강우·다습 시 병반 확대·낙엽 가속(6~7월)',
      '후기: 낙엽·월동 전염원 형성 — 위생 관리로 이듬해 압력 완화',
    ],
    damage:
      '잎에 붉은 별무늬 병반. 조기 낙엽으로 광합성·과실 비대 저하.',
    candidate_pesticides: ['만코제브', '디페노코나졸', '헥사코나졸'],
    summary: '강우·다습 조건에서 주의.',
  },
  {
    id: 'powdery',
    pest_nm: '흰가루병',
    kind: 'disease',
    kind_label: '병해',
    efficacy_days: 7,
    min_score: 4,
    exclude_notes: [],
    outbreak_rules: [
      { summary: '발생 적기 5~9월', score: 1 },
      { summary: '평균기온 ≥ 20℃', score: 2 },
      { summary: '평균 습도 ≤ 70% (건조)', score: 2 },
    ],
    season_period: '5월 이후 고온·건조기에 발생하기 쉬움.',
    generation_periods: [
      '초기(5~6월): 신초·어린잎에 흰 가루 병반 형성',
      '확대기(고온·건조 지속 시): 병반 확산·생육 지연',
      '후기: 이병 조직이 월동 전염원이 될 수 있음',
    ],
    damage:
      '잎·신초에 흰 가루 병반. 생육 지연·잎 변형, 심하면 광합성 저하.',
    candidate_pesticides: ['펜코나졸', '헥사코나졸', '트리플록시스트로빈'],
    summary: '고온·건조 조건에서 발생하기 쉬움.',
  },
  {
    id: 'fire-blight',
    pest_nm: '화상병',
    kind: 'disease',
    kind_label: '병해',
    efficacy_days: 7,
    min_score: 5,
    exclude_notes: [],
    outbreak_rules: [
      { summary: '발생 적기 5~9월', score: 1 },
      { summary: '평균기온 ≥ 20℃', score: 2 },
      { summary: '평균 습도 ≥ 70%', score: 2 },
    ],
    season_period:
      '개화기~생육기(대략 5월 이후) 위험. 고온·다습 시 급속 확산.',
    generation_periods: [
      '개화기 감염: 꽃·화경 통해 침입 — 초기 예찰·차단이 핵심',
      '신초·가지 진전: 고온·다습 시 급속 시들음·마름',
      '2차 전염: 이병지·도구·곤충 등으로 과원 내 확산',
      '※ 세대 개념보다 감염 파고 — 의심 시 즉시 예찰·신고',
    ],
    damage:
      '꽃·신초·가지가 불에 탄 듯 검게 시듦. 나무 고사·과원 전염 가능. 예찰·신고 필수.',
    candidate_pesticides: ['옥솔린산', '스트렙토마이신', '옥시테트라사이클린'],
    summary: '고위험 병해. 예찰·신고 체계를 우선하세요.',
  },
  {
    id: 'moth-general',
    pest_nm: '나방류(일반)',
    kind: 'pest',
    kind_label: '해충',
    efficacy_days: 10,
    min_score: 4,
    exclude_notes: [],
    outbreak_rules: [
      { summary: '발생 적기 5~9월', score: 1 },
      { summary: '평균기온 ≥ 20℃', score: 2 },
      { summary: '평균기온 ≥ 25℃', score: 4 },
    ],
    season_period: '5월~여름철 활동 증가. 종에 따라 세대·적기 상이.',
    generation_periods: [
      '1세대(봄~초여름): 발생 초기 예찰·밀도가 낮을 때 방제',
      '2세대 이후(여름): 기온 상승과 함께 식엽·식과 피해 확대',
      '후기세대(늦여름~초가을): 과실·잎 지속 가해 — 종별 적기 확인',
      '※ 나방류는 종이 다양하므로 성페로몬·예찰로 세대 확인 권장',
    ],
    damage:
      '잎·과실 가해. 식엽·식과로 수량·상품성 저하. 발생 초기 예찰이 중요.',
    candidate_pesticides: ['클로란트라닐리프롤', '에토펜프록스', '델타메트린'],
    summary: '여름철 활동 증가. 발생 초기 예찰.',
  },
] as const

export function filterPestDict(
  keyword: string,
  items: readonly PestDictEntry[] = TEMP_PEST_DICT,
): PestDictEntry[] {
  const q = String(keyword || '')
    .trim()
    .toLowerCase()
  if (!q) return [...items]
  return items.filter((it) => {
    const hay = [
      it.pest_nm,
      it.kind_label,
      it.summary,
      it.season_period,
      ...(it.generation_periods || []),
      it.damage,
      ...it.candidate_pesticides,
    ]
      .join(' ')
      .toLowerCase()
    return hay.includes(q)
  })
}

/** 발병여건·스마트방제와 동일 병해충명 목록 (사전 시드 SSOT) */
export const PEST_DICT_NAMES: readonly string[] = TEMP_PEST_DICT.map(
  (it) => it.pest_nm,
)

/** 월이 세대 창에 포함되는지 (양끝 포함, 연도 래핑 없음) */
export function isGenerationWindowActive(
  win: PestDictGenerationWindow,
  month: number,
): boolean {
  const m = Math.max(1, Math.min(12, Math.floor(month)))
  const lo = win.month_from
  const hi = win.month_to
  if (lo <= hi) return m >= lo && m <= hi
  return m >= lo || m <= hi
}

export function activeGenerationWindows(
  entry: PestDictEntry,
  month: number = todayBizParts().month,
): PestDictGenerationWindow[] {
  const wins = entry.generation_windows || []
  return wins.filter((w) => isGenerationWindowActive(w, month))
}
