/** WorkLog 월간 — KST 자정 경과 시 today/selectedDt/조회월 갱신 계획. */

export type BizDayRolloverPlan = {
  today: string
  selectedDt: string
  year: number
  month: number
}

/**
 * lastToday → nextToday 로 업무일이 바뀌면 갱신 계획 반환.
 * 동일일이면 null.
 */
export function planBizDayRollover(
  lastToday: string,
  nextToday: string,
  parts: { year: number; month: number },
): BizDayRolloverPlan | null {
  if (nextToday === lastToday) return null
  return {
    today: nextToday,
    selectedDt: nextToday,
    year: parts.year,
    month: parts.month,
  }
}
