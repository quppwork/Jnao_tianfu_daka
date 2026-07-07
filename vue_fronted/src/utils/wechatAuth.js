/** 微信内 H5 家长登录辅助 */

export function isWeChatBrowser() {
  if (typeof navigator === 'undefined') return false
  return /MicroMessenger/i.test(navigator.userAgent || '')
}

const SKIP_WECHAT_AUTO_KEY = 'jnao_skip_wechat_oauth'
const WECHAT_OAUTH_FAIL_KEY = 'jnao_wechat_oauth_fail_until'

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

export function readWechatError() {
  try {
    const params = new URLSearchParams(window.location.search)
    return params.get('wx_error') || ''
  } catch (_) {
    return ''
  }
}

export function shouldAutoWechatOAuth() {
  if (!isWeChatBrowser()) return false
  try {
    if (sessionStorage.getItem(SKIP_WECHAT_AUTO_KEY) === '1') return false
    if (wechatOAuthInCooldown()) return false
    const params = new URLSearchParams(window.location.search)
    if (params.get('wx') === '1') return false
    if (params.get('manual') === '1') return false
    if (params.get('wx_error')) return false
    return true
  } catch (_) {
    return false
  }
}

export function wechatLoginRedirectUrl() {
  return `${window.location.origin}${window.location.pathname}?from=mp`
}

export async function startWechatOAuth(fetchOAuthUrl) {
  const redirect = wechatLoginRedirectUrl()
  const data = await fetchOAuthUrl(redirect)
  if (data?.url) {
    window.location.href = data.url
    return true
  }
  return false
}

export function readWechatCallbackParams() {
  try {
    const params = new URLSearchParams(window.location.search)
    if (params.get('wx') !== '1') return null
    return {
      sessionToken: params.get('session_token') || '',
      userId: params.get('user_id') || '',
      nextStep: params.get('next_step') || 'home',
      bindTicket: params.get('bind_ticket') || '',
      role: params.get('role') || 'parent',
    }
  } catch (_) {
    return null
  }
}

export function clearWechatQueryFromUrl() {
  try {
    const url = new URL(window.location.href)
    ;['wx', 'session_token', 'user_id', 'next_step', 'bind_ticket', 'role', 'wx_error', 'manual'].forEach((k) => url.searchParams.delete(k))
    window.history.replaceState({}, '', url.pathname + (url.search || ''))
  } catch (_) { /* ignore */ }
}

export function redirectParentNextStep(nextStep, bindTicket = '', bindMobileUrl = '') {
  if (nextStep === 'bind-phone') {
    if (bindMobileUrl) {
      window.location.href = bindMobileUrl
      return
    }
    const q = bindTicket ? `?bind_ticket=${encodeURIComponent(bindTicket)}` : ''
    uni.redirectTo({ url: `/pages/login/bind-phone${q}` })
    return
  }
  if (nextStep === 'complete-profile') {
    uni.redirectTo({ url: '/pages/login/complete-parent?from=wechat' })
    return
  }
  uni.redirectTo({ url: '/pages/parent/index' })
}
