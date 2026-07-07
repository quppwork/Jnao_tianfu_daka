/** 微信内 H5 家长登录辅助 */

export function isWeChatBrowser() {
  if (typeof navigator === 'undefined') return false
  return /MicroMessenger/i.test(navigator.userAgent || '')
}

export function shouldAutoWechatOAuth() {
  if (!isWeChatBrowser()) return false
  try {
    const params = new URLSearchParams(window.location.search)
    if (params.get('wx') === '1') return false
    if (params.get('from') === 'mp') return true
    return params.get('wechat') === '1'
  } catch (_) {
    return false
  }
}

export async function startWechatOAuth(apiJson) {
  const redirect = encodeURIComponent(window.location.href.split('?')[0] + '?from=mp')
  const data = await apiJson(`/api/auth/wechat/oauth-url?redirect=${redirect}`)
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
    ;['wx', 'session_token', 'user_id', 'next_step', 'bind_ticket', 'role'].forEach((k) => url.searchParams.delete(k))
    window.history.replaceState({}, '', url.pathname + (url.search || ''))
  } catch (_) { /* ignore */ }
}

export function redirectParentNextStep(nextStep, bindTicket = '') {
  if (nextStep === 'bind-phone') {
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
