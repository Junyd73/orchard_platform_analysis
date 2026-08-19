import type { ProductionPrefillLine } from '@/api/production'

export type PrefillNameOption = { value: string; label: string }

function labelOf(opts: PrefillNameOption[], cd: string): string {
  return opts.find((o) => o.value === cd)?.label || ''
}

/** 표시용 명칭만 채움. API 확정 payload의 code는 그대로 둔다. */
export function attachPrefillDisplayNames(
  lines: ProductionPrefillLine[],
  lookups: {
    variety: PrefillNameOption[]
    grade: PrefillNameOption[]
    size: PrefillNameOption[]
  },
): ProductionPrefillLine[] {
  return lines.map((ln) => ({
    ...ln,
    variety_nm: ln.variety_nm || labelOf(lookups.variety, ln.variety_cd),
    grade_nm: ln.grade_nm || labelOf(lookups.grade, ln.grade_cd),
    size_nm: ln.size_nm || labelOf(lookups.size, ln.size_cd),
  }))
}
