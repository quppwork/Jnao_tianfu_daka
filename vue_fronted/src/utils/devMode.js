const DEV_KEY = 'jnao_dev_mode'

/** 本地 vite dev 为 true；Docker/生产 npm run build 为 false */
export function isDevToolsAvailable() {
  return import.meta.env.DEV
}

export function getDevMode() {
  if (!isDevToolsAvailable()) return false
  try {
    return sessionStorage.getItem(DEV_KEY) === '1'
  } catch (_) {
    return false
  }
}

export function setDevMode(on) {
  if (!isDevToolsAvailable()) return
  try {
    if (on) sessionStorage.setItem(DEV_KEY, '1')
    else sessionStorage.removeItem(DEV_KEY)
  } catch (_) { /* ignore */ }
}
