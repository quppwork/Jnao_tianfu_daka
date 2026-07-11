/** 微信内 H5 家长登录辅助 */

export function isWeChatBrowser() {
  if (typeof navigator === 'undefined') return false
  return /MicroMessenger/i.test(navigator.userAgent || '')
}

const SKIP_WECHAT_AUTO_KEY = 'jnao_skip_wechat_oauth'
const WECHAT_OAUTH_FAIL_KEY = 'jnao_wechat_oauth_fail_until'
const BROWSER_LOGIN_KEY = 'jnao_browser_login'

/** 用户主动选择手机号/密码登录时调用，本会话内不再自动跳 OAuth */
export function skipWechatAutoLogin() {
  try {
    sessionStorage.setItem(SKIP_WECHAT_AUTO_KEY, '1')
  } catch (_) { /* ignore */ }
}

/** OAuth 刚失败时调用，避免反复自动跳转 */
export function markWechatOAuthFailed(cooldownMs = 120000) {
  skipWechatAutoLogin()
  try {
    sessionStorage.setItem(WECHAT_OAUTH_FAIL_KEY, String(Date.now() + cooldownMs))
  } catch (_) { /* ignore */ }
}

function wechatOAuthInCooldown() {
  try {
    const until = parseInt(sessionStorage.getItem(WECHAT_OAUTH_FAIL_KEY) || '0', 10)
    return until > Date.now()
  } catch (_) {
    return false
  }
}

/** 合并 URL search、hash 查询串与 uni-app onLoad 参数 */
export function readLandingQueryParams(pageOpts = null) {
  const merged = new URLSearchParams()
  try {
    const url = new URL(window.location.href)
    url.searchParams.forEach((v, k) => merged.set(k, v))
    const hash = url.hash || ''
    const qIdx = hash.indexOf('?')
    if (qIdx >= 0) {
      new URLSearchParams(hash.slice(qIdx + 1)).forEach((v, k) => {
        if (!merged.has(k)) merged.set(k, v)
      })
    }
  } catch (_) { /* ignore */ }
  if (pageOpts && typeof pageOpts === 'object') {
    for (const [k, v] of Object.entries(pageOpts)) {
      if (v != null && String(v).trim() && !merged.has(k)) {
        merged.set(k, String(v).trim())
      }
    }
  }
  return merged
}

function pickQuery(params, ...keys) {
  for (const k of keys) {
    const v = params.get(k)
    if (v != null && String(v).trim()) return String(v).trim()
  }
  return ''
}

export function readWechatError(pageOpts = null) {
  try {
    return pickQuery(readLandingQueryParams(pageOpts), 'wx_error') || ''
  } catch (_) {
    return ''
  }
}

/** 用户点击「微信一键登录」时可清除失败冷却 */
export function clearWechatOAuthCooldown() {
  try {
    sessionStorage.removeItem(WECHAT_OAUTH_FAIL_KEY)
    sessionStorage.removeItem(SKIP_WECHAT_AUTO_KEY)
  } catch (_) { /* ignore */ }
}

export function clearBrowserLoginPreference() {
  try {
    sessionStorage.removeItem(BROWSER_LOGIN_KEY)
  } catch (_) { /* ignore */ }
}

export function setBrowserLoginPreference() {
  skipWechatAutoLogin()
  try {
    sessionStorage.setItem(BROWSER_LOGIN_KEY, '1')
  } catch (_) { /* ignore */ }
}

export function hasBrowserLoginPreference() {
  try {
    return sessionStorage.getItem(BROWSER_LOGIN_KEY) === '1'
  } catch (_) {
    return false
  }
}

export function shouldAutoWechatOAuth() {
  // 已改为仅手动点击，不再自动跳转 OAuth
  return false
}

export function wechatLoginRedirectUrl() {
  return `${window.location.origin}${window.location.pathname}?from=mp`
}

let _cachedOAuthUrl = ''
let _cachedOAuthAt = 0
const OAUTH_URL_CACHE_MS = 240000

/** 微信内进入登录页时预取 OAuth 链接，点击按钮可立即跳转 */
export async function prefetchWechatOAuthUrl(fetchOAuthUrl) {
  try {
    const redirect = wechatLoginRedirectUrl()
    const data = await fetchOAuthUrl(redirect)
    if (data?.url) {
      _cachedOAuthUrl = data.url
      _cachedOAuthAt = Date.now()
    }
    return data
  } catch (_) {
    return null
  }
}

function takeCachedOAuthUrl() {
  if (_cachedOAuthUrl && Date.now() - _cachedOAuthAt < OAUTH_URL_CACHE_MS) {
    const url = _cachedOAuthUrl
    _cachedOAuthUrl = ''
    _cachedOAuthAt = 0
    return url
  }
  _cachedOAuthUrl = ''
  _cachedOAuthAt = 0
  return ''
}

export async function startWechatOAuth(fetchOAuthUrl) {
  clearBrowserLoginPreference()
  let url = takeCachedOAuthUrl()
  if (!url) {
    const redirect = wechatLoginRedirectUrl()
    const data = await fetchOAuthUrl(redirect)
    url = data?.url || ''
  }
  if (url) {
    window.location.replace(url)
    return true
  }
  return false
}

export function readExternalBindReturn(pageOpts = null) {
  try {
    const params = readLandingQueryParams(pageOpts)
    if (params.get('from') !== 'mp') return null
    const bindTicket = params.get('bind_ticket') || ''
    if (!bindTicket) return null
    return { bindTicket }
  } catch (_) {
    return null
  }
}

export function readWechatCallbackParams(pageOpts = null) {
  try {
    const params = readLandingQueryParams(pageOpts)
    if (params.get('wx') !== '1') return null
    return {
      loginTicket: pickQuery(params, 'login_ticket'),
      userId: pickQuery(params, 'user_id'),
      nextStep: pickQuery(params, 'next_step') || 'home',
      bindTicket: pickQuery(params, 'bind_ticket'),
      role: pickQuery(params, 'role') || 'parent',
    }
  } catch (_) {
    return null
  }
}

export function clearWechatQueryFromUrl() {
  try {
    const url = new URL(window.location.href)
    const stripKeys = [
      'wx', 'login_ticket', 'session_token', 'user_id', 'next_step',
      'bind_ticket', 'role', 'wx_error', 'manual', 'from',
    ]
    stripKeys.forEach((k) => url.searchParams.delete(k))
    let hash = url.hash || ''
    const qIdx = hash.indexOf('?')
    if (qIdx >= 0) {
      const route = hash.slice(0, qIdx)
      const hq = new URLSearchParams(hash.slice(qIdx + 1))
      stripKeys.forEach((k) => hq.delete(k))
      const rest = hq.toString()
      hash = rest ? `${route}?${rest}` : route
      url.hash = hash
    }
    const search = url.searchParams.toString()
    window.history.replaceState(
      {},
      '',
      url.pathname + (search ? `?${search}` : '') + (url.hash || ''),
    )
  } catch (_) { /* ignore */ }
}

export function redirectToParentRegister(bindTicket = '') {
  const q = bindTicket
    ? `?from=wechat&bind_ticket=${encodeURIComponent(bindTicket)}`
    : ''
  uni.reLaunch({ url: `/pages/login/register-parent${q}` })
}

export function redirectParentNextStep(nextStep, bindTicket = '') {
  if (nextStep === 'bind-phone') {
    redirectToParentRegister(bindTicket)
    return
  }
  if (nextStep === 'complete-profile') {
    uni.reLaunch({ url: '/pages/login/complete-parent?from=wechat' })
    return
  }
  uni.reLaunch({ url: '/pages/parent/index' })
}
