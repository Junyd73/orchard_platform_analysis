/** 날씨 상세 화면 상수 */

export const LABEL_WEATHER_DETAIL = '날씨 상세'
export const LABEL_WEATHER_HOURLY = '시간별 예보'
export const LABEL_WEATHER_WEEKLY = '주간예보'
export const LABEL_WEATHER_AM = '오전'
export const LABEL_WEATHER_PM = '오후'
export const LABEL_WEATHER_UPDATED = '업데이트'
export const LABEL_WEATHER_TOMORROW_AM = '내일 오전'
export const LABEL_WEATHER_SUNRISE = '일출'
export const LABEL_WEATHER_SUNSET = '일몰'
export const LABEL_WEATHER_HUMIDITY = '습도'
export const LABEL_WEATHER_WIND = '바람'
export const LABEL_WEATHER_PRECIP = '강수'
export const LABEL_WEATHER_PRECIP_PROB = '강수확률'
export const LABEL_WEATHER_WEEKLY_NOTE =
  '오전은 06~12시, 오후는 12~18시 기준 예보입니다.'
export const BTN_WEATHER_WEEKLY_MORE = '더보기'
export const BTN_WEATHER_WEEKLY_LESS = '접기'
export const WEATHER_WEEKLY_COLLAPSED_DAYS = 3
export const MSG_WEATHER_LOADING = '날씨 정보를 불러오는 중…'
export const MSG_WEATHER_EMPTY = '표시할 날씨 정보가 없습니다.'
export const MSG_WEATHER_LOAD_FAILED = '날씨 상세를 불러오지 못했습니다.'

export const WEATHER_ICON_KEY = {
  SUN: 'sun',
  CLOUD: 'cloud',
  PARTLY_CLOUDY: 'partly_cloudy',
  RAIN: 'rain',
  SNOW: 'snow',
  SLEET: 'sleet',
  SUNRISE: 'sunrise',
  SUNSET: 'sunset',
} as const
