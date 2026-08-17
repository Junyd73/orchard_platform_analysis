/** OPS 업무일 — Asia/Seoul(KST). 기기 timezone에 의존하지 않음.
 *  UTC `toISOString().slice(0,10)` 금지.
 */
export const OPS_TZ_NAME = 'Asia/Seoul'

const _kstDateParts = new Intl.DateTimeFormat('en-CA', {
  timeZone: OPS_TZ_NAME,
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
})

/** 업무 '오늘' `YYYY-MM-DD` (KST). 테스트용 now 주입 가능. */
export function todayBizIso(now: Date = new Date()): string {
  // en-CA → YYYY-MM-DD
  return _kstDateParts.format(now)
}

/** KST 달력 년·월·일 */
export function todayBizParts(now: Date = new Date()): {
  year: number
  month: number
  day: number
} {
  const [year, month, day] = todayBizIso(now).split('-').map(Number)
  return { year, month, day }
}
