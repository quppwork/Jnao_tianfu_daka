/**
 * 会话与路由 — 刷新保登录、三端 session 槽位隔离
 * 纯函数可单测；异步校验见 userApi.requirePageAuth
 */

export const PUBLIC_PATH_PREFIXES = [
  '/pages/login/',
  '/pages/admin/login',
]

export const LAST_ROUTE_KEY = 'jnao_last_route'

export function normalizePath(path) {
  let p = String(path || '').trim()
  if (!p) return '/'
  const hashIdx = p.indexOf('#')
  if (hashIdx >= 0) p = p.slice(hashIdx + 1)
  if (!p.startsWith('/')) p = `/${p}`
  return p.split('?')[0]
}

export function isPublicPath(path) {
  const p = normalizePath(path)
  return PUBLIC_PATH_PREFIXES.some((prefix) => p.startsWith(prefix))
}

/** @returns {'admin'|'parent'|'student'|null} */
export function inferAuthKindFromPath(path) {
  const p = normalizePath(path)
  if (isPublicPath(p)) return null
  if (p.startsWith('/pages/admin/')) return 'admin'
  if (p.startsWith('/pages/parent/')) return 'parent'
  return 'student'
}

export function sessionKeysForKind(kind) {
  if (kind === 'admin') {
    return ['jnao_admin_user', 'jnao_admin_token']
  }
  if (kind === 'parent') {
    return [
      'jnao_parent_user_id',
      'jnao_child_user_id',
      'jnao_session_token',
      'jnao_user',
      'jnao_logged_in',
      'jnao_login_channel',
      'jnao_guest_phone',
      'jnao_guest_nickname',
    ]
  }
  return [
    'jnao_student_user_id',
    'jnao_child_user_id',
    'jnao_session_token',
    'jnao_user',
    'jnao_logged_in',
    'jnao_login_channel',
    'jnao_guest_phone',
    'jnao_guest_nickname',
  ]
}

/**
 * @param {(key: string) => string|null} [getItem]
 */
export function readAuthSnapshot(getItem) {
  const get = getItem || defaultGetItem

  let admin = null
  const adminRaw = get('jnao_admin_user')
  if (adminRaw) {
    try {
      const a = JSON.parse(adminRaw)
      const token = get('jnao_admin_token') || ''
      if (a?.id && token) admin = { userId: Number(a.id), token }
    } catch (_) { /* ignore */ }
  }

  const token = get('jnao_session_token') || ''
  let userId = null
  const childRaw = get('jnao_child_user_id')
  if (childRaw) userId = parseInt(childRaw, 10)

  let role = null
  const userRaw = get('jnao_user')
  if (userRaw) {
    try {
      const u = JSON.parse(userRaw)
      role = u.role || null
      if (!userId && u.id) userId = Number(u.id)
    } catch (_) { /* ignore */ }
  }

  let parent = null
  let student = null
  const parentSlotId = parseInt(get('jnao_parent_user_id') || '', 10) || null
  const studentSlotId = parseInt(get('jnao_student_user_id') || '', 10) || null
  if (token) {
    if (role === 'parent') {
      const pid = parentSlotId || userId
      if (pid) parent = { userId: pid, token }
    } else if (role === 'student') {
      const sid = studentSlotId || userId
      if (sid) student = { userId: sid, token }
    }
  }

  return {
    admin,
    parent,
    student,
    loggedIn: get('jnao_logged_in') === '1',
    role,
  }
}

function defaultGetItem(key) {
  try {
    return localStorage.getItem(key)
  } catch (_) {
    return null
  }
}

export function isTransientError(status) {
  const s = Number(status)
  return !s || s === 408 || s === 429 || s >= 502
}

export function isAuthExpiredError(status) {
  return Number(status) === 401
}

export function shouldLogoutOnError(err) {
  return isAuthExpiredError(err?.status)
}

export function saveRouteSnapshot(path, query = '') {
  try {
    const route = normalizePath(path)
    if (isPublicPath(route)) return
    const q = String(query || '').replace(/^\?/, '')
    sessionStorage.setItem(LAST_ROUTE_KEY, JSON.stringify({ route, query: q }))
  } catch (_) { /* ignore */ }
}

export function readRouteSnapshot() {
  try {
    const raw = sessionStorage.getItem(LAST_ROUTE_KEY)
    if (!raw) return null
    return JSON.parse(raw)
  } catch (_) {
    return null
  }
}

export function getCurrentAppPath() {
  try {
    const pages = typeof getCurrentPages === 'function' ? getCurrentPages() : []
    const cur = pages[pages.length - 1]
    if (cur?.route) {
      const route = cur.route.startsWith('/') ? cur.route : `/${cur.route}`
      const q = cur.options
        ? Object.entries(cur.options)
            .map(([k, v]) => `${k}=${encodeURIComponent(v)}`)
            .join('&')
        : ''
      return { route, query: q }
    }
  } catch (_) { /* ignore */ }
  try {
    return { route: normalizePath(window.location.hash || window.location.pathname), query: '' }
  } catch (_) {
    return { route: '/', query: '' }
  }
}

export function rememberCurrentRoute() {
  const { route, query } = getCurrentAppPath()
  saveRouteSnapshot(route, query)
}

export function routeToUrl(route, query = '') {
  const q = String(query || '').replace(/^\?/, '')
  return q ? `${route}?${q}` : route
}

/** 登录成功后恢复刷新前页面（F11） */
export function consumePostLoginRoute(fallbackUrl) {
  const snap = readRouteSnapshot()
  if (!snap?.route || isPublicPath(snap.route)) return fallbackUrl
  try {
    sessionStorage.removeItem(LAST_ROUTE_KEY)
  } catch (_) { /* ignore */ }
  return routeToUrl(snap.route, snap.query)
}
