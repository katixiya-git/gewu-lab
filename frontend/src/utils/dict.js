// 后端字段码 → 前端展示文案的统一映射

export const ROLE_LABELS = {
  student: '学生',
  admin: '管理员'
}

export function roleText(role) {
  return ROLE_LABELS[role] ?? role
}

export function roleTagType(role) {
  return role === 'admin' ? 'danger' : 'info'
}

export const USER_STATUS_LABELS = {
  active: '正常',
  disabled: '停用'
}

export function userStatusText(status) {
  return USER_STATUS_LABELS[status] ?? status
}

export function userStatusTagType(status) {
  return status === 'active' ? 'success' : 'info'
}
