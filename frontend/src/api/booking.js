import http from './request'

/** 分页查询预约：学生只看自己，管理员可按状态/实验室/关键字筛选 */
export function pageBookings(params) {
  return http.get('/bookings/page', { params })
}

/** 预约详情 */
export function fetchBooking(id) {
  return http.get(`/bookings/${id}`)
}

/** 学生提交预约 */
export function createBooking(data) {
  return http.post('/bookings', data)
}

/** 管理员审核：通过 / 驳回 */
export function reviewBooking(id, data) {
  return http.post(`/bookings/${id}/review`, data)
}

/** 直接取消预约（学生本人或管理员） */
export function cancelBooking(id, reason) {
  return http.post(`/bookings/${id}/cancel`, { reason })
}

/** 学生提交取消申请（距开始不足 12 小时） */
export function requestCancelBooking(id, reason) {
  return http.post(`/bookings/${id}/cancel-request`, { reason })
}

/** 管理员处理取消申请 */
export function reviewCancelBooking(id, data) {
  return http.post(`/bookings/${id}/cancel-review`, data)
}
