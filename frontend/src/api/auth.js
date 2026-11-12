import http from './request'

/** 登录：返回 { accessToken, tokenType, user }；登录接口不需要 token */
export function login(payload) {
  return http.post('/auth/login', payload, { auth: false })
}

/** 当前登录用户：token 失效会抛 ApiError（401） */
export function fetchMe() {
  return http.get('/auth/me')
}

/** 学生注册：成功即返回 { accessToken, tokenType, user }，等价于登录 */
export function register(payload) {
  return http.post('/auth/register', payload, { auth: false })
}

/** 更新个人资料：姓名、手机号、邮箱、头像；返回最新用户信息 */
export function updateProfile(payload) {
  return http.put('/auth/me', payload)
}
