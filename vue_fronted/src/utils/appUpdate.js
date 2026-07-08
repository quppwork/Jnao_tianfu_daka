/** 前端热更新探测 — 对比 build_id，提示用户刷新 */

const BUILD_KEY = 'jnao_build_id'
const DRAFT_KEY = 'jnao_page_draft'
const POLL_MS = 5 * 60 * 1000
let bannerEl = null
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

function showUpdateBanner(onReload) {
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
  text.textContent = '发现新版本，刷新后可继续使用最新功能'
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

async function checkVersion() {
  try {
    const res = await fetch('/api/meta/version', { cache: 'no-store' })
    if (!res.ok) return
    const data = await res.json()
    const buildId = data.build_id || data.version || 'dev'
    const stored = localStorage.getItem(BUILD_KEY)
    if (!stored) {
      localStorage.setItem(BUILD_KEY, buildId)
      return
    }
    if (stored !== buildId) {
      showUpdateBanner(() => {
        localStorage.setItem(BUILD_KEY, buildId)
        window.location.reload()
      })
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
