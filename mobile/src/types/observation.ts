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

/** POST .../candidates/confirm */
export type ObservationCandidateConfirmRequest = {
  analysis_id: string
  candidate_seq: number
  confirmed_name?: string | null
}

export type ObservationCandidateConfirmResponse = {
  success: boolean
  analysis_id?: string | null
  candidate_seq?: number | null
  confirmed_name?: string | null
  confirmed_by?: string | null
  confirmed_at?: string | null
  ai_status?: string | null
  error?: string | null
  error_code?: string | null
}

/** POST/GET .../psis */
export type ObservationPsisSearchRequest = {
  analysis_id?: string | null
  candidate_seq?: number | null
  crop_name?: string | null
  disease_name?: string | null
  force_refresh?: boolean
  allow_similar?: boolean
}

export type ObservationPsisCase = {
  rank: number
  snapshot_id?: string | null
  similarity?: string | null
  pesticide_name?: string | null
  brand_name?: string | null
  company_name?: string | null
  active_ingredient?: string | null
  crop_name?: string | null
  disease_name?: string | null
  purpose_name?: string | null
  usage_method?: string | null
  dilution?: string | null
  preharvest_interval?: string | null
  max_use_count?: string | null
  toxicity?: string | null
  fish_toxicity?: string | null
  source_nm?: string | null
}

export type ObservationPsisResponse = {
  success: boolean
  psis_status: string
  snapshot_id?: string | null
  snapshot_ids?: string[]
  analysis_id?: string | null
  candidate_seq?: number | null
  query_candidate?: string | null
  crop_name?: string | null
  match_type?: string | null
  from_cache?: boolean
  similar_cases: ObservationPsisCase[]
  searched_at?: string | null
  label?: string | null
  error?: string | null
  error_code?: string | null
}

/** GET .../smart-spray-guide — 읽기 전용 통합 DTO (UI 연동은 후속) */
export type SmartSprayGuideObservation = {
  obs_id: string
  farm_cd: string
  obs_title: string
  obs_dt?: string | null
  ai_status: string
  site_id: string
  site_nm: string
}

export type SmartSprayGuideCandidate = {
  analysis_id: string
  candidate_seq: number
  name_ko: string
  confirmed_name: string
  category: string
  confidence: number
}

export type SmartSprayGuideItem = {
  rank: number
  snapshot_id: string
  pesticide_name: string
  brand_name: string
  active_ingredient: string
  crop_name: string
  disease_name: string
  purpose: string
  pesti_code: string
  item_id: number
  info_id: number
  stock_qty: number
  stock_unit: string
  has_stock: boolean
  last_used_date?: string | null
  dilution: string
  phi: string
  max_use_count: string
  usage_method: string
  toxicity: string
  from_psis: boolean
  from_stock: boolean
  psis_registered: boolean
  information_available: boolean
  match_level: string
  match_key: string
}

export type ObservationSmartSprayGuideResponse = {
  success: boolean
  guide_status: string
  farm_cd: string
  obs_id: string
  observation?: SmartSprayGuideObservation | null
  confirmed_candidate?: SmartSprayGuideCandidate | null
  psis_status: string
  crop_name: string
  disease_name: string
  items: SmartSprayGuideItem[]
  error: string
  error_code: string
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
