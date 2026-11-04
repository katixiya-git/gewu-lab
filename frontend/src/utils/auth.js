const AUTH_KEY = 'gewu:auth'
const REMEMBER_KEY = 'gewu:remember-username'

/** 读取当前登录信息，未登录返回 null */
export function getAuth() {
  try {
    return JSON.parse(localStorage.getItem(AUTH_KEY))
  } catch {
    return null
  }
}

/** 写入登录信息；role: 'student' | 'admin' */
export function setAuth({ role, name, username }) {
  localStorage.setItem(AUTH_KEY, JSON.stringify({ role, name, username }))
}

/** 退出登录 */
export function clearAuth() {
  localStorage.removeItem(AUTH_KEY)
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
