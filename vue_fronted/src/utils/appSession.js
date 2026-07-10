/**
 * 会话与路由 — 刷新保登录、三端 session 槽位隔离
 * 纯函数可单测；异步校验见 userApi.requirePageAuth
 */

export const PUBLIC_PATH_PREFIXES = [
  '/pages/login/',
  '/pages/admin/login',
]

export const LAST_ROUTE_KEY = 'jnao_last_route' // legacy,不再写入

const LAST_ROUTE_KEYS = {
  admin: 'jnao_last_route_admin',
  parent: 'jnao_last_route_parent',
  student: 'jnao_last_route_student',
}

/** 路由是否属于指定登录端 */
export function routeMatchesAuthKind(route, kind) {
  const inferred = inferAuthKindFromPath(route)
  if (!inferred || !kind) return false
  return inferred === kind
}

function lastRouteKeyForKind(kind) {
  return LAST_ROUTE_KEYS[kind] || null
}

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
    return ['jnao_admin_user', 'jnao_admin_logged_in', 'jnao_admin_token']
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
      'jnao_parent_gate',
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

export const STORAGE_SCHEMA_VERSION = 3
export const STORAGE_VERSION_KEY = 'jnao_storage_schema'

/** 所有 auth 相关 localStorage 键（用于全量清理） */
export function allAuthStorageKeys() {
  const keys = new Set([
    STORAGE_VERSION_KEY,
    ...sessionKeysForKind('admin'),
    ...sessionKeysForKind('parent'),
    ...sessionKeysForKind('student'),
  ])
  return [...keys]
}

/** 清除全部登录态（用户自助 / 迁移） */
export function clearAllAuthSessions() {
  for (const key of allAuthStorageKeys()) {
    try { localStorage.removeItem(key) } catch (_) { /* ignore */ }
  }
  purgeLegacyRouteSnapshots()
}

function purgeLegacyRouteSnapshots() {
  try {
    sessionStorage.removeItem(LAST_ROUTE_KEY)
    for (const key of Object.values(LAST_ROUTE_KEYS)) {
      sessionStorage.removeItem(key)
    }
  } catch (_) { /* ignore */ }
}

/**
 * 修复 localStorage 中不一致的 session（孤儿 token、role 与槽位不符等）
 * @returns {string[]} 已清理项描述，便于调试
 */
