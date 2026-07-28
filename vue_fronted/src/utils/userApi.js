/**
 * 后端 API 封装层 — 所有前后端通信的统一入口
 *
 * 架构约定:
 * - 用户标识: localStorage 存 child_user_id，请求通过 Query ?user_id= 传递
 * - 认证方式: 明文 user_id（MVP 阶段，生产需升级为 JWT）
 * - 数据流:   Vue 页面 → userApi.js → fetch() → FastAPI → Service → DB
 * - 错误处理: 非 2xx 响应抛出 Error，调用方 try/catch
 *
 * 模块索引:
 *   L1-40    身份管理 (localStorage 读写 + 会话缓存)
 *   L43-61   底层 HTTP (apiJson / withUser / resolveQaImageUrl)
 *   L69-140  认证流程 (登录/注册/家长/学生)
 *   L140-180 家长端 (孩子 CRUD)
 *   L206-265 自动登录 (ensureChildUser — 全局入口)
 *   L269-280 用户资料 (profile CRUD)
 *   L283-320 天赋测评 (assessment CRUD + 冲突解决)
 *   L322-430 今日训练 (排课/打卡/窗口/媒体/历史)
 *   L431-470 学科答疑 (QA 会话 + 消息 + 图片)
 *   L471-490 成长里程碑 (徽章/时间线/摘要/分享)
 *   L491-520 语音 + 开发者工具
 */

import { getQaImageLocal, parseQaImageId } from './qaMedia.js'
import { authHeaders, getDeviceId } from './loginGuard.js'
import { applyDevBootReloginIfNeeded } from './devBootAuth.js'
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
  sanitizeAuthForLoginEntry,
  installAuthStorageSync,
  clearAllAuthSessions,
} from './appSession.js'

// ── localStorage 键名 ──
const CHILD_KEY = 'jnao_child_user_id'
const GUEST_PHONE_KEY = 'jnao_guest_phone'
const GUEST_NICKNAME_KEY = 'jnao_guest_nickname'
const SESSION_TOKEN_KEY = 'jnao_session_token'

