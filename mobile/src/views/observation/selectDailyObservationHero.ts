import {
  OBSERVATION_HERO_FALLBACK,
  type ObservationHeroItem,
} from '@/views/observation/observationHeroCatalog'

const ISO_DATE_RE = /^\d{4}-\d{2}-\d{2}$/

/** YYYY-MM-DD → 결정론적 양의 정수 (기기·재실행 동일) */
export function hashIsoDate(date: string): number {
  let h = 2166136261
  for (let i = 0; i < date.length; i += 1) {
    h ^= date.charCodeAt(i)
    h = Math.imul(h, 16777619)
  }
  return h >>> 0
}

function normalizeIsoDate(date: string): string {
  const d = String(date || '').trim()
  return ISO_DATE_RE.test(d) ? d : ''
}

/**
 * 활성화된 Hero 중 날짜 기준 결정론적 1건 선택.
 * — Math.random 미사용 · localStorage 불필요
 * — 후보 1개면 항상 해당 건 · 없으면 FALLBACK
 */
export function selectDailyObservationHero(
  heroItems: ObservationHeroItem[] | null | undefined,
  date: string,
): ObservationHeroItem {
  const enabled = (heroItems ?? []).filter((h) => h && h.enabled && h.image)
  if (enabled.length === 0) return OBSERVATION_HERO_FALLBACK
  if (enabled.length === 1) return enabled[0]

  const iso = normalizeIsoDate(date)
  const seed = iso ? hashIsoDate(iso) : 0
  const idx = seed % enabled.length
  return enabled[idx] ?? OBSERVATION_HERO_FALLBACK
}
