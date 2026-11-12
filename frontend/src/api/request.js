import { clearAuth, getToken } from '@/utils/auth'

const BASE_URL = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000'

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

/**
 * 统一请求入口：自动带 token、拆响应信封、401 清登录态。
 * 返回 Promise<data>，页面拿到的是信封里的 data，不用关心 code/message。
 */
export async function request(path, { method = 'GET', body, auth = true } = {}) {
  const headers = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'

  const token = getToken()
  if (auth && token) headers.Authorization = `Bearer ${token}`

  let response
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body)
    })
  } catch {
    throw new ApiError('无法连接服务器，请确认后端已启动')
  }

  let payload = null
  try {
    payload = await response.json()
  } catch {
    // 非 JSON 响应（如代理错误页）按 HTTP 状态处理
  }

  // 带着 token 还被拒，说明登录态失效：清掉并回登录页
  if (response.status === 401) {
    clearAuth()
    redirectToLogin()
  }

  if (!response.ok || payload?.code !== 200) {
    throw new ApiError(payload?.message || `请求失败（HTTP ${response.status}）`, {
      status: response.status,
      code: payload?.code ?? null,
      data: payload?.data ?? null
    })
  }

  return payload?.data ?? null
}