/** 读取当前登录的 child_user_id，无则返回 null */
export function getChildUserId() {
  try {
    const raw = localStorage.getItem(CHILD_KEY)
    if (raw) return parseInt(raw, 10)
  } catch (e) { /* ignore */ }
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
export function logoutAndGoLogin() {
  clearSessionForKind('parent')
  clearSessionForKind('student')
  try {
    uni.reLaunch({ url: '/pages/login/index' })
  } catch (e) {
    window.location.href = '/pages/login/index'
  }
}

export function logoutAdminAndGoLogin() {
  clearSessionForKind('admin')
  try {
    uni.redirectTo({ url: '/pages/admin/login' })
  } catch (e) {
    window.location.href = '/pages/admin/login'
  }
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
  logoutAndGoLogin()
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

/** 页面进入前校验 session；网络异常允许离线继续，仅 401 才登出 */
export async function requirePageAuth(kind) {
  const snap = readAuthSnapshot()
  const session = kind === 'admin' ? snap.admin : kind === 'parent' ? snap.parent : snap.student

  if (!session?.userId || !session?.token) {
    if (kind === 'student' && snap.parent?.token) {
      try { uni.reLaunch({ url: '/pages/parent/index' }) } catch (_) { /* ignore */ }
      return { ok: false, reason: 'wrong_role' }
    }
    if (kind === 'parent' && snap.student?.token) {
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
      clearSessionForKind(kind)
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
      if (kind === 'student' && (role === 'parent' || snap.parent?.token)) {
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

/** 读取 session_token */
export function getSessionToken() {
  try {
    return localStorage.getItem(SESSION_TOKEN_KEY) || ''
  } catch (e) { /* ignore */ }
  return ''
}

/** 存储 session_token */
export function setSessionToken(token) {
  try {
    if (token) {
      localStorage.setItem(SESSION_TOKEN_KEY, token)
    } else {
      localStorage.removeItem(SESSION_TOKEN_KEY)
    }
  } catch (e) { /* ignore */ }
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
  const kind = inferAuthKindFromUrl(url)
  const hasToken = kind === 'admin' ? !!getAdminSessionToken() : !!getSessionToken()
  if (!hasToken) return
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
  const userId = extractUserIdFromUrl(url)
  const headers = mergeAuthHeaders({ ...options, _url: url }, userId)
  let res
  try {
    res = await fetch(url, { ...options, headers })
  } catch (e) {
    console.error(`[api] NETWORK ${options.method || 'GET'} ${url} — ${e.message || 'fetch failed'}`)
    const err = new Error('网络连接失败，请检查网络')
    err.status = 0
    throw err
  }
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    if (res.status === 401) {
      handleMidSessionExpired(url)
    }
    const msg = formatApiError(data, res.status)
    console.error(`[api] ${res.status} ${options.method || 'GET'} ${url} — ${msg}`, data)
    const err = new Error(msg)
    err.status = res.status
    err.data = data
    throw err
  }
  return data
}

/** POST + SSE 流式读取（首页引导 / 学科答疑） */
async function streamPostSse(url, body, { onToken, onDone, onError, signal } = {}) {
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
    const adminTok = getAdminSessionToken()
    if (adminTok) headers['X-Session-Token'] = adminTok
    const aid = userId || getAdminUserId()
    if (aid) headers['X-Child-User-Id'] = String(aid)
  } else {
    const token = getSessionToken()
    if (token) headers['X-Session-Token'] = token
    const uid = userId || extractUserIdFromUrl(url) || getChildUserId()
    if (uid) headers['X-Child-User-Id'] = String(uid)
  }
  return headers
}

export function withUser(url, userId) {
  return ensureAuthQuery(url, userId)
}

/** 答疑图片需带 user_id + session_token 鉴权；补全绝对路径供 <image> 加载 */
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
  const token = getSessionToken()
  if (token && !/[?&]session_token=/.test(path)) {
    path += `${path.includes('?') ? '&' : '?'}session_token=${encodeURIComponent(token)}`
  }
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

function getOrCreateGuestPhone() {
  try {
    const saved = localStorage.getItem(GUEST_PHONE_KEY)
    if (saved) return saved
    const phone = `13${String(Math.floor(Math.random() * 1e9)).padStart(9, '0')}`
    localStorage.setItem(GUEST_PHONE_KEY, phone)
    return phone
  } catch (e) {
    return `13${String(Date.now()).slice(-9)}`
  }
}

/** 登录后存储 session；家长/学生分槽，避免 role 混用 */
export function saveAuthSession(data) {
  _storeAuth(data)
}

function _storeAuth(data) {
  const role = data.role || 'student'
  if (role === 'parent') {
    clearSessionsExcept('parent')
    invalidatePageAuthCache('admin')
  } else if (role === 'student') {
    clearSessionsExcept('student')
    invalidatePageAuthCache('admin')
  }
  if (data.session_token) {
    setSessionToken(data.session_token)
  }
  try {
    localStorage.setItem('jnao_user', JSON.stringify({
      id: data.child_user_id,
      name: data.nickname,
      phone: data.parent_phone,
      role,
      loginChannel: data.login_channel || 'standard',
    }))
    localStorage.setItem('jnao_logged_in', '1')
    if (data.login_channel === 'wechat') {
      localStorage.setItem('jnao_login_channel', 'wechat')
    }
  } catch (e) { /* ignore */ }
  if (role === 'student') {
    setChildUserId(data.child_user_id)
    try { localStorage.setItem('jnao_student_user_id', String(data.child_user_id)) } catch (_) {}
    markChildUserSessionValid(data.child_user_id)
    invalidatePageAuthCache('student')
    _authValidatedUid.student = data.child_user_id
    _authValidatedAt.student = Date.now()
  } else if (role === 'parent') {
    try { localStorage.setItem('jnao_parent_user_id', String(data.child_user_id)) } catch (_) {}
    setChildUserId(data.child_user_id)
    invalidateChildUserSession()
    invalidatePageAuthCache('parent')
    _authValidatedUid.parent = data.child_user_id
    _authValidatedAt.parent = Date.now()
  }
  resetSessionExpiryGuard()
}

export class NeedLoginError extends Error {
  constructor(message = '请先登录') {
    super(message)
    this.name = 'NeedLoginError'
  }
}

function _readStoredRole() {
  try {
    const raw = localStorage.getItem('jnao_user')
    if (!raw) return null
    return JSON.parse(raw).role || null
  } catch (e) {
    return null
  }
}

function _redirectToLogin() {
  try {
    uni.reLaunch({ url: '/pages/login/index' })
  } catch (e) { /* ignore */ }
}

/** 家长登录：手机号 + 密码 */
export async function loginParent(phone, password) {
  const data = await apiJson('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ parent_phone: phone, password, role: 'parent' }),
  })
  _storeAuth(data)
  return data
}

/** 获取图形验证码 */
export async function fetchCaptcha() {
  return apiJson('/api/auth/captcha')
}

/** 家长手机号注册状态 — 需图形验证码（B10） */
export async function checkParentPhone(phone, { captchaId, captchaCode } = {}) {
  return apiJson('/api/auth/parent/phone-check', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({
      phone,
      captcha_id: captchaId,
      captcha_code: captchaCode,
    }),
  })
}

/** 发送短信验证码 scene: login | register */
export async function sendParentSmsCode(phone, scene, { captchaId, captchaCode } = {}) {
  const body = { phone, scene, device_id: getDeviceId() }
  if (captchaId) body.captcha_id = captchaId
  if (captchaCode) body.captcha_code = captchaCode
  return apiJson('/api/auth/sms/send', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(body),
  })
}

/** 家长验证码登录（仅已注册手机号） */
export async function loginParentSms({ phone, smsCode }) {
  const data = await apiJson('/api/auth/sms/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ phone, sms_code: smsCode, device_id: getDeviceId() }),
  })
  _storeAuth(data)
  return data
}

