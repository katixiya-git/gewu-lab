import { request } from './request'

/** 登录：返回 { accessToken, tokenType, user } */
export function login(payload) {
  return request('/api/auth/login', { method: 'POST', body: payload, auth: false })
}

/** 当前登录用户：token 失效会抛 ApiError（401） */
export function fetchMe() {
  return request('/api/auth/me')
}
