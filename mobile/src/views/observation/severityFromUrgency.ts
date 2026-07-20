/**
 * AI urgency → OS01 위험도 제안 매핑 (최종 확정은 사용자)
 */
import {
  OBS_SEVERITY_CAUTION_CD,
  OBS_SEVERITY_DANGER_CD,
  OBS_SEVERITY_NORMAL_CD,
  OBS_SEVERITY_WATCH_CD,
} from '@/composables/constants/app'

export function suggestSeverityFromUrgency(
  urgency: string | null | undefined,
): string {
  const u = String(urgency || '')
    .trim()
    .toUpperCase()
  if (u === 'HIGH') return OBS_SEVERITY_DANGER_CD
  if (u === 'MEDIUM') return OBS_SEVERITY_CAUTION_CD
  if (u === 'LOW') return OBS_SEVERITY_WATCH_CD
  return OBS_SEVERITY_NORMAL_CD
}
