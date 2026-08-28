/**
 * API 底座 — session 键 + HTTP（域模块唯一依赖，禁止再依赖 userApi / 其它域）
 *
 * 依赖方向（无环）:
 *   api/client.js
 *     ↑
 *   api/{training,guide,qa,...}.js
 *     ↑
 *   userApi.js（聚合导出）
 *   api/{auth,parent,admin}.js → userApiCore.js（兼容）→ userApi.js
 */
import { getQaImageLocal, parseQaImageId } from '../qaMedia.js'
import { authHeaders } from '../loginGuard.js'
import { clearBrowserLoginPreference } from '../wechatAuth.js'
import { applyDevBootReloginIfNeeded } from '../devBootAuth.js'
import {
  inferAuthKindFromPath,
  readAuthSnapshot,
  isTransientError,
  isAuthExpiredError,
  sessionKeysForKind,
  rememberCurrentRoute,
  getCurrentAppPath,
  clearSessionsExcept,
  migrateAuthStorage,
  clearAllAuthSessions,
  prepareRoleLoginEntry,
} from '../appSession.js'

const CHILD_KEY = 'jnao_child_user_id'
const PARENT_SLOT_KEY = 'jnao_parent_user_id'
const STUDENT_SLOT_KEY = 'jnao_student_user_id'
const GUEST_PHONE_KEY = 'jnao_guest_phone'
const GUEST_NICKNAME_KEY = 'jnao_guest_nickname'
const SESSION_TOKEN_KEY = 'jnao_session_token' // legacy，迁移后不再写入
const ADMIN_USER_KEY = 'jnao_admin_user'
const ADMIN_LOGGED_IN_KEY = 'jnao_admin_logged_in'
const FRESH_LOGIN_KEY = 'jnao_fresh_login_until'
const FRESH_LOGIN_MS = 20000

export function getAdminUserId() {
  try {
    const raw = localStorage.getItem(ADMIN_USER_KEY)
    if (raw) return JSON.parse(raw).id
  } catch (_) { /* ignore */ }
  return null
}

export function getAdminSessionToken() {
  return ''
}

export function hasAdminSession() {
  try {
    return localStorage.getItem(ADMIN_LOGGED_IN_KEY) === '1' && !!getAdminUserId()
  } catch (_) {
    return false
  }
}

export function clearAdminSession() {
  clearSessionForKind('admin')
}

/** 写入管理员本地 session（登录成功后调用） */
export function persistAdminLocalSession(data) {
  localStorage.setItem(ADMIN_USER_KEY, JSON.stringify({
    id: data.child_user_id,
    name: data.nickname,
    role: 'admin',
    loginName: data.login_name,
  }))
  try { localStorage.setItem(ADMIN_LOGGED_IN_KEY, '1') } catch (_) { /* ignore */ }
  invalidatePageAuthCache('admin')
  markPageAuthValidated('admin', data.child_user_id)
}

/** 刚完成登录后的宽限期：Cookie 写入前避免 401 误踢回登录页 */
export function markFreshLogin() {
  try {
    sessionStorage.setItem(FRESH_LOGIN_KEY, String(Date.now() + FRESH_LOGIN_MS))
  } catch (_) { /* ignore */ }
}

export function isFreshLogin() {
  try {
    const until = parseInt(sessionStorage.getItem(FRESH_LOGIN_KEY) || '0', 10)
    return until > Date.now()
  } catch (_) {
    return false
  }
}

function clearFreshLogin() {
  try {
    sessionStorage.removeItem(FRESH_LOGIN_KEY)
  } catch (_) { /* ignore */ }
}

/** 读取当前登录的 child_user_id（活跃会话槽），无则返回 null */
export function getChildUserId() {
  try {
    const raw = localStorage.getItem(CHILD_KEY)
    if (raw) return parseInt(raw, 10)
  } catch (e) { /* ignore */ }
  return null
}

/** 家长身份 id：优先独立槽 jnao_parent_user_id，再读 auth 快照 */
export function getParentUserId() {
  try {
    const raw = localStorage.getItem(PARENT_SLOT_KEY)
    if (raw) {
      const n = parseInt(raw, 10)
      if (n) return n
    }
  } catch (_) { /* ignore */ }
  const snap = readAuthSnapshot()
  return snap.parent?.userId || null
}

