import { OBS_DRAFT_STORAGE_PREFIX } from '@/composables/constants/app'

export type ObsDraftRef = {
  obsId: string
  farmCd: string
}

function key(farmCd: string): string {
  return `${OBS_DRAFT_STORAGE_PREFIX}${farmCd}`
}

export function readObsDraft(farmCd: string): ObsDraftRef | null {
  try {
    const raw = sessionStorage.getItem(key(farmCd))
    if (!raw) return null
    const parsed = JSON.parse(raw) as ObsDraftRef
    if (!parsed?.obsId || !parsed?.farmCd) return null
    if (parsed.farmCd !== farmCd) return null
    return parsed
  } catch {
    return null
  }
}

export function writeObsDraft(farmCd: string, obsId: string): void {
  const payload: ObsDraftRef = { farmCd, obsId }
  sessionStorage.setItem(key(farmCd), JSON.stringify(payload))
}

export function clearObsDraft(farmCd: string): void {
  sessionStorage.removeItem(key(farmCd))
}
