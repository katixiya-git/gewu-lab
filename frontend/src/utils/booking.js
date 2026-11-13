import { statusTagType, statusText } from './status'

export const BOOKING_TYPE_LABELS = {
  personal: '个人',
  group: '小组',
  class: '班级'
}

export const BOOKING_TYPE_OPTIONS = Object.entries(BOOKING_TYPE_LABELS).map(([value, label]) => ({
  value,
  label
}))

export function bookingTypeText(type) {
  return BOOKING_TYPE_LABELS[type] ?? type
}

/** 预约开始的本地时间；后端返回 bookingDate=YYYY-MM-DD、startTime=HH:MM */
export function startDateTime(row) {
  return new Date(`${row.bookingDate}T${row.startTime}:00`)
}

/** 距开始还有多少小时（已开始则为负数） */
export function hoursUntilStart(row) {
  return (startDateTime(row).getTime() - Date.now()) / 3600000
}

/** 已通过且不足 12 小时：只能提交取消申请 */
export function needsCancelRequest(row) {
  return row.status === 'approved' && !row.cancelRequested && hoursUntilStart(row) <= 12
}

/** 可以直接取消：待审核/冲突随时可取消，已通过则需距开始超过 12 小时 */
export function canCancelDirectly(row) {
  if (row.cancelRequested) return false
  if (row.status === 'pending' || row.status === 'conflict') return true
  return row.status === 'approved' && hoursUntilStart(row) > 12
}

/** 列表里的「原因/备注」：冲突说明、驳回理由、取消理由 */
export function bookingReason(row) {
  if (row.status === 'conflict') {
    return '与其他已通过的预约时段重叠，等待管理员协调保留哪一单。'
  }
  if (row.cancelRequested && row.status === 'approved') {
    return row.cancelReason ? `学生申请取消：${row.cancelReason}` : '学生已提交取消申请，等待管理员处理。'
  }
  if (row.status === 'rejected') return row.rejectReason || ''
  if (row.status === 'cancelled') return row.cancelReason || ''
  return ''
}

export { statusTagType, statusText }