export function repairAuthStorage() {
  const fixed = []
  const snap = readAuthSnapshot()

  purgeLegacyRouteSnapshots()

  const adminRaw = defaultGetItem('jnao_admin_user')
  const adminTok = defaultGetItem('jnao_admin_token')
  if (adminTok && !adminRaw) {
    for (const key of sessionKeysForKind('admin')) {
      try { localStorage.removeItem(key) } catch (_) { /* ignore */ }
    }
    fixed.push('orphan_admin_token')
  }
  if (adminRaw && !adminTok) {
    for (const key of sessionKeysForKind('admin')) {
      try { localStorage.removeItem(key) } catch (_) { /* ignore */ }
    }
    fixed.push('orphan_admin_user')
  }

  const userTok = defaultGetItem('jnao_session_token')
  const loggedIn = defaultGetItem('jnao_logged_in') === '1'
  const schemaV3 = parseInt(defaultGetItem(STORAGE_VERSION_KEY) || '0', 10) >= STORAGE_SCHEMA_VERSION
  let role = snap.role
  let userId = snap.parent?.userId || snap.student?.userId || null
  if (!role || !userId) {
    try {
      const raw = defaultGetItem('jnao_user')
      if (raw) {
        const u = JSON.parse(raw)
        if (!role) role = u.role
        if (!userId && u.id) userId = Number(u.id)
      }
    } catch (_) { /* ignore */ }
  }
  if (!userId) {
    const childRaw = defaultGetItem('jnao_child_user_id')
    if (childRaw) userId = parseInt(childRaw, 10) || null
  }

  // v3：HttpOnly Cookie，本地无 token 仍可为有效登录态
  if (loggedIn && (!role || !userId)) {
    for (const key of sessionKeysForKind('parent')) {
      try { localStorage.removeItem(key) } catch (_) { /* ignore */ }
    }
    for (const key of sessionKeysForKind('student')) {
      try { localStorage.removeItem(key) } catch (_) { /* ignore */ }
    }
    fixed.push('logged_in_without_identity')
  } else if (loggedIn && !userTok && !schemaV3) {
    for (const key of sessionKeysForKind('parent')) {
      try { localStorage.removeItem(key) } catch (_) { /* ignore */ }
    }
    for (const key of sessionKeysForKind('student')) {
      try { localStorage.removeItem(key) } catch (_) { /* ignore */ }
    }
    fixed.push('logged_in_without_session')
  }

  if (userTok && role === 'parent' && !snap.parent) {
    for (const key of sessionKeysForKind('student')) {
      try { localStorage.removeItem(key) } catch (_) { /* ignore */ }
    }
    fixed.push('parent_role_slot_repair')
  }
  if (userTok && role === 'student' && !snap.student) {
    for (const key of sessionKeysForKind('parent')) {
      try { localStorage.removeItem(key) } catch (_) { /* ignore */ }
    }
    fixed.push('student_role_slot_repair')
  }

  // 三端 token 同时存在时只保留与当前页面匹配的一端
  const { route } = getCurrentAppPath()
  const pageKind = inferAuthKindFromPath(route)
  if (pageKind === 'parent' || pageKind === 'student') {
    if (snap.admin) {
      for (const key of sessionKeysForKind('admin')) {
        try { localStorage.removeItem(key) } catch (_) { /* ignore */ }
      }
      fixed.push('admin_on_user_page')
    }
  } else if (pageKind === 'admin' && (snap.parent || snap.student)) {
    clearSessionsExcept('admin')
    fixed.push('user_on_admin_page')
  }

  return fixed
}

/** App 启动 / 版本升级时迁移 storage，避免旧结构长期干扰 */
export function migrateAuthStorage() {
  try {
    const prev = parseInt(defaultGetItem(STORAGE_VERSION_KEY) || '0', 10)
      if (prev < STORAGE_SCHEMA_VERSION) {
        purgeLegacyRouteSnapshots()
        try {
          localStorage.removeItem('jnao_session_token')
          localStorage.removeItem('jnao_admin_token')
        } catch (_) { /* ignore */ }
        if (prev === 0) {
        // v0：历史上 admin 与 user 共用跳转键、登录互不清 session
        repairAuthStorage()
      }
      localStorage.setItem(STORAGE_VERSION_KEY, String(STORAGE_SCHEMA_VERSION))
      return { migrated: true, from: prev, to: STORAGE_SCHEMA_VERSION }
    }
    repairAuthStorage()
    return { migrated: false, version: prev }
  } catch (_) {
    return { migrated: false, error: true }
  }
}

/**
 * 进入公开登录页时剥离「不该出现在此入口」的 session
 * - 用户登录页：去掉管理员残留
 * - 管理员登录页：去掉家长/学生残留
 */
export function sanitizeAuthForLoginEntry(path) {
  const p = normalizePath(path)
  if (p.startsWith('/pages/admin/login')) {
    clearSessionsExcept('admin')
    return 'admin_login'
  }
  if (p.startsWith('/pages/login/') || p === '/pages/login/index') {
    for (const key of sessionKeysForKind('admin')) {
      try { localStorage.removeItem(key) } catch (_) { /* ignore */ }
    }
    purgeLegacyRouteSnapshots()
    return 'user_login'
  }
  return null
}

/** 多标签页：其它 tab 清 session 时同步失效内存校验缓存 */
export function installAuthStorageSync(onExternalChange) {
  if (typeof window === 'undefined' || window.__jnaoAuthStorageSync) return () => {}
  const handler = (ev) => {
    if (!ev.key || !ev.key.startsWith('jnao_')) return
    onExternalChange?.(ev.key)
  }
  window.addEventListener('storage', handler)
  window.__jnaoAuthStorageSync = true
  return () => window.removeEventListener('storage', handler)
}

