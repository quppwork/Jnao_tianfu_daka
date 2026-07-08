/**
 * 登录流程状态机 — 鉴权 /  settling / 跳转，session 已写入时不报失败
 */
import { computed, ref } from 'vue'
import { getLoggedInUserId, getSessionToken } from './userApi.js'

export function minDelay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

export function hasValidSession() {
  return !!(getSessionToken() && getLoggedInUserId())
}

export function inferHomeFromSession() {
  try {
    const raw = localStorage.getItem('jnao_user')
    const role = raw ? JSON.parse(raw).role : null
    if (role === 'parent') return '/pages/parent/index'
    if (role === 'student') return '/pages/index'
    if (role === 'admin') return '/pages/admin/index'
  } catch (_) { /* ignore */ }
  return '/pages/login/index'
}

export function useLoginFlow() {
  const phase = ref('idle')
  const overlayText = ref('')

  const loginBusy = computed(() => phase.value !== 'idle')

  function setPhase(next, text = '') {
    phase.value = next
    overlayText.value = text
  }

  function resetPhase() {
    setPhase('idle')
  }

  async function runAuthenticating(fn, { busyText = '正在登录…' } = {}) {
    if (phase.value !== 'idle') return null
    setPhase('authenticating', busyText)
    try {
      return await fn()
    } catch (e) {
      if (hasValidSession()) {
        return { _sessionFallback: true, error: e }
      }
      resetPhase()
      throw e
    }
  }

  async function completeAfterAuth(navigateFn, { minMs = 400, busyText = '正在进入…' } = {}) {
    setPhase('settling', busyText)
    try {
      await Promise.all([Promise.resolve(navigateFn()), minDelay(minMs)])
    } catch (e) {
      console.warn('[login] post-auth failed, fallback redirect', e?.message || e)
      if (hasValidSession()) {
        uni.reLaunch({ url: inferHomeFromSession() })
      } else {
        throw e
      }
    } finally {
      setPhase('redirecting', busyText)
    }
  }

  return {
    phase,
    overlayText,
    loginBusy,
    setPhase,
    resetPhase,
    runAuthenticating,
    completeAfterAuth,
  }
}
