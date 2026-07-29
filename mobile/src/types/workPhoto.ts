export type WorkPhotoItem = {
  photo_id: string
  work_id: string
  farm_cd: string
  sort_no: number
  display_nm: string
  original_nm?: string | null
  stored_nm?: string | null
  file_ext?: string | null
  file_size?: number | null
  width_px?: number | null
  height_px?: number | null
  thumb_url: string
  original_url: string
}

export type WorkPhotoListResponse = {
  work_id: string
  count: number
  max_count: number
  remaining: number
  photos: WorkPhotoItem[]
}

export type WorkPhotoUploadResponse = {
  uploaded: WorkPhotoItem[]
  skipped: string[]
  count: number
  max_count: number
  remaining: number
  message: string
  success: boolean
  photo_id?: string | null
  farm_cd?: string | null
  work_id?: string | null
  error?: string | null
  error_code?: string | null
}
