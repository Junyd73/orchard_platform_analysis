/**
 * Project A / 모바일 공통 상수
 * TODO(auth): 로그인 세션 farm_cd / user_id 로 교체
 */
export const DEFAULT_FARM_CD = 'OR001'

/** ODS Project A: 관찰 사진 최대 장수 */
export const OBS_PHOTO_MAX_COUNT = 5

/** 서버 OBS_PHOTO_MAX_BYTES 와 동일 (20MB) */
export const OBS_PHOTO_MAX_BYTES = 20 * 1024 * 1024

/** AI 분석에 동시에 보낼 사진 최대 장수 (ODS AI 흐름) */
export const OBS_AI_PHOTO_MAX_COUNT = 5

/** AI 분석 예상 소요 안내 (서버 DEFAULT_TIMEOUT_SEC=60 과 맞춤) */
export const OBS_AI_DURATION_NOTICE =
  '정확한 분석을 위해 60초정도의 시간이 소요됩니다.'

/** PC m_common_code OB01 — 병해충 / 과실(열매) */
export const OBS_TARGET_PEST_CD = 'OB010400'
export const OBS_TARGET_FRUIT_CD = 'OB010200'

/** PC m_common_code OS01 — 위험도(심각도) */
export const OBS_SEVERITY_PARENT_CD = 'OS01'
export const OBS_SEVERITY_NORMAL_CD = 'OS010100'
export const OBS_SEVERITY_WATCH_CD = 'OS010200'
export const OBS_SEVERITY_CAUTION_CD = 'OS010300'
export const OBS_SEVERITY_DANGER_CD = 'OS010400'

/** 추적관찰 등록 — 카드 타이틀 접두 (1차 관찰명) */
export const OBS_FOLLOW_UP_ROOT_TITLE_LABEL = '최초 관찰명'

/** PC Stage2 열매측정 공통코드 대분류 */
export const OBS_FRUIT_SHAPE_PARENT_CD = 'FS01'
export const OBS_FRUIT_COLOR_PARENT_CD = 'FC01'
export const OBS_STALK_PARENT_CD = 'FK01'
export const OBS_CALYX_PARENT_CD = 'FY01'

/** sessionStorage: 신규 등록 중 obs_id (새로고침·뒤로가기 중복 생성 방지) */
export const OBS_DRAFT_STORAGE_PREFIX = 'orchard_obs_draft:'
