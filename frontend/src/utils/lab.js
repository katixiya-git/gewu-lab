// 实验室相关的展示映射：类型码 / 状态码 / 开放日 / 时间格式

export const LAB_CATEGORY_LABELS = {
  ai: '人工智能',
  robot: '机器人',
  cloud: '云计算',
  se: '软件工程'
}

export const LAB_CATEGORY_OPTIONS = Object.entries(LAB_CATEGORY_LABELS).map(([value, label]) => ({
  value,
  label
}))

export function labCategoryText(category) {
  return LAB_CATEGORY_LABELS[category] ?? category
}

export function labCategoryTagType(category) {
  return (
    {
      ai: 'primary',
      robot: 'success',
      cloud: 'warning',
      se: 'info'
    }[category] ?? 'info'
  )
}

export const LAB_STATUS_LABELS = {
  enabled: '启用',
  disabled: '停用'
}

export function labStatusText(status) {
  return LAB_STATUS_LABELS[status] ?? status
}

export function labStatusTagType(status) {
  return status === 'enabled' ? 'success' : 'info'
}

const WEEK_LABELS = ['一', '二', '三', '四', '五', '六', '日']

/** 把 "1-5" 转成「周一至周五」，单日 "7" 转成「周日」 */
export function openDaysText(openDays) {
  if (!openDays) return '—'
  const [start, end] = String(openDays).split('-')
  const startLabel = WEEK_LABELS[Number(start) - 1]
  if (!startLabel) return openDays
  if (!end) return `周${startLabel}`
  const endLabel = WEEK_LABELS[Number(end) - 1] ?? end
  return `周一至周${endLabel}` === `周一至周${startLabel}`
    ? `周${startLabel}`
    : `周${startLabel}至周${endLabel}`
}

/** 后端 time 字段序列化成 "08:00:00"，展示时只保留时分 */
export function formatTime(value) {
  return value ? String(value).slice(0, 5) : '—'
}

/** 「周一至周五 08:00-22:00」 */
export function openTimeText(lab) {
  if (!lab) return '—'
  return `${openDaysText(lab.openDays)} ${formatTime(lab.openTime)}-${formatTime(lab.closeTime)}`
}
