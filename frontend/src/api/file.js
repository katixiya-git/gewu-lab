import http from './request'

/**
 * 上传单个文件，返回 { id, url, name, size, mime, isPublic }。
 * onProgress 回调收到 0–100 的整数。
 */
export function uploadFile(file, { bizType, bizId = null, onProgress } = {}) {
  const form = new FormData()
  form.append('file', file)
  form.append('bizType', bizType)
  if (bizId !== null && bizId !== undefined) form.append('bizId', String(bizId))

  return http.post('/files/upload', form, {
    timeout: 60000,
    onUploadProgress: (event) => {
      if (!onProgress || !event.total) return
      onProgress(Math.round((event.loaded / event.total) * 100))
    }
  })
}

/** 私有文件下载地址（需要携带 token，页面里用 axios 取 blob 或直接跳转由后端校验） */
export function downloadUrl(fileId) {
  return `/api/files/${fileId}/download`
}