/** 学生身份 id：优先 jnao_student_user_id / 快照，兼容 CHILD_KEY */
export function getStudentUserId() {
  try {
    const raw = localStorage.getItem(STUDENT_SLOT_KEY)
    if (raw) {
      const n = parseInt(raw, 10)
      if (n) return n
    }
  } catch (_) { /* ignore */ }
  const snap = readAuthSnapshot()
  if (snap.student?.userId) return snap.student.userId
  if (snap.role === 'student') return getChildUserId()
  return null
}

/** 当前登录用户 id（家长/学生），优先 CHILD_KEY，否则 jnao_user */
export function getLoggedInUserId() {
  const cid = getChildUserId()
  if (cid) return cid
  try {
    const raw = localStorage.getItem('jnao_user')
    if (raw) {
      const u = JSON.parse(raw)
      if (u?.id) return parseInt(u.id, 10)
    }
  } catch (e) { /* ignore */ }
  return null
}

/** 退出登录并回到登录页 */
export function logoutAndGoLogin(targetUrl = '/pages/login/index') {
  clearBrowserLoginPreference()
  logoutSession('parent').finally(() => {
    logoutSession('student').finally(() => {
      clearFreshLogin()
      try {
        uni.reLaunch({ url: targetUrl })
      } catch (e) {
        window.location.href = targetUrl
      }
    })
  })
}

export function logoutAdminAndGoLogin() {
  logoutSession('admin').finally(() => {
    try {
      uni.redirectTo({ url: '/pages/admin/login' })
    } catch (e) {
      window.location.href = '/pages/admin/login'
    }
  })
}

export async function logoutSession(kind) {
  try {
    if (kind === 'admin') {
      await apiJson('/api/admin/logout', { method: 'POST' })
    } else if (kind === 'parent' || kind === 'student') {
      await apiJson('/api/auth/logout', { method: 'POST' })
    }
  } catch (_) { /* ignore */ }
  clearSessionForKind(kind)
}

export function clearSessionForKind(kind) {
  for (const key of sessionKeysForKind(kind)) {
    try {
      localStorage.removeItem(key)
    } catch (e) { /* ignore */ }
  }
  if (kind === 'student' || kind === 'parent') {
    invalidateChildUserSession()
  }
}

export function redirectToLoginForKind(kind) {
  if (kind === 'admin') {
    logoutAdminAndGoLogin()
    return
  }
  const url = kind === 'student' ? '/pages/login/index?role=student' : '/pages/login/index'
  const msg = kind === 'student' ? '请先登录孩子账号' : '登录已失效，请重新登录'
  try {
    uni.showToast({ title: msg, icon: 'none', duration: 2500 })
  } catch (_) { /* ignore */ }
  logoutAndGoLogin(url)
}

const _authValidatedAt = { admin: 0, parent: 0, student: 0 }
const _authValidatedUid = { admin: null, parent: null, student: null }
const AUTH_VALIDATE_TTL = 60 * 1000

export function invalidatePageAuthCache(kind = null) {
  const kinds = kind ? [kind] : ['admin', 'parent', 'student']
  for (const k of kinds) {
    _authValidatedAt[k] = 0
    _authValidatedUid[k] = null
  }
}

/** 登录成功后标记本页 auth 已校验，避免立刻再打 /me */
export function markPageAuthValidated(kind, userId) {
  _authValidatedUid[kind] = userId
  _authValidatedAt[kind] = Date.now()
}

