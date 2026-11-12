import axios from 'axios'

import { clearAuth, getToken } from '@/utils/auth'

/**
 * 开发期 baseURL 走 Vite 代理（/api -> 127.0.0.1:8000），浏览器看到的是同源请求，不触发跨域；
 * 部署时可用 VITE_API_BASE 覆盖成完整地址。
 */
const baseURL = import.meta.env.VITE_API_BASE || '/api'

export class ApiError extends Error {
  constructor(message, { status = 0, code = null, data = null } = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.data = data
  }
}

function redirectToLogin() {
  if (typeof window === 'undefined') return
  const { pathname, search, hash } = window.location
  if (pathname === '/login') return
  const redirect = encodeURIComponent(pathname + search + hash)
  window.location.replace(`/login?redirect=${redirect}`)
}

const http = axios.create({
  baseURL,
  timeout: 10000
})

// 请求拦截：自动带上 JWT；登录这类接口传 { auth: false } 跳过
http.interceptors.request.use((config) => {
  if (config.auth !== false) {
    const token = getToken()
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
  }
  return config
})

// 响应拦截：拆 Result 信封，统一错误消息，401 清登录态
http.interceptors.response.use(
  (response) => {
    const body = response.data
    if (body && typeof body.code === 'number' && body.code !== 200) {
      return Promise.reject(
        new ApiError(body.message || '请求失败', {
          status: response.status,
          code: body.code,
          data: body.data
        })
      )
    }
    return body?.data ?? body
  },
  (error) => {
    const status = error.response?.status ?? 0
    const body = error.response?.data

    let message = body?.message
    if (!message) {
      if (status === 0) {
        message =
          error.code === 'ECONNABORTED' ? '请求超时，请稍后重试' : '无法连接服务器，请确认后端已启动'
      } else {
        message = `请求失败（HTTP ${status}）`
      }
    }

    if (status === 401) {
      clearAuth()
      redirectToLogin()
    }

    return Promise.reject(
      new ApiError(message, {
        status,
        code: body?.code ?? null,
        data: body?.data ?? null
      })
    )
  }
)

export default http