/** 家长验证码注册 */
export async function registerParentSms({ phone, smsCode, realName, nickname, password }) {
  const body = {
    phone,
    sms_code: smsCode,
    real_name: realName,
    nickname,
    device_id: getDeviceId(),
  }
  if (password) body.password = password
  const data = await apiJson('/api/auth/sms/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(body),
  })
  _storeAuth(data)
  return data
}

export function parentNeedsProfileComplete(data) {
  return data?.role === 'parent' && data?.profile_complete === false
}

export function parentNeedsAccountReady(data) {
  if (data?.role !== 'parent') return false
  if (data?.login_channel === 'wechat') return data?.account_ready === false
  return data?.profile_complete === false
}

export async function fetchWechatConfig() {
  return apiJson('/api/auth/wechat/config')
}

export async function fetchWechatOAuthUrl(redirect = '') {
  const q = redirect ? `?redirect=${encodeURIComponent(redirect)}` : ''
  return apiJson(`/api/auth/wechat/oauth-url${q}`)
}

/** OAuth 回调 login_ticket 一次性换取 session */
export async function exchangeWechatLogin(loginTicket) {
  const data = await apiJson(
    `/api/auth/wechat/exchange?login_ticket=${encodeURIComponent(loginTicket)}`,
  )
  _storeAuth({ ...data, login_channel: 'wechat' })
  return data
}

export async function sendWechatBindSms({ bindTicket, phone }) {
  return apiJson('/api/auth/wechat/send-bind-sms', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({
      bind_ticket: bindTicket,
      phone,
      device_id: getDeviceId(),
    }),
  })
}

export async function wechatBindPhone({ bindTicket, phone, smsCode }) {
  const data = await apiJson('/api/auth/wechat/bind-phone', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({
      bind_ticket: bindTicket,
      phone,
      sms_code: smsCode,
      device_id: getDeviceId(),
    }),
  })
  _storeAuth(data)
  return data
}

/** 外链 m.jnao.com 绑手机完成后换取 session */
export async function completeWechatExternalBind(bindTicket) {
  const data = await apiJson('/api/auth/wechat/complete-external-bind', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({
      bind_ticket: bindTicket,
      device_id: getDeviceId(),
    }),
  })
  _storeAuth({ ...data, login_channel: 'wechat' })
  return data
}

export function storeWechatCallbackAuth(data) {
  _storeAuth({ ...data, login_channel: 'wechat' })
}

export async function fetchParentProfile(parentId) {
  return apiJson(withUser('/api/parent/profile', parentId))
}

export async function updateParentProfile(parentId, body) {
  const data = await apiJson(withUser('/api/parent/profile', parentId), {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (data.session_token) {
    setSessionToken(data.session_token)
  }
  return data
}

export async function ensureParentAccountReady(parentId) {
  const p = await fetchParentProfile(parentId)
  if (p.login_channel === 'wechat' && !p.account_ready) {
    if (p.next_step === 'bind-phone') {
      try {
        const cfg = await fetchWechatConfig()
        if (cfg.use_external_bind_mobile && cfg.bind_mobile_url) {
          window.location.href = cfg.bind_mobile_url
          return false
        }
      } catch (_) { /* fallback */ }
      uni.redirectTo({ url: '/pages/login/index' })
    } else {
      uni.redirectTo({ url: '/pages/login/complete-parent?from=wechat' })
    }
    return false
  }
  if (!p.profile_complete) {
    uni.redirectTo({ url: '/pages/login/complete-parent' })
    return false
  }
  return true
}

/** 孩子登录：账号 + 密码 */
export async function loginStudent(loginName, password) {
  const data = await apiJson('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ login_name: loginName, password }),
  })
  _storeAuth(data)
  return data
}

/** 注册家长账户 */
export async function registerParent(phone, nickname, password) {
  const data = await apiJson('/api/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      parent_phone: phone,
      nickname,
      password,
      role: 'parent',
    }),
  })
  _storeAuth(data)
  return data
}

