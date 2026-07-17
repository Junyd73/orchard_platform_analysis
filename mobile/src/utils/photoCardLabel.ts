/**
 * 모바일 카드용 간결 라벨.
 * display_nm 예: 병해충_뒷밭_20260717_01.jpg
 * → 병해충 · 뒷밭 / 사진 1
 * 데이터(display_nm)는 그대로 두고 표시만 단순화.
 */
const DATE8 = /^\d{8}$/
const SEQ2 = /^\d{1,2}$/

export type PhotoCardLabel = {
  /** 전체명 (title / 접근성) */
  fullName: string
  /** 1행: 병해충 · 뒷밭 */
  primary: string
  /** 2행: 사진 1 */
  secondary: string
  /** 한 줄: 병해충 · 뒷밭 · 사진 1 */
  compact: string
}

export function formatPhotoCardLabel(
  displayNm: string | null | undefined,
  index: number,
): PhotoCardLabel {
  const raw = String(displayNm || '').trim()
  const seq = index + 1
  const secondary = `사진 ${seq}`
  const fullName = raw || secondary

  if (!raw) {
    const primary = '관찰사진'
    return {
      fullName,
      primary,
      secondary,
      compact: `${primary} · ${secondary}`,
    }
  }

  const stem = fullName.replace(/\.[a-z0-9]{2,5}$/i, '')
  const parts = stem.split('_').filter(Boolean)

  let tokens = [...parts]
  if (tokens.length >= 1 && SEQ2.test(tokens[tokens.length - 1] || '')) {
    tokens = tokens.slice(0, -1)
  }
  if (tokens.length >= 1 && DATE8.test(tokens[tokens.length - 1] || '')) {
    tokens = tokens.slice(0, -1)
  }

  const primary = tokens.length ? tokens.join(' · ') : '관찰사진'
  const compact = `${primary} · ${secondary}`

  return { fullName, primary, secondary, compact }
}
