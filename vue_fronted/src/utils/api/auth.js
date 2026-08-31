/**
 * 认证：登录 / 注册 / 微信 / 家长门禁
 */
import { getDeviceId, authHeaders } from '../loginGuard.js'
import { clearSessionsExcept } from '../appSession.js'
import {
  apiJson,
  withUser,
  getChildUserId,
  setChildUserId,
  clearChildUserId,
  setSessionToken,
  hasUserSession,
  markFreshLogin,
  markChildUserSessionValid,
  invalidateChildUserSession,
  invalidatePageAuthCache,
  markPageAuthValidated,
  resetSessionExpiryGuard,
} from './client.js'

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
    markPageAuthValidated('student', data.child_user_id)
  } else if (role === 'parent') {
    try { localStorage.setItem('jnao_parent_user_id', String(data.child_user_id)) } catch (_) {}
    setChildUserId(data.child_user_id)
    invalidateChildUserSession()
    invalidatePageAuthCache('parent')
    markPageAuthValidated('parent', data.child_user_id)
    saveParentGateCache({ role: 'parent', ...data })
  }
  resetSessionExpiryGuard()
  markFreshLogin()
}

export function _readStoredRole() {
  try {
    const raw = localStorage.getItem('jnao_user')
    if (!raw) return null
    return JSON.parse(raw).role || null
  } catch (e) {
    return null
  }
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

/**
 * 家长手机号预检 — 需图形验证码（B10）。
 * 注意：接口为防枚举统一返回，不包含 registered/action，不能用于判断是否已注册。
 * @deprecated 注册/登录发码请直接用 sendParentSmsCode
 */
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
export async function registerParentSms({ phone, smsCode, realName, nickname, password, bindTicket }) {
  const body = {
    phone,
    sms_code: smsCode,
    real_name: realName,
    nickname,
    device_id: getDeviceId(),
  }
  if (password) body.password = password
  if (bindTicket) body.bind_ticket = bindTicket
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
  if (data?.account_ready === false) return true
  if (data?.next_step === 'bind-phone') return true
  return data?.profile_complete === false
}

/** 家长登录/注册后统一跳转目标；`__bind_phone__` 表示需走绑手机注册流 */
export function resolveParentAuthTarget(data) {
  if (data?.role !== 'parent') return '/pages/parent/index'
  if (parentNeedsAccountReady(data)) {
    if (data.next_step === 'bind-phone') return '__bind_phone__'
    return '/pages/login/complete-parent' + (data.login_channel === 'wechat' ? '?from=wechat' : '')
  }
  if (parentNeedsProfileComplete(data)) {
    return '/pages/login/complete-parent'
  }
  return '/pages/parent/index'
}

/** 同家长下切换孩子账户后写入 session（Cookie 模式） */
export function applySwitchChildSession(data) {
  saveAuthSession({ ...data, role: 'student' })
  invalidatePageAuthCache('student')
  invalidatePageAuthCache('parent')
  invalidatePageAuthCache('admin')
  try { invalidateChildUserSession() } catch (_) { /* ignore */ }
}

const PARENT_GATE_KEY = 'jnao_parent_gate'

export function saveParentGateCache(data) {
  if (data?.role !== 'parent') return
  try {
    const passed = data.next_step !== 'bind-phone' && data.account_ready !== false
    localStorage.setItem(PARENT_GATE_KEY, JSON.stringify({
      passed,
      account_ready: data.account_ready !== false,
      next_step: data.next_step || 'home',
      at: Date.now(),
    }))
  } catch (_) { /* ignore */ }
}

export function readParentGateCache() {
  try {
    const raw = localStorage.getItem(PARENT_GATE_KEY)
    return raw ? JSON.parse(raw) : null
  } catch (_) {
    return null
  }
}

export function clearParentGateCache() {
  try {
    localStorage.removeItem(PARENT_GATE_KEY)
  } catch (_) { /* ignore */ }
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
  saveParentGateCache({ role: 'parent', ...data })
  return data
}

export async function ensureParentAccountReady(parentId, { forceRefresh = false } = {}) {
  if (!forceRefresh) {
    const cached = readParentGateCache()
    if (cached?.passed && cached?.account_ready) {
      return true
    }
  }
  const p = await fetchParentProfile(parentId)
  saveParentGateCache({ role: 'parent', ...p })
  if (p.next_step === 'bind-phone') {
    const phoneQ = p.parent_phone
      ? `&phone=${encodeURIComponent(p.parent_phone)}`
      : ''
    uni.reLaunch({ url: `/pages/login/register-parent?from=wechat${phoneQ}` })
    return false
  }
  if (p.login_channel === 'wechat' && !p.account_ready) {
    uni.redirectTo({ url: '/pages/login/complete-parent?from=wechat' })
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

/**
 * @deprecated 家长请使用 registerParentSms（POST /api/auth/sms/register）
 */
export async function registerParent() {
  throw new Error('家长请使用验证码注册')
}

/** 孩子是否仍需完成登录后引导（onboarding） */
export async function studentNeedsOnboarding(userId) {
  try {
    const profile = await fetchProfile(userId)
    const ob = profile.profile_json?.onboarding || {}
    if (ob.completed_at || profile.onboarding_completed) return false
    // 新学员已完成天赋测评但未写入 completed_at（如从首页直接测评）→ 不再重复引导
    const studentType = ob.student_type || 'new'
    if (studentType !== 'returning') {
      if (profile.latest_assessment_id || profile.talent_source === 'assessment') return false
      if (ob.talent_test_done) return false
    }
    return true
  } catch (e) {
    if (isFreshLogin()) return false
    return true
  }
}

