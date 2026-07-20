/** SCR-012 목록 유형 뱃지 — 공백 제거 후 2글자×N줄(2×2 기준) */

export function formatNotificationTypeBadge(raw: string | null | undefined): string {
  const s = String(raw || '')
    .replace(/\s+/g, '')
    .trim()
  if (!s) return ''
  const lines: string[] = []
  for (let i = 0; i < s.length; i += 2) {
    lines.push(s.slice(i, i + 2))
  }
  return lines.join('\n')
}
