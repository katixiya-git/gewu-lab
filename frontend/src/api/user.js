import http from './request'

/** 分页查询用户：keyword 模糊匹配用户名/姓名/手机号/邮箱 */
export function pageUsers(params) {
  return http.get('/users/page', { params })
}

/** 管理员新增用户 */
export function createUser(data) {
  return http.post('/users', data)
}

/** 管理员编辑用户（只传需要修改的字段） */
export function updateUser(id, data) {
  return http.put(`/users/${id}`, data)
}

/** 管理员删除用户 */
export function deleteUser(id) {
  return http.delete(`/users/${id}`)
}
