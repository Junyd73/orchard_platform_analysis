export type ObservationSummary = {
  today_count: number
  danger_count: number
  fruit_count: number
  ai_pending_count: number
  as_of_date: string
}

export type ObservationListItem = {
  obs_id: string
  farm_cd: string
  obs_dt: string
  obs_title: string | null
  target_type_cd: string
  target_type_nm: string
  obs_type_cd: string
  obs_type_nm: string
  site_id: string | null
  site_nm: string | null
  location_text: string
  severity_cd: string
  severity_nm: string
  progress_status_cd: string
  progress_status_nm: string
  ai_status: string
  followup_dt: string | null
  has_photo: boolean
  thumb_path: string | null
  thumb_url?: string | null
  thumb_photo_id?: string | null
  observation_status?: string
  record_status?: string
}

export type ObservationDraftItem = {
  obs_id: string
  farm_cd: string
  obs_dt: string
  obs_title: string | null
  target_type_cd: string
  target_type_nm: string
  site_id: string | null
  site_nm: string | null
  location_text: string
  photo_count: number
  mod_dt: string | null
  observation_status: string
  record_status: string
}

export type ObservationListQuery = {
  date_from?: string
  date_to?: string
  site_id?: string
  keyword?: string
  sort?: 'obs_dt_desc' | 'obs_dt_asc'
  limit?: number
}

/** SCR-002 사진 (등록 저장과 분리) */
export type ObservationPhotoItem = {
  photo_id: string
  obs_id: string
  farm_cd: string
  sort_no: number
  is_representative: boolean
  display_nm: string
  original_nm: string | null
  stored_nm?: string | null
  file_ext: string | null
  file_size: number | null
  width_px: number | null
  height_px: number | null
  thumb_url: string
  original_url: string
}

export type ObservationPhotoListResponse = {
  obs_id: string
  count: number
  max_count: number
  remaining: number
  photos: ObservationPhotoItem[]
}

export type ObservationPhotoUploadResponse = {
  uploaded: ObservationPhotoItem[]
  skipped: string[]
  count: number
  max_count: number
  remaining: number
  message: string
  success?: boolean
  photo_id?: string | null
  farm_cd?: string | null
  obs_id?: string | null
  file_name?: string | null
  file_path?: string | null
  thumbnail_path?: string | null
  file_size?: number | null
  width?: number | null
  height?: number | null
  created_by?: string | null
  created_at?: string | null
  error?: string | null
  error_code?: string | null
}

/** POST/GET /observations/{obs_id}/analysis */
export type ObservationAiCandidate = {
  candidate_seq: number
  category?: string | null
  name_ko?: string | null
  scientific_name?: string | null
  confidence?: number | null
  visual_evidence?: string[]
  differential_reason?: string | null
  urgency?: string | null
  selected_yn?: string | null
  confirmed_name?: string | null
}

export type ObservationAiPhotoRef = {
  photo_id: string
}

export type ObservationAiAnalyzeRequest = {
  consent: boolean
  photo_ids?: string[] | null
  crop_hint?: string
}

export type ObservationAiAnalysisResponse = {
  success: boolean
  ai_status: string
  analysis_id?: string | null
  summary?: string | null
  candidates: ObservationAiCandidate[]
  photos: ObservationAiPhotoRef[]
  confidence?: number | null
  analyzed_at?: string | null
  error?: string | null
  error_code?: string | null
  analysis_status?: string | null
  review_required?: boolean
  image_quality?: string | null
  analysis_possible?: boolean | null
}

export type ObservationBasicSavePayload = {
  obs_dt: string
  target_type_cd: string
  site_id: string
  obs_title?: string | null
  obs_content?: string | null
}

export type ObservationSaveResponse = {
  obs_id: string
  farm_cd: string
  created: boolean
  message: string
  observation_status?: string | null
}

export type ObservationDetail = {
  obs_id: string
  farm_cd: string
  obs_dt: string
  target_type_cd: string
  target_type_nm: string
  obs_type_cd: string
  obs_type_nm: string
  site_id: string | null
  site_nm: string | null
  severity_cd: string
  severity_nm: string
  progress_status_cd: string
  progress_status_nm: string
  obs_title: string | null
  obs_content: string | null
  ai_status: string
  use_yn: string
  observation_status?: string
  record_status?: string
  reg_id?: string | null
  reg_dt?: string | null
  mod_id?: string | null
  mod_dt?: string | null
  completed_at?: string | null
  completed_by?: string | null
  photo_count?: number
  can_delete?: boolean
  zone_nm?: string | null
  row_no?: string | null
  tree_no?: string | null
  sample_no?: string | null
}
