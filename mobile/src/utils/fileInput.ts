/**
 * file input 에서 File 배열을 안전하게 복사한다.
 * Android Chrome 등에서 FileList 는 live 참조이므로
 * input.value = '' 이전에 반드시 복사해야 한다.
 */
export function takeFilesFromInput(input: HTMLInputElement): File[] {
  const list = input.files
  const copied = list && list.length > 0 ? Array.from(list) : []
  // 동일 파일 재선택·피커 재오픈을 위해 값은 복사 후에만 초기화
  input.value = ''
  return copied.map((file, index) => normalizeUploadFile(file, index))
}

/** 카메라 등에서 파일명이 비거나 확장자가 없을 때 업로드용 이름 보정 */
export function normalizeUploadFile(file: File, index = 0): File {
  const rawName = String(file.name || '').trim()
  const hasExt = /\.[a-z0-9]{2,5}$/i.test(rawName)
  if (rawName && hasExt) return file

  const mime = String(file.type || '').toLowerCase()
  let ext = 'jpg'
  if (mime.includes('png')) ext = 'png'
  else if (mime.includes('webp')) ext = 'webp'
  else if (mime.includes('heic') || mime.includes('heif')) ext = 'heic'
  else if (mime.includes('jpeg') || mime.includes('jpg')) ext = 'jpg'

  const type =
    mime ||
    (ext === 'png'
      ? 'image/png'
      : ext === 'webp'
        ? 'image/webp'
        : ext === 'heic'
          ? 'image/heic'
          : 'image/jpeg')
  const base = rawName.replace(/\.[^.]*$/, '') || `photo_${Date.now()}_${index + 1}`
  return new File([file], `${base}.${ext}`, { type, lastModified: file.lastModified })
}
