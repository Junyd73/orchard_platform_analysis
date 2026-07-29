/** 모바일 날씨 상세 API 타입 */
export type WeatherSunMarker = 'sunrise' | 'sunset'
export type WeatherHourlyKind = 'hour' | 'sun'
export type WeatherWeeklySource = 'short' | 'mid'

export interface WeatherPeriodHalfDto {
  precip_prob_pct: number
  precip_mm?: number | null
  wind_ms?: number | null
}

export interface WeatherCurrentDto {
  temp_c?: number | null
  temp_min?: number | null
  temp_max?: number | null
  temp_diff_from_yesterday?: number | null
  weather_cd: string
  weather_nm: string
  humidity_pct?: number | null
  wind_ms?: number | null
  precip_mm?: number | null
  precip_prob_pct: number
  sun_rise?: string | null
  sun_set?: string | null
}

export interface WeatherHourlyItemDto {
  at: string
  kind: WeatherHourlyKind
  temp_c?: number | null
  precip_prob_pct?: number | null
  precip_mm?: number | null
  humidity_pct?: number | null
  wind_ms?: number | null
  icon?: string | null
  weather_cd?: string | null
  marker?: WeatherSunMarker | null
}

export interface WeatherSunEventDto {
  at: string
  kind: WeatherSunMarker
}

export interface WeatherWeeklyItemDto {
  date: string
  weekday: string
  temp_min: number
  temp_max: number
  icon: string
  am: WeatherPeriodHalfDto
  pm: WeatherPeriodHalfDto
  source: WeatherWeeklySource
}

export interface WeatherDetailResponse {
  success: boolean
  farm_cd: string
  date: string
  location: string
  current: WeatherCurrentDto
  tomorrow_am?: WeatherPeriodHalfDto | null
  hourly: WeatherHourlyItemDto[]
  sun_events: WeatherSunEventDto[]
  weekly: WeatherWeeklyItemDto[]
  updated_at?: string | null
  elapsed: number
  message: string
}
