import { apiDelete, apiGet, apiPutJson, apiUploadForm } from '@/api/client'
import { resolveMediaUrl } from '@/utils/mediaUrl'
import type {
  ObservationPhotoItem,
  ObservationPhotoListResponse,
  ObservationPhotoUploadResponse,
} from '@/types/observation'

const USER_HEADER = { 'X-User-Id': 'MIRROR' }

function photosBase(farmCd: string, obsId: string): string {
  return `/farms/${encodeURIComponent(farmCd)}/observations/${encodeURIComponent(obsId)}/photos`
}

export function fetchObservationPhotos(
  farmCd: string,
  obsId: string,
  signal?: AbortSignal,
): Promise<ObservationPhotoListResponse> {
  return apiGet<ObservationPhotoListResponse>(photosBase(farmCd, obsId), { signal })
}

export function fetchRepresentativePhoto(
  farmCd: string,
  obsId: string,
  signal?: AbortSignal,
): Promise<ObservationPhotoItem | null> {
  return apiGet<ObservationPhotoItem | null>(
    `${photosBase(farmCd, obsId)}/representative`,
    { signal },
  )
}

export function uploadObservationPhotos(
  farmCd: string,
  obsId: string,
  files: File[],
  options?: { signal?: AbortSignal },
): Promise<ObservationPhotoUploadResponse> {
  const form = new FormData()
  for (const file of files) {
    form.append('files', file, file.name || 'photo.jpg')
  }
  return apiUploadForm<ObservationPhotoUploadResponse>(photosBase(farmCd, obsId), form, {
    signal: options?.signal,
    headers: USER_HEADER,
  })
}

export function deleteObservationPhoto(
  farmCd: string,
  obsId: string,
  photoId: string,
  options?: { signal?: AbortSignal },
): Promise<{ detail: string }> {
  return apiDelete(`${photosBase(farmCd, obsId)}/${encodeURIComponent(photoId)}`, {
    signal: options?.signal,
    headers: USER_HEADER,
  })
}

export function reorderObservationPhotos(
  farmCd: string,
  obsId: string,
  photoIds: string[],
  options?: { signal?: AbortSignal },
): Promise<ObservationPhotoListResponse> {
  return apiPutJson<ObservationPhotoListResponse>(
    `${photosBase(farmCd, obsId)}/order`,
    { photo_ids: photoIds },
    { signal: options?.signal, headers: USER_HEADER },
  )
}

export function photoThumbSrc(
  photo: Pick<
    ObservationPhotoItem,
    'thumb_url' | 'original_url' | 'farm_cd' | 'obs_id' | 'photo_id'
  >,
): string {
  if (photo.thumb_url) return resolveMediaUrl(photo.thumb_url)
  if (photo.farm_cd && photo.obs_id && photo.photo_id) {
    return resolveMediaUrl(
      `/farms/${encodeURIComponent(photo.farm_cd)}/observations/${encodeURIComponent(photo.obs_id)}/photos/${encodeURIComponent(photo.photo_id)}/thumbnail`,
    )
  }
  return resolveMediaUrl(photo.original_url)
}

function photoIdFromThumbPath(path?: string | null): string | null {
  const raw = String(path || '').trim()
  if (!raw) return null
  const name = raw.split('/').pop() || ''
  const stem = name.replace(/\.[a-z0-9]{2,5}$/i, '')
  return stem || null
}

export function observationListThumbSrc(item: {
  farm_cd: string
  obs_id: string
  thumb_url?: string | null
  thumb_photo_id?: string | null
  thumb_path?: string | null
}): string {
  if (item.thumb_url) return resolveMediaUrl(item.thumb_url)
  const photoId = item.thumb_photo_id || photoIdFromThumbPath(item.thumb_path)
  if (!photoId) return ''
  return resolveMediaUrl(
    `/farms/${encodeURIComponent(item.farm_cd)}/observations/${encodeURIComponent(item.obs_id)}/photos/${encodeURIComponent(photoId)}/thumbnail`,
  )
}
