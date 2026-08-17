import { todayBizIso } from '@/shared/bizDate'

/** ISO `YYYY-MM-DD` → `YYYY년 MM월 DD일` */
export function formatDateKo(isoDate: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(isoDate.trim())
  if (!m) return isoDate
  return `${m[1]}년 ${m[2]}월 ${m[3]}일`
}

/** @deprecated use todayBizIso — OPS KST 업무일 (호환 alias) */
export function todayLocalIso(d: Date = new Date()): string {
  return todayBizIso(d)
}

export { todayBizIso } from '@/shared/bizDate'
