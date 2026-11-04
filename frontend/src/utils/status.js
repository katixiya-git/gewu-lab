const STATUS_MAP = {
  pending: { text: '待审核', tag: 'warning' },
  approved: { text: '已通过', tag: 'success' },
  rejected: { text: '已驳回', tag: 'danger' },
  conflict: { text: '冲突待协调', tag: 'danger' },
  cancelled: { text: '已取消', tag: 'info' }
}

export function statusText(status) {
  return STATUS_MAP[status]?.text ?? status
}

export function statusTagType(status) {
  return STATUS_MAP[status]?.tag ?? 'info'
}
