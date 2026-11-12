const TOKEN_KEY = 'gewu:token'
const USER_KEY = 'gewu:user'
const REMEMBER_KEY = 'gewu:remember-username'

/** 读取 JWT，未登录返回空字符串 */
export function getToken() {
  return localStorage.getItem(TOKEN_KEY) || ''
}

/** 读取当前用户（后端 UserOut 结构），未登录返回 null */
export function getUser() {
  try {
    return JSON.parse(localStorage.getItem(USER_KEY))
  } catch {
    return null
  }
}

/** 登录成功后写入 token 与用户信息 */
export function setAuth({ token, user }) {
  if (token) localStorage.setItem(TOKEN_KEY, token)
  if (user) localStorage.setItem(USER_KEY, JSON.stringify(user))
}

/** 退出登录 / token 失效时清理 */
export function clearAuth() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
}

export function getRememberedUsername() {
  return localStorage.getItem(REMEMBER_KEY) || ''
}

export function setRememberedUsername(username) {
  if (username) {
    localStorage.setItem(REMEMBER_KEY, username)
  } else {
    localStorage.removeItem(REMEMBER_KEY)
  }
}
