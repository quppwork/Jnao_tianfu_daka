/** 登录页客户端限流 — 配合服务端黑名单 */

const KEY = 'jnao_login_guard'
const MAX_FAILS = 8
const WINDOW_MS = 10 * 60 * 1000
const LOCK_MS = 15 * 60 * 1000

function load() {
  try {
    return JSON.parse(localStorage.getItem(KEY) || '{}')
  } catch (_) {
    return {}
  }
}

function save(data) {
  try {
    localStorage.setItem(KEY, JSON.stringify(data))
  } catch (_) {}
}

export function getDeviceId() {
  const k = 'jnao_device_id'
  try {
    let id = localStorage.getItem(k)
    if (!id) {
      id = `d_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`
      localStorage.setItem(k, id)
    }
    return id
  } catch (_) {
    return ''
  }
}

export function isLoginBlocked() {
  const s = load()
  const now = Date.now()
  if (s.lockedUntil && now < s.lockedUntil) {
    return { blocked: true, remainSec: Math.ceil((s.lockedUntil - now) / 1000) }
  }
  if (s.windowStart && now - s.windowStart > WINDOW_MS) {
    save({ fails: 0, windowStart: now, lockedUntil: 0 })
  }
  return { blocked: false, remainSec: 0 }
}

export function recordLoginFail() {
  const s = load()
  const now = Date.now()
  if (!s.windowStart || now - s.windowStart > WINDOW_MS) {
    s.fails = 0
    s.windowStart = now
  }
  s.fails = (s.fails || 0) + 1
  if (s.fails >= MAX_FAILS) {
    s.lockedUntil = now + LOCK_MS
  }
  save(s)
  return isLoginBlocked()
}

export function clearLoginGuard() {
  try {
    localStorage.removeItem(KEY)
  } catch (_) {}
}

export function authHeaders() {
  const did = getDeviceId()
  return did ? { 'X-Device-Id': did } : {}
}