/**
 * @param {(key: string) => string|null} [getItem]
 */
export function readAuthSnapshot(getItem) {
  const get = getItem || defaultGetItem

  let admin = null
  const adminRaw = get('jnao_admin_user')
  const adminLoggedIn = get('jnao_admin_logged_in') === '1'
  if (adminRaw && adminLoggedIn) {
    try {
      const a = JSON.parse(adminRaw)
      if (a?.id) admin = { userId: Number(a.id), active: true }
    } catch (_) { /* ignore */ }
  }

  const loggedIn = get('jnao_logged_in') === '1'
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
  if (loggedIn) {
    if (role === 'parent') {
      const pid = parentSlotId || userId
      if (pid) parent = { userId: pid, active: true }
    } else if (role === 'student') {
      const sid = studentSlotId || userId
      if (sid) student = { userId: sid, active: true }
    }
  }

  return {
    admin,
    parent,
    student,
    loggedIn,
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
    const kind = inferAuthKindFromPath(route)
    if (!kind) return
    const key = lastRouteKeyForKind(kind)
    if (!key) return
    const q = String(query || '').replace(/^\?/, '')
    sessionStorage.setItem(key, JSON.stringify({ route, query: q }))
  } catch (_) { /* ignore */ }
}

export function readRouteSnapshot(kind = null) {
  try {
    if (kind) {
      const key = lastRouteKeyForKind(kind)
      if (!key) return null
      const raw = sessionStorage.getItem(key)
      if (!raw) return null
      const snap = JSON.parse(raw)
      if (snap?.route && routeMatchesAuthKind(snap.route, kind)) return snap
      return null
    }
    // legacy fallback — 仅兼容旧数据，且必须能推断出 kind
    const raw = sessionStorage.getItem(LAST_ROUTE_KEY)
    if (!raw) return null
    const snap = JSON.parse(raw)
    if (!snap?.route) return null
    const inferred = inferAuthKindFromPath(snap.route)
    if (!inferred || !routeMatchesAuthKind(snap.route, inferred)) return null
    return snap
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

/** 登录成功后恢复刷新前页面；仅恢复与当前登录端一致的路由 */
export function consumePostLoginRoute(fallbackUrl, kind) {
  if (!kind) return fallbackUrl
  const snap = readRouteSnapshot(kind)
  if (!snap?.route || isPublicPath(snap.route)) return fallbackUrl
  if (!routeMatchesAuthKind(snap.route, kind)) return fallbackUrl
  try {
    const key = lastRouteKeyForKind(kind)
    if (key) sessionStorage.removeItem(key)
    sessionStorage.removeItem(LAST_ROUTE_KEY)
  } catch (_) { /* ignore */ }
  return routeToUrl(snap.route, snap.query)
}

/** 从某一端切到登录页前，清除其它端与共享 token，避免家长 session 把学生带进家长页 */
export function prepareRoleLoginEntry(targetRole) {
  const role = (targetRole || '').trim().toLowerCase()
  if (role !== 'student' && role !== 'parent') return
  for (const k of ['parent', 'student']) {
    for (const key of sessionKeysForKind(k)) {
      try { localStorage.removeItem(key) } catch (_) { /* ignore */ }
    }
  }
  for (const key of ['jnao_user', 'jnao_session_token', 'jnao_logged_in', 'jnao_child_user_id', 'jnao_login_channel']) {
    try { localStorage.removeItem(key) } catch (_) { /* ignore */ }
  }
  purgeLegacyRouteSnapshots()
}

/** 登录某一端时清除其它端的 session，避免串号 */
export function clearSessionsExcept(kind) {
  for (const k of ['admin', 'parent', 'student']) {
    if (k === kind) continue
    for (const key of sessionKeysForKind(k)) {
      try { localStorage.removeItem(key) } catch (_) { /* ignore */ }
    }
  }
  if (kind !== 'student' && kind !== 'parent') {
    try {
      localStorage.removeItem('jnao_logged_in')
    } catch (_) { /* ignore */ }
  }
  purgeLegacyRouteSnapshots()
}
