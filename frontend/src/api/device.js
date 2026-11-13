import http from './request'

/** 分页查询设备：学生只能看到启用实验室下、非停用的设备 */
export function pageDevices(params) {
  return http.get('/devices/page', { params })
}

/** 设备详情（学生访问停用实验室/停用设备会 404） */
export function fetchDevice(id) {
  return http.get(`/devices/${id}`)
}

/** 管理员新增设备 */
export function createDevice(data) {
  return http.post('/devices', data)
}

/** 管理员编辑设备，只传需要修改的字段 */
export function updateDevice(id, data) {
  return http.put(`/devices/${id}`, data)
}

/** 管理员切换设备状态：normal / maintenance / disabled */
export function changeDeviceStatus(id, status) {
  return http.put(`/devices/${id}/status`, { status })
}

/** 管理员删除设备 */
export function deleteDevice(id) {
  return http.delete(`/devices/${id}`)
}
