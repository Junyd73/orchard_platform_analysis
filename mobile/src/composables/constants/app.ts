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
export const OBS_AI_PHOTO_MAX_COUNT = 3

/** PC m_common_code OB01 — 병해충 / 과실(열매) */
export const OBS_TARGET_PEST_CD = 'OB010400'
export const OBS_TARGET_FRUIT_CD = 'OB010200'

/** sessionStorage: 신규 등록 중 obs_id (새로고침·뒤로가기 중복 생성 방지) */
export const OBS_DRAFT_STORAGE_PREFIX = 'orchard_obs_draft:'