/** 孩子是否仍需完成登录后引导（onboarding） */
export async function studentNeedsOnboarding(userId) {
  try {
    const profile = await fetchProfile(userId)
    return !profile.profile_json?.onboarding?.completed_at
  } catch (e) {
    return true
  }
}

// ── 家长端 ──

export async function fetchParentChildren(parentId) {
  const data = await apiJson(withUser('/api/parent/children', parentId))
  return data.children || []
}

export async function fetchParentQuota(parentId) {
  return apiJson(withUser('/api/parent/quota', parentId))
}

export async function createParentChild(parentId, { loginName, nickname, password, grade, age }) {
  return apiJson(withUser('/api/parent/children', parentId), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      login_name: loginName,
      nickname,
      password,
      grade: grade || null,
      age: age || null,
    }),
  })
}

export async function updateParentChild(parentId, childId, { nickname, password, grade, age } = {}) {
  const body = {}
  if (nickname != null) body.nickname = nickname
  if (password != null) body.password = password
  if (grade != null) body.grade = grade
  if (age != null) body.age = age
  return apiJson(withUser(`/api/parent/children/${childId}`, parentId), {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export async function deleteParentChild(parentId, childId) {
  return apiJson(withUser(`/api/parent/children/${childId}`, parentId), {
    method: 'DELETE',
  })
}

function getOrCreateGuestNickname(fallback = '学员') {
  try {
    const saved = localStorage.getItem(GUEST_NICKNAME_KEY)
    if (saved) return saved
    localStorage.setItem(GUEST_NICKNAME_KEY, fallback)
    return fallback
  } catch (e) {
    return fallback
  }
}

function readLoginProfile() {
  try {
    const raw = localStorage.getItem('jnao_user')
    if (!raw) return null
    const user = JSON.parse(raw)
    if (!user?.name) return null
    return {
      nickname: String(user.name).trim(),
      phone: String(user.phone || '').trim(),
    }
  } catch (e) {
    return null
  }
}

async function registerChildUser(parentPhone, nickname) {
  const data = await apiJson('/api/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ parent_phone: parentPhone, nickname }),
  })
  _storeAuth(data)
  try {
    localStorage.setItem(GUEST_PHONE_KEY, parentPhone)
    localStorage.setItem(GUEST_NICKNAME_KEY, nickname)
  } catch (e) { /* ignore */ }
  return data.child_user_id
}

/**
 * 全局用户入口 — 学生页 onMounted 调用
 * 无有效学生 session 时跳转登录，不再自动 guest 注册
 */
export async function ensureChildUser(nickname = '学员') {
  const role = _readStoredRole()
  if (role === 'parent') {
    try { uni.reLaunch({ url: '/pages/parent/index' }) } catch (e) { /* ignore */ }
    throw new NeedLoginError('请使用学生账号登录')
  }

  const auth = await requirePageAuth('student')
  if (!auth.ok) throw new NeedLoginError()
  return auth.userId
}

/** JNAO 外部 API 用的 uid（存于 child_user.jnao_uid） */
export async function ensureJnaoUid(userId) {
  const profile = await apiJson(withUser('/api/user/profile', userId))
  if (profile.jnao_uid) return parseInt(profile.jnao_uid, 10)
  const jnaoUid = userId * 1000 + (Date.now() % 1000)
  await apiJson(withUser('/api/user/profile', userId), {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ jnao_uid: String(jnaoUid) }),
  })
  return jnaoUid
}

// ── 用户资料 ──

export async function fetchProfile(userId) {
  return apiJson(withUser('/api/user/profile', userId))
}

export async function saveProfile(userId, data) {
  return apiJson(withUser('/api/user/profile', userId), {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
}

// ── 天赋测评 ──

export async function fetchAssessmentHistory(userId) {
  const data = await apiJson(withUser('/api/talent/assessment/history', userId))
  return data.items || []
}

export async function fetchAssessmentReport(userId, assessmentId) {
  return apiJson(withUser(`/api/talent/assessment/${assessmentId}`, userId))
}

export async function deleteAssessmentReport(userId, assessmentId) {
  return apiJson(withUser(`/api/talent/assessment/${assessmentId}`, userId), {
    method: 'DELETE',
  })
}

export async function fetchLatestAssessment(userId) {
  return apiJson(withUser('/api/talent/assessment/latest', userId))
}

export function gradeToSchoolStage(grade) {
  const g = String(grade || '')
  if (['一年级', '二年级', '三年级'].includes(g)) return 'primary_low'
  if (['四年级', '五年级', '六年级'].includes(g)) return 'primary_high'
  if (['初一', '初二', '初三'].includes(g)) return 'junior'
  if (['高一', '高二', '高三'].includes(g)) return 'senior'
  return 'primary_high'
}

export async function resolveTalentConflict(userId, action) {
  return apiJson(withUser('/api/user/talent/resolve-conflict', userId), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action }),
  })
}

