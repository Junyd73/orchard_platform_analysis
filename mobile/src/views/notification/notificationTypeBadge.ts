/** SCR-012 목록 유형 뱃지 — 표시명 보정 후 2글자×N줄(2×2 기준) */

const TYPE_LABEL_OVERRIDE: Record<string, string> = {
  NT010200: '생육관찰',
}

/** API noti_type_nm 보정 (공통코드 구명칭 호환) */
export function resolveNotificationTypeLabel(
  notiTypeCd: string | null | undefined,
  notiTypeNm: string | null | undefined,
): string {
  const cd = String(notiTypeCd || '')
    .trim()
    .toUpperCase()
  const override = TYPE_LABEL_OVERRIDE[cd]
  if (override) return override
  return String(notiTypeNm || cd || '').trim()
}

export function formatNotificationTypeBadge(
  raw: string | null | undefined,
  notiTypeCd?: string | null,
): string {
  const label = notiTypeCd
    ? resolveNotificationTypeLabel(notiTypeCd, raw)
    : String(raw || '')
        .replace(/\s+/g, '')
        .trim()
  const s = String(label || '')
    .replace(/\s+/g, '')
    .trim()
  if (!s) return ''
  const lines: string[] = []
  for (let i = 0; i < s.length; i += 2) {
    lines.push(s.slice(i, i + 2))
  }
  return lines.join('\n')
}