/** 页面进入前校验 session；网络异常允许离线继续，仅 401 才登出 */
export async function requirePageAuth(kind) {
  const snap = readAuthSnapshot()
  const session = kind === 'admin' ? snap.admin : kind === 'parent' ? snap.parent : snap.student

  if (!session?.userId) {
    if (kind === 'student' && snap.parent?.userId) {
      prepareRoleLoginEntry('student')
      try { uni.reLaunch({ url: '/pages/login/index?role=student' }) } catch (_) { /* ignore */ }
      return { ok: false, reason: 'wrong_role' }
    }
    if (kind === 'parent' && snap.student?.userId) {
      try { uni.reLaunch({ url: '/pages/index' }) } catch (_) { /* ignore */ }
      return { ok: false, reason: 'wrong_role' }
    }
    redirectToLoginForKind(kind)
    return { ok: false, reason: 'missing_local' }
  }

  if (
    _authValidatedUid[kind] === session.userId
    && (Date.now() - _authValidatedAt[kind]) < AUTH_VALIDATE_TTL
  ) {
    if (kind === 'student') markChildUserSessionValid(session.userId)
    return { ok: true, userId: session.userId }
  }

  try {
    if (kind === 'admin') {
      await apiJson(withAdmin('/api/admin/settings', session.userId))
    } else if (kind === 'parent') {
      await apiJson(withUser('/api/parent/profile', session.userId))
    } else {
      await apiJson(withUser('/api/user/profile', session.userId))
    }
    _authValidatedUid[kind] = session.userId
    _authValidatedAt[kind] = Date.now()
    if (kind === 'student') markChildUserSessionValid(session.userId)
    return { ok: true, userId: session.userId }
  } catch (e) {
    if (isTransientError(e.status)) {
      _authValidatedUid[kind] = session.userId
      _authValidatedAt[kind] = Date.now()
      if (kind === 'student') markChildUserSessionValid(session.userId)
      return { ok: true, userId: session.userId, offline: true }
    }
    if (isAuthExpiredError(e.status)) {
      if (isFreshLogin()) {
        return { ok: true, userId: session.userId, fresh: true }
      }
      clearSessionForKind(kind)
      clearFreshLogin()
      redirectToLoginForKind(kind)
      return { ok: false, reason: 'expired' }
    }
    if (e.status === 403) {
      const snap = readAuthSnapshot()
      let role = snap.role
      try {
        const raw = localStorage.getItem('jnao_user')
        if (raw) role = JSON.parse(raw).role || role
      } catch (_) { /* ignore */ }
      if (kind === 'student' && (role === 'parent' || snap.parent?.userId)) {
        try { uni.reLaunch({ url: '/pages/parent/index' }) } catch (_) { /* ignore */ }
        return { ok: false, reason: 'wrong_role' }
      }
      if (kind === 'parent' && role === 'student') {
        try { uni.reLaunch({ url: '/pages/index' }) } catch (_) { /* ignore */ }
        return { ok: false, reason: 'wrong_role' }
      }
      redirectToLoginForKind(kind)
      return { ok: false, reason: 'forbidden' }
    }
    _authValidatedUid[kind] = session.userId
    _authValidatedAt[kind] = Date.now()
    if (kind === 'student') markChildUserSessionValid(session.userId)
    return { ok: true, userId: session.userId, offline: true }
  }
}

/** App 启动：开发态对齐 boot_id → 迁移 storage → 静默校验当前页 session */
export async function bootstrapAppSession() {
  const boot = await applyDevBootReloginIfNeeded()
  if (boot.cleared) {
    invalidatePageAuthCache()
    invalidateChildUserSession()
    resetSessionExpiryGuard()
  }
  migrateAuthStorage()
  rememberCurrentRoute()
  const { route } = getCurrentAppPath()
  const kind = inferAuthKindFromPath(route)
  if (!kind) return { ok: true, skipped: true, bootCleared: !!boot.cleared }
  const auth = await requirePageAuth(kind)
  return { ...auth, bootCleared: !!boot.cleared }
}

/** 登录异常时一键清除本机全部登录缓存（无需清整个站点数据） */
export function resetLocalAuthCache() {
  clearAllAuthSessions()
  invalidatePageAuthCache()
  invalidateChildUserSession()
  resetSessionExpiryGuard()
}

export function setChildUserId(id) {
  try {
    localStorage.setItem(CHILD_KEY, String(id))
  } catch (e) { /* ignore */ }
}

export function clearChildUserId() {
  try {
    localStorage.removeItem(CHILD_KEY)
    localStorage.removeItem(GUEST_PHONE_KEY)
    localStorage.removeItem(GUEST_NICKNAME_KEY)
    localStorage.removeItem(SESSION_TOKEN_KEY)
  } catch (e) { /* ignore */ }
  invalidateChildUserSession()
  invalidatePageAuthCache('student')
  invalidatePageAuthCache('parent')
}

/** 是否已有用户端登录态（Cookie + local 标记） */
export function hasUserSession() {
  try {
    return localStorage.getItem('jnao_logged_in') === '1' && !!getLoggedInUserId()
  } catch (e) { return false }
}

/** 读取 session_token（HttpOnly Cookie 模式下恒为空，保留兼容） */
export function getSessionToken() {
  return ''
}

/** 不再向 localStorage 存 token */
export function setSessionToken(_token) {
  /* HttpOnly Cookie 由服务端 Set-Cookie */
}

/** 会话内已验证 uid，避免重复 ping /api/user/profile */
let _sessionValidatedUid = null
let _sessionValidatedAt = 0
let _validateInFlight = null
const SESSION_VALID_TTL = 5 * 60 * 1000  // 5 分钟，防止缓存过期 session

export function invalidateChildUserSession() {
  _sessionValidatedUid = null
  _sessionValidatedAt = 0
  _validateInFlight = null
}

