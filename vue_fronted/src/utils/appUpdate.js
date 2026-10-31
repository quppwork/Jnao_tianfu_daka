/**
 * 发版 / 维护探测 — 对比 build_id、维护模式、force_logout
 */

import { clearAllAuthSessions } from './appSession.js'

const BUILD_KEY = 'jnao_build_id'
const FORCE_LOGOUT_FLAG_KEY = 'jnao_force_logout_seen'
const DRAFT_KEY = 'jnao_page_draft'
const POLL_MS = 5 * 60 * 1000
let bannerEl = null
let maintenanceEl = null
let pollTimer = null

function saveDraftSnapshot() {
  try {
    const draft = {}
    document.querySelectorAll('textarea, input[type="text"], input:not([type])').forEach((el, i) => {
      if (el.value && el.offsetParent !== null) {
        draft[`f${i}`] = el.value
      }
    })
    if (Object.keys(draft).length) {
      sessionStorage.setItem(DRAFT_KEY, JSON.stringify(draft))
    }
  } catch (_) { /* ignore */ }
}

function restoreDraftSnapshot() {
  try {
    const raw = sessionStorage.getItem(DRAFT_KEY)
    if (!raw) return
    sessionStorage.removeItem(DRAFT_KEY)
    const draft = JSON.parse(raw)
    document.querySelectorAll('textarea, input[type="text"], input:not([type])').forEach((el, i) => {
      const v = draft[`f${i}`]
      if (v && !el.value) el.value = v
    })
  } catch (_) { /* ignore */ }
}

function showUpdateBanner(message, onReload) {
  if (bannerEl || typeof document === 'undefined') return
  bannerEl = document.createElement('div')
  bannerEl.setAttribute('data-jnao-update-banner', '1')
  Object.assign(bannerEl.style, {
    position: 'fixed',
    left: '0',
    right: '0',
    bottom: '0',
    zIndex: '99999',
    background: 'rgba(15,23,42,0.95)',
    color: '#fff',
    padding: '12px 16px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: '12px',
    fontSize: '13px',
    boxShadow: '0 -4px 20px rgba(0,0,0,0.3)',
  })
  const text = document.createElement('span')
  text.textContent = message || '发现新版本，刷新后可继续使用最新功能'
  const btn = document.createElement('button')
  btn.textContent = '立即刷新'
  Object.assign(btn.style, {
    background: '#f59e0b',
    color: '#fff',
    border: 'none',
    borderRadius: '8px',
    padding: '8px 14px',
    fontSize: '13px',
    cursor: 'pointer',
    flexShrink: '0',
  })
  btn.onclick = () => {
    saveDraftSnapshot()
    if (typeof onReload === 'function') onReload()
    else window.location.reload()
  }
  bannerEl.appendChild(text)
  bannerEl.appendChild(btn)
  document.body.appendChild(bannerEl)
}

function showMaintenanceOverlay(message) {
  if (typeof document === 'undefined') return
  if (maintenanceEl) {
    const t = maintenanceEl.querySelector('[data-msg]')
    if (t) t.textContent = message || '系统升级中，请稍后再试'
    return
  }
  maintenanceEl = document.createElement('div')
  maintenanceEl.setAttribute('data-jnao-maintenance', '1')
  Object.assign(maintenanceEl.style, {
    position: 'fixed',
    inset: '0',
    zIndex: '100000',
    background: 'rgba(15,23,42,0.92)',
    color: '#fff',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '12px',
    padding: '24px',
    textAlign: 'center',
    fontSize: '15px',
  })
  const title = document.createElement('div')
  title.textContent = '系统维护'
  title.style.fontSize = '20px'
  title.style.fontWeight = '700'
  const msg = document.createElement('div')
  msg.setAttribute('data-msg', '1')
  msg.textContent = message || '系统升级中，请稍后再试'
  msg.style.opacity = '0.85'
  msg.style.maxWidth = '320px'
  msg.style.lineHeight = '1.5'
  maintenanceEl.appendChild(title)
  maintenanceEl.appendChild(msg)
  document.body.appendChild(maintenanceEl)
}

function hideMaintenanceOverlay() {
  if (maintenanceEl && maintenanceEl.parentNode) {
    maintenanceEl.parentNode.removeChild(maintenanceEl)
  }
  maintenanceEl = null
}

function applyForceLogoutIfNeeded(data) {
  if (!data?.force_logout) {
    try { localStorage.removeItem(FORCE_LOGOUT_FLAG_KEY) } catch (_) { /* ignore */ }
    return false
  }
  const stamp = `${data.build_id || ''}:${data.boot_id || '1'}`
  let seen = ''
  try { seen = localStorage.getItem(FORCE_LOGOUT_FLAG_KEY) || '' } catch (_) { /* ignore */ }
  if (seen === stamp) return false
  clearAllAuthSessions()
  try {
    localStorage.setItem(FORCE_LOGOUT_FLAG_KEY, stamp)
  } catch (_) { /* ignore */ }
  console.info('[auth] 发版要求重新登录（force_logout）')
  return true
}

async function checkVersion() {
  try {
    const res = await fetch('/api/meta/version', { cache: 'no-store' })
    if (!res.ok) return
    const data = await res.json()

    if (data.maintenance) {
      showMaintenanceOverlay(data.maintenance_message)
      return
    }
    hideMaintenanceOverlay()

    const loggedOut = applyForceLogoutIfNeeded(data)

    const buildId = data.build_id || data.version || 'dev'
    const stored = localStorage.getItem(BUILD_KEY)
    if (!stored) {
      localStorage.setItem(BUILD_KEY, buildId)
      if (loggedOut) {
        window.location.href = '/pages/login/index'
      }
      return
    }
    if (stored !== buildId) {
      showUpdateBanner(
        loggedOut
          ? '系统已更新，请刷新后重新登录'
          : '发现新版本，刷新后可继续使用最新功能',
        () => {
          localStorage.setItem(BUILD_KEY, buildId)
          window.location.reload()
        },
      )
      return
    }
    if (loggedOut) {
      window.location.href = '/pages/login/index'
    }
  } catch (_) { /* ignore */ }
}

export function startAppUpdateWatcher() {
  if (typeof window === 'undefined') return
  restoreDraftSnapshot()
  checkVersion()
  if (pollTimer) clearInterval(pollTimer)
  pollTimer = setInterval(checkVersion, POLL_MS)
}

export function stopAppUpdateWatcher() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}