export async function submitTalentReport(userId, { answer, jnaoUid, type }) {
  return apiJson(withUser('/api/talent/report', userId), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      answer,
      uid: jnaoUid,
      type,
    }),
  })
}

// ── 今日训练（核心模块：入口→排课→打卡→历史）──

/** 训练入口：校验天赋状态 + 检查今日方案是否存在 */
export async function fetchTrainingEntry(userId) {
  return apiJson(withUser('/api/training/entry', userId))
}

/** 获取今日训练方案，skipAi=1 跳过 LLM 报告生成（首屏加速） */
export async function fetchTrainingToday(userId, options = {}) {
  const skipAi = options.skipAi ?? options.skip_ai ?? false
  const base = skipAi ? '/api/training/today?skip_ai=1' : '/api/training/today'
  try {
    const data = await apiJson(withUser(base, userId))
    return { data }
  } catch (e) {
    if (e.status === 403) {
      return { error: 'assessment', message: e.data?.detail || '请先完成天赋测评' }
    }
    return { error: 'api', message: e.message }
  }
}

/** 强制重新生成 AI 今日方案（开发者/刷新用） */
export async function refreshTrainingReport(userId, force = true) {
  try {
    const data = await apiJson(withUser(`/api/training/report/today?force=${force ? '1' : '0'}`, userId))
    return { data }
  } catch (e) {
    if (e.status === 403) {
      return { error: 'assessment', message: e.data?.detail || '请先完成天赋测评' }
    }
    return { error: 'api', message: e.message }
  }
}

/** 按训练时长排课：框架内 LLM 路由生成 plan_item */
export async function scheduleTrainingPlan(userId, plannedMinutes) {
  try {
    const data = await apiJson(withUser('/api/training/schedule', userId), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ planned_minutes: plannedMinutes }),
    })
    return { data }
  } catch (e) {
    if (e.status === 403) {
      return { error: 'assessment', message: e.data?.detail || '请先完成天赋测评' }
    }
    return { error: 'api', message: e.message }
  }
}

/** 设定时长用尽 — 后端隐藏媒体 URL，打卡仍可用 */
export async function markPlanMediaExhausted(userId) {
  try {
    const data = await apiJson(withUser('/api/training/plan/media-exhausted', userId), {
      method: 'POST',
    })
    return { data }
  } catch (e) {
    return { error: 'api', message: e.message }
  }
}

/** 记录今日训练时段（用于后端判断计时是否结束） */
export async function setTrainingWindow(userId, startTime, endTime) {
  return apiJson(withUser('/api/training/window', userId), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ start_time: startTime, end_time: endTime }),
  })
}

export async function clearTrainingWindow(userId) {
  return apiJson(withUser('/api/training/window', userId), { method: 'DELETE' })
}

/** 天赋固定训练视频 */
export async function fetchTalentTrainingVideo(userId) {
  return apiJson(withUser('/api/training/video/talent', userId))
}

export async function fetchTrainingProgress(userId) {
  return apiJson(withUser('/api/training/progress', userId))
}

