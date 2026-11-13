// 设备状态码与展示文案的映射

export const DEVICE_STATUS_LABELS = {
  normal: '正常',
  maintenance: '维护中',
  disabled: '停用'
}

export const DEVICE_STATUS_OPTIONS = Object.entries(DEVICE_STATUS_LABELS).map(([value, label]) => ({
  value,
  label
}))

export function deviceStatusText(status) {
  return DEVICE_STATUS_LABELS[status] ?? status
}

export function deviceStatusTagType(status) {
  return (
    {
      normal: 'success',
      maintenance: 'warning',
      disabled: 'info'
    }[status] ?? 'info'
  )
}
