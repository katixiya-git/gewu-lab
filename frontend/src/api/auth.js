import http from './request'

/** 登录：返回 { accessToken, tokenType, user }；登录接口不需要 token */
export function login(payload) {
  return http.post('/auth/login', payload, { auth: false })
}

/** 当前登录用户：token 失效会抛 ApiError（401） */
export function fetchMe() {
  return http.get('/auth/me')
}