export async function submitTrainingCheckin(userId, payload) {
  return apiJson(withUser('/api/training/checkin', userId), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export async function postTrainingWatchProgress(userId, itemId, payload) {
  return apiJson(withUser(`/api/training/items/${itemId}/watch-progress`, userId), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export async function fetchTodayCheckins(userId) {
  const data = await apiJson(withUser('/api/training/checkin/today', userId))
  return Array.isArray(data) ? data : []
}

export async function updateTrainingCheckin(userId, recordId, payload) {
  return apiJson(withUser(`/api/training/checkin/${recordId}`, userId), {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export async function deleteTrainingCheckin(userId, recordId) {
  return apiJson(withUser(`/api/training/checkin/${recordId}`, userId), {
    method: 'DELETE',
  })
}

export async function fetchTrainingHistory(userId, limit = 30, { excludeToday = false } = {}) {
  const qs = `limit=${limit}&group_by_day=1${excludeToday ? '&exclude_today=1' : ''}`
  const data = await apiJson(withUser(`/api/training/history?${qs}`, userId))
  return { items: data.items || [], days: data.days || [] }
}

// ── v2.0 选修弹窗 ──

/** 获取可用的选修技能列表 */
export async function fetchElectiveList(plannedMinutes = 0, overallTier = 1) {
  const data = await apiJson(`/api/training/elective/list?planned_minutes=${plannedMinutes}&overall_tier=${overallTier}`)
  return { offers: data.offers || [] }
}

/** 提交选修打卡（多元感知等） */
export async function submitElectiveCheckin(userId, payload) {
  return apiJson(withUser('/api/training/elective', userId), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

/** 整体替换今日方案中的训练项目（不改等级进度） */
export async function customizePlan(userId, planId, skills) {
  return apiJson(withUser('/api/training/plan/customize', userId), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ plan_id: planId, skills }),
  })
}

/** 开关选修项：action="add" 追加到末尾，action="remove" 从方案移除 */
export async function toggleElectiveItem(userId, planId, skill, action) {
  return apiJson(withUser('/api/training/plan/elective-toggle', userId), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ plan_id: planId, skill, action }),
  })
}

// ── 首页引导对话 ──

export async function fetchGuideSession(userId) {
  return apiJson(withUser('/api/guide/session', userId))
}

export async function fetchGuideSessions(userId) {
  const data = await apiJson(withUser('/api/guide/sessions', userId))
  return data.items || []
}

export async function fetchGuideSessionById(userId, sessionId) {
  return apiJson(withUser(`/api/guide/sessions/${sessionId}`, userId))
}

export async function deleteGuideSession(userId, sessionId) {
  return apiJson(withUser(`/api/guide/sessions/${sessionId}`, userId), { method: 'DELETE' })
}

/** 进首页开场 Agent：按情境返回欢迎语 */
export async function fetchGuideBootstrap(userId, { force = false, use_llm = true } = {}) {
  return apiJson(withUser('/api/guide/bootstrap', userId), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ force, use_llm }),
  })
}

export async function clearGuideSession(userId) {
  return apiJson(withUser('/api/guide/clear', userId), { method: 'POST' })
}

export async function sendGuideMessage(userId, message, sessionId = null) {
  return apiJson(withUser('/api/guide/chat', userId), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, session_id: sessionId }),
  })
}

export function sendGuideMessageStream(userId, message, sessionId = null, handlers = {}) {
  const controller = new AbortController()
  const promise = streamPostSse(
    withUser('/api/guide/chat/stream', userId),
    { message, session_id: sessionId },
    { ...handlers, signal: controller.signal },
  )
  return { promise, abort: () => controller.abort() }
}

// ── 学科答疑 ──

export async function fetchQaSessions(userId) {
  const data = await apiJson(withUser('/api/qa/sessions', userId))
  return data.items || []
}

export async function createQaSession(userId, subject = null) {
  return apiJson(withUser('/api/qa/sessions', userId), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ subject: subject || null }),
  })
}

export async function deleteQaSession(userId, sessionId) {
  return apiJson(withUser(`/api/qa/sessions/${sessionId}`, userId), { method: 'DELETE' })
}

export async function fetchQaSession(userId, sessionId) {
  return apiJson(withUser(`/api/qa/sessions/${sessionId}`, userId))
}

export async function sendQaMessage(userId, message, sessionId = null, options = {}) {
  const subject = typeof options === 'string' ? options : options.subject
  const imageId = options.image_id || options.imageId || null
  const useRag = options.use_rag ?? options.useRag ?? null
  return apiJson(withUser('/api/qa/chat', userId), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      session_id: sessionId,
      subject: subject || null,
      image_id: imageId,
      use_rag: useRag,
    }),
  })
}

export function sendQaMessageStream(userId, message, sessionId = null, options = {}, handlers = {}) {
  const subject = typeof options === 'string' ? options : options.subject
  const imageId = options.image_id || options.imageId || null
  const useRag = options.use_rag ?? options.useRag ?? null
  const controller = new AbortController()
  const promise = streamPostSse(
    withUser('/api/qa/chat/stream', userId),
    {
      message,
      session_id: sessionId,
      subject: subject || null,
      image_id: imageId,
      use_rag: useRag,
    },
    { ...handlers, signal: controller.signal },
  )
  return { promise, abort: () => controller.abort() }
}

