import wxCloud from '@/assets/ods/work-log/wx-cloud.svg'
import wxRain from '@/assets/ods/work-log/wx-rain.svg'
import wxSnow from '@/assets/ods/work-log/wx-snow.svg'
import wxSunny from '@/assets/ods/work-log/wx-sunny.svg'
import { weatherIconSrc } from '@/views/work-log/workLogConstants'
import { WEATHER_ICON_KEY } from '@/views/weather/weatherConstants'

const ICON_BY_KEY: Record<string, string> = {
  [WEATHER_ICON_KEY.SUN]: wxSunny,
  [WEATHER_ICON_KEY.PARTLY_CLOUDY]: wxSunny,
  [WEATHER_ICON_KEY.CLOUD]: wxCloud,
  [WEATHER_ICON_KEY.RAIN]: wxRain,
  [WEATHER_ICON_KEY.SLEET]: wxRain,
  [WEATHER_ICON_KEY.SNOW]: wxSnow,
  [WEATHER_ICON_KEY.SUNRISE]: wxSunny,
  [WEATHER_ICON_KEY.SUNSET]: wxSunny,
}

export function weatherIconByKey(
  icon?: string | null,
  weatherCd?: string | null,
): string {
  const key = String(icon || '').trim()
  if (key && ICON_BY_KEY[key]) return ICON_BY_KEY[key]
  return weatherIconSrc(weatherCd)
}

export function formatTempC(value?: number | null, digits = 0): string {
  if (value == null || !Number.isFinite(Number(value))) return '—'
  const n = Number(value)
  if (digits <= 0) return `${Math.round(n)}°`
  return `${n.toFixed(digits)}°`
}

export function formatPct(value?: number | null): string {
  if (value == null || !Number.isFinite(Number(value))) return '—'
  return `${Math.round(Number(value))}%`
}

export function formatMm(value?: number | null): string {
  if (value == null || !Number.isFinite(Number(value))) return '—'
  const n = Number(value)
  if (n <= 0) return '0mm'
  return `${Math.round(n * 10) / 10}mm`
}

export function formatWindMs(value?: number | null): string {
  if (value == null || !Number.isFinite(Number(value))) return '—'
  return `${Math.round(Number(value) * 10) / 10}m/s`
}

export function formatHourLabel(at: string): string {
  const s = String(at || '').trim()
  if (s.length >= 16) return s.slice(11, 16)
  return s || '—'
}

export function formatUpdatedAt(raw?: string | null): string {
  const s = String(raw || '').trim()
  if (s.length >= 16) return `${s.slice(5, 10)} ${s.slice(11, 16)}`
  return s || '—'
}

export function formatTempDiff(diff?: number | null): string {
  if (diff == null || !Number.isFinite(Number(diff))) return ''
  const n = Math.round(Number(diff) * 10) / 10
  if (n === 0) return '어제와 비슷'
  if (n > 0) return `어제보다 +${n}°`
  return `어제보다 ${n}°`
}

export function weeklyDateLabel(date: string, weekday: string): string {
  const ds = String(date || '')
  const day = ds.length >= 10 ? ds.slice(8, 10) : ds
  const wd = String(weekday || '').trim()
  if (day && wd) return `${day} ${wd}`
  return wd || day || '—'
}
