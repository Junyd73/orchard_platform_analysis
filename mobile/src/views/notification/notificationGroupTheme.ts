/**
 * SCR-012 알림 그룹 시각화 — ODS SVG + tokens.css 변수 매핑
 * (lucide / Tailwind 미사용)
 */
import iconBell from '@/assets/ods/common/icon-bell.svg'
import iconFruit from '@/assets/ods/common/icon-kpi-fruit.svg'
import iconWarn from '@/assets/ods/common/icon-kpi-warn.svg'
import iconClipboard from '@/assets/ods/work-log/icon-clipboard.svg'
import wxSunny from '@/assets/ods/work-log/wx-sunny.svg'

export type NotificationGroupId = 'market' | 'weather' | 'rda' | 'system'

export type NotificationGroupTheme = {
  id: NotificationGroupId
  /** OdsBadge tone — ODS 팔레트와 정렬 */
  badgeTone: 'ok' | 'ai' | 'caution' | 'neutral'
  iconSrc: string
  /** 카드/뱃지 래퍼 class: ntf-group--market 등 */
  className: string
}

const GROUP_MARKET: NotificationGroupTheme = {
  id: 'market',
  badgeTone: 'ok',
  iconSrc: iconFruit,
  className: 'ntf-group--market',
}

const GROUP_WEATHER: NotificationGroupTheme = {
  id: 'weather',
  badgeTone: 'ai',
  iconSrc: wxSunny,
  className: 'ntf-group--weather',
}

const GROUP_RDA: NotificationGroupTheme = {
  id: 'rda',
  badgeTone: 'caution',
  iconSrc: iconWarn,
  className: 'ntf-group--rda',
}

const GROUP_SYSTEM: NotificationGroupTheme = {
  id: 'system',
  badgeTone: 'neutral',
  iconSrc: iconClipboard,
  className: 'ntf-group--system',
}

/** 미매핑·시스템성 유형 폴백 */
const GROUP_FALLBACK: NotificationGroupTheme = {
  ...GROUP_SYSTEM,
  iconSrc: iconBell,
}

/**
 * noti_type_cd → 알림 그룹 테마
 * - NT011000 가락 시세
 * - NT010500 기상
 * - NT010600 농진청
 * - NT010100~NT010400 (+ NT010900) 과수원 시스템/영농
 */
export function resolveNotificationGroup(
  notiTypeCd: string | null | undefined,
): NotificationGroupTheme {
  const t = String(notiTypeCd || '').trim().toUpperCase()
  if (t === 'NT011000') return GROUP_MARKET
  if (t === 'NT010500') return GROUP_WEATHER
  if (t === 'NT010600') return GROUP_RDA
  if (
    t === 'NT010100' ||
    t === 'NT010200' ||
    t === 'NT010300' ||
    t === 'NT010400' ||
    t === 'NT010900'
  ) {
    return GROUP_SYSTEM
  }
  return GROUP_FALLBACK
}