export async function uploadQaImage(userId, file) {
  const form = new FormData()
  form.append('file', file)
  const headers = mergeAuthHeaders({}, userId)
  const res = await fetch(withUser('/api/qa/upload-image', userId), {
    method: 'POST',
    headers,
    body: form,
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`)
  return data
}

export async function transcribeVoice(audioBlob, filename = 'speech.webm') {
  const userId = getChildUserId()
  if (!userId || !getSessionToken()) throw new NeedLoginError()
  const form = new FormData()
  form.append('audio', audioBlob, filename)
  const headers = mergeAuthHeaders({}, userId)
  const res = await fetch(withUser('/api/voice/asr', userId), { method: 'POST', headers, body: form })
  const data = await res.json().catch(() => ({}))
  if (!res.ok || data.error) throw new Error(data.error || data.detail || '语音识别失败')
  return data.text || ''
}

/** uni.chooseImage / getRecorderManager 返回的临时路径 → 转写 */
export async function transcribeVoicePath(tempFilePath) {
  const resp = await fetch(tempFilePath)
  const blob = await resp.blob()
  const ext = (blob.type || '').includes('mpeg') ? 'mp3' : 'webm'
  return transcribeVoice(blob, `recording.${ext}`)
}

export async function updateLearnerProfile(userId, profile) {
  return apiJson(withUser('/api/user/learner-profile', userId), {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(profile),
  })
}

// ── 成长里程碑 ──

export async function fetchGrowthBadges(userId) {
  const data = await apiJson(withUser('/api/growth/badges', userId))
  return data.items || []
}

export async function fetchGrowthTimeline(userId) {
  const data = await apiJson(withUser('/api/growth/timeline', userId))
  return data.items || []
}

export async function fetchGrowthSummary(userId) {
  return apiJson(withUser('/api/growth/summary', userId))
}

export async function fetchGrowthMilestones(userId) {
  const data = await apiJson(withUser('/api/growth/milestones', userId))
  return data.items || []
}

export async function fetchGrowthShare(userId) {
  return apiJson(withUser('/api/growth/share', userId))
}

// ── 开发者工具（JNAO_DEV_MODE=1）──

export async function fetchDevTrainingStatus(userId) {
  return apiJson(withUser('/api/dev/training/status', userId))
}

export async function devResetTodayTraining(userId) {
  return apiJson(withUser('/api/dev/training/reset-today', userId), { method: 'POST' })
}

export async function devResetTrainingProgress(userId) {
  return apiJson(withUser('/api/dev/training/reset-progress', userId), { method: 'POST' })
}

export async function devResetAllTraining(userId) {
  return apiJson(withUser('/api/dev/training/reset-all', userId), { method: 'POST' })
}

export async function devSimulateNextDay(userId) {
  return apiJson(withUser('/api/dev/training/next-day', userId), { method: 'POST' })
}

export async function devSimulate4amCutoff(userId) {
  return apiJson(withUser('/api/dev/training/simulate-4am-cutoff', userId), { method: 'POST' })
}

export async function devResetTalent(userId) {
  return apiJson(withUser('/api/dev/training/reset-talent', userId), { method: 'POST' })
}

export async function devResetClock(userId) {
  return apiJson(withUser('/api/dev/training/reset-clock', userId), { method: 'POST' })
}

// ── 管理员 ──

const ADMIN_USER_KEY = 'jnao_admin_user'
const ADMIN_TOKEN_KEY = 'jnao_admin_token'

export function getAdminUserId() {
  try {
    const raw = localStorage.getItem(ADMIN_USER_KEY)
    if (raw) return JSON.parse(raw).id
  } catch (_) {}
  return null
}

export function getAdminSessionToken() {
  try { return localStorage.getItem(ADMIN_TOKEN_KEY) || '' } catch (_) { return '' }
}

function withAdmin(url, adminId) {
  let result = url
  const id = adminId || getAdminUserId()
  if (id && !/[?&]user_id=/.test(result)) {
    const sep = result.includes('?') ? '&' : '?'
    result = `${result}${sep}user_id=${id}`
  }
  return result
}

export function clearAdminSession() {
  clearSessionForKind('admin')
}

export async function loginAdmin(loginName, password) {
  clearSessionsExcept('admin')
  invalidatePageAuthCache('parent')
  invalidatePageAuthCache('student')
  invalidateChildUserSession()
  const data = await apiJson('/api/admin/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ login_name: loginName, password }),
  })
  localStorage.setItem(ADMIN_USER_KEY, JSON.stringify({
    id: data.child_user_id,
    name: data.nickname,
    role: 'admin',
    loginName: data.login_name,
  }))
  if (data.session_token) localStorage.setItem(ADMIN_TOKEN_KEY, data.session_token)
  invalidatePageAuthCache('admin')
  _authValidatedUid.admin = data.child_user_id
  _authValidatedAt.admin = Date.now()
  resetSessionExpiryGuard()
  return data
}

export async function fetchAdminParents(adminId, q = '') {
  const qs = q ? `?q=${encodeURIComponent(q)}` : ''
  const data = await apiJson(withAdmin(`/api/admin/parents${qs}`, adminId))
  return data.parents || []
}

export async function fetchAdminRemovedParents(adminId, q = '') {
  const qs = q ? `?q=${encodeURIComponent(q)}` : ''
  const data = await apiJson(withAdmin(`/api/admin/parents/removed${qs}`, adminId))
  return data.parents || []
}

export async function createAdminParent(adminId, body) {
  return apiJson(withAdmin('/api/admin/parents', adminId), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export async function restoreAdminParent(adminId, parentId) {
  return apiJson(withAdmin(`/api/admin/parents/${parentId}/restore`, adminId), {
    method: 'POST',
  })
}

export async function restoreAdminParentByPhone(adminId, { phone, nickname } = {}) {
  return apiJson(withAdmin('/api/admin/parents/restore-by-phone', adminId), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ phone, nickname }),
  })
}

export async function restoreAdminChild(adminId, childId) {
  return apiJson(withAdmin(`/api/admin/children/${childId}/restore`, adminId), {
    method: 'POST',
  })
}

export async function updateAdminParent(adminId, parentId, body) {
  return apiJson(withAdmin(`/api/admin/parents/${parentId}`, adminId), {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export async function deleteAdminParent(adminId, parentId) {
  return apiJson(withAdmin(`/api/admin/parents/${parentId}`, adminId), { method: 'DELETE' })
}

export async function fetchAdminChildren(adminId, { parentId = null, q = '' } = {}) {
  const params = []
  if (parentId) params.push(`parent_id=${parentId}`)
  if (q) params.push(`q=${encodeURIComponent(q)}`)
  const qs = params.length ? `?${params.join('&')}` : ''
  const data = await apiJson(withAdmin(`/api/admin/children${qs}`, adminId))
  return data.children || []
}

export async function createAdminChild(adminId, body) {
  return apiJson(withAdmin('/api/admin/children', adminId), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export async function updateAdminChild(adminId, childId, body) {
  return apiJson(withAdmin(`/api/admin/children/${childId}`, adminId), {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export async function deleteAdminChild(adminId, childId) {
  return apiJson(withAdmin(`/api/admin/children/${childId}`, adminId), { method: 'DELETE' })
}

export async function bindAdminChild(adminId, childId, parentId) {
  return apiJson(withAdmin(`/api/admin/children/${childId}/bind`, adminId), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ parent_id: parentId }),
  })
}

export async function unbindAdminChild(adminId, childId) {
  return apiJson(withAdmin(`/api/admin/children/${childId}/bind`, adminId), { method: 'DELETE' })
}

export async function fetchAdminBlacklist(adminId) {
  return apiJson(withAdmin('/api/admin/blacklist', adminId))
}

export async function removeAdminBlacklist(adminId, kind, value) {
  const enc = encodeURIComponent(value)
  return apiJson(withAdmin(`/api/admin/blacklist/${kind}/${enc}`, adminId), { method: 'DELETE' })
}

export async function fetchAdminSettings(adminId) {
  return apiJson(withAdmin('/api/admin/settings', adminId))
}

export async function updateAdminSettings(adminId, body) {
  return apiJson(withAdmin('/api/admin/settings', adminId), {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export async function fetchAdminParentDetail(adminId, parentId) {
  return apiJson(withAdmin(`/api/admin/parents/${parentId}/detail`, adminId))
}

export async function reconcileAdminParent(adminId, parentId) {
  return apiJson(withAdmin(`/api/admin/parents/${parentId}/reconcile`, adminId), {
    method: 'POST',
  })
}

export async function fetchAdminChildDetail(adminId, childId) {
  return apiJson(withAdmin(`/api/admin/children/${childId}/detail`, adminId))
}

export async function fetchChildTalentQuota(adminId, childId) {
  return apiJson(withAdmin(`/api/admin/children/${childId}/talent-quota`, adminId))
}

export async function updateChildTalentQuota(adminId, childId, add) {
  return apiJson(withAdmin(`/api/admin/children/${childId}/talent-quota`, adminId), {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ add }),
  })
}

export async function batchUpdateTalentQuota(adminId, { childIds, add } = {}) {
  return apiJson(withAdmin('/api/admin/children/talent-quota/batch', adminId), {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ child_ids: childIds, add }),
  })
}

export async function fetchAdminChildAssessments(adminId, childId) {
  return apiJson(withAdmin(`/api/admin/children/${childId}/talent-assessments`, adminId))
}

// ── 切换账户 ──
export async function fetchSiblings(userId) {
  return apiJson(withUser('/api/auth/siblings', userId))
}

export async function switchChildAccount(userId, targetChildId) {
  return apiJson(withUser(`/api/auth/switch-child?target_child_id=${targetChildId}`, userId), {
    method: 'POST',
  })
}