export function markChildUserSessionValid(uid) {
  if (uid) {
    _sessionValidatedUid = uid
    _sessionValidatedAt = Date.now()
  }
}

const AUTH_ATTEMPT_PREFIXES = [
  '/api/auth/login',
  '/api/auth/sms/',
  '/api/auth/register',
  '/api/auth/wechat/exchange',
  '/api/admin/login',
]

function isAuthAttemptRequest(url) {
  const path = String(url || '').split('?')[0]
  return AUTH_ATTEMPT_PREFIXES.some((p) => path === p || path.startsWith(p))
}

function inferAuthKindFromUrl(url) {
  if (String(url).includes('/api/admin/')) return 'admin'
  if (String(url).includes('/api/parent/')) return 'parent'
  return 'student'
}

let _sessionExpiryHandled = false

export function resetSessionExpiryGuard() {
  _sessionExpiryHandled = false
}

function handleMidSessionExpired(url) {
  if (_sessionExpiryHandled || isAuthAttemptRequest(url)) return
  if (isFreshLogin()) return
  const kind = inferAuthKindFromUrl(url)
  const hasSession = kind === 'admin'
    ? (localStorage.getItem(ADMIN_LOGGED_IN_KEY) === '1' && !!getAdminUserId())
    : hasUserSession()
  if (!hasSession) return
  _sessionExpiryHandled = true
  invalidatePageAuthCache(kind)
  clearSessionForKind(kind)
  try {
    uni.showToast({ title: '登录已失效，请重新登录', icon: 'none' })
  } catch (_) { /* ignore */ }
  setTimeout(() => redirectToLoginForKind(kind), 400)
}
function formatApiError(data, status) {
  const d = data?.detail ?? data?.message
  if (typeof d === 'string' && d.trim()) return d
  if (Array.isArray(d)) {
    const parts = d.map((x) => x?.msg || x?.message).filter(Boolean)
    if (parts.length) return parts.join('；')
  }
  return `HTTP ${status}`
}

export async function apiJson(url, options = {}) {
  const { timeoutMs, signal: userSignal, ...fetchOptions } = options
  const userId = extractUserIdFromUrl(url)
  const headers = mergeAuthHeaders({ ...fetchOptions, _url: url }, userId)
  const ctrl = timeoutMs ? new AbortController() : null
  if (ctrl && userSignal) {
    if (userSignal.aborted) ctrl.abort()
    else userSignal.addEventListener('abort', () => ctrl.abort(), { once: true })
  }
  const signal = ctrl?.signal || userSignal
  let timeoutId
  let res
  try {
    if (ctrl) timeoutId = setTimeout(() => ctrl.abort(), timeoutMs)
    res = await fetch(url, { ...fetchOptions, headers, credentials: 'include', signal })
  } catch (e) {
    const aborted = e?.name === 'AbortError'
    console.error(`[api] NETWORK ${fetchOptions.method || 'GET'} ${url} — ${e.message || 'fetch failed'}`)
    const err = new Error(aborted ? '请求超时，请稍后重试' : '网络连接失败，请检查网络')
    err.status = 0
    throw err
  } finally {
    if (timeoutId) clearTimeout(timeoutId)
  }
  if (res.status === 401 && isFreshLogin() && !isAuthAttemptRequest(url)) {
    await new Promise((r) => setTimeout(r, 400))
    res = await fetch(url, { ...fetchOptions, headers, credentials: 'include', signal })
  }
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    if (res.status === 401) {
      handleMidSessionExpired(url)
    }
    const msg = formatApiError(data, res.status)
    console.error(`[api] ${res.status} ${fetchOptions.method || 'GET'} ${url} — ${msg}`, data)
    const err = new Error(msg)
    err.status = res.status
    err.data = data
    throw err
  }
  return data
}

