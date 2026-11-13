import http from './request'

/** 分页查询实验室：学生只会拿到 enabled 的，管理员可按状态/类型筛选 */
export function pageLabs(params) {
  return http.get('/labs/page', { params })
}

/** 实验室详情（学生访问停用实验室会 404） */
export function fetchLab(id) {
  return http.get(`/labs/${id}`)
}

/** 管理员新增实验室 */
export function createLab(data) {
  return http.post('/labs', data)
}

/** 管理员编辑实验室，只传需要修改的字段 */
export function updateLab(id, data) {
  return http.put(`/labs/${id}`, data)
}

/** 管理员启用/停用实验室 */
export function changeLabStatus(id, status) {
  return http.put(`/labs/${id}/status`, { status })
}

/** 管理员删除实验室 */
export function deleteLab(id) {
  return http.delete(`/labs/${id}`)
}