/** POST + SSE 流式读取（首页引导 / 学科答疑） */
export async function streamPostSse(url, body, { onToken, onDone, onError, signal } = {}) {
  const userId = extractUserIdFromUrl(url)
  const headers = mergeAuthHeaders(
    {
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
      },
      _url: url,
    },
    userId,
  )
  const res = await fetch(url, {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
    signal,
    credentials: 'include',
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    if (res.status === 401) {
      handleMidSessionExpired(url)
    }
    const err = new Error(data.detail || data.message || `HTTP ${res.status}`)
    err.status = res.status
    throw err
  }
  const reader = res.body?.getReader()
  if (!reader) throw new Error('流式响应不可用')

  const decoder = new TextDecoder()
  let buffer = ''
  let finalPayload = null

  while (true) {
    if (signal?.aborted) {
      await reader.cancel().catch(() => {})
      throw new DOMException('Aborted', 'AbortError')
    }
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let sep
    while ((sep = buffer.indexOf('\n\n')) >= 0) {
      const block = buffer.slice(0, sep)
      buffer = buffer.slice(sep + 2)
      const line = block.split('\n').find(l => l.startsWith('data: '))
      if (!line) continue
      const raw = line.slice(6).trim()
      if (raw === '[DONE]') continue
      let evt
      try {
        evt = JSON.parse(raw)
      } catch {
        evt = { type: 'token', content: raw }
      }
      if (evt.type === 'token' && evt.content) {
        onToken?.(evt.content, evt)
      } else if (evt.type === 'done') {
        finalPayload = evt
        onDone?.(evt)
      } else if (evt.type === 'error') {
        const msg = evt.message || '流式请求失败'
        onError?.(msg)
        throw new Error(msg)
      }
    }
  }
  return finalPayload
}

/** 给 URL 拼接 ?user_id=（session_token 改走 Header） */
function ensureAuthQuery(url, userId) {
  if (userId && !/[?&]user_id=/.test(url)) {
    const sep = url.includes('?') ? '&' : '?'
    return `${url}${sep}user_id=${userId}`
  }
  return url
}

function extractUserIdFromUrl(url) {
  const m = String(url || '').match(/[?&]user_id=(\d+)/)
  return m ? parseInt(m[1], 10) : null
}

function mergeAuthHeaders(options = {}, userId = null) {
  const headers = { ...(options.headers || {}), ...authHeaders() }
  const url = options._url || ''
  const isAdminApi = String(url).includes('/api/admin/')

  if (isAdminApi) {
    const aid = userId || getAdminUserId()
    if (aid) headers['X-Child-User-Id'] = String(aid)
  } else {
    const uid = userId || extractUserIdFromUrl(url) || getChildUserId()
    if (uid) headers['X-Child-User-Id'] = String(uid)
  }
  return headers
}

export function withUser(url, userId) {
  return ensureAuthQuery(url, userId)
}

/** 训练音视频流 — 同源代理 URL，附带 user_id 鉴权；H5 video 需绝对路径 */
export function resolveTrainingStreamUrl(url, userId) {
  if (!url || !userId) return url || ''
  if (url.startsWith('blob:') || url.startsWith('data:')) return url
  if (!url.includes('/api/training/') || !url.includes('/stream')) return url

  let path = url
  let origin = ''
  if (path.startsWith('http://') || path.startsWith('https://')) {
    try {
      const u = new URL(path)
      origin = u.origin
      path = u.pathname + u.search
    } catch (_) { /* keep path */ }
  }
  path = ensureAuthQuery(path, userId)
  if (!origin && path.startsWith('/')) {
    try { origin = window.location.origin } catch (_) {}
  }
  return origin ? origin + path : path
}

/** 答疑图片需带 user_id 鉴权（session 走 Cookie）；补全绝对路径供 <image> 加载 */
export function resolveQaImageUrl(url, userId) {
  if (!url || !userId) return url
  if (url.startsWith('blob:') || url.startsWith('data:')) return url
  if (!url.includes('/api/qa/images/')) return url

  let path = url
  let origin = ''
  if (path.startsWith('http://') || path.startsWith('https://')) {
    try {
      const u = new URL(path)
      origin = u.origin
      path = u.pathname + u.search
    } catch (_) { /* keep path */ }
  }
  path = ensureAuthQuery(path, userId)
  if (!origin && path.startsWith('/')) {
    try { origin = window.location.origin } catch (_) {}
  }
  return origin ? origin + path : path
}

/**
 * 消息图片显示：优先本地 session 缓存（data URL），无缓存再走服务器
 */
export function resolveMessageImageDisplay(imageUrl, userId) {
  const imageId = parseQaImageId(imageUrl)
  if (imageId) {
    const cached = getQaImageLocal(imageId)
    if (cached) return cached
  }
  return imageUrl ? resolveQaImageUrl(imageUrl, userId) : null
}

export function withAdmin(url, adminId) {
  let result = url
  const id = adminId || getAdminUserId()
  if (id && !/[?&]user_id=/.test(result)) {
    const sep = result.includes('?') ? '&' : '?'
    result = `${result}${sep}user_id=${id}`
  }
  return result
}

export class NeedLoginError extends Error {
  constructor(message = '请先登录') {
    super(message)
    this.name = 'NeedLoginError'
  }
}


